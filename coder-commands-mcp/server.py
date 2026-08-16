"""
MCP tool server. Reads Postgres only (populated by the sync service, Step 4)
and exposes:
  - search_commands: full-text search, the main entry point for natural-
    language questions like "how do I insert a new row into a table".
  - list_topics: discovery -- what topics exist and how big each is.
  - browse_<topic>: one thin tool per distinct topic in the database,
    generated at startup rather than hand-written, returning that topic's
    entries in original sheet order.

Served over Streamable HTTP so it can run as its own container and be
reverse-proxied by the FastAPI gateway (Step 6).
"""
from __future__ import annotations

import asyncio
import re
import sys

if sys.platform == "win32":
    # psycopg's async mode requires a selector-based event loop; Windows
    # defaults to ProactorEventLoop. Irrelevant inside the Linux container
    # this ships in (Step 7), but keeps the server runnable directly on a
    # Windows host for local dev/testing (see Step 5 verification record).
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import db
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

mcp: MCPServer = MCPServer(name="codercommands", version="0.1.0")


@mcp.tool()
async def search_commands(query: str, topic: str | None = None, limit: int = 10) -> list[dict]:
    """Full-text search across the command reference (mongo, sql, docker, git,
    ansible, python, shell, etc). Pass `topic` to scope the search to a single
    topic; omit it to search everything. Returns matches ranked by relevance,
    each with topic, section, command, description, and any extra notes."""
    return await db.search_commands(query, topic, limit)


@mcp.tool()
async def list_topics() -> list[dict]:
    """List every topic in the command reference along with how many entries
    each one has, so you know what's available before searching or browsing."""
    return await db.list_topics()


def _slugify(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_")


def register_browse_tools(server: MCPServer) -> None:
    for topic_name, count in db.fetch_topics_sync():
        def make_browse(topic: str = topic_name):
            async def browse(limit: int = 200) -> list[dict]:
                return await db.browse_topic(topic, limit)
            return browse

        server.add_tool(
            make_browse(),
            name=f"browse_{_slugify(topic_name)}",
            description=(
                f"Return all {count} entries in the '{topic_name}' topic, "
                "in original spreadsheet order."
            ),
        )


register_browse_tools(mcp)

# The SDK's default DNS-rebinding protection only allows Host: localhost/
# 127.0.0.1, which rejects every request arriving via the gateway's reverse
# proxy (Host: coder-commands-mcp:9000, the real internal service name).
# Kept enabled rather than disabled outright, with the internal service name
# allow-listed explicitly: this container has no published host port and is
# only reachable from other containers on the compose network, so this is
# the actual trusted-caller identity, not an open door.
app = mcp.streamable_http_app(
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["coder-commands-mcp:9000", "localhost:9000", "127.0.0.1:9000"],
        allowed_origins=[
            "http://coder-commands-mcp:9000", "http://localhost:9000", "http://127.0.0.1:9000",
        ],
    ),
)
