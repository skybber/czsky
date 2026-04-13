from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Callable

OBJECT_ID_PATTERN = re.compile(r"^(dso|double_star):(\d+)$", re.IGNORECASE)


def parse_wishlist_object_id(object_id: str | None) -> tuple[str, int] | None:
    if object_id is None:
        return None
    if not isinstance(object_id, str):
        raise ValueError("object_id must be a string")

    stripped = object_id.strip()
    if not stripped:
        return None

    matched = OBJECT_ID_PATTERN.match(stripped)
    if not matched:
        raise ValueError("object_id must be in format dso:<id> or double_star:<id>")

    object_type = matched.group(1).lower()
    target_id = int(matched.group(2))
    if target_id <= 0:
        raise ValueError("object_id numeric part must be positive")

    return object_type, target_id


def _normalize_transfer_format(transfer_format: str | None) -> str:
    normalized = (transfer_format or "json").strip().lower()
    if normalized not in {"json", "csv"}:
        raise ValueError("format must be either 'json' or 'csv'")
    return normalized


def _resolve_target_from_object_reference(
    *,
    object_id: str,
    parse_wishlist_object_id_func: Callable[[str | None], tuple[str, int] | None],
):
    from app.models import DeepskyObject, DoubleStar

    parsed = parse_wishlist_object_id_func(object_id)
    if parsed is None:
        return None, "not_found"

    object_type, target_id = parsed
    if object_type == "dso":
        resolved = DeepskyObject.query.filter_by(id=target_id).first()
    else:
        resolved = DoubleStar.query.filter_by(id=target_id).first()

    if resolved is None:
        return None, "not_found"

    return {
        "objectType": object_type,
        "targetId": target_id,
        "resolvedObjectId": f"{object_type}:{target_id}",
    }, None


def _resolve_target_from_query(
    *,
    app: Any,
    query: str,
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
):
    stripped_query = (query or "").strip()
    if not stripped_query:
        return None, "missing_query"

    with app.test_request_context("/", headers={"Host": "localhost"}):
        resolved = resolve_global_object_func(stripped_query)

    if not resolved:
        return None, "not_found"

    object_type = resolved.get("object_type")
    if object_type not in {"dso", "double_star"}:
        return None, "unsupported_object_type"

    target = resolved.get("object")
    target_id = getattr(target, "id", None)
    if not isinstance(target_id, int) or target_id <= 0:
        return None, "not_found"

    return {
        "objectType": object_type,
        "targetId": target_id,
        "resolvedObjectId": f"{object_type}:{target_id}",
    }, None


def _resolve_wishlist_target(
    *,
    app: Any,
    object_id: str | None,
    query: str | None,
    parse_wishlist_object_id_func: Callable[[str | None], tuple[str, int] | None],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
):
    stripped_object_id = (object_id or "").strip()
    stripped_query = (query or "").strip()

    if stripped_object_id:
        return _resolve_target_from_object_reference(
            object_id=stripped_object_id,
            parse_wishlist_object_id_func=parse_wishlist_object_id_func,
        )

    if stripped_query:
        return _resolve_target_from_query(
            app=app,
            query=stripped_query,
            resolve_global_object_func=resolve_global_object_func,
        )

    raise ValueError("Provide object_id or query")


def _find_wishlist_item_by_target(wish_list_id: int, object_type: str, target_id: int):
    from app.models import WishListItem

    if object_type == "dso":
        return WishListItem.query.filter_by(wish_list_id=wish_list_id, dso_id=target_id).first()

    return WishListItem.query.filter_by(
        wish_list_id=wish_list_id,
        double_star_id=target_id,
    ).first()


def _create_wishlist_item_for_target(wish_list: Any, object_type: str, target_id: int):
    if object_type == "dso":
        return wish_list.create_new_deepsky_object_item(target_id)
    return wish_list.create_new_double_star_item(target_id)


def _item_key(item: Any) -> tuple[str, int] | None:
    if getattr(item, "dso_id", None) is not None:
        return "dso", item.dso_id
    if getattr(item, "double_star_id", None) is not None:
        return "double_star", item.double_star_id
    return None


