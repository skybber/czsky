from __future__ import annotations

from typing import Any, Callable


def register_tools(
    server: Any,
    *,
    wishlist_list_resolver: Callable[..., dict[str, Any]],
    wishlist_get_resolver: Callable[..., dict[str, Any]],
    wishlist_stats_resolver: Callable[..., dict[str, Any]],
    wishlist_add_resolver: Callable[..., dict[str, Any]],
    wishlist_remove_resolver: Callable[..., dict[str, Any]],
    wishlist_bulk_add_resolver: Callable[..., dict[str, Any]],
    wishlist_bulk_remove_resolver: Callable[..., dict[str, Any]],
    wishlist_export_resolver: Callable[..., dict[str, Any]],
    wishlist_import_resolver: Callable[..., dict[str, Any]],
) -> None:
    @server.tool(name="wishlist.list")
    def wishlist_list(
        user_id: int | None = None,
        cursor: str | int | None = None,
        limit: int = 20,
        sort: str = "addedAt:desc",
        observed: bool | None = None,
        object_types: list[str] | None = None,
        constellations: list[str] | None = None,
    ) -> dict[str, Any]:
        """List wishlist items for the authenticated user.

        If MCP auth context is available, user identity and scopes are read from
        the token. In stub mode, pass user_id explicitly.
        """
        return wishlist_list_resolver(
            user_id=user_id,
            cursor=cursor,
            limit=limit,
            sort=sort,
            observed=observed,
            object_types=object_types,
            constellations=constellations,
        )

    @server.tool(name="wishlist.get")
    def wishlist_get(wishlist_item_id: str, user_id: int | None = None) -> dict[str, Any]:
        """Return details for a single wishlist item."""
        return wishlist_get_resolver(wishlist_item_id=wishlist_item_id, user_id=user_id)

    @server.tool(name="wishlist.stats")
    def wishlist_stats(user_id: int | None = None) -> dict[str, Any]:
        """Return aggregate wishlist statistics."""
        return wishlist_stats_resolver(user_id=user_id)

    @server.tool(name="wishlist.add")
    def wishlist_add(
        object_id: str | None = None,
        query: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Add an object to wishlist by object_id or query."""
        return wishlist_add_resolver(object_id=object_id, query=query, user_id=user_id)

    @server.tool(name="wishlist.remove")
    def wishlist_remove(wishlist_item_id: str, user_id: int | None = None) -> dict[str, Any]:
        """Remove a wishlist item by id."""
        return wishlist_remove_resolver(wishlist_item_id=wishlist_item_id, user_id=user_id)

    @server.tool(name="wishlist.bulk_add")
    def wishlist_bulk_add(objects: list[str], user_id: int | None = None) -> dict[str, Any]:
        """Add multiple wishlist objects in one call."""
        return wishlist_bulk_add_resolver(objects=objects, user_id=user_id)

    @server.tool(name="wishlist.bulk_remove")
    def wishlist_bulk_remove(
        wishlist_item_ids: list[str],
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Remove multiple wishlist items in one call."""
        return wishlist_bulk_remove_resolver(wishlist_item_ids=wishlist_item_ids, user_id=user_id)

    @server.tool(name="wishlist.export")
    def wishlist_export(format: str = "json", user_id: int | None = None) -> dict[str, Any]:
        """Export wishlist into JSON or CSV content."""
        return wishlist_export_resolver(format=format, user_id=user_id)

    @server.tool(name="wishlist.import")
    def wishlist_import(
        content: str,
        format: str = "json",
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Import wishlist from JSON or CSV content."""
        return wishlist_import_resolver(content=content, format=format, user_id=user_id)
