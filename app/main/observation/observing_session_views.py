import os
from datetime import datetime
import base64
from io import StringIO, BytesIO
import codecs
from werkzeug.utils import secure_filename

from flask import (
    abort,
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import current_user, login_required
from flask_babel import gettext

from app import db, csrf

from .observing_session_forms import (
    ObservingSessionNewForm,
    ObservingSessionEditForm,
    ObservingSessionItemsEditForm,
    ObservingSessionExportForm,
    ObservingSessionRunPlanForm,
)

from .observation_export import create_oal_observations
from .observation_import import import_observations

from app.models import (
    Eyepiece,
    Filter,
    Location,
    Observation,
    ObservingSession,
    ObservationTargetType,
    ObsSessionPlanRun,
    Planet,
    Seeing,
    SessionPlan,
    Telescope,
    Transparency,
    User,
)

from app.commons.search_utils import get_items_per_page, ITEMS_PER_PAGE
from app.commons.pagination import Pagination, get_page_parameter
from app.commons.observation_target_utils import set_observation_targets

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_ra_dec_dt_fsz_from_request,
    common_chart_pdf_img,
)
from app.commons.chart_scene import (
    build_scene_v1,
    build_cross_highlight,
    build_circle_highlight,
    ensure_scene_dso_item,
)
from app.commons.dso_utils import (
    CHART_DOUBLE_STAR_PREFIX,
    CHART_COMET_PREFIX,
    CHART_MINOR_PLANET_PREFIX,
)

from app.main.chart.chart_forms import ChartForm
from app.commons.coordinates import *
from app.commons.prevnext_utils import get_default_chart_iframe_url, parse_prefix_obj_id
from app.commons.highlights_list_utils import common_highlights_from_observing_session
from app.commons.utils import get_about_oal

main_observing_session = Blueprint('main_observing_session', __name__)


@main_observing_session.route('/observing-sessions', methods=['GET', 'POST'])
@login_required
def observing_sessions():
    """View observing sessions."""
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    observing_sessions = ObservingSession.query.filter_by(user_id=current_user.id).order_by(ObservingSession.date_from.desc())
    search = False

    obs_sessions_for_render = observing_sessions.limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=observing_sessions.count(), search=search, record_name='observations', css_framework='semantic')
    return render_template('main/observation/observing_sessions.html', observing_sessions=obs_sessions_for_render, pagination=pagination, user=None)


@main_observing_session.route('/user-observing-sessions/<int:user_id>', methods=['GET', 'POST'])
def user_observing_sessions(user_id):
    """View observing sessions of given user."""
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        abort(404)
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    observing_sessions = ObservingSession.query.filter_by(user_id=user_id, is_public=True) \
                                               .order_by(ObservingSession.date_from.desc())
    search = False

    obs_sessions_for_render = observing_sessions.limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=observing_sessions.count(), search=search, record_name='observations', css_framework='semantic')
    return render_template('main/observation/observing_sessions.html', observing_sessions=obs_sessions_for_render, pagination=pagination, user=user)


def _check_observing_session(observing_session, allow_public=False):
    if observing_session is None:
        abort(404)
    if current_user.is_anonymous:
        if observing_session.is_public:
            return False
        abort(404)
    elif observing_session.user_id != current_user.id:
        if allow_public and observing_session.is_public:
            return False
        abort(404)

    return True


@main_observing_session.route('/observing-session/<int:observing_session_id>', methods=['GET'])
@main_observing_session.route('/observing-session/<int:observing_session_id>/info', methods=['GET'])
def observing_session_info(observing_session_id):
    """View a observation info."""
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, allow_public=True)
    location_position_mapy_cz_url = None
    location_position_google_maps_url = None
    if not observing_session.location_id and observing_session.location_position:
        lat, lon = parse_latlon(observing_session.location_position)
        location_position_mapy_cz_url = mapy_cz_url(lon, lat)
        location_position_google_maps_url = google_url(lon, lat)

    show_observ_time = False

    if observing_session.observations:
        ofrom = observing_session.observations[0].date_from
        oto = observing_session.observations[0].date_to
        for o in observing_session.observations:
            if o.date_from != ofrom or o.date_to != oto:
                show_observ_time = True
                break

    return render_template('main/observation/observing_session_info.html', observing_session=observing_session, type='info',
                           is_mine_observing_session=is_mine_observing_session, location_position_mapy_cz_url=location_position_mapy_cz_url,
                           location_position_google_maps_url=location_position_google_maps_url, show_observ_time=show_observ_time)


