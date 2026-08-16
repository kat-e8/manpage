# postgres-mcp

MCP server for ad-hoc Postgres access. Defaults to the database named by
`DATABASE_URL`, but any tool call can override the target for that call
only via `connection_uri` — mirroring the same per-call override pattern
used by `docker-mcp` (`docker_host`) and `ignition-mcp` (`gateway_url`,
`api_key`) elsewhere in this system.

## Usage

```
uv run python mcp_server.py                     # HTTP on port 8000
uv run python mcp_server.py --transport stdio    # stdio for Claude Desktop
```

## Tools

- `list_schemas` — schemas in the target database
- `list_tables(schema="public")` — tables in a schema
- `describe_table(table, schema="public")` — columns, types, nullability, defaults
- `run_query(sql)` — run a query and return the resulting rows

All four take an optional `connection_uri` to target a different database
for that one call. Database-level permissions on the connecting role are
the actual access boundary (e.g. a read-only role) — these tools don't add
their own write/DDL restriction on top of that.
