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

from app.commons.pagination import Pagination, get_page_parameter
from app.main.views import ITEMS_PER_PAGE

main_planner = Blueprint('main_planner', __name__)

@main_planner.route('/planner-menu', methods=['GET'])
@login_required
def planner_menu():
    return render_template('main/planner/planner_menu.html')

@main_planner.route('/session-plans', methods=['GET'])
@login_required
def session_plans():
    """View session plans."""
    # session_plans = SessionPlans.query.filter_by(user_id=current_user.id)
    return render_template('main/planner/session_plans.html', session_plans=session_plans)

@main_planner.route('/session-plan/<int:session_plan_id>', methods=['GET'])
@main_planner.route('/session-plan/<int:session_plan_id>/info', methods=['GET'])
@login_required
def session_plan_info(session_plan_id):
    """View a session plan info."""
    session_plan = SessionPlans.query.filter_by(id=session_plan_id).first()
    if session_plan is None:
        abort(404)
    if session_plan.user_id != current_user.id:
        abort(404)
    return render_template('main/planner/session_plan_info.html', session_plan=session_plan)

@main_planner.route('/new-session-plan', methods=['GET', 'POST'])
@login_required
def new_session_plan():
    """Create new session plan"""
#    form = ObservationNewForm()
#    if request.method == 'POST' and form.validate_on_submit():
#        if form.advmode.data == 'true':
#            new_observation_id = create_from_advanced_form(form)
#        else:
#            new_observation_id = create_from_basic_form(form)
#        if new_observation_id:
#            return redirect(url_for('main_planner.observation_edit', observation_id=new_observation_id))
#
#    location = None
#    if form.location_id.data:
#        location = Location.query.filter_by(id=form.location_id.data).first()
    return render_template('main/planner/session_plan_edit.html', form=form, is_new=True, location=location)

@main_planner.route('/wish-list', methods=['GET'])
@login_required
def wish_list():
    """View wish list."""
    # session_plans = SessionPlans.query.filter_by(user_id=current_user.id)
    return render_template('main/planner/wish_list.html', session_plans=session_plans)