def _build_item_ref(item: Any) -> dict[str, Any]:
    if getattr(item, "dso_id", None) is not None:
        object_id = f"dso:{item.dso_id}"
    elif getattr(item, "double_star_id", None) is not None:
        object_id = f"double_star:{item.double_star_id}"
    else:
        object_id = None

    return {
        "wishlistItemId": f"w_{item.id}",
        "objectId": object_id,
    }


def _build_item_detail_if_available(
    *,
    item: Any,
    user_id: int,
    wish_list_id: int,
    load_observed_sets_for_user_wishlist_func: Callable[[int, int], tuple[set[int], set[int]]],
    build_wishlist_item_detail_func: Callable[[Any, set[int], set[int]], dict[str, Any] | None],
) -> dict[str, Any] | None:
    observed_dso_ids, observed_double_star_ids = load_observed_sets_for_user_wishlist_func(
        user_id,
        wish_list_id,
    )
    return build_wishlist_item_detail_func(item, observed_dso_ids, observed_double_star_ids)


def wishlist_add_payload(
    *,
    object_id: str | None,
    query: str | None,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
    parse_wishlist_object_id_func: Callable[[str | None], tuple[str, int] | None],
    load_observed_sets_for_user_wishlist_func: Callable[[int, int], tuple[set[int], set[int]]],
    build_wishlist_item_detail_func: Callable[[Any, set[int], set[int]], dict[str, Any] | None],
) -> dict[str, Any]:
    from app import db
    from app.models import WishList

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_wishlist_user_id_func(user_id)

    app = get_app()
    with app.app_context():
        resolved_target, reason = _resolve_wishlist_target(
            app=app,
            object_id=object_id,
            query=query,
            parse_wishlist_object_id_func=parse_wishlist_object_id_func,
            resolve_global_object_func=resolve_global_object_func,
        )
        if resolved_target is None:
            return {
                "added": False,
                "reason": reason,
                "item": None,
                "resolvedObjectId": None,
            }

        wish_list = WishList.create_get_wishlist_by_user_id(resolved_user_id)

        existing_item = _find_wishlist_item_by_target(
            wish_list.id,
            resolved_target["objectType"],
            resolved_target["targetId"],
        )
        if existing_item is not None:
            detail = _build_item_detail_if_available(
                item=existing_item,
                user_id=resolved_user_id,
                wish_list_id=wish_list.id,
                load_observed_sets_for_user_wishlist_func=load_observed_sets_for_user_wishlist_func,
                build_wishlist_item_detail_func=build_wishlist_item_detail_func,
            )
            return {
                "added": False,
                "reason": "already_exists",
                "item": detail,
                "resolvedObjectId": resolved_target["resolvedObjectId"],
            }

        new_item = _create_wishlist_item_for_target(
            wish_list,
            resolved_target["objectType"],
            resolved_target["targetId"],
        )
        db.session.add(new_item)
        db.session.commit()

        detail = _build_item_detail_if_available(
            item=new_item,
            user_id=resolved_user_id,
            wish_list_id=wish_list.id,
            load_observed_sets_for_user_wishlist_func=load_observed_sets_for_user_wishlist_func,
            build_wishlist_item_detail_func=build_wishlist_item_detail_func,
        )
        return {
            "added": True,
            "reason": "added",
            "item": detail,
            "resolvedObjectId": resolved_target["resolvedObjectId"],
        }


