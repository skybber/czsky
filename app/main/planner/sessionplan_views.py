import os
import csv
from io import StringIO, BytesIO
from datetime import datetime, timedelta
import base64
import pytz
import codecs

from werkzeug.utils import secure_filename

from astropy.time import Time
from astropy.coordinates import EarthLocation, SkyCoord
import astropy.units as u
from astroplan import Observer

from skyfield import almanac
from skyfield.api import load, wgs84

from flask import (
    abort,
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from flask_login import current_user, login_required

from flask_babel import gettext

from app import db, csrf

from app.models import (
    Constellation,
    DeepskyObject,
    DsoList,
    Location,
    ObservedList,
    SessionPlan,
    SessionPlanItem,
    SessionPlanItemType,
)

from app.commons.pagination import Pagination

from app.commons.search_utils import (
    process_session_search,
    process_paginated_session_search,
    get_items_per_page,
    create_table_sort,
    get_catalogues_menu_items,
    get_packed_constell_list
)

from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_chart_pdf_img,
    common_ra_dec_dt_fsz_from_request,
)

from .sessionplan_forms import (
    SCHEDULE_TIME_FORMAT,
    AddToSessionPlanForm,
    SearchSessionPlanForm,
    SessionPlanNewForm,
    SessionPlanEditForm,
    SessionPlanScheduleFilterForm,
)

from app.main.chart.chart_forms import ChartForm

from app.commons.dso_utils import normalize_dso_name, get_norm_visible_objects_set, chart_items_to_file
from app.commons.utils import get_anonymous_user
from app.commons.coordinates import parse_latlon
from app.commons.prevnext_utils import find_by_url_obj_id_in_list, get_default_chart_iframe_url
from app.commons.highlights_list_utils import common_highlights_from_session_plan, find_session_plan_observed

from .session_scheduler import create_selection_coumpound_list, create_session_plan_compound_list, reorder_by_merid_time
from .sessionplan_import import import_session_plan_items
from .sessionplan_export import create_oal_observations_from_session_plan
from app.commons.comet_utils import find_mpc_comet, get_mpc_comet_position
from app.commons.search_sky_object_utils import search_double_star, search_comet, search_minor_planet, search_planet, search_dso
from app.commons.minor_planet_utils import get_mpc_minor_planet_position, find_mpc_minor_planet
from app.commons.solar_system_chart_utils import get_mpc_planet_position

main_sessionplan = Blueprint('main_sessionplan', __name__)

min_alt_item_list = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45]


@main_sessionplan.route('/session-plans',  methods=['GET', 'POST'])
@login_required
def session_plans():
    """View session plans."""
    search_form = SearchSessionPlanForm()

    if not process_session_search([('session_plan_search', search_form.q),
                                   ('session_plan_status', search_form.status)
                                   ]):
        return redirect(url_for('main_sessionplan.session_plans'))

    session_plans = SessionPlan.query.filter_by(user_id=current_user.id)
    if search_form.status.data == 'Active':
        session_plans = session_plans.filter_by(is_archived=False)
    elif search_form.status.data == 'Archived':
        session_plans = session_plans.filter_by(is_archived=True)
    if search_form.q.data:
        session_plans = session_plans.filter(SessionPlan.title.like('%' + search_form.q.data + '%'))

    session_plans = session_plans.order_by(SessionPlan.for_date.desc())

    return render_template('main/planner/session_plans.html', session_plans=session_plans, search_form=search_form)


def _check_session_plan(session_plan, allow_public=False):
    if session_plan is None:
        abort(404)

    if current_user.is_anonymous:
        if not session_plan.is_anonymous or session.get('session_plan_id') != session_plan.id:
            if allow_public and session_plan.is_public:
                return False
            abort(404)
    elif session_plan.user_id != current_user.id:
        if allow_public and session_plan.is_public:
            return False
        abort(404)

    return True


