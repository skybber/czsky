import os
import csv
from io import StringIO, BytesIO
import base64

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
    url_for,
)
from flask_login import current_user, login_required

from app import db

from .observation_forms import (
    ObservationNewForm,
    ObservationEditForm,
    ObservationRunPlanForm,
)

from app.models import Observation, Location, ObservedList, ObservedListItem, Seeing, Transparency, SessionPlan, \
                       ObservationPlanRun

from app.commons.search_utils import get_items_per_page, ITEMS_PER_PAGE
from app.commons.pagination import Pagination, get_page_parameter
from .observation_form_utils import *
from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_ra_dec_fsz_from_request,
)

from app.main.chart.chart_forms import ChartForm

main_observation = Blueprint('main_observation', __name__)


@main_observation.route('/observation-menu', methods=['GET'])
@login_required
def observation_menu():
    return render_template('main/observation/observation_menu.html')


@main_observation.route('/observations', methods=['GET', 'POST'])
@login_required
def observations():
    """View observations."""
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    observations = Observation.query.filter_by(user_id=current_user.id).order_by(Observation.date.desc())
    search = False

    observations_for_render = observations.limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, total=observations.count(), search=search, record_name='observations', css_framework='semantic')
    return render_template('main/observation/observations.html', observations=observations_for_render, pagination=pagination)


def _check_observation(observation, allow_public=False):
    if observation is None:
        abort(404)
    if current_user.is_anonymous:
        if observation.is_public:
            return False
        abort(404)
    elif observation.user_id != current_user.id:
        if allow_public and observation.is_public:
            return False
        abort(404)

    return True


@main_observation.route('/observation/<int:observation_id>', methods=['GET'])
@main_observation.route('/observation/<int:observation_id>/info', methods=['GET'])
def observation_info(observation_id):
    """View a observation info."""
    observation = Observation.query.filter_by(id=observation_id).first()
    is_mine_observation = _check_observation(observation, allow_public=True)
    return render_template('main/observation/observation_info.html', observation=observation, type='info', is_mine_observation=is_mine_observation)


@main_observation.route('/new-observation', methods=['GET', 'POST'])
@login_required
def new_observation():
    """Create new observation"""
    form = ObservationNewForm()
    if request.method == 'POST' and form.validate_on_submit():
        if form.advmode.data == 'true':
            new_observation_id = create_from_advanced_form(form)
        else:
            new_observation_id = create_from_basic_form(form)
        if new_observation_id:
            return redirect(url_for('main_observation.observation_edit', observation_id=new_observation_id))

    location, location_position = _get_location_data2_from_form(form)

    return render_template('main/observation/observation_edit.html', form=form, is_new=True, location=location, location_position=location_position)


@main_observation.route('/observation/<int:observation_id>/edit', methods=['GET', 'POST'])
@login_required
def observation_edit(observation_id):
    """Update observation"""
    observation = Observation.query.filter_by(id=observation_id).first()
    _check_observation(observation)

    form = ObservationEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            if form.advmode.data == 'true':
                update_from_advanced_form(form, observation)
            else:
                update_from_basic_form(form, observation)
            if form.goback.data == 'true':
                return redirect(url_for('main_observation.observation_info', observation_id=observation.id))
    else:
        form.title.data = observation.title
        form.date.data = observation.date
        form.location.data = observation.location_id if observation.location_id is not None else observation.location_position
        form.sqm.data = observation.sqm
        form.seeing.data = observation.seeing if observation.seeing else Seeing.AVERAGE
        form.transparency.data = observation.transparency if observation.transparency else Transparency.AVERAGE
        form.rating.data = observation.rating // 2
        form.notes.data = observation.notes
        form.omd_content.data = observation.omd_content
        form.is_public.data = observation.is_public
        for oi in observation.observation_items:
            oif = form.items.append_entry()
            oif.deepsky_object_id_list.data = oi.txt_deepsky_objects
            oif.date_time.data = oi.date_time
            oif.notes.data = oi.notes

    location, location_position = _get_location_data2_from_form(form)

    return render_template('main/observation/observation_edit.html', form=form, is_new=False, observation=observation,
                           location=location, location_position=location_position)


def _get_location_data2_from_form(form):
    location_position = None
    location = None
    if form.location.data and (isinstance(form.location.data, int) or form.location.data.isdigit()):
        location = Location.query.filter_by(id=int(form.location.data)).first()
    else:
        location_position = form.location.data

    return location, location_position


