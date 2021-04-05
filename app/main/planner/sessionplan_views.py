import os
import csv
from datetime import datetime, timedelta
import base64
import pytz

from werkzeug.utils import secure_filename

from astropy.time import Time, TimeDelta
from astropy.coordinates import EarthLocation, SkyCoord
import astropy.units as u
from astroplan import Observer, FixedTarget
from astroplan import (AltitudeConstraint, AirmassConstraint, AtNightConstraint)
from astroplan import is_observable, is_always_observable, months_observable

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

from app import db

from app.models import (
    DeepskyObject,
    DsoList,
    Location,
    SessionPlan,
    SessionPlanItem,
)

from app.commons.pagination import Pagination, get_page_parameter
from app.commons.search_utils import process_session_search, process_paginated_session_search, get_items_per_page, create_table_sort, get_catalogues_menu_items
from app.commons.chart_generator import (
    common_chart_pos_img,
    common_chart_legend_img,
    common_prepare_chart_data,
    common_chart_pdf_img,
)
from app.commons.utils import to_int


from .sessionplan_forms import (
    SCHEDULE_TIME_FORMAT,
    AddToSessionPlanForm,
    SearchSessionPlanForm,
    SessionPlanNewForm,
    SessionPlanEditForm,
    SessionPlanScheduleFilterForm,
)

from app.main.chart.chart_forms import ChartForm

from app.commons.dso_utils import normalize_dso_name
from app.commons.utils import get_anonymous_user

from .session_scheduler import create_selection_coumpound_list, create_session_plan_compound_list, reorder_by_merid_time

main_sessionplan = Blueprint('main_sessionplan', __name__)

min_alt_item_list = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45]

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


def _check_session_plan(session_plan):
    if session_plan is None:
        abort(404)

    if current_user.is_anonymous:
        if not session_plan.is_anonymous or session.get('session_plan_id') != session_plan.id:
            abort(404)
    elif session_plan.user_id != current_user.id:
        abort(404)


@main_sessionplan.route('/session-plan/<int:session_plan_id>/info', methods=['GET', 'POST'])
def session_plan_info(session_plan_id):
    """View a session plan info."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()

    _check_session_plan(session_plan)

    form = SessionPlanEditForm()
    if request.method == 'POST':
        if form.validate_on_submit():

            user = get_anonymous_user() if current_user.is_anonymous else current_user

            session_plan.title = form.title.data
            session_plan.for_date = form.for_date.data
            session_plan.location_id = form.location_id.data
            session_plan.notes = form.notes.data
            session_plan.update_by = user.id
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

    return render_template('main/planner/session_plan.html', type='info', session_plan=session_plan, form=form, location=location)


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
            new_session_plan = SessionPlan(
                user_id = user.id,
                title = form.title.data,
                for_date = form.for_date.data,
                location_id = form.location_id.data,
                notes = form.notes.data,
                is_anonymous = current_user.is_anonymous,
                create_by = user.id,
                update_by = user.id,
                create_date = datetime.now(),
                update_date = datetime.now(),
                )

            db.session.add(new_session_plan)
            db.session.commit()

            if current_user.is_anonymous:
                session['session_plan_id'] = new_session_plan.id

            flash('Session plan successfully created', 'form-success')
        else:
            flash('Session plan already exists', 'form-success')

        return redirect(url_for('main_sessionplan.session_plan_info', session_plan_id=new_session_plan.id))

    location = None
    if form.location_id.data:
        location = Location.query.filter_by(id=form.location_id.data).first()

    return render_template('main/planner/session_plan.html', type='info', form=form, is_new=True, location=location, is_anonymous=current_user.is_anonymous)


@main_sessionplan.route('/session-plan/<int:session_plan_id>/delete')
def session_plan_delete(session_plan_id):
    """Request deletion of a observation."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    db.session.delete(session_plan)
    db.session.commit()

    flash('Session plan was deleted', 'form-success')
    return redirect(url_for('main_sessionplan.session_plans'))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/clear')
