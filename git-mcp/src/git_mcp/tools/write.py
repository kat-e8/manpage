"""Safe mutating git tools.

Deliberately excluded from this module, by omission rather than a runtime
gate (see git-mcp/design-plan.pdf): force-push, `reset --hard`,
`clean -f`/`-fdx`, rebase, `commit --amend`, history rewriting, force
branch delete, `tag -f`, `checkout --force`. None of these are implemented
anywhere in git-mcp -- there is no `force` parameter on any tool here.
"""

from typing import Any, List, Optional

from fastmcp import FastMCP

from .. import ssh_executor
from ..quoting import validate_pathspec, validate_ref_name, validate_remote_name
from ._scope import RepoPathArg, TargetArg


def _result(returncode: int, stdout: str, stderr: str) -> Any:
    if returncode != 0:
        return {"error": stderr.strip() or stdout.strip() or f"git exited with code {returncode}"}
    return {"output": stdout}


async def git_add(target: TargetArg, repo_path: RepoPathArg, pathspecs: List[str]) -> Any:
    """Stage files for the next commit."""
    try:
        validated = [validate_pathspec(p) for p in pathspecs]
        code, out, err = await ssh_executor.run_git(target, repo_path, ["add"], pathspecs=validated)
        return _result(code, out, err)
    except Exception as exc:
        return {"error": f"git_add failed: {exc}"}


async def git_commit(target: TargetArg, repo_path: RepoPathArg, message: str, all: bool = False) -> Any:
    """Commit staged changes. `all=True` also stages modified/deleted tracked
    files first (git commit -a) -- new untracked files still need git_add.
    No --amend -- always creates a new commit."""
    try:
        args = ["commit"]
        if all:
            args.append("-a")
        args += ["-m", message]
        code, out, err = await ssh_executor.run_git(target, repo_path, args)
        return _result(code, out, err)
    except Exception as exc:
        return {"error": f"git_commit failed: {exc}"}


async def git_fetch(target: TargetArg, repo_path: RepoPathArg, remote: str = "origin") -> Any:
    """Fetch refs and objects from a remote without merging."""
    try:
        args = ["fetch", validate_remote_name(remote)]
        code, out, err = await ssh_executor.run_git(target, repo_path, args, needs_network=True)
        return _result(code, out, err)
    except Exception as exc:
        return {"error": f"git_fetch failed: {exc}"}


async def git_pull(
    target: TargetArg,
    repo_path: RepoPathArg,
    remote: str = "origin",
    branch: Optional[str] = None,
) -> Any:
    """Fetch and merge from a remote. Plain merge only -- no --rebase, no
    --force."""
    try:
        args = ["pull", validate_remote_name(remote)]
        if branch:
            args.append(validate_ref_name(branch))
        code, out, err = await ssh_executor.run_git(target, repo_path, args, needs_network=True)
        return _result(code, out, err)
    except Exception as exc:
        return {"error": f"git_pull failed: {exc}"}


async def git_checkout(target: TargetArg, repo_path: RepoPathArg, ref: str, create: bool = False) -> Any:
    """Switch to an existing branch/ref, or create a new one (create=True,
    equivalent to `git checkout -b`). No --force -- git itself refuses if
    this would discard uncommitted changes, and that refusal is preserved
    here, not worked around."""
    try:
        args = ["checkout"]
        if create:
            args.append("-b")
        args.append(validate_ref_name(ref))
        code, out, err = await ssh_executor.run_git(target, repo_path, args)
        return _result(code, out, err)
    except Exception as exc:
        return {"error": f"git_checkout failed: {exc}"}


async def git_branch_create(
    target: TargetArg,
    repo_path: RepoPathArg,
    name: str,
    start_point: Optional[str] = None,
) -> Any:
    """Create a new branch without switching to it. `start_point` defaults
    to HEAD if omitted."""
    try:
        args = ["branch", validate_ref_name(name)]
        if start_point:
            args.append(validate_ref_name(start_point))
        code, out, err = await ssh_executor.run_git(target, repo_path, args)
        return _result(code, out, err)
    except Exception as exc:
        return {"error": f"git_branch_create failed: {exc}"}


async def git_push(
    target: TargetArg,
    repo_path: RepoPathArg,
    remote: str = "origin",
    branch: Optional[str] = None,
) -> Any:
    """Push commits to a remote. Plain push only -- there is no force
    parameter on this tool, and none is ever constructed."""
    try:
        args = ["push", validate_remote_name(remote)]
        if branch:
            args.append(validate_ref_name(branch))
        code, out, err = await ssh_executor.run_git(target, repo_path, args, needs_network=True)
        return _result(code, out, err)
    except Exception as exc:
        return {"error": f"git_push failed: {exc}"}


def register(mcp: FastMCP) -> None:
    """Register all write tools with the FastMCP instance."""
    mcp.tool()(git_add)
    mcp.tool()(git_commit)
    mcp.tool()(git_fetch)
    mcp.tool()(git_pull)
    mcp.tool()(git_checkout)
    mcp.tool()(git_branch_create)
    mcp.tool()(git_push)
