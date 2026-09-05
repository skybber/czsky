from app import db
from datetime import datetime
import pytz

from astropy.time import Time, TimeDelta
import astropy.units as u
from astropy.coordinates import EarthLocation, SkyCoord
from astroplan import Observer, FixedTarget
from astroplan import (AltitudeConstraint, AirmassConstraint, AtNightConstraint)
from astroplan import is_observable, is_always_observable, months_observable
from lru import LRU

from sqlalchemy import func, or_
from flask_login import current_user, login_required

from app.commons.search_utils import get_order_by_field
from app.models import (
    Catalogue,
    Comet,
    Constellation,
    DeepskyObject,
    DsoList,
    DsoListItem,
    ObservedListItem,
    ObservedList,
    SessionPlanItem,
    MinorPlanet,
    Planet,
    WishList,
    WishListItem,
)
from app.commons.comet_utils import get_comet_radec
from app.commons.minor_planet_utils import find_mpc_minor_planet, get_mpc_minor_planet_position
from app.commons.solar_system_chart_utils import get_mpc_planet_position


SOURCE_COMETS = 'COMETS'
SOURCE_MINOR_PLANETS = 'MINOR_PLANETS'
SOURCE_PLANETS = 'PLANETS'


class SelectionCandidate:
    """Object rendered in the planner source table."""

    def __init__(self, name, constellation, mag, ra, dec, object_type, object_id,
                 display_type=None, detail_id=None):
        self.name = name
        self.constellation = constellation or ''
        self.mag = mag
        self.ra = ra
        self.dec = dec
        self.object_type = object_type
        self.object_id = object_id
        self.detail_id = detail_id if detail_id is not None else object_id
        self.display_type = display_type

    def denormalized_name(self):
        return self.name

    def get_constellation_iau_code(self):
        return self.constellation

rise_set_cache = l = LRU(10000)


def create_session_plan_compound_list(session_plan, observer, observation_time, tz_info, sort_def):
    # create session plan list
    spi = session_plan.session_plan_items.copy()
    spi.sort(key=lambda x: x.order)

    session_plan_rms_list = rise_merid_set_time_str(observation_time, observer, [(x.get_ra(), x.get_dec()) for x in spi], tz_info)
    session_plan_compound_list = [(spi[i], *session_plan_rms_list[i]) for i in range(len(spi))]

    return session_plan_compound_list


def get_session_plan_position_datetime(session_plan, tz_info):
    """Return local midnight of the plan date as a naive UTC datetime."""
    if isinstance(session_plan.for_date, datetime):
        plan_midnight = session_plan.for_date.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        plan_midnight = datetime.combine(session_plan.for_date, datetime.min.time())
    if plan_midnight.tzinfo is None:
        plan_midnight = tz_info.localize(plan_midnight)
    else:
        plan_midnight = plan_midnight.astimezone(tz_info)
    return plan_midnight.astimezone(pytz.UTC).replace(tzinfo=None)


def _get_selected_object_ids(session_plan, id_attribute):
    return {
        object_id for item in session_plan.session_plan_items
        if (object_id := getattr(item, id_attribute)) is not None
    }