def session_plan_clear(session_plan_id):
    """Request deletion of a observation."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    SessionPlanItem.query.filter_by(session_plan_id=session_plan_id).delete()
    db.session.commit()
    flash('Session items deleted', 'form-success')
    session['is_backr'] = True
    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan.id))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/item-add', methods=['GET', 'POST'])
def session_plan_item_add(session_plan_id):
    """Add item to session plan."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

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
        if not session_plan.find_dso_by_id(deepsky_object.id):
            user = get_anonymous_user() if current_user.is_anonymous else current_user
            new_item = session_plan.create_new_session_plan_item(deepsky_object.id, user.id)
            db.session.add(new_item)
            db.session.commit()
            flash('Object was added to session plan.', 'form-success')
        else:
            flash('Object is already on session plan.', 'form-info')

        reorder_by_merid_time(session_plan)
    else:
        flash('Deepsky object not found.', 'form-error')

    session['is_backr'] = True

    srow_index=request.args.get('row_index')

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
    flash('Session plan item was deleted', 'form-success')

    session['is_backr'] = True
    drow_index=request.args.get('row_index')
    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan_id, drow_index=drow_index))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/upload', methods=['POST'])
def session_plan_upload(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

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
            existing_ids = set(item.dso_id for item in session_plan.session_plan_items)

            for row in reader:
                dso_name = row['DSO_NAME']
                if dso_name == 'none':
                    continue

                dso_name = normalize_dso_name(dso_name)
                dso = DeepskyObject.query.filter(DeepskyObject.name==dso_name).first()

                if dso and not dso.id in existing_ids:

                    if not session_plan.find_dso_by_id(dso.id):
                        user = get_anonymous_user() if current_user.is_anonymous else current_user
                        new_item = session_plan.create_new_session_plan_item(dso.id, user.id)
                        db.session.add(new_item)
                    existing_ids.add(dso.id)
        db.session.commit()
        os.remove(path)
        flash('Session plan uploaded.', 'form-success')

    session['is_backr'] = True
    return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan.id))


@main_sessionplan.route('/session-plan/<int:session_plan_id>/schedule', methods=['GET', 'POST'])
def session_plan_schedule(session_plan_id):
    """View a session plan schedule."""
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    schedule_form = SessionPlanScheduleFilterForm()

    sort_by = request.args.get('sortby')

    str_per_page = request.args.get('per_page', None)
    if str_per_page is not None:
        session['items_per_page'] = int(str_per_page)

    ret, page = process_paginated_session_search('planner_page', [
        ('planner_dso_type', schedule_form.dso_type),
        ('planner_dso_obj_source', schedule_form.obj_source),
        ('planner_dso_maglim', schedule_form.maglim),
        ('planner_min_altitude', schedule_form.min_altitude),
        ('planner_time_from', schedule_form.time_from),
        ('planner_time_to', schedule_form.time_to),
        ('planner_not_observed', schedule_form.not_observed),
        ('planner_selected_dso_name', schedule_form.selected_dso_name),
        ('items_per_page', schedule_form.items_per_page)
        ]);

    if not ret:
        return redirect(url_for('main_sessionplan.session_plan_schedule', session_plan_id=session_plan_id, page=page, sortby=sort_by))

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

    table_sort = create_table_sort(sort_by, sort_def.keys())

    observer, tz_info = _get_observer_tzinfo(session_plan)

    observation_time = Time(session_plan.for_date)

    # try astronomical twilight
    default_t1, default_t2 = _get_twighligh_component(session_plan, 1)
    if not default_t2 and not default_t2:
        # try nautical twilight
        default_t1, default_t2 = _get_twighligh_component(session_plan, 1)

    time_from = _setup_search_from(schedule_form, observer, observation_time, tz_info, default_t1)
    time_to = _setup_search_to(schedule_form, observer, observation_time, time_from, tz_info, default_t2)

    selection_compound_list, page, all_count = create_selection_coumpound_list(session_plan, schedule_form, observer, observation_time, time_from, time_to, tz_info,
                                                              page, offset, per_page, sort_by, mag_scale)
    session_plan_compound_list = create_session_plan_compound_list(session_plan, observer, observation_time, tz_info)

    pagination = Pagination(page=page, total=all_count, search=False, record_name='deepskyobjects', css_framework='semantic', not_passed_args='back')

    selected_dso_name = None

    srow_index = request.args.get('srow_index', type=int, default=-1)
    drow_index = request.args.get('drow_index', type=int, default=-1)

    if drow_index == -1 and srow_index == -1:
        srow_index = 1

    if drow_index > len(session_plan_compound_list):
        drow_index = len(session_plan_compound_list)
    if drow_index > 0:
        selected_dso_name = session_plan_compound_list[drow_index-1][0].deepskyObject.name

    if srow_index > len(selection_compound_list):
        srow_index = len(selection_compound_list)
    if srow_index > 0:
        selected_dso_name = selection_compound_list[srow_index-1][0].name

    if not schedule_form.selected_dso_name.data:
        schedule_form.selected_dso_name.data = 'M1'
    if not selected_dso_name:
        selected_dso_name = schedule_form.selected_dso_name.data

    return render_template('main/planner/session_plan.html', type='schedule', session_plan=session_plan,
                           selection_compound_list=selection_compound_list, session_plan_compound_list=session_plan_compound_list,
                           dso_lists=DsoList.query.all(), catalogues_menu_items=get_catalogues_menu_items(), mag_scale=mag_scale,
                           add_form=add_form, schedule_form=schedule_form, pagination=pagination,table_sort=table_sort, min_alt_item_list=min_alt_item_list,
                           selected_dso_name=selected_dso_name, srow_index=srow_index, drow_index=drow_index)


