from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any, Callable


def _to_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def parse_for_date(for_date: Any) -> datetime:
    if isinstance(for_date, datetime):
        if for_date.tzinfo is not None:
            return for_date.astimezone(timezone.utc).replace(tzinfo=None)
        return for_date

    if isinstance(for_date, date):
        return datetime.combine(for_date, time.min)

    if not isinstance(for_date, str):
        raise ValueError("for_date must be a datetime/date string")

    stripped = for_date.strip()
    if not stripped:
        raise ValueError("for_date must not be empty")

    normalized = stripped.replace("Z", "+00:00") if stripped.endswith("Z") else stripped
    try:
        parsed_datetime = datetime.fromisoformat(normalized)
    except ValueError:
        parsed_datetime = None

    if parsed_datetime is not None:
        if parsed_datetime.tzinfo is not None:
            return parsed_datetime.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed_datetime

    for date_format in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed_date = datetime.strptime(stripped, date_format).date()
            return datetime.combine(parsed_date, time.min)
        except ValueError:
            continue

    raise ValueError("Unsupported for_date format; use ISO datetime/date or DD/MM/YYYY")


def parse_location_id(location_id: Any) -> int | None:
    if location_id is None:
        return None

    if isinstance(location_id, bool):
        raise ValueError("location_id must be a positive integer")

    if isinstance(location_id, int):
        if location_id <= 0:
            raise ValueError("location_id must be a positive integer")
        return location_id

    if isinstance(location_id, str):
        stripped = location_id.strip()
        if not stripped:
            return None
        if not stripped.isdigit():
            raise ValueError("location_id must be a positive integer")
        parsed_id = int(stripped)
        if parsed_id <= 0:
            raise ValueError("location_id must be a positive integer")
        return parsed_id

    raise ValueError("location_id must be a positive integer")


def parse_location_name(location_name: Any) -> str | None:
    if location_name is None:
        return None

    if not isinstance(location_name, str):
        raise ValueError("location_name must be a string")

    stripped = location_name.strip()
    if not stripped:
        return None

    if len(stripped) > 128:
        raise ValueError("location_name must be at most 128 characters")

    return stripped


def parse_location_fallback(location: Any) -> tuple[int | None, str | None]:
    if location is None:
        return None, None

    if isinstance(location, int):
        parsed_location_id = parse_location_id(location)
        return parsed_location_id, None

    if not isinstance(location, str):
        raise ValueError("location must be a string or integer id")

    stripped = location.strip()
    if not stripped:
        return None, None

    if stripped.isdigit():
        parsed_location_id = parse_location_id(stripped)
        return parsed_location_id, None

    if len(stripped) > 256:
        raise ValueError("location text must be at most 256 characters")

    return None, stripped


def _serialize_location_row(location: Any) -> dict[str, Any]:
    return {
        "locationId": location.id,
        "locationName": location.name,
    }


