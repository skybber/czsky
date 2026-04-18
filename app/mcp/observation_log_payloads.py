from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Callable

from app.mcp.observing_session_payloads import (
    _load_owned_active_observing_session,
    _load_owned_observing_session,
    parse_observing_session_datetime,
)

OBJECT_ID_PATTERN = re.compile(r"^(dso|double_star|planet|planet_moon|comet|minor_planet):(\d+)$", re.IGNORECASE)


def parse_observation_object_id(object_id: str | None) -> tuple[str, int] | None:
    if object_id is None:
        return None
    if not isinstance(object_id, str):
        raise ValueError("object_id must be a string")

    stripped = object_id.strip()
    if not stripped:
        return None

    matched = OBJECT_ID_PATTERN.match(stripped)
    if not matched:
        raise ValueError(
            "object_id must be in format dso:<id>, double_star:<id>, planet:<id>, planet_moon:<id>, comet:<id>, or minor_planet:<id>"
        )

    object_type = matched.group(1).lower()
    target_id = int(matched.group(2))
    if target_id <= 0:
        raise ValueError("object_id numeric part must be positive")

    return object_type, target_id


def _parse_optional_positive_int(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a positive integer")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError(f"{field_name} must be a positive integer")
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a positive integer")
    stripped = value.strip()
    if not stripped:
        return None
    if not stripped.isdigit():
        raise ValueError(f"{field_name} must be a positive integer")
    parsed = int(stripped)
    if parsed <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return parsed


def _resolve_target_from_object_reference(*, object_id: str, parse_observation_object_id_func: Callable[[str | None], tuple[str, int] | None]):
    from app.models import Comet, DeepskyObject, DoubleStar, MinorPlanet, Planet, PlanetMoon

    parsed = parse_observation_object_id_func(object_id)
    if parsed is None:
        return None, "target_not_found"

    object_type, target_id = parsed
    model_map = {
        "dso": DeepskyObject,
        "double_star": DoubleStar,
        "planet": Planet,
        "planet_moon": PlanetMoon,
        "comet": Comet,
        "minor_planet": MinorPlanet,
    }
    model = model_map.get(object_type)
    if model is None:
        return None, "unsupported_object_type"

    target_object = model.query.filter_by(id=target_id).first()
    if target_object is None:
        return None, "target_not_found"

    return {
        "objectType": object_type,
        "targetId": target_id,
        "targetObject": target_object,
        "objectId": f"{object_type}:{target_id}",
    }, None


def _resolve_target_from_query(*, app: Any, query: str, resolve_global_object_func: Callable[[str], dict[str, Any] | None]):
    stripped_query = (query or "").strip()
    if not stripped_query:
        return None, "invalid_arguments"

    with app.test_request_context("/", headers={"Host": "localhost"}):
        resolved = resolve_global_object_func(stripped_query)

    if not resolved:
        return None, "target_not_found"

    object_type = resolved.get("object_type")
    if object_type not in {"dso", "double_star", "planet", "planet_moon", "comet", "minor_planet"}:
        return None, "unsupported_object_type"

    target_object = resolved.get("object")
    target_id = getattr(target_object, "id", None)
    if not isinstance(target_id, int) or target_id <= 0:
        return None, "target_not_found"

    return {
        "objectType": object_type,
        "targetId": target_id,
        "targetObject": target_object,
        "objectId": f"{object_type}:{target_id}",
    }, None


def _resolve_observation_target(
    *,
    app: Any,
    object_id: str | None,
    query: str | None,
    parse_observation_object_id_func: Callable[[str | None], tuple[str, int] | None],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
):
    stripped_object_id = (object_id or "").strip()
    stripped_query = (query or "").strip()

    if bool(stripped_object_id) == bool(stripped_query):
        return None, "invalid_arguments"

    if stripped_object_id:
        return _resolve_target_from_object_reference(
            object_id=stripped_object_id,
            parse_observation_object_id_func=parse_observation_object_id_func,
        )

    return _resolve_target_from_query(
        app=app,
        query=stripped_query,
        resolve_global_object_func=resolve_global_object_func,
    )


def _find_observation_for_target(observing_session: Any, object_type: str, target_id: int):
    if object_type == "dso":
        return observing_session.find_observation_by_dso_id(target_id)
    if object_type == "double_star":
        return observing_session.find_observation_by_double_star_id(target_id)
    if object_type == "planet":
        return observing_session.find_observation_by_planet_id(target_id)
    if object_type == "planet_moon":
        return observing_session.find_observation_by_planet_moon_id(target_id)
    if object_type == "comet":
        return observing_session.find_observation_by_comet_id(target_id)
    if object_type == "minor_planet":
        return observing_session.find_observation_by_minor_planet_id(target_id)
    return None


def _default_observation_datetime(observing_session: Any) -> datetime:
    date_from = datetime.now()
    if date_from.date() not in {observing_session.date_from.date(), observing_session.date_to.date()}:
        return observing_session.date_from
    return date_from


def _create_observation_for_target(*, observing_session: Any, target: dict[str, Any], resolved_user_id: int, notes: str | None, date_from: datetime | None, telescope_id: int | None, eyepiece_id: int | None, filter_id: int | None):
    from app.models import Observation, ObservationTargetType

    target_object = target["targetObject"]
    object_type = target["objectType"]
    observation_date = date_from or _default_observation_datetime(observing_session)
    resolved_telescope_id = telescope_id
    if resolved_telescope_id is None and observing_session.default_telescope_id is not None:
        resolved_telescope_id = observing_session.default_telescope_id

    observation = Observation(
        observing_session_id=observing_session.id,
        date_from=observation_date,
        date_to=observation_date,
        notes=notes or "",
        telescope_id=resolved_telescope_id,
        eyepiece_id=eyepiece_id,
        filter_id=filter_id,
        create_by=resolved_user_id,
        update_by=resolved_user_id,
        create_date=datetime.now(),
        update_date=datetime.now(),
    )

    if object_type == "dso":
        observation.target_type = ObservationTargetType.DSO
        observation.deepsky_objects.append(target_object)
        return observation
    if object_type == "double_star":
        observation.target_type = ObservationTargetType.DBL_STAR
        observation.double_star_id = target_object.id
        return observation
    if object_type == "planet":
        observation.target_type = ObservationTargetType.PLANET
        observation.planet_id = target_object.id
        return observation
    if object_type == "planet_moon":
        observation.target_type = ObservationTargetType.PLANET_MOON
        observation.planet_moon_id = target_object.id
        return observation
    if object_type == "comet":
        observation.target_type = ObservationTargetType.COMET
        observation.comet_id = target_object.id
        return observation
    if object_type == "minor_planet":
        observation.target_type = ObservationTargetType.M_PLANET
        observation.minor_planet_id = target_object.id
        return observation

    raise ValueError("unsupported object type")


def observation_log_upsert_payload(
    *,
    object_id: str | None,
    query: str | None,
    observing_session_id: Any,
    notes: str | None,
    date_from: Any,
    telescope_id: Any,
    eyepiece_id: Any,
    filter_id: Any,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
    parse_observation_object_id_func: Callable[[str | None], tuple[str, int] | None],
) -> dict[str, Any]:
    from app import db

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)
    parsed_session_id = _parse_optional_positive_int(observing_session_id, field_name="observing_session_id")
    parsed_telescope_id = _parse_optional_positive_int(telescope_id, field_name="telescope_id")
    parsed_eyepiece_id = _parse_optional_positive_int(eyepiece_id, field_name="eyepiece_id")
    parsed_filter_id = _parse_optional_positive_int(filter_id, field_name="filter_id")
    parsed_date_from = parse_observing_session_datetime(date_from, field_name="date_from") if date_from is not None and str(date_from).strip() else None

    app = get_app()
    with app.app_context():
        target, reason = _resolve_observation_target(
            app=app,
            object_id=object_id,
            query=query,
            parse_observation_object_id_func=parse_observation_object_id_func,
            resolve_global_object_func=resolve_global_object_func,
        )
        if reason is not None:
            return {
                "upserted": False,
                "created": False,
                "updated": False,
                "reason": reason,
                "observingSessionId": parsed_session_id,
                "observationId": None,
                "objectId": None,
                "objectType": None,
            }

        if parsed_session_id is not None:
            observing_session = _load_owned_observing_session(resolved_user_id, parsed_session_id)
            missing_reason = "observing_session_not_found"
        else:
            observing_session = _load_owned_active_observing_session(resolved_user_id)
            missing_reason = "no_active_observing_session"

        if observing_session is None:
            return {
                "upserted": False,
                "created": False,
                "updated": False,
                "reason": missing_reason,
                "observingSessionId": parsed_session_id,
                "observationId": None,
                "objectId": target["objectId"],
                "objectType": target["objectType"],
            }

        if observing_session.is_finished:
            return {
                "upserted": False,
                "created": False,
                "updated": False,
                "reason": "session_finished",
                "observingSessionId": observing_session.id,
                "observationId": None,
                "objectId": target["objectId"],
                "objectType": target["objectType"],
            }

        observation = _find_observation_for_target(observing_session, target["objectType"], target["targetId"])
        created = observation is None

        if created:
            observation = _create_observation_for_target(
                observing_session=observing_session,
                target=target,
                resolved_user_id=resolved_user_id,
                notes=notes,
                date_from=parsed_date_from,
                telescope_id=parsed_telescope_id,
                eyepiece_id=parsed_eyepiece_id,
                filter_id=parsed_filter_id,
            )
        else:
            if notes is not None:
                observation.notes = notes
            if parsed_date_from is not None:
                observation.date_from = parsed_date_from
                observation.date_to = parsed_date_from
            if parsed_telescope_id is not None:
                observation.telescope_id = parsed_telescope_id
            if parsed_eyepiece_id is not None:
                observation.eyepiece_id = parsed_eyepiece_id
            if parsed_filter_id is not None:
                observation.filter_id = parsed_filter_id
            observation.update_by = resolved_user_id
            observation.update_date = datetime.now()

        db.session.add(observation)
        db.session.commit()

        return {
            "upserted": True,
            "created": created,
            "updated": not created,
            "reason": "upserted",
            "observingSessionId": observing_session.id,
            "observationId": observation.id,
            "objectId": target["objectId"],
            "objectType": target["objectType"],
        }
