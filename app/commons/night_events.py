"""Sun twilight and Moon rise/set events of one night, computed with skyfield.

A night is the 24 hour window starting at local noon, so all evening and morning events
of one observing night are reported together.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

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

NIGHT_LENGTH = timedelta(hours=24)


def get_ephemeris():
    from app.commons.solar_system_chart_utils import _get_ephemeris

    return _get_ephemeris(EPHEMERIS_FILE)


def get_timescale():
    from skyfield.api import load

    return load.timescale(builtin=True)


def skyfield_observer(latitude: float, longitude: float, elevation: float = 0.0):
    from skyfield.api import wgs84

    return wgs84.latlon(latitude, longitude, elevation_m=elevation or 0.0)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def twilight_events(latitude: float, longitude: float, night_start: datetime) -> dict[str, Any]:
    """Sun and twilight events within 24 hours from ``night_start`` (local noon)."""
    from skyfield import almanac

    eph = get_ephemeris()
    ts = get_timescale()
    t1 = ts.from_datetime(_as_utc(night_start))
    t2 = ts.from_datetime(_as_utc(night_start + NIGHT_LENGTH))
    f = almanac.dark_twilight_day(eph, skyfield_observer(latitude, longitude))
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
        "sunUpAtStart": int(f(t1)) == 4,
    }


def moon_phase_name(phase_deg: float) -> str:
    # Principal phases are instants; keep them within +-10 degrees (about +-20 hours).
    names = [
        (10, "new"), (80, "waxing_crescent"), (100, "first_quarter"), (170, "waxing_gibbous"),
        (190, "full"), (260, "waning_gibbous"), (280, "last_quarter"), (350, "waning_crescent"),
    ]
    for limit, name in names:
        if phase_deg < limit:
            return name
    return "new"


def moon_events(latitude: float, longitude: float, night_start: datetime) -> dict[str, Any]:
    """Moon phase at the middle of the night and its rise/set within 24 hours from ``night_start``."""
    from skyfield import almanac

    eph = get_ephemeris()
    ts = get_timescale()
    t1 = ts.from_datetime(_as_utc(night_start))
    t2 = ts.from_datetime(_as_utc(night_start + NIGHT_LENGTH))
    t_mid = ts.from_datetime(_as_utc(night_start + NIGHT_LENGTH / 2))
    f = almanac.risings_and_settings(eph, eph["moon"], skyfield_observer(latitude, longitude))
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
        "upAtStart": is_up,
        "upIntervals": up_intervals,
        "phaseDeg": round(phase_deg, 1),
        "phaseName": moon_phase_name(phase_deg),
        "illumination": round(illumination, 3),
    }


def _iso(dt: datetime | None) -> str | None:
    return _as_utc(dt).isoformat(timespec="seconds").replace("+00:00", "Z") if dt is not None else None


@lru_cache(maxsize=256)
def _cached_night_info(latitude: float, longitude: float, night_start: datetime) -> dict[str, Any]:
    twilight = twilight_events(latitude, longitude, night_start)
    moon = moon_events(latitude, longitude, night_start)
    events = twilight["events"]
    return {
        "nightStart": _iso(night_start),
        "sun": {
            "set": _iso(events["sunset"]),
            "rise": _iso(events["sunrise"]),
            "upAllNight": events["sunset"] is None and twilight["sunUpAtStart"],
            "downAllNight": events["sunset"] is None and not twilight["sunUpAtStart"],
        },
        "astronomicalNight": {
            "from": _iso(events["astronomicalDusk"]),
            "to": _iso(events["astronomicalDawn"]),
        },
        "moon": {
            "rise": _iso(moon["rise"]),
            "set": _iso(moon["set"]),
            "upAtStart": moon["upAtStart"],
            "phaseName": moon["phaseName"],
            "phaseDeg": moon["phaseDeg"],
            "illumination": moon["illumination"],
        },
    }


def night_info(latitude: float, longitude: float, night_start: datetime) -> dict[str, Any]:
    """JSON-ready Sun, astronomical night and Moon events of the night starting at ``night_start``.

    Inputs are rounded (0.01 deg, 1 minute) so repeated requests share the cache.
    """
    start = _as_utc(night_start).replace(second=0, microsecond=0)
    return _cached_night_info(round(latitude, 2), round(longitude, 2), start)
