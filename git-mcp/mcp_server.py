#!/usr/bin/env python3
"""git MCP Server — typed git operations against any registered tailnet host.

Every tool requires a `target` (a registered alias, resolved against
GIT_MCP_TARGETS) and a `repo_path` -- there is no local default, unlike
docker-mcp/postgres-mcp, since this server's own container has no
meaningful repos of its own. Supports streamable HTTP (default) and stdio
transports.

Usage:
    uv run python mcp_server.py                     # HTTP on port 8010
    uv run python mcp_server.py --transport stdio    # stdio for Claude Desktop
"""

import argparse
import os
import sys

# Ensure src/ is importable when running as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from git_mcp.config import settings
from git_mcp.server import mcp

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="git MCP Server")
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
