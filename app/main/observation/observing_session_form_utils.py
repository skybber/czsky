from datetime import datetime

from flask import (
    flash,
)
from flask_login import current_user

from app import db

from app.models import DeepskyObject, ObservingSession, Observation
from app.commons.dso_utils import normalize_dso_name


def _parse_compound_notes(comp_notes):
    if ':' in comp_notes:
        comp_dso, notes = comp_notes.split(':', 1)
        return comp_dso.split(','), notes
    else:
        return (), comp_notes


def create_from_basic_form(form):
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
        rating=form.rating.data,
        weather=form.weather.data,
        equipment=form.equipment.data,
        notes=form.notes.data,
        create_by=current_user.id,
        update_by=current_user.id,
        create_date=datetime.now(),
        update_date=datetime.now()
        )

    for item_form in form.items[1:]:
        item_time = datetime.combine(observing_session.date_from, item_form.date_from.data)
        dsos, notes = _parse_compound_notes(item_form.comp_notes.data)
        observation = Observation(
            observing_session_id=observing_session.id,
            date_from=item_time,
            date_to=item_time,
            notes=notes,
            )
        observing_session.observations.append(observation)

        for dso_name in dsos:
            dso_name = normalize_dso_name(dso_name)
            dso = DeepskyObject.query.filter_by(name=dso_name).first()
            if dso:
                observation.deepsky_objects.append(dso)
            else:
                flash('Deepsky object \'' + dso_name + '\' not found', 'form-warning')

    db.session.add(observing_session)
    db.session.commit()
    flash('ObservingSession successfully created', 'form-success')
    return observing_session.id


def update_from_basic_form(form, observing_session):
    location_position = None
    location_id = None
    if isinstance(form.location.data, int) or form.location.data.isdigit():
        location_id = int(form.location.data)
    else:
        location_position = form.location.data

    if observing_session.id is not None:
        for observation in observing_session.observations:
            observation.deepsky_objects = []
            db.session.delete(observation)
        observing_session.observations.clear()

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
    observing_session.observations.clear()
    observing_session.is_public = form.is_public.data

    for item_form in form.items[1:]:
        item_time = datetime.combine(observing_session.date_from, item_form.date_from.data)
        dsos, notes = _parse_compound_notes(item_form.comp_notes.data)
        observation = Observation(
            observing_session_id=observing_session.id,
            date_from=item_time,
            date_to=item_time,
            notes=notes
            )
        observing_session.observations.append(observation)

        for dso_name in dsos:
            dso_name = normalize_dso_name(dso_name)
            dso = DeepskyObject.query.filter_by(name=dso_name).first()
            if dso:
                observation.deepsky_objects.append(dso)
            else:
                flash('Deepsky object \'' + dso_name + '\' not found', 'form-warning')

    db.session.add(observing_session)
    db.session.commit()
    flash('Observing session successfully updated', 'form-success')
