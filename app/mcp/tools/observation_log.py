from __future__ import annotations

from typing import Any, Callable


def register_tools(
    server: Any,
    *,
    observation_log_upsert_resolver: Callable[..., dict[str, Any]],
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
