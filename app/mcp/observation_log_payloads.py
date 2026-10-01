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


def _find_foreign_equipment(resolved_user_id: int, telescope_id: int | None, eyepiece_id: int | None,
                            filter_id: int | None) -> str | None:
    """Return the reason when any given equipment id does not belong to the user."""
    from app.models import Eyepiece, Filter, Telescope

    for model, equipment_id, reason in (
        (Telescope, telescope_id, "telescope_not_found"),
        (Eyepiece, eyepiece_id, "eyepiece_not_found"),
        (Filter, filter_id, "filter_not_found"),
    ):
        if equipment_id is None:
            continue
        owned = (
            model.query
            .filter(model.id == equipment_id, model.user_id == resolved_user_id, model.is_deleted.is_not(True))
            .first()
        )
        if owned is None:
            return reason
    return None


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

        foreign_equipment_reason = _find_foreign_equipment(
            resolved_user_id, parsed_telescope_id, parsed_eyepiece_id, parsed_filter_id,
        )
        if foreign_equipment_reason is not None:
            return {
                "upserted": False,
                "created": False,
                "updated": False,
                "reason": foreign_equipment_reason,
                "observingSessionId": observing_session.id,
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


MAX_OBSERVATION_LIST_LIMIT = 100


def _enum_value(value: Any) -> str | None:
    return value.value if value is not None and hasattr(value, "value") else value


def _observation_targets(observation: Any) -> list[dict[str, Any]]:
    targets = []
    for dso in observation.deepsky_objects or []:
        targets.append({"objectId": f"dso:{dso.id}", "name": dso.denormalized_name(), "type": dso.type})
    single_targets = (
        ("double_star", observation.double_star, lambda o: o.get_common_norm_name()),
        ("comet", observation.comet, lambda o: o.designation),
        ("minor_planet", observation.minor_planet, lambda o: o.designation),
        ("planet", observation.planet, lambda o: o.get_localized_name()),
        ("planet_moon", observation.planet_moon, lambda o: getattr(o, "name", None)),
    )
    for object_type, target, name_func in single_targets:
        if target is not None:
            targets.append({"objectId": f"{object_type}:{target.id}", "name": name_func(target), "type": object_type})
    return targets


def _owned_equipment(observation: Any, equipment: Any, id_key: str) -> dict[str, Any] | None:
    # Older data may reference equipment of another user; never expose its name.
    if equipment is None or equipment.user_id != observation.user_id:
        return None
    return {id_key: equipment.id, "name": equipment.name}


def serialize_observation(observation: Any, *, include_notes: bool = True) -> dict[str, Any]:
    result = {
        "observationId": observation.id,
        "observingSessionId": observation.observing_session_id,
        "dateFrom": observation.date_from.isoformat() if observation.date_from else None,
        "targetType": _enum_value(observation.target_type),
        "targets": _observation_targets(observation),
        "telescope": _owned_equipment(observation, observation.telescope, "telescopeId"),
        "eyepiece": _owned_equipment(observation, observation.eyepiece, "eyepieceId"),
        "filter": _owned_equipment(observation, observation.filter, "filterId"),
        "magnification": observation.magnification,
        "seeing": _enum_value(observation.seeing),
        "sqm": observation.sqm,
        "faintestStar": observation.faintest_star,
        "locationId": observation.location_id,
    }
    if include_notes:
        result["notes"] = observation.notes
    else:
        notes = (observation.notes or "").strip()
        result["notesPreview"] = (notes[:200] + "…") if len(notes) > 200 else notes
    return result


def _filter_observations_by_target(query: Any, target: dict[str, Any]):
    from app.models import DeepskyObject, Observation

    object_type, target_id = target["objectType"], target["targetId"]
    if object_type == "dso":
        return query.filter(Observation.deepsky_objects.any(DeepskyObject.id == target_id))
    column = {
        "double_star": Observation.double_star_id,
        "planet": Observation.planet_id,
        "planet_moon": Observation.planet_moon_id,
        "comet": Observation.comet_id,
        "minor_planet": Observation.minor_planet_id,
    }[object_type]
    return query.filter(column == target_id)


def observation_log_list_payload(
    *,
    object_id: str | None,
    query: str | None,
    observing_session_id: int | str | None,
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    parse_observation_object_id_func: Callable[[str | None], tuple[str, int] | None],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_OBSERVATION_LIST_LIMIT:
        raise ValueError(f"limit must be an integer from 1 to {MAX_OBSERVATION_LIST_LIMIT}")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    parsed_session_id = _parse_optional_positive_int(observing_session_id, field_name="observing_session_id")
    parsed_from = parse_observing_session_datetime(date_from, field_name="date_from") if date_from else None
    parsed_to = parse_observing_session_datetime(date_to, field_name="date_to") if date_to else None

    app = get_app()
    with app.app_context():
        from app.models import Observation

        observations = Observation.query.filter(Observation.user_id == resolved_user_id)

        target = None
        if (object_id or "").strip() or (query or "").strip():
            target, error_reason = _resolve_observation_target(
                app=app,
                object_id=object_id,
                query=query,
                parse_observation_object_id_func=parse_observation_object_id_func,
                resolve_global_object_func=resolve_global_object_func,
            )
            if error_reason:
                return {"found": False, "reason": error_reason, "total": 0, "observations": []}
            observations = _filter_observations_by_target(observations, target)

        if parsed_session_id is not None:
            observations = observations.filter(Observation.observing_session_id == parsed_session_id)
        if parsed_from is not None:
            observations = observations.filter(Observation.date_from >= parsed_from)
        if parsed_to is not None:
            observations = observations.filter(Observation.date_from <= parsed_to)

        total = observations.count()
        rows = (
            observations.order_by(Observation.date_from.desc(), Observation.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "found": total > 0,
            "reason": "ok" if total else "no_observations",
            "objectId": target["objectId"] if target else None,
            "total": total,
            "offset": offset,
            "nextOffset": offset + len(rows) if offset + len(rows) < total else None,
            "observations": [serialize_observation(row, include_notes=False) for row in rows],
        }


def observation_log_get_payload(
    *,
    observation_id: int | str,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_mcp_user_id_func(user_id)
    parsed_id = _parse_optional_positive_int(observation_id, field_name="observation_id")
    if parsed_id is None:
        raise ValueError("observation_id is required")

    app = get_app()
    with app.app_context():
        from app.models import Observation

        observation = Observation.query.filter_by(id=parsed_id, user_id=resolved_user_id).first()
        if observation is None:
            return {"found": False, "reason": "observation_not_found", "observation": None}
        return {"found": True, "reason": "found", "observation": serialize_observation(observation)}
