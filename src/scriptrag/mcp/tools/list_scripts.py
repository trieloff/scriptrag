"""MCP tool for listing scripts."""

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from scriptrag.api.list import ScriptLister
from scriptrag.config import get_logger
from scriptrag.mcp.models import ScriptMetadata
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import AsyncAPIWrapper, format_error_response

logger = get_logger(__name__)


class ListScriptsInput(BaseModel):
    """Input for listing scripts."""

    limit: int = Field(
        10, ge=1, le=100, description="Maximum number of scripts to return"
    )
    offset: int = Field(0, ge=0, description="Offset for pagination")


class ListScriptsOutput(BaseModel):
    """Output from listing scripts."""

    scripts: list[ScriptMetadata]
    total_count: int
    has_more: bool
    success: bool = True
    message: str | None = None


@mcp.tool()
async def scriptrag_list_scripts(
    limit: int = 10, offset: int = 0, ctx: Context | None = None
) -> ListScriptsOutput:
    """List all imported scripts with metadata.

    Args:
        limit: Maximum number of scripts to return (1-100)
        offset: Offset for pagination
        ctx: MCP context

    Returns:
        List of scripts with metadata
    """
    try:
        # Validate inputs
        limit = max(1, min(100, limit))
        offset = max(0, offset)

        if ctx:
            await ctx.info(f"Listing scripts (limit={limit}, offset={offset})")

        # Use the List API to get scripts
        lister = ScriptLister()
        wrapper = AsyncAPIWrapper()

        # Get the list of scripts
        scripts_data = await wrapper.run_sync(lister.list_scripts)

        # Apply pagination
        total_count = len(scripts_data)
        paginated_scripts = scripts_data[offset : offset + limit]

        # Convert to MCP models
        script_models = []
        for script_info in paginated_scripts:
            # Extract metadata from FountainMetadata
            script_models.append(
                ScriptMetadata(
                    script_id=getattr(script_info, "script_id", 0) or 0,
                    title=script_info.title or "Untitled",
                    file_path=str(script_info.path),
                    scene_count=getattr(script_info, "scene_count", 0) or 0,
                    character_count=getattr(script_info, "character_count", 0) or 0,
                    created_at=getattr(script_info, "created_at", "") or "",
                    updated_at=getattr(script_info, "updated_at", None),
                )
            )

        has_more = (offset + limit) < total_count

        if ctx:
            await ctx.info(f"Found {len(script_models)} scripts (total: {total_count})")

        return ListScriptsOutput(
            scripts=script_models,
            total_count=total_count,
            has_more=has_more,
            success=True,
            message=f"Found {total_count} scripts",
        )

    except Exception as e:
        logger.error("Failed to list scripts", error=str(e))
        error_response = format_error_response(e, "scriptrag_list_scripts")
        return ListScriptsOutput(
            scripts=[],
            total_count=0,
            has_more=False,
            success=False,
            message=error_response["message"],
        )
