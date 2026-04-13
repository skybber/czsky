from __future__ import annotations

import re
from datetime import datetime
from typing import Any

MAX_WISHLIST_PAGE_SIZE = 100
CURSOR_PATTERN = re.compile(r"^\d+$")
WISHLIST_ITEM_PATTERN = re.compile(r"^w_(\d+)$")


def parse_wishlist_cursor(cursor: str | int | None) -> int:
    if cursor is None or cursor == "":
        return 0

    if isinstance(cursor, int):
        if cursor < 0:
            raise ValueError("cursor must be non-negative")
        return cursor

    if not isinstance(cursor, str):
        raise ValueError("cursor must be a string")

    stripped = cursor.strip()
    if not CURSOR_PATTERN.match(stripped):
        raise ValueError("cursor must be a non-negative integer string")

    return int(stripped)


def parse_wishlist_item_id(wishlist_item_id: str | int) -> int:
    if isinstance(wishlist_item_id, int):
        if wishlist_item_id <= 0:
            raise ValueError("wishlist_item_id must be positive")
        return wishlist_item_id

    if not isinstance(wishlist_item_id, str):
        raise ValueError("wishlist_item_id must be a string")

    stripped = wishlist_item_id.strip()
    if stripped.isdigit():
        parsed = int(stripped)
        if parsed > 0:
            return parsed

    matched = WISHLIST_ITEM_PATTERN.match(stripped)
    if matched:
        parsed = int(matched.group(1))
        if parsed > 0:
            return parsed

    raise ValueError("wishlist_item_id must be in format w_<id> or numeric id")


def validate_wishlist_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer")
    if limit < 1 or limit > MAX_WISHLIST_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_WISHLIST_PAGE_SIZE}")
    return limit


def apply_wishlist_filters(
    entries: list[dict[str, Any]],
    observed: bool | None,
    object_types: list[str] | None,
    constellations: list[str] | None,
) -> list[dict[str, Any]]:
    filtered = list(entries)

    if observed is not None:
        filtered = [entry for entry in filtered if entry["item"]["observed"] is observed]

    if object_types:
        allowed_object_types = {
            value.strip().lower()
            for value in object_types
            if isinstance(value, str) and value.strip()
        }
        filtered = [
            entry
            for entry in filtered
            if str(entry["item"].get("objectType") or "").lower() in allowed_object_types
        ]

    if constellations:
        allowed_constellations = {
            value.strip().upper()
            for value in constellations
            if isinstance(value, str) and value.strip()
        }
        filtered = [
            entry
            for entry in filtered
            if str(entry["item"].get("constellation") or "").upper() in allowed_constellations
        ]

    return filtered


def sort_wishlist_entries(entries: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    ordered = list(entries)

    if sort == "addedAt:desc":
        ordered.sort(key=lambda entry: entry["added_at"] or datetime.min, reverse=True)
        return ordered
    if sort == "addedAt:asc":
        ordered.sort(key=lambda entry: entry["added_at"] or datetime.min)
        return ordered
    if sort == "magnitude:asc":
        ordered.sort(
            key=lambda entry: (
                entry["magnitude"] is None,
                entry["magnitude"] if entry["magnitude"] is not None else float("inf"),
                entry["name_sort"],
            )
        )
        return ordered
    if sort == "name:asc":
        ordered.sort(key=lambda entry: entry["name_sort"])
        return ordered

    raise ValueError("Unsupported sort option")


def paginate_entries(entries: list[dict[str, Any]], offset: int, limit: int):
    page_plus_one = entries[offset:offset + limit + 1]
    has_more = len(page_plus_one) > limit
    page_entries = page_plus_one[:limit]
    next_cursor = str(offset + limit) if has_more else None
    return page_entries, next_cursor, has_more
