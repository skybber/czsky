"""Finder chart rendering for MCP tools (uses the same fchart3 pipeline as the web chart)."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

from app.mcp.astro_common import McpLookupError, radec_to_text, target_label, target_radec

MIN_FOV_DEG = 0.5
MAX_FOV_DEG = 120.0
MIN_SIZE_PX = 200
MAX_SIZE_PX = 1600
CHART_THEMES = ("dark", "light", "night")
# Constellation lines + borders, deep-sky, star labels, solar system, Milky Way.
DEFAULT_FLAGS = "CBDNOW"

# Chart rendering is CPU and memory heavy; never render more than two charts at once.
_render_slots = threading.BoundedSemaphore(2)


def chart_image_payload(
    *,
    object_id: str | None,
    query: str | None,
    fov_deg: float,
    width: int,
    height: int,
    theme: str,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_mcp_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
) -> tuple[bytes | None, str | None, dict[str, Any]]:
    """Return (image bytes, image format, info). On failure bytes are None and info holds the reason."""
    from app.mcp.astro_payloads import resolve_sky_target

    require_scope_if_available_func(required_scope)
    resolve_mcp_user_id_func(user_id)

    if not (MIN_FOV_DEG <= float(fov_deg) <= MAX_FOV_DEG):
        raise ValueError(f"fov_deg must be from {MIN_FOV_DEG} to {MAX_FOV_DEG}")
    for name, value in (("width", width), ("height", height)):
        if isinstance(value, bool) or not isinstance(value, int) or not (MIN_SIZE_PX <= value <= MAX_SIZE_PX):
            raise ValueError(f"{name} must be an integer from {MIN_SIZE_PX} to {MAX_SIZE_PX}")
    theme = (theme or "dark").strip().lower()
    if theme not in CHART_THEMES:
        raise ValueError(f"theme must be one of: {', '.join(CHART_THEMES)}")

    app = get_app()
    with app.app_context():
        try:
            object_type, obj = resolve_sky_target(
                app, object_id=object_id, query=query, resolve_global_object_func=resolve_global_object_func,
            )
            ra, dec = target_radec(object_type, obj, datetime.now(timezone.utc).replace(tzinfo=None))
        except McpLookupError as e:
            return None, None, e.to_payload()

        info = {
            "found": True,
            "object": {"objectType": object_type, "name": target_label(object_type, obj), **radec_to_text(ra, dec)},
            "fovDeg": float(fov_deg),
            "theme": theme,
        }

        if not _render_slots.acquire(blocking=False):
            return None, None, {"found": False, "reason": "chart_renderer_busy"}
        try:
            from flask import session

            from app.commons.chart_generator import common_chart_pos_img

            query_string = {
                "ra": float(ra),
                "dec": float(dec),
                "fsz": float(fov_deg),
                "width": width,
                "height": height,
                "flags": DEFAULT_FLAGS,
            }
            with app.test_request_context("/", query_string=query_string, headers={"Host": "localhost"}):
                session["theme"] = theme
                dso_names = (obj.name,) if object_type == "dso" else None
                img_bytes, img_format = common_chart_pos_img(float(ra), float(dec), dso_names=dso_names)
            return img_bytes.read(), img_format, info
        finally:
            _render_slots.release()
