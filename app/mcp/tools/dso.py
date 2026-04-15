from __future__ import annotations

from typing import Any, Callable


def register_tools(
    server: Any,
    *,
    dso_find_resolver: Callable[..., dict[str, Any]],
) -> None:
    @server.tool(name="dso.find")
    def dso_find(
        obj_source: str | None = None,
        dso_type: str | None = None,
        maglim: int | None = None,
        constellation: str | None = None,
        min_altitude: int = 5,
        session_plan_id: int | None = None,
        time_from: str | None = None,
        time_to: str | None = None,
        not_observed: bool = True,
        max_results: int = 20,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Find deep-sky objects matching given criteria, optionally filtered by visibility.

        Returns a list of matching DSO names and metadata. Use the returned names
        directly with session_plan.add_item or wishlist.add.

        obj_source values:
          - "WL"              — user's wish list (default for logged-in users)
          - "dso_list:<id>"   — specific DSO list by numeric id (use
                                session_plan.get_dso_list_id_by_name to resolve the id)
          - catalogue code    — e.g. "M" (Messier), "NGC", "IC", "Sh2" …

        dso_type values: "GX", "GC", "OC", "BN", "PN" (omit for all types).

        constellation: IAU 3-letter code (e.g. "Ori") or full constellation name.

        session_plan_id: when provided, uses the plan's location and date to compute
          visibility (rise/set/altitude). Objects already in the plan are excluded.
          Without session_plan_id, visibility filtering is skipped.

        time_from / time_to: "HH:MM" local-time strings defining the observation
          window. Requires session_plan_id. Defaults to the astronomical twilight
          window for the plan's date and location.

        not_observed: exclude objects the user has already observed (default true).

        max_results: 1–200, default 20.

        Each result includes: name, type, magnitude, constellation,
        and (when session_plan_id given) riseTime, meridianTime, setTime.
        """
        return dso_find_resolver(
            obj_source=obj_source,
            dso_type=dso_type,
            maglim=maglim,
            constellation=constellation,
            min_altitude=min_altitude,
            session_plan_id=session_plan_id,
            time_from=time_from,
            time_to=time_to,
            not_observed=not_observed,
            max_results=max_results,
            user_id=user_id,
        )
