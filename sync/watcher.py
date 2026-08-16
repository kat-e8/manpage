"""
Sync service entry point.

Polls the source xlsx's modified-time (not inotify -- Docker Desktop bind-mount
file events are unreliable on Windows, see coderCommands_Plan/Step04 for why)
and, on change, runs a full per-topic transactional replace into Postgres:
for each topic, DELETE existing rows then INSERT the freshly normalized ones,
inside one transaction per sync pass. This sidesteps row-level diffing
entirely -- an edit, reorder, or deletion in the xlsx all resolve the same way.

Every pass is logged to sync_runs (db/schema.sql) so sync health can be
audited with a query instead of container logs.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

import psycopg

from ingest import normalize_workbook

XLSX_PATH = os.environ.get("XLSX_PATH", "/data/coder_commands.xlsx")
POLL_SECONDS = int(os.environ.get("SYNC_POLL_SECONDS", "7"))
DATABASE_URL = os.environ["DATABASE_URL"]


def _mtime(path: str) -> datetime:
    return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)


def sync_once(conn: psycopg.Connection, mtime: datetime) -> None:
    topics = normalize_workbook(XLSX_PATH)

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO sync_runs (started_at, xlsx_mtime, status) "
            "VALUES (%s, %s, 'running') RETURNING id",
            (datetime.now(timezone.utc), mtime),
        )
        run_id = cur.fetchone()[0]
    conn.commit()

    total_rows = 0
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                for topic, rows in topics.items():
                    cur.execute("DELETE FROM commands WHERE topic = %s", (topic,))
                    for r in rows:
                        cur.execute(
                            "INSERT INTO commands "
                            "(topic, section, command, description, extra, row_order) "
                            "VALUES (%s, %s, %s, %s, %s, %s)",
                            (r.topic, r.section, r.command, r.description, r.extra, r.row_order),
                        )
                        total_rows += 1
    except Exception as exc:  # noqa: BLE001 - logged to sync_runs, not swallowed
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sync_runs SET finished_at=%s, status='failed', error=%s WHERE id=%s",
                (datetime.now(timezone.utc), str(exc), run_id),
            )
        conn.commit()
        print(f"[sync] FAILED: {exc}", file=sys.stderr)
        return

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE sync_runs SET finished_at=%s, topics_synced=%s, rows_synced=%s, "
            "status='success' WHERE id=%s",
            (datetime.now(timezone.utc), len(topics), total_rows, run_id),
        )
    conn.commit()
    print(f"[sync] success: {len(topics)} topics, {total_rows} rows")


def _connect_with_retry(max_attempts: int = 10, delay: float = 2.0) -> psycopg.Connection:
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return psycopg.connect(DATABASE_URL, autocommit=False)
        except psycopg.OperationalError as exc:
            last_exc = exc
            print(f"[sync] Postgres not ready (attempt {attempt}/{max_attempts}): {exc}", file=sys.stderr)
            time.sleep(delay)
    raise RuntimeError("could not connect to Postgres") from last_exc


def main() -> None:
    conn = _connect_with_retry()
    last_mtime: datetime | None = None
    print(f"[sync] watching {XLSX_PATH} every {POLL_SECONDS}s")
    while True:
        try:
            mtime = _mtime(XLSX_PATH)
        except FileNotFoundError:
            print(f"[sync] {XLSX_PATH} not found, retrying", file=sys.stderr)
            time.sleep(POLL_SECONDS)
            continue

        if mtime != last_mtime:
            sync_once(conn, mtime)
            last_mtime = mtime

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