@main_observation.route('/observation/<int:observation_id>/delete')
@login_required
def observation_delete(observation_id):
    """Request deletion of a observation."""
    observation = Observation.query.filter_by(id=observation_id).first()
    _check_observation(observation)
    db.session.delete(observation)
    db.session.commit()
    flash('Observation was deleted', 'form-success')
    return redirect(url_for('main_observation.observations'))


@main_observation.route('/observation/<int:observation_id>/chart', methods=['GET', 'POST'])
def observation_chart(observation_id):
    observation = Observation.query.filter_by(id=observation_id).first()
    is_mine_observation = _check_observation(observation, allow_public=True)

    form = ChartForm()

    dso_id = request.args.get('dso_id')
    observation_item = None
    dso = None

    if dso_id and dso_id.isdigit():
        idso_id = int(dso_id)
        for oitem in observation.observation_items:
            for oitem_dso in oitem.deepsky_objects:
                if oitem_dso.id == idso_id:
                    observation_item = oitem
                    dso = oitem_dso
                    break
            if observation_item is not None:
                break
    elif observation.observation_items:
        for oitem in observation.observation_items:
            for oitem_dso in oitem.deepsky_objects:
                observation_item = oitem
                dso = oitem_dso
                break
            if observation_item is not None:
                break

    if observation_item and not common_ra_dec_fsz_from_request(form):
        if form.ra.data is None or form.dec.data is None:
            if not dso:
                dso = observation_item.deepsky_objects[0] if observation_item and observation_item.deepsky_objects else None
            form.ra.data = dso.ra if dso else 0
            form.dec.data = dso.dec if dso else 0

    if observation_item:
        default_chart_iframe_url = url_for('main_deepskyobject.deepskyobject_info', back='observation', back_id=observation.id, dso_id=dso.name, embed='fc', allow_back='true')
    else:
        default_chart_iframe_url = None

    chart_control = common_prepare_chart_data(form)

    return render_template('main/observation/observation_info.html', fchart_form=form, type='chart', observation=observation, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url, is_mine_observation=is_mine_observation)


@main_observation.route('/observation/<int:observation_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def  observation_chart_pos_img(observation_id, ra, dec):
    observation = Observation.query.filter_by(id=observation_id).first()
    is_mine_observation = _check_observation(observation, allow_public=True)

    highlights_dso_list = []

    for oitem in observation.observation_items:
        for oitem_dso in oitem.deepsky_objects:
            highlights_dso_list.append(oitem_dso)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes = common_chart_pos_img(None, None, ra, dec, visible_objects=visible_objects, highlights_dso_list=highlights_dso_list)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


@main_observation.route('/observation/<int:observation_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def observation_chart_legend_img(observation_id, ra, dec):
    observation = Observation.query.filter_by(id=observation_id).first()
    is_mine_observation = _check_observation(observation, allow_public=True)

    img_bytes = common_chart_legend_img(None, None, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_observation.route('/observation/<int:observation_id>/run-plan', methods=['GET', 'POST'])
def observation_run_plan(observation_id):
    observation = Observation.query.filter_by(id=observation_id).first()
    is_mine_observation = _check_observation(observation, False)
    if not is_mine_observation:
        abort(404)

    form = ObservationRunPlanForm()

    if request.method == 'POST':
        print(form.session_plan.data, flush=True)
        if form.validate_on_submit():
            pass
    else:
        form.session_plan.data = None

    session_plan_id = int(form.session_plan.data) if form.session_plan.data else None
    observation_plan_run = None

    if session_plan_id is not None:
        session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
        if session_plan.user_id != current_user.id:
            abort(404)
        observation_plan_run = ObservationPlanRun.query.filter_by(observation_id=observation_id, session_plan_id=session_plan_id) \
                                                 .first()

    available_session_plans = SessionPlan.query.filter_by(user_id=current_user.id, is_archived=False) \
                                         .order_by(SessionPlan.for_date.desc())

    return render_template('main/observation/observation_info.html', observation=observation, type='run_plan',
                           run_plan_form=form, is_mine_observation=True, available_session_plans=available_session_plans,
                           observation_plan_run=observation_plan_run)


@main_observation.route('/observation/<int:observation_id>/<int:session_plan_id>/run-plan-execute', methods=['GET'])
def observation_run_plan_execute(observation_id, session_plan_id):
    observation = Observation.query.filter_by(id=observation_id).first()
    is_mine_observation = _check_observation(observation, False)
    if not is_mine_observation:
        abort(404)
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    if session_plan is None or session_plan.user_id != current_user.id:
        abort(404)
