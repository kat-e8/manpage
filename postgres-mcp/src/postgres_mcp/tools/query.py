"""Query tools — schema introspection and read access."""

from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import Field

from ._scope import ConnectionUriOverride, scoped_query


async def list_schemas(
    ctx: Context,
    connection_uri: ConnectionUriOverride = None,
) -> Any:
    """List all schemas in the database.

    Use this first to see what's available before listing tables.
    """
    try:
        async with scoped_query(ctx, connection_uri) as client:
            return await client.fetch(
                "SELECT schema_name FROM information_schema.schemata ORDER BY schema_name"
            )
    except Exception as exc:
        return {"error": f"Failed to list schemas: {exc}"}


async def list_tables(
    ctx: Context,
    schema: Annotated[str, Field(description="Schema to list tables from")] = "public",
    connection_uri: ConnectionUriOverride = None,
) -> Any:
    """List all tables in a schema."""
    try:
        async with scoped_query(ctx, connection_uri) as client:
            return await client.fetch(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = $1 ORDER BY table_name",
                schema,
            )
    except Exception as exc:
        return {"error": f"Failed to list tables: {exc}"}


async def describe_table(
    ctx: Context,
    table: Annotated[str, Field(description="Table name to describe")],
    schema: Annotated[str, Field(description="Schema the table lives in")] = "public",
    connection_uri: ConnectionUriOverride = None,
) -> Any:
    """Get column names, types, nullability, and defaults for a table."""
    try:
        async with scoped_query(ctx, connection_uri) as client:
            return await client.fetch(
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_schema = $1 AND table_name = $2 "
                "ORDER BY ordinal_position",
                schema,
                table,
            )
    except Exception as exc:
        return {"error": f"Failed to describe table: {exc}"}


async def run_query(
    ctx: Context,
    sql: Annotated[str, Field(description="SQL query to run, e.g. a SELECT statement")],
    connection_uri: ConnectionUriOverride = None,
) -> Any:
    """Run a SQL query against the database and return the resulting rows.

    Database-level permissions on the connecting role are the actual access
    boundary (e.g. a read-only role) -- this tool does not add its own
    write/DDL restriction on top of that.
    """
    try:
        async with scoped_query(ctx, connection_uri) as client:
            return await client.fetch(sql)
    except Exception as exc:
        return {"error": f"Query failed: {exc}"}


def register(mcp: FastMCP) -> None:
    """Register all query tools with the FastMCP instance."""
    mcp.tool()(list_schemas)
    mcp.tool()(list_tables)
    mcp.tool()(describe_table)
    mcp.tool()(run_query)
