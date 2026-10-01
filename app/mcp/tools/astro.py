from __future__ import annotations

from typing import Any, Callable


def register_tools(
    server: Any,
    *,
    visibility_get_resolver: Callable[..., dict[str, Any]],
    night_info_resolver: Callable[..., dict[str, Any]],
) -> None:
    @server.tool(name="visibility.get")
    def visibility_get(
        query: str | None = None,
        object_id: str | None = None,
        date: str | None = None,
        location: str | int | None = None,
        time: str | None = None,
        horizon_deg: float = 0.0,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Rise, transit and set of an object for an observing night at a location.

        Object: query (e.g. "M42", "Jupiter", "C/2023 A3", "Moon") or object_id
        (e.g. "dso:123"). date: YYYY-MM-DD of the evening (default today).
        location: location id, name or "lat,lon" (default: user's most recently used
        location). time: optional local "HH:MM" (times before 12:00 mean the morning
        after) to get altitude/azimuth at that moment.

        Returns local times (ISO with offset), transitAltitudeDeg, status
        (ok / circumpolar / never_rises) and the dark window of the night with the
        object's altitude at its start, middle and end.
        """
        return visibility_get_resolver(
            query=query,
            object_id=object_id,
            date=date,
            location=location,
            time=time,
            horizon_deg=horizon_deg,
            user_id=user_id,
        )

    @server.tool(name="night.info")
    def night_info(
        date: str | None = None,
        location: str | int | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Observing conditions of a night: sun and twilight times, Moon and moonless dark time.

        date: YYYY-MM-DD of the evening (default today). location: location id, name
        or "lat,lon" (default: user's most recently used location).

        Returns sunset/sunrise, civil/nautical/astronomical dusk and dawn, the darkest
        window (darkness = astronomical / nautical / none in summer at high latitudes),
        Moon rise/set/phase/illumination and moonless dark windows with total hours.
        """
        return night_info_resolver(date=date, location=location, user_id=user_id)
