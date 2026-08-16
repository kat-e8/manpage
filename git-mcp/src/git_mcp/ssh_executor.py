"""The one place that builds and runs a remote git command over ssh.

Every tool in tools/read.py and tools/write.py calls into run_git() --
no tool module ever touches asyncio subprocess machinery directly, and
this module never receives an argument that hasn't already been through
the appropriate validate_*() in quoting.py. Quoting happens here, once,
right before execution; structural validation happens in the caller,
before it. Neither step is ever skipped or merged with the other.
"""

import asyncio
from typing import List, Optional, Tuple

from .config import settings
from .quoting import posix_quote, windows_quote

TIMEOUT_SECONDS = 30

# Found live: git_diff against a real repo whose tracked files included a
# multi-GB log file returned a 138MB response -- unbounded output from a
# caller-supplied repo_path/ref is a real resource risk (MCP client, LLM
# context), not a hypothetical one. Each stream is capped independently;
# note this bounds the *returned* size, not subprocess memory during
# communicate() itself, which still buffers the full output before this
# function ever sees it.
MAX_OUTPUT_BYTES = 200_000


def _decode_capped(data: bytes) -> str:
    if len(data) > MAX_OUTPUT_BYTES:
        omitted = len(data) - MAX_OUTPUT_BYTES
        return data[:MAX_OUTPUT_BYTES].decode(errors="replace") + f"\n... [truncated, {omitted} more bytes omitted]"
    return data.decode(errors="replace")


class UnknownTargetError(ValueError):
    pass


class GitCommandTimeout(RuntimeError):
    pass


async def run_git(
    target: str,
    repo_path: str,
    args: List[str],
    *,
    pathspecs: Optional[List[str]] = None,
    needs_network: bool = False,
) -> Tuple[int, str, str]:
    """Run `git -C <repo_path> <args> [-- <pathspecs>]` on `target` over ssh.

    `args` must already be individually validated by the caller (ref/branch/
    remote names via quoting.validate_ref_name/validate_remote_name) --
    this function only quotes and executes.

    `pathspecs`, if given, are appended after a literal `--` end-of-options
    marker that this function inserts itself (never caller-supplied) -- the
    real protection against a pathspec being read as a flag, independent of
    quoting.validate_pathspec's own leading-dash check.

    `needs_network=True` (fetch/pull/push) sets GIT_TERMINAL_PROMPT=0 so a
    target needing interactive git credentials fails fast instead of
    hanging the call forever with no TTY to prompt against.
    """
    spec = settings.targets.get(target)
    if spec is None:
        raise UnknownTargetError(f"Unknown target {target!r}; known targets: {sorted(settings.targets)}")

    quote = posix_quote if spec.os == "posix" else windows_quote

    prefix_tokens: List[str] = []
    if needs_network:
        if spec.os == "posix":
            prefix_tokens = ["env", "GIT_TERMINAL_PROMPT=0"]
        else:
            # cmd.exe has no `env` -- `set VAR=value && command` scopes it
            # to this one invocation instead. "&&" is a control token we
            # construct ourselves, never user input, so it is deliberately
            # not passed through quote().
            prefix_tokens = ["set", "GIT_TERMINAL_PROMPT=0", "&&"]

    git_tokens = ["git", "-C", quote(repo_path)] + [quote(a) for a in args]
    if pathspecs:
        git_tokens += ["--"] + [quote(p) for p in pathspecs]

    remote_cmd = " ".join(prefix_tokens + git_tokens)

    proc = await asyncio.create_subprocess_exec(
        "ssh",
        spec.ssh,
        remote_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise GitCommandTimeout(f"git command on {target!r} timed out after {TIMEOUT_SECONDS}s")

    return proc.returncode, _decode_capped(stdout), _decode_capped(stderr)
