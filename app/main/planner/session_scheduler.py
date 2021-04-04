from app import db
import pytz

from astropy.time import Time, TimeDelta
import astropy.units as u
from astropy.coordinates import EarthLocation, SkyCoord
from astroplan import Observer, FixedTarget
from astroplan import (AltitudeConstraint, AirmassConstraint, AtNightConstraint)
from astroplan import is_observable, is_always_observable, months_observable

from flask_login import current_user, login_required

from app.models import (
    Catalogue,
    DeepskyObject,
    DsoList,
    DsoListItem,
    ObservedList,
    ObservedListItem,
    SessionPlanItem,
    WishList,
    WishListItem,
)

def create_session_plan_compound_list(session_plan, observer, observation_time, tz_info):
    # create session plan list
    spi = session_plan.session_plan_items.copy()
    spi.sort(key=lambda x: x.order)
    session_plan_rms_list = rise_merid_set_time_str(observation_time, observer, [ (x.deepskyObject.ra, x.deepskyObject.dec) for x in spi], tz_info)
    session_plan_compound_list = [ (spi[i], *session_plan_rms_list[i]) for i in range(len(spi))]

    return session_plan_compound_list


def create_selection_coumpound_list(session_plan, schedule_form, observer, observation_time, time_from, time_to, tz_info,
                                    page, offset, per_page, sort_by, mag_scale):

    if session_plan.is_anonymous and (schedule_form.obj_source.data is None or schedule_form.obj_source.data == 'WL'):
        schedule_form.obj_source.data = 'M' # set Messier

    if schedule_form.obj_source.data is None or schedule_form.obj_source.data == 'WL':
        wishlist_subquery = db.session.query(WishListItem.dso_id) \
            .join(WishListItem.wish_list) \
            .filter(WishList.user_id==current_user.id)

        dso_query = DeepskyObject.query \
            .filter(DeepskyObject.id.in_(wishlist_subquery))

    elif schedule_form.obj_source.data.startswith('DL_'):
        dso_list_id = int(schedule_form.obj_source.data[3:])

        dsolist_subquery = db.session.query(DsoListItem.dso_id) \
            .join(DsoListItem.dso_list) \
            .filter(DsoList.id==dso_list_id)

        dso_query = DeepskyObject.query \
            .filter(DeepskyObject.id.in_(dsolist_subquery))
    else:
        dso_query = DeepskyObject.query
        cat_id = Catalogue.get_catalogue_id_by_cat_code(schedule_form.obj_source.data)
        if cat_id:
            dso_query = dso_query.filter_by(catalogue_id=cat_id)

    scheduled_subquery = db.session.query(SessionPlanItem.dso_id) \
        .filter(SessionPlanItem.session_plan_id==session_plan.id)

    # Subtract already scheduled dsos
    dso_query = dso_query.filter(DeepskyObject.id.notin_(scheduled_subquery))

    # Subtract observed dsos
    if not session_plan.is_anonymous and schedule_form.not_observed.data:
        observed_subquery = db.session.query(ObservedListItem.dso_id) \
            .join(ObservedListItem.observed_list) \
            .filter(ObservedList.user_id==current_user.id)
        dso_query = dso_query.filter(DeepskyObject.id.notin_(observed_subquery))


    # filter by type
    if schedule_form.dso_type.data and schedule_form.dso_type.data != 'All':
        dso_query = dso_query.filter(DeepskyObject.type==schedule_form.dso_type.data)

    # filter by magnitude limit
    if schedule_form.maglim.data is not None and schedule_form.maglim.data < mag_scale[1]:
        dso_query = dso_query.filter(DeepskyObject.mag<schedule_form.maglim.data)

    order_by_field = None
    if sort_by:
        desc = sort_by[0] == '-'
        sort_by_name = sort_by[1:] if desc else sort_by
        order_by_field = sort_def.get(sort_by_name)
        if order_by_field and desc:
            order_by_field = order_by_field.desc()

    if order_by_field is None:
        order_by_field = DeepskyObject.id

    all_count = dso_query.count()

    if all_count > 500:
        selection_list = dso_query.order_by(order_by_field).limit(per_page).offset(offset).all().copy()
        use_time_filter = False
    else:
        selection_list = dso_query.order_by(order_by_field).all().copy()
        use_time_filter = True

    # filter by rise-set time
    if use_time_filter:
        time_filtered_list = []
        selection_rms_list = rise_merid_set_up(time_from, time_to, observer, [ (x.ra, x.dec) for x in selection_list])
        for i in range(len(selection_rms_list)):
            rise_t, merid_t, set_t, is_up = selection_rms_list[i]
            if is_up or rise_t < time_to or set_t>time_from:
                time_filtered_list.append((selection_list[i], _to_HM_format(rise_t, tz_info), _to_HM_format(merid_t, tz_info), _to_HM_format(set_t, tz_info)))

        # filter by altitude
        if len(time_filtered_list) > 0 and schedule_form.min_altitude.data > 0:
            constraints = [AltitudeConstraint(schedule_form.min_altitude.data*u.deg)]
            targets = []
            for item in time_filtered_list:
                dso = item[0]
                target = FixedTarget(coord=SkyCoord(ra=dso.ra * u.rad, dec=dso.dec * u.rad), name=dso.name)
                targets.append(target)
            time_range = Time([time_from, time_to])
            observable_list = is_observable(constraints, observer, targets, time_range=time_range)
            time_filtered_list = [ time_filtered_list[i] for i in range(len(time_filtered_list)) if observable_list[i] ]

        all_count = len(time_filtered_list)
        if offset>=all_count:
            offset = 0
            page = 1
        selection_compound_list = time_filtered_list[offset:offset+per_page]
    else:
        selection_rms_list = rise_merid_set_time_str(observation_time, observer, [ (x.ra, x.dec) for x in selection_list], tz_info)
        selection_compound_list = [ (selection_list[i], *selection_rms_list[i]) for i in range(len(selection_list))]

    return selection_compound_list, page, all_count


