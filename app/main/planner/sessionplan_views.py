import os
import csv
from datetime import datetime

from werkzeug.utils import secure_filename

import numpy as np

from astropy.time import Time
from astropy.coordinates import EarthLocation, SkyCoord
import astropy.units as u
from astroplan import Observer

from flask import (
    abort,
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

from app.models import (
    Catalogue,
    Constellation,
    DeepskyObject,
    DsoList,
    Location,
    SessionPlan,
    SkyList,
    SkyListItem,
    User,
    WishList,
    WishListItem,
)

from app.commons.pagination import Pagination, get_page_parameter
from app.commons.search_utils import process_session_search, process_paginated_session_search, get_items_per_page, create_table_sort, get_catalogues_menu_items

from .sessionplan_forms import (
    AddToSessionPlanForm,
    SearchSessionPlanForm,
    SessionPlanNewForm,
    SessionPlanEditForm,
    SessionPlanScheduleSearch,
)

from app.commons.dso_utils import normalize_dso_name

main_sessionplan = Blueprint('main_sessionplan', __name__)


@main_sessionplan.route('/session-plans',  methods=['GET', 'POST'])
@login_required
def session_plans():
    """View session plans."""
    search_form = SearchSessionPlanForm()

    if not process_session_search([('session_plan_search', search_form.q)]):
        return redirect(url_for('main_sessionplan.session_plans'))

    session_plans = SessionPlan.query.filter_by(user_id=current_user.id)
    if search_form.q.data:
        session_plans = session_plans.filter(SessionPlan.title.like('%' + search_form.q.data + '%'))

    return render_template('main/planner/session_plans.html', session_plans=session_plans, search_form=search_form)


@main_sessionplan.route('/session-plan/<int:session_plan_id>/info', methods=['GET', 'POST'])
@login_required
def session_plan_info(session_plan_id):
    """View a session plan info."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    if session_plan is None:
        abort(404)

    if session_plan.user_id != current_user.id:
        abort(404)
    form = SessionPlanEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            session_plan.title = form.title.data
            session_plan.for_date = form.for_date.data
            session_plan.location_id = form.location_id.data
            session_plan.notes = form.notes.data
            session_plan.update_by = current_user.id
            session_plan.update_date = datetime.now()
            db.session.add(session_plan)
            db.session.commit()
            flash('Session plan successfully updated', 'form-success')
            return redirect(url_for('main_sessionplan.session_plan_info', session_plan_id=session_plan.id))
    else:
        form.title.data = session_plan.title
        form.for_date.data = session_plan.for_date
        form.location_id.data = session_plan.location_id
        form.notes.data = session_plan.notes

    location = None
    if form.location_id.data:
        location = Location.query.filter_by(id=form.location_id.data).first()

    return render_template('main/planner/session_plan.html', tab='info', session_plan=session_plan, form=form, location=location)


@main_sessionplan.route('/session-plan/<int:session_plan_id>/schedule', methods=['GET', 'POST'])
@login_required
def session_plan_schedule(session_plan_id):
    """View a session plan schedule."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    if session_plan is None:
        abort(404)
    if session_plan.user_id != current_user.id:
        abort(404)

    search_form = SessionPlanScheduleSearch()

    sort_by = request.args.get('sortby')

    ret, page = process_paginated_session_search('planner_search_page', [
        ('planner_dso_type', search_form.dso_type),
        ('planner_dso_obj_source', search_form.obj_source),
        ('planner_dso_maglim', search_form.maglim),
        ]);

    if not ret:
        return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan_id, page=page, sortby=sort_by))

    per_page = get_items_per_page(search_form.items_per_page)

    offset = (page - 1) * per_page

    mag_scale = (8, 16)

    sort_def = { 'name': DeepskyObject.name,
                 'type': DeepskyObject.type,
                 'constellation': DeepskyObject.constellation_id,
                 'mag': DeepskyObject.mag,
    }

    table_sort = create_table_sort(sort_by, sort_def.keys())

    if search_form.obj_source.data is None or search_form.obj_source.data == 'WL':
        selection_list = []
        wish_list = WishList.query.filter_by(user_id=current_user.id).first()
        if wish_list and wish_list.wish_list_items:
            for item in wish_list.wish_list_items:
                if item.deepskyObject is not None:
                    selection_list.append(item.deepskyObject)
        all_count = len(selection_list)
    elif search_form.obj_source.data.startswith('DL_'):
        dso_list_id = int(search_form.obj_source.data[3:])
        dso_list = DsoList.query.filter_by(id=dso_list_id).first()
        selection_list = []
        if dso_list:
            selection_list = [ x.deepskyObject for x in dso_list.dso_list_items ]
        else:
            selection_list = []
        all_count = len(selection_list)
    else:
        selection_dsos = DeepskyObject.query
        cat_id = Catalogue.get_catalogue_id_by_cat_code(search_form.obj_source.data)
        if cat_id:
            selection_dsos = selection_dsos.filter_by(catalogue_id=cat_id)

        if search_form.dso_type.data and search_form.dso_type.data != 'All':
            selection_dsos = selection_dsos.filter(DeepskyObject.type==search_form.dso_type.data)

        if search_form.maglim.data is not None and search_form.maglim.data < mag_scale[1]:
            selection_dsos = selection_dsos.filter(DeepskyObject.mag<search_form.maglim.data)

        order_by_field = None
        if sort_by:
            desc = sort_by[0] == '-'
            sort_by_name = sort_by[1:] if desc else sort_by
            order_by_field = sort_def.get(sort_by_name)
            if order_by_field and desc:
                order_by_field = order_by_field.desc()

        if order_by_field is None:
            order_by_field = DeepskyObject.id

        page_dsos = selection_dsos.order_by(order_by_field).limit(per_page).offset(offset).all()

        all_count = selection_dsos.count()

        selection_list = page_dsos.copy()

    pagination = Pagination(page=page, total=all_count, search=False, record_name='deepskyobjects', css_framework='semantic', not_passed_args='back')

    for item in session_plan.sky_list.sky_list_items:
        if item.deepskyObject:
            selection_list = list(filter(lambda x: x.id != item.deepskyObject.id, selection_list))

    add_form = AddToSessionPlanForm()
    add_form.session_plan_id.data = session_plan.id
    catalogues_menu_items = get_catalogues_menu_items()

    dso_lists = DsoList.query.all()

    loc = session_plan.location

    loc_coords = EarthLocation.from_geodetic(loc.longitude*u.deg, loc.latitude*u.deg, loc.elevation*u.m if loc.elevation else 0)
    t = Time(session_plan.for_date)
    observer = Observer(name=loc.name, location=loc_coords, timezone='Europe/Prague')

    selection_rms_list = rise_merid_set_time(t, observer, [ (x.ra, x.dec) for x in selection_list])
    selection_compound_list = [ (selection_list[i], *selection_rms_list[i]) for i in range(len(selection_list))]

    sli = session_plan.sky_list.sky_list_items
    session_plan_rms_list = rise_merid_set_time(t, observer, [ (x.deepskyObject.ra, x.deepskyObject.dec) for x in sli])
    session_plan_compound_list = [ (sli[i], *session_plan_rms_list[i]) for i in range(len(sli))]

    return render_template('main/planner/session_plan.html', tab='schedule', session_plan=session_plan,
                           selection_compound_list=selection_compound_list, session_plan_compound_list=session_plan_compound_list,
                           dso_lists=dso_lists, catalogues_menu_items=catalogues_menu_items, mag_scale=mag_scale,
                           add_form=add_form, search_form=search_form, pagination=pagination,table_sort=table_sort)


