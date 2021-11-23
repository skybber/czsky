from datetime import datetime

from flask import (
    flash,
)
from flask_login import current_user

from app import db

from app.models import DeepskyObject, Observation, ObservationItem
from .observation_parser import parse_observation
from app.commons.dso_utils import normalize_dso_name


def create_from_basic_form(form):
    location_position = None
    location_id = None
    if isinstance(form.location.data, int) or form.location.data.isdigit():
        location_id = int(form.location.data)
    else:
        location_position = form.location.data
    observation = Observation(
        user_id=current_user.id,
        title=form.title.data,
        date=form.date.data,
        location_id=location_id,
        location_position=location_position,
        sqm=form.sqm.data,
        seeing=form.seeing.data,
        transparency=form.transparency.data,
        rating=form.rating.data,
        notes=form.notes.data,
        create_by=current_user.id,
        update_by=current_user.id,
        create_date=datetime.now(),
        update_date=datetime.now()
        )

    for item_form in form.items[1:]:
        item_time = datetime.combine(observation.date, item_form.date_time.data)
        item = ObservationItem(
            observation_id=observation.id,
            date_time=item_time,
            txt_deepsky_objects=item_form.deepsky_object_id_list.data,
            notes=item_form.notes.data
            )
        observation.observation_items.append(item)

        dsos = item.txt_deepsky_objects
        if ':' in dsos:
            dsos = dsos[:dsos.index(':')]
        for dso_name in dsos.split(','):
            dso_name = normalize_dso_name(dso_name)
            dso = DeepskyObject.query.filter_by(name=dso_name).first()
            if dso:
                item.deepsky_objects.append(dso)
            else:
                flash('Deepsky object \'' + dso_name + '\' not found', 'form-warning')

    db.session.add(observation)
    db.session.commit()
    flash('Observation successfully created', 'form-success')
    return observation.id


def create_from_advanced_form(form):
    observation, warn_msgs, error_msgs = parse_observation(form.omd_content.data)
    if observation:
        observation.user_id = current_user.id
        observation.omd_content = form.omd_content.data
        observation.create_by = current_user.id
        observation.update_by = current_user.id
        observation.create_date = datetime.now()
        observation.update_date = datetime.now()
        db.session.add(observation)
        db.session.commit()
        for warn in warn_msgs:
            flash(warn, 'form-warn')
        flash('Observation successfully created', 'form-success')
        return observation.id
    for error in error_msgs:
        flash(error, 'form-error')
    return None


def update_from_basic_form(form, observation):
    location_position = None
    location_id = None
    if isinstance(form.location.data, int) or form.location.data.isdigit():
        location_id = int(form.location.data)
    else:
        location_position = form.location.data

    if observation.id is not None:
        for item in observation.observation_items:
            item.deepsky_objects = []
            db.session.delete(item)
        observation.observation_items.clear()

    observation.user_id = current_user.id
    observation.title = form.title.data
    observation.date = form.date.data
    observation.location_id = location_id
    observation.location_position = location_position
    observation.sqm = form.sqm.data
    observation.seeing = form.seeing.data
    observation.transparency = form.transparency.data
    observation.rating = int(form.rating.data) * 2
    observation.notes = form.notes.data
    observation.update_by = current_user.id
    observation.update_date = datetime.now()
    observation.observation_items.clear()
    observation.is_public = form.is_public.data

    for item_form in form.items[1:]:
        item_time = datetime.combine(observation.date, item_form.date_time.data)
        item = ObservationItem(
            observation_id=observation.id,
            date_time=item_time,
            txt_deepsky_objects=item_form.deepsky_object_id_list.data,
            notes=item_form.notes.data
            )
        observation.observation_items.append(item)

        dsos = item.txt_deepsky_objects
        if ':' in dsos:
            dsos = dsos[:dsos.index(':')]
        for dso_name in dsos.split(','):
            dso_name = normalize_dso_name(dso_name)
            dso = DeepskyObject.query.filter_by(name=dso_name).first()
            if dso:
                item.deepsky_objects.append(dso)
            else:
                flash('Deepsky object \'' + dso_name + '\' not found', 'form-warning')

    db.session.add(observation)
    db.session.commit()
    flash('Observation successfully updated', 'form-success')


def update_from_advanced_form(form, observation):
    updated_observation, warn_msgs, error_msgs = parse_observation(form.omd_content.data)
    if updated_observation:
        observation.user_id = current_user.id
        observation.title = updated_observation.title
        observation.date = updated_observation.date,
        observation.rating = updated_observation.rating
        observation.notes = updated_observation.notes
        observation.is_public = updated_observation.is_public
        observation.omd_content = updated_observation.omd_content
        observation.update_by = current_user.id
        observation.update_date = datetime.now(),
        observation.observation_items.clear()
        observation.observation_items.extend(updated_observation.observation_items)
        db.session.add(observation)
        db.session.commit()
        for warn in warn_msgs:
            flash(warn, 'form-warn')
        flash('Observation successfully updated', 'form-success')
    else:
        for error in error_msgs:
            flash(error, 'form-error')