def _resolve_location_for_session_plan_create(
    *,
    resolved_user_id: int,
    location_id: Any,
    location_name: Any,
    location: Any,
) -> tuple[int | None, str | None, str | None, list[dict[str, Any]]]:
    from sqlalchemy import and_, func, or_

    from app.models import Location

    parsed_location_id = parse_location_id(location_id)
    parsed_location_name = parse_location_name(location_name)

    if parsed_location_id is not None:
        resolved_location = (
            Location.query
            .filter(Location.id == parsed_location_id)
            .filter(
                or_(
                    Location.user_id == resolved_user_id,
                    and_(Location.is_public.is_(True), Location.is_for_observation.is_(True)),
                )
            )
            .first()
        )
        if resolved_location is None:
            return None, None, "location_not_found", []
        return resolved_location.id, None, None, []

    if parsed_location_name is not None:
        exact_matches = (
            Location.query
            .filter(func.lower(Location.name) == parsed_location_name.casefold())
            .filter(
                or_(
                    Location.user_id == resolved_user_id,
                    and_(Location.is_public.is_(True), Location.is_for_observation.is_(True)),
                )
            )
            .order_by(Location.id.asc())
            .all()
        )
        if len(exact_matches) == 1:
            return exact_matches[0].id, None, None, []
        if len(exact_matches) > 1:
            return None, None, "location_ambiguous", [
                _serialize_location_row(match) for match in exact_matches[:10]
            ]

        escaped_name = parsed_location_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        similar_matches = (
            Location.query
            .filter(Location.name.ilike(f"%{escaped_name}%", escape="\\"))
            .filter(
                or_(
                    Location.user_id == resolved_user_id,
                    and_(Location.is_public.is_(True), Location.is_for_observation.is_(True)),
                )
            )
            .order_by(Location.id.asc())
            .limit(10)
            .all()
        )
        if similar_matches:
            return None, None, "location_ambiguous", [
                _serialize_location_row(match) for match in similar_matches
            ]
        return None, None, "location_not_found", []

    fallback_location_id, fallback_location_position = parse_location_fallback(location)
    if fallback_location_id is not None:
        resolved_location = (
            Location.query
            .filter(Location.id == fallback_location_id)
            .filter(
                or_(
                    Location.user_id == resolved_user_id,
                    and_(Location.is_public.is_(True), Location.is_for_observation.is_(True)),
                )
            )
            .first()
        )
        if resolved_location is None:
            return None, None, "location_not_found", []
        return resolved_location.id, None, None, []

    if fallback_location_position is not None:
        return None, fallback_location_position, None, []

    raise ValueError("Provide location_id or location_name")


def _resolve_session_plan_target(
    *,
    app: Any,
    query: str,
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
):
    stripped_query = (query or "").strip()
    if not stripped_query:
        raise ValueError("query must not be empty")

    with app.test_request_context("/", headers={"Host": "localhost"}):
        resolved = resolve_global_object_func(stripped_query)

    if not resolved:
        return None, "not_found"

    object_type = resolved.get("object_type")
    if object_type not in {"dso", "double_star", "comet", "minor_planet", "planet"}:
        return None, "unsupported_object_type"

    target_object = resolved.get("object")
    target_id = getattr(target_object, "id", None)
    if not isinstance(target_id, int) or target_id <= 0:
        return None, "not_found"

    return {
        "query": stripped_query,
        "objectType": object_type,
        "targetObject": target_object,
        "targetId": target_id,
        "objectId": f"{object_type}:{target_id}",
    }, None


def _load_owned_active_session_plan(resolved_user_id: int, session_plan_id: int):
    from app.models import SessionPlan

    return (
        SessionPlan.query
        .filter_by(id=session_plan_id, user_id=resolved_user_id, is_archived=False)
        .first()
    )


def _load_owned_session_plan(resolved_user_id: int, session_plan_id: int):
    from app.models import SessionPlan

    return (
        SessionPlan.query
        .filter_by(id=session_plan_id, user_id=resolved_user_id)
        .first()
    )


def _serialize_session_plan_location(session_plan: Any) -> dict[str, Any]:
    location_name = session_plan.location.name if session_plan.location else None
    return {
        "locationId": session_plan.location_id,
        "locationName": location_name,
        "locationPosition": session_plan.location_position,
    }


