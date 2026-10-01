"""Shared helpers for MCP tools working with locations, dates and ephemerides.

All functions expect an active Flask app context.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any

DEFAULT_TIMEZONE = "Europe/Prague"
EPHEMERIS_FILE = "de421.bsp"

# almanac.dark_twilight_day states: 0 dark, 1 astronomical, 2 nautical, 3 civil twilight, 4 day.
_TWILIGHT_TRANSITIONS = {
    (4, 3): "sunset",
    (3, 2): "civilDusk",
    (2, 1): "nauticalDusk",
    (1, 0): "astronomicalDusk",
    (0, 1): "astronomicalDawn",
    (1, 2): "nauticalDawn",
    (2, 3): "civilDawn",
    (3, 4): "sunrise",
}


class McpLookupError(Exception):
    """Raised when an input (location, object, date) cannot be resolved; ``reason`` is machine readable."""

    def __init__(self, reason: str, candidates: list[dict[str, Any]] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.candidates = candidates or []

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"found": False, "reason": self.reason}
        if self.candidates:
            payload["candidates"] = self.candidates
        return payload


def get_ephemeris():
    from app.commons.solar_system_chart_utils import _get_ephemeris

    return _get_ephemeris(EPHEMERIS_FILE)


def get_timescale():
    from skyfield.api import load

    return load.timescale(builtin=True)


def get_location_timezone(location: Any = None):
    import pytz

    tz_name = getattr(location, "time_zone", None) if location is not None else None
    if tz_name:
        try:
            return pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            pass
    return pytz.timezone(DEFAULT_TIMEZONE)


def serialize_location(location: Any) -> dict[str, Any]:
    return {
        "locationId": location.id,
        "name": location.name,
        "latitude": round(location.latitude, 5) if location.latitude is not None else None,
        "longitude": round(location.longitude, 5) if location.longitude is not None else None,
        "elevation": location.elevation,
        "bortle": location.bortle,
        "rating": location.rating,
        "countryCode": location.country_code,
        "isPublic": bool(location.is_public),
    }


def location_visible_to_user(resolved_user_id: int):
    """SQL condition: own location, or public location meant for observation (checked at read time)."""
    from sqlalchemy import and_, or_

    from app.models import Location

    return or_(
        Location.user_id == resolved_user_id,
        and_(Location.is_public.is_(True), Location.is_for_observation.is_(True)),
    )


def find_default_location(resolved_user_id: int):
    """Most recently used location of the user (observing session or session plan) still visible to them."""
    from app.models import Location, ObservingSession, SessionPlan

    candidates = []
    session_row = (
        ObservingSession.query
        .join(Location, ObservingSession.location_id == Location.id)
        .filter(ObservingSession.user_id == resolved_user_id, location_visible_to_user(resolved_user_id))
        .order_by(ObservingSession.date_from.desc())
        .first()
    )
    if session_row is not None:
        candidates.append((session_row.date_from, session_row.location_id))
    plan_row = (
        SessionPlan.query
        .join(Location, SessionPlan.location_id == Location.id)
        .filter(SessionPlan.user_id == resolved_user_id, location_visible_to_user(resolved_user_id))
        .order_by(SessionPlan.for_date.desc())
        .first()
    )
    if plan_row is not None:
        candidates.append((plan_row.for_date, plan_row.location_id))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0] or datetime.min, reverse=True)
    return Location.query.filter_by(id=candidates[0][1]).first()


def _looks_like_coordinates(value: str) -> bool:
    from app.commons.coordinates import parse_latlon

    if "," not in value:
        return False
    try:
        parse_latlon(value)
    except Exception:
        return False
    return True


def resolve_user_location(resolved_user_id: int, location: Any) -> dict[str, Any]:
    """Resolve location id, name or "lat,lon" text into observer data.

    Without ``location`` the most recently used location of the user is taken.
    """
    from app.commons.coordinates import parse_latlon
    from app.mcp.session_plan_payloads import _resolve_location_for_session_plan_create
    from app.models import Location

    if location is None or (isinstance(location, str) and not location.strip()):
        default_location = find_default_location(resolved_user_id)
        if default_location is None:
            raise McpLookupError("location_required")
        location_row = default_location
    elif isinstance(location, str) and _looks_like_coordinates(location.strip()):
        latitude, longitude = parse_latlon(location.strip())
        return {
            "locationId": None,
            "name": location.strip(),
            "latitude": float(latitude),
            "longitude": float(longitude),
            "elevation": 0.0,
            "timezone": get_location_timezone(None),
        }
    else:
        kwargs = {"location_id": None, "location_name": None, "location": None}
        if isinstance(location, int) or (isinstance(location, str) and location.strip().isdigit()):
            kwargs["location_id"] = location
        else:
            kwargs["location_name"] = str(location)
        location_id, _, error_reason, candidates = _resolve_location_for_session_plan_create(
            resolved_user_id=resolved_user_id,
            **kwargs,
        )
        if error_reason:
            raise McpLookupError(error_reason, candidates)
        location_row = Location.query.filter_by(id=location_id).first()

    return {
        "locationId": location_row.id,
        "name": location_row.name,
        "latitude": float(location_row.latitude),
        "longitude": float(location_row.longitude),
        "elevation": float(location_row.elevation or 0.0),
        "timezone": get_location_timezone(location_row),
    }


def public_location(observer_location: dict[str, Any]) -> dict[str, Any]:
    return {
        "locationId": observer_location["locationId"],
        "name": observer_location["name"],
        "latitude": round(observer_location["latitude"], 5),
        "longitude": round(observer_location["longitude"], 5),
        "timezone": observer_location["timezone"].zone,
    }


def parse_date_param(value: Any, tz: Any) -> date:
    """Parse YYYY-MM-DD; default is today in the given timezone (evening of the observing night)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return datetime.now(tz).date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise McpLookupError("invalid_date")
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError as exc:
        raise McpLookupError("invalid_date") from exc