def rise_merid_set_time(t, observer, ra_dec_list):
    coords = [ SkyCoord(x[0] * u.rad, x[1] * u.rad) for x in ra_dec_list]
    rise_list = to_HM_format(observer.target_rise_time(t, coords)) if len(coords) > 0 else []
    merid_list = to_HM_format(observer.target_meridian_transit_time(t, coords))  if len(coords) > 0 else []
    set_list = to_HM_format(observer.target_set_time(t, coords)) if len(coords) > 0 else []

    return [(rise_list[i], merid_list[i], set_list[i]) for i in range(len(rise_list))]

def to_HM_format(tm):
    ret = []
    try:
        it = iter(tm)
    except TypeError:
        tm = [tm]

    for t in tm:
        try:
            ret.append(t.strftime("%H:%M"))
        except ValueError:
            ret.append('')
    return ret


@main_sessionplan.route('/new-session-plan', methods=['GET', 'POST'])
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
        return redirect(url_for('main_sessionplan.session_plan_info', session_plan_id=new_session_plan.id))

    location = None
    if form.location_id.data:
        location = Location.query.filter_by(id=form.location_id.data).first()

    return render_template('main/planner/session_plan.html', tab='info', form=form, is_new=True, location=location)


@main_sessionplan.route('/session-plan/<int:session_plan_id>/delete')
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
    return redirect(url_for('main_sessionplan.session_plans'))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/clear')
