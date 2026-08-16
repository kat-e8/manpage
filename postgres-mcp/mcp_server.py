#!/usr/bin/env python3
"""Postgres MCP Server — FastMCP server for ad-hoc Postgres access.

Provides schema introspection and query tools against a default database,
with an optional per-call connection_uri override so a single deployment
can reach more than one database. Supports streamable HTTP (default) and
stdio transports.

Usage:
    uv run python mcp_server.py                     # HTTP on port 8000
    uv run python mcp_server.py --transport stdio    # stdio for Claude Desktop
"""

import argparse
import os
import sys

# Ensure src/ is importable when running as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from postgres_mcp.config import settings
from postgres_mcp.server import mcp

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Postgres MCP Server")
    parser.add_argument(
        "--transport",
        choices=["streamable-http", "stdio"],
        default="streamable-http",
        help="MCP transport (default: streamable-http)",
    )
    parser.add_argument("--host", default=settings.server_host)
    parser.add_argument("--port", type=int, default=settings.server_port)
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
