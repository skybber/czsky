from datetime import datetime
import base64

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
    ObservationSessionRunPlanForm,
)

from app.models import (
    Location,
    Observation,
    ObservingSession,
    ObservationTargetType,
    ObsSessionPlanRun,
    Planet,
    Seeing,
    SessionPlan,
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
    common_ra_dec_fsz_from_request,
    common_set_initial_ra_dec,
    common_chart_pdf_img,
)

from app.main.chart.chart_forms import ChartForm
from app.commons.coordinates import *
from app.commons.prevnext_utils import get_default_chart_iframe_url, parse_prefix_obj_id
from app.commons.highlights_list_utils import common_highlights_from_observing_session

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

    return render_template('main/observation/observing_session_info.html', observing_session=observing_session, type='info', is_mine_observing_session=is_mine_observing_session,
                           location_position_mapy_cz_url=location_position_mapy_cz_url, location_position_google_maps_url=location_position_google_maps_url,
                           show_observ_time=show_observ_time)


@main_observing_session.route('/new-observing_session', methods=['GET', 'POST'])
@login_required
def new_observing_session():
    """Create new observing_session"""
    form = ObservingSessionNewForm()
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
            is_public = form.is_public.data,
            is_finished = form.is_finished.data,
            create_by=current_user.id,
            update_by=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now()
        )

        db.session.add(observing_session)
        db.session.commit()
        flash(gettext('Observing session successfully created'), 'form-success')
        return redirect(url_for('main_observing_session.observing_session_edit', observing_session_id=observing_session.id))

    location, location_position = _get_location_data2_from_form(form)

    return render_template('main/observation/observing_session_edit.html', form=form, is_new=True, location=location, location_position=location_position)


@main_observing_session.route('/observing-session/<int:observing_session_id>/edit', methods=['GET', 'POST'])
@login_required
def observing_session_edit(observing_session_id):
    """Update observing_session"""
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    _check_observing_session(observing_session)

    form = ObservingSessionEditForm()
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
            observing_session.update_by = current_user.id
            observing_session.update_date = datetime.now()
            observing_session.is_public = form.is_public.data
            observing_session.is_finished = form.is_finished.data

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
        form.is_public.data = observing_session.is_public
        form.is_finished.data = observing_session.is_finished

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
    if request.method == 'POST':
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
        for oi in observing_session.observations:
            oif = form.items.append_entry()
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

    return render_template('main/observation/observing_session_items_edit.html', form=form, observing_session=observing_session)


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

    if not common_ra_dec_fsz_from_request(form):
        if observing_session_item:
            if request.method == 'GET' and (form.ra.data is None or form.dec.data is None):
                form.ra.data = observing_session_item.get_ra()
                form.dec.data = observing_session_item.get_dec()
        else:
            common_set_initial_ra_dec(form)

    chart_control = common_prepare_chart_data(form)
    default_chart_iframe_url = get_default_chart_iframe_url(observing_session_item, back='observation', back_id=observing_session.id)

    return render_template('main/observation/observing_session_info.html', fchart_form=form, type='chart', observing_session=observing_session, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url, is_mine_observing_session=is_mine_observing_session)


@main_observing_session.route('/observing-session/<int:observing_session_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def observing_session_chart_pos_img(observing_session_id, ra, dec):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, allow_public=True)

    highlights_dso_list, highlights_pos_list = common_highlights_from_observing_session(observing_session)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes, img_format = common_chart_pos_img(None, None, ra, dec, visible_objects=visible_objects,
                                                 highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_observing_session.route('/observing-session/<int:observing_session_id>/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def observing_session_chart_pdf(observing_session_id, ra, dec):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    _check_observing_session(observing_session, allow_public=True)

    highlights_dso_list, highlights_pos_list = common_highlights_from_observing_session(observing_session)

    img_bytes = common_chart_pdf_img(None, None, ra, dec,
                                     highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list)

    return send_file(img_bytes, mimetype='application/pdf')

@main_observing_session.route('/observing-session/<int:observing_session_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def observing_session_chart_legend_img(observing_session_id, ra, dec):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, allow_public=True)

    img_bytes = common_chart_legend_img(None, None, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_observing_session.route('/observing-session/<int:observing_session_id>/run-plan', methods=['GET', 'POST'])
def observing_session_run_plan(observing_session_id):
    observing_session = ObservingSession.query.filter_by(id=observing_session_id).first()
    is_mine_observing_session = _check_observing_session(observing_session, False)
    if not is_mine_observing_session:
        abort(404)

    form = ObservationSessionRunPlanForm()

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
