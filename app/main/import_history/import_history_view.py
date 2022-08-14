from datetime import datetime

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app import db

from app.models import (
    ImportHistoryRec,
    ImportType,
    ImportHistoryRecStatus,
    Location,
    ObservingSession,
    Observation,
    Telescope,
    Eyepiece,
    Filter,
    Lens
)

from app.commons.pagination import Pagination, get_page_parameter, get_page_args
from app.commons.search_utils import process_paginated_session_search, get_items_per_page

main_import_history = Blueprint('main_import_history', __name__)

from .import_history_forms import SearchImportHistoryRecsForm


@main_import_history.route('/import-history-records', methods=['GET', 'POST'])
@login_required
def import_history_records():
    search_form = SearchImportHistoryRecsForm()

    ret, page, _ = process_paginated_session_search('import_history_search_page', None, [
        ('import_history_search', search_form.q),
        ('items_per_page', search_form.items_per_page)
    ])

    per_page = get_items_per_page(search_form.items_per_page)

    if not ret:
        return redirect(url_for('main_import_history.import_history_records'))

    offset = (page - 1) * per_page

    import_type_code = request.args.get('type')
    import_type = None

    if import_type_code == 'obs':
        import_type = ImportType.OBSERVATION
    elif import_type_code == 'sess':
        import_type = ImportType.SESSION

    import_history_recs = ImportHistoryRec.query.filter_by(create_by=current_user.id)
    if import_type:
        import_history_recs = import_history_recs.filter_by(import_type=import_type)

    import_history_recs = import_history_recs.order_by(ImportHistoryRec.create_date.desc())
    import_history_recs_for_render = import_history_recs.limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=import_history_recs.count(), search=False, rec_name='import_history_recs', css_framework='semantic', not_passed_args='back')

    return render_template('main/import_history/import_history_records.html', import_history_recs=import_history_recs_for_render, pagination=pagination, search_form=search_form)


@main_import_history.route('/import-history-record/<int:import_history_rec_id>', methods=['GET'])
@main_import_history.route('/import-history-record/<int:import_history_rec_id>/info', methods=['GET'])
@login_required
def import_history_record_info(import_history_rec_id):
    """View a import history rec."""
    import_history_rec = ImportHistoryRec.query.filter_by(id=import_history_rec_id).first()
    if import_history_rec is None:
        abort(404)
    if import_history_rec.create_by != current_user.id:
        abort(404)

    imp_obs_sess_count = ObservingSession.query.filter_by(import_history_rec_id=import_history_rec_id).count()
    imp_observations_count = Observation.query.filter_by(import_history_rec_id=import_history_rec_id).count()

    can_delete_observations = import_history_rec.status != ImportHistoryRecStatus.DELETED and \
                              (imp_obs_sess_count > 0 or imp_observations_count > 0)
    return render_template('main/import_history/import_history_record_info.html', import_history_rec=import_history_rec,
                           can_delete_observations=can_delete_observations)


@main_import_history.route('/delete-imported-observing-sessions/<int:import_history_rec_id>', methods=['GET'])
@login_required
def delete_imported_observations(import_history_rec_id):
    """Request deletion of imported observing_session."""
    import_history_rec = ImportHistoryRec.query.filter_by(id=import_history_rec_id).first()
    if import_history_rec is None:
        abort(404)
    if import_history_rec.create_by != current_user.id:
        abort(404)

    observations = Observation.query.filter_by(import_history_rec_id=import_history_rec_id).all()
    if len(observations) > 0:
        for observation in observations:
            db.session.delete(observation)
        import_history_rec.status = ImportHistoryRecStatus.DELETED
        db.session.commit()
        flash('{} imported standalone observations was deleted'.format(len(observations)), 'form-success')

    observing_sessions = ObservingSession.query.filter_by(import_history_rec_id=import_history_rec_id).all()
    if len(observing_sessions) > 0:
        for observing_session in observing_sessions:
            db.session.delete(observing_session)
        import_history_rec.status = ImportHistoryRecStatus.DELETED
        db.session.commit()
        flash('{} imported observing sessions was deleted'.format(len(observing_sessions)), 'form-success')

    telescopes = Telescope.query.filter_by(import_history_rec_id=import_history_rec_id).all()
    if len(telescopes) > 0:
        for telescope in telescopes:
            if Observation.query.filter_by(telescope_id=telescope.id).count() == 0:
                db.session.delete(telescope)
        import_history_rec.status = ImportHistoryRecStatus.DELETED
        db.session.commit()
        flash('{} imported telescopes was deleted'.format(len(telescopes)), 'form-success')

    eyepieces = Eyepiece.query.filter_by(import_history_rec_id=import_history_rec_id).all()
    if len(eyepieces) > 0:
        for eyepiece in eyepieces:
            if Observation.query.filter_by(eyepiece_id=eyepiece.id).count() == 0:
                db.session.delete(eyepiece)
        import_history_rec.status = ImportHistoryRecStatus.DELETED
        db.session.commit()
        flash('{} imported eyepeces was deleted'.format(len(eyepieces)), 'form-success')

    filters = Filter.query.filter_by(import_history_rec_id=import_history_rec_id).all()
    if len(filters) > 0:
        for filter in filters:
            if Observation.query.filter_by(filter_id=filter.id).count() == 0:
                db.session.delete(filter)
        import_history_rec.status = ImportHistoryRecStatus.DELETED
        db.session.commit()
        flash('{} imported filters was deleted'.format(len(filters)), 'form-success')

    lenses = Lens.query.filter_by(import_history_rec_id=import_history_rec_id).all()
    if len(lenses) > 0:
        for lens in lenses:
            if Observation.query.filter_by(lens_id=lens.id).count() == 0:
                db.session.delete(lens)
        import_history_rec.status = ImportHistoryRecStatus.DELETED
        db.session.commit()
        flash('{} imported filters was deleted'.format(len(lenses)), 'form-success')

    locations = Location.query.filter_by(import_history_rec_id=import_history_rec_id).all()
    if len(locations) > 0:
        for location in locations:
            if ObservingSession.query.filter_by(location_id=location.id).count():
                db.session.delete(location)
        import_history_rec.status = ImportHistoryRecStatus.DELETED
        db.session.commit()
        flash('{} imported locations was deleted'.format(len(locations)), 'form-success')

    return redirect(url_for('main_import_history.import_history_record_info', import_history_rec_id=import_history_rec_id))
