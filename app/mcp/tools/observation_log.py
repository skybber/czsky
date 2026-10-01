from __future__ import annotations

from typing import Any, Callable


def register_tools(
    server: Any,
    *,
    observation_log_upsert_resolver: Callable[..., dict[str, Any]],
    observation_log_list_resolver: Callable[..., dict[str, Any]],
    observation_log_get_resolver: Callable[..., dict[str, Any]],
) -> None:
    @server.tool(name="observation_log.upsert")
    def observation_log_upsert(
        object_id: str | None = None,
        query: str | None = None,
        observing_session_id: int | str | None = None,
        notes: str | None = None,
        date_from: str | None = None,
        telescope_id: int | str | None = None,
        eyepiece_id: int | str | None = None,
        filter_id: int | str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Create or update an observation log for a resolved target in a session."""
        return observation_log_upsert_resolver(
            object_id=object_id,
            query=query,
            observing_session_id=observing_session_id,
            notes=notes,
            date_from=date_from,
            telescope_id=telescope_id,
            eyepiece_id=eyepiece_id,
            filter_id=filter_id,
            user_id=user_id,
        )

    @server.tool(name="observation_log.list")
    def observation_log_list(
        query: str | None = None,
        object_id: str | None = None,
        observing_session_id: int | str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 20,
        offset: int = 0,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """List the user's observation log entries, newest first.

        Filter by object (query such as "M13" or object_id such as "dso:123"), by
        observing session or by ISO date range. Notes are shortened to notesPreview;
        use observation_log.get for the full entry. Paginate with offset / nextOffset.
        """
        return observation_log_list_resolver(
            query=query,
            object_id=object_id,
            observing_session_id=observing_session_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
            user_id=user_id,
        )

    @server.tool(name="observation_log.get")
    def observation_log_get(
        observation_id: int,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Full observation log entry including notes, equipment and conditions."""
        return observation_log_get_resolver(observation_id=observation_id, user_id=user_id)