def create_selection_coumpound_list(session_plan, schedule_form, observer, observation_time, time_from, time_to, tz_info,
                                    page, offset, per_page, sort_by, mag_scale, sort_def):

    global rise_set_cache

    if schedule_form.obj_source.data in (SOURCE_COMETS, SOURCE_MINOR_PLANETS, SOURCE_PLANETS):
        return _create_solar_system_selection_compound_list(
            session_plan, schedule_form, observer, observation_time, time_from, time_to,
            tz_info, page, offset, per_page, sort_by,
        )

    if session_plan.is_anonymous and (schedule_form.obj_source.data is None or schedule_form.obj_source.data == 'WL'):
        schedule_form.obj_source.data = 'M'  # set Messier

    if schedule_form.obj_source.data is None or schedule_form.obj_source.data == 'WL':
        wishlist_subquery = db.session.query(WishListItem.dso_id) \
            .join(WishListItem.wish_list) \
            .filter(WishList.user_id == current_user.id) \
            .filter(WishListItem.dso_id.is_not(None))

        dso_query = DeepskyObject.query \
            .filter(DeepskyObject.id.in_(wishlist_subquery))

    elif schedule_form.obj_source.data.startswith('DL_'):
        dso_list_id = int(schedule_form.obj_source.data[3:])

        dsolist_subquery = db.session.query(DsoListItem.dso_id) \
            .join(DsoListItem.dso_list) \
            .filter(DsoList.id == dso_list_id)

        dso_query = DeepskyObject.query \
            .filter(DeepskyObject.id.in_(dsolist_subquery))
    else:
        dso_query = DeepskyObject.query
        cat_id = Catalogue.get_catalogue_id_by_cat_code(schedule_form.obj_source.data)
        if cat_id:
            dso_query = dso_query.filter_by(catalogue_id=cat_id)

    scheduled_subquery = db.session.query(SessionPlanItem.dso_id) \
        .filter(SessionPlanItem.session_plan_id == session_plan.id) \
        .filter(SessionPlanItem.dso_id.is_not(None))

    # Subtract already scheduled dsos
    dso_query = dso_query.filter(DeepskyObject.id.notin_(scheduled_subquery))

    # Subtract observed dsos
    if not session_plan.is_anonymous and schedule_form.not_observed.data:
        observed_subquery = db.session.query(ObservedListItem.dso_id) \
            .join(ObservedListItem.observed_list) \
            .filter(ObservedList.user_id == current_user.id) \
            .filter(ObservedListItem.dso_id.is_not(None))

        dso_query = dso_query.filter(DeepskyObject.id.notin_(observed_subquery))
        dso_query = dso_query.filter(or_(DeepskyObject.master_id.is_(None), DeepskyObject.master_id.notin_(observed_subquery)))

    # filter by type
    if schedule_form.dso_type.data and schedule_form.dso_type.data != 'All':
        dso_query = dso_query.filter(DeepskyObject.type == schedule_form.dso_type.data)

    # filter by magnitude limit
    if schedule_form.maglim.data is not None and schedule_form.maglim.data < mag_scale[1]:
        dso_query = dso_query.filter(DeepskyObject.mag<schedule_form.maglim.data)

    # filter by constellation
    if schedule_form.constellation_id.data is not None:
        dso_query = dso_query.filter(DeepskyObject.constellation_id == schedule_form.constellation_id.data)

    order_by_field = get_order_by_field(sort_def, sort_by)

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
        key_suffix = '/' + str(observer.location.lat) + '/' + str(observer.location.lon) + '/' + observation_time.strftime('%Y-%m-%d')
        index_table = []
        i = 0
        composed_selection_rms_list = []
        to_process_list = []
        for x in selection_list:
            key = str(x.id) + key_suffix
            cached = rise_set_cache.get(key, None)
            if cached is None:
                index_table.append(i)
                composed_selection_rms_list.append(None)
                to_process_list.append((x.ra, x.dec))
            else:
                composed_selection_rms_list.append(cached)
            i += 1

        if to_process_list:
            selection_rms_list = rise_merid_set_up(time_from, time_to, observer, to_process_list)
            for i in range(len(selection_rms_list)):
                index = index_table[i]
                val = selection_rms_list[i]
                composed_selection_rms_list[index] = val
                key = str(selection_list[index].id) + key_suffix
                rise_set_cache[key] = val

        time_filtered_list = []
        i = 0
        for rise_t, merid_t, set_t, is_up in composed_selection_rms_list:
            if is_up or rise_t < time_to or set_t>time_from:
                time_filtered_list.append((selection_list[i], _to_HM_format(rise_t, tz_info), _to_HM_format(merid_t, tz_info), _to_HM_format(set_t, tz_info)))
            i += 1

        # filter by altitude
        if len(time_filtered_list) > 0 and schedule_form.min_altitude.data is not None and schedule_form.min_altitude.data > 0:
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
        if offset >= all_count:
            offset = 0
            page = 1
        selection_compound_list = time_filtered_list[offset:offset+per_page]
    else:
        selection_rms_list = rise_merid_set_time_str(observation_time, observer, [(x.ra, x.dec) for x in selection_list], tz_info)
        selection_compound_list = [(selection_list[i], selection_rms_list[i]) for i in range(len(selection_list))]

    for row in selection_compound_list:
        obj = row[0]
        obj.object_type = 'dso'
        obj.object_id = obj.id
        obj.display_type = obj.type
        obj.display_constellation = obj.get_constellation_iau_code()
    return selection_compound_list, page, all_count


