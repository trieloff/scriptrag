"""Query tool for ScriptRAG MCP server."""

from typing import Any, TypedDict

from mcp import Context

from scriptrag.mcp.server import mcp


class QueryOutput(TypedDict):
    """Output format for query tool."""

    result: str
    query_name: str
    row_count: int


@mcp.tool()
async def scriptrag_query(
    query_name: str,
    params: dict[str, Any] | None = None,
    limit: int = 50,
    offset: int = 0,
    output_json: bool = False,
    ctx: Context | None = None,
) -> QueryOutput:
    """Execute named SQL queries from the query library.

    Args:
        query_name: Name of query from library
        params: Query parameters
        limit: Maximum rows to return
        offset: Row offset for pagination
        output_json: Return JSON formatted output
        ctx: MCP context

    Returns:
        Query results as formatted string
    """
    if ctx is None or ctx.server_context is None:
        raise ValueError("Server context not available")

    from scriptrag.api.query import QueryAPI

    settings = ctx.server_context.settings
    query_api = QueryAPI(settings=settings)

    # Execute query and get formatted result
    try:
        result = query_api.execute_query(
            name=query_name,
            params=params,
            limit=limit,
            offset=offset,
            output_json=output_json,
        )

        # Count rows in result (simple heuristic)
        row_count = 0
        if result:
            lines = result.split("\n")
            # Assume table format has separator line
            row_count = max(0, len(lines) - 3)  # Header, separator, footer

        return QueryOutput(
            result=result or "No results",
            query_name=query_name,
            row_count=row_count,
        )

    except Exception as e:
        raise ValueError(f"Query execution failed: {e}") from e