@main_sessionplan.route('/session-plan/<int:session_plan_id>', methods=['GET'])
@main_sessionplan.route('/session-plan/<int:session_plan_id>/overview', methods=['GET'])  # backward compatibility
@main_sessionplan.route('/session-plan/<int:session_plan_id>/info', methods=['GET'])
def session_plan_info(session_plan_id):
    """View a session plan info."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    is_mine_session_plan = _check_session_plan(session_plan, allow_public=True)
    observed = { dso.id for dso in ObservedList.get_observed_dsos_by_user_id(current_user.id) } if not current_user.is_anonymous else None
    observer, tz_info = _get_observer_tzinfo(session_plan)
    observation_time = Time(session_plan.for_date)
    session_plan_compound_list = create_session_plan_compound_list(session_plan, observer, observation_time, tz_info, None)
    return render_template('main/planner/session_plan_info.html', type='info', session_plan=session_plan, is_mine_session_plan=is_mine_session_plan,
                           observed=observed, constellation_by_id_dict=Constellation.get_id_dict(), session_plan_compound_list=session_plan_compound_list)


@main_sessionplan.route('/new-session-plan', methods=['GET', 'POST'])
def new_session_plan():
    """Create new session plan"""
    form = SessionPlanNewForm()
    if request.method == 'POST' and form.validate_on_submit():
        new_session_plan = None
        if current_user.is_anonymous:
            if session.get('session_plan_id'):
                new_session_plan = SessionPlan.query.filter_by(id=session.get('session_plan_id')).first()

        if not new_session_plan:
            user = get_anonymous_user() if current_user.is_anonymous else current_user
            location_id, location_position = _get_location_data_from_form(form)
            new_session_plan = SessionPlan(
                user_id=user.id,
                title=form.title.data,
                for_date=form.for_date.data,
                location_id=location_id,
                location_position=location_position,
                is_public=form.is_public.data,
                is_archived=form.is_archived.data,
                notes=form.notes.data,
                is_anonymous=current_user.is_anonymous,
                create_by=user.id,
                update_by=user.id,
                create_date=datetime.now(),
                update_date=datetime.now(),
            )
            db.session.add(new_session_plan)
            db.session.commit()

            if current_user.is_anonymous:
                session['session_plan_id'] = new_session_plan.id

            flash(gettext('Session plan successfully created'), 'form-success')
        else:
            flash(gettext('Session plan already exists'), 'form-success')
        return redirect(url_for('main_sessionplan.session_plan_edit', session_plan_id=new_session_plan.id))

    location, location_position = _get_location_data2_from_form(form)
    return render_template('main/planner/session_plan_edit.html', form=form, is_new=True, location=location,
                           location_position=location_position, is_anonymous=current_user.is_anonymous)


@main_sessionplan.route('/session-plan/<int:session_plan_id>/edit', methods=['GET', 'POST'])
def session_plan_edit(session_plan_id):
    """View a session plan info."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()

    is_mine_session_plan = _check_session_plan(session_plan, allow_public=True)
    if not is_mine_session_plan:
        return redirect(url_for('main_sessionplan.session_plan_info', session_plan_id=session_plan.id))

    form = SessionPlanEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            user = get_anonymous_user() if current_user.is_anonymous else current_user
            location_id, location_position = _get_location_data_from_form(form)
            session_plan.title = form.title.data
            date_changed = (session_plan.for_date != form.for_date.data)
            session_plan.for_date = form.for_date.data
            session_plan.location_id = location_id
            session_plan.location_position = location_position
            session_plan.is_public = form.is_public.data
            session_plan.is_archived = form.is_archived.data
            session_plan.notes = form.notes.data
            session_plan.update_by = user.id
            session_plan.update_date = datetime.now()
            db.session.add(session_plan)
            if date_changed:
                for_date = datetime.combine(session_plan.for_date, datetime.min.time())
                for item in session_plan.session_plan_items:
                    ra, dec = None, None
                    if item.item_type == SessionPlanItemType.COMET:
                        ra, dec = get_mpc_comet_position(find_mpc_comet(item.comet.comet_id), for_date)
                    elif item.item_type == SessionPlanItemType.MINOR_PLANET:
                        ra, dec = get_mpc_minor_planet_position(find_mpc_minor_planet(item.minor_planet.int_designation), for_date)
                    elif item.item_type == SessionPlanItemType.PLANET:
                        ra, dec = get_mpc_planet_position(item.planet, for_date)
                    if (ra is not None) and (dec is not None):
                        ra = ra.radians
                        dec = dec.radians
                        if (ra != item.ra) or (dec != item.dec):
                            constell = Constellation.get_constellation_by_position(ra, dec)
                            item.ra = ra
                            item.dec = dec
                            item.constell_id = constell.id if constell else None
                            db.session.add(item)
            db.session.commit()
            flash(gettext('Session plan successfully updated'), 'form-success')
            if form.goback.data == 'true':
                return redirect(url_for('main_sessionplan.session_plan_info', session_plan_id=session_plan.id))
            return redirect(url_for('main_sessionplan.session_plan_edit', session_plan_id=session_plan.id))
    else:
        form.title.data = session_plan.title
        form.for_date.data = session_plan.for_date
        form.location.data = session_plan.location_id if session_plan.location_id is not None else session_plan.location_position
        form.is_public.data = session_plan.is_public
        form.is_archived.data = session_plan.is_archived
        form.notes.data = session_plan.notes

    location, location_position = _get_location_data2_from_form(form)

    return render_template('main/planner/session_plan_edit.html', session_plan=session_plan, form=form, is_new=False,
                           location=location, location_position=location_position, is_mine_session_plan=is_mine_session_plan)


