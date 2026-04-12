from __future__ import annotations

import inspect
import os
import re
from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app import create_app
from app.commons.comet_utils import fetch_recent_cobs_observations
from app.commons.global_search_resolver import resolve_global_object
from app.commons.mcp_sky_object_formatters import format_resolved_object

# MCP runs as a sidecar process. It is not mounted into Flask routes and only
# uses Flask app/context machinery to access config, database, and models.

_APP = None

WISHLIST_READ_SCOPE = "wishlist:read"
MAX_WISHLIST_PAGE_SIZE = 100
_CURSOR_PATTERN = re.compile(r"^\d+$")
_WISHLIST_ITEM_PATTERN = re.compile(r"^w_(\d+)$")
_USER_SUBJECT_PATTERNS = (
    re.compile(r"^(\d+)$"),
    re.compile(r"^u_(\d+)$"),
    re.compile(r"^user:(\d+)$"),
)
_ENV_FALSE_VALUES = {"0", "false", "no", "off"}


def get_app():
    global _APP
    if _APP is None:
        _APP = create_app(os.getenv("FLASK_CONFIG") or "default", web=False)
    return _APP


def _to_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _get_access_token():
    try:
        from mcp.server.auth.middleware.auth_context import get_access_token
    except ImportError:
        return None

    try:
        return get_access_token()
    except Exception:
        return None


def _is_env_flag_enabled(name: str, default: bool = True) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in _ENV_FALSE_VALUES


def _normalize_host_for_url(host: str) -> str:
    normalized = (host or "").strip() or "127.0.0.1"
    if normalized in {"0.0.0.0", "::", "[::]"}:
        return "127.0.0.1"
    return normalized


def _build_base_url(host: str, port: int) -> str:
    normalized_host = _normalize_host_for_url(host)
    if ":" in normalized_host and not normalized_host.startswith("["):
        normalized_host = f"[{normalized_host}]"
    return f"http://{normalized_host}:{port}"


def _verify_db_mcp_token(raw_token: str) -> dict[str, Any] | None:
    from app.main.usersettings.mcp_token_service import verify_user_mcp_token

    app = get_app()
    with app.app_context():
        return verify_user_mcp_token(raw_token=raw_token)


def _build_mcp_auth_kwargs(mcp_host: str, mcp_port: int) -> dict[str, Any]:
    if not _is_env_flag_enabled("MCP_ENABLE_TOKEN_AUTH", default=True):
        return {}

    try:
        from mcp.server.auth.provider import AccessToken
        from mcp.server.auth.settings import AuthSettings
    except ImportError:
        return {}

    class CzskyAccessToken(AccessToken):
        user_id: int
        token_id: str | None = None

    class CzskyTokenVerifier:
        async def verify_token(self, token: str) -> AccessToken | None:
            try:
                verified_token = _verify_db_mcp_token(token)
            except Exception:
                return None

            if not verified_token:
                return None

            user_id = _parse_positive_user_id(verified_token.get("user_id"))
            if user_id is None:
                return None

            scopes = verified_token.get("scopes") or []
            if isinstance(scopes, str):
                scopes = scopes.split()
            else:
                scopes = [scope for scope in scopes if isinstance(scope, str) and scope]

            token_id = verified_token.get("token_id")
            return CzskyAccessToken(
                token=token,
                client_id=f"user:{user_id}",
                scopes=scopes,
                user_id=user_id,
                token_id=str(token_id) if token_id is not None else None,
            )

    base_url = _build_base_url(mcp_host, mcp_port)
    issuer_url = os.getenv("MCP_AUTH_ISSUER_URL") or base_url
    resource_server_url = os.getenv("MCP_AUTH_RESOURCE_SERVER_URL") or f"{base_url}/mcp"

    return {
        "token_verifier": CzskyTokenVerifier(),
        "auth": AuthSettings(
            issuer_url=issuer_url,
            resource_server_url=resource_server_url,
        ),
    }


def _parse_positive_user_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        for pattern in _USER_SUBJECT_PATTERNS:
            matched = pattern.match(stripped)
            if matched:
                parsed = int(matched.group(1))
                return parsed if parsed > 0 else None
    return None


def _extract_user_id_from_access_token(access_token: Any) -> int | None:
    if not access_token:
        return None

    candidate_values = []
    for key in ("user_id", "sub", "subject", "uid", "client_id"):
        candidate_values.append(getattr(access_token, key, None))

    if hasattr(access_token, "model_dump"):
        token_payload = access_token.model_dump()
        for key in ("user_id", "sub", "subject", "uid", "client_id"):
            candidate_values.append(token_payload.get(key))

    for candidate in candidate_values:
        parsed_user_id = _parse_positive_user_id(candidate)
        if parsed_user_id is not None:
            return parsed_user_id
    return None


