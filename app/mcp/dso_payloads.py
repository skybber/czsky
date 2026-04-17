from __future__ import annotations

from typing import Any, Callable


def _build_observer_tzinfo(session_plan: Any):
    """Build astroplan Observer and pytz timezone from session plan location."""
    import pytz
    import astropy.units as u
    from astropy.coordinates import EarthLocation
    from astroplan import Observer

    from app.commons.coordinates import parse_latlon

    if session_plan.location:
        loc = session_plan.location
        loc_name = loc.name
        latitude = loc.latitude
        longitude = loc.longitude
        elevation = loc.elevation or 0
    else:
        loc_name = session_plan.location_position
        latitude, longitude = parse_latlon(session_plan.location_position)
        elevation = 0

    tz_info = pytz.timezone('Europe/Prague')
    loc_coords = EarthLocation.from_geodetic(longitude * u.deg, latitude * u.deg, elevation * u.m)
    observer = Observer(name=loc_name, location=loc_coords, timezone=tz_info)
    return observer, tz_info, latitude, longitude


def _get_twilight_window(session_plan: Any, latitude: float, longitude: float, tz_info: Any):
    """Return (time_from, time_to) for astronomical twilight, falling back to nautical then fixed."""
    from datetime import timedelta

    from skyfield.api import load, wgs84
    from skyfield import almanac

    def _try_twilight(comp):
        try:
            ts = load.timescale()
            observer = wgs84.latlon(latitude, longitude)
            ldate1 = tz_info.localize(session_plan.for_date + timedelta(hours=12))
            ldate2 = tz_info.localize(session_plan.for_date + timedelta(hours=36))
            t1 = ts.from_datetime(ldate1)
            t2 = ts.from_datetime(ldate2)
            eph = load('de421.bsp')
            t, y = almanac.find_discrete(t1, t2, almanac.dark_twilight_day(eph, observer))
            index1 = index2 = None
            for i in range(len(y)):
                if y[i] == comp:
                    if index1 is None:
                        index1 = i + 1
                    elif index2 is None:
                        index2 = i
            if index1 is not None and index2 is not None:
                return t[index1].astimezone(tz_info), t[index2].astimezone(tz_info)
        except Exception:
            pass
        return None, None

    t1, t2 = _try_twilight(1)  # astronomical
    if t1 and t2:
        return t1, t2
    t1, t2 = _try_twilight(2)  # nautical
    if t1 and t2:
        return t1, t2
    # fallback: 22:00 – 02:00
    t1 = tz_info.localize(session_plan.for_date + timedelta(hours=22))
    t2 = tz_info.localize(session_plan.for_date + timedelta(hours=26))
    return t1, t2


def _parse_time_filter(time_str: str | None, for_date: Any, tz_info: Any, default_dt: Any):
    """Parse HH:MM string into a timezone-aware datetime, falling back to default_dt."""
    from datetime import date, datetime, time, timedelta

    def _resolve_filter_date() -> date:
        if hasattr(for_date, "to_datetime"):
            return for_date.to_datetime().date()
        if isinstance(for_date, datetime):
            return for_date.date()
        if isinstance(for_date, date):
            return for_date
        if isinstance(default_dt, datetime):
            return default_dt.date()
        raise ValueError("Unsupported date type for time filter")

    if not time_str:
        return default_dt
    try:
        stripped = time_str.strip()
        filter_date = _resolve_filter_date()
        if stripped == '24:00':
            return tz_info.localize(datetime.combine(filter_date, time.min)) + timedelta(days=1)
        t = datetime.strptime(stripped, '%H:%M').time()
        parsed_dt = tz_info.localize(datetime.combine(filter_date, t))
        # Session-plan nights are modeled as the evening of for_date into the next morning.
        # Interpret early-morning local times as belonging to the next calendar day.
        if t < time(12, 0):
            parsed_dt += timedelta(days=1)
        return parsed_dt
    except (TypeError, ValueError, AttributeError):
        return default_dt


def _resolve_constellation_id(constellation: Any) -> int | None:
    from app.models import Constellation
    if constellation is None:
        return None
    if isinstance(constellation, int):
        return constellation
    if not isinstance(constellation, str) or not constellation.strip():
        return None
    stripped = constellation.strip()
    c = Constellation.get_constellation_by_iau_code(stripped)
    if c:
        return c.id
    match = Constellation.query.filter(Constellation.name.ilike(stripped)).first()
    return match.id if match else None