@main_observing_session.route('/observing-session/<int:observing_session_id>/export', methods=['GET', 'POST'])
def observing_session_export(observing_session_id):
    """Export observation."""
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, allow_public=True)
    user = User.query.filter_by(id=observing_session.user_id).first()
    exp_form = ObservingSessionExportForm()
    if request.method == 'POST':
        buf = StringIO()
        buf.write('<?xml version="1.0" encoding="utf-8"?>\n')
        oal_observations = create_oal_observations(user, [observing_session])
        oal_observations.export(buf, 0)
        mem = BytesIO()
        mem.write(codecs.BOM_UTF8)
        mem.write(buf.getvalue().encode('utf-8'))
        mem.seek(0)
        return send_file(mem, as_attachment=True,
                         download_name='observation-' + user.user_name + '.xml',
                         mimetype='text/xml')

    return render_template('main/observation/observing_session_info.html', exp_form=exp_form, type='imp_exp',
                           observing_session=observing_session, is_mine_observing_session=is_mine_observing_session, about_oal=get_about_oal())


@main_observing_session.route('/observing-session/<int:observing_session_id>/import-upload', methods=['GET', 'POST'])
@login_required
def observing_session_import_upload(observing_session_id):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, allow_public=False)
    if not is_mine_observing_session:
        abort(404)
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
        encoding = None

        with open(path, 'r', errors='replace') as f:
            firstline = f.readline().rstrip()
            if firstline:
                m = re.search('encoding="(.*)"', firstline)
                if m:
                    encoding = m.group(1).lower()

        with codecs.open(path, 'r', encoding=encoding) as oal_file:
            try:
                log_warn, log_error = import_observations(current_user.id, current_user.id, None, oal_file,
                                                          imp_observing_session=observing_session)
                db.session.commit()
            except:
                db.session.rollback()

    flash(gettext('Observing session imported'), 'form-success')

    exp_form = ObservingSessionExportForm()

    return render_template('main/observation/observing_session_info.html', exp_form=exp_form, type='imp_exp',
                           observing_session=observing_session, is_mine_observing_session=is_mine_observing_session, about_oal=get_about_oal(),
                           log_warn=log_warn, log_error=log_error)


@main_observing_session.route('/new-observing_session', methods=['GET', 'POST'])
@login_required
def new_observing_session():
    """Create new observing_session"""
    form = ObservingSessionNewForm()
    telescopes = Telescope.query.filter_by(user_id=current_user.id, is_active=True, is_deleted=False).all()
    form.default_telescope.choices = [(-1, "---")] + [(t.id, t.name) for t in telescopes]

    if request.method == 'POST' and form.validate_on_submit():
        location_position = None
        location_id = None
        if isinstance(form.location.data, int) or form.location.data.isdigit():
            location_id = int(form.location.data)
        else:
            location_position = form.location.data

        observing_session = ObservingSession(
            user_id=current_user.id,
            title=form.title.data,
            date_from=form.date_from.data,
            date_to=form.date_to.data,
            location_id=location_id,
            location_position=location_position,
            sqm=form.sqm.data,
            faintest_star=form.faintest_star.data,
            seeing=form.seeing.data,
            transparency=form.transparency.data,
            rating=int(form.rating.data) * 2,
            weather=form.weather.data,
            equipment=form.equipment.data,
            notes=form.notes.data,
            default_telescope_id=form.default_telescope.data,
            is_public = form.is_public.data,
            is_finished = form.is_finished.data,
            is_active = form.is_active.data,
            create_by=current_user.id,
            update_by=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now()
        )

        if observing_session.is_finished:
            observing_session.is_active = False

        if observing_session.is_active:
            _deactivate_all_user_observing_sessions()

        db.session.add(observing_session)
        db.session.commit()
        flash(gettext('Observing session successfully created'), 'form-success')
        return redirect(url_for('main_observing_session.observing_session_edit', observing_session_id=observing_session.id))

    location, location_position = _get_location_data2_from_form(form)

    return render_template('main/observation/observing_session_edit.html', form=form, is_new=True, location=location,
                           location_position=location_position, observing_session=None)


