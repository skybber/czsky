from __future__ import annotations

from typing import Any, Callable


def resolve_sky_object_payload(
    query: str,
    *,
    get_app: Callable[[], Any],
    resolve_global_object: Callable[[str], dict[str, Any] | None],
    format_resolved_object: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
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


def resolve_sky_objects_payload(
    queries: list[str],
    *,
    get_app: Callable[[], Any],
    resolve_global_object: Callable[[str], dict[str, Any] | None],
    format_resolved_object: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(queries, list):
        raise ValueError("queries must be a list of strings")
    if not queries:
        raise ValueError("queries must not be empty")
    if len(queries) > 100:
        raise ValueError("queries must contain at most 100 items")

    app = get_app()
    results = []

    with app.app_context():
        # Some existing search helpers still depend on Flask request globals.
        with app.test_request_context("/", headers={"Host": "localhost"}):
            for raw_query in queries:
                if not isinstance(raw_query, str):
                    results.append({
                        "query": raw_query,
                        "found": False,
                        "result": None,
                    })
                    continue

                query = raw_query.strip()
                if not query:
                    results.append({
                        "query": raw_query,
                        "found": False,
                        "result": None,
                    })
                    continue

                resolved = resolve_global_object(query)
                if not resolved:
                    results.append({
                        "query": query,
                        "found": False,
                        "result": None,
                    })
                    continue

                formatted = format_resolved_object(query, resolved)
                results.append({
                    "query": query,
                    "found": True,
                    "result": formatted,
                })

    return {
        "results": results,
    }


def get_comet_recent_observations_payload(
    query: str,
    limit: int = 5,
    *,
    get_app: Callable[[], Any],
    resolve_global_object: Callable[[str], dict[str, Any] | None],
    fetch_recent_cobs_observations: Callable[[int, int], list[dict[str, Any]]],
) -> dict[str, Any]:
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
