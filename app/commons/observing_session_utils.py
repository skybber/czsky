import pytz
from datetime import datetime

from flask import (
    abort,
    request,
    url_for,
)
from flask_login import current_user

from app.models import (
    ObservingSession,
    ObsSessionPlanRun,
)

def find_observing_session(back, back_id):
    if back == 'running_plan':
        observation_plan_run = ObsSessionPlanRun.query.filter_by(id=back_id).first()
        if observation_plan_run is not None and observation_plan_run.session_plan.user_id == current_user.id:
            return observation_plan_run.observing_session
    elif back == 'observation':
        observing_session = ObservingSession.query.filter_by(id=back_id).first()
        if observing_session is not None and observing_session.user_id == current_user.id:
            return observing_session
    elif not current_user.is_anonymous:
        active_observing_session = ObservingSession.query.filter_by(user_id=current_user.id, is_active=True).first()
        if active_observing_session is not None:
            return active_observing_session
    abort(404)

def show_observation_log():
    back = request.args.get('back')
    back_id = request.args.get('back_id')
    if back == 'running_plan':
        if back_id:
            observation_plan_run = ObsSessionPlanRun.query.filter_by(id=back_id).first()
            if observation_plan_run is not None and observation_plan_run.session_plan.user_id == current_user.id:
                return True
    elif back == 'observation':
        if back_id:
            observing_session = ObservingSession.query.filter_by(id=back_id).first()
            if observing_session and not current_user.is_anonymous and observing_session.user_id == current_user.id and not observing_session.is_finished:
                return True
    elif not current_user.is_anonymous:
        active_observing_session = ObservingSession.query.filter_by(user_id=current_user.id, is_active=True).first()
        if active_observing_session:
            return True
    return False

def combine_observing_session_date_time(observing_session, date_part, time_part):
    tz_info = pytz.timezone('Europe/Prague')
    return datetime.combine(date_part, time_part, tz_info)
