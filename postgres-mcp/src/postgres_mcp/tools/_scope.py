"""Shared per-call Postgres connection scoping.

Lets any tool override the target database for a single call instead of
always using the server's configured default (a pool opened once at startup
and shared across all calls via the FastMCP lifespan). Mirrors the same
pattern as ignition-mcp's gateway_url/api_key override and docker-mcp's
docker_host override.
"""

from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator, Optional, Union, cast

from fastmcp import Context
from pydantic import Field

from ..pg_client import PgClient, ScopedPgConnection

ConnectionUriOverride = Annotated[
    Optional[str],
    Field(
        description=(
            "Override the Postgres connection string for this call only, e.g. "
            "'postgresql://user:pass@host:5432/dbname'. Omit to use the "
            "server's configured default database."
        )
    ),
]


@asynccontextmanager
async def scoped_query(
    ctx: Context,
    connection_uri: Optional[str] = None,
) -> AsyncIterator[Union[PgClient, ScopedPgConnection]]:
    """Yield something with an async .fetch(query, *args) for this call.

    With no override, yields the shared pooled client created once at server
    startup (owned by the FastMCP lifespan -- not closed here). With
    connection_uri given, opens a single throwaway connection scoped to this
    call and closes it on exit, leaving the shared pool untouched.
    """
    if connection_uri:
        async with ScopedPgConnection(connection_uri) as conn:
            yield conn
        return

    if ctx.request_context is None:
        raise RuntimeError("Tool called outside of a request context")
    yield cast(PgClient, ctx.request_context.lifespan_context["client"])