@login_required
def session_plan_clear(session_plan_id):
    """Request deletion of a observation."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    if session_plan is None:
        abort(404)
    if session_plan.user_id != current_user.id:
        abort(404)

    SkyListItem.query.filter_by(sky_list_id=session_plan.sky_list_id).delete()
    db.session.commit()
    flash('Session items deleted', 'form-success')
    session['is_backr'] = True
    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan.id))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/item-add', methods=['GET', 'POST'])
@login_required
def session_plan_item_add(session_plan_id):
    """Add item to session plan."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    if session_plan is None:
        abort(404)
    if session_plan.user_id != current_user.id:
        abort(404)

    deepsky_object = None
    form = AddToSessionPlanForm()
    if request.method == 'POST' and form.validate_on_submit():
        dso_name = normalize_dso_name(form.dso_name.data)
        deepsky_object = DeepskyObject.query.filter(DeepskyObject.name==dso_name).first()
    elif request.method == 'GET':
        dso_id = request.args.get('dso_id', None)
        if dso_id is not None:
            deepsky_object = DeepskyObject.query.filter(DeepskyObject.id==dso_id).first()

    if deepsky_object:
        if session_plan.append_deepsky_object(deepsky_object.id, current_user.id):
            flash('Object was added to session plan.', 'form-success')
        else:
            flash('Object is already on session plan.', 'form-info')
    else:
        flash('Deepsky object not found.', 'form-error')

    session['is_backr'] = True
    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan_id))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/item/<int:item_id>/delete')
@login_required
def session_plan_item_delete(session_plan_id, item_id):
    """Remove item from session plan."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    if session_plan is None:
        abort(404)
    if session_plan.user_id != current_user.id:
        abort(404)

    list_item = SkyListItem.query.filter_by(id=item_id).first()
    if list_item is not None:
        session_plan2 = SessionPlan.query.filter_by(sky_list_id=list_item.sky_list.id).first()
        if session_plan2 is not None and session_plan2.id == session_plan.id:
            db.session.delete(list_item)
            flash('Session plan item was deleted', 'form-success')

    session['is_backr'] = True
    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan.id))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/upload', methods=['POST'])
@login_required
def session_plan_upload(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    if session_plan is None:
        abort(404)
    if session_plan.user_id != current_user.id:
        abort(404)

    if 'file' not in request.files:
        flash('No file part', 'form-error')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file:
        filename = secure_filename(file.filename)
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        with open(path) as csvfile:
            reader = csv.DictReader(csvfile, delimiter=';', fieldnames=['DSO_NAME'])
            existing_ids = set(item.dso_id for item in session_plan.sky_list.sky_list_items)

            for row in reader:
                dso_name = row['DSO_NAME']
                if dso_name == 'none':
                    continue

                dso_name = normalize_dso_name(dso_name)
                dso = DeepskyObject.query.filter(DeepskyObject.name==dso_name).first()

                if dso and not dso.id in existing_ids:

                    if not session_plan.sky_list.find_dso_in_skylist(dso.id):
                        new_item = session_plan.create_new_sky_list_item(session_plan.sky_list_id, dso.id, current_user.id)
                        db.session.add(new_item)

                    existing_ids.add(dso.id)
        db.session.commit()
        os.remove(path)
        flash('Session plan uploaded.', 'form-success')

    session['is_backr'] = True
    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan.id))