def _get_location_data_from_form(form):
    location_position = None
    location_id = None
    if form.location.data and (isinstance(form.location.data, int) or form.location.data.isdigit()):
        location_id = int(form.location.data)
    else:
        location_position = form.location.data

    return location_id, location_position


def _get_location_data2_from_form(form):
    location_position = None
    location = None
    if form.location.data and (isinstance(form.location.data, int) or form.location.data.isdigit()):
        location = Location.query.filter_by(id=int(form.location.data)).first()
    else:
        location_position = form.location.data

    return location, location_position


@main_sessionplan.route('/session-plan/<int:session_plan_id>/delete')
def session_plan_delete(session_plan_id):
    """Request deletion of a observation."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    for item in session_plan.session_plan_items:
        db.session.delete(item)
    db.session.delete(session_plan)
    db.session.commit()

    flash(gettext('Session plan was deleted'), 'form-success')
    return redirect(url_for('main_sessionplan.session_plans'))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/clear')
def session_plan_clear(session_plan_id):
    """Request for clear of a session plan items."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    SessionPlanItem.query.filter_by(session_plan_id=session_plan_id).delete()
    db.session.commit()
    flash(gettext('Session items deleted'), 'form-success')
    session['is_backr'] = True
    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan.id))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/item-add', methods=['GET', 'POST'])
