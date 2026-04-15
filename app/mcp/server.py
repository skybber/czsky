from __future__ import annotations

from typing import Any

from app.commons.comet_utils import fetch_recent_cobs_observations
from app.commons.global_search_resolver import resolve_global_object
from app.commons.mcp_sky_object_formatters import format_resolved_object
from app.mcp import app_context
from app.mcp import auth as mcp_auth
from app.mcp import runtime as mcp_runtime
from app.mcp import sky_objects as mcp_sky_objects
from app.mcp import session_plan_payloads as mcp_session_plan_payloads
from app.mcp import wishlist_lookup_payloads as mcp_wishlist_lookup_payloads
from app.mcp import wishlist_payloads as mcp_wishlist_payloads
from app.mcp import wishlist_query
from app.mcp import wishlist_repo
from app.mcp import wishlist_write_payloads as mcp_wishlist_write_payloads
from app.mcp.tools import session_plan as session_plan_tools
from app.mcp.tools import sky_objects as sky_object_tools
from app.mcp.tools import wishlist as wishlist_tools

# MCP runs as a sidecar process. It is not mounted into Flask routes and only
# uses Flask app/context machinery to access config, database, and models.

WISHLIST_READ_SCOPE = "wishlist:read"
WISHLIST_WRITE_SCOPE = "wishlist:write"
SESSION_PLAN_READ_SCOPE = "sessionplan:read"
SESSION_PLAN_WRITE_SCOPE = "sessionplan:write"
MAX_WISHLIST_PAGE_SIZE = wishlist_query.MAX_WISHLIST_PAGE_SIZE
_USER_SUBJECT_PATTERNS = mcp_auth.USER_SUBJECT_PATTERNS
_ENV_FALSE_VALUES = mcp_auth.ENV_FALSE_VALUES


def get_app():
    return app_context.get_app()


def _to_iso(dt):
    return mcp_wishlist_payloads.to_iso(dt)


def _get_access_token():
    return mcp_auth.get_access_token()


def _is_env_flag_enabled(name: str, default: bool = True) -> bool:
    return mcp_auth.is_env_flag_enabled(name=name, default=default)


def _normalize_host_for_url(host: str) -> str:
    return mcp_auth.normalize_host_for_url(host)


def _build_base_url(host: str, port: int) -> str:
    return mcp_auth.build_base_url(host, port)


def _verify_db_mcp_token(raw_token: str) -> dict[str, Any] | None:
    return mcp_auth.verify_db_mcp_token(raw_token=raw_token, get_app=get_app)


def _build_mcp_auth_kwargs(mcp_host: str, mcp_port: int) -> dict[str, Any]:
    return mcp_auth.build_mcp_auth_kwargs(
        mcp_host=mcp_host,
        mcp_port=mcp_port,
        is_env_flag_enabled_func=_is_env_flag_enabled,
        build_base_url_func=_build_base_url,
        verify_db_mcp_token_func=_verify_db_mcp_token,
        parse_positive_user_id_func=_parse_positive_user_id,
    )


def _parse_positive_user_id(value: Any) -> int | None:
    return mcp_auth.parse_positive_user_id(value)


def _extract_user_id_from_access_token(access_token: Any) -> int | None:
    return mcp_auth.extract_user_id_from_access_token(
        access_token,
        parse_positive_user_id_func=_parse_positive_user_id,
    )


def _resolve_wishlist_user_id(user_id: int | None = None) -> int:
    return mcp_auth.resolve_wishlist_user_id(
        user_id=user_id,
        get_access_token_func=_get_access_token,
        extract_user_id_from_access_token_func=_extract_user_id_from_access_token,
        parse_positive_user_id_func=_parse_positive_user_id,
    )


def _require_scope_if_available(required_scope: str) -> None:
    mcp_auth.require_scope_if_available(
        required_scope,
        get_access_token_func=_get_access_token,
    )


def _load_wishlist_items_for_user(user_id: int):
    return wishlist_repo.load_wishlist_items_for_user(user_id=user_id, get_app=get_app)


def _load_observed_sets_for_user_wishlist(
    user_id: int,
    wish_list_id: int,
) -> tuple[set[int], set[int]]:
    return wishlist_repo.load_observed_sets_for_user_wishlist(
        user_id=user_id,
        wish_list_id=wish_list_id,
        get_app=get_app,
    )


