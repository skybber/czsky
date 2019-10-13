from datetime import datetime

from flask import (
    Blueprint,
    flash,
    render_template,
    request,
)
from flask_login import current_user, login_required

from app import db

from .forms import (
    ObservationNewForm,
    ObservationEditForm,
)

from app.models import Observation, observation
from app.commons.pagination import Pagination, get_page_parameter, get_page_args

from .. import db
from .views import ITEMS_PER_PAGE

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
    return render_template('main/observation/observation_info.html', observation=observation, type='info')

@main_observation.route('/new-observation', methods=['GET', 'POST'])
@login_required
def new_observation():
    """Create new observation"""
    form = ObservationNewForm()
    if form.validate_on_submit():
        observation = Observation(
            user_id = current_user.id,
            date = form.date.data,
            rating = form.rating.data,
            omd_content=form.omd_content.data,
            create_by = current_user.id,
            update_by = current_user.id,
            create_date = datetime.now(),
            update_date = datetime.now()
            )
        db.session.add(observation)
        db.session.commit()
        flash('Observation successfully created', 'form-success')
    return render_template('main/observation/observation_new.html', form=form)

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
    if form.validate_on_submit():
        observation.date = form.date.data,
        observation.rating = form.rating.data,
        observation.omd_content = form.omd_content.data,
        observation.update_by = current_user.id,
        observation.update_date = datetime.now()
        db.session.add(observation)
        db.session.commit()
        flash('Observation successfully updated', 'form-success')
    return render_template('main/observation/observation_edit.html', form=form)

@main_observation.route('/observation/<int:observation_id>/sqm', methods=['GET'])
@login_required
def observation_sqm(observation_id):
    """View a observation sqm."""
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)
    if observation.user_id != current_user.id:
        abort(404)
    return render_template('main/observation/observation_info.html', observation=observation, type='sqm')
