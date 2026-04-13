from __future__ import annotations

from typing import Any, Callable


SUPPORTED_OBJECT_TYPES = {"dso", "double_star"}


def _resolve_target_from_query(
    *,
    app: Any,
    query: str,
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
):
    stripped_query = (query or "").strip()
    if not stripped_query:
        raise ValueError("query must not be empty")

    with app.test_request_context("/", headers={"Host": "localhost"}):
        resolved = resolve_global_object_func(stripped_query)

    if not resolved:
        return None, "not_found"

    object_type = resolved.get("object_type")
    if object_type not in SUPPORTED_OBJECT_TYPES:
        return None, "unsupported_object_type"

    target = resolved.get("object")
    target_id = getattr(target, "id", None)
    if not isinstance(target_id, int) or target_id <= 0:
        return None, "not_found"

    return {
        "query": stripped_query,
        "objectType": object_type,
        "targetId": target_id,
        "objectId": f"{object_type}:{target_id}",
    }, None


def _find_matching_item(
    wish_list_items: list[Any],
    object_type: str,
    target_id: int,
):
    for item in wish_list_items:
        if object_type == "dso" and getattr(item, "dso_id", None) == target_id:
            return item
        if object_type == "double_star" and getattr(item, "double_star_id", None) == target_id:
            return item
    return None


def wishlist_contains_payload(
    *,
    query: str,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
    load_wishlist_items_for_user_func: Callable[[int], tuple[Any, list[Any]]],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_wishlist_user_id_func(user_id)

    app = get_app()
    with app.app_context():
        resolved_target, reason = _resolve_target_from_query(
            app=app,
            query=query,
            resolve_global_object_func=resolve_global_object_func,
        )
        if resolved_target is None:
            return {
                "query": (query or "").strip(),
                "contains": False,
                "reason": reason,
                "wishlistItemId": None,
                "objectId": None,
            }

        # Only load entries for the resolved user id, never across users.
        wish_list, wish_list_items = load_wishlist_items_for_user_func(resolved_user_id)
        if not wish_list:
            return {
                "query": resolved_target["query"],
                "contains": False,
                "reason": "not_in_wishlist",
                "wishlistItemId": None,
                "objectId": resolved_target["objectId"],
            }

        matched_item = _find_matching_item(
            wish_list_items,
            resolved_target["objectType"],
            resolved_target["targetId"],
        )
        if matched_item is None:
            return {
                "query": resolved_target["query"],
                "contains": False,
                "reason": "not_in_wishlist",
                "wishlistItemId": None,
                "objectId": resolved_target["objectId"],
            }

        return {
            "query": resolved_target["query"],
            "contains": True,
            "reason": "in_wishlist",
            "wishlistItemId": f"w_{matched_item.id}",
            "objectId": resolved_target["objectId"],
        }


def wishlist_find_payload(
    *,
    query: str,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
    load_wishlist_items_for_user_func: Callable[[int], tuple[Any, list[Any]]],
    load_observed_sets_for_user_wishlist_func: Callable[[int, int], tuple[set[int], set[int]]],
    build_wishlist_item_detail_func: Callable[[Any, set[int], set[int]], dict[str, Any] | None],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_wishlist_user_id_func(user_id)

    app = get_app()
    with app.app_context():
        resolved_target, reason = _resolve_target_from_query(
            app=app,
            query=query,
            resolve_global_object_func=resolve_global_object_func,
        )
        if resolved_target is None:
            return {
                "query": (query or "").strip(),
                "found": False,
                "reason": reason,
                "item": None,
            }

        # Only load entries for the resolved user id, never across users.
        wish_list, wish_list_items = load_wishlist_items_for_user_func(resolved_user_id)
        if not wish_list:
            return {
                "query": resolved_target["query"],
                "found": False,
                "reason": "not_in_wishlist",
                "item": None,
            }

        matched_item = _find_matching_item(
            wish_list_items,
            resolved_target["objectType"],
            resolved_target["targetId"],
        )
        if matched_item is None:
            return {
                "query": resolved_target["query"],
                "found": False,
                "reason": "not_in_wishlist",
                "item": None,
            }

        observed_dso_ids, observed_double_star_ids = load_observed_sets_for_user_wishlist_func(
            resolved_user_id,
            wish_list.id,
        )
        item_payload = build_wishlist_item_detail_func(
            matched_item,
            observed_dso_ids,
            observed_double_star_ids,
        )

        return {
            "query": resolved_target["query"],
            "found": item_payload is not None,
            "reason": "in_wishlist" if item_payload is not None else "not_in_wishlist",
            "item": item_payload,
        }
