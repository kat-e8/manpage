# git-mcp

MCP server for git operations against a repo on any registered tailnet
host, over SSH — typed tools (`git_status`, `git_commit`, `git_push`, etc.),
not a raw passthrough. Mirrors `docker-mcp`'s SSH-execute pattern and
`postgres-mcp`'s per-call-override tool shape; see the top-level `README.md`
and `git-mcp/design-plan.pdf` for the full design.

Every tool takes a required `target` (a registered alias, e.g. `"katmint"`)
and a `repo_path` (absolute path on that host). There is no local/default
target — this container has no meaningful repos of its own, so every call,
including ones against the host git-mcp itself runs on, goes over SSH.

## Configuration

- `GIT_MCP_SSH_KEY_PATH` / `GIT_MCP_SSH_KNOWN_HOSTS_PATH` — host paths
  bind-mounted into the container (see `docker-compose.yml`).
- `GIT_MCP_TARGETS` — JSON registry: `{"alias": {"ssh": "user@host", "os":
  "posix"|"windows"}}`. `os` selects shell-quoting dialect for that target
  — required for safe command construction, not just cosmetic. Don't add a
  new `"windows"` entry without first verifying `quoting.py`'s
  `windows_quote()` against real cmd.exe metacharacters on that specific
  host (see `design-plan.pdf`'s "Staged rollout" and `final-run/07` for how
  `katlegog` was verified before being enabled).

## Tool inventory

Read: `git_status`, `git_log`, `git_diff`, `git_show`, `git_branch_list`,
`git_remote_list`.

Write: `git_add`, `git_commit`, `git_fetch`, `git_pull`, `git_checkout`,
`git_branch_create`, `git_push`. No force/history-rewriting operations are
implemented — that's a deliberate exclusion, not a gated option.
