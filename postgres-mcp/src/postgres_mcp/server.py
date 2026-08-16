"""FastMCP application construction for postgres-mcp."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .config import settings
from .pg_client import PgClient
from .tools import register_all

logger = logging.getLogger("postgres-mcp")


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncGenerator[dict, None]:
    """Create and share a single pooled PgClient across all tool calls."""
    client = await PgClient(settings.database_url).connect()
    logger.info("PgClient connected — default database ready")
    try:
        yield {"client": client}
    finally:
        await client.close()
        logger.info("PgClient pool closed")


mcp = FastMCP("postgres-mcp", lifespan=lifespan)
register_all(mcp)