def dso_find_payload(
    *,
    obj_source: str | None,
    dso_type: str | None,
    maglim: int | None,
    constellation: str | int | None,
    min_altitude: int,
    session_plan_id: int | None,
    time_from: str | None,
    time_to: str | None,
    not_observed: bool,
    max_results: int,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from astropy.time import Time
    from astroplan import AltitudeConstraint, FixedTarget, is_observable
    from sqlalchemy import or_

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

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_wishlist_user_id_func(user_id)

    if max_results < 1 or max_results > 200:
        raise ValueError("max_results must be between 1 and 200")

    if session_plan_id is not None:
        if isinstance(session_plan_id, bool) or not isinstance(session_plan_id, int) or session_plan_id <= 0:
            raise ValueError("session_plan_id must be a positive integer")

    app = get_app()
    with app.app_context():
        # resolve session plan context if provided
        session_plan = None
        if session_plan_id is not None:
            from app.models import SessionPlan
            session_plan = SessionPlan.query.filter_by(
                id=session_plan_id, user_id=resolved_user_id, is_archived=False
            ).first()
            if session_plan is None:
                return {
                    "found": False,
                    "reason": "session_plan_not_found",
                    "total": 0,
                    "results": [],
                }

        # --- build base DSO query by source ---
        is_anonymous = session_plan.is_anonymous if session_plan else False
        effective_source = obj_source or ("M" if is_anonymous else None)

        if effective_source == "WL":
            wishlist_subq = (
                WishListItem.query
                .join(WishListItem.wish_list)
                .filter(WishList.user_id == resolved_user_id)
                .filter(WishListItem.dso_id.is_not(None))
                .with_entities(WishListItem.dso_id)
            )
            dso_query = DeepskyObject.query.filter(DeepskyObject.id.in_(wishlist_subq))
        elif isinstance(effective_source, str) and effective_source.startswith("dso_list:"):
            raw_id = effective_source[len("dso_list:"):]
            if not raw_id.isdigit():
                return {
                    "found": False,
                    "reason": "invalid_dso_list_id",
                    "total": 0,
                    "results": [],
                }
            dso_list_id = int(raw_id)
            dsolist_subq = (
                DsoListItem.query
                .join(DsoListItem.dso_list)
                .filter(DsoList.id == dso_list_id)
                .with_entities(DsoListItem.dso_id)
            )
            dso_query = DeepskyObject.query.filter(DeepskyObject.id.in_(dsolist_subq))
        else:
            dso_query = DeepskyObject.query
            cat_id = Catalogue.get_catalogue_id_by_cat_code(effective_source)
            if cat_id:
                dso_query = dso_query.filter_by(catalogue_id=cat_id)

        # optionally exclude already scheduled objects
        if session_plan is not None:
            scheduled_subq = (
                SessionPlanItem.query
                .filter(SessionPlanItem.session_plan_id == session_plan.id)
                .filter(SessionPlanItem.dso_id.is_not(None))
                .with_entities(SessionPlanItem.dso_id)
            )
            dso_query = dso_query.filter(DeepskyObject.id.notin_(scheduled_subq))

        # optionally exclude already observed
        if not is_anonymous and not_observed:
            observed_subq = (
                ObservedListItem.query
                .join(ObservedListItem.observed_list)
                .filter(ObservedList.user_id == resolved_user_id)
                .filter(ObservedListItem.dso_id.is_not(None))
                .with_entities(ObservedListItem.dso_id)
            )
            dso_query = dso_query.filter(DeepskyObject.id.notin_(observed_subq))
            dso_query = dso_query.filter(
                or_(DeepskyObject.master_id.is_(None), DeepskyObject.master_id.notin_(observed_subq))
            )

        # filter by type
        valid_types = {"GX", "GC", "OC", "BN", "PN"}
        if dso_type and dso_type in valid_types:
            dso_query = dso_query.filter(DeepskyObject.type == dso_type)

        # filter by magnitude
        if maglim is not None:
            dso_query = dso_query.filter(DeepskyObject.mag < maglim)

        # filter by constellation
        constellation_id = _resolve_constellation_id(constellation)
        if constellation_id is not None:
            dso_query = dso_query.filter(DeepskyObject.constellation_id == constellation_id)

        candidate_dsos = dso_query.order_by(DeepskyObject.mag.nullslast()).all()

        if not candidate_dsos:
            return {
                "found": True,
                "reason": "no_matching_objects",
                "total": 0,
                "results": [],
            }

        # --- visibility filter (only when session_plan provides location context) ---
        def _serialize(dso: Any, rise_str: str | None = None, merid_str: str | None = None, set_str: str | None = None) -> dict[str, Any]:
            from app.models import Constellation
            constell = Constellation.get_constellation_by_id(dso.constellation_id)
            result = {
                "name": dso.name,
                "type": dso.type,
                "magnitude": round(dso.mag, 1) if dso.mag is not None else None,
                "constellation": constell.iau_code if constell else None,
            }
            if rise_str is not None:
                result["riseTime"] = rise_str
                result["meridianTime"] = merid_str
                result["setTime"] = set_str
            return result

        if session_plan is not None:
            from app.main.planner.session_scheduler import rise_merid_set_up

            observer, tz_info, latitude, longitude = _build_observer_tzinfo(session_plan)
            observation_time = Time(session_plan.for_date)

            default_t1, default_t2 = _get_twilight_window(session_plan, latitude, longitude, tz_info)
            tf = _parse_time_filter(time_from, observation_time, tz_info, default_t1)
            tt = _parse_time_filter(time_to, observation_time, tz_info, default_t2)
            if tt < tf:
                from datetime import timedelta
                tt = tt + timedelta(days=1)

            coords_list = [(dso.ra, dso.dec) for dso in candidate_dsos]
            rms_list = rise_merid_set_up(tf, tt, observer, coords_list)

            def _fmt(t: Any) -> str | None:
                if t is None:
                    return None
                try:
                    return t.astimezone(tz_info).strftime('%H:%M')
                except Exception:
                    return None

            visible_items = [
                (candidate_dsos[i], _fmt(rms_list[i][0]), _fmt(rms_list[i][1]), _fmt(rms_list[i][2]))
                for i, (rise_t, merid_t, set_t, is_up) in enumerate(rms_list)
                if is_up or rise_t < tt or set_t > tf
            ]

            if min_altitude > 0 and visible_items:
                constraints = [AltitudeConstraint(min_altitude * u.deg)]
                targets = [
                    FixedTarget(coord=SkyCoord(ra=item[0].ra * u.rad, dec=item[0].dec * u.rad), name=item[0].name)
                    for item in visible_items
                ]
                time_range = Time([tf, tt])
                observable = is_observable(constraints, observer, targets, time_range=time_range)
                visible_items = [visible_items[i] for i in range(len(visible_items)) if observable[i]]

            results = [_serialize(dso, rise, merid, sett) for dso, rise, merid, sett in visible_items[:max_results]]
        else:
            results = [_serialize(dso) for dso in candidate_dsos[:max_results]]

        return {
            "found": True,
            "reason": "ok",
            "total": len(results),
            "results": results,
        }


def dso_list_sources_payload(
    *,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app.models import Catalogue, DsoList

    require_scope_if_available_func(required_scope)
    resolve_wishlist_user_id_func(user_id)

    app = get_app()
    with app.app_context():
        catalogues = [
            {
                "sourceType": "catalogue",
                "sourceValue": catalogue.code,
                "catalogueId": catalogue.id,
                "code": catalogue.code,
                "name": catalogue.name,
                "description": catalogue.descr,
            }
            for catalogue in Catalogue.query.order_by(Catalogue.code.asc()).all()
        ]
        dso_lists = [
            {
                "sourceType": "dso_list",
                "sourceValue": f"dso_list:{dso_list.id}",
                "dsoListId": dso_list.id,
                "name": dso_list.name,
                "longName": dso_list.long_name,
            }
            for dso_list in DsoList.query.filter(DsoList.hidden.is_(False)).order_by(DsoList.name.asc(), DsoList.id.asc()).all()
        ]

        return {
            "sources": [
                {
                    "sourceType": "wishlist",
                    "sourceValue": "WL",
                    "name": "Wishlist",
                },
                *catalogues,
                *dso_lists,
            ],
            "catalogues": catalogues,
            "dsoLists": dso_lists,
        }
