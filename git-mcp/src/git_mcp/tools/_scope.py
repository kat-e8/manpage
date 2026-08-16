"""Shared per-call parameter types for every git-mcp tool.

No connection/pool to scope here (unlike postgres-mcp's _scope.py) -- every
call is a stateless ssh subprocess, so this module only holds the common
Annotated parameter shapes every tool function reuses.
"""

from typing import Annotated

from pydantic import Field

TargetArg = Annotated[
    str,
    Field(
        description=(
            "Registered target alias, e.g. 'clubuntu', 'katmint', 'katlegog'. "
            "No default -- every call must name a target explicitly."
        )
    ),
]

RepoPathArg = Annotated[
    str,
    Field(description="Absolute path to the git repository on the target host's filesystem."),
]
