from __future__ import annotations

import inspect
import os
from typing import Any

from app import create_app
from app.commons.comet_utils import fetch_recent_cobs_observations
from app.commons.global_search_resolver import resolve_global_object
from app.commons.mcp_sky_object_formatters import format_resolved_object

# MCP runs as a sidecar process. It is not mounted into Flask routes and only
# uses Flask app/context machinery to access config, database, and models.

_APP = None


def get_app():
    global _APP
    if _APP is None:
        _APP = create_app(os.getenv("FLASK_CONFIG") or "default", web=False)
    return _APP


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


def build_mcp_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'mcp'. Install project requirements before running the MCP server."
        ) from exc

    kwargs = {"name": "czsky-sky-objects"}
    init_signature = inspect.signature(FastMCP)
    init_env_kwargs = {
        "host": os.getenv("MCP_HOST", "127.0.0.1"),
        "port": int(os.getenv("MCP_PORT", "8001")),
    }
    for key, value in init_env_kwargs.items():
        if key in init_signature.parameters:
            kwargs[key] = value
    if "json_response" in init_signature.parameters:
        kwargs["json_response"] = True
    if "stateless_http" in init_signature.parameters:
        kwargs["stateless_http"] = True

    server = FastMCP(**kwargs)
    resolver = resolve_sky_object_payload
    comet_observations_resolver = get_comet_recent_observations_payload

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