def wishlist_remove_payload(
    *,
    wishlist_item_id: str,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    parse_wishlist_item_id_func: Callable[[str | int], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app import db
    from app.models import WishList, WishListItem

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_wishlist_user_id_func(user_id)
    target_item_id = parse_wishlist_item_id_func(wishlist_item_id)

    app = get_app()
    with app.app_context():
        wish_list = WishList.query.filter_by(user_id=resolved_user_id).first()
        if not wish_list:
            return {
                "removed": False,
                "reason": "not_found",
                "wishlistItemId": f"w_{target_item_id}",
            }

        wish_list_item = WishListItem.query.filter_by(
            id=target_item_id,
            wish_list_id=wish_list.id,
        ).first()
        if wish_list_item is None:
            return {
                "removed": False,
                "reason": "not_found",
                "wishlistItemId": f"w_{target_item_id}",
            }

        db.session.delete(wish_list_item)
        db.session.commit()

        return {
            "removed": True,
            "reason": "removed",
            "wishlistItemId": f"w_{target_item_id}",
        }


def _bulk_add_objects_for_user(
    *,
    object_inputs: list[str],
    resolved_user_id: int,
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
    parse_wishlist_object_id_func: Callable[[str | None], tuple[str, int] | None],
) -> tuple[list[dict[str, Any]], int, int]:
    from app import db
    from app.models import WishList

    if isinstance(object_inputs, str) or not isinstance(object_inputs, list):
        raise ValueError("objects must be a list of strings")

    app = get_app()
    with app.app_context():
        wish_list = WishList.create_get_wishlist_by_user_id(resolved_user_id)

        existing_items_by_key: dict[tuple[str, int], Any] = {}
        for item in wish_list.wish_list_items:
            key = _item_key(item)
            if key is not None:
                existing_items_by_key[key] = item

        results: list[dict[str, Any]] = []
        new_items: list[Any] = []

        for raw_input in object_inputs:
            if not isinstance(raw_input, str):
                results.append(
                    {
                        "input": raw_input,
                        "added": False,
                        "reason": "invalid_input",
                        "item": None,
                    }
                )
                continue

            stripped_input = raw_input.strip()
            if not stripped_input:
                results.append(
                    {
                        "input": raw_input,
                        "added": False,
                        "reason": "invalid_input",
                        "item": None,
                    }
                )
                continue

            lower_input = stripped_input.lower()
            has_object_prefix = lower_input.startswith("dso:") or lower_input.startswith("double_star:")

            if has_object_prefix:
                try:
                    resolved_target, reason = _resolve_target_from_object_reference(
                        object_id=stripped_input,
                        parse_wishlist_object_id_func=parse_wishlist_object_id_func,
                    )
                except ValueError:
                    resolved_target, reason = None, "invalid_input"
            else:
                resolved_target, reason = _resolve_target_from_query(
                    app=app,
                    query=stripped_input,
                    resolve_global_object_func=resolve_global_object_func,
                )

            if resolved_target is None:
                results.append(
                    {
                        "input": raw_input,
                        "added": False,
                        "reason": reason,
                        "item": None,
                    }
                )
                continue

            key = (resolved_target["objectType"], resolved_target["targetId"])
            existing_item = existing_items_by_key.get(key)
            if existing_item is not None:
                results.append(
                    {
                        "input": raw_input,
                        "added": False,
                        "reason": "already_exists",
                        "item": _build_item_ref(existing_item),
                    }
                )
                continue

            new_item = _create_wishlist_item_for_target(
                wish_list,
                resolved_target["objectType"],
                resolved_target["targetId"],
            )
            db.session.add(new_item)
            new_items.append(new_item)
            existing_items_by_key[key] = new_item

            results.append(
                {
                    "input": raw_input,
                    "added": True,
                    "reason": "added",
                    "item": None,
                    "_wishlist_item_obj": new_item,
                }
            )

        if new_items:
            db.session.commit()

        for result in results:
            pending_item = result.pop("_wishlist_item_obj", None)
            if pending_item is not None:
                result["item"] = _build_item_ref(pending_item)

        added_count = sum(1 for result in results if result["added"])
        skipped_count = len(results) - added_count
        return results, added_count, skipped_count


def wishlist_bulk_add_payload(
    *,
    objects: list[str],
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
    parse_wishlist_object_id_func: Callable[[str | None], tuple[str, int] | None],
) -> dict[str, Any]:
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_wishlist_user_id_func(user_id)

    results, added_count, skipped_count = _bulk_add_objects_for_user(
        object_inputs=objects,
        resolved_user_id=resolved_user_id,
        get_app=get_app,
        resolve_global_object_func=resolve_global_object_func,
        parse_wishlist_object_id_func=parse_wishlist_object_id_func,
    )

    return {
        "total": len(results),
        "added": added_count,
        "skipped": skipped_count,
        "results": results,
    }


def wishlist_bulk_remove_payload(
    *,
    wishlist_item_ids: list[str],
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    parse_wishlist_item_id_func: Callable[[str | int], int],
    get_app: Callable[[], Any],
) -> dict[str, Any]:
    from app import db
    from app.models import WishList, WishListItem

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_wishlist_user_id_func(user_id)

    if isinstance(wishlist_item_ids, str) or not isinstance(wishlist_item_ids, list):
        raise ValueError("wishlist_item_ids must be a list")

    app = get_app()
    with app.app_context():
        wish_list = WishList.query.filter_by(user_id=resolved_user_id).first()

        results: list[dict[str, Any]] = []
        removed_count = 0

        for raw_item_id in wishlist_item_ids:
            try:
                target_item_id = parse_wishlist_item_id_func(raw_item_id)
            except ValueError:
                results.append(
                    {
                        "wishlistItemId": str(raw_item_id),
                        "removed": False,
                        "reason": "invalid_input",
                    }
                )
                continue

            if not wish_list:
                results.append(
                    {
                        "wishlistItemId": f"w_{target_item_id}",
                        "removed": False,
                        "reason": "not_found",
                    }
                )
                continue

            wish_list_item = WishListItem.query.filter_by(
                id=target_item_id,
                wish_list_id=wish_list.id,
            ).first()
            if wish_list_item is None:
                results.append(
                    {
                        "wishlistItemId": f"w_{target_item_id}",
                        "removed": False,
                        "reason": "not_found",
                    }
                )
                continue

            db.session.delete(wish_list_item)
            removed_count += 1
            results.append(
                {
                    "wishlistItemId": f"w_{target_item_id}",
                    "removed": True,
                    "reason": "removed",
                }
            )

        if removed_count:
            db.session.commit()

        return {
            "total": len(results),
            "removed": removed_count,
            "notRemoved": len(results) - removed_count,
            "results": results,
        }


def wishlist_export_payload(
    *,
    export_format: str,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    load_wishlist_items_for_user_func: Callable[[int], tuple[Any, list[Any]]],
    load_observed_sets_for_user_wishlist_func: Callable[[int, int], tuple[set[int], set[int]]],
    build_wishlist_item_detail_func: Callable[[Any, set[int], set[int]], dict[str, Any] | None],
) -> dict[str, Any]:
    normalized_format = _normalize_transfer_format(export_format)
    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_wishlist_user_id_func(user_id)

    wish_list, wish_list_items = load_wishlist_items_for_user_func(resolved_user_id)
    if not wish_list:
        item_payloads = []
    else:
        observed_dso_ids, observed_double_star_ids = load_observed_sets_for_user_wishlist_func(
            resolved_user_id,
            wish_list.id,
        )
        item_payloads = []
        for item in wish_list_items:
            detail = build_wishlist_item_detail_func(item, observed_dso_ids, observed_double_star_ids)
            if detail is not None:
                item_payloads.append(detail)

    if normalized_format == "json":
        content = json.dumps(
            {
                "format": "czsky.wishlist.v1",
                "items": item_payloads,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        return {
            "format": "json",
            "filename": "wishlist.json",
            "mimeType": "application/json",
            "content": content,
            "total": len(item_payloads),
        }

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "objectId",
            "query",
            "wishlistItemId",
            "identifier",
            "name",
            "itemType",
            "objectType",
            "constellation",
            "magnitude",
            "observed",
            "addedAt",
            "updatedAt",
        ]
    )
    for item in item_payloads:
        writer.writerow(
            [
                item.get("objectId"),
                item.get("identifier"),
                item.get("wishlistItemId"),
                item.get("identifier"),
                item.get("name"),
                item.get("itemType"),
                item.get("objectType"),
                item.get("constellation"),
                item.get("magnitude"),
                item.get("observed"),
                item.get("addedAt"),
                item.get("updatedAt"),
            ]
        )

    return {
        "format": "csv",
        "filename": "wishlist.csv",
        "mimeType": "text/csv",
        "content": output.getvalue(),
        "total": len(item_payloads),
    }


def _extract_object_input_from_mapping(item: dict[str, Any]) -> str | None:
    object_id = item.get("objectId") or item.get("object_id")
    if isinstance(object_id, str) and object_id.strip():
        return object_id.strip()

    for key in ("query", "identifier", "name", "Name", "DSO_NAME"):
        candidate = item.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    return None


def _parse_json_import_entries(content: str) -> tuple[list[str], list[dict[str, Any]]]:
    loaded = json.loads(content)

    if isinstance(loaded, dict):
        raw_items = loaded.get("items")
        if raw_items is None:
            raise ValueError("JSON import requires an 'items' array")
    elif isinstance(loaded, list):
        raw_items = loaded
    else:
        raise ValueError("JSON import content must be an object or array")

    if not isinstance(raw_items, list):
        raise ValueError("JSON import 'items' must be a list")

    inputs: list[str] = []
    errors: list[dict[str, Any]] = []

    for index, entry in enumerate(raw_items):
        if isinstance(entry, str):
            stripped = entry.strip()
            if stripped:
                inputs.append(stripped)
            else:
                errors.append(
                    {
                        "index": index,
                        "input": entry,
                        "added": False,
                        "reason": "invalid_input",
                        "item": None,
                    }
                )
            continue

        if isinstance(entry, dict):
            extracted = _extract_object_input_from_mapping(entry)
            if extracted:
                inputs.append(extracted)
            else:
                errors.append(
                    {
                        "index": index,
                        "input": entry,
                        "added": False,
                        "reason": "invalid_input",
                        "item": None,
                    }
                )
            continue

        errors.append(
            {
                "index": index,
                "input": entry,
                "added": False,
                "reason": "invalid_input",
                "item": None,
            }
        )

    return inputs, errors


def _parse_csv_import_entries(content: str) -> tuple[list[str], list[dict[str, Any]]]:
    inputs: list[str] = []
    errors: list[dict[str, Any]] = []

    sample = content[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel

    stream = io.StringIO(content)
    reader = csv.DictReader(stream, dialect=dialect)

    fieldnames = [name.strip() for name in (reader.fieldnames or []) if isinstance(name, str)]
    known_fields = {
        "objectId",
        "object_id",
        "query",
        "identifier",
        "name",
        "Name",
        "DSO_NAME",
    }

    if fieldnames and any(field in known_fields for field in fieldnames):
        for index, row in enumerate(reader):
            extracted = _extract_object_input_from_mapping(row)
            if extracted:
                inputs.append(extracted)
            else:
                errors.append(
                    {
                        "index": index,
                        "input": row,
                        "added": False,
                        "reason": "invalid_input",
                        "item": None,
                    }
                )
        return inputs, errors

    stream.seek(0)
    plain_reader = csv.reader(stream, dialect=dialect)
    for index, row in enumerate(plain_reader):
        if not row:
            continue
        first_column = (row[0] or "").strip()
        if not first_column:
            errors.append(
                {
                    "index": index,
                    "input": row,
                    "added": False,
                    "reason": "invalid_input",
                    "item": None,
                }
            )
            continue
        inputs.append(first_column)

    return inputs, errors


def wishlist_import_payload(
    *,
    content: str,
    import_format: str,
    user_id: int | None,
    require_scope_if_available_func: Callable[[str], None],
    required_scope: str,
    resolve_wishlist_user_id_func: Callable[[int | None], int],
    get_app: Callable[[], Any],
    resolve_global_object_func: Callable[[str], dict[str, Any] | None],
    parse_wishlist_object_id_func: Callable[[str | None], tuple[str, int] | None],
) -> dict[str, Any]:
    normalized_format = _normalize_transfer_format(import_format)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("content must be a non-empty string")

    require_scope_if_available_func(required_scope)
    resolved_user_id = resolve_wishlist_user_id_func(user_id)

    if normalized_format == "json":
        object_inputs, parse_errors = _parse_json_import_entries(content)
    else:
        object_inputs, parse_errors = _parse_csv_import_entries(content)

    add_results, added_count, skipped_count = _bulk_add_objects_for_user(
        object_inputs=object_inputs,
        resolved_user_id=resolved_user_id,
        get_app=get_app,
        resolve_global_object_func=resolve_global_object_func,
        parse_wishlist_object_id_func=parse_wishlist_object_id_func,
    )

    results = parse_errors + add_results

    return {
        "format": normalized_format,
        "processed": len(results),
        "added": added_count,
        "skipped": skipped_count + len(parse_errors),
        "errors": len(parse_errors),
        "results": results,
    }