def _resolve_wishlist_user_id(user_id: int | None = None) -> int:
    if user_id is not None and user_id <= 0:
        raise ValueError("user_id must be positive")

    access_token = _get_access_token()
    token_user_id = _extract_user_id_from_access_token(access_token)
    if token_user_id is not None:
        if user_id is not None and user_id != token_user_id:
            raise PermissionError("Provided user_id does not match authenticated token subject")
        return token_user_id

    if user_id is not None:
        return user_id

    env_user_id = _parse_positive_user_id(os.getenv("MCP_USER_ID"))
    if env_user_id is not None:
        return env_user_id

    raise PermissionError(
        "Missing user identity for wishlist tools. "
        "Provide a token with subject claims or pass user_id in stub mode."
    )


def _require_scope_if_available(required_scope: str) -> None:
    access_token = _get_access_token()
    if access_token is None:
        return

    token_scopes = getattr(access_token, "scopes", None)
    if token_scopes is None and hasattr(access_token, "model_dump"):
        token_scopes = access_token.model_dump().get("scopes")
    if token_scopes is None:
        return

    if isinstance(token_scopes, str):
        token_scopes = token_scopes.split()

    if required_scope not in token_scopes:
        raise PermissionError(f"Missing required scope '{required_scope}'")


def _load_wishlist_items_for_user(user_id: int):
    from app.models import WishList, WishListItem

    app = get_app()
    with app.app_context():
        wish_list = WishList.query.filter_by(user_id=user_id).first()
        if not wish_list:
            return None, []

        wish_list_items = (
            WishListItem.query
            .options(joinedload(WishListItem.deepsky_object), joinedload(WishListItem.double_star))
            .filter_by(wish_list_id=wish_list.id)
            .all()
        )
        return wish_list, wish_list_items


def _load_observed_sets_for_user_wishlist(
    user_id: int, wish_list_id: int
) -> tuple[set[int], set[int]]:
    from app import db
    from app.models import DeepskyObject, ObservedList, ObservedListItem, WishListItem

    app = get_app()
    with app.app_context():
        observed_dso_subquery = (
            db.session.query(ObservedListItem.dso_id)
            .join(ObservedList, ObservedListItem.observed_list_id == ObservedList.id)
            .filter(ObservedList.user_id == user_id)
            .filter(ObservedListItem.dso_id.is_not(None))
        )

        observed_wishlist_dso_rows = (
            db.session.query(WishListItem.dso_id)
            .join(WishListItem.deepsky_object)
            .filter(WishListItem.wish_list_id == wish_list_id)
            .filter(
                or_(
                    WishListItem.dso_id.in_(observed_dso_subquery),
                    DeepskyObject.master_id.in_(observed_dso_subquery),
                )
            )
            .all()
        )
        observed_wishlist_dso_ids = {
            row[0] for row in observed_wishlist_dso_rows if row and row[0] is not None
        }

        observed_double_star_rows = (
            db.session.query(ObservedListItem.double_star_id)
            .join(ObservedList, ObservedListItem.observed_list_id == ObservedList.id)
            .filter(ObservedList.user_id == user_id)
            .filter(ObservedListItem.double_star_id.is_not(None))
            .all()
        )
        observed_double_star_ids = {
            row[0] for row in observed_double_star_rows if row and row[0] is not None
        }

    return observed_wishlist_dso_ids, observed_double_star_ids


def _build_wishlist_item_summary(
    item: Any,
    observed_dso_ids: set[int],
    observed_double_star_ids: set[int],
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
            "addedAt": _to_iso(added_at),
            "updatedAt": _to_iso(updated_at),
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
            "addedAt": _to_iso(added_at),
            "updatedAt": _to_iso(updated_at),
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


def _build_wishlist_item_detail(
    item: Any, observed_dso_ids: set[int], observed_double_star_ids: set[int]
) -> dict[str, Any] | None:
    entry = _build_wishlist_item_summary(item, observed_dso_ids, observed_double_star_ids)
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


def _parse_wishlist_cursor(cursor: str | int | None) -> int:
    if cursor is None or cursor == "":
        return 0

    if isinstance(cursor, int):
        if cursor < 0:
            raise ValueError("cursor must be non-negative")
        return cursor

    if not isinstance(cursor, str):
        raise ValueError("cursor must be a string")

    stripped = cursor.strip()
    if not _CURSOR_PATTERN.match(stripped):
        raise ValueError("cursor must be a non-negative integer string")

    return int(stripped)


def _parse_wishlist_item_id(wishlist_item_id: str | int) -> int:
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

    matched = _WISHLIST_ITEM_PATTERN.match(stripped)
    if matched:
        parsed = int(matched.group(1))
        if parsed > 0:
            return parsed

    raise ValueError("wishlist_item_id must be in format w_<id> or numeric id")


def _validate_wishlist_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("limit must be an integer")
    if limit < 1 or limit > MAX_WISHLIST_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_WISHLIST_PAGE_SIZE}")
    return limit


