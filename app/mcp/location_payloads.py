from __future__ import annotations

import math
from typing import Any, Callable

from app.mcp.astro_common import location_visible_to_user, serialize_location

DEFAULT_MY_LIMIT = 20
DEFAULT_SEARCH_LIMIT = 10
MAX_LIMIT = 50
DEFAULT_RADIUS_KM = 50.0
MAX_RADIUS_KM = 1000.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _visible_locations_query(resolved_user_id: int):
    from app.models import Location

    return Location.query.filter(location_visible_to_user(resolved_user_id))


def _validate_limit(limit: Any, default: int) -> int:
    if limit is None:
        return default
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValueError(f"limit must be an integer from 1 to {MAX_LIMIT}")
    return limit


def _usage_by_location(resolved_user_id: int) -> dict[int, dict[str, Any]]:
    """Number of uses and last use of each location in user's observing sessions and session plans."""
    from sqlalchemy import func

    from app import db
    from app.models import ObservingSession, SessionPlan

    usage: dict[int, dict[str, Any]] = {}
    sources = (
        (ObservingSession.location_id, ObservingSession.date_from, ObservingSession.user_id),
        (SessionPlan.location_id, SessionPlan.for_date, SessionPlan.user_id),
    )
    for location_col, date_col, user_col in sources:
        rows = (
            db.session.query(location_col, func.count(), func.max(date_col))
            .filter(user_col == resolved_user_id, location_col.is_not(None))
            .group_by(location_col)
            .all()
        )
        for location_id, count, last_used in rows:
            entry = usage.setdefault(location_id, {"useCount": 0, "lastUsed": None})
            entry["useCount"] += count
            if last_used is not None and (entry["lastUsed"] is None or last_used > entry["lastUsed"]):
                entry["lastUsed"] = last_used
    return usage


def location_find_payload(
    *,
    query: str | None,
    near: str | None,
    radius_km: float | None,
    limit: int | None,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    query = query.strip() if isinstance(query, str) else None
    near = near.strip() if isinstance(near, str) else None

    app = get_app()
    with app.app_context():
        from app.commons.coordinates import parse_latlon
        from app.models import Location

        if near:
            try:
                center_lat, center_lon = (float(v) for v in parse_latlon(near))
            except Exception:
                return {"found": False, "reason": "invalid_near", "locations": []}
            radius = DEFAULT_RADIUS_KM if radius_km is None else float(radius_km)
            if radius <= 0 or radius > MAX_RADIUS_KM:
                raise ValueError(f"radius_km must be in (0, {MAX_RADIUS_KM}]")
            max_results = _validate_limit(limit, DEFAULT_SEARCH_LIMIT)

            candidates = _visible_locations_query(resolved_user_id)
            if query:
                candidates = candidates.filter(Location.name.ilike(f"%{query}%"))
            with_distance = []
            for location in candidates.all():
                distance = _haversine_km(center_lat, center_lon, location.latitude, location.longitude)
                if distance <= radius:
                    with_distance.append((distance, location))
            with_distance.sort(key=lambda item: item[0])
            locations = []
            for distance, location in with_distance[:max_results]:
                entry = serialize_location(location)
                entry["distanceKm"] = round(distance, 1)
                locations.append(entry)
            return {
                "found": bool(locations),
                "reason": "ok" if locations else "no_locations_nearby",
                "mode": "near",
                "total": len(with_distance),
                "locations": locations,
            }

        if query:
            max_results = _validate_limit(limit, DEFAULT_SEARCH_LIMIT)
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            matches = (
                _visible_locations_query(resolved_user_id)
                .filter(Location.name.ilike(f"%{escaped}%", escape="\\"))
                .order_by(Location.name.asc())
                .limit(max_results)
                .all()
            )
            return {
                "found": bool(matches),
                "reason": "ok" if matches else "location_not_found",
                "mode": "search",
                "total": len(matches),
                "locations": [serialize_location(location) for location in matches],
            }

        # "My locations": own ones and those used in sessions/plans, most recently used first.
        max_results = _validate_limit(limit, DEFAULT_MY_LIMIT)
        usage = _usage_by_location(resolved_user_id)
        own_ids = {row.id for row in Location.query.with_entities(Location.id).filter(Location.user_id == resolved_user_id)}
        location_ids = set(usage) | own_ids
        # Locations used in the past may have been made private by their owner since then.
        rows = (
            _visible_locations_query(resolved_user_id).filter(Location.id.in_(location_ids)).all()
            if location_ids else []
        )

        def _sort_key(location):
            entry = usage.get(location.id)
            last_used = entry["lastUsed"] if entry else None
            return (last_used is not None, last_used or 0, location.id in own_ids)

        rows.sort(key=_sort_key, reverse=True)
        locations = []
        for location in rows[:max_results]:
            entry = serialize_location(location)
            entry["isOwn"] = location.id in own_ids
            entry["useCount"] = usage.get(location.id, {}).get("useCount", 0)
            last_used = usage.get(location.id, {}).get("lastUsed")
            entry["lastUsed"] = last_used.date().isoformat() if last_used else None
            locations.append(entry)
        return {
            "found": bool(locations),
            "reason": "ok" if locations else "no_user_locations",
            "mode": "mine",
            "total": len(rows),
            "locations": locations,
        }
