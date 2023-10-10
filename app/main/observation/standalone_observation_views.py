from datetime import datetime

from flask import (
    abort,
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import current_user, login_required
from flask_babel import gettext

from app import db

from app.commons.search_utils import (
    process_paginated_session_search,
    get_items_per_page,
)

from app.commons.dso_utils import normalize_dso_name, denormalize_dso_name, normalize_double_star_name

from app.commons.pagination import Pagination, get_page_parameter

from .standalone_observation_forms import (
    StandaloneObservationNewForm,
    StandaloneObservationEditForm,
    SearchStandaloneObservationForm,
)

from app.models import (
    Comet,
    DeepskyObject,
    DoubleStar,
    Eyepiece,
    Filter,
    Location,
    MinorPlanet,
    Observation,
    ObservationTargetType,
    Planet,
    Seeing,
    Telescope,
    dso_observation_association_table,
)

from app.commons.observation_target_utils import set_observation_targets

from app.commons.observation_form_utils import assign_equipment_choices

main_standalone_observation = Blueprint('main_standalone_observation', __name__)


@main_standalone_observation.route('/standalone-observations', methods=['GET', 'POST'])
@login_required
def standalone_observations():
    """View standalone observations."""
    search_form = SearchStandaloneObservationForm()

    ret, page, sort_by = process_paginated_session_search('stobservation_search_page', 'stobservation_sort_by', [
        ('sto_search', search_form.q),
        ('items_per_page', search_form.items_per_page)
    ])

    if not ret:
        return redirect(url_for('main_standalone_observation.standalone_observations', page=page, sortby=sort_by))

    per_page = get_items_per_page(search_form.items_per_page)

    offset = (page - 1) * per_page

    observations = Observation.query.filter_by(user_id=current_user.id)
    if search_form.q.data:
        dso_q = normalize_dso_name(denormalize_dso_name(search_form.q.data))
        double_star_q = normalize_double_star_name(search_form.q.data)
        comet_q = search_form.q.data
        minor_planet_q = search_form.q.data
        planet_q = search_form.q.data
        observations = observations.join(dso_observation_association_table, isouter=True) \
                                   .join(DeepskyObject, isouter=True) \
                                   .join(DoubleStar, isouter=True) \
                                   .join(Comet, isouter=True) \
                                   .join(MinorPlanet, isouter=True) \
                                   .filter(((Observation.target_type == ObservationTargetType.DSO) &
                                            (dso_observation_association_table.c.observation_id == Observation.id) &
                                            (dso_observation_association_table.c.dso_id == DeepskyObject.id) &
                                            (DeepskyObject.name == dso_q)
                                            )
                                           |
                                           ((Observation.target_type == ObservationTargetType.DBL_STAR) &
                                            (DoubleStar.id == Observation.double_star_id) &
                                            (DoubleStar.common_cat_id == double_star_q))
                                           |
                                           ((Observation.target_type == ObservationTargetType.PLANET) &
                                            (Planet.id == Observation.planet_id) &
                                            (Planet.iau_code == planet_q))
                                           |
                                           ((Observation.target_type == ObservationTargetType.COMET) &
                                            (Comet.id == Observation.comet_id) &
                                            (Comet.designation == comet_q))
                                           |
                                           ((Observation.target_type == ObservationTargetType.M_PLANET) &
                                            (MinorPlanet.id == Observation.minor_planet_id) &
                                            (MinorPlanet.designation == minor_planet_q))
                                           )

    observations = observations.order_by(Observation.date_from.desc())
    statement = observations.statement
    print(str(statement), flush=True)
    search = False

    observations_for_render = observations.limit(per_page).offset(offset).all()

    pagination = Pagination(page=page, per_page=per_page, total=observations.count(), search=search, record_name='observations', css_framework='semantic')
    return render_template('main/observation/standalone_observations.html', observations=observations_for_render, pagination=pagination,
                           search_form=search_form)


@main_standalone_observation.route('/standalone-observation/<int:observation_id>', methods=['GET'])
@main_standalone_observation.route('/standalone-observation/<int:observation_id>/info', methods=['GET'])
def standalone_observation_info(observation_id):
    """View a standalone observation info."""
    observation = Observation.query.filter_by(id=observation_id).first()
    if observation is None:
        abort(404)
    if observation.user_id != current_user.id:
        abort(404)
    editable = observation.user_id == current_user.id
    return render_template('main/observation/standalone_observation_info.html', observation=observation, editable=editable)


@main_standalone_observation.route('/new-standalone-observation', methods=['GET', 'POST'])
@login_required
def new_standalone_observation():
    """Create new standalone observation"""
    form = StandaloneObservationNewForm()
    assign_equipment_choices(form)
    if request.method == 'POST' and form.validate_on_submit():
        location_position = None
        location_id = None
        if isinstance(form.location.data, int) or form.location.data.isdigit():
            location_id = int(form.location.data)
        else:
            location_position = form.location.data

        observation = Observation(
            user_id=current_user.id,
            date_from=form.date_from.data,
            date_to=form.date_to.data,
            location_id=location_id,
            location_position=location_position,
            sqm=form.sqm.data,
            faintest_star=form.faintest_star.data,
            seeing=form.seeing.data,
            telescope_id=form.telescope.data if form.telescope.data != -1 else None,
            eyepiece_id=form.eyepiece.data if form.eyepiece.data != -1 else None,
            filter_id=form.filter.data if form.filter.data != -1 else None,
            notes=form.notes.data,
            create_by=current_user.id,
            update_by=current_user.id,
            create_date=datetime.now(),
            update_date=datetime.now()
        )

        set_observation_targets(observation, form.target.data)

        db.session.add(observation)
        db.session.commit()
        flash(gettext('Observation successfully created'), 'form-success')
        return redirect(url_for('main_standalone_observation.standalone_observation_edit', observation_id=observation.id))

    location, location_position = _get_location_data2_from_form(form)

    return render_template('main/observation/standalone_observation_edit.html', form=form, is_new=True, location=location, location_position=location_position)


@main_standalone_observation.route('/standalone-observation/<int:observation_id>/edit', methods=['GET', 'POST'])
@login_required
def standalone_observation_edit(observation_id):
    """Update standalone observation"""
    observation = Observation.query.filter_by(id=observation_id).first()
    _check_observation(observation)

    form = StandaloneObservationEditForm()
    assign_equipment_choices(form)
    if request.method == 'POST':
        if form.validate_on_submit():
            location_position = None
            location_id = None
            if isinstance(form.location.data, int) or form.location.data.isdigit():
                location_id = int(form.location.data)
            else:
                location_position = form.location.data

            set_observation_targets(observation, form.target.data)

            observation.user_id = current_user.id
            observation.date_from = form.date_from.data
            observation.date_to = form.date_to.data
            observation.location_id = location_id
            observation.location_position = location_position
            observation.sqm = form.sqm.data
            observation.faintest_star = form.faintest_star.data
            observation.seeing = form.seeing.data
            observation.telescope_id = form.telescope.data if form.telescope.data != -1 else None
            observation.eyepiece_id = form.eyepiece.data if form.eyepiece.data != -1 else None
            observation.filter_id = form.filter.data if form.filter.data != -1 else None
            observation.notes = form.notes.data
            observation.update_by = current_user.id
            observation.update_date = datetime.now()

            db.session.add(observation)
            db.session.commit()

            flash(gettext('Observation successfully updated'), 'form-success')

            if form.goback.data == 'true':
                return redirect(url_for('main_standalone_observation.standalone_observation_info', observation_id=observation.id))
            return redirect(url_for('main_standalone_observation.standalone_observation_edit', observation_id=observation.id))
    else:
        form.observing_session_id.data = observation.observing_session_id
        form.target.data = observation.get_target_name()
        form.date_from.data = observation.date_from
        form.date_to.data = observation.date_to
        form.location.data = observation.location_id if observation.location_id is not None else observation.location_position
        form.sqm.data = observation.sqm
        form.faintest_star.data = observation.faintest_star
        form.seeing.data = observation.seeing if observation.seeing else Seeing.AVERAGE
        form.telescope.data = observation.telescope_id if observation.telescope_id is not None else -1
        form.eyepiece.data = observation.eyepiece_id if observation.eyepiece_id is not None else -1
        form.filter.data = observation.filter_id if observation.filter_id is not None else -1
        form.notes.data = observation.notes

    location, location_position = _get_location_data2_from_form(form)

    return render_template('main/observation/standalone_observation_edit.html', form=form, is_new=False, observation=observation,
                           location=location, location_position=location_position)


@main_standalone_observation.route('/standalone-observation/<int:observation_id>/delete')
@login_required
def standalone_observation_delete(observation_id):
    """Request deletion of a standalone observation."""
    observation = Observation.query.filter_by(id=observation_id).first()
    _check_observation(observation)
    db.session.delete(observation)
    db.session.commit()
    flash(gettext('Observation was deleted'), 'form-success')
    return redirect(url_for('main_standalone_observation.standalone_observations'))


def _get_location_data2_from_form(form):
    location_position = None
    location = None
    if form.location.data and (isinstance(form.location.data, int) or form.location.data.isdigit()):
        location = Location.query.filter_by(id=int(form.location.data)).first()
    else:
        location_position = form.location.data

    return location, location_position


def _check_observation(observation):
    if observation is None:
        abort(404)
    if current_user.is_anonymous:
        abort(404)
    elif observation.user_id != current_user.id:
        abort(404)
