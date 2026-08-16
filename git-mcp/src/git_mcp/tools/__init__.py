"""git-mcp tool modules.

Each module exposes a register(mcp) function that registers its tools with
the FastMCP instance. Call register_all(mcp) from server.py to register
everything at once.

Tool inventory (13 total):

Read (6):
  git_status, git_log, git_diff, git_show, git_branch_list, git_remote_list

Write (7):
  git_add, git_commit, git_fetch, git_pull, git_checkout, git_branch_create,
  git_push

No force-push, reset --hard, clean -f, rebase, commit --amend, or any other
history-rewriting operation is implemented -- deliberately excluded, not
gated behind a runtime flag (see git-mcp/design-plan.pdf).
"""

from fastmcp import FastMCP

from . import read, write

__all__ = ["read", "write", "register_all"]


def register_all(mcp: FastMCP) -> None:
    """Register all tool modules with the FastMCP instance."""
    read.register(mcp)
    write.register(mcp)