def local_datetime(day: date, hour: float, tz: Any) -> datetime:
    return tz.localize(datetime.combine(day, datetime.min.time()) + timedelta(hours=hour))


def to_utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def fmt_local(dt: datetime | None, tz: Any) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).isoformat(timespec="minutes")


def _skyfield_observer(latitude: float, longitude: float, elevation: float = 0.0):
    from skyfield.api import wgs84

    return wgs84.latlon(latitude, longitude, elevation_m=elevation or 0.0)


def compute_twilight(latitude: float, longitude: float, day: date, tz: Any) -> dict[str, Any]:
    """Sun and twilight events of the night starting on ``day`` (local noon to next noon)."""
    from skyfield import almanac

    eph = get_ephemeris()
    ts = get_timescale()
    t1 = ts.from_datetime(local_datetime(day, 12, tz))
    t2 = ts.from_datetime(local_datetime(day, 36, tz))
    f = almanac.dark_twilight_day(eph, _skyfield_observer(latitude, longitude))
    times, states = almanac.find_discrete(t1, t2, f)

    events: dict[str, Any] = {name: None for name in _TWILIGHT_TRANSITIONS.values()}
    previous = int(f(t1))
    for t, state in zip(times, states):
        name = _TWILIGHT_TRANSITIONS.get((previous, int(state)))
        if name and events[name] is None:
            events[name] = t.utc_datetime()
        previous = int(state)

    # Darkest available window: astronomical night, otherwise nautical twilight (summer at high latitude).
    dark_from, dark_to = events["astronomicalDusk"], events["astronomicalDawn"]
    darkness = "astronomical"
    if dark_from is None or dark_to is None:
        dark_from, dark_to = events["civilDusk"], events["civilDawn"]
        darkness = "nautical" if dark_from and dark_to else "none"
    return {
        "events": events,
        "darkFrom": dark_from,
        "darkTo": dark_to,
        "darkness": darkness,
    }


def _moon_phase_name(phase_deg: float) -> str:
    # Principal phases are instants; keep them within +-10 degrees (about +-20 hours).
    names = [
        (10, "new"), (80, "waxing_crescent"), (100, "first_quarter"), (170, "waxing_gibbous"),
        (190, "full"), (260, "waning_gibbous"), (280, "last_quarter"), (350, "waning_crescent"),
    ]
    for limit, name in names:
        if phase_deg < limit:
            return name
    return "new"


