"""Two independent safety layers for building a remote git command.

SSH always re-joins its trailing argv into one string and hands it to the
*target's* login shell -- there is no argv-preserving remote-exec mode in
the protocol. That creates two risks quoting alone does not fully cover:

1. Shell-metacharacter injection -- a backtick or `$( )` in a commit
   message gets executed by the target's shell instead of stored as text.
   Mitigated here by posix_quote()/windows_quote(), dialect-selected by the
   target's registered `os`.

2. Argument-shape / flag injection -- a perfectly shell-safe string can
   still be dangerous by *position*: a branch name of `--upload-pack=...`
   or a pathspec of `--force` gets parsed by git itself as a flag once it
   arrives intact as an argument, regardless of quoting. Mitigated here by
   validate_ref_name()/validate_remote_name(), called *before* quoting --
   never skipped, never merged into the quoting step.
"""

import shlex

_REF_NAME_RE_DISALLOWED = set(' \t\n\r~^:?*[\\')


def posix_quote(s: str) -> str:
    """Shell-safe quoting for POSIX targets (sh/bash)."""
    return shlex.quote(s)


def windows_quote(s: str) -> str:
    """Shell-safe quoting for Windows (cmd.exe) targets.

    Two layers, both required:

    - The argv layer (how CreateProcess/CommandLineToArgvW splits a command
      line into arguments) -- handled by the backslash-doubling-before-
      quotes algorithm below, the same one Python's own subprocess module
      uses on Windows.
    - The cmd.exe tokenizer layer itself, which -- unlike a POSIX shell --
      does NOT fully suppress its own metacharacters (`&|<>^()!"`) just by
      being inside double quotes for `%` specifically: percent-expansion in
      cmd.exe happens regardless of quoting. There is no reliable universal
      escape for a bare `%` at the `cmd /c "..."` invocation level, so
      inputs containing one are rejected outright rather than passed
      through with a false sense of safety.

    NOTE: per the approved design plan, Windows-target support is gated
    behind dedicated verification of this function against real cmd.exe
    metacharacter test cases before any Windows registry entry is enabled
    in production (see git-mcp/design-plan.pdf, "Staged rollout").
    """
    if "%" in s:
        raise ValueError(
            "Argument contains '%', which cmd.exe can expand as an environment "
            "variable reference regardless of quoting -- rejected rather than "
            "passed through unsafely."
        )
    if any(c in s for c in "\n\r\x00"):
        raise ValueError("Argument contains a control character that is not safe to pass through ssh.")

    needs_quoting = s == "" or any(c in s for c in ' \t"&|<>^()!\'')
    if not needs_quoting:
        return s

    result = ['"']
    n_backslashes = 0
    for c in s:
        if c == "\\":
            n_backslashes += 1
        elif c == '"':
            result.append("\\" * (n_backslashes * 2 + 1))
            result.append('"')
            n_backslashes = 0
        else:
            if n_backslashes:
                result.append("\\" * n_backslashes)
                n_backslashes = 0
            result.append(c)
    if n_backslashes:
        result.append("\\" * n_backslashes * 2)
    result.append('"')
    return "".join(result)


def validate_ref_name(name: str, *, label: str = "ref") -> str:
    """Reject anything that isn't safely shaped as a git ref/branch name.

    Conservative subset of `git check-ref-format` -- rejects, rather than
    tries to sanitize, anything ambiguous. Most importantly: rejects a
    leading '-', since git parses a leading-dash argument as a flag no
    matter how safely it was shell-quoted.
    """
    if not name:
        raise ValueError(f"{label} must not be empty")
    if name.startswith("-"):
        raise ValueError(f"{label} {name!r} must not start with '-' (would be parsed as a flag)")
    if name.startswith("/") or name.endswith("/"):
        raise ValueError(f"{label} {name!r} must not start or end with '/'")
    if ".." in name:
        raise ValueError(f"{label} {name!r} must not contain '..'")
    if name.endswith(".lock") or name.endswith("."):
        raise ValueError(f"{label} {name!r} must not end with '.' or '.lock'")
    if name == "@":
        raise ValueError(f"{label} must not be exactly '@'")
    if "//" in name:
        raise ValueError(f"{label} {name!r} must not contain '//'")
    if any(c in _REF_NAME_RE_DISALLOWED for c in name):
        raise ValueError(f"{label} {name!r} contains a disallowed character")
    return name


def validate_remote_name(name: str) -> str:
    """Remote names are a narrower subset of ref names -- short identifiers
    like 'origin', never a raw URL (closes off a push/fetch-to-attacker-URL
    vector)."""
    validate_ref_name(name, label="remote")
    if not all(c.isalnum() or c in "._-" for c in name):
        raise ValueError(f"remote {name!r} must be a short name (letters, digits, '.', '_', '-'), not a URL")
    return name


def validate_pathspec(path: str) -> str:
    """Pathspecs (git add/diff arguments) get their real protection from a
    literal '--' end-of-options marker inserted by ssh_executor.py itself,
    never caller-supplied -- this validation is a second, independent
    check, not the only one."""
    if not path:
        raise ValueError("pathspec must not be empty")
    if path.startswith("-"):
        raise ValueError(f"pathspec {path!r} must not start with '-' (would be parsed as a flag)")
    if any(c in "\n\r\x00" for c in path):
        raise ValueError(f"pathspec {path!r} contains a control character")
    return path
