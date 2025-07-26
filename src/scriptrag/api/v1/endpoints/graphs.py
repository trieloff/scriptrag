"""Graph visualization endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request

from scriptrag.api.db_operations import DatabaseOperations
from scriptrag.api.v1.schemas import (
    CharacterGraphRequest,
    GraphEdge,
    GraphNode,
    GraphNodeType,
    GraphResponse,
    ResponseStatus,
    TimelineGraphRequest,
)
from scriptrag.config import get_logger

logger = get_logger(__name__)
router = APIRouter()


async def get_db_ops(request: Request) -> DatabaseOperations:
    """Get database operations from app state."""
    db_ops: DatabaseOperations = request.app.state.db_ops
    return db_ops


@router.post("/characters", response_model=GraphResponse)
async def get_character_graph(
    request: CharacterGraphRequest,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> GraphResponse:
    """Get character relationship graph."""
    try:
        graph_data = await db_ops.get_character_graph(
            character_name=request.character_name,
            script_id=request.script_id,
            depth=request.depth,
            min_interaction_count=request.min_interaction_count,
        )

        # Convert to API models
        nodes = [
            GraphNode(
                id=node["id"],
                type=(
                    GraphNodeType.CHARACTER
                    if node["type"] == "character"
                    else GraphNodeType.SCENE
                ),
                label=node["label"],
                properties=node.get("properties", {}),
            )
            for node in graph_data["nodes"]
        ]

        edges = [
            GraphEdge(
                source=edge["source"],
                target=edge["target"],
                type=edge["type"],
                weight=edge.get("weight", 1.0),
                properties=edge.get("properties", {}),
            )
            for edge in graph_data["edges"]
        ]

        return GraphResponse(
            status=ResponseStatus.SUCCESS,
            nodes=nodes,
            edges=edges,
            metadata={
                "character": request.character_name,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "depth": request.depth,
            },
        )

    except Exception as e:
        logger.error(
            "Failed to get character graph",
            character=request.character_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail="Failed to get character graph"
        ) from e


@router.post("/timeline", response_model=GraphResponse)
async def get_timeline_graph(
    request: TimelineGraphRequest,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> GraphResponse:
    """Get timeline visualization graph."""
    try:
        # Check if script exists
        script = await db_ops.get_script(request.script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        graph_data = await db_ops.get_timeline_graph(
            script_id=request.script_id,
            group_by=request.group_by,
            include_characters=request.include_characters,
        )

        # Convert to API models
        nodes = [
            GraphNode(
                id=node["id"],
                type=GraphNodeType[node["type"].upper()],
                label=node["label"],
                properties=node.get("properties", {}),
            )
            for node in graph_data["nodes"]
        ]

        edges = [
            GraphEdge(
                source=edge["source"],
                target=edge["target"],
                type=edge["type"],
                weight=edge.get("weight", 1.0),
                properties=edge.get("properties", {}),
            )
            for edge in graph_data["edges"]
        ]

        return GraphResponse(
            status=ResponseStatus.SUCCESS,
            nodes=nodes,
            edges=edges,
            metadata={
                "script_id": request.script_id,
                "script_title": script.title,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "group_by": request.group_by,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get timeline graph", script_id=request.script_id, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail="Failed to get timeline graph"
        ) from e


@router.get("/scripts/{script_id}/locations")
async def get_location_graph(
    script_id: int,
    db_ops: DatabaseOperations = Depends(get_db_ops),
) -> GraphResponse:
    """Get location-based scene graph for a script."""
    try:
        # Check if script exists
        script = await db_ops.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        graph_data = await db_ops.get_location_graph(script_id)

        # Convert to API models
        nodes = [
            GraphNode(
                id=node["id"],
                type=(
                    GraphNodeType.LOCATION
                    if node["type"] == "location"
                    else GraphNodeType.SCENE
                ),
                label=node["label"],
                properties=node.get("properties", {}),
            )
            for node in graph_data["nodes"]
        ]

        edges = [
            GraphEdge(
                source=edge["source"],
                target=edge["target"],
                type=edge["type"],
                weight=edge.get("weight", 1.0),
                properties=edge.get("properties", {}),
            )
            for edge in graph_data["edges"]
        ]

        return GraphResponse(
            status=ResponseStatus.SUCCESS,
            nodes=nodes,
            edges=edges,
            metadata={
                "script_id": script_id,
                "script_title": script.title,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "total_locations": sum(
                    1 for n in nodes if n.type == GraphNodeType.LOCATION
                ),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get location graph", script_id=script_id, error=str(e))
        raise HTTPException(
            status_code=500, detail="Failed to get location graph"
        ) from e
