"""Scene management tools for MCP server."""

from __future__ import annotations

from typing import Any

from mcp.server import FastMCP

from scriptrag.api.scene_management import SceneManagementAPI
from scriptrag.api.scene_models import SceneIdentifier
from scriptrag.config import get_logger

logger = get_logger(__name__)


def register_scene_tools(mcp: FastMCP) -> None:
    """Register scene management tools with the MCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool()
    async def scriptrag_scene_read(
        project: str,
        scene_number: int,
        season: int | None = None,
        episode: int | None = None,
        reader_id: str = "mcp_agent",
    ) -> dict[str, Any]:
        """Read a scene and get session token for updates.

        This tool reads a scene from the database and returns its content
        along with a session token that's valid for 10 minutes. The session
        token must be used for any subsequent update operations on this scene.

        Args:
            project: Project/script name (e.g., "breaking_bad", "inception")
            scene_number: Scene number to read
            season: Season number (for TV shows, optional)
            episode: Episode number (for TV shows, optional)
            reader_id: Identifier for the reader (default: "mcp_agent")

        Returns:
            Dictionary containing:
            - success: Whether the operation succeeded
            - scene: Scene data including number, heading, and content
            - session_token: Token for updates (valid for 10 minutes)
            - expires_at: ISO timestamp when the session expires
            - error: Error message if operation failed

        Examples:
            Read a TV show scene:
            {"project": "breaking_bad", "season": 1, "episode": 1, "scene_number": 3}

            Read a feature film scene:
            {"project": "inception", "scene_number": 42}
        """
        try:
            scene_id = SceneIdentifier(
                project=project,
                scene_number=scene_number,
                season=season,
                episode=episode,
            )

            api = SceneManagementAPI()
            result = await api.read_scene(scene_id, reader_id)

            if result.success and result.scene:
                return {
                    "success": True,
                    "scene": {
                        "number": result.scene.number,
                        "heading": result.scene.heading,
                        "content": result.scene.content,
                        "location": result.scene.location,
                        "time_of_day": result.scene.time_of_day,
                    },
                    "last_read": result.last_read.isoformat()
                    if result.last_read
                    else None,
                    "error": None,
                }
            return {
                "success": False,
                "scene": None,
                "last_read": None,
                "error": result.error or "Unknown error",
            }

        except Exception as e:
            logger.error(f"Scene read failed: {e}")
            return {
                "success": False,
                "scene": None,
                "last_read": None,
                "error": str(e),
            }

    @mcp.tool()
    async def scriptrag_scene_add(
        project: str,
        content: str,
        after_scene: int | None = None,
        before_scene: int | None = None,
        season: int | None = None,
        episode: int | None = None,
    ) -> dict[str, Any]:
        r"""Add a new scene with automatic renumbering.

        This tool adds a new scene either before or after an existing scene.
        The content must be valid Fountain format starting with a scene heading
        (INT., EXT., I/E., or INT/EXT.). Subsequent scenes are automatically
        renumbered to maintain sequence.

        Args:
            project: Project/script name
            content: Scene content in Fountain format (must start with scene heading)
            after_scene: Add the new scene after this scene number
            before_scene: Add the new scene before this scene number
            season: Season number (for TV shows, optional)
            episode: Episode number (for TV shows, optional)

        Returns:
            Dictionary containing:
            - success: Whether the operation succeeded
            - created_scene: The newly created scene data
            - renumbered_scenes: List of scene numbers that were renumbered
            - error: Error message if operation failed

        Note:
            You must specify either after_scene OR before_scene, not both.

        Examples:
            Add scene after scene 4 in a TV show:
            {
                "project": "breaking_bad",
                "season": 2,
                "episode": 5,
                "after_scene": 4,
                "content": "INT. COFFEE SHOP - DAY\\n\\nWalter enters, looking tired."
            }

            Add scene before scene 10 in a feature:
            {
                "project": "inception",
                "before_scene": 10,
                "content": "EXT. CITY STREET - NIGHT\\n\\nCobb walks alone."
            }
        """
        try:
            # Validate position arguments
            if after_scene is None and before_scene is None:
                return {
                    "success": False,
                    "created_scene": None,
                    "renumbered_scenes": [],
                    "error": "Must specify either after_scene or before_scene",
                }

            if after_scene is not None and before_scene is not None:
                return {
                    "success": False,
                    "created_scene": None,
                    "renumbered_scenes": [],
                    "error": "Cannot specify both after_scene and before_scene",
                }

            # Determine reference scene and position
            if after_scene is not None:
                reference_scene = after_scene
                position = "after"
            else:
                # At this point, before_scene must be not None due to validation above
                if before_scene is None:
                    raise ValueError(
                        "Internal error: before_scene is None after validation"
                    )
                reference_scene = before_scene
                position = "before"

            scene_id = SceneIdentifier(
                project=project,
                scene_number=reference_scene,
                season=season,
                episode=episode,
            )

            api = SceneManagementAPI()
            result = await api.add_scene(scene_id, content, position)

            if result.success and result.created_scene:
                return {
                    "success": True,
                    "created_scene": {
                        "number": result.created_scene.number,
                        "heading": result.created_scene.heading,
                        "content": result.created_scene.content,
                    },
                    "renumbered_scenes": result.renumbered_scenes,
                    "error": None,
                }
            return {
                "success": False,
                "created_scene": None,
                "renumbered_scenes": [],
                "error": result.error or "Unknown error",
            }

        except Exception as e:
            logger.error(f"Scene add failed: {e}")
            return {
                "success": False,
                "created_scene": None,
                "renumbered_scenes": [],
                "error": str(e),
            }

    @mcp.tool()
    async def scriptrag_scene_update(
        project: str,
        scene_number: int,
        content: str,
        check_conflicts: bool = False,
        last_read: str | None = None,
        season: int | None = None,
        episode: int | None = None,
        reader_id: str = "mcp_agent",
    ) -> dict[str, Any]:
        r"""Update scene content with optional conflict checking.

        This tool updates an existing scene's content. By default, updates happen
        immediately without conflict checking. Use check_conflicts=True with a
        last_read timestamp for safe updates that prevent concurrent modifications.

        Args:
            project: Project/script name
            scene_number: Scene number to update
            content: New scene content in Fountain format
            check_conflicts: If True, check for concurrent modifications
            last_read: ISO timestamp of when scene was last read (required if
                check_conflicts=True)
            season: Season number (for TV shows, optional)
            episode: Episode number (for TV shows, optional)
            reader_id: Identifier for the updater (default: "mcp_agent")

        Returns:
            Dictionary containing:
            - success: Whether the operation succeeded
            - updated_scene: The updated scene data
            - validation_errors: List of validation errors if any
            - error: Error message if operation failed

        Validation Errors:
            - MISSING_TIMESTAMP: check_conflicts=True but no last_read provided
            - CONCURRENT_MODIFICATION: Scene modified by another process
            - SCENE_NOT_FOUND: Scene no longer exists
            - Fountain format errors: Specific formatting issues

        Examples:
            Update a TV show scene:
            {
                "project": "breaking_bad",
                "season": 2,
                "episode": 5,
                "scene_number": 5,
                "check_conflicts": true,
                "last_read": "2024-01-15T10:30:00",
                "content": "INT. COFFEE SHOP - DAY\\n\\nUpdated scene content."
            }
        """
        try:
            scene_id = SceneIdentifier(
                project=project,
                scene_number=scene_number,
                season=season,
                episode=episode,
            )

            # Parse last_read timestamp if provided
            from datetime import datetime

            last_read_dt = None
            if check_conflicts and last_read:
                try:
                    last_read_dt = datetime.fromisoformat(last_read)
                except ValueError:
                    return {
                        "success": False,
                        "updated_scene": None,
                        "validation_errors": ["INVALID_TIMESTAMP"],
                        "error": f"Invalid timestamp format: {last_read}",
                    }

            api = SceneManagementAPI()
            result = await api.update_scene(
                scene_id,
                content,
                check_conflicts=check_conflicts,
                last_read=last_read_dt,
                reader_id=reader_id,
            )

            if result.success and result.updated_scene:
                return {
                    "success": True,
                    "updated_scene": {
                        "number": result.updated_scene.number,
                        "heading": result.updated_scene.heading,
                        "content": result.updated_scene.content,
                    },
                    "validation_errors": [],
                    "error": None,
                }
            return {
                "success": False,
                "updated_scene": None,
                "validation_errors": result.validation_errors,
                "error": result.error or "Unknown error",
            }

        except Exception as e:
            logger.error(f"Scene update failed: {e}")
            return {
                "success": False,
                "updated_scene": None,
                "validation_errors": ["EXCEPTION"],
                "error": str(e),
            }

    @mcp.tool()
    async def scriptrag_scene_delete(
        project: str,
        scene_number: int,
        season: int | None = None,
        episode: int | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Delete a scene with automatic renumbering.

        This tool deletes a scene and automatically renumbers subsequent scenes
        to maintain sequence. Requires confirm=True to prevent accidental deletions.

        Args:
            project: Project/script name
            scene_number: Scene number to delete
            season: Season number (for TV shows, optional)
            episode: Episode number (for TV shows, optional)
            confirm: Must be True to confirm deletion

        Returns:
            Dictionary containing:
            - success: Whether the operation succeeded
            - renumbered_scenes: List of scene numbers that were renumbered
            - error: Error message if operation failed

        Examples:
            Delete a TV show scene:
            {
                "project": "breaking_bad",
                "season": 1,
                "episode": 1,
                "scene_number": 5,
                "confirm": true
            }

            Delete a feature film scene:
            {
                "project": "inception",
                "scene_number": 42,
                "confirm": true
            }
        """
        try:
            if not confirm:
                return {
                    "success": False,
                    "renumbered_scenes": [],
                    "error": "Deletion requires confirm=True to prevent "
                    "accidental deletions",
                }

            scene_id = SceneIdentifier(
                project=project,
                scene_number=scene_number,
                season=season,
                episode=episode,
            )

            api = SceneManagementAPI()
            result = await api.delete_scene(scene_id, confirm=True)

            if result.success:
                return {
                    "success": True,
                    "renumbered_scenes": result.renumbered_scenes,
                    "error": None,
                }
            return {
                "success": False,
                "renumbered_scenes": [],
                "error": result.error or "Unknown error",
            }

        except Exception as e:
            logger.error(f"Scene delete failed: {e}")
            return {
                "success": False,
                "renumbered_scenes": [],
                "error": str(e),
            }

    @mcp.tool()
    async def scriptrag_bible_read(
        project: str, bible_name: str | None = None
    ) -> dict[str, Any]:
        """Read script bible content.

        This tool reads script bible (markdown) files associated with a project.
        If no specific bible file is specified, it returns a list of available
        bible files. Bible files typically contain world-building information,
        character descriptions, backstory, and other reference material.

        Args:
            project: Project/script name
            bible_name: Optional specific bible file name (can be just the filename
                       or relative path from project root)

        Returns:
            Dictionary containing either:
            - When bible_name is None: List of available bible files with their
              names, paths, and sizes
            - When bible_name is specified: The content of that bible file

        Examples:
            List available bible files:
            {"project": "inception"}

            Read a specific bible file:
            {"project": "inception", "bible_name": "world_bible.md"}
            {"project": "breaking_bad", "bible_name": "characters.md"}
        """
        try:
            api = SceneManagementAPI()
            result = await api.read_bible(project, bible_name)

            if result.success:
                if result.content:
                    # Returning specific bible content
                    return {
                        "success": True,
                        "content": result.content,
                        "bible_name": bible_name,
                        "error": None,
                    }
                # Returning list of available bible files
                return {
                    "success": True,
                    "bible_files": result.bible_files,
                    "error": None,
                }
            return {"success": False, "error": result.error or "Unknown error"}

        except Exception as e:
            logger.error(f"Bible read failed: {e}")
            return {"success": False, "error": str(e)}
