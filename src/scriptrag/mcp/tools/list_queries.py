"""List queries tool for ScriptRAG MCP server."""

from typing import TypedDict

from mcp import Context

from scriptrag.mcp.server import mcp


class QueryInfo(TypedDict):
    """Information about a query."""

    name: str
    description: str | None
    category: str | None


class ListQueriesOutput(TypedDict):
    """Output format for list queries tool."""

    queries: list[QueryInfo]
    total_count: int


@mcp.tool()
async def scriptrag_list_queries(
    ctx: Context | None = None,
) -> ListQueriesOutput:
    """List all available SQL queries in the query library.

    Args:
        ctx: MCP context

    Returns:
        List of available queries with their descriptions
    """
    if ctx is None or ctx.server_context is None:
        raise ValueError("Server context not available")

    from scriptrag.api.query import QueryAPI

    settings = ctx.server_context.settings
    query_api = QueryAPI(settings=settings)

    # Get all queries
    queries = query_api.list_queries()

    # Convert to our format
    query_list = []
    for query in queries:
        query_list.append(
            QueryInfo(
                name=query.name,
                description=query.description,
                category=getattr(query, "category", None),
            )
        )

    return ListQueriesOutput(
        queries=query_list,
        total_count=len(query_list),
    )