def _serialize_session_plan_item(item: Any) -> dict[str, Any]:
    from app.models import Constellation

    object_type = None
    object_id = None
    title = None
    identifier = None
    summary = {}
    coordinates = {
        "ra": item.get_ra(),
        "dec": item.get_dec(),
        "ra_str": item.get_ra_str_short(),
        "dec_str": item.get_dec_str_short(),
    }

    if item.deepsky_object is not None:
        dso = item.deepsky_object
        object_type = "dso"
        object_id = f"dso:{dso.id}"
        title = dso.denormalized_name()
        identifier = dso.name
        summary = {
            "classification": dso.type,
            "magnitude": dso.mag,
        }
        constell = Constellation.get_constellation_by_id(dso.constellation_id) if dso.constellation_id else None
    elif item.double_star is not None:
        double_star = item.double_star
        object_type = "double_star"
        object_id = f"double_star:{double_star.id}"
        title = double_star.get_catalog_name()
        identifier = double_star.common_cat_id or double_star.wds_number
        summary = {
            "classification": "double_star",
            "separation": double_star.separation,
        }
        constell = Constellation.get_constellation_by_id(double_star.constellation_id) if double_star.constellation_id else None
    elif item.comet is not None:
        comet = item.comet
        object_type = "comet"
        object_id = f"comet:{comet.id}"
        title = comet.designation
        identifier = comet.comet_id
        summary = {
            "classification": "comet",
            "magnitude": comet.real_mag if comet.real_mag is not None else comet.eval_mag,
        }
        constell = Constellation.get_constellation_by_id(item.constell_id) if item.constell_id else comet.cur_constell()
    elif item.minor_planet is not None:
        minor_planet = item.minor_planet
        object_type = "minor_planet"
        object_id = f"minor_planet:{minor_planet.id}"
        title = minor_planet.designation or str(minor_planet.int_designation)
        identifier = str(minor_planet.int_designation)
        summary = {
            "classification": "minor_planet",
            "magnitude": minor_planet.eval_mag,
        }
        constell = Constellation.get_constellation_by_id(item.constell_id) if item.constell_id else minor_planet.cur_constell()
    elif item.planet is not None:
        planet = item.planet
        object_type = "planet"
        object_id = f"planet:{planet.id}"
        title = planet.get_localized_name()
        identifier = planet.iau_code
        summary = {
            "classification": "planet",
        }
        constell = Constellation.get_constellation_by_id(item.constell_id) if item.constell_id else None
    else:
        constell = Constellation.get_constellation_by_id(item.constell_id) if item.constell_id else None

    return {
        "sessionPlanItemId": item.id,
        "order": item.order,
        "itemType": object_type,
        "objectId": object_id,
        "title": title,
        "identifier": identifier,
        "coordinates": coordinates,
        "summary": summary,
        "constellation": constell.iau_code if constell else None,
        "constellationName": constell.name if constell else None,
    }


def _get_session_plan_astronomical_night(session_plan: Any) -> dict[str, Any]:
    try:
        from app.mcp.dso_payloads import _build_observer_tzinfo, _get_twilight_window

        _observer, tz_info, latitude, longitude = _build_observer_tzinfo(session_plan)
        time_from, time_to = _get_twilight_window(session_plan, latitude, longitude, tz_info)
        return {
            "astronomicalNightStart": _to_iso(time_from),
            "astronomicalNightEnd": _to_iso(time_to),
        }
    except Exception:
        return {
            "astronomicalNightStart": None,
            "astronomicalNightEnd": None,
        }


def _serialize_session_plan_summary(session_plan: Any) -> dict[str, Any]:
    return {
        "sessionPlanId": session_plan.id,
        "title": session_plan.title,
        "forDate": _to_iso(session_plan.for_date),
        "isArchived": bool(session_plan.is_archived),
        "isPublic": bool(session_plan.is_public),
        "isAnonymous": bool(session_plan.is_anonymous),
        **_serialize_session_plan_location(session_plan),
        **_get_session_plan_astronomical_night(session_plan),
    }


