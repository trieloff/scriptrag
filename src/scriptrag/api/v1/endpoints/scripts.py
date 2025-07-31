"""Script management endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from scriptrag.api.db_operations import DatabaseOperations
from scriptrag.api.fountain_parser import FountainParser
from scriptrag.api.v1.schemas import (
    SceneResponse,
    ScriptDetailResponse,
    ScriptResponse,
    ScriptUploadRequest,
)
from scriptrag.config import get_logger

logger = get_logger(__name__)
router = APIRouter()


async def get_db_ops(request: Request) -> DatabaseOperations:
    """Get database operations from app state."""
    db_ops: DatabaseOperations = request.app.state.db_ops
    return db_ops


@router.post("/upload", response_model=ScriptResponse)
async def upload_script(
    script_data: ScriptUploadRequest,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> ScriptResponse:
    """Upload and parse a Fountain script."""
    try:
        # Parse fountain content
        parser = FountainParser()
        script_model = parser.parse_string(
            script_data.content, title=script_data.title, author=script_data.author
        )

        # Store in database
        script_id = await db_ops.store_script(script_model)

        # Get stored script
        stored_script = await db_ops.get_script(script_id)
        if not stored_script:
            raise HTTPException(status_code=500, detail="Failed to store script")

        return ScriptResponse(
            id=stored_script.id or "",
            title=stored_script.title,
            author=stored_script.author,
            created_at=stored_script.created_at or datetime.now(UTC),
            updated_at=stored_script.updated_at or datetime.now(UTC),
            scene_count=len(stored_script.scenes),
            character_count=len(stored_script.characters),
            has_embeddings=any(
                scene.embedding is not None for scene in stored_script.scenes
            ),
        )

    except Exception as e:
        logger.error("Failed to upload script", error=str(e))
        raise HTTPException(
            status_code=400, detail=f"Failed to parse script: {e!s}"
        ) from e


@router.post("/upload-file", response_model=ScriptResponse)
async def upload_script_file(
    file: UploadFile = File(...),
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> ScriptResponse:
    """Upload a Fountain script file."""
    if not file.filename or not file.filename.endswith(".fountain"):
        raise HTTPException(
            status_code=400, detail="Only .fountain files are supported"
        )

    try:
        content = await file.read()
        content_str = content.decode("utf-8")

        # Extract title from filename if needed
        title = (file.filename or "untitled").replace(".fountain", "")

        # Parse and store
        parser = FountainParser()
        script_model = parser.parse_string(content_str, title=title)

        script_id = await db_ops.store_script(script_model)

        stored_script = await db_ops.get_script(script_id)
        if not stored_script:
            raise HTTPException(status_code=500, detail="Failed to store script")

        return ScriptResponse(
            id=stored_script.id or "",
            title=stored_script.title,
            author=stored_script.author,
            created_at=stored_script.created_at or datetime.now(UTC),
            updated_at=stored_script.updated_at or datetime.now(UTC),
            scene_count=len(stored_script.scenes),
            character_count=len(stored_script.characters),
            has_embeddings=any(
                scene.embedding is not None for scene in stored_script.scenes
            ),
        )

    except Exception as e:
        logger.error("Failed to upload script file", error=str(e))
        raise HTTPException(
            status_code=400, detail=f"Failed to parse script: {e!s}"
        ) from e


@router.get("/", response_model=list[ScriptResponse])
async def list_scripts(
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> list[ScriptResponse]:
    """List all scripts."""
    try:
        scripts = await db_ops.list_scripts()

        return [
            ScriptResponse(
                id=str(script.id) if script.id else "",
                title=script.title,
                author=script.author,
                created_at=script.created_at or datetime.now(UTC),
                updated_at=script.updated_at or datetime.now(UTC),
                scene_count=len(script.scenes) if hasattr(script, "scenes") else 0,
                character_count=(
                    len(script.characters) if hasattr(script, "characters") else 0
                ),
                has_embeddings=False,  # TODO: Implement embedding check
            )
            for script in scripts
        ]

    except Exception as e:
        logger.error("Failed to list scripts", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list scripts") from e


@router.get("/{script_id}", response_model=ScriptDetailResponse)
async def get_script(
    script_id: str,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> ScriptDetailResponse:
    """Get script details."""
    try:
        script = await db_ops.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        return ScriptDetailResponse(
            id=script.id or "",
            title=script.title,
            author=script.author,
            created_at=script.created_at or datetime.now(UTC),
            updated_at=script.updated_at or datetime.now(UTC),
            scene_count=len(script.scenes),
            character_count=len(script.characters),
            has_embeddings=any(scene.embedding is not None for scene in script.scenes),
            scenes=[
                SceneResponse(
                    id=scene.id or "",
                    script_id=scene.script_id or "",
                    scene_number=scene.scene_number,
                    heading=scene.heading,
                    content=scene.content,
                    character_count=len(scene.characters),
                    word_count=len(scene.content.split()),
                    page_start=scene.page_start,
                    page_end=scene.page_end,
                    has_embedding=scene.embedding is not None,
                )
                for scene in script.scenes
            ],
            characters=list(script.characters),
            metadata=script.metadata or {},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get script", script_id=script_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get script") from e


@router.delete("/{script_id}")
async def delete_script(
    script_id: str,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> dict[str, str]:
    """Delete a script."""
    try:
        # Check if script exists
        script = await db_ops.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        # Delete script (cascade will handle scenes and embeddings)
        await db_ops.delete_script(script_id)

        return {"message": f"Script {script_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete script", script_id=script_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete script") from e
