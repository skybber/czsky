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

        similar_matches = (
            Location.query
            .filter(Location.name.ilike(f"%{parsed_location_name}%"))
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


def _load_owned_session_plan(resolved_user_id: int, session_plan_id: int):
    from app.models import SessionPlan

    return SessionPlan.query.filter_by(id=session_plan_id, user_id=resolved_user_id).first()


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
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app import db
    from app.models import SessionPlan

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_wishlist_user_id_func(user_id)

    parsed_for_date = parse_for_date(for_date)
    normalized_title = (title or "").strip() or "Uknown"

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


def session_plan_get_id_by_date_payload(
    *,
    for_date: Any,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app import db
    from app.models import SessionPlan

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_wishlist_user_id_func(user_id)

    parsed_for_date = parse_for_date(for_date)
    target_date = parsed_for_date.date()

    app = get_app()
    with app.app_context():
        session_plans = (
            SessionPlan.query
            .filter(SessionPlan.user_id == resolved_user_id)
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


def session_plan_add_item_payload(
    *,
    session_plan_id: int,
    query: str,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
) -> dict[str, Any]:
    from app import db

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_wishlist_user_id_func(user_id)

    if isinstance(session_plan_id, bool) or not isinstance(session_plan_id, int) or session_plan_id <= 0:
        raise ValueError("session_plan_id must be a positive integer")

    app = get_app()
    with app.app_context():
        session_plan = _load_owned_session_plan(resolved_user_id, session_plan_id)
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


def session_plan_remove_item_payload(
    *,
    session_plan_id: int,
    query: str,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
) -> dict[str, Any]:
    from app import db

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_wishlist_user_id_func(user_id)

    if isinstance(session_plan_id, bool) or not isinstance(session_plan_id, int) or session_plan_id <= 0:
        raise ValueError("session_plan_id must be a positive integer")

    app = get_app()
    with app.app_context():
        session_plan = _load_owned_session_plan(resolved_user_id, session_plan_id)
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
