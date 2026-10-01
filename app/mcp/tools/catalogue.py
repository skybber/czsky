from __future__ import annotations

from typing import Any, Callable


def register_tools(
    server: Any,
    *,
    observed_list_resolver: Callable[..., dict[str, Any]],
    observed_stats_resolver: Callable[..., dict[str, Any]],
    dso_list_progress_resolver: Callable[..., dict[str, Any]],
    double_star_find_resolver: Callable[..., dict[str, Any]],
) -> None:
    @server.tool(name="observed.list")
    def observed_list(
        object_types: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """List objects the user has marked as observed, newest first.

        object_types: subset of "dso", "double_star", "comet", "minor_planet".
        Paginate with offset / nextOffset.
        """
        return observed_list_resolver(object_types=object_types, limit=limit, offset=offset, user_id=user_id)

    @server.tool(name="observed.stats")
    def observed_stats(user_id: int | None = None) -> dict[str, Any]:
        """Observing statistics: observed objects by type, DSO by type, sessions and log entries."""
        return observed_stats_resolver(user_id=user_id)

    @server.tool(name="dso_list.progress")
    def dso_list_progress(
        dso_list: str | int,
        include_missing: bool = True,
        missing_limit: int = 200,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Progress in an observing list such as Messier or Caldwell.

        dso_list: list id or name (e.g. "Messier"). Returns observed / missing counts,
        percent and (with include_missing) the missing objects in list order.
        """
        return dso_list_progress_resolver(
            dso_list=dso_list, include_missing=include_missing, missing_limit=missing_limit, user_id=user_id,
        )

    @server.tool(name="double_star.find")
    def double_star_find(
        constellation: str | None = None,
        mag_max: float | None = None,
        delta_mag_max: float | None = None,
        separation_min: float | None = None,
        separation_max: float | None = None,
        min_dec: float | None = None,
        not_observed: bool = True,
        location: str | int | None = None,
        date: str | None = None,
        limit: int = 20,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Find double stars, brightest primary first.

        constellation: IAU code or name. mag_max applies to both components.
        separation_min / separation_max in arcseconds (e.g. min 2 for a small
        telescope). min_dec in degrees. not_observed excludes double stars the user
        has already observed. With location also returns rise/transit/set for the
        night of date (default today).
        """
        return double_star_find_resolver(
            constellation=constellation,
            mag_max=mag_max,
            delta_mag_max=delta_mag_max,
            separation_min=separation_min,
            separation_max=separation_max,
            min_dec=min_dec,
            not_observed=not_observed,
            location=location,
            date=date,
            limit=limit,
            user_id=user_id,
        )
