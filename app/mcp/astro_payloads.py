"""Visibility, night conditions and session plan scheduling for MCP tools."""

from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO
from typing import Any, Callable

from app.mcp.astro_common import (
    McpLookupError,
    altaz_at,
    compute_moon,
    compute_twilight,
    constellation_code,
    fmt_local,
    local_datetime,
    moonless_windows,
    parse_date_param,
    public_location,
    radec_to_text,
    resolve_user_location,
    rise_transit_set,
    target_label,
    target_radec,
    to_utc_naive,
)

POSITION_OBJECT_TYPES = {"dso", "double_star", "star", "comet", "minor_planet", "planet", "earth_moon"}


def resolve_sky_target(
    app: Any,
    *,
    object_id: str | None,
    query: str | None,
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
) -> tuple[str, Any]:
    """Resolve ``object_id`` (e.g. dso:123) or free text query into (object_type, object)."""
    from app.mcp.observation_log_payloads import _resolve_target_from_object_reference, parse_observation_object_id

    stripped_object_id = (object_id or "").strip()
    stripped_query = (query or "").strip()
    if bool(stripped_object_id) == bool(stripped_query):
        raise McpLookupError("invalid_arguments")

    if stripped_object_id:
        target, error_reason = _resolve_target_from_object_reference(
            object_id=stripped_object_id,
            parse_observation_object_id_func=parse_observation_object_id,
        )
        if error_reason:
            raise McpLookupError(error_reason)
        object_type, obj = target["objectType"], target["targetObject"]
        if object_type == "planet":
            from app.models import Planet

            obj = Planet.get_planet_by_id(obj.id)
    else:
        with app.test_request_context("/", headers={"Host": "localhost"}):
            resolved = resolve_global_object_func(stripped_query)
        if not resolved:
            raise McpLookupError("target_not_found")
        object_type, obj = resolved["object_type"], resolved["object"]

    if object_type not in POSITION_OBJECT_TYPES:
        raise McpLookupError("unsupported_object_type")
    return object_type, obj


def _parse_local_time(value: str, day, tz) -> datetime:
    """HH:MM of the observing night; times before noon belong to the next day."""
    try:
        parsed = datetime.strptime(value.strip(), "%H:%M")
    except ValueError as exc:
        raise McpLookupError("invalid_time") from exc
    hours = parsed.hour + parsed.minute / 60.0
    if hours < 12:
        hours += 24
    return local_datetime(day, hours, tz)


