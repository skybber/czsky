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
)

from app.models import Observation, Location, ObservedList, ObservedListItem
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

    observations = Observation.query.filter_by(user_id=current_user.id)
    search = False

    observations_for_render = observations.limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, total=observations.count(), search=search, record_name='observations', css_framework='semantic')
    return render_template('main/observation/observations.html', observations=observations_for_render, pagination=pagination)

@main_observation.route('/observation/<int:observation_id>', methods=['GET'])
@main_observation.route('/observation/<int:observation_id>/info', methods=['GET'])
@login_required
def observation_info(observation_id):
    """View a observation info."""
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)
    if observation.user_id != current_user.id:
        abort(404)
    return render_template('main/observation/observation_info.html', observation=observation, type='info')

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

    location = None
    if form.location_id.data:
        location = Location.query.filter_by(id=form.location_id.data).first()
    return render_template('main/observation/observation_edit.html', form=form, is_new=True, location=location)

@main_observation.route('/observation/<int:observation_id>/edit', methods=['GET', 'POST'])
@login_required
def observation_edit(observation_id):
    """Update observation"""
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)
    if observation.user_id != current_user.id:
        abort(404)
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
        form.location_id.data = observation.location_id
        form.rating.data = observation.rating
        form.notes.data = observation.notes
        form.omd_content.data = observation.omd_content
        for oi in observation.observation_items:
            oif = form.items.append_entry()
            oif.deepsky_object_id_list.data = oi.txt_deepsky_objects
            oif.date_time.data = oi.date_time
            oif.notes.data = oi.notes

    location = None
    if form.location_id.data:
        location = Location.query.filter_by(id=form.location_id.data).first()

    return render_template('main/observation/observation_edit.html', form=form, is_new=False, observation=observation, location=location)

@main_observation.route('/observation/<int:observation_id>/delete')
@login_required
def observation_delete(observation_id):
    """Request deletion of a observation."""
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)
    if observation.user_id != current_user.id:
        abort(404)
    db.session.delete(observation)
    db.session.commit()
    flash('Observation was deleted', 'form-success')
    return redirect(url_for('main_observation.observations'))


@main_observation.route('/observation/<int:observation_id>/chart', methods=['GET', 'POST'])
def observation_chart(observation_id):
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)

    form  = ChartForm()

    dso_id = request.args.get('dso_id')
    observation_item = None
    if dso_id and dso_id.isdigit():
        idso_id = int(dso_id)
        observation_item = next((x for x in observation.observation_items if x.deepskyObject.id == idso_id), None)

    if not observation_item:
        observation_item = ObservationItem.query.filter_by(observation_id=observation.id).first()

    if not common_ra_dec_fsz_from_request(form):
        if form.ra.data is None or form.dec.data is None:
            form.ra.data = observation_item.deepskyObject.ra if observation_item else 0
            form.dec.data = observation_item.deepskyObject.dec if observation_item else 0

    if observation_item:
        default_chart_iframe_url = url_for('main_deepskyobject.deepskyobject_info', back='observation', back_id=observation.id, dso_id=observation_item.deepskyObject.name, embed='fc', allow_back='true')
    else:
        default_chart_iframe_url = None

    chart_control = common_prepare_chart_data(form)

    return render_template('main/observation/observation_info.html', fchart_form=form, type='chart', observation=observation, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url,)


@main_observation.route('/observation/<int:observation_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def  observation_chart_pos_img(observation_id, ra, dec):
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)

    highlights_dso_list = [ x.deepskyObject for x in observation.observation_items if observation ]

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
    if observation is None:
        abort(404)

    img_bytes = common_chart_legend_img(None, None, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')

