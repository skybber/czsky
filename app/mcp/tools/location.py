from __future__ import annotations

from typing import Any, Callable


def register_tools(
    server: Any,
    *,
    location_find_resolver: Callable[..., dict[str, Any]],
) -> None:
    @server.tool(name="location.find")
    def location_find(
        query: str | None = None,
        near: str | None = None,
        radius_km: float | None = None,
        limit: int | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Find observing locations without listing the whole (large) location database.

        Modes:
          - no arguments: "my locations" - user's own locations and locations used in
            their observing sessions and session plans, most recently used first
            (with useCount and lastUsed). Use this first to pick a location id.
          - query: search own and public locations by name (substring match).
          - near: "lat,lon" (e.g. "49.91,14.78"); public and own locations within
            radius_km (default 50), nearest first, with distanceKm. Can be combined
            with query.

        Results include locationId, coordinates, bortle and rating. The locationId
        can be passed as location to session_plan.create, observing_session.create,
        night.info, visibility.get and other tools.
        """
        return location_find_resolver(query=query, near=near, radius_km=radius_km, limit=limit, user_id=user_id)
