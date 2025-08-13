"""Scene management tools for MCP server."""

from typing import Any

from mcp.server import FastMCP

from scriptrag.api.scene_management import SceneIdentifier, SceneManagementAPI
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
                    "session_token": result.session_token,
                    "expires_at": result.expires_at.isoformat()
                    if result.expires_at
                    else None,
                    "error": None,
                }
            return {
                "success": False,
                "scene": None,
                "session_token": None,
                "expires_at": None,
                "error": result.error or "Unknown error",
            }

        except Exception as e:
            logger.error(f"Scene read failed: {e}")
            return {
                "success": False,
                "scene": None,
                "session_token": None,
                "expires_at": None,
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
                reference_scene = before_scene  # type: ignore[assignment]
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
        session_token: str,
        season: int | None = None,
        episode: int | None = None,
        reader_id: str = "mcp_agent",
    ) -> dict[str, Any]:
        r"""Update scene content with validation.

        This tool updates an existing scene's content. It requires a valid
        session token from a recent scriptrag_scene_read call (within 10 minutes).
        The content must be valid Fountain format. If the scene has been modified
        by another process since it was read, the update will fail to prevent
        conflicts.

        Args:
            project: Project/script name
            scene_number: Scene number to update
            content: New scene content in Fountain format
            session_token: Session token from scriptrag_scene_read
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
            - SESSION_INVALID: Session token expired or invalid
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
                "session_token": "abc-123-def",
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

            api = SceneManagementAPI()
            result = await api.update_scene(scene_id, content, session_token, reader_id)

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
