import json
import os
from datetime import datetime
from io import BytesIO

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_babel import gettext
from flask_login import current_user, login_required

from app import db, csrf
from app.models import ChartDrawing
from app.commons.chart_drawings import (
    compute_drawings_view,
    drawings_to_json,
    parse_drawings_json,
)
from app.commons.chart_generator import FIELD_SIZES

from .chart_drawing_forms import ChartDrawingEditForm

main_chart_drawing = Blueprint('main_chart_drawing', __name__)

MAX_DRAWINGS_PER_USER = 200
MAX_NAME_LEN = 128


def _get_own_drawing_or_404(drawing_id):
    drawing = ChartDrawing.query.filter_by(id=drawing_id, user_id=current_user.id).first()
    if drawing is None:
        abort(404)
    return drawing


def _user_drawing_count():
    return ChartDrawing.query.filter_by(user_id=current_user.id).count()


def _iso(dt):
    return dt.isoformat() if dt else None


def _apply_definition(drawing, drawings):
    drawing.definition = drawings_to_json(drawings)
    drawing.item_count = len(drawings)
    drawing.center_ra, drawing.center_dec, drawing.fld_size = compute_drawings_view(drawings, FIELD_SIZES)
    drawing.update_date = datetime.now()


def _new_drawing(name, drawings, description=None):
    now = datetime.now()
    drawing = ChartDrawing(
        user_id=current_user.id,
        name=name[:MAX_NAME_LEN],
        description=description,
        is_public=False,
        create_date=now,
    )
    _apply_definition(drawing, drawings)
    db.session.add(drawing)
    db.session.commit()
    return drawing


def chart_url_for_drawing(drawing, external=False):
    params = {'dset': drawing.id}
    if drawing.center_ra is not None and drawing.center_dec is not None:
        params.update(ra=round(drawing.center_ra, 6), dec=round(drawing.center_dec, 6), fsz=drawing.fld_size)
    return url_for('main_chart.chart', _external=external, **params)


def _drawing_meta(drawing):
    return {
        'id': drawing.id,
        'name': drawing.name,
        'item_count': drawing.item_count,
        'is_public': drawing.is_public,
        'update_date': _iso(drawing.update_date),
    }


# ---------------------------------------------------------------------------------------------
# JSON API used by the chart.
#
# CSRF: these endpoints are exempt from the form CSRF token (it expires while a chart page stays
# open for hours) and instead require an application/json body, which a cross-site form cannot
# send without a CORS preflight.
# ---------------------------------------------------------------------------------------------

def _json_body_or_400():
    if not request.is_json:
        abort(400)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    return data


def _parse_definition_or_none(data):
    definition = data.get('definition')
    if not isinstance(definition, dict):
        return None
    drawings = parse_drawings_json(json.dumps(definition))
    return drawings or None


def _json_error(message, status):
    return jsonify(error=message), status


@main_chart_drawing.route('/chart/drawings', methods=['GET'])
@login_required
def api_chart_drawings():
    drawings = (ChartDrawing.query
                .filter_by(user_id=current_user.id)
                .order_by(ChartDrawing.update_date.desc())
                .all())
    return jsonify(items=[_drawing_meta(d) for d in drawings])


@main_chart_drawing.route('/chart/drawings/<int:drawing_id>', methods=['GET'])
def api_chart_drawing(drawing_id):
    drawing = ChartDrawing.query.get(drawing_id)
    if drawing is None or not drawing.is_readable_by(current_user):
        abort(404)
    result = _drawing_meta(drawing)
    result.update(
        is_owner=drawing.is_owned_by(current_user),
        owner=drawing.user.user_name if drawing.user else None,
        center_ra=drawing.center_ra,
        center_dec=drawing.center_dec,
        fld_size=drawing.fld_size,
        definition=json.loads(drawing.definition),
    )
    return jsonify(result)


@main_chart_drawing.route('/chart/drawings', methods=['POST'])
@login_required
@csrf.exempt
def api_chart_drawing_create():
    data = _json_body_or_400()
    name = str(data.get('name') or '').strip()
    if not name:
        return _json_error(gettext('Name is required.'), 400)
    drawings = _parse_definition_or_none(data)
    if drawings is None:
        return _json_error(gettext('Nothing to save.'), 400)
    if _user_drawing_count() >= MAX_DRAWINGS_PER_USER:
        return _json_error(gettext('Maximum number of saved drawings reached.'), 400)
    drawing = _new_drawing(name, drawings)
    return jsonify(_drawing_meta(drawing)), 201


@main_chart_drawing.route('/chart/drawings/<int:drawing_id>', methods=['PUT'])
@login_required
@csrf.exempt
def api_chart_drawing_update(drawing_id):
    data = _json_body_or_400()
    drawing = _get_own_drawing_or_404(drawing_id)
    drawings = _parse_definition_or_none(data)
    if drawings is None:
        return _json_error(gettext('Nothing to save.'), 400)
    # Optimistic locking: the client sends the version it started from.
    if not data.get('force') and data.get('base_update_date') != _iso(drawing.update_date):
        return jsonify(error='conflict', update_date=_iso(drawing.update_date)), 409
    _apply_definition(drawing, drawings)
    db.session.commit()
    return jsonify(_drawing_meta(drawing))


