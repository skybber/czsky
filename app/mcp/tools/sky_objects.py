from __future__ import annotations

from typing import Any, Callable


def register_tools(
    server: Any,
    *,
    resolve_sky_object_resolver: Callable[[str], dict[str, Any]],
    comet_observations_resolver: Callable[[str, int], dict[str, Any]],
) -> None:
    @server.tool()
    def resolve_sky_object(query: str) -> dict[str, Any]:
        """Find an astronomical object in the local CzSkY database.

        Accepts identifiers and names such as M31, NGC891, Saturn, Moon, comet
        designations, minor planets, stars, double stars, and constellation
        names. Returns the first match using the same priority as the CzSkY
        global search. For comets, the payload may also include recent local
        COBS observations stored in the CzSkY database.
        """
        return resolve_sky_object_resolver(query)

    @server.tool()
    def get_comet_recent_observations(query: str, limit: int = 5) -> dict[str, Any]:
        """Return recent local COBS observations for a comet from the CzSkY database.

        Accepts the same comet identifiers or names as resolve_sky_object, for
        example 88P/Howell or C/2023 A3. Returns only comet-specific recent
        observation reports stored in the local database.
        """
        return comet_observations_resolver(query, limit=limit)
