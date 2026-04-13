from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Callable


def to_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def build_wishlist_item_summary(
    item: Any,
    observed_dso_ids: set[int],
    observed_double_star_ids: set[int],
    *,
    to_iso_func: Callable[[datetime | None], str | None],
):
    added_at = getattr(item, "create_date", None)
    updated_at = getattr(item, "update_date", None)

    if item.dso_id is not None and item.deepsky_object is not None:
        dso = item.deepsky_object
        payload = {
            "wishlistItemId": f"w_{item.id}",
            "objectId": f"dso:{dso.id}",
            "identifier": dso.name,
            "name": dso.denormalized_name(),
            "itemType": "dso",
            "objectType": dso.type or "dso",
            "constellation": dso.get_constellation_iau_code(),
            "magnitude": dso.mag,
            "order": item.order,
            "observed": item.dso_id in observed_dso_ids,
            "addedAt": to_iso_func(added_at),
            "updatedAt": to_iso_func(updated_at),
        }
    elif item.double_star_id is not None and item.double_star is not None:
        double_star = item.double_star
        payload = {
            "wishlistItemId": f"w_{item.id}",
            "objectId": f"double_star:{double_star.id}",
            "identifier": double_star.common_cat_id or double_star.wds_number,
            "name": double_star.get_common_name(),
            "itemType": "double_star",
            "objectType": "double_star",
            "constellation": double_star.get_constellation_iau_code(),
            "magnitude": double_star.mag_first,
            "order": item.order,
            "observed": item.double_star_id in observed_double_star_ids,
            "addedAt": to_iso_func(added_at),
            "updatedAt": to_iso_func(updated_at),
        }
    else:
        return None

    return {
        "item": payload,
        "added_at": added_at,
        "updated_at": updated_at,
        "magnitude": payload.get("magnitude"),
        "name_sort": str(payload.get("name") or "").casefold(),
    }


def build_wishlist_item_detail(
    item: Any,
    observed_dso_ids: set[int],
    observed_double_star_ids: set[int],
    *,
    build_wishlist_item_summary_func: Callable[[Any, set[int], set[int]], dict[str, Any] | None],
) -> dict[str, Any] | None:
    entry = build_wishlist_item_summary_func(item, observed_dso_ids, observed_double_star_ids)
    if entry is None:
        return None

    payload = dict(entry["item"])

    if item.dso_id is not None and item.deepsky_object is not None:
        dso = item.deepsky_object
        payload["coordinates"] = {
            "ra": dso.ra,
            "dec": dso.dec,
            "raStr": dso.ra_str_short(),
            "decStr": dso.dec_str_short(),
        }
        payload["details"] = {
            "subtype": dso.subtype,
            "surfaceBrightness": dso.surface_bright,
            "positionAngle": dso.position_angle,
            "majorAxis": dso.major_axis,
            "minorAxis": dso.minor_axis,
            "distance": dso.distance,
        }
    elif item.double_star_id is not None and item.double_star is not None:
        double_star = item.double_star
        payload["coordinates"] = {
            "ra": double_star.ra_first,
            "dec": double_star.dec_first,
            "raStr": double_star.ra_first_str_short(),
            "decStr": double_star.dec_first_str_short(),
        }
        payload["details"] = {
            "wdsNumber": double_star.wds_number,
            "components": double_star.components,
            "positionAngle": double_star.pos_angle,
            "separation": double_star.separation,
            "magFirst": double_star.mag_first,
            "magSecond": double_star.mag_second,
            "deltaMag": double_star.delta_mag,
            "spectralType": double_star.spectral_type,
        }
    return payload


