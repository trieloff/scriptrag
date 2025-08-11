"""MCP tool for semantic search using embeddings."""

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from scriptrag.api.query import QueryAPI
from scriptrag.config import get_logger, get_settings
from scriptrag.mcp.models import BibleSearchResult, SemanticSearchResult
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import AsyncAPIWrapper, format_error_response

logger = get_logger(__name__)


class SemanticSearchInput(BaseModel):
    """Input for semantic search."""

    query: str = Field(..., min_length=3, description="Semantic search query")
    include_bible: bool = Field(True, description="Include bible content in search")
    only_bible: bool = Field(False, description="Search only bible content")
    threshold: float = Field(0.7, ge=0.0, le=1.0, description="Similarity threshold")
    limit: int = Field(10, ge=1, le=50, description="Maximum results")


class SemanticSearchOutput(BaseModel):
    """Output from semantic search."""

    success: bool
    results: list[SemanticSearchResult]
    bible_results: list[BibleSearchResult]
    total_count: int
    query_embedding_info: dict | None = None
    message: str | None = None


@mcp.tool()
async def scriptrag_semantic_search(
    query: str,
    include_bible: bool = True,
    only_bible: bool = False,
    threshold: float = 0.7,
    limit: int = 10,
    ctx: Context | None = None,
) -> SemanticSearchOutput:
    """Semantic search using vector embeddings.

    Args:
        query: Semantic search query
        include_bible: Include bible content in search
        only_bible: Search only bible content
        threshold: Similarity threshold (0.0-1.0)
        limit: Maximum results (1-50)
        ctx: MCP context

    Returns:
        Semantic search results with similarity scores
    """
    try:
        # Validate inputs
        limit = max(1, min(50, limit))
        threshold = max(0.0, min(1.0, threshold))

        if ctx:
            search_scope = "bible only" if only_bible else "all content"
            await ctx.info(
                f"Semantic search for '{query}' in {search_scope} (threshold={threshold})"
            )

        # Use Query API for semantic search
        settings = get_settings()
        query_api = QueryAPI(settings)
        wrapper = AsyncAPIWrapper()

        # Perform semantic search
        search_results = await wrapper.run_sync(
            query_api.semantic_search,
            query=query,
            limit=limit,
            threshold=threshold,
            include_bible=include_bible,
            only_bible=only_bible,
        )

        # Convert results to MCP models
        semantic_results = []
        bible_results = []

        for result in search_results.get("results", []):
            content_type = result.get("type", "unknown")

            if content_type == "bible":
                bible_results.append(
                    BibleSearchResult(
                        bible_id=result.get("id", 0),
                        script_id=result.get("script_id", 0),
                        content=result.get("content", ""),
                        similarity_score=result.get("score", 0.0),
                        chunk_index=result.get("chunk_index"),
                    )
                )
            else:
                semantic_results.append(
                    SemanticSearchResult(
                        content_type=content_type,
                        content_id=result.get("id", 0),
                        content=result.get("content", ""),
                        similarity_score=result.get("score", 0.0),
                        metadata=result.get("metadata"),
                    )
                )

        total_count = len(semantic_results) + len(bible_results)

        # Get embedding info if available
        query_embedding_info = search_results.get("embedding_info")

        if ctx:
            await ctx.info(
                f"Found {total_count} results ({len(semantic_results)} scenes, {len(bible_results)} bible entries)"
            )

        return SemanticSearchOutput(
            success=True,
            results=semantic_results,
            bible_results=bible_results,
            total_count=total_count,
            query_embedding_info=query_embedding_info,
            message=f"Found {total_count} semantic matches",
        )

    except Exception as e:
        logger.error("Failed to perform semantic search", error=str(e))
        error_response = format_error_response(e, "scriptrag_semantic_search")
        return SemanticSearchOutput(
            success=False,
            results=[],
            bible_results=[],
            total_count=0,
            message=error_response["message"],
        )
