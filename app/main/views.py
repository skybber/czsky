from datetime import datetime

from flask import (
    Blueprint,
    flash,
    render_template,
    request,
)
from flask_login import current_user, login_required

from app.models import Constellation, DeepSkyObject, Observation, observation
from app.models import EditableHTML
from flask_paginate import Pagination, get_page_parameter, get_page_args

from .forms import (
    SearchForm,
    ObservationNewForm,
    ObservationEditForm,
)

main = Blueprint('main', __name__)

ITEMS_PER_PAGE = 10

@main.route('/')
def index():
    return render_template('main/index.html')


@main.route('/about')
def about():
    editable_html_obj = EditableHTML.get_editable_html('about')
    return render_template(
        'main/about.html', editable_html_obj=editable_html_obj)



@main.route('/constellations')
def constellations():
    """View all constellations."""
    constellations = Constellation.query.all()
    return render_template(
        'main/constellations.html', constellations=constellations)


@main.route('/constellation/<int:constellation_id>')
@main.route('/constellation/<int:constellation_id>/info')
def constellation_info(constellation_id):
    """View a constellation info."""
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)
    return render_template('main/constellation_info.html', constellation=constellation, type='info')


@main.route('/constellation/<int:constellation_id>/stars')
@login_required
def constellation_stars(constellation_id):
    """View a constellation info."""
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)
    return render_template('main/constellation_info.html', constellation=constellation, type='stars')


@main.route('/constellation/<int:constellation_id>/deepskyobjects')
def constellation_deepskyobjects(constellation_id):
    """View a constellation deep sky objects."""
    constellation = Constellation.query.filter_by(id=constellation_id).first()
    if constellation is None:
        abort(404)
    return render_template('main/constellation_info.html', constellation=constellation, type='dso')

@main.route('/deepskyobjects', methods=['GET', 'POST'])
def deepskyobjects():
    """View deepsky objects."""
    search_form = SearchForm()

    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    deepskyobjects = DeepSkyObject.query
    search = False
    if search_form.q.data:
        deepskyobjects = deepskyobjects.filter(DeepSkyObject.name.like('%' + search_form.q.data + '%'))
        search = True

    deepskyobjects_for_render = deepskyobjects.limit(per_page).offset(offset)

    pagination = Pagination(page=page, total=deepskyobjects.count(), search=search, record_name='deepskyobjects', css_framework='foundation')
    return render_template('main/deepskyobjects.html', deepskyobjects=deepskyobjects_for_render, pagination=pagination, search_form=search_form)


@main.route('/deepskyobject/<int:dso_id>')
@main.route('/deepskyobject/<int:dso_id>/info')
def deepskyobject_info(dso_id):
    """View a deepsky object info."""
    dso = DeepSkyObject.query.filter_by(id=dso_id).first()
    if dso is None:
        abort(404)
    return render_template('main/deepskyobject_info.html', dso=dso)

@main.route('/observations', methods=['GET', 'POST'])
@login_required
def observations():
    """View observations."""
    search_form = SearchForm()

    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    observations = Observation.query.filter_by(user_id=current_user.id)
    search = False
    if search_form.q.data:
        observations = observations.filter(DeepSkyObject.name.description('%' + search_form.q.data + '%'))
        search = True

    observations_for_render = observations.limit(per_page).offset(offset)

    pagination = Pagination(page=page, total=observations.count(), search=search, record_name='observations', css_framework='foundation')
    return render_template('main/observations.html', observations=observations_for_render, pagination=pagination, search_form=search_form)

@main.route('/observation/<int:observation_id>', methods=['GET'])
@main.route('/observation/<int:observation_id>/info', methods=['GET'])
@login_required
def observation_info(observation_id):
    """View a observation info."""
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)
    if observation.user_id != current_user.id:
        abort(404)
    return render_template('main/observation_info.html', observation=observation)

@main.route('/new-observation', methods=['GET', 'POST'])
@login_required
def new_observation():
    """Create new observation"""
    form = ObservationNewForm()
    if form.validate_on_submit():
        observation = Observation(
            date=datetime.now(),
            ranking=form.ranking,
            notes=form.notes
            )
        db.session.add(observation)
        db.session.commit()
        flash('Observation successfully created', 'form-success')
    return render_template('main/observation_new.html', form=form)

@main.route('/observation/<int:observation_id>/edit', methods=['GET', 'POST'])
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
        observation.ranking = form.ranking
        observation.notes = form.notes
        db.session.add(observation)
        db.session.commit()
        flash('Observation successfully updated', 'form-success')
    return render_template('main/observation_edit.html', form=form)
