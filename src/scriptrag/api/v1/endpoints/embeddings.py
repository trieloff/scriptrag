"""Embedding generation endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from scriptrag.api.db_operations import DatabaseOperations
from scriptrag.api.v1.schemas import (
    EmbeddingGenerateRequest,
    EmbeddingResponse,
    ResponseStatus,
)
from scriptrag.config import get_logger

logger = get_logger(__name__)
router = APIRouter()


async def get_db_ops(request: Request) -> DatabaseOperations:
    """Get database operations from app state."""
    db_ops: DatabaseOperations = request.app.state.db_ops
    return db_ops


@router.post("/scripts/{script_id}/generate", response_model=EmbeddingResponse)
async def generate_embeddings(
    script_id: str,
    request: EmbeddingGenerateRequest,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> EmbeddingResponse:
    """Generate embeddings for all scenes in a script."""
    try:
        # Check if script exists
        script = await db_ops.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        # Generate embeddings
        result = await db_ops.generate_embeddings(
            script_id, regenerate=request.regenerate
        )

        return EmbeddingResponse(
            status=ResponseStatus.SUCCESS,
            message="Embeddings generated successfully",
            script_id=script_id,
            scenes_processed=result["scenes_processed"],
            scenes_skipped=result["scenes_skipped"],
            processing_time=result["processing_time"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate embeddings", script_id=script_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to generate embeddings: {e!s}"
        ) from e


@router.get("/scripts/{script_id}/status")
async def get_embedding_status(
    script_id: str,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> dict[str, Any]:
    """Get embedding generation status for a script."""
    try:
        script = await db_ops.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        total_scenes = len(script.scenes)
        scenes_with_embeddings = sum(
            1 for scene in script.scenes if scene.embedding is not None
        )

        return {
            "script_id": script_id,
            "total_scenes": total_scenes,
            "scenes_with_embeddings": scenes_with_embeddings,
            "completion_percentage": (
                (scenes_with_embeddings / total_scenes * 100) if total_scenes > 0 else 0
            ),
            "is_complete": scenes_with_embeddings == total_scenes,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get embedding status", script_id=script_id, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail="Failed to get embedding status"
        ) from e