@main_observing_session.route('/observing-session/<int:observing_session_id>/edit', methods=['GET', 'POST'])
@login_required
def observing_session_edit(observing_session_id):
    """Update observing_session"""
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    _check_observing_session(observing_session)

    telescopes = Telescope.query.filter_by(user_id=current_user.id, is_active=True, is_deleted=False).all()
    form = ObservingSessionEditForm()
    form.default_telescope.choices = [(-1, "---")] + [(t.id, t.name) for t in telescopes]

    if request.method == 'POST':
        if form.validate_on_submit():
            location_position = None
            location_id = None
            if isinstance(form.location.data, int) or form.location.data.isdigit():
                location_id = int(form.location.data)
            else:
                location_position = form.location.data

            observing_session.user_id = current_user.id
            observing_session.title = form.title.data
            observing_session.date_from = form.date_from.data
            observing_session.date_to = form.date_to.data
            observing_session.location_id = location_id
            observing_session.location_position = location_position
            observing_session.sqm = form.sqm.data
            observing_session.faintest_star = form.faintest_star.data
            observing_session.seeing = form.seeing.data
            observing_session.transparency = form.transparency.data
            observing_session.rating = int(form.rating.data) * 2
            observing_session.weather = form.weather.data
            observing_session.equipment = form.equipment.data
            observing_session.notes = form.notes.data
            observing_session.default_telescope_id = form.default_telescope.data
            observing_session.update_by = current_user.id
            observing_session.update_date = datetime.now()
            observing_session.is_public = form.is_public.data
            observing_session.is_finished = form.is_finished.data
            if observing_session.is_finished:
                observing_session.is_active = False
                activated = False
            else:
                activated = form.is_active.data and observing_session.is_active != form.is_active.data
                observing_session.is_active = form.is_active.data

            if activated:
                _deactivate_all_user_observing_sessions()
                observing_session.is_active = True

            db.session.add(observing_session)
            db.session.commit()

            flash(gettext('Observing session successfully updated'), 'form-success')

            if form.goback.data == 'true':
                return redirect(url_for('main_observing_session.observing_session_info', observing_session_id=observing_session.id))
            return redirect(url_for('main_observing_session.observing_session_edit', observing_session_id=observing_session.id))
    else:
        form.title.data = observing_session.title
        form.date_from.data = observing_session.date_from
        form.date_to.data = observing_session.date_to
        form.location.data = observing_session.location_id if observing_session.location_id is not None else observing_session.location_position
        form.sqm.data = observing_session.sqm
        form.faintest_star.data = observing_session.faintest_star
        form.seeing.data = observing_session.seeing if observing_session.seeing else Seeing.AVERAGE
        form.transparency.data = observing_session.transparency if observing_session.transparency else Transparency.AVERAGE
        form.rating.data = observing_session.rating // 2 if observing_session.rating is not None else 0
        form.weather.data = observing_session.weather
        form.equipment.data = observing_session.equipment
        form.notes.data = observing_session.notes
        form.default_telescope.data = observing_session.default_telescope_id
        form.is_public.data = observing_session.is_public
        form.is_finished.data = observing_session.is_finished
        form.is_active.data = observing_session.is_active

    location, location_position = _get_location_data2_from_form(form)

    return render_template('main/observation/observing_session_edit.html', form=form, is_new=False, observing_session=observing_session,
                           location=location, location_position=location_position)