def compute_moon(latitude: float, longitude: float, day: date, tz: Any) -> dict[str, Any]:
    """Moon phase at local midnight and its rise/set events from local noon to next noon."""
    from skyfield import almanac

    eph = get_ephemeris()
    ts = get_timescale()
    t1 = ts.from_datetime(local_datetime(day, 12, tz))
    t2 = ts.from_datetime(local_datetime(day, 36, tz))
    t_mid = ts.from_datetime(local_datetime(day, 24, tz))
    f = almanac.risings_and_settings(eph, eph["moon"], _skyfield_observer(latitude, longitude))
    times, ups = almanac.find_discrete(t1, t2, f)

    up_intervals = []
    is_up = bool(f(t1))
    start = t1.utc_datetime() if is_up else None
    rise = moon_set = None
    for t, up in zip(times, ups):
        if up:
            rise = rise or t.utc_datetime()
            start = t.utc_datetime()
        else:
            moon_set = moon_set or t.utc_datetime()
            if start is not None:
                up_intervals.append((start, t.utc_datetime()))
            start = None
    if start is not None:
        up_intervals.append((start, t2.utc_datetime()))

    phase_deg = float(almanac.moon_phase(eph, t_mid).degrees) % 360
    illumination = float(almanac.fraction_illuminated(eph, "moon", t_mid))
    return {
        "rise": rise,
        "set": moon_set,
        "upIntervals": up_intervals,
        "phaseDeg": round(phase_deg, 1),
        "phaseName": _moon_phase_name(phase_deg),
        "illumination": round(illumination, 3),
    }


