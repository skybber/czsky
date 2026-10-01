from __future__ import annotations

from typing import Any, Callable


def _enum_value(value: Any) -> str | None:
    return value.value if value is not None and hasattr(value, "value") else value


def _serialize_telescope(telescope: Any) -> dict[str, Any]:
    return {
        "telescopeId": telescope.id,
        "name": telescope.name,
        "vendor": telescope.vendor,
        "model": telescope.model,
        "type": _enum_value(telescope.telescope_type),
        "apertureMm": telescope.aperture_mm,
        "focalLengthMm": telescope.focal_length_mm,
        "focalRatio": round(telescope.focal_length_mm / telescope.aperture_mm, 1)
        if telescope.focal_length_mm and telescope.aperture_mm else None,
        "fixedMagnification": telescope.fixed_magnification,
        "isDefault": bool(telescope.is_default),
        "isActive": bool(telescope.is_active),
    }


def _serialize_eyepiece(eyepiece: Any) -> dict[str, Any]:
    return {
        "eyepieceId": eyepiece.id,
        "name": eyepiece.name,
        "vendor": eyepiece.vendor,
        "model": eyepiece.model,
        "focalLengthMm": eyepiece.focal_length_mm,
        "apparentFovDeg": eyepiece.fov_deg,
        "barrelInch": eyepiece.diameter_inch,
        "isActive": bool(eyepiece.is_active),
    }


def _serialize_filter(filter_row: Any) -> dict[str, Any]:
    return {
        "filterId": filter_row.id,
        "name": filter_row.name,
        "vendor": filter_row.vendor,
        "model": filter_row.model,
        "type": _enum_value(filter_row.filter_type),
        "barrelInch": filter_row.diameter_inch,
        "isActive": bool(filter_row.is_active),
    }


def _serialize_lens(lens: Any) -> dict[str, Any]:
    return {
        "lensId": lens.id,
        "name": lens.name,
        "vendor": lens.vendor,
        "model": lens.model,
        "type": _enum_value(lens.lens_type),
        "magnification": lens.magnification,
        "barrelInch": lens.diameter_inch,
        "isActive": bool(lens.is_active),
    }


def equipment_list_payload(
    *,
    include_inactive: bool,
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
        from app.models import Eyepiece, Filter, Lens, Telescope

        def _rows(model):
            query = model.query.filter(model.user_id == resolved_user_id, model.is_deleted.is_not(True))
            if not include_inactive:
                query = query.filter(model.is_active.is_not(False))
            return query.order_by(model.name.asc()).all()

        telescopes = [_serialize_telescope(row) for row in _rows(Telescope)]
        telescopes.sort(key=lambda item: not item["isDefault"])
        return {
            "telescopes": telescopes,
            "eyepieces": [_serialize_eyepiece(row) for row in _rows(Eyepiece)],
            "filters": [_serialize_filter(row) for row in _rows(Filter)],
            "lenses": [_serialize_lens(row) for row in _rows(Lens)],
        }
