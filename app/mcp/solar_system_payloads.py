"""Currently interesting moving and transient objects: comets, minor planets, supernovae, planets."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.mcp.astro_common import (
    McpLookupError,
    constellation_code,
    get_ephemeris,
    get_timescale,
    local_datetime,
    parse_date_param,
    public_location,
    radec_to_text,
    resolve_user_location,
    rise_transit_set,
    to_utc_naive,
)

MAX_LIST_LIMIT = 50


def _validate_limit(limit: Any) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_LIST_LIMIT:
        raise ValueError(f"limit must be an integer from 1 to {MAX_LIST_LIMIT}")
    return limit


def _round(value: Any, digits: int = 1) -> float | None:
    return round(float(value), digits) if value is not None else None


def _resolve_optional_location(resolved_user_id: int, location: Any, date: Any):
    """Observer location and night for optional visibility columns; None without ``location``."""
    if location is None or (isinstance(location, str) and not location.strip()):
        return None, None
    observer_location = resolve_user_location(resolved_user_id, location)
    return observer_location, parse_date_param(date, observer_location["timezone"])


def _add_visibility(entry: dict[str, Any], observer_location, day, ra, dec) -> None:
    if observer_location is None or ra is None or dec is None:
        return
    try:
        entry["visibility"] = rise_transit_set(observer_location, day, ra, dec)
    except Exception:
        entry["visibility"] = None


def _visibility_context(observer_location, day) -> dict[str, Any] | None:
    if observer_location is None:
        return None
    return {"date": day.isoformat(), "location": public_location(observer_location)}


def comet_list_bright_payload(
    *,
    maglim: float,
    min_dec: float | None,
    location: Any,
    date: str | None,
    limit: int,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)
    limit = _validate_limit(limit)

    app = get_app()
    with app.app_context():
        from app.models import Comet

        try:
            observer_location, day = _resolve_optional_location(resolved_user_id, location, date)
        except McpLookupError as e:
            return e.to_payload()

        comets = Comet.query.filter(
            Comet.mag.is_not(None),
            Comet.mag <= maglim,
            Comet.is_disintegrated.is_not(True),
        )
        if min_dec is not None:
            comets = comets.filter(Comet.cur_dec > math.radians(min_dec))
        rows = comets.order_by(Comet.mag.asc()).limit(limit).all()

        results = []
        for comet in rows:
            entry = {
                "objectId": f"comet:{comet.id}",
                "designation": comet.designation,
                "cometId": comet.comet_id,
                "magnitude": _round(comet.mag),
                "observedMagnitude": _round(comet.real_mag),
                "comaDiameterArcmin": _round(comet.real_coma_diameter),
                "constellation": comet.cur_constellation_iau_code(),
                **(radec_to_text(comet.cur_ra, comet.cur_dec) if comet.cur_ra is not None else {}),
            }
            _add_visibility(entry, observer_location, day, comet.cur_ra, comet.cur_dec)
            results.append(entry)
        return {
            "found": bool(results),
            "reason": "ok" if results else "no_comets",
            "maglim": maglim,
            "visibilityFor": _visibility_context(observer_location, day),
            "total": len(results),
            "comets": results,
        }


def minor_planet_list_bright_payload(
    *,
    maglim: float,
    min_elongation_deg: float | None,
    location: Any,
    date: str | None,
    limit: int,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)
    limit = _validate_limit(limit)

    app = get_app()
    with app.app_context():
        from app.models import MinorPlanet

        try:
            observer_location, day = _resolve_optional_location(resolved_user_id, location, date)
        except McpLookupError as e:
            return e.to_payload()

        minor_planets = MinorPlanet.query.filter(MinorPlanet.eval_mag.is_not(None), MinorPlanet.eval_mag <= maglim)
        if min_elongation_deg is not None:
            minor_planets = minor_planets.filter(
                MinorPlanet.cur_angular_dist_from_sun > math.radians(min_elongation_deg)
            )
        rows = minor_planets.order_by(MinorPlanet.eval_mag.asc()).limit(limit).all()

        results = []
        for minor_planet in rows:
            entry = {
                "objectId": f"minor_planet:{minor_planet.id}",
                "designation": minor_planet.designation or str(minor_planet.int_designation),
                "number": minor_planet.int_designation,
                "magnitude": _round(minor_planet.eval_mag),
                "elongationDeg": _round(math.degrees(minor_planet.cur_angular_dist_from_sun))
                if minor_planet.cur_angular_dist_from_sun is not None else None,
                "constellation": minor_planet.cur_constellation_iau_code(),
                **(radec_to_text(minor_planet.cur_ra, minor_planet.cur_dec) if minor_planet.cur_ra is not None else {}),
            }
            _add_visibility(entry, observer_location, day, minor_planet.cur_ra, minor_planet.cur_dec)
            results.append(entry)
        return {
            "found": bool(results),
            "reason": "ok" if results else "no_minor_planets",
            "maglim": maglim,
            "visibilityFor": _visibility_context(observer_location, day),
            "total": len(results),
            "minorPlanets": results,
        }


def supernova_list_recent_payload(
    *,
    maglim: float,
    days: int,
    min_dec: float | None,
    location: Any,
    date: str | None,
    limit: int,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)
    limit = _validate_limit(limit)
    if isinstance(days, bool) or not isinstance(days, int) or days < 1 or days > 365:
        raise ValueError("days must be an integer from 1 to 365")

    app = get_app()
    with app.app_context():
        from app.models import Supernova

        try:
            observer_location, day = _resolve_optional_location(resolved_user_id, location, date)
        except McpLookupError as e:
            return e.to_payload()

        supernovae = Supernova.query.filter(
            Supernova.is_archived.is_not(True),
            Supernova.latest_mag.is_not(None),
            Supernova.latest_mag <= maglim,
            Supernova.latest_observed >= datetime.now() - timedelta(days=days),
        )
        if min_dec is not None:
            supernovae = supernovae.filter(Supernova.dec > math.radians(min_dec))
        rows = supernovae.order_by(Supernova.latest_mag.asc()).limit(limit).all()

        results = []
        for supernova in rows:
            entry = {
                "designation": ", ".join(part for part in (supernova.designation or "").split(";") if part) or None,
                "hostGalaxy": supernova.host_galaxy,
                "type": supernova.sn_type,
                "latestMagnitude": _round(supernova.latest_mag),
                "latestObserved": supernova.latest_observed.date().isoformat() if supernova.latest_observed else None,
                "maxMagnitude": _round(supernova.max_mag),
                "firstObserved": supernova.first_observed.date().isoformat() if supernova.first_observed else None,
                "offset": supernova.offset,
                "discoverer": supernova.discoverer,
                "constellation": constellation_code(supernova.ra, supernova.dec) if supernova.ra is not None else None,
                **(radec_to_text(supernova.ra, supernova.dec) if supernova.ra is not None else {}),
            }
            _add_visibility(entry, observer_location, day, supernova.ra, supernova.dec)
            results.append(entry)
        return {
            "found": bool(results),
            "reason": "ok" if results else "no_supernovae",
            "maglim": maglim,
            "days": days,
            "visibilityFor": _visibility_context(observer_location, day),
            "total": len(results),
            "supernovae": results,
        }


def planet_positions_payload(
    *,
    date: str | None,
    location: Any,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    app = get_app()
    with app.app_context():
        from skyfield.magnitudelib import planetary_magnitude

        from app.mcp.astro_common import get_location_timezone
        from app.models import Planet

        try:
            observer_location = resolve_user_location(resolved_user_id, location)
        except McpLookupError as e:
            if e.reason != "location_required":
                return e.to_payload()
            observer_location = None
        tz = observer_location["timezone"] if observer_location else get_location_timezone(None)
        try:
            day = parse_date_param(date, tz)
        except McpLookupError as e:
            return e.to_payload()

        midnight_utc = to_utc_naive(local_datetime(day, 24, tz))
        eph = get_ephemeris()
        t = get_timescale().from_datetime(midnight_utc.replace(tzinfo=timezone.utc))
        earth = eph["earth"].at(t)
        sun = earth.observe(eph["sun"]).apparent()

        results = []
        for planet in Planet.get_all():
            astrometric = earth.observe(planet.eph).apparent()
            ra, dec, distance = astrometric.radec()
            try:
                magnitude = _round(planetary_magnitude(astrometric))
                if magnitude is not None and math.isnan(magnitude):
                    magnitude = None
            except Exception:
                magnitude = None
            entry = {
                "objectId": f"planet:{planet.id}",
                "name": planet.iau_code.capitalize(),
                "iauCode": planet.iau_code,
                "magnitude": magnitude,
                "elongationDeg": _round(astrometric.separation_from(sun).degrees),
                "distanceAu": round(float(distance.au), 3),
                "constellation": constellation_code(ra.radians, dec.radians),
                **radec_to_text(ra.radians, dec.radians),
            }
            _add_visibility(entry, observer_location, day, ra.radians, dec.radians)
            results.append(entry)

        return {
            "found": True,
            "reason": "ok",
            "date": day.isoformat(),
            "positionsAt": midnight_utc.isoformat() + "Z",
            "visibilityFor": _visibility_context(observer_location, day),
            "planets": results,
        }