def _build_wishlist_item_summary(
    item: Any,
    observed_dso_ids: set[int],
    observed_double_star_ids: set[int],
):
    return mcp_wishlist_payloads.build_wishlist_item_summary(
        item=item,
        observed_dso_ids=observed_dso_ids,
        observed_double_star_ids=observed_double_star_ids,
        to_iso_func=_to_iso,
    )


def _build_wishlist_item_detail(
    item: Any,
    observed_dso_ids: set[int],
    observed_double_star_ids: set[int],
) -> dict[str, Any] | None:
    return mcp_wishlist_payloads.build_wishlist_item_detail(
        item=item,
        observed_dso_ids=observed_dso_ids,
        observed_double_star_ids=observed_double_star_ids,
        build_wishlist_item_summary_func=_build_wishlist_item_summary,
    )


def _parse_wishlist_cursor(cursor: str | int | None) -> int:
    return wishlist_query.parse_wishlist_cursor(cursor)


def _parse_wishlist_item_id(wishlist_item_id: str | int) -> int:
    return wishlist_query.parse_wishlist_item_id(wishlist_item_id)


def _parse_wishlist_object_id(object_id: str | None) -> tuple[str, int] | None:
    return mcp_wishlist_write_payloads.parse_wishlist_object_id(object_id)


def _validate_wishlist_limit(limit: int) -> int:
    return wishlist_query.validate_wishlist_limit(limit)


def _apply_wishlist_filters(
    entries: list[dict[str, Any]],
    observed: bool | None,
    object_types: list[str] | None,
    constellations: list[str] | None,
) -> list[dict[str, Any]]:
    return wishlist_query.apply_wishlist_filters(
        entries=entries,
        observed=observed,
        object_types=object_types,
        constellations=constellations,
    )