@main_observing_session.route('/observing-session/<int:observing_session_id>/items-edit', methods=['GET', 'POST'])
@login_required
def observing_session_items_edit(observing_session_id):
    """Update observing_session items"""
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    _check_observing_session(observing_session)

    form = ObservingSessionItemsEditForm()

    telescopes = Telescope.query.filter_by(user_id=current_user.id, is_active=True, is_deleted=False).all()
    eyepieces = Eyepiece.query.filter_by(user_id=current_user.id, is_active=True, is_deleted=False).all()
    filters = Filter.query.filter_by(user_id=current_user.id, is_active=True, is_deleted=False).all()

    if request.method == 'POST':
        for item_form in form.items:
            _assign_equipment_choices(item_form, telescopes, eyepieces, filters)
        # set fake item
        form.items[0].telescope.data = -1
        form.items[0].eyepiece.data = -1
        form.items[0].filter.data = -1
        if form.validate_on_submit():
            for observation in observing_session.observations:
                observation.deepsky_objects = []
                db.session.delete(observation)
            observing_session.observations.clear()
            for item_form in form.items[1:]:
                if observing_session.date_from.day != observing_session.date_to.day:
                    if item_form.date_from.data.hour >= 12:
                        item_time = datetime.combine(observing_session.date_from, item_form.date_from.data)
                    else:
                        item_time = datetime.combine(observing_session.date_to, item_form.date_from.data)
                else:
                    item_time = datetime.combine(observing_session.date_from, item_form.date_from.data)

                if ':' in item_form.comp_notes.data:
                    targets, notes = item_form.comp_notes.data.split(':', 1)
                else:
                    targets, notes = item_form.comp_notes.data.strip(), ''

                observation = Observation(
                    observing_session_id=observing_session.id,
                    user_id=current_user.id,
                    date_from=item_time,
                    date_to=item_time,
                    notes=notes,
                    telescope_id=item_form.telescope.data if item_form.telescope.data != -1 else None,
                    eyepiece_id=item_form.eyepiece.data if item_form.eyepiece.data != -1 else None,
                    filter_id=item_form.filter.data if item_form.filter.data != -1 else None,
                    create_by=current_user.id,
                    update_by=current_user.id,
                    create_date=datetime.now(),
                    update_date=datetime.now(),
                )
                observing_session.observations.append(observation)

                set_observation_targets(observation, targets)

            db.session.add(observing_session)
            db.session.commit()

            if form.goback.data == 'true':
                return redirect(url_for('main_observing_session.observing_session_info', observing_session_id=observing_session.id))
            return redirect(url_for('main_observing_session.observing_session_items_edit', observing_session_id=observing_session.id))
    else:
        _assign_equipment_choices(form.items[0], telescopes, eyepieces, filters)
        for oi in observing_session.observations:
            oif = form.items.append_entry()
            _assign_equipment_choices(oif, telescopes, eyepieces, filters)
            if oi.target_type == ObservationTargetType.DBL_STAR:
                targets_comp = oi.double_star.get_common_norm_name()
            elif oi.target_type == ObservationTargetType.PLANET:
                targets_comp = Planet.get_by_iau_code(oi.planet.iau_code).get_localized_name()
            elif oi.target_type == ObservationTargetType.COMET:
                targets_comp = oi.comet.designation
            elif oi.target_type == ObservationTargetType.M_PLANET:
                targets_comp = oi.minor_planet.designation
            else:
                targets_comp = ','.join([dso.name for dso in oi.deepsky_objects])
            targets_comp += ':'
            oif.comp_notes.data = targets_comp + oi.notes
            oif.date_from.data = oi.date_from
            oif.telescope.data = oi.telescope_id if oi.telescope_id is not None else -1
            oif.eyepiece.data = oi.eyepiece_id if oi.eyepiece_id is not None else -1
            oif.filter.data = oi.filter_id if oi.filter_id is not None else -1

    return render_template('main/observation/observing_session_items_edit.html', form=form, observing_session=observing_session)


