import os
import re
from datetime import datetime
from io import StringIO, BytesIO
import codecs

from werkzeug.utils import secure_filename

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
)
from flask_login import current_user, login_required
from flask_babel import gettext
from app.compat.flask_rq import get_queue

from app import db

from app.models import (
    ImportHistoryRec,
    ImportHistoryRecStatus,
    ImportType,
    ObservingSession,
)

from .observation_forms import (
    ObservationExportForm,
)

from .observation_export import create_oal_observations
from .observation_import import import_observations
from app.commons.utils import get_about_oal

main_observation = Blueprint('main_observation', __name__)


@main_observation.route('/observation-menu', methods=['GET'])
@login_required
def observation_menu():
    return render_template('main/observation/observation_menu.html')


@main_observation.route('/observation-export', methods=['GET', 'POST'])
@login_required
def observation_export():
    """Export observation."""
    form = ObservationExportForm()
    if request.method == 'POST':
        buf = StringIO()
        buf.write('<?xml version="1.0" encoding="utf-8"?>\n')
        observing_sessions = ObservingSession.query.filter_by(user_id=current_user.id).all()
        oal_observations = create_oal_observations(current_user, observing_sessions)
        oal_observations.export(buf, 0)
        mem = BytesIO()
        mem.write(codecs.BOM_UTF8)
        mem.write(buf.getvalue().encode('utf-8'))
        mem.seek(0)
        return send_file(mem, as_attachment=True,
                         download_name='observations-' + current_user.user_name + '.xml',
                         mimetype='text/xml')
    return render_template('main/observation/observation_export.html', about_oal=get_about_oal())


@main_observation.route('/observation-import', methods=['GET', 'POST'])
@login_required
def observation_import():
    return render_template('main/observation/observation_import.html', about_oal=get_about_oal(), log_warn=[], log_error=[])


@main_observation.route('/observation-import-upload', methods=['GET', 'POST'])
@login_required
def observation_import_upload():
    if 'file' not in request.files:
        flash(gettext('No file part'), 'form-error')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash(gettext('No selected file'))
        return redirect(request.url)
    log_warn, log_error = [], []
    if file:
        filename = secure_filename(file.filename)
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(path)

        import_history_rec = ImportHistoryRec()
        import_history_rec.import_type = ImportType.OBSERVATION
        import_history_rec.status = ImportHistoryRecStatus.PROCESSING
        import_history_rec.create_by = current_user.id
        import_history_rec.create_date = datetime.now()
        db.session.add(import_history_rec)
        db.session.commit()

        encoding = None

        with open(path, 'r', errors='replace') as f:
            firstline = f.readline().rstrip()
            if firstline:
                m = re.search('encoding="(.*)"', firstline)
                if m:
                    encoding = m.group(1).lower()

        if encoding:
            get_queue().enqueue_call(
                _do_import_observations_enc,
                args=(current_user.id, current_user.id, import_history_rec.id, path, encoding),
                timeout=3600
            )
        else:
            get_queue().enqueue_call(
                _do_import_observations,
                args=(current_user.id, current_user.id, import_history_rec.id, path),
                timeout=3600
            )

    flash(gettext('Observations import enqued.'), 'form-success')

    return render_template('main/observation/observation_import.html', about_oal=get_about_oal(), log_warn=log_warn, log_error=log_error)


def _do_import_observations_enc(user_id, import_user_id, import_history_rec_id, path, encoding):
    with codecs.open(path, 'r', encoding=encoding) as oal_file:
        try:
            log_warn, log_error = import_observations(user_id, import_user_id, import_history_rec_id, oal_file)
            _do_process_import_log(log_warn, log_error, import_history_rec_id)
            db.session.commit()
        except:
            db.session.rollback()
        finally:
            db.session.close()


def _do_import_observations(user_id, import_user_id, import_history_rec_id, path):
    with open(path) as oal_file:
        try:
            log_warn, log_error = import_observations(user_id, import_user_id, import_history_rec_id, oal_file)
            _do_process_import_log(log_warn, log_error, import_history_rec_id)
            db.session.commit()
        except:
            db.session.rollback()
        finally:
            db.session.close()


def _do_process_import_log(log_warn, log_error, import_history_rec_id):
    import_history_rec = ImportHistoryRec.query.filter_by(id=import_history_rec_id).first()
    if not import_history_rec:
        return
    import_history_rec.status = ImportHistoryRecStatus.IMPORTED
    if log_warn is not None and log_error is not None:
        log = 'Warnings:\n' + '\n'.join(log_warn) + '\nErrrors:' + '\n'.join(log_error)
        import_history_rec.log = log
        import_history_rec.create_date = datetime.now()
        db.session.add(import_history_rec)
    else:
        db.session.delete(import_history_rec)
