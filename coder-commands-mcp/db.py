"""
Postgres access for the MCP server. Read-only (v1 scope, per Step 3 of the
CodeCommands plan) -- no INSERT/UPDATE/DELETE paths exist here.
"""
from __future__ import annotations

import os

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ["DATABASE_URL"]

# ts_rank's weights array is ordered {D, C, B, A} (least to most significant
# label). Postgres's own default is {0.1, 0.2, 0.4, 1.0} -- a 10x gap
# between a command-field (A) match and a section-field (D) match. That
# proved too aggressive in practice: it let a wrong row win outright when
# it happened to contain a query word literally in its command syntax (e.g.
# "kill-session" containing "session") while the correct row only had that
# word in its description. This narrower gap still rewards a command-field
# match over an incidental one, without letting it dominate everything else.
RANK_WEIGHTS = [0.3, 0.5, 0.8, 1.0]


def fetch_topics_sync() -> list[tuple[str, int]]:
    """Synchronous, used once at startup to discover topics before the ASGI
    app (and its tool list) is built."""
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT topic, count(*) FROM commands GROUP BY topic ORDER BY topic")
            return cur.fetchall()


async def search_commands(query: str, topic: str | None, limit: int) -> list[dict]:
    """Full-text search with OR semantics between query terms.

    plainto_tsquery ANDs every term, which is too strict for this corpus: a
    natural-language question like "insert a new row into a table" shares
    almost no vocabulary with the terse sheet text ("INSERT INTO tabName
    (f1,f2,fN) VALUES (...)" -- no "new", "row", or "table" as literal
    words), so an AND query matches nothing even though "insert" alone
    should surface the right row. Terms are OR-combined instead and results
    are still ordered by ts_rank, so documents matching more/rarer terms
    still rank above single-term matches.
    """
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT plainto_tsquery('english', %s)::text AS q", (query,))
            row = await cur.fetchone()
            and_form = row["q"] if row else ""
            or_form = and_form.replace(" & ", " | ")
            if not or_form:
                return []

            sql = (
                "SELECT topic, section, command, description, extra, "
                "ts_rank(%(weights)s::float4[], search_vector, to_tsquery('english', %(q)s)) AS rank "
                "FROM commands "
                "WHERE search_vector @@ to_tsquery('english', %(q)s)"
            )
            params: dict = {"q": or_form, "limit": limit, "weights": RANK_WEIGHTS}
            if topic:
                sql += " AND topic = %(topic)s"
                params["topic"] = topic
            sql += " ORDER BY rank DESC LIMIT %(limit)s"

            await cur.execute(sql, params)
            rows = await cur.fetchall()
    for r in rows:
        r.pop("rank", None)
    return rows


async def browse_topic(topic: str, limit: int) -> list[dict]:
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT topic, section, command, description, extra FROM commands "
                "WHERE topic = %s ORDER BY row_order LIMIT %s",
                (topic, limit),
            )
            return await cur.fetchall()


async def list_topics() -> list[dict]:
    async with await psycopg.AsyncConnection.connect(DATABASE_URL) as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT topic, count(*) AS count FROM commands GROUP BY topic ORDER BY topic"
            )
            return await cur.fetchall()