def _assign_equipment_choices(form_item, telescopes, eyepieces, filters):
    form_item.telescope.choices = [(-1, "---")] + [(t.id, t.name) for t in telescopes]
    form_item.eyepiece.choices = [(-1, "---")] + [(e.id, e.name) for e in eyepieces]
    form_item.filter.choices = [(-1, "---")] + [(f.id, f.name) for f in filters]


def _get_location_data2_from_form(form):
    location_position = None
    location = None
    if form.location.data and (isinstance(form.location.data, int) or form.location.data.isdigit()):
        location = Location.query.filter_by(id=int(form.location.data)).first()
    else:
        location_position = form.location.data

    return location, location_position


@main_observing_session.route('/observing-session/<int:observing_session_id>/delete')
@login_required
def observing_session_delete(observing_session_id):
    """Request deletion of a observing_session."""
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    _check_observing_session(observing_session)
    db.session.delete(observing_session)
    db.session.commit()
    flash(gettext('Observation was deleted'), 'form-success')
    return redirect(url_for('main_observing_session.observing_sessions'))


@main_observing_session.route('/observing-session/<int:observing_session_id>/set-activity/<int:activity>')
@login_required
def observing_session_set_activity(observing_session_id, activity):
    """Request activation of a observing_session."""
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    _check_observing_session(observing_session)
    if activity == 1:
        _deactivate_all_user_observing_sessions()
        observing_session.is_active = True
    else:
        observing_session.is_active = False
    db.session.add(observing_session)
    db.session.commit()
    return redirect(url_for('main_observing_session.observing_session_info', observing_session_id=observing_session.id))


@main_observing_session.route('/observing-session/<int:observing_session_id>/chart', methods=['GET', 'POST'])
@csrf.exempt
def observing_session_chart(observing_session_id):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, allow_public=True)

    form = ChartForm()

    prefix, obj_id = parse_prefix_obj_id(request.args.get('obj_id'))

    observing_session_item = None

    for oitem in observing_session.observations:
        if oitem.target_type == ObservationTargetType.DSO:
            for oitem_dso in oitem.deepsky_objects:
                if obj_id is None or oitem_dso.id == obj_id:
                    observing_session_item = oitem
                    break
        elif oitem.target_type == ObservationTargetType.DBL_STAR:
            if obj_id is None or oitem.double_star_id == obj_id:
                observing_session_item = oitem
        if observing_session_item is not None:
            break

    common_ra_dec_dt_fsz_from_request(form,
                                   observing_session_item.get_ra() if observing_session_item else None,
                                   observing_session_item.get_dec() if observing_session_item else None)

    chart_control = common_prepare_chart_data(form)
    default_chart_iframe_url = get_default_chart_iframe_url(observing_session_item, back='observation', back_id=observing_session.id)

    return render_template('main/observation/observing_session_info.html', fchart_form=form, type='chart',
                           observing_session=observing_session, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url, is_mine_observing_session=is_mine_observing_session,
                           back='observation', back_id=observing_session.id)


