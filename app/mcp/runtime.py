from __future__ import annotations

import inspect
import os
from typing import Any, Callable


def build_mcp_server(
    *,
    build_auth_kwargs: Callable[[str, int], dict[str, Any]],
    register_tools: Callable[[Any], None],
):
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

    auth_kwargs = build_auth_kwargs(mcp_host, mcp_port)
    for key, value in auth_kwargs.items():
        if key in init_signature.parameters:
            kwargs[key] = value

    server = FastMCP(**kwargs)
    register_tools(server)
    return server


def run_mcp_server(server: Any) -> None:
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


def main(build_server: Callable[[], Any]) -> None:
    server = build_server()
    run_mcp_server(server)