def session_plan_item_add(session_plan_id):
    """Add item to session plan."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    deepsky_object = None
    form = AddToSessionPlanForm()
    double_star, comet, minor_planet, planet, deepsky_object = None, None, None, None, None
    if request.method == 'POST' and form.validate_on_submit():
        query = form.object_id.data.strip()
        double_star = search_double_star(query, number_search=False)
        if not double_star:
            comet = search_comet(query)
            if not comet:
                planet = search_planet(query)
                if not planet:
                    minor_planet = search_minor_planet(query)
                    if not minor_planet:
                        deepsky_object = search_dso(query)

    elif request.method == 'GET':
        dso_id = request.args.get('dso_id', None)
        if dso_id is not None:
            deepsky_object = DeepskyObject.query.filter(DeepskyObject.id==dso_id).first()

    new_item = None
    if double_star:
        if not session_plan.find_double_star_item_by_id(double_star.id):
            new_item = session_plan.create_new_double_star_item(double_star.id)
    if comet:
        if not session_plan.find_comet_item_by_id(comet.id):
            comet_ra, comet_dec = get_mpc_comet_position(find_mpc_comet(comet.comet_id), session_plan.for_date)
            new_item = session_plan.create_new_comet_item(comet, comet_ra.radians, comet_dec.radians,
                                                          Constellation.get_constellation_by_position(comet_ra.radians, comet_dec.radians))
    if minor_planet:
        if not session_plan.find_minor_planet_item_by_id(minor_planet.id):
            mplanet_ra, mplanet_dec = get_mpc_minor_planet_position(find_mpc_minor_planet(minor_planet.int_designation), session_plan.for_date)
            new_item = session_plan.create_new_minor_planet_item(minor_planet, mplanet_ra.radians, mplanet_dec.radians,
                                                                 Constellation.get_constellation_by_position(mplanet_ra.radians, mplanet_dec.radians))
    if planet:
        if not session_plan.find_planet_item_by_id(planet.id):
            planet_ra, planet_dec = get_mpc_planet_position(planet, session_plan.for_date)
            new_item = session_plan.create_new_planet_item(planet, planet_ra.radians, planet_dec.radians,
                                                                 Constellation.get_constellation_by_position(planet_ra.radians, planet_dec.radians))
    if deepsky_object:
        if not session_plan.find_dso_item_by_id(deepsky_object.id):
            new_item = session_plan.create_new_deepsky_object_item(deepsky_object.id)

    if new_item is not None:
        db.session.add(new_item)
        db.session.commit()
        flash(gettext('Object was added to session plan.'), 'form-success')
        reorder_by_merid_time(session_plan)

    session['is_backr'] = True

    srow_index = request.args.get('row_index')

    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan_id, srow_index=srow_index))


@main_sessionplan.route('/session-plan-item/<int:item_id>/delete')
def session_plan_item_delete(item_id):
    """Remove item from session plan."""
    session_plan_item = SessionPlanItem.query.filter_by(id=item_id).first()
    if session_plan_item is None:
        abort(404)
    _check_session_plan(session_plan_item.session_plan)

    session_plan_id = session_plan_item.session_plan_id
    db.session.delete(session_plan_item)
    db.session.commit()
    flash(gettext('Session plan item was deleted'), 'form-success')

    session['is_backr'] = True
    drow_index = request.args.get('row_index')
    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan_id, drow_index=drow_index))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/import', methods=['POST'])
def session_plan_import(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    if 'file' not in request.files:
        flash(gettext('No file part'), 'form-error')
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        flash(gettext('No file selected'))
        return redirect(request.url)
    if file:
        is_oal = file.filename.lower().endswith('oal')
        filename = secure_filename(file.filename)
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(path)
        if is_oal:
            with open(path) as oalfile:
                log_warn, log_error = import_session_plan_items(session_plan, oalfile)
            db.session.commit()
            flash(gettext('Session plan uploaded.'), 'form-success')
        else:
            with open(path) as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';', fieldnames=['DSO_NAME'])
                existing_ids = set(item.dso_id for item in session_plan.session_plan_items)

                for row in reader:
                    dso_name = row['DSO_NAME']
                    if dso_name == 'none':
                        continue

                    dso_name = normalize_dso_name(dso_name)
                    dso = DeepskyObject.query.filter(DeepskyObject.name==dso_name).first()

                    if dso and dso.id not in existing_ids:
                        if not session_plan.find_dso_by_id(dso.id):
                            new_item = session_plan.create_new_deepsky_object_item(dso.id)
                            db.session.add(new_item)
                        existing_ids.add(dso.id)
                db.session.commit()
                os.remove(path)
                flash(gettext('Session plan uploaded.'), 'form-success')

    session['is_backr'] = True
    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan.id))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/export-csv', methods=['POST'])
def session_plan_export_csv(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    observer, tz_info = _get_observer_tzinfo(session_plan)
    observation_time = Time(session_plan.for_date)

    session_plan_compound_list = create_session_plan_compound_list(session_plan, observer, observation_time, tz_info, None)

    buf = StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_NONNUMERIC, delimiter=';')

    writer.writerow([gettext('Name'), gettext('Type'), gettext('Constellation'), 'RA', 'DEC', gettext('Rise'), gettext('Merid'), gettext('Set')])

    for item in session_plan_compound_list:
        dso = item[0].deepsky_object
        name = dso.denormalized_name() + (('/' + dso.master_dso.denormalized_name()) if dso.master_dso else '')
        writer.writerow([name, dso.type, dso.get_constellation_iau_code(), dso.ra_str_short(), dso.dec_str_short(), item[1], item[2], item[3]])

    mem = BytesIO()
    mem.write(buf.getvalue().encode('utf-8'))
    mem.seek(0)
    return send_file(mem, as_attachment=True,
                     download_name='sessionplan-' + session_plan.title.replace(' ', '_') + '.csv',
                     mimetype='text/csv')


@main_sessionplan.route('/session-plan/<int:session_plan_id>/export-oal', methods=['POST'])
def session_plan_export_oal(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    buf = StringIO()
    buf.write('<?xml version="1.0" encoding="utf-8"?>\n')
    oal_observations = create_oal_observations_from_session_plan(current_user, session_plan)
    oal_observations.export(buf, 0)
    mem = BytesIO()
    mem.write(codecs.BOM_UTF8)
    mem.write(buf.getvalue().encode('utf-8'))
    mem.seek(0)

    return send_file(mem, as_attachment=True,
                     download_name='sessionplan-' + session_plan.title.replace(' ', '_') + '.oal',
                     mimetype='text/xml')


@main_sessionplan.route('/session-plan/<int:session_plan_id>/schedule', methods=['GET', 'POST'])
def session_plan_schedule(session_plan_id):
    """View a session plan schedule."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    is_mine_session_plan = _check_session_plan(session_plan, allow_public=True)
    if not is_mine_session_plan:
        return redirect(url_for('main_sessionplan.session_plan_info', session_plan_id=session_plan.id))

    schedule_form = SessionPlanScheduleFilterForm()

    src_sort_by = request.args.get('src_sortby')

    str_per_page = request.args.get('per_page', None)
    if str_per_page is not None:
        session['items_per_page'] = int(str_per_page)

    ret, page, _ = process_paginated_session_search('planner_page', None, [
        ('planner_dso_type', schedule_form.dso_type),
        ('planner_dso_obj_source', schedule_form.obj_source),
        ('planner_dso_maglim', schedule_form.maglim),
        ('planner_constellation_id', schedule_form.constellation_id),
        ('planner_min_altitude', schedule_form.min_altitude),
        ('planner_time_from', schedule_form.time_from),
        ('planner_time_to', schedule_form.time_to),
        ('planner_not_observed', schedule_form.not_observed),
        ('planner_selected_dso_name', schedule_form.selected_dso_name),
        ('items_per_page', schedule_form.items_per_page)
        ]);

    if not ret:
        return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan_id, page=page, sortby=src_sort_by))

    add_form = AddToSessionPlanForm()
    add_form.session_plan_id.data = session_plan.id

    per_page = get_items_per_page(schedule_form.items_per_page)

    offset = (page - 1) * per_page

    mag_scale = (8, 16)

    sort_def = { 'name': DeepskyObject.name,
                 'type': DeepskyObject.type,
                 'constellation': DeepskyObject.constellation_id,
                 'mag': DeepskyObject.mag,
    }

    src_table_sort = create_table_sort(src_sort_by, sort_def.keys())

    observer, tz_info = _get_observer_tzinfo(session_plan)

    observation_time = Time(session_plan.for_date)

    # try astronomical twilight
    default_t1, default_t2 = _get_twighligh_component(session_plan, 1)
    if not default_t2 and not default_t2:
        # try nautical twilight
        default_t1, default_t2 = _get_twighligh_component(session_plan, 2)
        if not default_t2 and not default_t2:
            default_t1 = tz_info.localize(session_plan.for_date + timedelta(hours=22)).time()
            default_t2 = tz_info.localize(session_plan.for_date + timedelta(hours=26)).time()

    time_from = _setup_search_from(schedule_form, observer, observation_time, tz_info, default_t1)
    time_to = _setup_search_to(schedule_form, observer, observation_time, time_from, tz_info, default_t2)

    selection_compound_list, page, all_count = create_selection_coumpound_list(session_plan, schedule_form, observer, observation_time, time_from, time_to, tz_info,
            page, offset, per_page, src_sort_by, mag_scale, sort_def)

    src_pagination = Pagination(page=page, per_page=per_page, total=all_count, search=False, record_name='deepskyobjects',
                                css_framework='semantic', not_passed_args='back')

    session_plan_compound_list = create_session_plan_compound_list(session_plan, observer, observation_time, tz_info, sort_def)

    dst_page = request.args.get('dst_page', type=int, default=session.get('planner_dst_page', 1))

    last_dst_page = (len(session_plan_compound_list) - 1) // per_page + 1
    if dst_page >= last_dst_page:
        dst_page =  last_dst_page
    if dst_page < 1:
        dst_page = 1

    session['planner_dst_page'] = dst_page

    dst_offset = (dst_page - 1) * per_page

    session_plan_compound_list_for_render = session_plan_compound_list[dst_offset:dst_offset + per_page]

    dst_pagination = Pagination(dst_page=dst_page, page_parameter='dst_page', total=len(session_plan_compound_list), search=False,
                                per_page=per_page, record_name='deepskyobjects', css_framework='semantic', not_passed_args='back')

    selected_dso_name = None

    srow_index = request.args.get('srow_index', type=int, default=-1)
    drow_index = request.args.get('drow_index', type=int, default=-1)

    if drow_index == -1 and srow_index == -1:
        srow_index = 1

    if srow_index > len(selection_compound_list):
        srow_index = len(selection_compound_list)
    if srow_index > 0:
        selected_dso_name = selection_compound_list[srow_index-1][0].name

    if drow_index > len(session_plan_compound_list_for_render):
        drow_index = len(session_plan_compound_list_for_render)
    if drow_index > 0:
        sel_item = session_plan_compound_list_for_render[drow_index-1][0]
        if sel_item.dso_id is not None:
            selected_dso_name = sel_item.deepsky_object.name
        elif sel_item.double_star_id is not None:
            selected_dso_name = sel_item.double_star.common_cat_id

    if not schedule_form.selected_dso_name.data:
        schedule_form.selected_dso_name.data = 'M1'
    if not selected_dso_name:
        selected_dso_name = schedule_form.selected_dso_name.data

    packed_constell_list = get_packed_constell_list()

    Constellation.get_id_dict()

    return render_template('main/planner/session_plan_info.html', type='schedule', session_plan=session_plan,
                           selection_compound_list=selection_compound_list, session_plan_compound_list=session_plan_compound_list_for_render,
                           dso_lists=DsoList.query.all(), catalogues_menu_items=get_catalogues_menu_items(), mag_scale=mag_scale,
                           add_form=add_form, schedule_form=schedule_form, min_alt_item_list=min_alt_item_list,
                           src_pagination=src_pagination, src_table_sort=src_table_sort, dst_pagination=dst_pagination,
                           selected_dso_name=selected_dso_name, srow_index=srow_index, drow_index=drow_index,
                           is_mine_session_plan=is_mine_session_plan, packed_constell_list=packed_constell_list,
                           constellation_by_id_dict=Constellation.get_id_dict()
                           )


