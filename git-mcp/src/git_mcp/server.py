"""FastMCP application construction for git-mcp."""

from fastmcp import FastMCP

from .tools import register_all

mcp = FastMCP("git-mcp")
register_all(mcp)
