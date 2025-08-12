"""Query tools for MCP server."""

import json
from typing import Any

from mcp.server import FastMCP

from scriptrag.api.query import QueryAPI
from scriptrag.config import get_logger, get_settings
from scriptrag.query import QuerySpec

logger = get_logger(__name__)


def register_query_tools(mcp: FastMCP) -> None:
    """Register query tools with the MCP server.

    This function dynamically creates one tool per discovered query.

    Args:
        mcp: FastMCP server instance
    """
    # Get settings and initialize API
    settings = get_settings()
    api = QueryAPI(settings)

    # Force reload queries
    api.loader.reload_queries()

    # Discover all queries
    queries = api.list_queries()

    if not queries:
        logger.warning("No queries found in query directory")

        # Register a placeholder tool to indicate no queries
        @mcp.tool()
        async def scriptrag_query_list_empty() -> dict[str, Any]:
            """List available SQL queries.

            No queries are currently available. Add .sql files to the query
            directory to make them available as tools.

            Returns:
                Dictionary with empty query list
            """
            return {
                "success": True,
                "queries": [],
                "message": "No queries found. Add .sql files to the query directory.",
            }

        return

    # Register a tool for each query
    for spec in queries:
        # Create a unique function for each query
        # We need to capture spec in the closure properly
        def create_query_tool(query_spec: QuerySpec) -> Any:
            """Create a query tool for the given spec."""

            # Build the tool function
            async def query_tool(**kwargs: Any) -> dict[str, Any]:
                """Execute the query and return results."""
                try:
                    # Extract limit and offset
                    limit = kwargs.pop("limit", None)
                    offset = kwargs.pop("offset", None)

                    # Remaining kwargs are query parameters
                    params = kwargs

                    # Get fresh API instance
                    from scriptrag.config import get_settings as get_config

                    current_api = QueryAPI(get_config())

                    # Execute query and get JSON output
                    result = current_api.execute_query(
                        name=query_spec.name,
                        params=params,
                        limit=limit,
                        offset=offset,
                        output_json=True,
                    )

                    # Parse JSON result
                    if result:
                        data = json.loads(result)
                        return {
                            "success": True,
                            "query": query_spec.name,
                            "results": data,
                        }
                    return {
                        "success": True,
                        "query": query_spec.name,
                        "results": [],
                        "message": "No results found",
                    }

                except Exception as e:
                    logger.error(f"Query '{query_spec.name}' failed: {e}")
                    return {
                        "error": str(e),
                        "success": False,
                        "query": query_spec.name,
                    }

            # Set function metadata
            tool_name = f"scriptrag_query_{query_spec.name.replace('-', '_')}"
            query_tool.__name__ = tool_name

            # Build docstring with parameter documentation
            docstring_parts = [
                query_spec.description or f"Execute {query_spec.name} query",
                "",
                "Args:",
            ]

            # Add parameter documentation
            for param in query_spec.params:
                param_doc = f"    {param.name}: {param.help or ''}"
                if param.type:
                    param_doc += f" (type: {param.type})"
                if param.choices:
                    param_doc += f" (choices: {', '.join(param.choices)})"
                if param.default is not None:
                    param_doc += f" (default: {param.default})"
                docstring_parts.append(param_doc)

            # Add standard parameters if query supports them
            has_limit, has_offset = query_spec.has_limit_offset()
            if has_limit:
                docstring_parts.append("    limit: Maximum number of rows to return")
            if has_offset:
                docstring_parts.append("    offset: Number of rows to skip")

            docstring_parts.extend(
                [
                    "",
                    "Returns:",
                    "    Dictionary containing query results",
                ]
            )

            query_tool.__doc__ = "\n".join(docstring_parts)

            return query_tool

        # Create and register the tool
        tool_func = create_query_tool(spec)
        mcp.tool()(tool_func)

    # Also register a list tool to show available queries
    @mcp.tool()
    async def scriptrag_query_list() -> dict[str, Any]:
        """List all available SQL queries.

        Returns a list of all queries that can be executed, along with
        their descriptions and parameter information.

        Returns:
            Dictionary containing list of available queries
        """
        query_list = []
        for spec in queries:
            query_info = {
                "name": spec.name,
                "description": spec.description,
                "params": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "required": p.required,
                        "help": p.help,
                        "default": p.default,
                        "choices": p.choices,
                    }
                    for p in spec.params
                ],
            }
            query_list.append(query_info)

        return {
            "success": True,
            "queries": query_list,
        }
