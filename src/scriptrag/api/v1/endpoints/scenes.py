"""Scene management CRUD endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from scriptrag.api.db_operations import DatabaseOperations
from scriptrag.api.v1.schemas import (
    SceneCreateRequest,
    SceneOrderingRequest,
    SceneOrderingResponse,
    SceneResponse,
    SceneUpdateRequest,
)
from scriptrag.config import get_logger


def scene_to_response(scene: Any) -> SceneResponse:
    """Convert a SceneModel or dict to SceneResponse."""
    if isinstance(scene, dict):
        # Handle dict responses from database operations
        return SceneResponse(
            id=str(scene.get("id", "")),
            script_id=str(scene.get("script_id", "")),
            scene_number=scene.get("scene_number", 0),
            heading=scene.get("heading", ""),
            content=scene.get("content", ""),
            character_count=scene.get("character_count", 0),
            word_count=scene.get("word_count", 0),
            page_start=scene.get("page_start"),
            page_end=scene.get("page_end"),
            has_embedding=scene.get("has_embedding", False),
        )
    # Handle SceneModel objects
    return SceneResponse(
        id=str(scene.id) if scene.id else "",
        script_id=str(scene.script_id) if scene.script_id else "",
        scene_number=getattr(scene, "scene_number", 0),  # SceneModel uses scene_number
        heading=scene.heading or "",
        content=scene.content or "",  # SceneModel uses content not description
        character_count=len(scene.characters) if hasattr(scene, "characters") else 0,
        word_count=len((scene.content or "").split()),  # Use content
        page_start=getattr(scene, "page_start", None),
        page_end=getattr(scene, "page_end", None),
        has_embedding=(
            scene.embedding is not None if hasattr(scene, "embedding") else False
        ),
    )


logger = get_logger(__name__)
router = APIRouter()


async def get_db_ops(request: Request) -> DatabaseOperations:
    """Get database operations from app state."""
    db_ops: DatabaseOperations = request.app.state.db_ops
    return db_ops


@router.get("/{scene_id}", response_model=SceneResponse)
async def get_scene(
    scene_id: str,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> SceneResponse:
    """Get scene details by ID."""
    try:
        scene = await db_ops.get_scene(scene_id)
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")

        return scene_to_response(scene)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get scene", scene_id=scene_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get scene") from e


@router.post("/", response_model=SceneResponse)
async def create_scene(
    script_id: str,
    scene_data: SceneCreateRequest,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> SceneResponse:
    """Create a new scene in a script."""
    try:
        # Check if script exists
        script = await db_ops.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        # Create scene
        scene_id = await db_ops.create_scene(
            script_id=script_id,
            scene_number=scene_data.scene_number,
            heading=scene_data.heading,
            content=scene_data.content,
        )

        # Get created scene
        scene = await db_ops.get_scene(scene_id)
        if not scene:
            raise HTTPException(status_code=500, detail="Failed to create scene")

        return scene_to_response(scene)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create scene", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create scene") from e


@router.patch("/{scene_id}", response_model=SceneResponse)
async def update_scene(
    scene_id: str,
    scene_update: SceneUpdateRequest,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> SceneResponse:
    """Update a scene with enhanced graph propagation."""
    try:
        # Check if scene exists
        scene = await db_ops.get_scene(scene_id)
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")

        # Update the scene with enhanced graph propagation
        success = await db_ops.update_scene_with_graph_propagation(
            scene_id=scene_id,
            scene_number=scene_update.scene_number,
            heading=scene_update.heading,
            content=scene_update.content,
            location=scene_update.location,
            time_of_day=scene_update.time_of_day,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update scene")

        # Get updated scene
        updated_scene = await db_ops.get_scene(scene_id)
        if not updated_scene:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve updated scene"
            )

        return scene_to_response(updated_scene)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update scene", scene_id=scene_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update scene") from e


@router.delete("/{scene_id}")
async def delete_scene(
    scene_id: str,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> dict[str, str]:
    """Delete a scene with reference maintenance."""
    try:
        # Check if scene exists
        scene = await db_ops.get_scene(scene_id)
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")

        # Delete the scene with reference maintenance
        success = await db_ops.delete_scene_with_references(scene_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete scene")

        return {
            "message": f"Scene {scene_id} deleted successfully with reference integrity"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete scene", scene_id=scene_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete scene") from e


# Enhanced Scene Operations (for Phase 5.2 enhanced tests)
async def update_scene_enhanced(
    scene_id: str,
    scene_update: SceneUpdateRequest,
    db_ops: DatabaseOperations,
) -> SceneResponse:
    """Enhanced scene update with graph propagation."""
    try:
        # Check if scene exists
        scene = await db_ops.get_scene(scene_id)
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")

        # Update the scene with enhanced graph propagation
        success = await db_ops.update_scene_with_graph_propagation(
            scene_id=scene_id,
            scene_number=scene_update.scene_number,
            heading=scene_update.heading,
            content=scene_update.content,
            location=scene_update.location,
            time_of_day=scene_update.time_of_day,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update scene")

        # Get updated scene
        updated_scene = await db_ops.get_scene(scene_id)
        if not updated_scene:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve updated scene"
            )

        return scene_to_response(updated_scene)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update scene", scene_id=scene_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update scene") from e


async def delete_scene_enhanced(
    scene_id: str,
    db_ops: DatabaseOperations,
) -> dict[str, str]:
    """Enhanced scene deletion with reference maintenance."""
    try:
        # Check if scene exists
        scene = await db_ops.get_scene(scene_id)
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")

        # Delete the scene with reference maintenance
        success = await db_ops.delete_scene_with_references(scene_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete scene")

        return {
            "message": f"Scene {scene_id} deleted successfully with reference integrity"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete scene", scene_id=scene_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete scene") from e


@router.post("/{scene_id}/inject-after", response_model=SceneResponse)
async def inject_scene_after(
    scene_id: str,
    scene_data: SceneCreateRequest,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> SceneResponse:
    """Inject a new scene after the specified scene."""
    try:
        # Get the reference scene
        ref_scene = await db_ops.get_scene(scene_id)
        if not ref_scene:
            raise HTTPException(status_code=404, detail="Reference scene not found")

        # Calculate position (inject after means position = current + 1)
        new_position = ref_scene.get("scene_number", 1) + 1

        # Use enhanced inject method with full re-indexing
        new_scene_id = await db_ops.inject_scene_at_position(
            script_id=ref_scene.get("script_id", ""),
            scene_data=scene_data,
            position=new_position,
        )

        if not new_scene_id:
            raise HTTPException(status_code=500, detail="Failed to inject scene")

        # Get created scene
        scene = await db_ops.get_scene(new_scene_id)
        if not scene:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve injected scene"
            )

        return scene_to_response(scene)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to inject scene after", scene_id=scene_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to inject scene") from e


# Scene ordering endpoints
@router.post("/script/{script_id}/reorder", response_model=SceneOrderingResponse)
async def reorder_scenes(
    script_id: str,
    ordering_request: SceneOrderingRequest,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> SceneOrderingResponse:
    """Reorder scenes in a script."""
    try:
        # Validate script exists
        script = await db_ops.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        # Reorder scenes
        success = await db_ops.reorder_scenes(
            script_id=script_id,
            scene_ids=ordering_request.scene_ids,
            order_type=ordering_request.order_type,
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to reorder scenes")

        return SceneOrderingResponse(
            script_id=script_id,
            order_type=ordering_request.order_type,
            scene_ids=ordering_request.scene_ids,
            message=(
                f"Successfully reordered scenes using "
                f"{ordering_request.order_type} ordering"
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reorder scenes", script_id=script_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to reorder scenes") from e


@router.post("/script/{script_id}/infer-temporal-order")
async def infer_temporal_order(
    script_id: str,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> dict[str, Any]:
    """Infer temporal (chronological) order of scenes."""
    try:
        # Validate script exists
        script = await db_ops.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        # Infer temporal order
        temporal_order = await db_ops.infer_temporal_order(script_id)

        return {
            "script_id": script_id,
            "temporal_order": temporal_order,
            "scene_count": len(temporal_order),
            "message": "Successfully inferred temporal order",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to infer temporal order", script_id=script_id, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail="Failed to infer temporal order"
        ) from e


@router.post("/script/{script_id}/analyze-dependencies")
async def analyze_dependencies(
    script_id: str,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> dict[str, Any]:
    """Analyze and create logical dependencies between scenes."""
    try:
        # Validate script exists
        script = await db_ops.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        # Analyze dependencies
        dependencies = await db_ops.analyze_scene_dependencies(script_id)

        return {
            "script_id": script_id,
            "dependencies_created": len(dependencies),
            "message": "Successfully analyzed scene dependencies",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to analyze dependencies", script_id=script_id, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail="Failed to analyze dependencies"
        ) from e


@router.get("/{scene_id}/dependencies")
async def get_scene_dependencies(
    scene_id: str,
    direction: str = "both",
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> dict[str, Any]:
    """Get dependencies for a specific scene."""
    try:
        # Validate scene exists
        scene = await db_ops.get_scene(scene_id)
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")

        # Validate direction parameter
        if direction not in ["from", "to", "both"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid direction. Must be 'from', 'to', or 'both'",
            )

        # Get dependencies
        dependencies = await db_ops.get_scene_dependencies(scene_id)

        return {
            "scene_id": scene_id,
            "direction": direction,
            "dependencies": dependencies,
            "dependency_count": len(dependencies),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get scene dependencies", scene_id=scene_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to get dependencies") from e


@router.post("/script/{script_id}/calculate-logical-order")
async def calculate_logical_order(
    script_id: str,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> dict[str, Any]:
    """Calculate logical order based on dependencies."""
    try:
        # Validate script exists
        script = await db_ops.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        # Calculate logical order
        logical_order = await db_ops.calculate_logical_order(script_id)

        return {
            "script_id": script_id,
            "logical_order": logical_order,
            "scene_count": len(logical_order),
            "message": "Successfully calculated logical order",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to calculate logical order", script_id=script_id, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail="Failed to calculate logical order"
        ) from e


@router.get("/script/{script_id}/validate-ordering")
async def validate_ordering(
    script_id: str,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> dict[str, Any]:
    """Validate consistency across different ordering systems."""
    try:
        # Validate script exists
        script = await db_ops.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        # Validate ordering
        return await db_ops.validate_scene_ordering(script_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to validate ordering", script_id=script_id, error=str(e))
        raise HTTPException(
            status_code=500, detail="Failed to validate ordering"
        ) from e


# Enhanced Scene Operations for Phase 5.2
@router.post("/{scene_id}/inject-at-position", response_model=SceneResponse)
async def inject_scene_at_position(
    scene_id: str,
    position: int,
    scene_data: SceneCreateRequest,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> SceneResponse:
    """Inject a new scene at a specific position with full re-indexing."""
    try:
        # Get the reference scene to find script
        ref_scene = await db_ops.get_scene(scene_id)
        if not ref_scene:
            raise HTTPException(status_code=404, detail="Reference scene not found")

        # Inject scene with enhanced operations
        new_scene_id = await db_ops.inject_scene_at_position(
            script_id=ref_scene.get("script_id", ""),
            scene_data=scene_data,
            position=position,
        )

        if not new_scene_id:
            raise HTTPException(status_code=500, detail="Failed to inject scene")

        # Get created scene
        scene = await db_ops.get_scene(new_scene_id)
        if not scene:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve injected scene"
            )

        return scene_to_response(scene)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to inject scene at position",
            scene_id=scene_id,
            position=position,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Failed to inject scene") from e


@router.post("/script/{script_id}/validate-continuity")
async def validate_story_continuity(
    script_id: str,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> dict[str, Any]:
    """Validate story continuity across all scenes in a script."""
    try:
        # Validate script exists
        script = await db_ops.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        # Validate story continuity
        results = await db_ops.validate_story_continuity(script_id)

        return {
            "script_id": script_id,
            "continuity_results": results,
            "message": "Continuity validation completed",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to validate story continuity", script_id=script_id, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail="Failed to validate story continuity"
        ) from e


@router.patch("/{scene_id}/metadata", response_model=SceneResponse)
async def update_scene_metadata(
    scene_id: str,
    heading: str | None = None,
    description: str | None = None,
    time_of_day: str | None = None,
    location: str | None = None,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> SceneResponse:
    """Update scene metadata with optional graph propagation."""
    try:
        # Check if scene exists
        scene = await db_ops.get_scene(scene_id)
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")

        # Update metadata with graph propagation
        success = await db_ops.update_scene_metadata(
            scene_id=scene_id,
            heading=heading,
            description=description,
            time_of_day=time_of_day,
            location=location,
        )

        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to update scene metadata"
            )

        # Get updated scene
        updated_scene = await db_ops.get_scene(scene_id)
        if not updated_scene:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve updated scene"
            )

        return scene_to_response(updated_scene)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update scene metadata", scene_id=scene_id, error=str(e))
        raise HTTPException(
            status_code=500, detail="Failed to update scene metadata"
        ) from e
