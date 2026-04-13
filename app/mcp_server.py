"""Compatibility entrypoint for the MCP server.

The MCP implementation lives in ``app.mcp.server``. This module stays in
place to preserve existing imports and runtime entrypoints.
"""

from __future__ import annotations

import sys

from app.mcp import server as _server

if __name__ == "__main__":
    _server.main()
else:
    sys.modules[__name__] = _server
