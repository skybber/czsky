import os

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app import db

from app.commons.dso_utils import normalize_dso_name

from app.models import (
    SessionPlan,
)

main_planner = Blueprint('main_planner', __name__)

@main_planner.route('/planner-menu', methods=['GET'])
@login_required
def planner_menu():
    return render_template('main/planner/planner_menu.html')


@main_planner.route('/anonymous-planner-menu', methods=['GET'])
def anonymous_planner_menu():
    if not current_user.is_anonymous:
        return redirect(url_for('main_planner.planner_menu'))

    session_plan_id = session.get('session_plan_id')
    if session_plan_id:
        session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
        if not session_plan.is_anonymous:
            session.pop('session_plan_id')
            session_plan_id = None

    if not session_plan_id:
        return redirect(url_for('main_sessionplan.new_session_plan'))

    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan_id))