# ---------------------------------------------------------------------------------------------
# Management pages
# ---------------------------------------------------------------------------------------------

@main_chart_drawing.route('/chart-drawings', methods=['GET'])
@login_required
def chart_drawings():
    drawings = (ChartDrawing.query
                .filter_by(user_id=current_user.id)
                .order_by(ChartDrawing.update_date.desc())
                .all())
    return render_template('main/chart/chart_drawings.html', chart_drawings=drawings,
                           chart_url_for_drawing=chart_url_for_drawing)


@main_chart_drawing.route('/chart-drawing/<int:drawing_id>/edit', methods=['GET', 'POST'])
@login_required
def chart_drawing_edit(drawing_id):
    drawing = _get_own_drawing_or_404(drawing_id)
    form = ChartDrawingEditForm()
    if request.method == 'GET':
        form.name.data = drawing.name
        form.description.data = drawing.description
        form.is_public.data = drawing.is_public
    elif form.validate_on_submit():
        drawing.name = form.name.data.strip()
        drawing.description = form.description.data
        drawing.is_public = form.is_public.data
        drawing.update_date = datetime.now()
        db.session.commit()
        flash(gettext('Drawing successfully updated'), 'form-success')
        return redirect(url_for('main_chart_drawing.chart_drawing_edit', drawing_id=drawing.id))
    share_url = chart_url_for_drawing(drawing, external=True)
    return render_template('main/chart/chart_drawing_edit.html', form=form, chart_drawing=drawing,
                           chart_url=chart_url_for_drawing(drawing), share_url=share_url)


@main_chart_drawing.route('/chart-drawing/<int:drawing_id>/delete', methods=['POST'])
@login_required
def chart_drawing_delete(drawing_id):
    drawing = _get_own_drawing_or_404(drawing_id)
    db.session.delete(drawing)
    db.session.commit()
    flash(gettext('Drawing was deleted'), 'form-success')
    return redirect(url_for('main_chart_drawing.chart_drawings'))


@main_chart_drawing.route('/chart-drawing/<int:drawing_id>/duplicate', methods=['POST'])
@login_required
def chart_drawing_duplicate(drawing_id):
    drawing = _get_own_drawing_or_404(drawing_id)
    if _user_drawing_count() >= MAX_DRAWINGS_PER_USER:
        flash(gettext('Maximum number of saved drawings reached.'), 'form-error')
        return redirect(url_for('main_chart_drawing.chart_drawings'))
    copy = _new_drawing(gettext('Copy of %(name)s', name=drawing.name),
                        parse_drawings_json(drawing.definition), drawing.description)
    flash(gettext('Drawing was duplicated'), 'form-success')
    return redirect(url_for('main_chart_drawing.chart_drawing_edit', drawing_id=copy.id))


@main_chart_drawing.route('/chart-drawing/<int:drawing_id>/export', methods=['GET'])
@login_required
def chart_drawing_export(drawing_id):
    drawing = _get_own_drawing_or_404(drawing_id)
    data = json.loads(drawing.definition)
    data['name'] = drawing.name
    if drawing.description:
        data['description'] = drawing.description
    mem = BytesIO(json.dumps(data, ensure_ascii=False, indent=1).encode('utf-8'))
    return send_file(mem, as_attachment=True, mimetype='application/json',
                     download_name='drawing-{}.json'.format(drawing.id))


@main_chart_drawing.route('/chart-drawings/import', methods=['POST'])
@login_required
def chart_drawing_import():
    file = request.files.get('file')
    if file is None or file.filename == '':
        flash(gettext('No selected file'), 'form-error')
        return redirect(url_for('main_chart_drawing.chart_drawings'))
    payload = file.read().decode('utf-8', errors='replace')
    drawings = parse_drawings_json(payload)
    if not drawings:
        flash(gettext('The file does not contain any valid drawings.'), 'form-error')
        return redirect(url_for('main_chart_drawing.chart_drawings'))
    if _user_drawing_count() >= MAX_DRAWINGS_PER_USER:
        flash(gettext('Maximum number of saved drawings reached.'), 'form-error')
        return redirect(url_for('main_chart_drawing.chart_drawings'))
    try:
        meta = json.loads(payload)
    except ValueError:
        meta = None
    if not isinstance(meta, dict):
        meta = {}
    name = str(meta.get('name') or os.path.splitext(file.filename)[0] or gettext('Imported drawing')).strip()
    description = meta.get('description') if isinstance(meta.get('description'), str) else None
    drawing = _new_drawing(name, drawings, description)
    flash(gettext('Drawing was imported'), 'form-success')
    return redirect(url_for('main_chart_drawing.chart_drawing_edit', drawing_id=drawing.id))