def _get_session_plan_tzinfo(session_plan):
    tz_info = pytz.timezone('Europe/Prague')
    return tz_info


def _get_observer_tzinfo(session_plan):
    loc_name, latitude, longitude, elevation = _get_location_info_from_session_plan(session_plan)
    loc_coords = EarthLocation.from_geodetic(longitude*u.deg, latitude*u.deg, elevation*u.m if elevation else 0)
    tz_info = _get_session_plan_tzinfo(session_plan)
    observer = Observer(name=loc_name, location=loc_coords, timezone=tz_info)
    return observer, tz_info


def _get_location_info_from_session_plan(session_plan):
    if session_plan.location:
        loc = session_plan.location
        loc_name = loc.name
        longitude = loc.longitude
        latitude = loc.latitude
        elevation = loc.elevation
    else:
        loc_name = session_plan.location_position
        latitude, longitude = parse_latlon(session_plan.location_position)
        elevation = 0

    return loc_name, latitude, longitude, elevation


def _setup_search_from(schedule_form, observer, observation_time, tz_info, default_time):
    if schedule_form.time_from.data:
        try:
            field_time = _combine_date_and_time(observation_time, schedule_form.time_from.data, tz_info)
        except ValueError:
            field_time = default_time
    else:
        field_time = default_time
    schedule_form.time_from.data = field_time.time()
    return field_time