def visibility_get_payload(
    *,
    object_id: str | None,
    query: str | None,
    date: str | None,
    location: Any,
    time: str | None,
    horizon_deg: float,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    app = get_app()
    with app.app_context():
        try:
            object_type, obj = resolve_sky_target(
                app, object_id=object_id, query=query, resolve_global_object_func=resolve_global_object_func,
            )
            observer_location = resolve_user_location(resolved_user_id, location)
            tz = observer_location["timezone"]
            day = parse_date_param(date, tz)
            midnight_utc = to_utc_naive(local_datetime(day, 24, tz))
            ra, dec = target_radec(object_type, obj, midnight_utc)
        except McpLookupError as e:
            return e.to_payload()

        latitude, longitude = observer_location["latitude"], observer_location["longitude"]
        elevation = observer_location["elevation"]
        twilight = compute_twilight(latitude, longitude, day, tz)

        if object_type == "earth_moon":
            moon = compute_moon(latitude, longitude, day, tz)
            events = {
                "status": "ok",
                "rise": fmt_local(moon["rise"], tz),
                "transit": None,
                "set": fmt_local(moon["set"], tz),
                "transitAltitudeDeg": None,
                "illumination": moon["illumination"],
                "phaseName": moon["phaseName"],
            }
        else:
            events = rise_transit_set(observer_location, day, ra, dec, horizon_deg=horizon_deg)

        dark_window = None
        if twilight["darkFrom"] and twilight["darkTo"]:
            dark_from, dark_to = twilight["darkFrom"].replace(tzinfo=None), twilight["darkTo"].replace(tzinfo=None)
            middle = dark_from + (dark_to - dark_from) / 2
            dark_window = {
                "from": fmt_local(twilight["darkFrom"], tz),
                "to": fmt_local(twilight["darkTo"], tz),
                "darkness": twilight["darkness"],
                "altitudeAtStartDeg": altaz_at(latitude, longitude, elevation, ra, dec, dark_from)[0],
                "altitudeAtMiddleDeg": altaz_at(latitude, longitude, elevation, ra, dec, middle)[0],
                "altitudeAtEndDeg": altaz_at(latitude, longitude, elevation, ra, dec, dark_to)[0],
            }

        at_time = None
        if time:
            try:
                local_dt = _parse_local_time(time, day, tz)
            except McpLookupError as e:
                return e.to_payload()
            altitude, azimuth = altaz_at(latitude, longitude, elevation, ra, dec, to_utc_naive(local_dt))
            at_time = {"time": local_dt.isoformat(timespec="minutes"), "altitudeDeg": altitude, "azimuthDeg": azimuth}

        return {
            "found": True,
            "reason": "ok",
            "object": {
                "objectType": object_type,
                "name": target_label(object_type, obj),
                **radec_to_text(ra, dec),
                "constellation": constellation_code(ra, dec),
            },
            "date": day.isoformat(),
            "location": public_location(observer_location),
            "events": events,
            "darkWindow": dark_window,
            "atTime": at_time,
        }


def night_info_payload(
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
        try:
            observer_location = resolve_user_location(resolved_user_id, location)
            tz = observer_location["timezone"]
            day = parse_date_param(date, tz)
        except McpLookupError as e:
            return e.to_payload()

        latitude, longitude = observer_location["latitude"], observer_location["longitude"]
        twilight = compute_twilight(latitude, longitude, day, tz)
        moon = compute_moon(latitude, longitude, day, tz)
        windows = moonless_windows(twilight["darkFrom"], twilight["darkTo"], moon["upIntervals"])

        def _hours(start, end):
            return round((end - start).total_seconds() / 3600.0, 2) if start and end else 0.0

        return {
            "found": True,
            "reason": "ok",
            "date": day.isoformat(),
            "location": public_location(observer_location),
            "sun": {name: fmt_local(value, tz) for name, value in twilight["events"].items()},
            "darkness": twilight["darkness"],
            "darkWindow": {
                "from": fmt_local(twilight["darkFrom"], tz),
                "to": fmt_local(twilight["darkTo"], tz),
                "hours": _hours(twilight["darkFrom"], twilight["darkTo"]),
            } if twilight["darkFrom"] else None,
            "moon": {
                "rise": fmt_local(moon["rise"], tz),
                "set": fmt_local(moon["set"], tz),
                "phaseName": moon["phaseName"],
                "phaseDeg": moon["phaseDeg"],
                "illumination": moon["illumination"],
            },
            "moonlessDarkWindows": [
                {"from": fmt_local(start, tz), "to": fmt_local(end, tz), "hours": _hours(start, end)}
                for start, end in windows
            ],
            "moonlessDarkHours": round(sum(_hours(start, end) for start, end in windows), 2),
        }


def _session_plan_observer_location(session_plan: Any) -> dict[str, Any]:
    from app.commons.coordinates import parse_latlon
    from app.mcp.astro_common import get_location_timezone

    if session_plan.location:
        location = session_plan.location
        return {
            "locationId": location.id,
            "name": location.name,
            "latitude": float(location.latitude),
            "longitude": float(location.longitude),
            "elevation": float(location.elevation or 0.0),
            "timezone": get_location_timezone(location),
        }
    latitude, longitude = parse_latlon(session_plan.location_position)
    return {
        "locationId": None,
        "name": session_plan.location_position,
        "latitude": float(latitude),
        "longitude": float(longitude),
        "elevation": 0.0,
        "timezone": get_location_timezone(None),
    }


def _session_plan_schedule_rows(session_plan: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Plan items with local rise/transit/set for the plan's night, ordered by transit time."""
    from app.mcp.session_plan_payloads import _serialize_session_plan_item

    observer_location = _session_plan_observer_location(session_plan)
    tz = observer_location["timezone"]
    day = session_plan.for_date.date()

    rows = []
    for item in session_plan.session_plan_items:
        row = _serialize_session_plan_item(item)
        if item.get_ra() is not None and item.get_dec() is not None:
            row.update(rise_transit_set(observer_location, day, item.get_ra(), item.get_dec()))
        else:
            row.update({"status": "unknown", "rise": None, "transit": None, "set": None, "transitAltitudeDeg": None})
        rows.append(row)
    # Objects that never rise go last; ISO strings with the same offset sort chronologically.
    rows.sort(key=lambda row: (row["transit"] is None, row["transit"] or "", row["order"] or 0))

    twilight = compute_twilight(observer_location["latitude"], observer_location["longitude"], day, tz)
    window = {
        "from": fmt_local(twilight["darkFrom"], tz),
        "to": fmt_local(twilight["darkTo"], tz),
        "darkness": twilight["darkness"],
    }
    return rows, window


def session_plan_schedule_payload(
    *,
    session_plan_id: int,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app.mcp.session_plan_payloads import _load_owned_session_plan

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    app = get_app()
    with app.app_context():
        session_plan = _load_owned_session_plan(resolved_user_id, session_plan_id)
        if session_plan is None:
            return {"found": False, "reason": "session_plan_not_found", "items": []}
        rows, window = _session_plan_schedule_rows(session_plan)
        return {
            "found": True,
            "reason": "ok",
            "sessionPlanId": session_plan.id,
            "forDate": session_plan.for_date.date().isoformat() if session_plan.for_date else None,
            "darkWindow": window,
            "total": len(rows),
            "items": rows,
        }


def session_plan_export_payload(
    *,
    session_plan_id: int,
    export_format: str,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app.mcp.session_plan_payloads import _load_owned_session_plan

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)
    export_format = (export_format or "csv").strip().lower()
    if export_format not in ("csv", "oal"):
        raise ValueError("format must be csv or oal")

    app = get_app()
    with app.app_context():
        from app.models import User

        session_plan = _load_owned_session_plan(resolved_user_id, session_plan_id)
        if session_plan is None:
            return {"found": False, "reason": "session_plan_not_found"}
        file_stem = "sessionplan-" + (session_plan.title or str(session_plan.id)).replace(" ", "_")

        if export_format == "oal":
            from app.main.planner.sessionplan_export import create_oal_observations_from_session_plan

            user = User.query.filter_by(id=resolved_user_id).first()
            buf = StringIO()
            buf.write('<?xml version="1.0" encoding="utf-8"?>\n')
            with app.test_request_context("/", headers={"Host": "localhost"}):
                create_oal_observations_from_session_plan(user, session_plan).export(buf, 0)
            return {
                "found": True,
                "format": "oal",
                "fileName": file_stem + ".oal",
                "mimeType": "text/xml",
                "content": buf.getvalue(),
            }

        rows, _ = _session_plan_schedule_rows(session_plan)
        buf = StringIO()
        writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_NONNUMERIC)
        writer.writerow(["Name", "Type", "Constellation", "RA", "DEC", "Rise", "Merid", "Set"])

        def _hh_mm(value):
            return value[11:16] if value else ""

        for row in rows:
            writer.writerow([
                row["title"], row["summary"].get("classification") or row["itemType"], row["constellation"] or "",
                row["coordinates"]["ra_str"], row["coordinates"]["dec_str"],
                _hh_mm(row["rise"]), _hh_mm(row["transit"]), _hh_mm(row["set"]),
            ])
        return {
            "found": True,
            "format": "csv",
            "fileName": file_stem + ".csv",
            "mimeType": "text/csv",
            "content": buf.getvalue(),
        }