def _serialize_session_plan(session_plan: Any, items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sorted_items = items
    if sorted_items is None:
        sorted_items = [
            _serialize_session_plan_item(item)
            for item in sorted(session_plan.session_plan_items, key=lambda current: ((current.order or 0), current.id or 0))
        ]

    return {
        **_serialize_session_plan_summary(session_plan),
        "itemCount": len(sorted_items),
        "items": sorted_items,
    }


def _parse_session_plan_object_types(object_types: Any) -> set[str] | None:
    if object_types is None:
        return None
    if not isinstance(object_types, list):
        raise ValueError("object_types must be a list of strings")

    valid = {"dso", "double_star", "comet", "minor_planet", "planet"}
    parsed = set()
    for value in object_types:
        if not isinstance(value, str):
            raise ValueError("object_types must be a list of strings")
        normalized = value.strip().lower()
        if normalized not in valid:
            raise ValueError("object_types contains unsupported value")
        parsed.add(normalized)
    return parsed


def _find_session_plan_item(session_plan: Any, object_type: str, target_id: int):
    if object_type == "dso":
        return session_plan.find_dso_item_by_id(target_id)
    if object_type == "double_star":
        return session_plan.find_double_star_item_by_id(target_id)
    if object_type == "comet":
        return session_plan.find_comet_item_by_id(target_id)
    if object_type == "minor_planet":
        return session_plan.find_minor_planet_item_by_id(target_id)
    if object_type == "planet":
        return session_plan.find_planet_item_by_id(target_id)
    return None


def _create_session_plan_item(session_plan: Any, target: dict[str, Any]):
    from app.models import Constellation
    from app.commons.comet_utils import find_mpc_comet, get_mpc_comet_position
    from app.commons.minor_planet_utils import find_mpc_minor_planet, get_mpc_minor_planet_position
    from app.commons.solar_system_chart_utils import get_mpc_planet_position

    object_type = target["objectType"]
    target_object = target["targetObject"]

    if object_type == "dso":
        return session_plan.create_new_deepsky_object_item(target["targetId"]), None

    if object_type == "double_star":
        return session_plan.create_new_double_star_item(target["targetId"]), None

    if object_type == "comet":
        try:
            comet_for_position = find_mpc_comet(target_object.comet_id)
            comet_ra, comet_dec = get_mpc_comet_position(comet_for_position, session_plan.for_date)
        except Exception:
            return None, "ephemeris_unavailable"

        constell = Constellation.get_constellation_by_position(comet_ra.radians, comet_dec.radians)
        return (
            session_plan.create_new_comet_item(
                target_object,
                comet_ra.radians,
                comet_dec.radians,
                constell,
            ),
            None,
        )

    if object_type == "minor_planet":
        try:
            minor_planet_for_position = find_mpc_minor_planet(target_object.int_designation)
            mplanet_ra, mplanet_dec = get_mpc_minor_planet_position(
                minor_planet_for_position,
                session_plan.for_date,
            )
        except Exception:
            return None, "ephemeris_unavailable"

        constell = Constellation.get_constellation_by_position(mplanet_ra.radians, mplanet_dec.radians)
        return (
            session_plan.create_new_minor_planet_item(
                target_object,
                mplanet_ra.radians,
                mplanet_dec.radians,
                constell,
            ),
            None,
        )

    if object_type == "planet":
        try:
            planet_ra, planet_dec = get_mpc_planet_position(target_object, session_plan.for_date)
        except Exception:
            return None, "ephemeris_unavailable"

        constell = Constellation.get_constellation_by_position(planet_ra.radians, planet_dec.radians)
        return (
            session_plan.create_new_planet_item(
                target_object,
                planet_ra.radians,
                planet_dec.radians,
                constell,
            ),
            None,
        )

    return None, "unsupported_object_type"


def _safe_reorder_session_plan(session_plan: Any) -> None:
    try:
        from app.main.planner.session_scheduler import reorder_by_merid_time

        reorder_by_merid_time(session_plan)
    except Exception:
        # Reordering is best-effort and should not invalidate a successful mutation.
        return


def session_plan_create_payload(
    *,
    for_date: Any,
    location_id: Any,
    location_name: Any,
    location: Any,
    title: str | None,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app import db
    from app.models import SessionPlan

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    parsed_for_date = parse_for_date(for_date)
    normalized_title = ((title or "").strip() or "Unknown")[:128]

    app = get_app()
    with app.app_context():
        resolved_location_id, resolved_location_position, reason, candidates = (
            _resolve_location_for_session_plan_create(
                resolved_user_id=resolved_user_id,
                location_id=location_id,
                location_name=location_name,
                location=location,
            )
        )
        if reason is not None:
            return {
                "created": False,
                "reason": reason,
                "sessionPlanId": None,
                "title": normalized_title,
                "forDate": _to_iso(parsed_for_date),
                "locationId": None,
                "locationPosition": None,
                "candidates": candidates,
                "isPublic": False,
                "isAnonymous": False,
            }

        new_session_plan = SessionPlan(
            user_id=resolved_user_id,
            title=normalized_title,
            for_date=parsed_for_date,
            location_id=resolved_location_id,
            location_position=resolved_location_position,
            is_public=False,
            is_anonymous=False,
            is_archived=False,
            notes=None,
            create_by=resolved_user_id,
            update_by=resolved_user_id,
            create_date=datetime.now(),
            update_date=datetime.now(),
        )

        db.session.add(new_session_plan)
        db.session.commit()

        return {
            "created": True,
            "reason": "created",
            "sessionPlanId": new_session_plan.id,
            "title": new_session_plan.title,
            "forDate": _to_iso(new_session_plan.for_date),
            "locationId": new_session_plan.location_id,
            "locationPosition": new_session_plan.location_position,
            "candidates": [],
            "isPublic": bool(new_session_plan.is_public),
            "isAnonymous": bool(new_session_plan.is_anonymous),
        }


def session_plan_get_payload(
    *,
    session_plan_id: int,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    if isinstance(session_plan_id, bool) or not isinstance(session_plan_id, int) or session_plan_id <= 0:
        raise ValueError("session_plan_id must be a positive integer")

    app = get_app()
    with app.app_context():
        session_plan = _load_owned_session_plan(resolved_user_id, session_plan_id)
        if session_plan is None:
            return {
                "found": False,
                "reason": "session_plan_not_found",
                "sessionPlan": None,
            }

        return {
            "found": True,
            "reason": "found",
            "sessionPlan": _serialize_session_plan(session_plan),
        }


def session_plan_list_payload(
    *,
    for_date: Any,
    include_archived: bool,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app import db
    from app.models import SessionPlan

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    parsed_for_date = parse_for_date(for_date).date() if for_date is not None else None

    app = get_app()
    with app.app_context():
        query = SessionPlan.query.filter(SessionPlan.user_id == resolved_user_id)
        if not include_archived:
            query = query.filter(SessionPlan.is_archived.is_(False))
        if parsed_for_date is not None:
            query = query.filter(db.func.date(SessionPlan.for_date) == parsed_for_date)

        session_plans = query.order_by(SessionPlan.for_date.desc(), SessionPlan.id.desc()).all()
        items = [
            {
                **_serialize_session_plan_summary(session_plan),
                "itemCount": len(session_plan.session_plan_items),
            }
            for session_plan in session_plans
        ]

        return {
            "total": len(items),
            "sessionPlans": items,
        }


def session_plan_get_id_by_date_payload(
    *,
    for_date: Any,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app import db
    from app.models import SessionPlan

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    parsed_for_date = parse_for_date(for_date)
    target_date = parsed_for_date.date()

    app = get_app()
    with app.app_context():
        session_plans = (
            SessionPlan.query
            .filter(SessionPlan.user_id == resolved_user_id)
            .filter(SessionPlan.is_archived.is_(False))
            .filter(db.func.date(SessionPlan.for_date) == target_date)
            .order_by(SessionPlan.for_date.desc(), SessionPlan.id.desc())
            .all()
        )

        if not session_plans:
            return {
                "found": False,
                "forDate": parsed_for_date.date().isoformat(),
                "sessionPlanId": None,
                "sessionPlanIds": [],
                "total": 0,
            }

        ids = [session_plan.id for session_plan in session_plans]
        return {
            "found": True,
            "forDate": parsed_for_date.date().isoformat(),
            "sessionPlanId": ids[0],
            "sessionPlanIds": ids,
            "total": len(ids),
        }


def session_plan_items_payload(
    *,
    session_plan_id: int,
    object_types: Any,
    dso_list_id: Any,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app.models import DsoList, DsoListItem

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    if isinstance(session_plan_id, bool) or not isinstance(session_plan_id, int) or session_plan_id <= 0:
        raise ValueError("session_plan_id must be a positive integer")

    parsed_object_types = _parse_session_plan_object_types(object_types)
    parsed_dso_list_id = parse_location_id(dso_list_id)

    app = get_app()
    with app.app_context():
        session_plan = _load_owned_session_plan(resolved_user_id, session_plan_id)
        if session_plan is None:
            return {
                "found": False,
                "reason": "session_plan_not_found",
                "sessionPlanId": session_plan_id,
                "items": [],
                "total": 0,
            }

        dso_ids_in_list = None
        if parsed_dso_list_id is not None:
            dso_list = DsoList.query.filter_by(id=parsed_dso_list_id, hidden=False).first()
            if dso_list is None:
                return {
                    "found": False,
                    "reason": "dso_list_not_found",
                    "sessionPlanId": session_plan_id,
                    "items": [],
                    "total": 0,
                }
            dso_ids_in_list = {
                dso_id
                for (dso_id,) in DsoListItem.query
                .filter(DsoListItem.dso_list_id == parsed_dso_list_id)
                .with_entities(DsoListItem.dso_id)
                .all()
            }

        items = []
        for item in sorted(session_plan.session_plan_items, key=lambda current: ((current.order or 0), current.id or 0)):
            serialized = _serialize_session_plan_item(item)
            if parsed_object_types is not None and serialized["itemType"] not in parsed_object_types:
                continue
            if dso_ids_in_list is not None and (item.dso_id is None or item.dso_id not in dso_ids_in_list):
                continue
            items.append(serialized)

        return {
            "found": True,
            "reason": "found",
            "sessionPlanId": session_plan_id,
            "items": items,
            "total": len(items),
        }


def session_plan_add_item_payload(
    *,
    session_plan_id: int,
    query: str,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
) -> dict[str, Any]:
    from app import db

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    if isinstance(session_plan_id, bool) or not isinstance(session_plan_id, int) or session_plan_id <= 0:
        raise ValueError("session_plan_id must be a positive integer")

    app = get_app()
    with app.app_context():
        session_plan = _load_owned_active_session_plan(resolved_user_id, session_plan_id)
        if session_plan is None:
            return {
                "added": False,
                "reason": "session_plan_not_found",
                "sessionPlanId": session_plan_id,
                "sessionPlanItemId": None,
                "objectId": None,
            }

        target, reason = _resolve_session_plan_target(
            app=app,
            query=query,
            resolve_global_object_func=resolve_global_object_func,
        )
        if target is None:
            return {
                "added": False,
                "reason": reason,
                "sessionPlanId": session_plan_id,
                "sessionPlanItemId": None,
                "objectId": None,
            }

        existing_item = _find_session_plan_item(
            session_plan,
            target["objectType"],
            target["targetId"],
        )
        if existing_item is not None:
            return {
                "added": False,
                "reason": "already_exists",
                "sessionPlanId": session_plan_id,
                "sessionPlanItemId": existing_item.id,
                "objectId": target["objectId"],
            }

        new_item, create_reason = _create_session_plan_item(session_plan, target)
        if new_item is None:
            return {
                "added": False,
                "reason": create_reason or "cannot_create_item",
                "sessionPlanId": session_plan_id,
                "sessionPlanItemId": None,
                "objectId": target["objectId"],
            }

        db.session.add(new_item)
        db.session.commit()
        _safe_reorder_session_plan(session_plan)

        return {
            "added": True,
            "reason": "added",
            "sessionPlanId": session_plan_id,
            "sessionPlanItemId": new_item.id,
            "objectId": target["objectId"],
        }


def session_plan_add_items_payload(
    *,
    session_plan_id: int,
    queries: Any,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
) -> dict[str, Any]:
    from app import db

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    if isinstance(session_plan_id, bool) or not isinstance(session_plan_id, int) or session_plan_id <= 0:
        raise ValueError("session_plan_id must be a positive integer")

    if not isinstance(queries, list):
        raise ValueError("queries must be a list of object names")
    if not queries:
        raise ValueError("queries must not be empty")
    if len(queries) > 100:
        raise ValueError("queries must contain at most 100 items")

    app = get_app()
    with app.app_context():
        session_plan = _load_owned_active_session_plan(resolved_user_id, session_plan_id)
        if session_plan is None:
            return {
                "sessionPlanId": session_plan_id,
                "addedCount": 0,
                "results": [
                    {
                        "query": query,
                        "added": False,
                        "reason": "session_plan_not_found",
                        "sessionPlanItemId": None,
                        "objectId": None,
                    }
                    for query in queries
                ],
            }

        results = []
        added_items = []

        for query in queries:
            if not isinstance(query, str):
                results.append({
                    "query": query,
                    "added": False,
                    "reason": "invalid_query",
                    "sessionPlanItemId": None,
                    "objectId": None,
                })
                continue

            target, reason = _resolve_session_plan_target(
                app=app,
                query=query,
                resolve_global_object_func=resolve_global_object_func,
            )
            if target is None:
                results.append({
                    "query": query,
                    "added": False,
                    "reason": reason,
                    "sessionPlanItemId": None,
                    "objectId": None,
                })
                continue

            existing_item = _find_session_plan_item(
                session_plan,
                target["objectType"],
                target["targetId"],
            )
            if existing_item is not None:
                results.append({
                    "query": target["query"],
                    "added": False,
                    "reason": "already_exists",
                    "sessionPlanItemId": existing_item.id,
                    "objectId": target["objectId"],
                })
                continue

            new_item, create_reason = _create_session_plan_item(session_plan, target)
            if new_item is None:
                results.append({
                    "query": target["query"],
                    "added": False,
                    "reason": create_reason or "cannot_create_item",
                    "sessionPlanItemId": None,
                    "objectId": target["objectId"],
                })
                continue

            db.session.add(new_item)
            added_items.append(new_item)
            results.append({
                "query": target["query"],
                "added": True,
                "reason": "added",
                "sessionPlanItemId": new_item.id,
                "objectId": target["objectId"],
            })

        if added_items:
            db.session.commit()
            _safe_reorder_session_plan(session_plan)

        return {
            "sessionPlanId": session_plan_id,
            "addedCount": len(added_items),
            "results": results,
        }


def session_plan_remove_items_payload(
    *,
    session_plan_id: int,
    queries: Any,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
) -> dict[str, Any]:
    from app import db

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    if isinstance(session_plan_id, bool) or not isinstance(session_plan_id, int) or session_plan_id <= 0:
        raise ValueError("session_plan_id must be a positive integer")

    if not isinstance(queries, list):
        raise ValueError("queries must be a list of object names")
    if not queries:
        raise ValueError("queries must not be empty")
    if len(queries) > 100:
        raise ValueError("queries must contain at most 100 items")

    app = get_app()
    with app.app_context():
        session_plan = _load_owned_active_session_plan(resolved_user_id, session_plan_id)
        if session_plan is None:
            return {
                "sessionPlanId": session_plan_id,
                "removedCount": 0,
                "results": [
                    {
                        "query": query,
                        "removed": False,
                        "reason": "session_plan_not_found",
                        "sessionPlanItemId": None,
                        "objectId": None,
                    }
                    for query in queries
                ],
            }

        results = []
        removed_items = []
        for query in queries:
            if not isinstance(query, str):
                results.append({
                    "query": query,
                    "removed": False,
                    "reason": "invalid_query",
                    "sessionPlanItemId": None,
                    "objectId": None,
                })
                continue

            target, reason = _resolve_session_plan_target(
                app=app,
                query=query,
                resolve_global_object_func=resolve_global_object_func,
            )
            if target is None:
                results.append({
                    "query": query,
                    "removed": False,
                    "reason": reason,
                    "sessionPlanItemId": None,
                    "objectId": None,
                })
                continue

            existing_item = _find_session_plan_item(
                session_plan,
                target["objectType"],
                target["targetId"],
            )
            if existing_item is None:
                results.append({
                    "query": target["query"],
                    "removed": False,
                    "reason": "not_in_session_plan",
                    "sessionPlanItemId": None,
                    "objectId": target["objectId"],
                })
                continue

            db.session.delete(existing_item)
            removed_items.append(existing_item.id)
            results.append({
                "query": target["query"],
                "removed": True,
                "reason": "removed",
                "sessionPlanItemId": existing_item.id,
                "objectId": target["objectId"],
            })

        if removed_items:
            db.session.commit()

        return {
            "sessionPlanId": session_plan_id,
            "removedCount": len(removed_items),
            "results": results,
        }


def session_plan_clear_payload(
    *,
    session_plan_id: int,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app import db

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    if isinstance(session_plan_id, bool) or not isinstance(session_plan_id, int) or session_plan_id <= 0:
        raise ValueError("session_plan_id must be a positive integer")

    app = get_app()
    with app.app_context():
        session_plan = _load_owned_active_session_plan(resolved_user_id, session_plan_id)
        if session_plan is None:
            return {
                "cleared": False,
                "reason": "session_plan_not_found",
                "sessionPlanId": session_plan_id,
                "removedCount": 0,
            }

        removed_count = len(session_plan.session_plan_items)
        for item in list(session_plan.session_plan_items):
            db.session.delete(item)

        if removed_count:
            db.session.commit()

        return {
            "cleared": True,
            "reason": "cleared",
            "sessionPlanId": session_plan_id,
            "removedCount": removed_count,
        }


def dso_list_get_id_by_name_payload(
    *,
    name: Any,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from sqlalchemy import func

    from app.models import DsoList

    require_scope_if_available_func(required_scope)
    resolve_mcp_user_id_func(user_id)

    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string")

    stripped = name.strip()
    if len(stripped) > 256:
        raise ValueError("name must be at most 256 characters")

    app = get_app()
    with app.app_context():
        def _serialize(dso_list: Any) -> dict[str, Any]:
            return {
                "dsoListId": dso_list.id,
                "name": dso_list.name,
                "longName": dso_list.long_name,
            }

        # exact match on name or long_name
        exact_matches = (
            DsoList.query
            .filter(DsoList.hidden.is_(False))
            .filter(
                (func.lower(DsoList.name) == stripped.casefold()) |
                (func.lower(DsoList.long_name) == stripped.casefold())
            )
            .order_by(DsoList.id.asc())
            .all()
        )
        if len(exact_matches) == 1:
            return {
                "found": True,
                "reason": "found",
                "dsoListId": exact_matches[0].id,
                "candidates": [_serialize(exact_matches[0])],
            }
        if len(exact_matches) > 1:
            return {
                "found": False,
                "reason": "ambiguous",
                "dsoListId": None,
                "candidates": [_serialize(m) for m in exact_matches[:10]],
            }

        # fuzzy match
        escaped = stripped.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        similar_matches = (
            DsoList.query
            .filter(DsoList.hidden.is_(False))
            .filter(
                DsoList.name.ilike(f"%{escaped}%", escape="\\") |
                DsoList.long_name.ilike(f"%{escaped}%", escape="\\")
            )
            .order_by(DsoList.id.asc())
            .limit(10)
            .all()
        )
        if similar_matches:
            return {
                "found": False,
                "reason": "ambiguous",
                "dsoListId": None,
                "candidates": [_serialize(m) for m in similar_matches],
            }

        return {
            "found": False,
            "reason": "not_found",
            "dsoListId": None,
            "candidates": [],
        }


def session_plan_remove_item_payload(
    *,
    session_plan_id: int,
    query: str,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
) -> dict[str, Any]:
    from app import db

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    if isinstance(session_plan_id, bool) or not isinstance(session_plan_id, int) or session_plan_id <= 0:
        raise ValueError("session_plan_id must be a positive integer")

    app = get_app()
    with app.app_context():
        session_plan = _load_owned_active_session_plan(resolved_user_id, session_plan_id)
        if session_plan is None:
            return {
                "removed": False,
                "reason": "session_plan_not_found",
                "sessionPlanId": session_plan_id,
                "sessionPlanItemId": None,
                "objectId": None,
            }

        target, reason = _resolve_session_plan_target(
            app=app,
            query=query,
            resolve_global_object_func=resolve_global_object_func,
        )
        if target is None:
            return {
                "removed": False,
                "reason": reason,
                "sessionPlanId": session_plan_id,
                "sessionPlanItemId": None,
                "objectId": None,
            }

        existing_item = _find_session_plan_item(
            session_plan,
            target["objectType"],
            target["targetId"],
        )
        if existing_item is None:
            return {
                "removed": False,
                "reason": "not_in_session_plan",
                "sessionPlanId": session_plan_id,
                "sessionPlanItemId": None,
                "objectId": target["objectId"],
            }

        item_id = existing_item.id
        db.session.delete(existing_item)
        db.session.commit()

        return {
            "removed": True,
            "reason": "removed",
            "sessionPlanId": session_plan_id,
            "sessionPlanItemId": item_id,
            "objectId": target["objectId"],
        }
