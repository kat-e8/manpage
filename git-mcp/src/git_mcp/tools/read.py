"""Read-only git tools -- safe by construction, no mutation possible."""

from typing import Any, Optional

from fastmcp import FastMCP

from .. import ssh_executor
from ..quoting import validate_pathspec, validate_ref_name
from ._scope import RepoPathArg, TargetArg


def _result(returncode: int, stdout: str, stderr: str) -> Any:
    if returncode != 0:
        return {"error": stderr.strip() or stdout.strip() or f"git exited with code {returncode}"}
    return {"output": stdout}


async def git_status(target: TargetArg, repo_path: RepoPathArg) -> Any:
    """Show the working tree status: staged, unstaged, and untracked changes."""
    try:
        code, out, err = await ssh_executor.run_git(target, repo_path, ["status"])
        return _result(code, out, err)
    except Exception as exc:
        return {"error": f"git_status failed: {exc}"}


async def git_log(
    target: TargetArg,
    repo_path: RepoPathArg,
    max_count: int = 20,
    ref: Optional[str] = None,
) -> Any:
    """Show commit history, most recent first."""
    try:
        args = ["log", f"--max-count={max_count}", "--oneline", "--decorate"]
        if ref:
            args.append(validate_ref_name(ref))
        code, out, err = await ssh_executor.run_git(target, repo_path, args)
        return _result(code, out, err)
    except Exception as exc:
        return {"error": f"git_log failed: {exc}"}


async def git_diff(
    target: TargetArg,
    repo_path: RepoPathArg,
    ref: Optional[str] = None,
    staged: bool = False,
    path: Optional[str] = None,
) -> Any:
    """Show changes between commits, working tree, or the staging area.

    With no arguments, shows unstaged changes. `staged=True` shows what's
    staged for the next commit. `ref` diffs against a specific commit/branch.
    """
    try:
        args = ["diff"]
        if staged:
            args.append("--staged")
        if ref:
            args.append(validate_ref_name(ref))
        pathspecs = [validate_pathspec(path)] if path else None
        code, out, err = await ssh_executor.run_git(target, repo_path, args, pathspecs=pathspecs)
        return _result(code, out, err)
    except Exception as exc:
        return {"error": f"git_diff failed: {exc}"}


async def git_show(target: TargetArg, repo_path: RepoPathArg, ref: str) -> Any:
    """Show the log message and diff for a single commit/ref."""
    try:
        args = ["show", validate_ref_name(ref)]
        code, out, err = await ssh_executor.run_git(target, repo_path, args)
        return _result(code, out, err)
    except Exception as exc:
        return {"error": f"git_show failed: {exc}"}


async def git_branch_list(target: TargetArg, repo_path: RepoPathArg, include_remote: bool = True) -> Any:
    """List branches. include_remote also lists remote-tracking branches."""
    try:
        args = ["branch", "-a"] if include_remote else ["branch"]
        code, out, err = await ssh_executor.run_git(target, repo_path, args)
        return _result(code, out, err)
    except Exception as exc:
        return {"error": f"git_branch_list failed: {exc}"}


async def git_remote_list(target: TargetArg, repo_path: RepoPathArg) -> Any:
    """List configured remotes and their URLs."""
    try:
        code, out, err = await ssh_executor.run_git(target, repo_path, ["remote", "-v"])
        return _result(code, out, err)
    except Exception as exc:
        return {"error": f"git_remote_list failed: {exc}"}


def register(mcp: FastMCP) -> None:
    """Register all read tools with the FastMCP instance."""
    mcp.tool()(git_status)
    mcp.tool()(git_log)
    mcp.tool()(git_diff)
    mcp.tool()(git_show)
    mcp.tool()(git_branch_list)
    mcp.tool()(git_remote_list)
