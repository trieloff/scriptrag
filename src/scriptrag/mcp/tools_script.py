"""Script-related MCP tools."""

import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from scriptrag.config import get_logger

from .exceptions import InvalidArgumentError

if TYPE_CHECKING:
    from scriptrag.mcp.server import ScriptRAGMCPServer


class ScriptTools:
    """Tools for script management."""

    def __init__(self, server: "ScriptRAGMCPServer"):
        """Initialize script tools.

        Args:
            server: Parent MCP server instance
        """
        self.server = server
        self.logger = get_logger(__name__)
        self.scriptrag = server.scriptrag
        self.config = server.config

    async def parse_fountain(self, args: dict[str, Any]) -> dict[str, Any]:
        """Parse a screenplay file.

        Args:
            args: Tool arguments with path and optional title

        Returns:
            Parsed script information
        """
        if "path" not in args:
            raise InvalidArgumentError("path is required")

        path = Path(args["path"])
        if not path.exists():
            raise InvalidArgumentError(f"File not found: {path}")

        script = self.scriptrag.parse_fountain(str(path))

        # Override title if provided
        if args.get("title"):
            script.title = args["title"]

        # Cache the script
        script_id = f"script_{uuid.uuid4().hex[:8]}"
        self.server._add_to_cache(script_id, script)

        self.logger.info("Script parsed", path=path, script_id=script_id)

        return {
            "script_id": script_id,
            "title": script.title,
            "author": script.author,
            "source_file": script.source_file,
            "scene_count": len(script.scenes),
            "character_count": len(script.characters),
            "location_count": 0,  # TODO: Load actual scenes from database
            "time_of_day_distribution": {},  # TODO: Calculate from scenes
        }

    async def list_scripts(self, _args: dict[str, Any]) -> dict[str, Any]:
        """List all cached scripts.

        Returns:
            List of script summaries
        """
        scripts = []
        for script_id, script in self.server._scripts_cache.items():
            scripts.append(
                {
                    "script_id": script_id,
                    "title": script.title,
                    "author": script.author,
                    "scene_count": len(script.scenes),
                }
            )
        return {"scripts": scripts, "count": len(scripts)}

    async def export_data(self, args: dict[str, Any]) -> dict[str, Any]:
        """Export data from a script."""
        script_id = args["script_id"]
        format_type = args.get("format", "json")

        script = self.server._validate_script_id(script_id)

        if format_type == "json":
            # Export basic metadata
            return {
                "title": script.title,
                "author": script.author,
                "scenes": [],  # TODO: Load actual scenes from database
                "characters": list(script.characters),
            }
        raise InvalidArgumentError(f"Unsupported export format: {format_type}")