def rise_merid_set_up(time_from, time_to, observer, ra_dec_list):
    coords = [ SkyCoord(x[0] * u.rad, x[1] * u.rad) for x in ra_dec_list]
    rise_list = _wrap2array(observer.target_rise_time(time_from, coords, which='next', n_grid_points=10)) if len(coords) > 0 else []
    merid_list = _wrap2array(observer.target_meridian_transit_time(time_from, coords, which='next', n_grid_points=10))  if len(coords) > 0 else []
    set_list = _wrap2array(observer.target_set_time(time_to, coords, which='previous', n_grid_points=10)) if len(coords) > 0 else []
    up_list = _wrap2array(observer.target_is_up(time_from, coords)) if len(coords) > 0 else []

    return [(rise_list[i], merid_list[i], set_list[i], up_list[i]) for i in range(len(rise_list))]


def rise_merid_set_time_str(t, observer, ra_dec_list, tz_info):
    coords = [ SkyCoord(x[0] * u.rad, x[1] * u.rad) for x in ra_dec_list]
    rise_list = _ar_to_HM_format(observer.target_rise_time(t, coords, n_grid_points=10), tz_info) if len(coords) > 0 else []
    merid_list = _ar_to_HM_format(observer.target_meridian_transit_time(t, coords, n_grid_points=10), tz_info)  if len(coords) > 0 else []
    set_list = _ar_to_HM_format(observer.target_set_time(t, coords, n_grid_points=10), tz_info) if len(coords) > 0 else []

    return [(rise_list[i], merid_list[i], set_list[i]) for i in range(len(rise_list))]


def merid_time(t, observer, ra_dec_list):
    coords = [ SkyCoord(x[0] * u.rad, x[1] * u.rad) for x in ra_dec_list]
    merid_list = observer.target_meridian_transit_time(t, coords, n_grid_points=10) if len(coords) > 0 else []
    return _wrap2array(merid_list)


def reorder_by_merid_time(session_plan):
    loc = session_plan.location
    loc_coords = EarthLocation.from_geodetic(loc.longitude*u.deg, loc.latitude*u.deg, loc.elevation*u.m if loc.elevation else 0)
    observation_time = Time(session_plan.for_date)
    tz_info = pytz.timezone('Europe/Prague')

    observer = Observer(name=loc.name, location=loc_coords, timezone=tz_info)

    spi = session_plan.session_plan_items
    merid_time_list = merid_time(observation_time, observer, [ (x.deepskyObject.ra, x.deepskyObject.dec) for x in spi])
    session_plan_compound_list = [ (spi[i], merid_time_list[i]) for i in range(len(spi))]
    session_plan_compound_list.sort(key=lambda x: x[1])
    i = 1
    for item in session_plan_compound_list:
        session_plan_item = item[0]
        session_plan_item.order = i
        i += 1
        db.session.add(session_plan_item)
    db.session.commit()


def _to_HM_format(t, tz_info):
    try:
        return t.to_datetime(tz_info).strftime('%H:%M')
    except ValueError:
        return ''


def _ar_to_HM_format(tm, tz_info):
    ret = []
    tm = _wrap2array(tm)

    for t in tm:
        try:
            ret.append(t.to_datetime(tz_info).strftime('%H:%M'))
        except ValueError:
            ret.append('')
    return ret


def _wrap2array(ar):
    try:
        it = iter(ar)
        return ar
    except TypeError:
        return [ar]

