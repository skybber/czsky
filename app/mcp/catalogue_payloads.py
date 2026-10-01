"""Observed objects, DSO list progress and double star search for MCP tools."""

from __future__ import annotations

import math
from typing import Any, Callable

from app.mcp.astro_common import (
    McpLookupError,
    parse_date_param,
    public_location,
    radec_to_text,
    resolve_user_location,
    rise_transit_set,
)

MAX_LIST_LIMIT = 200
OBSERVED_TYPE_NAMES = {
    "DSO": "dso",
    "DBL_STAR": "double_star",
    "COMET": "comet",
    "M_PLANET": "minor_planet",
}


def _validate_limit(limit: Any, maximum: int = MAX_LIST_LIMIT) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > maximum:
        raise ValueError(f"limit must be an integer from 1 to {maximum}")
    return limit


def _validate_offset(offset: Any) -> int:
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    return offset


def _round(value: Any, digits: int = 1) -> float | None:
    return round(float(value), digits) if value is not None else None


def _constellation_iau(constellation_id: int | None) -> str | None:
    from app.models import Constellation

    constellation = Constellation.get_constellation_by_id(constellation_id) if constellation_id else None
    return constellation.iau_code if constellation else None


def _observed_dso_ids_subquery(resolved_user_id: int):
    from app import db
    from app.models import ObservedList, ObservedListItem

    return (
        db.session.query(ObservedListItem.dso_id)
        .join(ObservedList, ObservedListItem.observed_list_id == ObservedList.id)
        .filter(ObservedList.user_id == resolved_user_id, ObservedListItem.dso_id.is_not(None))
    )


def _serialize_observed_item(item: Any) -> dict[str, Any]:
    object_type = OBSERVED_TYPE_NAMES.get(item.target_type.value if item.target_type else "", None)
    entry: dict[str, Any] = {
        "observedItemId": item.id,
        "objectType": object_type,
        "addedAt": item.create_date.date().isoformat() if item.create_date else None,
        "notes": item.notes,
    }
    if item.deepsky_object is not None:
        dso = item.deepsky_object
        entry.update({
            "objectId": f"dso:{dso.id}",
            "name": dso.denormalized_name(),
            "type": dso.type,
            "magnitude": _round(dso.mag),
            "constellation": _constellation_iau(dso.constellation_id),
        })
    elif item.double_star is not None:
        double_star = item.double_star
        entry.update({
            "objectId": f"double_star:{double_star.id}",
            "name": double_star.get_catalog_name(),
            "type": "double_star",
            "magnitude": _round(double_star.mag_first),
            "constellation": _constellation_iau(double_star.constellation_id),
        })
    elif item.comet is not None:
        entry.update({"objectId": f"comet:{item.comet.id}", "name": item.comet.designation, "type": "comet"})
    elif item.minor_planet is not None:
        minor_planet = item.minor_planet
        entry.update({
            "objectId": f"minor_planet:{minor_planet.id}",
            "name": minor_planet.designation or str(minor_planet.int_designation),
            "type": "minor_planet",
        })
    return entry


