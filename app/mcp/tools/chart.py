from __future__ import annotations

from typing import Any, Callable


def register_tools(
    server: Any,
    *,
    chart_image_resolver: Callable[..., Any],
) -> None:
    @server.tool(name="chart.image", structured_output=False)
    def chart_image(
        query: str | None = None,
        object_id: str | None = None,
        fov_deg: float = 10.0,
        width: int = 800,
        height: int = 600,
        theme: str = "light",
        user_id: int | None = None,
    ) -> Any:
        """Render a finder chart image centred on an object.

        Object: query (e.g. "M51", "Saturn", comet designation) or object_id
        (e.g. "dso:123"). fov_deg: field of view in degrees (0.5-120; ~1-2 for a
        telescope eyepiece view, 5-15 for a finder, 30+ for naked-eye orientation).
        theme: "light" (printable), "dark" or "night" (red). The limiting magnitude is
        chosen automatically from the field of view. Rendering takes a few seconds.
        """
        return chart_image_resolver(
            query=query,
            object_id=object_id,
            fov_deg=fov_deg,
            width=width,
            height=height,
            theme=theme,
            user_id=user_id,
        )