@main_observing_session.route('/observing-session/<int:observing_session_id>/chart-pos-img', methods=['GET'])
def observing_session_chart_pos_img(observing_session_id):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, allow_public=True)

    highlights_dso_list, highlights_pos_list = common_highlights_from_observing_session(observing_session)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes, img_format = common_chart_pos_img(None, None, visible_objects=visible_objects,
                                                 highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_observing_session.route('/observing-session/<int:observing_session_id>/chart/scene-v1', methods=['GET'])
def observing_session_chart_scene_v1(observing_session_id):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    _check_observing_session(observing_session, allow_public=True)

    prefix, obj_id = parse_prefix_obj_id(request.args.get('obj_id'))
    observing_session_item = None

    for oitem in observing_session.observations:
        if oitem.target_type == ObservationTargetType.DSO:
            for oitem_dso in oitem.deepsky_objects:
                if obj_id is None or oitem_dso.id == obj_id:
                    observing_session_item = oitem
                    break
        elif oitem.target_type == ObservationTargetType.DBL_STAR:
            if obj_id is None or oitem.double_star_id == obj_id:
                observing_session_item = oitem
        if observing_session_item is not None:
            break

    highlights_dso_list, highlights_pos_list = common_highlights_from_observing_session(observing_session)

    scene = build_scene_v1()
    scene_meta = scene.setdefault('meta', {})
    scene_objects = scene.setdefault('objects', {})
    highlights = scene_objects.setdefault('highlights', [])
    cur_theme = session.get('theme')

    if observing_session_item:
        if observing_session_item.target_type == ObservationTargetType.DSO and observing_session_item.deepsky_objects:
            dso = observing_session_item.deepsky_objects[0]
            ensure_scene_dso_item(scene, dso)
            highlights.append(
                build_cross_highlight(highlight_id=str(dso.name).replace(' ', ''), label=dso.denormalized_name(), ra=dso.ra, dec=dso.dec, theme_name=cur_theme,)
            )
        elif observing_session_item.target_type == ObservationTargetType.DBL_STAR and observing_session_item.double_star:
            ds = observing_session_item.double_star
            highlights.append(
                build_cross_highlight(highlight_id=CHART_DOUBLE_STAR_PREFIX + str(ds.id), label=ds.get_catalog_name(), ra=ds.ra_first, dec=ds.dec_first, theme_name=cur_theme,)
            )
        elif observing_session_item.target_type == ObservationTargetType.COMET and observing_session_item.comet:
            comet = observing_session_item.comet
            highlights.append(
                build_cross_highlight(highlight_id=CHART_COMET_PREFIX + str(comet.id), label=comet.designation, ra=comet.cur_ra, dec=comet.cur_dec, theme_name=cur_theme,)
            )
        elif observing_session_item.target_type == ObservationTargetType.M_PLANET and observing_session_item.minor_planet:
            mp = observing_session_item.minor_planet
            highlights.append(
                build_cross_highlight(highlight_id=CHART_MINOR_PLANET_PREFIX + str(mp.id), label=mp.designation, ra=mp.cur_ra, dec=mp.cur_dec, theme_name=cur_theme,)
            )

    if highlights_dso_list:
        for hl_dso in highlights_dso_list:
            if hl_dso is None:
                continue
            ensure_scene_dso_item(scene, hl_dso)
            highlights.append(
                build_circle_highlight(highlight_id=str(hl_dso.name).replace(' ', ''), label=hl_dso.denormalized_name(), ra=hl_dso.ra, dec=hl_dso.dec, dashed=False, theme_name=cur_theme,)
            )

    if highlights_pos_list:
        for hl_pos in highlights_pos_list:
            if hl_pos is None or len(hl_pos) < 4:
                continue
            hl_ra, hl_dec, hl_id, hl_label = hl_pos[0], hl_pos[1], hl_pos[2], hl_pos[3]
            if hl_ra is None or hl_dec is None:
                continue
            highlights.append(
                build_circle_highlight(highlight_id=str(hl_id), label=str(hl_label or hl_id), ra=hl_ra, dec=hl_dec, dashed=False, theme_name=cur_theme,)
            )

    scene_meta['object_context'] = {
        'kind': 'observing_session',
        'id': str(observing_session.id),
        'selected_prefix': prefix,
    }
    return jsonify(scene)


@main_observing_session.route('/observing-session/<int:observing_session_id>/chart-pdf', methods=['GET'])
def observing_session_chart_pdf(observing_session_id):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    _check_observing_session(observing_session, allow_public=True)

    highlights_dso_list, highlights_pos_list = common_highlights_from_observing_session(observing_session)

    img_bytes = common_chart_pdf_img(None, None, highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list)

    return send_file(img_bytes, mimetype='application/pdf')


@main_observing_session.route('/observing-session/<int:observing_session_id>/run-plan', methods=['GET', 'POST'])
def observing_session_run_plan(observing_session_id):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, False)
    if not is_mine_observing_session:
        abort(404)

    form = ObservingSessionRunPlanForm()

    session_plan_id = None
    if request.method == 'POST':
        if form.validate_on_submit():
            session_plan_id = form.session_plan.data
    else:
        session_plan_id = form.session_plan.data
        if session_plan_id is None:
            running_plan_id = session.get('running_plan_id', None)
            if running_plan_id is not None:
                observing_session_plan_run = ObsSessionPlanRun.query.filter_by(id=int(running_plan_id)).first()
                if observing_session_plan_run and \
                        not observing_session_plan_run.session_plan.is_archived and \
                        observing_session_plan_run.session_plan.user_id == current_user.id:
                    session_plan_id = observing_session_plan_run.session_plan.id
                else:
                    session.pop('running_plan_id')

    available_session_plans = SessionPlan.query.filter_by(user_id=current_user.id, is_archived=False) \
        .order_by(SessionPlan.for_date.desc())

    observing_session_plan_run = None

    observed_items = []
    not_observed_plan_items = []

    session_plan = None

    if session_plan_id is not None:
        session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
        if session_plan.user_id == current_user.id:
            observing_session_plan_run = ObsSessionPlanRun.query.filter_by(observing_session_id=observing_session_id, session_plan_id=session_plan_id) \
                                                     .first()
            form.session_plan.data = session_plan_id
        else:
            session.pop('running_plan_id')
            form.session_plan.data = None

    if session_plan:
        for plan_item in session_plan.session_plan_items:
            observation = None
            if plan_item.dso_id is not None:
                observation = observing_session.find_observation_by_dso_id(plan_item.dso_id)
            elif plan_item.double_star_id is not None:
                observation = observing_session.find_observation_by_double_star_id(plan_item.double_star_id)
            if observation:
                observed_items.append((plan_item, observation))
            else:
                not_observed_plan_items.append(plan_item)

    return render_template('main/observation/observing_session_info.html', observing_session=observing_session, type='run_plan',
                           run_plan_form=form, is_mine_observing_session=True, available_session_plans=available_session_plans,
                           observed_items=observed_items, not_observed_plan_items=not_observed_plan_items,
                           observing_session_plan_run=observing_session_plan_run)


