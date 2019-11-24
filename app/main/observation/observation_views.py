from flask import (
    abort,
    Blueprint,
    url_for,
    redirect,
    render_template,
    request,
)
from flask_login import current_user, login_required

from app import db

from .observation_forms import (
    ObservationNewForm,
    ObservationEditForm,
)

from app.models import Observation, Location
from app.commons.pagination import Pagination, get_page_parameter
from app.main.views import ITEMS_PER_PAGE
from .observation_form_utils import *

main_observation = Blueprint('main_observation', __name__)

@main_observation.route('/observations', methods=['GET', 'POST'])
@login_required
def observations():
    """View observations."""
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    observations = Observation.query.filter_by(user_id=current_user.id)
    search = False

    observations_for_render = observations.limit(per_page).offset(offset)

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
    return render_template('main/observation/observation_info.html', observation=observation)

@main_observation.route('/new-observation', methods=['GET', 'POST'])
@login_required
def new_observation():
    """Create new observation"""
    form = ObservationNewForm()
    new_observation_id = None
    if request.method == 'POST' and form.validate_on_submit():
        if form.advmode.data == 'true':
            new_observation_id = create_from_advanced_form(form)
        else:
            new_observation_id = create_from_basic_form(form)
    if new_observation_id:
        return redirect(url_for('main_observation.observation_edit', observation_id=new_observation_id))
    location = Location()
    location.name = ''
    location.id = -1
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

    if (form.location_id.data and form.location_id.data!=-1):
        location = Location.query.find_by(location_id=form.location_id.data)
    else:
        location = Location()
        location.name = ''
        location.id = -1

    return render_template('main/observation/observation_edit.html', form=form, is_new=False, observation=observation)

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
    flash('Observation was deleted', 'form-success')
    return redirect(url_for('main_observation.observations'))