def _create_solar_system_selection_compound_list(session_plan, schedule_form, observer,
                                                 observation_time, time_from, time_to,
                                                 tz_info, page, offset, per_page, sort_by):
    source = schedule_form.obj_source.data
    id_attribute = ('comet_id' if source == SOURCE_COMETS else
                    'minor_planet_id' if source == SOURCE_MINOR_PLANETS else 'planet_id')
    selected_ids = _get_selected_object_ids(session_plan, id_attribute)
    candidates = []
    position_dt = get_session_plan_position_datetime(session_plan, tz_info)

    if source == SOURCE_COMETS:
        query = Comet.query
        if selected_ids:
            query = query.filter(Comet.id.notin_(selected_ids))
        if schedule_form.maglim.data is not None:
            query = query.filter(func.coalesce(Comet.real_mag, Comet.eval_mag) < schedule_form.maglim.data)
        if not session_plan.is_anonymous and schedule_form.not_observed.data:
            observed_subquery = db.session.query(ObservedListItem.comet_id) \
                .join(ObservedListItem.observed_list) \
                .filter(ObservedList.user_id == current_user.id,
                        ObservedListItem.comet_id.is_not(None))
            query = query.filter(Comet.id.notin_(observed_subquery))
        objects = query.all()
        for obj in objects:
            try:
                ra, dec = get_comet_radec(obj.comet_id, position_dt)
            except Exception:
                continue
            constell = Constellation.get_constellation_by_position(ra, dec)
            candidates.append(SelectionCandidate(
                obj.designation, constell.iau_code if constell else '',
                obj.real_mag if obj.real_mag is not None else obj.eval_mag,
                ra, dec, 'comet', obj.id, detail_id=obj.comet_id,
            ))
    elif source == SOURCE_MINOR_PLANETS:
        query = MinorPlanet.query.filter(MinorPlanet.id.notin_(selected_ids)) if selected_ids else MinorPlanet.query
        query = query.filter(MinorPlanet.cur_ra.is_not(None), MinorPlanet.cur_dec.is_not(None))
        if schedule_form.maglim.data is not None:
            query = query.filter(MinorPlanet.eval_mag < schedule_form.maglim.data)
        if schedule_form.constellation_id.data is not None:
            query = query.filter(MinorPlanet.cur_constell_id == schedule_form.constellation_id.data)
        if not session_plan.is_anonymous and schedule_form.not_observed.data:
            observed_subquery = db.session.query(ObservedListItem.minor_planet_id) \
                .join(ObservedListItem.observed_list) \
                .filter(ObservedList.user_id == current_user.id,
                        ObservedListItem.minor_planet_id.is_not(None))
            query = query.filter(MinorPlanet.id.notin_(observed_subquery))
        objects = query.all()
        for obj in objects:
            constell = obj.cur_constell()
            candidates.append(SelectionCandidate(
                obj.designation, constell.iau_code if constell else '', obj.eval_mag,
                obj.cur_ra, obj.cur_dec, 'minor_planet', obj.id, detail_id=obj.url_id(),
            ))
    else:
        objects = Planet.get_all()
        for obj in objects:
            if obj.id in selected_ids:
                continue
            try:
                ra, dec = get_mpc_planet_position(obj, position_dt)
            except Exception:
                continue
            constell = Constellation.get_constellation_by_position(ra.radians, dec.radians)
            candidates.append(SelectionCandidate(
                obj.get_localized_name(), constell.iau_code if constell else '', None,
                ra.radians, dec.radians, 'planet', obj.id,
                detail_id=obj.iau_code,
            ))

    # Solar-system sources use the same visible columns as the DSO source.
    if source != SOURCE_PLANETS and schedule_form.maglim.data is not None:
        candidates = [x for x in candidates if x.mag is not None and x.mag < schedule_form.maglim.data]
    if schedule_form.constellation_id.data is not None:
        constell = Constellation.get_constellation_by_id(schedule_form.constellation_id.data)
        if constell:
            candidates = [x for x in candidates if x.constellation == constell.iau_code]

    if sort_by:
        descending = sort_by.startswith('-')
        sort_name = sort_by.lstrip('-')
        key = {
            'name': lambda x: x.name or '',
            'constellation': lambda x: x.constellation or '',
            'mag': lambda x: x.mag if x.mag is not None else float('inf'),
        }.get(sort_name)
        if key:
            candidates.sort(key=key, reverse=descending)
    else:
        candidates.sort(key=lambda x: x.name or '')

    visibility = rise_merid_set_up(time_from, time_to, observer, [(x.ra, x.dec) for x in candidates])
    visible = []
    for candidate, (rise_t, merid_t, set_t, is_up) in zip(candidates, visibility):
        if is_up or rise_t < time_to or set_t > time_from:
            visible.append((candidate, rise_t, merid_t, set_t))

    if visible and schedule_form.min_altitude.data is not None and schedule_form.min_altitude.data > 0:
        constraints = [AltitudeConstraint(schedule_form.min_altitude.data * u.deg)]
        targets = [FixedTarget(coord=SkyCoord(ra=x[0].ra * u.rad, dec=x[0].dec * u.rad), name=x[0].name)
                   for x in visible]
        observable = is_observable(constraints, observer, targets, time_range=Time([time_from, time_to]))
        visible = [visible[i] for i in range(len(visible)) if observable[i]]

    all_count = len(visible)
    if offset >= all_count:
        offset = 0
        page = 1
    selected = visible[offset:offset + per_page]
    return [
        (row[0], _to_HM_format(row[1], tz_info), _to_HM_format(row[2], tz_info), _to_HM_format(row[3], tz_info))
        for row in selected
    ], page, all_count


