"""Postgres client wrapper.

Owns an asyncpg pool for the lifetime of the MCP server (the default
target). Per-call overrides get a single throwaway connection instead of a
pool -- see tools/_scope.py.
"""

from typing import Any, List, Optional

import asyncpg


class PgClient:
    """Pooled connection to the server's default database."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> "PgClient":
        self._pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5)
        return self

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def fetch(self, query: str, *args: Any) -> List[dict]:
        assert self._pool is not None, "PgClient.connect() was not awaited"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]


class ScopedPgConnection:
    """A single throwaway connection for one per-call connection_uri override.

    No pool -- opened for one tool call and closed on exit, so an override
    never lingers as a held connection to a database the server doesn't
    otherwise talk to.
    """

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._conn: Optional[asyncpg.Connection] = None

    async def __aenter__(self) -> "ScopedPgConnection":
        self._conn = await asyncpg.connect(self.dsn)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._conn is not None:
            await self._conn.close()

    async def fetch(self, query: str, *args: Any) -> List[dict]:
        assert self._conn is not None, "ScopedPgConnection used outside 'async with'"
        rows = await self._conn.fetch(query, *args)
        return [dict(r) for r in rows]