def _apply_wishlist_filters(
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


def _sort_wishlist_entries(entries: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
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


def _paginate_entries(entries: list[dict[str, Any]], offset: int, limit: int):
    page_plus_one = entries[offset:offset + limit + 1]
    has_more = len(page_plus_one) > limit
    page_entries = page_plus_one[:limit]
    next_cursor = str(offset + limit) if has_more else None
    return page_entries, next_cursor, has_more


def resolve_sky_object_payload(query: str) -> dict[str, Any]:
    query = (query or "").strip()
    if not query:
        raise ValueError("query must not be empty")

    app = get_app()
    with app.app_context():
        # Some existing search helpers still depend on Flask request globals.
        with app.test_request_context("/", headers={"Host": "localhost"}):
            resolved = resolve_global_object(query)

            if not resolved:
                return {
                    "query": query,
                    "found": False,
                    "result": None,
                }

            formatted = format_resolved_object(query, resolved)

    return {
        "query": query,
        "found": True,
        "result": formatted,
    }


def resolve_sky_object(query: str) -> dict[str, Any]:
    return resolve_sky_object_payload(query)


def get_comet_recent_observations_payload(query: str, limit: int = 5) -> dict[str, Any]:
    query = (query or "").strip()
    if not query:
        raise ValueError("query must not be empty")

    app = get_app()
    with app.app_context():
        # Reuse the same lookup path and Flask globals assumptions as the main tool.
        with app.test_request_context("/", headers={"Host": "localhost"}):
            resolved = resolve_global_object(query)

            if not resolved or resolved["object_type"] != "comet":
                return {
                    "query": query,
                    "found": False,
                    "result": None,
                }

            comet = resolved["object"]
            observations = fetch_recent_cobs_observations(comet.id, limit=limit)

    return {
        "query": query,
        "found": True,
        "result": {
            "object_type": "comet",
            "identifier": comet.comet_id,
            "title": comet.designation,
            "recent_cobs_observations": observations,
        },
    }


def wishlist_list_payload(
    user_id: int | None = None,
    cursor: str | int | None = None,
    limit: int = 20,
    sort: str = "addedAt:desc",
    observed: bool | None = None,
    object_types: list[str] | None = None,
    constellations: list[str] | None = None,
) -> dict[str, Any]:
    _require_scope_if_available(WISHLIST_READ_SCOPE)

    app = get_app()
    with app.app_context():
        resolved_user_id = _resolve_wishlist_user_id(user_id=user_id)
        valid_limit = _validate_wishlist_limit(limit)
        offset = _parse_wishlist_cursor(cursor)

        wish_list, wish_list_items = _load_wishlist_items_for_user(resolved_user_id)
        if not wish_list:
            return {"items": [], "nextCursor": None, "hasMore": False}

        observed_dso_ids, observed_double_star_ids = _load_observed_sets_for_user_wishlist(
            resolved_user_id, wish_list.id
        )

        entries = []
        for item in wish_list_items:
            entry = _build_wishlist_item_summary(item, observed_dso_ids, observed_double_star_ids)
            if entry is not None:
                entries.append(entry)

        filtered_entries = _apply_wishlist_filters(entries, observed, object_types, constellations)
        ordered_entries = _sort_wishlist_entries(filtered_entries, sort)
        page_entries, next_cursor, has_more = _paginate_entries(ordered_entries, offset, valid_limit)

        return {
            "items": [entry["item"] for entry in page_entries],
            "nextCursor": next_cursor,
            "hasMore": has_more,
        }


def wishlist_get_payload(wishlist_item_id: str, user_id: int | None = None) -> dict[str, Any]:
    _require_scope_if_available(WISHLIST_READ_SCOPE)

    app = get_app()
    with app.app_context():
        resolved_user_id = _resolve_wishlist_user_id(user_id=user_id)
        target_item_id = _parse_wishlist_item_id(wishlist_item_id)

        wish_list, wish_list_items = _load_wishlist_items_for_user(resolved_user_id)
        if not wish_list:
            return {"found": False, "item": None}

        matched_item = next((item for item in wish_list_items if item.id == target_item_id), None)
        if matched_item is None:
            return {"found": False, "item": None}

        observed_dso_ids, observed_double_star_ids = _load_observed_sets_for_user_wishlist(
            resolved_user_id, wish_list.id
        )
        item_payload = _build_wishlist_item_detail(
            matched_item,
            observed_dso_ids,
            observed_double_star_ids,
        )

        return {"found": item_payload is not None, "item": item_payload}


def wishlist_stats_payload(user_id: int | None = None) -> dict[str, Any]:
    _require_scope_if_available(WISHLIST_READ_SCOPE)

    app = get_app()
    with app.app_context():
        resolved_user_id = _resolve_wishlist_user_id(user_id=user_id)
        wish_list, wish_list_items = _load_wishlist_items_for_user(resolved_user_id)

        if not wish_list:
            return {
                "total": 0,
                "observed": 0,
                "unobserved": 0,
                "byItemType": {},
                "byObjectType": {},
                "updatedAt": None,
            }

        observed_dso_ids, observed_double_star_ids = _load_observed_sets_for_user_wishlist(
            resolved_user_id, wish_list.id
        )

        total = 0
        observed_count = 0
        unobserved_count = 0
        by_item_type: Counter[str] = Counter()
        by_object_type: Counter[str] = Counter()
        updated_candidates: list[datetime] = []

        for item in wish_list_items:
            entry = _build_wishlist_item_summary(item, observed_dso_ids, observed_double_star_ids)
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
            "updatedAt": _to_iso(max(updated_candidates) if updated_candidates else None),
        }


def build_mcp_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'mcp'. Install project requirements before running the MCP server."
        ) from exc

    kwargs = {"name": "czsky-sky-objects"}
    init_signature = inspect.signature(FastMCP)
    mcp_host = os.getenv("MCP_HOST", "127.0.0.1")
    mcp_port = int(os.getenv("MCP_PORT", "8001"))
    init_env_kwargs = {
        "host": mcp_host,
        "port": mcp_port,
    }
    for key, value in init_env_kwargs.items():
        if key in init_signature.parameters:
            kwargs[key] = value
    if "json_response" in init_signature.parameters:
        kwargs["json_response"] = True
    if "stateless_http" in init_signature.parameters:
        kwargs["stateless_http"] = True
    auth_kwargs = _build_mcp_auth_kwargs(mcp_host, mcp_port)
    for key, value in auth_kwargs.items():
        if key in init_signature.parameters:
            kwargs[key] = value

    server = FastMCP(**kwargs)
    resolver = resolve_sky_object_payload
    comet_observations_resolver = get_comet_recent_observations_payload
    wishlist_list_resolver = wishlist_list_payload
    wishlist_get_resolver = wishlist_get_payload
    wishlist_stats_resolver = wishlist_stats_payload

    @server.tool()
    def resolve_sky_object(query: str) -> dict[str, Any]:
        """Find an astronomical object in the local CzSkY database.

        Accepts identifiers and names such as M31, NGC891, Saturn, Moon, comet
        designations, minor planets, stars, double stars, and constellation
        names. Returns the first match using the same priority as the CzSkY
        global search. For comets, the payload may also include recent local
        COBS observations stored in the CzSkY database.
        """
        return resolver(query)

    @server.tool()
    def get_comet_recent_observations(query: str, limit: int = 5) -> dict[str, Any]:
        """Return recent local COBS observations for a comet from the CzSkY database.

        Accepts the same comet identifiers or names as resolve_sky_object, for
        example 88P/Howell or C/2023 A3. Returns only comet-specific recent
        observation reports stored in the local database.
        """
        return comet_observations_resolver(query, limit=limit)

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

    return server


def main():
    server = build_mcp_server()
    run_signature = inspect.signature(server.run)
    run_kwargs = {
        "transport": os.getenv("MCP_TRANSPORT", "streamable-http"),
    }
    supported_kwargs = {
        key: value
        for key, value in run_kwargs.items()
        if key in run_signature.parameters
    }
    server.run(**supported_kwargs)


if __name__ == "__main__":
    main()