def rise_merid_set_up(time_from, time_to, observer, ra_dec_list):
    coords = [ SkyCoord(x[0] * u.rad, x[1] * u.rad) for x in ra_dec_list]
    rise_list = _unmask_time(_wrap2array(observer.target_rise_time(time_from, coords, which='next', n_grid_points=10))) if len(coords) > 0 else []
    merid_list = _unmask_time(_wrap2array(observer.target_meridian_transit_time(time_from, coords, which='next', n_grid_points=10)))  if len(coords) > 0 else []
    set_list = _unmask_time(_wrap2array(observer.target_set_time(time_to, coords, which='previous', n_grid_points=10))) if len(coords) > 0 else []
    up_list = _wrap2array(observer.target_is_up(time_from, coords)) if len(coords) > 0 else []

    return [(rise_list[i], merid_list[i], set_list[i], up_list[i]) for i in range(len(rise_list))]


def rise_merid_set_time_str(t, observer, ra_dec_list, tz_info):
    coords = [SkyCoord(x[0] * u.rad, x[1] * u.rad) for x in ra_dec_list]
    rise_list = _ar_to_HM_format(_unmask_time(_wrap2array(observer.target_rise_time(t, coords, n_grid_points=10))), tz_info) if len(coords) > 0 else []
    merid_list = _ar_to_HM_format(_unmask_time(_wrap2array(observer.target_meridian_transit_time(t, coords, n_grid_points=10))), tz_info) if len(coords) > 0 else []
    set_list = _ar_to_HM_format(_unmask_time(_wrap2array(observer.target_set_time(t, coords, n_grid_points=10))), tz_info) if len(coords) > 0 else []

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
    merid_time_list = merid_time(observation_time, observer, [(x.get_ra(), x.get_dec()) for x in spi])
    session_plan_compound_list = [(spi[i], merid_time_list[i]) for i in range(len(spi))]
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

def _unmask_time(ar):
    result = []
    for t in ar:
        if t.masked:
            result.append(t.unmasked)
        else:
            result.append(t)
    return result
