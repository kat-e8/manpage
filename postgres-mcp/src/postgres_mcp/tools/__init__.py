"""Postgres MCP tool modules.

Each module exposes a register(mcp) function that registers its tools
with the FastMCP instance. Call register_all(mcp) from mcp_server.py
to register everything at once.

Tool inventory (4 total):

Query (4):
  list_schemas, list_tables, describe_table, run_query
"""

from fastmcp import FastMCP

from . import query

__all__ = ["query", "register_all"]


def register_all(mcp: FastMCP) -> None:
    """Register all tool modules with the FastMCP instance."""
    query.register(mcp)
