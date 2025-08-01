"""Search endpoints for scenes and semantic similarity."""

from fastapi import APIRouter, Depends, HTTPException, Request

from scriptrag.api.db_operations import DatabaseOperations
from scriptrag.api.v1.schemas import (
    ResponseStatus,
    SceneSearchRequest,
    SearchResponse,
    SearchResultItem,
    SemanticSearchRequest,
)
from scriptrag.config import get_logger

logger = get_logger(__name__)
router = APIRouter()


async def get_db_ops(request: Request) -> DatabaseOperations:
    """Get database operations from app state."""
    db_ops: DatabaseOperations = request.app.state.db_ops
    return db_ops


@router.post("/scenes", response_model=SearchResponse)
async def search_scenes(
    search_request: SceneSearchRequest,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> SearchResponse:
    """Search scenes with text and filters."""
    try:
        # Validate required parameters
        if not search_request.query:
            raise HTTPException(status_code=422, detail="Query is required")

        result = await db_ops.search_scenes(
            query=search_request.query,
            script_id=search_request.script_id or "",  # Provide empty string for None
            character=search_request.character,
            limit=search_request.limit,
            offset=search_request.offset,
        )

        return SearchResponse(
            status=ResponseStatus.SUCCESS,
            results=[
                SearchResultItem(scene=item["scene"], score=None, highlights=[])
                for item in result["results"]
            ],
            total=result["total"],
            limit=result["limit"],
            offset=result["offset"],
        )

    except HTTPException:
        # Re-raise HTTPException without wrapping
        raise
    except Exception as e:
        logger.error("Failed to search scenes", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to search scenes") from e


@router.post("/similar", response_model=SearchResponse)
async def semantic_search(
    search_request: SemanticSearchRequest,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> SearchResponse:
    """Search scenes by semantic similarity."""
    try:
        # Validate required parameters
        if not search_request.query:
            raise HTTPException(status_code=422, detail="Query is required")

        result = await db_ops.semantic_search(
            query=search_request.query,
            script_id=search_request.script_id or "",  # Provide empty string for None
            threshold=search_request.threshold,
            limit=search_request.limit,
        )

        return SearchResponse(
            status=ResponseStatus.SUCCESS,
            results=[
                SearchResultItem(
                    scene=item["scene"],
                    score=item["score"],
                    highlights=item.get("highlights", []),
                )
                for item in result["results"]
            ],
            total=result["total"],
            limit=result["limit"],
            offset=result["offset"],
        )

    except Exception as e:
        logger.error("Failed to perform semantic search", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to perform semantic search: {e!s}"
        ) from e


@router.get("/scenes/by-character/{character_name}")
async def search_by_character(
    character_name: str,
    script_id: str | None = None,
    limit: int = 10,
    offset: int = 0,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> SearchResponse:
    """Search scenes containing a specific character."""
    try:
        # Allow searching without script_id for global search
        pass

        result = await db_ops.search_scenes(
            query="",  # Empty query for character-only search
            character=character_name,
            script_id=script_id or "",
            limit=limit,
            offset=offset,
        )

        return SearchResponse(
            status=ResponseStatus.SUCCESS,
            results=[
                SearchResultItem(scene=item["scene"], score=None, highlights=[])
                for item in result["results"]
            ],
            total=result["total"],
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(
            "Failed to search by character", character=character_name, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail="Failed to search by character"
        ) from e
