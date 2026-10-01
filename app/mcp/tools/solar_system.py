from __future__ import annotations

from typing import Any, Callable


def register_tools(
    server: Any,
    *,
    comet_list_bright_resolver: Callable[..., dict[str, Any]],
    minor_planet_list_bright_resolver: Callable[..., dict[str, Any]],
    supernova_list_recent_resolver: Callable[..., dict[str, Any]],
    planet_positions_resolver: Callable[..., dict[str, Any]],
) -> None:
    @server.tool(name="comet.list_bright")
    def comet_list_bright(
        maglim: float = 12.0,
        min_dec: float | None = None,
        location: str | int | None = None,
        date: str | None = None,
        limit: int = 20,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Currently bright comets, brightest first.

        Magnitudes and positions are refreshed several times a day from MPC and COBS.
        min_dec: minimal declination in degrees (e.g. -10 for objects visible from
        central Europe). With location (id, name or "lat,lon") also returns
        rise/transit/set for the night of date (default today).
        """
        return comet_list_bright_resolver(
            maglim=maglim, min_dec=min_dec, location=location, date=date, limit=limit, user_id=user_id,
        )

    @server.tool(name="minor_planet.list_bright")
    def minor_planet_list_bright(
        maglim: float = 10.0,
        min_elongation_deg: float | None = None,
        location: str | int | None = None,
        date: str | None = None,
        limit: int = 20,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Currently bright minor planets (asteroids), brightest first.

        min_elongation_deg filters out objects too close to the Sun. With location
        also returns rise/transit/set for the night of date (default today).
        """
        return minor_planet_list_bright_resolver(
            maglim=maglim,
            min_elongation_deg=min_elongation_deg,
            location=location,
            date=date,
            limit=limit,
            user_id=user_id,
        )

    @server.tool(name="supernova.list_recent")
    def supernova_list_recent(
        maglim: float = 16.0,
        days: int = 60,
        min_dec: float | None = None,
        location: str | int | None = None,
        date: str | None = None,
        limit: int = 20,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Recent bright supernovae (observed within the last `days`), brightest first.

        Data come from rochesterastronomy.org and are refreshed twice a day. With
        location also returns rise/transit/set for the night of date (default today).
        """
        return supernova_list_recent_resolver(
            maglim=maglim, days=days, min_dec=min_dec, location=location, date=date, limit=limit, user_id=user_id,
        )

    @server.tool(name="planet.positions")
    def planet_positions(
        date: str | None = None,
        location: str | int | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Positions of planets at local midnight of the night starting on date (default today).

        Returns magnitude, elongation from the Sun, distance, constellation and
        rise/transit/set at the location (default: user's most recently used location;
        omitted when the user has none).
        """
        return planet_positions_resolver(date=date, location=location, user_id=user_id)
