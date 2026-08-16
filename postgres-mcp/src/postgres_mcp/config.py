"""Configuration management for Postgres MCP server."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file.

    database_url matches the DATABASE_URL convention already used by the
    sync and coder-commands-mcp services in this compose project, rather
    than a postgres-mcp-specific prefix, so the same variable name works
    everywhere.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql://mcp_user:mcp_secure_password@postgres:5432/application_db",
        description=(
            "Default Postgres connection string, used when a tool call gives "
            "no connection_uri override."
        ),
    )

    server_host: str = Field(default="0.0.0.0", description="Host to bind the MCP server to")

    server_port: int = Field(default=8000, description="Port to bind the MCP server to")


settings = Settings()
