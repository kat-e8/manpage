"""Configuration management for git MCP server."""

from typing import Dict, Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class TargetSpec(BaseModel):
    """One registered SSH destination a tool call can name as `target`.

    `os` selects which shell-quoting dialect ssh_executor.py uses when
    building the remote command -- posix (shlex-style) or windows
    (cmd.exe-style). Getting this wrong for a target is a command-injection
    risk, not a formatting detail, so it's a required field with no default.
    """

    ssh: str
    os: Literal["posix", "windows"]


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file.

    No "default" target exists (unlike postgres-mcp's database_url) --
    git-mcp's own container has no meaningful repos on it, so every tool
    call must name a target explicitly, resolved against this registry.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    targets: Dict[str, TargetSpec] = {}

    server_host: str = "0.0.0.0"
    server_port: int = 8010


settings = Settings()
