"""Status tool for ScriptRAG MCP server."""

from typing import TypedDict

from mcp import Context

from scriptrag.mcp.server import mcp


class StatusOutput(TypedDict):
    """Output format for status tool."""

    database_path: str
    database_exists: bool
    database_size_mb: float | None
    available_queries: int


@mcp.tool()
async def scriptrag_status(
    ctx: Context | None = None,
) -> StatusOutput:
    """Get ScriptRAG system status.

    Returns basic information about the database and available queries.

    Args:
        ctx: MCP context

    Returns:
        System status information
    """
    if ctx is None or ctx.server_context is None:
        raise ValueError("Server context not available")

    settings = ctx.server_context.settings

    # Check database
    db_path = settings.database_path
    db_exists = db_path.exists()
    db_size_mb = None

    if db_exists:
        db_size_mb = db_path.stat().st_size / (1024 * 1024)  # Convert to MB

    # Count available queries
    available_queries = 0
    try:
        from scriptrag.api.query import QueryAPI

        query_api = QueryAPI(settings)
        queries = query_api.list_queries()
        available_queries = len(queries)
    except (ImportError, AttributeError):
        # Query library may not be available or configured
        available_queries = 0

    return StatusOutput(
        database_path=str(db_path),
        database_exists=db_exists,
        database_size_mb=round(db_size_mb, 2) if db_size_mb else None,
        available_queries=available_queries,
    )