@main_observing_session.route('/observing-session/<int:observing_session_plan_run_id>/run-plan-redirect', methods=['GET'])
def observing_session_run_plan_redirect(observing_session_plan_run_id):
    observing_session_plan_run = ObsSessionPlanRun.query.filter_by(id=observing_session_plan_run_id).first()
    if not observing_session_plan_run:
        abort(404)
    return redirect(url_for('main_observing_session.observing_session_run_plan', observing_session_id=observing_session_plan_run.observing_session_id))


@main_observing_session.route('/observing-session/<int:observing_session_id>/<int:session_plan_id>/run-plan-execute', methods=['GET'])
def observing_session_run_plan_execute(observing_session_id, session_plan_id):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, False)
    if not is_mine_observing_session:
        abort(404)
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    if session_plan is None or session_plan.user_id != current_user.id:
        abort(404)

    observing_session_plan_run = ObsSessionPlanRun.query.filter_by(observing_session_id=observing_session_id, session_plan_id=session_plan_id) \
        .first()

    if observing_session_plan_run is None:
        observing_session_plan_run = ObsSessionPlanRun(
            observing_session_id=observing_session_id,
            session_plan_id=session_plan_id
        )
        db.session.add(observing_session_plan_run)
        db.session.commit()

    session['running_plan_id'] = observing_session_plan_run.id

    if len(session_plan.session_plan_items) and session_plan.session_plan_items[0].deepsky_object is not None:
        dso_name = session_plan.session_plan_items[0].deepsky_object.name
    else:
        dso_name = 'M1'  # fallback
    return redirect(url_for('main_deepskyobject.deepskyobject_observation_log', dso_id=dso_name, back='running_plan', back_id=observing_session_plan_run.id))


def _deactivate_all_user_observing_sessions():
    for act_obs_session in ObservingSession.query.filter_by(user_id=current_user.id, is_active=True).all():
        act_obs_session.is_active = False
        db.session.add(act_obs_session)