def moonless_windows(dark_from: datetime | None, dark_to: datetime | None,
                     up_intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if dark_from is None or dark_to is None:
        return []
    windows = [(dark_from, dark_to)]
    for up_from, up_to in up_intervals:
        next_windows = []
        for w_from, w_to in windows:
            if up_to <= w_from or up_from >= w_to:
                next_windows.append((w_from, w_to))
                continue
            if up_from > w_from:
                next_windows.append((w_from, up_from))
            if up_to < w_to:
                next_windows.append((up_to, w_to))
        windows = next_windows
    return [(w_from, w_to) for w_from, w_to in windows if (w_to - w_from) >= timedelta(minutes=1)]


def target_label(object_type: str, obj: Any) -> str:
    if object_type == "dso":
        return obj.denormalized_name()
    if object_type == "double_star":
        return obj.get_catalog_name()
    if object_type == "star":
        return obj.get_name() or f"Star {obj.id}"
    if object_type == "comet":
        return obj.designation
    if object_type == "minor_planet":
        return obj.designation
    if object_type == "planet":
        # get_localized_name() needs a request context (Babel); MCP answers in English anyway.
        return obj.iau_code.capitalize()
    if object_type == "earth_moon":
        return "Moon"
    return str(obj)


def target_radec(object_type: str, obj: Any, dt_utc: datetime) -> tuple[float, float]:
    """Return (ra, dec) in radians of a resolved object at given UTC time."""
    if object_type == "dso":
        return obj.ra, obj.dec
    if object_type == "double_star":
        return obj.ra_first, obj.dec_first
    if object_type == "star":
        return obj.ra, obj.dec
    if object_type == "comet":
        from app.commons.comet_utils import find_mpc_comet, get_mpc_comet_position

        mpc_comet = find_mpc_comet(obj.comet_id)
        if mpc_comet is None:
            raise McpLookupError("ephemeris_unavailable")
        ra, dec = get_mpc_comet_position(mpc_comet, dt_utc)
        return ra.radians, dec.radians
    if object_type == "minor_planet":
        from app.commons.minor_planet_utils import find_mpc_minor_planet, get_mpc_minor_planet_position

        ra, dec = get_mpc_minor_planet_position(find_mpc_minor_planet(obj), dt_utc)
        return ra.radians, dec.radians
    if object_type == "planet":
        from app.commons.solar_system_chart_utils import get_mpc_planet_position

        ra, dec = get_mpc_planet_position(obj, dt_utc)
        return ra.radians, dec.radians
    if object_type == "earth_moon":
        eph = get_ephemeris()
        t = get_timescale().from_datetime(dt_utc.replace(tzinfo=timezone.utc))
        ra, dec, _ = eph["earth"].at(t).observe(eph["moon"]).apparent().radec()
        return ra.radians, dec.radians
    raise McpLookupError("unsupported_object_type")


def altaz_at(latitude: float, longitude: float, elevation: float, ra: float, dec: float,
             dt_utc: datetime) -> tuple[float, float]:
    """Altitude and azimuth in degrees of a fixed RA/Dec (radians) at given UTC time."""
    from skyfield.api import Angle, Star

    eph = get_ephemeris()
    t = get_timescale().from_datetime(dt_utc.replace(tzinfo=timezone.utc))
    observer = eph["earth"] + _skyfield_observer(latitude, longitude, elevation)
    star = Star(ra=Angle(radians=ra), dec=Angle(radians=dec))
    alt, az, _ = observer.at(t).observe(star).apparent().altaz()
    return round(float(alt.degrees), 1), round(float(az.degrees), 1)


def max_altitude_deg(latitude: float, dec: float) -> float:
    return round(90.0 - abs(latitude - math.degrees(dec)), 1)


SIDEREAL_TO_SOLAR = 0.9972695663
_J2000 = datetime(2000, 1, 1, 12, 0, 0)


def _gmst_hours(dt_utc: datetime) -> float:
    """Greenwich mean sidereal time in hours (accurate to a fraction of a second over decades)."""
    days = (dt_utc - _J2000).total_seconds() / 86400.0
    return (18.697374558 + 24.06570982441908 * days) % 24.0


def rise_transit_set(observer_location: dict[str, Any], day: date, ra: float, dec: float,
                     horizon_deg: float = 0.0) -> dict[str, Any]:
    """Rise, transit and set of a fixed RA/Dec (radians) for the night starting on ``day``.

    Transit is the one nearest to local midnight, rise the one before it and set the one
    after it, so the three events always describe one pass over the sky. Computed from the
    hour angle (geometric horizon, no refraction), which is exact to about a minute and
    avoids astroplan's grid search that can skip an event close to the start time.
    """
    tz = observer_location["timezone"]
    latitude = math.radians(observer_location["latitude"])
    midnight_utc = to_utc_naive(local_datetime(day, 24, tz))

    lst = (_gmst_hours(midnight_utc) + observer_location["longitude"] / 15.0) % 24.0
    hour_angle = (lst - math.degrees(ra) / 15.0 + 12.0) % 24.0 - 12.0
    transit = midnight_utc - timedelta(hours=hour_angle * SIDEREAL_TO_SOLAR)

    numerator = math.sin(math.radians(horizon_deg)) - math.sin(latitude) * math.sin(dec)
    cos_h0 = numerator / (math.cos(latitude) * math.cos(dec))
    rise = set_ = None
    if cos_h0 > 1.0:
        status = "never_rises"
        transit = None
    elif cos_h0 < -1.0:
        status = "circumpolar"
    else:
        status = "ok"
        half_arc = timedelta(hours=math.degrees(math.acos(cos_h0)) / 15.0 * SIDEREAL_TO_SOLAR)
        rise, set_ = transit - half_arc, transit + half_arc
    return {
        "status": status,
        "rise": fmt_local(rise, tz),
        "transit": fmt_local(transit, tz),
        "set": fmt_local(set_, tz),
        "transitAltitudeDeg": max_altitude_deg(observer_location["latitude"], dec),
    }


def radec_to_text(ra: float, dec: float) -> dict[str, Any]:
    return {
        "raDeg": round(math.degrees(ra) % 360, 4),
        "decDeg": round(math.degrees(dec), 4),
    }


def constellation_code(ra: float, dec: float) -> str | None:
    from app.models import Constellation

    try:
        constellation = Constellation.get_constellation_by_position(ra, dec)
    except Exception:
        return None
    return constellation.iau_code if constellation else None
