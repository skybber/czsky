from __future__ import annotations

from typing import Any, Callable


def register_tools(
    server: Any,
    *,
    session_plan_create_resolver: Callable[..., dict[str, Any]],
    session_plan_get_resolver: Callable[..., dict[str, Any]],
    session_plan_list_resolver: Callable[..., dict[str, Any]],
    session_plan_get_id_by_date_resolver: Callable[..., dict[str, Any]],
    session_plan_items_resolver: Callable[..., dict[str, Any]],
    session_plan_add_item_resolver: Callable[..., dict[str, Any]],
    session_plan_add_items_resolver: Callable[..., dict[str, Any]],
    session_plan_remove_item_resolver: Callable[..., dict[str, Any]],
    session_plan_remove_items_resolver: Callable[..., dict[str, Any]],
    session_plan_clear_resolver: Callable[..., dict[str, Any]],
    dso_list_get_id_by_name_resolver: Callable[..., dict[str, Any]],
) -> None:
    @server.tool(name="session_plan.create")
    def session_plan_create(
        for_date: str,
        location_id: int | str | None = None,
        location_name: str | None = None,
        location: str | int | None = None,
        title: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Create session plan for a date and location id/name."""
        return session_plan_create_resolver(
            for_date=for_date,
            location_id=location_id,
            location_name=location_name,
            location=location,
            title=title,
            user_id=user_id,
        )

    @server.tool(name="session_plan.get")
    def session_plan_get(
        session_plan_id: int,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Get one session plan with its items by id."""
        return session_plan_get_resolver(session_plan_id=session_plan_id, user_id=user_id)

    @server.tool(name="session_plan.list")
    def session_plan_list(
        for_date: str | None = None,
        include_archived: bool = False,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """List user's session plans, optionally filtered by date."""
        return session_plan_list_resolver(
            for_date=for_date,
            include_archived=include_archived,
            user_id=user_id,
        )

    @server.tool(name="session_plan.get_id_by_date")
    def session_plan_get_id_by_date(
        for_date: str,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Get current user's session plan id(s) for a date."""
        return session_plan_get_id_by_date_resolver(for_date=for_date, user_id=user_id)

    @server.tool(name="session_plan.add_item")
    def session_plan_add_item(
        session_plan_id: int,
        query: str,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Add an object to a session plan by object name/query."""
        return session_plan_add_item_resolver(
            session_plan_id=session_plan_id,
            query=query,
            user_id=user_id,
        )

    @server.tool(name="session_plan.add_items")
    def session_plan_add_items(
        session_plan_id: int,
        queries: list[str],
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Add multiple objects to a session plan by object name/query."""
        return session_plan_add_items_resolver(
            session_plan_id=session_plan_id,
            queries=queries,
            user_id=user_id,
        )

    @server.tool(name="session_plan.items")
    def session_plan_items(
        session_plan_id: int,
        object_types: list[str] | None = None,
        dso_list_id: int | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """List items in a session plan, optionally filtered by object type or DSO list."""
        return session_plan_items_resolver(
            session_plan_id=session_plan_id,
            object_types=object_types,
            dso_list_id=dso_list_id,
            user_id=user_id,
        )

    @server.tool(name="session_plan.remove_item")
    def session_plan_remove_item(
        session_plan_id: int,
        query: str,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Remove an object from a session plan by object name/query."""
        return session_plan_remove_item_resolver(
            session_plan_id=session_plan_id,
            query=query,
            user_id=user_id,
        )

    @server.tool(name="session_plan.remove_items")
    def session_plan_remove_items(
        session_plan_id: int,
        queries: list[str],
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Remove multiple objects from a session plan by object name/query."""
        return session_plan_remove_items_resolver(
            session_plan_id=session_plan_id,
            queries=queries,
            user_id=user_id,
        )

    @server.tool(name="session_plan.clear")
    def session_plan_clear(
        session_plan_id: int,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Remove all items from a session plan."""
        return session_plan_clear_resolver(
            session_plan_id=session_plan_id,
            user_id=user_id,
        )

    @server.tool(name="session_plan.get_dso_list_id_by_name")
    def dso_list_get_id_by_name(
        name: str,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Find a DSO list ID by its name or long name.

        Returns an exact match when unique, or a list of candidates when the name
        is ambiguous or only partially matched. Use the returned dsoListId as the
        dso_list_id parameter when filtering session plan items by DSO list.
        """
        return dso_list_get_id_by_name_resolver(name=name, user_id=user_id)
