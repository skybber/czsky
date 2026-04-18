from __future__ import annotations

from typing import Any, Callable


def register_tools(
    server: Any,
    *,
    observing_session_create_resolver: Callable[..., dict[str, Any]],
    observing_session_set_active_resolver: Callable[..., dict[str, Any]],
    observing_session_get_active_resolver: Callable[..., dict[str, Any]],
) -> None:
    @server.tool(name="observing_session.create")
    def observing_session_create(
        date_from: str,
        date_to: str,
        location_id: int | str | None = None,
        location_name: str | None = None,
        location: str | int | None = None,
        title: str | None = None,
        sqm: float | str | None = None,
        faintest_star: float | str | None = None,
        seeing: str | None = None,
        transparency: str | None = None,
        weather: str | None = None,
        equipment: str | None = None,
        notes: str | None = None,
        is_public: bool = False,
        is_finished: bool = False,
        is_active: bool = False,
        rating: int | str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Create an observing session for one observing night."""
        return observing_session_create_resolver(
            date_from=date_from,
            date_to=date_to,
            location_id=location_id,
            location_name=location_name,
            location=location,
            title=title,
            sqm=sqm,
            faintest_star=faintest_star,
            seeing=seeing,
            transparency=transparency,
            weather=weather,
            equipment=equipment,
            notes=notes,
            is_public=is_public,
            is_finished=is_finished,
            is_active=is_active,
            rating=rating,
            user_id=user_id,
        )


    @server.tool(name="observing_session.set_active")
    def observing_session_set_active(
        observing_session_id: int,
        is_active: bool = True,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Set an observing session active or inactive."""
        return observing_session_set_active_resolver(
            observing_session_id=observing_session_id,
            is_active=is_active,
            user_id=user_id,
        )

    @server.tool(name="observing_session.get_active")
    def observing_session_get_active(
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Return the current active observing session for the user."""
        return observing_session_get_active_resolver(user_id=user_id)
