from __future__ import annotations

from typing import Any, Callable


def register_tools(
    server: Any,
    *,
    equipment_list_resolver: Callable[..., dict[str, Any]],
) -> None:
    @server.tool(name="equipment.list")
    def equipment_list(
        include_inactive: bool = False,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """List the user's telescopes, eyepieces, filters and lenses (Barlow/reducers).

        Use the returned telescopeId, eyepieceId and filterId with observation_log.upsert.
        The default telescope is listed first. Magnification = telescope focalLengthMm /
        eyepiece focalLengthMm (times lens magnification when a lens is used).
        """
        return equipment_list_resolver(include_inactive=include_inactive, user_id=user_id)