def _setup_search_to(schedule_form, observer, observation_time, time_from, tz_info, default_time):
    if schedule_form.time_to.data:
        try:
            field_time = _combine_date_and_time(observation_time, schedule_form.time_to.data, tz_info)
        except ValueError:
            field_time = default_time
    else:
        field_time = default_time
    if field_time < time_from:
        field_time += timedelta(days=1)
    schedule_form.time_to.data = field_time.time()
    return field_time


def _combine_date_and_time(date_part, time_part, tz_info):
    return datetime.combine(date_part.to_datetime().date(), datetime.strptime(time_part, '%H:%M').time(), tz_info)


@main_sessionplan.route('/session-plan/<int:session_plan_id>/chart', methods=['GET', 'POST'])
@csrf.exempt
def session_plan_chart(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    is_mine_session_plan = _check_session_plan(session_plan, allow_public=True)

    form = ChartForm()

    session_plan_item = find_by_url_obj_id_in_list(request.args.get('obj_id'), session_plan.session_plan_items)

    if not session_plan_item:
        session_plan_item = SessionPlanItem.query.filter_by(session_plan_id=session_plan.id).first()

    common_ra_dec_dt_fsz_from_request(form,
                                   session_plan_item.get_ra() if session_plan_item else 0,
                                   session_plan_item.get_dec() if session_plan_item else 0)

    chart_control = common_prepare_chart_data(form)
    default_chart_iframe_url = get_default_chart_iframe_url(session_plan_item, back='session_plan', back_id=session_plan.id)

    return render_template('main/planner/session_plan_info.html', fchart_form=form, type='chart',
                           session_plan=session_plan, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url, is_mine_session_plan=is_mine_session_plan,
                           back='session_plan', back_id=session_plan.id,
                           )


@main_sessionplan.route('/session-plan/<int:session_plan_id>/chart-pos-img', methods=['GET'])
def session_plan_chart_pos_img(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan, allow_public=True)

    highlights_dso_list, highlights_pos_list = common_highlights_from_session_plan(session_plan)
    observed_dso_ids = find_session_plan_observed(session_plan)

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes, img_format = common_chart_pos_img(None, None, visible_objects=visible_objects,
                                                 highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list,
                                                 observed_dso_ids=observed_dso_ids)
    img = base64.b64encode(img_bytes.read()).decode()
    return jsonify(img=img, img_format=img_format, img_map=visible_objects)


@main_sessionplan.route('/session-plan/<int:session_plan_id>/chart-legend-img', methods=['GET'])
def session_plan_chart_legend_img(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan, allow_public=True)

    img_bytes = common_chart_legend_img(None, None)
    return send_file(img_bytes, mimetype='image/png')


@main_sessionplan.route('/session-plan/<int:session_plan_id>/chart-pdf', methods=['GET'])
def session_plan_chart_pdf(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan, allow_public=True)

    highlights_dso_list, highlights_pos_list = common_highlights_from_session_plan(session_plan)
    observed_dso_ids = find_session_plan_observed(session_plan)

    img_bytes = common_chart_pdf_img(None, None, highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list,
                                     observed_dso_ids=observed_dso_ids)

    return send_file(img_bytes, mimetype='application/pdf')


@main_sessionplan.route('/session-plan/<int:session_plan_id>/chart-items', methods=['GET'])
def session_plan_chart_items(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan, allow_public=True)

    highlights_dso_list, highlights_pos_list = common_highlights_from_session_plan(session_plan)

    visible_objects = []
    _ = common_chart_pdf_img(None, None, visible_objects=visible_objects,
                             highlights_dso_list=highlights_dso_list, highlights_pos_list=highlights_pos_list)

    norm_dso_names = get_norm_visible_objects_set(visible_objects)

    chart_items = []
    for session_plan_item in session_plan.session_plan_items:
        if session_plan_item.item_type == SessionPlanItemType.DSO and session_plan_item.deepsky_object.name in norm_dso_names:
            chart_items.append((session_plan_item.deepsky_object.name, session_plan_item.deepsky_object.mag))

    file = chart_items_to_file(chart_items)

    return send_file(file, as_attachment=True,
                     download_name='sessionplan-items-' + session_plan.title.replace(' ', '_') + '.csv',
                     mimetype='text/csv')


def _get_twighligh_component(session_plan, comp):
    ts = load.timescale()
    _, latitude, longitude, _ = _get_location_info_from_session_plan(session_plan)
    observer = wgs84.latlon(latitude, longitude)
    tz_info = _get_session_plan_tzinfo(session_plan)
    ldate1 = tz_info.localize(session_plan.for_date + timedelta(hours=12))
    ldate2 = tz_info.localize(session_plan.for_date + timedelta(hours=36))
    t1 = ts.from_datetime(ldate1)
    t2 = ts.from_datetime(ldate2)
    eph = load('de421.bsp')
    t, y = almanac.find_discrete(t1, t2, almanac.dark_twilight_day(eph, observer))

    index1 = None
    index2 = None
    for i in range(len(y)):
        if y[i] == comp:
            if index1 is None:
                index1 = i + 1
            elif index2 is None:
                index2 = i
    if index1 is None or index2 is None:
        return None, None
    return t[index1].astimezone(tz_info), t[index2].astimezone(tz_info)


@main_sessionplan.route('/session-plan/<int:session_plan_id>/set-nautical-twilight', methods=['GET'])
def session_plan_set_nautical_twilight(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    t1, t2 = _get_twighligh_component(session_plan, 2)

    if t1 and t2:
        session['planner_time_from'] = t1.strftime(SCHEDULE_TIME_FORMAT)
        session['planner_time_to'] = t2.strftime(SCHEDULE_TIME_FORMAT)

    session['is_backr'] = True
    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan.id))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/set-astro-twilight', methods=['GET'])
