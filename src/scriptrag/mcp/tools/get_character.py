"""MCP tool for getting character details."""

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.config import get_logger, get_settings
from scriptrag.mcp.models import (
    CharacterDetail,
    CharacterRelationship,
    DialogueStats,
    SceneAppearance,
)
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import AsyncAPIWrapper, format_error_response

logger = get_logger(__name__)


class GetCharacterInput(BaseModel):
    """Input for getting character details."""

    character_name: str = Field(..., description="Character name")
    script_id: int | None = Field(None, description="Filter by script")
    include_relationships: bool = Field(
        True, description="Include character relationships"
    )
    include_arc_analysis: bool = Field(
        False, description="Include character arc analysis"
    )


class GetCharacterOutput(BaseModel):
    """Output from getting character details."""

    success: bool
    character: CharacterDetail | None = None
    dialogue_stats: DialogueStats | None = None
    scene_appearances: list[SceneAppearance] = []
    relationships: list[CharacterRelationship] | None = None
    arc_analysis: dict | None = None
    message: str | None = None


@mcp.tool()
async def scriptrag_get_character(
    character_name: str,
    script_id: int | None = None,
    include_relationships: bool = True,
    include_arc_analysis: bool = False,
    ctx: Context | None = None,
) -> GetCharacterOutput:
    """Get detailed character information and analysis.

    Args:
        character_name: Character name
        script_id: Filter by script
        include_relationships: Include character relationships
        include_arc_analysis: Include character arc analysis
        ctx: MCP context

    Returns:
        Detailed character information with optional analysis
    """
    try:
        character_name = character_name.strip().upper()

        if ctx:
            filters = []
            if script_id:
                filters.append(f"script_id={script_id}")
            if include_relationships:
                filters.append("relationships=true")
            if include_arc_analysis:
                filters.append("arc_analysis=true")
            filter_str = f" with {', '.join(filters)}" if filters else ""
            await ctx.info(f"Getting character '{character_name}'{filter_str}")

        # Use Database Operations API
        settings = get_settings()
        db_ops = DatabaseOperations(settings)
        wrapper = AsyncAPIWrapper()

        # Get character data
        character_data = await wrapper.run_sync(
            db_ops.get_character_by_name, character_name, script_id
        )

        if not character_data:
            return GetCharacterOutput(
                success=False,
                message=f"Character '{character_name}' not found",
            )

        # Calculate dialogue statistics
        dialogue_lines = getattr(character_data, "dialogue_lines", [])
        word_counts = []
        vocabulary = set()

        for line in dialogue_lines:
            words = line.split()
            word_counts.append(len(words))
            vocabulary.update(word.lower() for word in words)

        dialogue_stats = None
        if word_counts:
            dialogue_stats = DialogueStats(
                total_lines=len(dialogue_lines),
                total_words=sum(word_counts),
                average_words_per_line=sum(word_counts) / len(word_counts)
                if word_counts
                else 0,
                longest_line_words=max(word_counts) if word_counts else 0,
                shortest_line_words=min(word_counts) if word_counts else 0,
                vocabulary_size=len(vocabulary),
            )

        # Get scene appearances
        scene_appearances = []
        scenes = await wrapper.run_sync(
            db_ops.get_scenes_with_character, character_name, script_id
        )

        for scene in scenes:
            # Count dialogue and action mentions in this scene
            dialogue_count = 0
            action_mentions = 0

            if hasattr(scene, "content"):
                lines = scene.content.split("\n")
                current_character = None

                for line in lines:
                    line_stripped = line.strip()
                    # Check if it's this character's name
                    if line_stripped.upper() == character_name:
                        current_character = character_name
                    elif (
                        current_character == character_name
                        and line_stripped
                        and not line_stripped.startswith("(")
                    ):
                        dialogue_count += 1
                    elif character_name.lower() in line_stripped.lower():
                        action_mentions += 1

            scene_appearances.append(
                SceneAppearance(
                    scene_id=scene.id,
                    scene_number=scene.scene_number,
                    scene_heading=scene.heading,
                    dialogue_count=dialogue_count,
                    action_mentions=action_mentions,
                )
            )

        # Get first and last appearance scenes
        first_scene = None
        last_scene = None
        if scene_appearances:
            first_scene = min(scene_appearances, key=lambda x: x.scene_number)
            last_scene = max(scene_appearances, key=lambda x: x.scene_number)

        # Create character detail
        character_detail = CharacterDetail(
            name=character_name,
            dialogue_count=len(dialogue_lines),
            scene_count=len(scene_appearances),
            total_words=dialogue_stats.total_words if dialogue_stats else 0,
            average_words_per_line=dialogue_stats.average_words_per_line
            if dialogue_stats
            else 0,
            first_appearance=first_scene,
            last_appearance=last_scene,
            metadata=getattr(character_data, "metadata", None),
        )

        # Get relationships if requested
        relationships = None
        if include_relationships:
            relationship_data = await wrapper.run_sync(
                db_ops.get_character_relationships, character_name, script_id
            )
            relationships = []
            for rel in relationship_data:
                relationships.append(
                    CharacterRelationship(
                        character1=character_name,
                        character2=rel.get("character2", ""),
                        shared_scenes=rel.get("shared_scenes", 0),
                        interaction_count=rel.get("interactions", 0),
                        relationship_type=rel.get("type"),
                    )
                )

        # Get arc analysis if requested
        arc_analysis = None
        if include_arc_analysis:
            # This would require running an analysis agent
            arc_analysis = {
                "message": "Character arc analysis requires running analysis agents",
                "available": False,
            }

        if ctx:
            await ctx.info(
                f"Retrieved character '{character_name}' with {len(scene_appearances)} scene appearances"
            )

        return GetCharacterOutput(
            success=True,
            character=character_detail,
            dialogue_stats=dialogue_stats,
            scene_appearances=scene_appearances,
            relationships=relationships,
            arc_analysis=arc_analysis,
            message=f"Retrieved character '{character_name}'",
        )

    except Exception as e:
        logger.error("Failed to get character", error=str(e))
        error_response = format_error_response(e, "scriptrag_get_character")
        return GetCharacterOutput(success=False, message=error_response["message"])
