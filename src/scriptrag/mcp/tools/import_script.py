"""MCP tool for importing Fountain scripts."""

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from scriptrag.api.index import IndexCommand
from scriptrag.config import get_logger
from scriptrag.mcp.server import mcp
from scriptrag.mcp.utils import (
    AsyncAPIWrapper,
    format_error_response,
    validate_file_path,
)

logger = get_logger(__name__)


class ImportScriptInput(BaseModel):
    """Input for importing a script."""

    file_path: str = Field(..., description="Path to the Fountain file to import")
    force: bool = Field(False, description="Force re-import if script already exists")


class ImportScriptOutput(BaseModel):
    """Output from importing a script."""

    success: bool
    script_id: int | None = None
    title: str | None = None
    scenes_imported: int = 0
    characters_indexed: int = 0
    message: str


@mcp.tool()
async def scriptrag_import_script(
    file_path: str, force: bool = False, ctx: Context | None = None
) -> ImportScriptOutput:
    """Import a Fountain screenplay file into ScriptRAG.

    Args:
        file_path: Path to the Fountain file to import
        force: Force re-import if script already exists
        ctx: MCP context

    Returns:
        Import result with script details
    """
    try:
        # Log the operation
        if ctx:
            await ctx.info(f"Importing script from {file_path}")

        # Validate file path
        script_path = validate_file_path(file_path)

        # Check if it's a Fountain file
        if script_path.suffix.lower() not in [".fountain", ".spmd", ".txt"]:
            return ImportScriptOutput(
                success=False,
                message=f"File must be a Fountain format file (.fountain, .spmd, or .txt), got {script_path.suffix}",
            )

        # Use the Index API to import the script
        index_api = IndexCommand.from_config()
        wrapper = AsyncAPIWrapper()

        # Run the synchronous index operation asynchronously
        result = await wrapper.run_sync(index_api.index, path=script_path, force=force)

        if result.errors:
            error_msg = "; ".join(result.errors)
            if ctx:
                await ctx.error(f"Import had errors: {error_msg}")
            return ImportScriptOutput(
                success=False, message=f"Import failed: {error_msg}"
            )

        # Get the first script result (we're importing one file)
        if result.scripts:
            script_result = result.scripts[0]
            if script_result.error:
                return ImportScriptOutput(
                    success=False, message=f"Import failed: {script_result.error}"
                )

            if ctx:
                await ctx.info(
                    f"Successfully imported script with {script_result.scenes_indexed} scenes"
                )

            return ImportScriptOutput(
                success=True,
                script_id=script_result.script_id,
                title=str(script_path.stem),
                scenes_imported=script_result.scenes_indexed,
                characters_indexed=script_result.characters_indexed,
                message=f"Successfully imported {script_result.scenes_indexed} scenes and {script_result.characters_indexed} characters",
            )
        return ImportScriptOutput(
            success=False,
            message="No script was imported - file may be empty or invalid",
        )

    except ValueError as e:
        return ImportScriptOutput(success=False, message=str(e))
    except Exception as e:
        logger.error("Failed to import script", error=str(e))
        error_response = format_error_response(e, "scriptrag_import_script")
        return ImportScriptOutput(success=False, message=error_response["message"])