def _get_session_plan_tzinfo(session_plan):
    tz_info = pytz.timezone('Europe/Prague')
    return tz_info


def _get_observer_tzinfo(session_plan):
    loc = session_plan.location
    loc_coords = EarthLocation.from_geodetic(loc.longitude*u.deg, loc.latitude*u.deg, loc.elevation*u.m if loc.elevation else 0)
    tz_info = _get_session_plan_tzinfo(session_plan)
    observer = Observer(name=loc.name, location=loc_coords, timezone=tz_info)
    return observer, tz_info


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
def session_plan_chart(session_plan_id):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    form  = ChartForm()

    chart_control = common_prepare_chart_data(form)

    dso_id = request.args.get('dso_id')
    session_plan_item = None
    if dso_id and dso_id.isdigit():
        idso_id = int(dso_id)
        session_plan_item = next((x for x in session_plan.session_plan_items if x.deepskyObject.id == idso_id), None)

    if not session_plan_item:
        session_plan_item = SessionPlanItem.query.filter_by(session_plan_id=session_plan.id).first()

    if form.ra.data is None:
        form.ra.data = session_plan_item.deepskyObject.ra if session_plan_item else 0
    if form.dec.data is None:
        form.dec.data = session_plan_item.deepskyObject.dec if session_plan_item else 0

    if session_plan_item:
        default_chart_iframe_url = url_for('main_deepskyobject.deepskyobject_info', back='session_plan', back_id=session_plan.id, dso_id=session_plan_item.dso_id, embed='fc', allow_back='true')
    else:
        default_chart_iframe_url = None

    return render_template('main/planner/session_plan.html', fchart_form=form, type='chart', session_plan=session_plan, chart_control=chart_control,
                           default_chart_iframe_url=default_chart_iframe_url)


@main_sessionplan.route('/session-plan/<int:session_plan_id>/chart-pos-img/<string:ra>/<string:dec>', methods=['GET'])
def  session_plan_chart_pos_img(session_plan_id, ra, dec):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    highlights_dso_list = [ x.deepskyObject for x in session_plan.session_plan_items if session_plan ]

    flags = request.args.get('json')
    visible_objects = [] if flags else None
    img_bytes = common_chart_pos_img(None, None, ra, dec, visible_objects=visible_objects, highlights_dso_list=highlights_dso_list)
    if visible_objects is not None:
        img = base64.b64encode(img_bytes.read()).decode()
        return jsonify(img=img, img_map=visible_objects)
    else:
        return send_file(img_bytes, mimetype='image/png')


@main_sessionplan.route('/session-plan/<int:session_plan_id>/chart-legend-img/<string:ra>/<string:dec>', methods=['GET'])
def session_plan_chart_legend_img(session_plan_id, ra, dec):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    img_bytes = common_chart_legend_img(None, None, ra, dec, )
    return send_file(img_bytes, mimetype='image/png')


@main_sessionplan.route('/session-plan/<int:session_plan_id>/chart-pdf/<string:ra>/<string:dec>', methods=['GET'])
def session_plan_chart_pdf(session_plan_id, ra, dec):
    session_plan = SessionPlan.query.filter_by(id=session_plan_id).first()
    _check_session_plan(session_plan)

    highlights_dso_list = [ x.deepskyObject for x in session_plan.session_plan_items if session_plan ]

    img_bytes = common_chart_pdf_img(None, None, ra, dec, highlights_dso_list=highlights_dso_list)

    return send_file(img_bytes, mimetype='application/pdf')

def _get_twighligh_component(session_plan, comp):
    ts = load.timescale()
    observer = wgs84.latlon(session_plan.location.latitude, session_plan.location.longitude)
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
        observer = wgs84.latlon(session_plan.location.latitude, session_plan.location.longitude)
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
