from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.mcp.session_plan_payloads import (
    _resolve_location_for_session_plan_create,
    _to_iso,
)


def parse_observing_session_datetime(value: Any, *, field_name: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO datetime string")

    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")

    normalized = stripped.replace("Z", "+00:00") if stripped.endswith("Z") else stripped
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Unsupported {field_name} format; use ISO datetime") from exc

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def parse_optional_float(value: Any, *, field_name: str) -> float | None:
    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")

    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a number")

    stripped = value.strip()
    if not stripped:
        return None

    try:
        return float(stripped)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a number") from exc


def parse_optional_text(value: Any, *, field_name: str, max_length: int | None = None) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")

    stripped = value.strip()
    if not stripped:
        return None

    if max_length is not None and len(stripped) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")

    return stripped


def parse_optional_rating(value: Any) -> int:
    if value is None:
        return 0

    if isinstance(value, bool):
        raise ValueError("rating must be an integer from 0 to 5")

    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0
        if not stripped.isdigit():
            raise ValueError("rating must be an integer from 0 to 5")
        parsed = int(stripped)
    else:
        raise ValueError("rating must be an integer from 0 to 5")

    if parsed < 0 or parsed > 5:
        raise ValueError("rating must be an integer from 0 to 5")

    return parsed * 2


def parse_optional_enum(value: Any, *, field_name: str, enum_cls: Any, default: Any):
    if value is None:
        return default

    if isinstance(value, enum_cls):
        return value

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")

    stripped = value.strip()
    if not stripped:
        return default

    normalized = stripped.upper()
    try:
        return enum_cls.coerce(normalized)
    except ValueError as exc:
        allowed = ", ".join(choice.value for choice in enum_cls)
        raise ValueError(f"{field_name} must be one of: {allowed}") from exc


def _is_valid_observing_night_range(date_from: datetime, date_to: datetime) -> bool:
    if date_from > date_to:
        return False
    if date_to - date_from > timedelta(days=1):
        return False
    return date_to.date() in {date_from.date(), (date_from + timedelta(days=1)).date()}


def _deactivate_all_user_observing_sessions(*, resolved_user_id: int) -> None:
    from app import db
    from app.models import ObservingSession

    for active_session in ObservingSession.query.filter_by(user_id=resolved_user_id, is_active=True).all():
        active_session.is_active = False
        db.session.add(active_session)




def _load_owned_observing_session(resolved_user_id: int, observing_session_id: int):
    from app.models import ObservingSession

    return (
        ObservingSession.query
        .filter_by(id=observing_session_id, user_id=resolved_user_id)
        .first()
    )


def _load_owned_active_observing_session(resolved_user_id: int):
    from app.models import ObservingSession

    return (
        ObservingSession.query
        .filter_by(user_id=resolved_user_id, is_active=True)
        .first()
    )


def _serialize_observing_session_summary(observing_session: Any) -> dict[str, Any]:
    return {
        "observingSessionId": observing_session.id,
        "title": observing_session.title,
        "dateFrom": _to_iso(observing_session.date_from),
        "dateTo": _to_iso(observing_session.date_to),
        "locationId": observing_session.location_id,
        "locationPosition": observing_session.location_position,
        "isPublic": bool(observing_session.is_public),
        "isFinished": bool(observing_session.is_finished),
        "isActive": bool(observing_session.is_active),
    }

def observing_session_create_payload(
    *,
    date_from: Any,
    date_to: Any,
    location_id: Any,
    location_name: Any,
    location: Any,
    title: str | None,
    sqm: Any,
    faintest_star: Any,
    seeing: Any,
    transparency: Any,
    weather: Any,
    equipment: Any,
    notes: Any,
    is_public: bool,
    is_finished: bool,
    is_active: bool,
    rating: Any,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app import db
    from app.models import ObservingSession, Seeing, Transparency

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    parsed_date_from = parse_observing_session_datetime(date_from, field_name="date_from")
    parsed_date_to = parse_observing_session_datetime(date_to, field_name="date_to")
    normalized_title = parse_optional_text(title, field_name="title", max_length=256) or "Unknown"
    normalized_sqm = parse_optional_float(sqm, field_name="sqm")
    normalized_faintest_star = parse_optional_float(faintest_star, field_name="faintest_star")
    normalized_seeing = parse_optional_enum(
        seeing, field_name="seeing", enum_cls=Seeing, default=Seeing.AVERAGE
    )
    normalized_transparency = parse_optional_enum(
        transparency,
        field_name="transparency",
        enum_cls=Transparency,
        default=Transparency.AVERAGE,
    )
    normalized_weather = parse_optional_text(weather, field_name="weather")
    normalized_equipment = parse_optional_text(equipment, field_name="equipment")
    normalized_notes = parse_optional_text(notes, field_name="notes")
    normalized_rating = parse_optional_rating(rating)

    if not _is_valid_observing_night_range(parsed_date_from, parsed_date_to):
        return {
            "created": False,
            "reason": "invalid_date_range",
            "observingSessionId": None,
            "title": normalized_title,
            "dateFrom": _to_iso(parsed_date_from),
            "dateTo": _to_iso(parsed_date_to),
            "locationId": None,
            "locationPosition": None,
            "candidates": [],
            "isPublic": bool(is_public),
            "isFinished": bool(is_finished),
            "isActive": False if is_finished else bool(is_active),
        }

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
                "observingSessionId": None,
                "title": normalized_title,
                "dateFrom": _to_iso(parsed_date_from),
                "dateTo": _to_iso(parsed_date_to),
                "locationId": None,
                "locationPosition": None,
                "candidates": candidates,
                "isPublic": bool(is_public),
                "isFinished": bool(is_finished),
                "isActive": False if is_finished else bool(is_active),
            }

        effective_is_active = False if is_finished else bool(is_active)
        if effective_is_active:
            _deactivate_all_user_observing_sessions(resolved_user_id=resolved_user_id)

        new_observing_session = ObservingSession(
            user_id=resolved_user_id,
            title=normalized_title,
            date_from=parsed_date_from,
            date_to=parsed_date_to,
            location_id=resolved_location_id,
            location_position=resolved_location_position,
            sqm=normalized_sqm,
            faintest_star=normalized_faintest_star,
            seeing=normalized_seeing,
            transparency=normalized_transparency,
            weather=normalized_weather,
            equipment=normalized_equipment,
            rating=normalized_rating,
            notes=normalized_notes,
            default_telescope_id=None,
            is_public=bool(is_public),
            is_finished=bool(is_finished),
            is_active=effective_is_active,
            create_by=resolved_user_id,
            update_by=resolved_user_id,
            create_date=datetime.now(),
            update_date=datetime.now(),
        )

        db.session.add(new_observing_session)
        db.session.commit()

        return {
            "created": True,
            "reason": "created",
            "observingSessionId": new_observing_session.id,
            "title": new_observing_session.title,
            "dateFrom": _to_iso(new_observing_session.date_from),
            "dateTo": _to_iso(new_observing_session.date_to),
            "locationId": new_observing_session.location_id,
            "locationPosition": new_observing_session.location_position,
            "candidates": [],
            "isPublic": bool(new_observing_session.is_public),
            "isFinished": bool(new_observing_session.is_finished),
            "isActive": bool(new_observing_session.is_active),
        }



def observing_session_set_active_payload(
    *,
    observing_session_id: int,
    is_active: bool,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app import db

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    if isinstance(observing_session_id, bool) or not isinstance(observing_session_id, int) or observing_session_id <= 0:
        raise ValueError("observing_session_id must be a positive integer")

    app = get_app()
    with app.app_context():
        observing_session = _load_owned_observing_session(resolved_user_id, observing_session_id)
        if observing_session is None:
            return {
                "updated": False,
                "reason": "observing_session_not_found",
                "observingSessionId": None,
                "isActive": False,
            }

        if is_active and observing_session.is_finished:
            return {
                "updated": False,
                "reason": "session_finished",
                "observingSessionId": observing_session.id,
                "isActive": bool(observing_session.is_active),
            }

        if is_active:
            _deactivate_all_user_observing_sessions(resolved_user_id=resolved_user_id)
            observing_session.is_active = True
        else:
            observing_session.is_active = False

        db.session.add(observing_session)
        db.session.commit()

        return {
            "updated": True,
            "reason": "updated",
            "observingSessionId": observing_session.id,
            "isActive": bool(observing_session.is_active),
        }


def observing_session_get_active_payload(
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
        observing_session = _load_owned_active_observing_session(resolved_user_id)
        if observing_session is None:
            return {
                "found": False,
                "reason": "no_active_session",
                "observingSession": None,
            }

        return {
            "found": True,
            "reason": "found",
            "observingSession": _serialize_observing_session_summary(observing_session),
        }
