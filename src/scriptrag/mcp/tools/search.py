"""Search tool for MCP server."""

from typing import Any

from mcp.server import FastMCP

from scriptrag.api.search import SearchAPI
from scriptrag.config import get_logger

logger = get_logger(__name__)


def register_search_tool(mcp: FastMCP) -> None:
    """Register the search tool with the MCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool()
    async def scriptrag_search(
        query: str,
        character: str | None = None,
        dialogue: str | None = None,
        parenthetical: str | None = None,
        location: str | None = None,  # noqa: ARG001
        project: str | None = None,
        range: str | None = None,  # noqa: A002
        fuzzy: bool = False,
        strict: bool = False,
        limit: int = 5,
        offset: int = 0,
        include_bible: bool = True,
        only_bible: bool = False,
    ) -> dict[str, Any]:
        """Search through indexed screenplays.

        This tool searches through all indexed scripts in the database.
        It automatically detects:
        - ALL CAPS words as characters or locations
        - "Quoted text" as dialogue
        - (Parenthetical text) as stage directions

        By default, queries longer than 10 words trigger vector search.
        Use strict=True to disable this or fuzzy=True to always enable it.

        Args:
            query: Search query (quoted dialogue, parentheticals, CAPS)
            character: Filter by character name
            dialogue: Search for specific dialogue
            parenthetical: Search for parenthetical directions
            location: Filter by location
            project: Filter by project/script title
            range: Episode range (e.g., s1e2-s1e5)
            fuzzy: Enable fuzzy/vector search
            strict: Disable vector search, use exact matching only
            limit: Maximum number of results to return
            offset: Skip this many results (for pagination)
            include_bible: Include bible content in search results
            only_bible: Search only bible content, exclude script scenes

        Returns:
            Dictionary containing search results with scenes and metadata
        """
        try:
            # Initialize search API
            search_api = SearchAPI.from_config()

            # Validate conflicting options
            if fuzzy and strict:
                return {
                    "error": "Cannot use both fuzzy and strict options",
                    "success": False,
                }

            if include_bible is False and only_bible:
                return {
                    "error": "Cannot use both no_bible and only_bible options",
                    "success": False,
                }

            # Execute search
            response = search_api.search(
                query=query,
                character=character,
                dialogue=dialogue,
                parenthetical=parenthetical,
                project=project,
                range_str=range,
                fuzzy=fuzzy,
                strict=strict,
                limit=limit,
                offset=offset,
                include_bible=include_bible,
                only_bible=only_bible,
            )

            # Convert response to dictionary
            results = []
            for result in response.results:
                result_dict = {
                    "script_id": result.script_id,
                    "script_title": result.script_title,
                    "script_author": result.script_author,
                    "scene_id": result.scene_id,
                    "scene_number": result.scene_number,
                    "scene_heading": result.scene_heading,
                    "scene_location": result.scene_location,
                    "scene_time": result.scene_time,
                    "scene_content": result.scene_content,
                    "season": result.season,
                    "episode": result.episode,
                    "match_type": result.match_type,
                    "relevance_score": result.relevance_score,
                }

                # Add optional fields if present
                if result.matched_text:
                    result_dict["matched_text"] = result.matched_text
                if result.character_name:
                    result_dict["character_name"] = result.character_name

                results.append(result_dict)

            # Convert bible results
            bible_results = []
            for bible_result in response.bible_results:
                bible_dict = {
                    "script_id": bible_result.script_id,
                    "script_title": bible_result.script_title,
                    "bible_id": bible_result.bible_id,
                    "bible_title": bible_result.bible_title,
                    "chunk_id": bible_result.chunk_id,
                    "chunk_heading": bible_result.chunk_heading,
                    "chunk_level": bible_result.chunk_level,
                    "chunk_content": bible_result.chunk_content,
                    "match_type": bible_result.match_type,
                    "relevance_score": bible_result.relevance_score,
                }
                if bible_result.matched_text:
                    bible_dict["matched_text"] = bible_result.matched_text
                bible_results.append(bible_dict)

            return {
                "success": True,
                "query": {
                    "raw_query": response.query.raw_query,
                    "text_query": response.query.text_query,
                    "mode": response.query.mode.value,
                },
                "results": results,
                "bible_results": bible_results,
                "total_count": response.total_count,
                "bible_total_count": response.bible_total_count,
                "has_more": response.has_more,
                "execution_time_ms": response.execution_time_ms,
                "search_methods": response.search_methods,
            }

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {
                "error": str(e),
                "success": False,
            }