def _sort_wishlist_entries(entries: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    return wishlist_query.sort_wishlist_entries(entries=entries, sort=sort)


def _paginate_entries(entries: list[dict[str, Any]], offset: int, limit: int):
    return wishlist_query.paginate_entries(entries=entries, offset=offset, limit=limit)


def resolve_sky_object_payload(query: str) -> dict[str, Any]:
    return mcp_sky_objects.resolve_sky_object_payload(
        query=query,
        get_app=get_app,
        resolve_global_object=resolve_global_object,
        format_resolved_object=format_resolved_object,
    )


def resolve_sky_object(query: str) -> dict[str, Any]:
    return resolve_sky_object_payload(query)


def get_comet_recent_observations_payload(query: str, limit: int = 5) -> dict[str, Any]:
    return mcp_sky_objects.get_comet_recent_observations_payload(
        query=query,
        limit=limit,
        get_app=get_app,
        resolve_global_object=resolve_global_object,
        fetch_recent_cobs_observations=fetch_recent_cobs_observations,
    )


def wishlist_list_payload(
    user_id: int | None = None,
    cursor: str | int | None = None,
    limit: int = 20,
    sort: str = "addedAt:desc",
    observed: bool | None = None,
    object_types: list[str] | None = None,
    constellations: list[str] | None = None,
) -> dict[str, Any]:
    return mcp_wishlist_payloads.wishlist_list_payload(
        user_id=user_id,
        cursor=cursor,
        limit=limit,
        sort=sort,
        observed=observed,
        object_types=object_types,
        constellations=constellations,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=WISHLIST_READ_SCOPE,
        get_app=get_app,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        validate_wishlist_limit_func=_validate_wishlist_limit,
        parse_wishlist_cursor_func=_parse_wishlist_cursor,
        load_wishlist_items_for_user_func=_load_wishlist_items_for_user,
        load_observed_sets_for_user_wishlist_func=_load_observed_sets_for_user_wishlist,
        build_wishlist_item_summary_func=_build_wishlist_item_summary,
        apply_wishlist_filters_func=_apply_wishlist_filters,
        sort_wishlist_entries_func=_sort_wishlist_entries,
        paginate_entries_func=_paginate_entries,
    )


def wishlist_get_payload(wishlist_item_id: str, user_id: int | None = None) -> dict[str, Any]:
    return mcp_wishlist_payloads.wishlist_get_payload(
        wishlist_item_id=wishlist_item_id,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=WISHLIST_READ_SCOPE,
        get_app=get_app,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        parse_wishlist_item_id_func=_parse_wishlist_item_id,
        load_wishlist_items_for_user_func=_load_wishlist_items_for_user,
        load_observed_sets_for_user_wishlist_func=_load_observed_sets_for_user_wishlist,
        build_wishlist_item_detail_func=_build_wishlist_item_detail,
    )


def wishlist_contains_payload(
    query: str,
    user_id: int | None = None,
) -> dict[str, Any]:
    return mcp_wishlist_lookup_payloads.wishlist_contains_payload(
        query=query,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=WISHLIST_READ_SCOPE,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        get_app=get_app,
        resolve_global_object_func=resolve_global_object,
        load_wishlist_items_for_user_func=_load_wishlist_items_for_user,
    )


def wishlist_find_payload(
    query: str,
    user_id: int | None = None,
) -> dict[str, Any]:
    return mcp_wishlist_lookup_payloads.wishlist_find_payload(
        query=query,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=WISHLIST_READ_SCOPE,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        get_app=get_app,
        resolve_global_object_func=resolve_global_object,
        load_wishlist_items_for_user_func=_load_wishlist_items_for_user,
        load_observed_sets_for_user_wishlist_func=_load_observed_sets_for_user_wishlist,
        build_wishlist_item_detail_func=_build_wishlist_item_detail,
    )


def wishlist_stats_payload(user_id: int | None = None) -> dict[str, Any]:
    return mcp_wishlist_payloads.wishlist_stats_payload(
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=WISHLIST_READ_SCOPE,
        get_app=get_app,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        load_wishlist_items_for_user_func=_load_wishlist_items_for_user,
        load_observed_sets_for_user_wishlist_func=_load_observed_sets_for_user_wishlist,
        build_wishlist_item_summary_func=_build_wishlist_item_summary,
        to_iso_func=_to_iso,
    )


def wishlist_add_payload(
    object_id: str | None = None,
    query: str | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    return mcp_wishlist_write_payloads.wishlist_add_payload(
        object_id=object_id,
        query=query,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=WISHLIST_WRITE_SCOPE,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        get_app=get_app,
        resolve_global_object_func=resolve_global_object,
        parse_wishlist_object_id_func=_parse_wishlist_object_id,
        load_observed_sets_for_user_wishlist_func=_load_observed_sets_for_user_wishlist,
        build_wishlist_item_detail_func=_build_wishlist_item_detail,
    )


def wishlist_remove_payload(
    wishlist_item_id: str,
    user_id: int | None = None,
) -> dict[str, Any]:
    return mcp_wishlist_write_payloads.wishlist_remove_payload(
        wishlist_item_id=wishlist_item_id,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=WISHLIST_WRITE_SCOPE,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        parse_wishlist_item_id_func=_parse_wishlist_item_id,
        get_app=get_app,
    )


def wishlist_bulk_add_payload(
    objects: list[str],
    user_id: int | None = None,
) -> dict[str, Any]:
    return mcp_wishlist_write_payloads.wishlist_bulk_add_payload(
        objects=objects,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=WISHLIST_WRITE_SCOPE,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        get_app=get_app,
        resolve_global_object_func=resolve_global_object,
        parse_wishlist_object_id_func=_parse_wishlist_object_id,
    )


def wishlist_bulk_remove_payload(
    wishlist_item_ids: list[str],
    user_id: int | None = None,
) -> dict[str, Any]:
    return mcp_wishlist_write_payloads.wishlist_bulk_remove_payload(
        wishlist_item_ids=wishlist_item_ids,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=WISHLIST_WRITE_SCOPE,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        parse_wishlist_item_id_func=_parse_wishlist_item_id,
        get_app=get_app,
    )


def wishlist_export_payload(
    format: str = "json",
    user_id: int | None = None,
) -> dict[str, Any]:
    return mcp_wishlist_write_payloads.wishlist_export_payload(
        export_format=format,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=WISHLIST_READ_SCOPE,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        load_wishlist_items_for_user_func=_load_wishlist_items_for_user,
        load_observed_sets_for_user_wishlist_func=_load_observed_sets_for_user_wishlist,
        build_wishlist_item_detail_func=_build_wishlist_item_detail,
    )


def wishlist_import_payload(
    content: str,
    format: str = "json",
    user_id: int | None = None,
) -> dict[str, Any]:
    return mcp_wishlist_write_payloads.wishlist_import_payload(
        content=content,
        import_format=format,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=WISHLIST_WRITE_SCOPE,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        get_app=get_app,
        resolve_global_object_func=resolve_global_object,
        parse_wishlist_object_id_func=_parse_wishlist_object_id,
    )


def session_plan_create_payload(
    for_date: str,
    location_id: int | str | None = None,
    location_name: str | None = None,
    location: str | int | None = None,
    title: str | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    return mcp_session_plan_payloads.session_plan_create_payload(
        for_date=for_date,
        location_id=location_id,
        location_name=location_name,
        location=location,
        title=title,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=SESSION_PLAN_WRITE_SCOPE,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        get_app=get_app,
    )


def session_plan_get_id_by_date_payload(
    for_date: str,
    user_id: int | None = None,
) -> dict[str, Any]:
    return mcp_session_plan_payloads.session_plan_get_id_by_date_payload(
        for_date=for_date,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=SESSION_PLAN_READ_SCOPE,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        get_app=get_app,
    )


def session_plan_add_item_payload(
    session_plan_id: int,
    query: str,
    user_id: int | None = None,
) -> dict[str, Any]:
    return mcp_session_plan_payloads.session_plan_add_item_payload(
        session_plan_id=session_plan_id,
        query=query,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=SESSION_PLAN_WRITE_SCOPE,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        get_app=get_app,
        resolve_global_object_func=resolve_global_object,
    )


def dso_list_get_id_by_name_payload(
    name: str,
    user_id: int | None = None,
) -> dict[str, Any]:
    return mcp_session_plan_payloads.dso_list_get_id_by_name_payload(
        name=name,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=SESSION_PLAN_READ_SCOPE,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        get_app=get_app,
    )


def session_plan_remove_item_payload(
    session_plan_id: int,
    query: str,
    user_id: int | None = None,
) -> dict[str, Any]:
    return mcp_session_plan_payloads.session_plan_remove_item_payload(
        session_plan_id=session_plan_id,
        query=query,
        user_id=user_id,
        require_scope_if_available_func=_require_scope_if_available,
        required_scope=SESSION_PLAN_WRITE_SCOPE,
        resolve_wishlist_user_id_func=_resolve_wishlist_user_id,
        get_app=get_app,
        resolve_global_object_func=resolve_global_object,
    )


def build_mcp_server():
    def _register_tools(server):
        sky_object_tools.register_tools(
            server,
            resolve_sky_object_resolver=resolve_sky_object_payload,
            comet_observations_resolver=get_comet_recent_observations_payload,
        )
        session_plan_tools.register_tools(
            server,
            session_plan_create_resolver=session_plan_create_payload,
            session_plan_get_id_by_date_resolver=session_plan_get_id_by_date_payload,
            session_plan_add_item_resolver=session_plan_add_item_payload,
            session_plan_remove_item_resolver=session_plan_remove_item_payload,
            dso_list_get_id_by_name_resolver=dso_list_get_id_by_name_payload,
        )
        wishlist_tools.register_tools(
            server,
            wishlist_list_resolver=wishlist_list_payload,
            wishlist_stats_resolver=wishlist_stats_payload,
            wishlist_contains_resolver=wishlist_contains_payload,
            wishlist_find_resolver=wishlist_find_payload,
            wishlist_add_resolver=wishlist_add_payload,
            wishlist_remove_resolver=wishlist_remove_payload,
            wishlist_bulk_add_resolver=wishlist_bulk_add_payload,
            wishlist_bulk_remove_resolver=wishlist_bulk_remove_payload,
            wishlist_export_resolver=wishlist_export_payload,
            wishlist_import_resolver=wishlist_import_payload,
        )

    return mcp_runtime.build_mcp_server(
        build_auth_kwargs=_build_mcp_auth_kwargs,
        register_tools=_register_tools,
    )


def main():
    mcp_runtime.main(build_mcp_server)


if __name__ == "__main__":
    main()