def session_plan_set_astro_twilight(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    t1, t2 = _get_twighligh_component(session_plan, 1)

    if t1 and t2:
        session['planner_time_from'] = t1.strftime(SCHEDULE_TIME_FORMAT)
        session['planner_time_to'] = t2.strftime(SCHEDULE_TIME_FORMAT)

    session['is_backr'] = True
    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan.id))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/set-moonless-astro-twilight', methods=['GET'])
def session_plan_set_moonless_astro_twilight(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    t1, t2 = _get_twighligh_component(session_plan, 1)

    if t1 and t2:
        ts = load.timescale()
        _,  latitude, longitude, _ = _get_location_info_from_session_plan(session_plan)
        observer = wgs84.latlon(latitude, longitude)
        tz_info = _get_session_plan_tzinfo(session_plan)
        ldate_start = tz_info.localize(session_plan.for_date + timedelta(hours=0))
        ldate_end = tz_info.localize(session_plan.for_date + timedelta(hours=48))
        start_t = ts.from_datetime(ldate_start)
        end_t = ts.from_datetime(ldate_end)
        eph = load('de421.bsp')
        f = almanac.risings_and_settings(eph, eph['Moon'], observer)
        t, y = almanac.find_discrete(start_t, end_t, f)

        if t1 and t2:
            rise_sets = []
            moon_rise, moon_set = None, None
            for i in range(len(y)):
                if y[i]:
                    moon_rise = t[i].astimezone(tz_info)
                else:
                    moon_set = t[i].astimezone(tz_info)
                    rise_sets.append((moon_rise, moon_set))
                    moon_rise, moon_set = None, None
            if moon_rise or moon_set:
                rise_sets.append((moon_rise, moon_set))

            for moon_rise, moon_set in rise_sets:
                if not moon_rise:
                    moon_rise = ldate_start
                if not moon_set:
                    moon_set = ldate_end
                if moon_set < t1 or moon_rise > t2:
                    continue
                if moon_rise < t1 and moon_set > t2:
                    t1, t2 = None, None
                    break
                if moon_rise > t1:
                    t2 = moon_rise
                else:
                    t1 = moon_set
            if t1 and t2 and t1 > t2:
                t1, t2 = None, None

    if t1 and t2:
        session['planner_time_from'] = t1.strftime(SCHEDULE_TIME_FORMAT)
        session['planner_time_to'] = t2.strftime(SCHEDULE_TIME_FORMAT)

    session['is_backr'] = True
    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan.id))
