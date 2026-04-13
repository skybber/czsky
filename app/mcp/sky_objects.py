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
