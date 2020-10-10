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

from app import db

from app.models import DeepskyObject, Location, SessionPlan, SkyList, SkyListItem, User, WishList, WishListItem
from app.commons.pagination import Pagination, get_page_parameter
from app.main.views import ITEMS_PER_PAGE
from app.commons.search_utils import process_session_search

from .planner_forms import (
    AddToSessionPlanForm,
    AddToWishListForm,
    SearchSessionPlanForm,
    SessionPlanNewForm,
    SessionPlanEditForm,
)

from app.commons.dso_utils import normalize_dso_name

main_planner = Blueprint('main_planner', __name__)

@main_planner.route('/planner-menu', methods=['GET'])
@login_required
def planner_menu():
    return render_template('main/planner/planner_menu.html')

@main_planner.route('/session-plans',  methods=['GET', 'POST'])
@login_required
def session_plans():
    """View session plans."""
    search_form = SearchSessionPlanForm()

    (search_expr,) = process_session_search([('session_plan_search', search_form.q)])

    session_plans = SessionPlan.query
    if search_expr:
        session_plans = session_plans.filter(SessionPlan.title.like('%' + search_expr + '%'))

    return render_template('main/planner/session_plans.html', session_plans=session_plans, search_form=search_form)

@main_planner.route('/session-plan/<int:session_plan_id>', methods=['GET'])
@main_planner.route('/session-plan/<int:session_plan_id>/info', methods=['GET'])
@login_required
def session_plan_info(session_plan_id):
    """View a session plan info."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    if session_plan is None:
        abort(404)
    if session_plan.user_id != current_user.id:
        abort(404)
    add_form = AddToSessionPlanForm()
    add_form.session_plan_id.data = session_plan.id
    return render_template('main/planner/session_plan_info.html', session_plan=session_plan, add_form=add_form)

@main_planner.route('/new-session-plan', methods=['GET', 'POST'])
@login_required
def new_session_plan():
    """Create new session plan"""
    form = SessionPlanNewForm()
    if request.method == 'POST' and form.validate_on_submit():

        new_sky_list = SkyList(
            user_id = current_user.id,
            name = 'future',
            create_by = current_user.id,
            update_by = current_user.id,
            create_date = datetime.now(),
            update_date = datetime.now(),
        )

        new_session_plan = SessionPlan(
            user_id = current_user.id,
            title = form.title.data,
            for_date = form.for_date.data,
            location_id = form.location_id.data,
            notes = form.notes.data,
            sky_list = new_sky_list,
            create_by = current_user.id,
            update_by = current_user.id,
            create_date = datetime.now(),
            update_date = datetime.now(),
            )

        db.session.add(new_session_plan)
        db.session.commit()
        new_sky_list.name = 'SessionPlan[user.id={}]'.format(new_session_plan.id)
        db.session.add(new_sky_list)
        db.session.commit()

        flash('Session plan successfully created', 'form-success')
        return redirect(url_for('main_planner.session_plan_edit', session_plan_id=new_session_plan.id))

    location = None
    if form.location_id.data:
        location = Location.query.filter_by(id=form.location_id.data).first()
    return render_template('main/planner/session_plan_edit.html', form=form, is_new=True, location=location)


@main_planner.route('/session-plan/<int:session_plan_id>/edit', methods=['GET', 'POST'])
@login_required
def session_plan_edit(session_plan_id):
    """Update session plan"""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    if session_plan is None:
        abort(404)
    if session_plan.user_id != current_user.id:
        abort(404)
    form = SessionPlanEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            pass
    else:
        form.title.data = session_plan.title
        form.for_date.data = session_plan.for_date
        form.location_id.data = session_plan.location_id
        form.notes.data = session_plan.notes

    location = None
    if form.location_id.data:
        location = Location.query.filter_by(id=form.location_id.data).first()

    return render_template('main/planner/session_plan_edit.html', form=form, is_new=False, session_plan=session_plan, location=location)

@main_planner.route('/session-plan/<int:session_plan_id>/delete')
@login_required
def session_plan_delete(session_plan_id):
    """Request deletion of a observation."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    if session_plan is None:
        abort(404)
    if session_plan.user_id != current_user.id:
        abort(404)
    db.session.delete(session_plan)
    flash('Session plan was deleted', 'form-success')
    return redirect(url_for('main_planner.session_plans'))

@main_planner.route('/session-plan-item-add', methods=['POST'])
@login_required
def session_plan_item_add():
    """Add item to session plan."""
    form = AddToSessionPlanForm()
    if request.method == 'POST' and form.validate_on_submit():
        session_plan = SessionPlan.query.filter_by(id=form.session_plan_id.data).first()
        if session_plan is None:
            abort(404)
        if session_plan.user_id != current_user.id:
            abort(404)
        dso_name = normalize_dso_name(form.dso_name.data)
        deepsky_object = DeepskyObject.query.filter(DeepskyObject.name==dso_name).first()
        if deepsky_object:
            if session_plan.append_deepsky_object(deepsky_object.id, current_user.id):
                flash('Object was added to session plan.', 'form-success')
            else:
                flash('Object is already on session plan.', 'form-info')
        else:
            flash('Deepsky object not found.', 'form-error')

    return redirect(url_for('main_planner.session_plan_info', session_plan_id=session_plan.id))

@main_planner.route('/session-plan-item/<int:item_id>/delete')
@login_required
def session_plan_item_remove(item_id):
    """Remove item from session plan."""
    list_item = SkyListItem.query.filter_by(id=item_id).first()
    if list_item is None:
        abort(404)
    session_plan = SessionPlan.query.filter_by(sky_list_id=list_item.sky_list.id).first()
    if session_plan is None:
        abort(404)
    if session_plan.user_id != current_user.id:
        abort(404)
    db.session.delete(list_item)
    flash('Session plan item was deleted', 'form-success')
    return redirect(url_for('main_planner.session_plan_info', session_plan_id=session_plan.id))

@main_planner.route('/wish-list', methods=['GET'])
@login_required
def wish_list():
    """View wish list."""
    add_form = AddToWishListForm()
    wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
    return render_template('main/planner/wish_list.html', wish_list=wish_list, add_form=add_form)

@main_planner.route('/wish-list-item-add', methods=['POST'])
@login_required
def wish_list_item_add():
    """Add item to wish list."""
    form = AddToWishListForm()
    dso_name = normalize_dso_name(form.dso_name.data)
    if request.method == 'POST' and form.validate_on_submit():
        deepsky_object = DeepskyObject.query.filter(DeepskyObject.name==dso_name).first()
        if deepsky_object:
            wish_list = WishList.create_get_wishlist_by_user_id(current_user.id)
            if wish_list.append_deepsky_object(deepsky_object.id, current_user.id):
                flash('Object was added to wishlist.', 'form-success')
            else:
                flash('Object is already on wishlist.', 'form-info')
        else:
            flash('Deepsky object not found.', 'form-error')

    return redirect(url_for('main_planner.wish_list'))

@main_planner.route('/wish-list-item/<int:item_id>/delete')
@login_required
def wish_list_item_remove(item_id):
    """Remove item to wish list."""
    wish_list_item = WishListItem.query.filter_by(id=item_id).first()
    if wish_list_item is None:
        abort(404)
    if wish_list_item.wish_list.user_id != current_user.id:
        abort(404)
    db.session.delete(wish_list_item)
    flash('Wishlist item was deleted', 'form-success')
    return redirect(url_for('main_planner.wish_list'))

