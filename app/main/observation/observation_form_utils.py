from datetime import datetime

from flask import (
    flash,
)
from flask_login import current_user

from app import db

from app.models import DeepskyObject, Observation, ObservationItem
from .observation_parser import parse_observation

def save_basic_form_data(form):
    observation = Observation(
        user_id = current_user.id,
        title = form.title.data,
        date = form.date.data,
        rating = form.rating.data,
        location = form.location.data,
        notes = form.notes.data,
        create_by = current_user.id,
        update_by = current_user.id,
        create_date = datetime.now(),
        update_date = datetime.now()
        )

    for item_form in form.items:
        item = ObservationItem(
            observation_id = observation.id,
            date_time = item_form.date_time.data,
            deepsky_objects = item_form.deepsky_object_id_list.data,
            notes = item_form.notes
            )
        observation.observation_items.add(item)

        for dso_name in item.deepsky_objects.split(','):
            dso = DeepskyObject.query.filter_by(name=dso_name).first()
            if dso:
                item.deepsky_objects.append(dso)
            else:
                flash('Deepsky object \'' + dso_name + '\' not found', 'form-warning')

    db.session.add(observation)
    db.session.commit()
    flash('Observation successfully created', 'form-success')

def save_advanced_form_data(form):
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
    else:
        for error in error_msgs:
            flash(error, 'form-error')