def wishlist_list_payload(
    *,
    user_id: int | None,
    cursor: str | int | None,
    limit: int,
    sort: str,
    observed: bool | None,
    object_types: list[str] | None,
    constellations: list[str] | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    get_app: Callable[[], Any],
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    validate_wishlist_limit_func: Callable[[int], int],
    parse_wishlist_cursor_func: Callable[[str | int | None], int],
    load_wishlist_items_for_user_func: Callable[[int], tuple[Any, list[Any]]],
    load_observed_sets_for_user_wishlist_func: Callable[[int, int], tuple[set[int], set[int]]],
    build_wishlist_item_summary_func: Callable[[Any, set[int], set[int]], dict[str, Any] | None],
    apply_wishlist_filters_func: Callable[[list[dict[str, Any]], bool | None, list[str] | None, list[str] | None], list[dict[str, Any]]],
    sort_wishlist_entries_func: Callable[[list[dict[str, Any]], str], list[dict[str, Any]]],
    paginate_entries_func: Callable[[list[dict[str, Any]], int, int], tuple[list[dict[str, Any]], str | None, bool]],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)

    app = get_app()
    with app.app_context():
        resolved_user_id = resolve_wishlist_user_id_func(user_id)
        valid_limit = validate_wishlist_limit_func(limit)
        offset = parse_wishlist_cursor_func(cursor)

        wish_list, wish_list_items = load_wishlist_items_for_user_func(resolved_user_id)
        if not wish_list:
            return {"items": [], "nextCursor": None, "hasMore": False}

        observed_dso_ids, observed_double_star_ids = load_observed_sets_for_user_wishlist_func(
            resolved_user_id, wish_list.id
        )

        entries = []
        for item in wish_list_items:
            entry = build_wishlist_item_summary_func(item, observed_dso_ids, observed_double_star_ids)
            if entry is not None:
                entries.append(entry)

        filtered_entries = apply_wishlist_filters_func(entries, observed, object_types, constellations)
        ordered_entries = sort_wishlist_entries_func(filtered_entries, sort)
        page_entries, next_cursor, has_more = paginate_entries_func(ordered_entries, offset, valid_limit)

        return {
            "items": [entry["item"] for entry in page_entries],
            "nextCursor": next_cursor,
            "hasMore": has_more,
        }


def wishlist_get_payload(
    *,
    wishlist_item_id: str,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    get_app: Callable[[], Any],
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    parse_wishlist_item_id_func: Callable[[str | int], int],
    load_wishlist_items_for_user_func: Callable[[int], tuple[Any, list[Any]]],
    load_observed_sets_for_user_wishlist_func: Callable[[int, int], tuple[set[int], set[int]]],
    build_wishlist_item_detail_func: Callable[[Any, set[int], set[int]], dict[str, Any] | None],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)

    app = get_app()
    with app.app_context():
        resolved_user_id = resolve_wishlist_user_id_func(user_id)
        target_item_id = parse_wishlist_item_id_func(wishlist_item_id)

        wish_list, wish_list_items = load_wishlist_items_for_user_func(resolved_user_id)
        if not wish_list:
            return {"found": False, "item": None}

        matched_item = next((item for item in wish_list_items if item.id == target_item_id), None)
        if matched_item is None:
            return {"found": False, "item": None}

        observed_dso_ids, observed_double_star_ids = load_observed_sets_for_user_wishlist_func(
            resolved_user_id, wish_list.id
        )
        item_payload = build_wishlist_item_detail_func(
            matched_item,
            observed_dso_ids,
            observed_double_star_ids,
        )

        return {"found": item_payload is not None, "item": item_payload}


def wishlist_stats_payload(
    *,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    get_app: Callable[[], Any],
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    load_wishlist_items_for_user_func: Callable[[int], tuple[Any, list[Any]]],
    load_observed_sets_for_user_wishlist_func: Callable[[int, int], tuple[set[int], set[int]]],
    build_wishlist_item_summary_func: Callable[[Any, set[int], set[int]], dict[str, Any] | None],
    to_iso_func: Callable[[datetime | None], str | None],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)

    app = get_app()
    with app.app_context():
        resolved_user_id = resolve_wishlist_user_id_func(user_id)
        wish_list, wish_list_items = load_wishlist_items_for_user_func(resolved_user_id)

        if not wish_list:
            return {
                "total": 0,
                "observed": 0,
                "unobserved": 0,
                "byItemType": {},
                "byObjectType": {},
                "updatedAt": None,
            }

        observed_dso_ids, observed_double_star_ids = load_observed_sets_for_user_wishlist_func(
            resolved_user_id, wish_list.id
        )

        total = 0
        observed_count = 0
        unobserved_count = 0
        by_item_type: Counter[str] = Counter()
        by_object_type: Counter[str] = Counter()
        updated_candidates: list[datetime] = []

        for item in wish_list_items:
            entry = build_wishlist_item_summary_func(item, observed_dso_ids, observed_double_star_ids)
            if entry is None:
                continue
            payload = entry["item"]

            total += 1
            if payload["observed"]:
                observed_count += 1
            else:
                unobserved_count += 1

            by_item_type[payload["itemType"]] += 1
            by_object_type[payload["objectType"]] += 1

            if entry["updated_at"]:
                updated_candidates.append(entry["updated_at"])
            elif entry["added_at"]:
                updated_candidates.append(entry["added_at"])

        return {
            "total": total,
            "observed": observed_count,
            "unobserved": unobserved_count,
            "byItemType": dict(by_item_type),
            "byObjectType": dict(by_object_type),
            "updatedAt": to_iso_func(max(updated_candidates) if updated_candidates else None),
        }
