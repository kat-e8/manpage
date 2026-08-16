# CoderCommands MCP System

Turns `coder_commands.xlsx` (14 sheets of commands collected while learning
mongo, sql, docker, git, ansible, python, and more) into an MCP server so
Claude Code can look up the right command and explanation from a plain
question like "how do I insert a new row into a table".

Full build history, decisions, and issues found along the way are in
`coderCommands_Plan/` (`Step01_...` through `Step09_...`), and the original
plan/decisions summary is `CodeCommands.pdf`.

Moving this stack to a cloud server (clubuntu, over Tailscale) via an
immutable-image CI/CD pipeline — self-hosted GitHub Actions runner,
tag-gated deploys, no codebase ever shipped to the server — is documented
in [`Deployment/`](Deployment/), a seven-part walkthrough plus a concepts
FAQ, each as its own diagram-heavy PDF.

## Architecture

```
coder_commands.xlsx --(read, polled)--> sync --(write)--> postgres --(read)--> coder-commands-mcp --(proxied)--> gateway --> Claude Code
                                                                     docker-mcp --(proxied)--^
                                                                     postgres-mcp --(proxied)--^
```

| Service | Role | Reachable from |
|---|---|---|
| `postgres` | Canonical store (`commands`, `sync_runs` tables) | Only other containers on `codercommands-net` |
| `sync` | Watches the xlsx, normalizes it, writes it into Postgres | Not network-reachable (no server) |
| `coder-commands-mcp` | Exposes `search_commands`, `list_topics`, `browse_<topic>` as MCP tools -- the coder-commands lookup server specifically | Only `gateway`, by service name |
| `docker-mcp` | Exposes `create-container`, `deploy-compose`, `get-logs`, `list-containers` as MCP tools, driving the *host's* Docker daemon via a bind-mounted `/var/run/docker.sock` (docker-outside-of-docker -- see [Known limitations](#known-limitations-v1)) | Only `gateway`, by service name |
| `postgres-mcp` | Exposes `list_schemas`, `list_tables`, `describe_table`, `run_query` as MCP tools, against its own `postgres` by default or any database given a per-call `connection_uri` | Only `gateway`, by service name |
| `gateway` | Generic MCP gateway, not coder-commands-specific -- reverse-proxies `/coder-commands-mcp`, `/docker-mcp`, and `/postgres-mcp` to their respective services; the one published port. Meant to keep mounting whatever MCP servers this project ends up with. | The host, at `GATEWAY_HOST_PORT` |

`docker-mcp`'s source is a fork of
[QuantGeekDev/docker-mcp](https://github.com/QuantGeekDev/docker-mcp), kept
at `./docker-mcp` in this repo -- a standalone copy, duplicated from
`backend/docker-mcp/docker-mcp` rather than built from that path, so this
project has no build-time dependency on `backend/`. The two copies are
independent from the point of copying: changes to one do not propagate to
the other. The fork added a `streamable-http` transport (upstream only
shipped `stdio`, for Claude-Desktop-style subprocess use) plus the same
DNS-rebinding allow-list treatment `coder-commands-mcp` uses below, both
needed to run it as a proxied container instead of a local subprocess.

`postgres-mcp` is also this project's own code, at `./postgres-mcp` -- a
small custom FastMCP server (not the third-party `crystaldba/postgres-mcp`
image the separate `../POSTGRES` project runs for local testing). It
defaults to this project's own `postgres` service, and every tool also takes
an optional `connection_uri` to target a different database for that one
call -- the same per-call override pattern `docker-mcp` uses for
`docker_host`. No shared Docker network or sibling project is required.

## Running it

```
cp .env.example .env      # adjust if needed
docker compose up -d --build
```

Then register the servers with Claude Code (once per machine/project). All
three upstreams speak MCP Streamable HTTP, so all three are registered the
same way:

```
claude mcp add --transport http codercommands http://127.0.0.1:8100/coder-commands-mcp
claude mcp add --transport http docker http://127.0.0.1:8100/docker-mcp
claude mcp add --transport http postgres http://127.0.0.1:8100/postgres-mcp
```

Check everything is healthy:

```
docker compose ps
claude mcp get codercommands
```

## Updating the command reference

Just edit `coder_commands.xlsx` and save. The `sync` container polls the
file's modified time every `SYNC_POLL_SECONDS` (default 7s) and, on change,
re-syncs automatically -- no restart, no manual command. Watch it happen:

```
docker logs -f codercommands-sync
```

Each pass fully replaces that topic's rows (delete + reinsert), so edits,
reorders, and deletions all just work. Every pass is also logged to
`sync_runs`, queryable if you want to check sync history:

```
docker exec codercommands-postgres psql -U codercommands -d codercommands \
  -c "SELECT * FROM sync_runs ORDER BY id DESC LIMIT 5;"
```

### Adding a new topic (a new sheet)

Add the sheet to the workbook and save. `coder-commands-mcp` discovers
topics from Postgres at container startup, so a `browse_<topic>` tool
appears for it automatically the next time it restarts:

```
docker compose restart coder-commands-mcp
```

(`search_commands` and `list_topics` need no restart -- they already cover
every topic without change.)

### Sheet formatting rules ingest.py relies on

- First row is a header only if its first cell reads exactly `COMMAND`
  (case-insensitive). Otherwise every row is treated as data.
- A row with exactly one populated, all-caps cell (e.g. `IMAGE MANAGEMENT`)
  is treated as a section label applied to every row until the next one.
- If more than 30% of a sheet's rows have a blank first column, the whole
  sheet is parsed in "outline mode": populated-column-A rows are headings,
  blank-column-A rows are their column-shifted sub-entries (this is how the
  `jython` sheet is structured). Below that threshold, blank-column-A rows
  are instead folded into the previous row's notes as free text.

## Restarting / rebuilding

```
docker compose restart <service>          # restart without rebuilding
docker compose up -d --build <service>    # rebuild after a code change
docker compose down                       # stop everything (keeps data)
docker compose down -v                    # stop and wipe the Postgres volume
```

## Known limitations (v1)

- Read-only: there's no tool for Claude to write a new entry back into the
  spreadsheet or database. Edit `coder_commands.xlsx` directly.
- Search is full-text (Postgres `tsvector`/`ts_rank`), not semantic --
  wording that shares little vocabulary with the source data (e.g. a
  request phrased very differently from how a sheet describes it) can miss.
  See `Step08_LocalVerification.pdf` for a concrete example.
- A handful of source rows contain a corrupted character (`�`) from
  whatever they were originally pasted from. Ingest passes these through
  unchanged rather than guessing at the intended text.
- `docker-mcp` has no auth of its own and, via the bind-mounted host socket,
  effectively root-equivalent control of the host's Docker daemon (create
  containers with arbitrary bind mounts, read any other container's logs,
  etc). It's only reachable from other containers on `codercommands-net`
  (no published host port), which is the only thing standing between "an
  internal MCP tool" and "an open door to the host" -- treat that network
  boundary as security-relevant before changing it.