def observed_list_payload(
    *,
    object_types: list[str] | None,
    limit: int,
    offset: int,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)
    limit = _validate_limit(limit)
    offset = _validate_offset(offset)

    type_filter = None
    if object_types:
        reverse = {value: key for key, value in OBSERVED_TYPE_NAMES.items()}
        unknown = [value for value in object_types if value not in reverse]
        if unknown:
            raise ValueError(f"object_types must be from: {', '.join(reverse)}")
        type_filter = [reverse[value] for value in object_types]

    app = get_app()
    with app.app_context():
        from app.models import ObservedList, ObservedListItem, ObservedTargetType

        items = (
            ObservedListItem.query
            .join(ObservedList, ObservedListItem.observed_list_id == ObservedList.id)
            .filter(ObservedList.user_id == resolved_user_id)
        )
        if type_filter:
            items = items.filter(ObservedListItem.target_type.in_([ObservedTargetType(value) for value in type_filter]))
        total = items.count()
        rows = (
            items.order_by(ObservedListItem.create_date.desc(), ObservedListItem.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "found": total > 0,
            "reason": "ok" if total else "no_observed_objects",
            "total": total,
            "offset": offset,
            "nextOffset": offset + len(rows) if offset + len(rows) < total else None,
            "items": [_serialize_observed_item(row) for row in rows],
        }


def observed_stats_payload(
    *,
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
        from sqlalchemy import func

        from app import db
        from app.models import DeepskyObject, Observation, ObservedList, ObservedListItem, ObservingSession

        by_target = dict(
            db.session.query(ObservedListItem.target_type, func.count(ObservedListItem.id))
            .join(ObservedList, ObservedListItem.observed_list_id == ObservedList.id)
            .filter(ObservedList.user_id == resolved_user_id)
            .group_by(ObservedListItem.target_type)
            .all()
        )
        by_dso_type = dict(
            db.session.query(DeepskyObject.type, func.count(ObservedListItem.id))
            .join(ObservedListItem, ObservedListItem.dso_id == DeepskyObject.id)
            .join(ObservedList, ObservedListItem.observed_list_id == ObservedList.id)
            .filter(ObservedList.user_id == resolved_user_id)
            .group_by(DeepskyObject.type)
            .all()
        )
        session_count, first_session, last_session = (
            db.session.query(
                func.count(ObservingSession.id), func.min(ObservingSession.date_from), func.max(ObservingSession.date_from),
            )
            .filter(ObservingSession.user_id == resolved_user_id)
            .one()
        )
        observation_count = Observation.query.filter(Observation.user_id == resolved_user_id).count()

        observed_by_type = {
            OBSERVED_TYPE_NAMES.get(target_type.value if target_type else "", "other"): count
            for target_type, count in by_target.items()
        }
        return {
            "observedObjects": {
                "total": sum(by_target.values()),
                "byObjectType": observed_by_type,
                "dsoByType": {dso_type or "unknown": count for dso_type, count in by_dso_type.items()},
            },
            "observingSessions": {
                "total": session_count,
                "first": first_session.date().isoformat() if first_session else None,
                "last": last_session.date().isoformat() if last_session else None,
            },
            "observationLogEntries": observation_count,
        }


def dso_list_progress_payload(
    *,
    dso_list: int | str,
    include_missing: bool,
    missing_limit: int,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app.mcp.session_plan_payloads import dso_list_get_id_by_name_payload

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)
    missing_limit = _validate_limit(missing_limit)

    if isinstance(dso_list, int) and not isinstance(dso_list, bool):
        dso_list_id = dso_list
    elif isinstance(dso_list, str) and dso_list.strip().isdigit():
        dso_list_id = int(dso_list.strip())
    else:
        lookup = dso_list_get_id_by_name_payload(
            name=dso_list,
            user_id=resolved_user_id,
            require_scope_if_available_func=lambda _scope: None,
            required_scope=required_scope,
            resolve_mcp_user_id_func=lambda _user_id: resolved_user_id,
            get_app=get_app,
        )
        if not lookup["found"]:
            return {"found": False, "reason": f"dso_list_{lookup['reason']}", "candidates": lookup["candidates"]}
        dso_list_id = lookup["dsoListId"]

    app = get_app()
    with app.app_context():
        from app.models import DsoList

        dso_list_row = DsoList.query.filter_by(id=dso_list_id).first()
        if dso_list_row is None or dso_list_row.hidden:
            return {"found": False, "reason": "dso_list_not_found"}

        observed_ids = {row[0] for row in _observed_dso_ids_subquery(resolved_user_id).all()}
        items = sorted(dso_list_row.dso_list_items, key=lambda item: item.item_id)
        observed_items, missing_items = [], []
        for item in items:
            dso = item.deepsky_object
            is_observed = dso.id in observed_ids or (dso.master_id is not None and dso.master_id in observed_ids)
            (observed_items if is_observed else missing_items).append(item)

        total = len(items)
        result = {
            "found": True,
            "reason": "ok",
            "dsoList": {"dsoListId": dso_list_row.id, "name": dso_list_row.name, "longName": dso_list_row.long_name},
            "total": total,
            "observed": len(observed_items),
            "missing": len(missing_items),
            "percent": round(100.0 * len(observed_items) / total, 1) if total else 0.0,
        }
        if include_missing:
            result["missingObjects"] = [
                {
                    "itemNumber": item.item_id,
                    "objectId": f"dso:{item.deepsky_object.id}",
                    "name": item.deepsky_object.denormalized_name(),
                    "type": item.deepsky_object.type,
                    "magnitude": _round(item.deepsky_object.mag),
                    "constellation": _constellation_iau(item.deepsky_object.constellation_id),
                }
                for item in missing_items[:missing_limit]
            ]
            result["missingTruncated"] = len(missing_items) > missing_limit
        return result


def double_star_find_payload(
    *,
    constellation: str | None,
    mag_max: float | None,
    delta_mag_max: float | None,
    separation_min: float | None,
    separation_max: float | None,
    min_dec: float | None,
    not_observed: bool,
    location: Any,
    date: str | None,
    limit: int,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app.mcp.dso_payloads import _resolve_constellation_id

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)
    limit = _validate_limit(limit, 50)

    app = get_app()
    with app.app_context():
        from app import db
        from app.models import DoubleStar, ObservedList, ObservedListItem

        observer_location = day = None
        if location is not None and not (isinstance(location, str) and not location.strip()):
            try:
                observer_location = resolve_user_location(resolved_user_id, location)
                day = parse_date_param(date, observer_location["timezone"])
            except McpLookupError as e:
                return e.to_payload()

        double_stars = DoubleStar.query
        if constellation:
            constellation_id = _resolve_constellation_id(constellation)
            if constellation_id is None:
                return {"found": False, "reason": "constellation_not_found", "doubleStars": []}
            double_stars = double_stars.filter(DoubleStar.constellation_id == constellation_id)
        if mag_max is not None:
            double_stars = double_stars.filter(DoubleStar.mag_first < mag_max, DoubleStar.mag_second < mag_max)
        if delta_mag_max is not None:
            double_stars = double_stars.filter(DoubleStar.delta_mag < delta_mag_max)
        if separation_min is not None:
            double_stars = double_stars.filter(DoubleStar.separation > separation_min)
        if separation_max is not None:
            double_stars = double_stars.filter(DoubleStar.separation < separation_max)
        if min_dec is not None:
            double_stars = double_stars.filter(DoubleStar.dec_first > math.radians(min_dec))
        if not_observed:
            observed_subquery = (
                db.session.query(ObservedListItem.double_star_id)
                .join(ObservedList, ObservedListItem.observed_list_id == ObservedList.id)
                .filter(ObservedList.user_id == resolved_user_id, ObservedListItem.double_star_id.is_not(None))
            )
            double_stars = double_stars.filter(DoubleStar.id.notin_(observed_subquery))

        rows = double_stars.order_by(DoubleStar.mag_first.asc().nullslast()).limit(limit).all()
        results = []
        for double_star in rows:
            entry = {
                "objectId": f"double_star:{double_star.id}",
                "name": double_star.get_catalog_name(),
                "commonName": double_star.get_common_norm_name(),
                "wds": double_star.wds_number,
                "components": double_star.components,
                "magFirst": _round(double_star.mag_first, 2),
                "magSecond": _round(double_star.mag_second, 2),
                "deltaMag": _round(double_star.delta_mag, 2),
                "separationArcsec": _round(double_star.separation, 2),
                "positionAngleDeg": double_star.pos_angle,
                "spectralType": double_star.spectral_type,
                "constellation": _constellation_iau(double_star.constellation_id),
                **radec_to_text(double_star.ra_first, double_star.dec_first),
            }
            if observer_location is not None:
                entry["visibility"] = rise_transit_set(
                    observer_location, day, double_star.ra_first, double_star.dec_first,
                )
            results.append(entry)

        return {
            "found": bool(results),
            "reason": "ok" if results else "no_matching_double_stars",
            "visibilityFor": {"date": day.isoformat(), "location": public_location(observer_location)}
            if observer_location else None,
            "total": len(results),
            "doubleStars": results,
        }
