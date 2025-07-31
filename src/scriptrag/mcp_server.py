"""MCP (Model Context Protocol) server for ScriptRAG.

This module provides an MCP server that exposes ScriptRAG functionality
to AI assistants and other MCP-compatible clients.
"""

import asyncio
import json
import sys
import uuid
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl

from . import ScriptRAG
from .config import (
    ScriptRAGSettings,
    get_logger,
    get_settings,
    load_settings,
    setup_logging_for_environment,
)
from .models import Script


class ScriptRAGMCPServer:
    """MCP server for ScriptRAG functionality."""

    def __init__(self, config: ScriptRAGSettings):
        """Initialize the MCP server.

        Args:
            config: ScriptRAG configuration settings
        """
        self.config = config
        self.logger = get_logger(__name__)
        self.scriptrag = ScriptRAG(config=config)
        self.server: Server = Server("scriptrag")
        self._scripts_cache: OrderedDict[str, Script] = OrderedDict()
        self._max_cache_size = config.mcp.max_resources or 100

        # Register handlers
        self._register_handlers()

        self.logger.info(
            "ScriptRAG MCP server initialized",
            host=config.mcp.host,
            port=config.mcp.port,
            max_resources=config.mcp.max_resources,
        )

    def _register_handlers(self) -> None:
        """Register all MCP handlers."""
        # Tool handlers
        self.server.request_handlers[types.CallToolRequest] = self._handle_tool_call

        # Resource handlers
        self.server.request_handlers[types.ListResourcesRequest] = (
            self._handle_list_resources
        )
        self.server.request_handlers[types.ReadResourceRequest] = (
            self._handle_read_resource
        )

        # Prompt handlers
        self.server.request_handlers[types.ListPromptsRequest] = (
            self._handle_list_prompts
        )
        self.server.request_handlers[types.GetPromptRequest] = self._handle_get_prompt

        # Tool listing
        self.server.request_handlers[types.ListToolsRequest] = self._handle_list_tools

    async def start(self) -> None:
        """Start the MCP server."""
        self.logger.info(
            "Starting MCP server",
            host=self.config.mcp.host,
            port=self.config.mcp.port,
        )

        # Run the server using stdio transport
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            init_options = InitializationOptions(
                server_name="scriptrag",
                server_version=self._get_version(),
                capabilities=self.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            )
            await self.server.run(
                read_stream,
                write_stream,
                init_options,
            )

    async def stop(self) -> None:
        """Stop the MCP server."""
        self.logger.info("Stopping MCP server")
        # Clean up any resources
        self._scripts_cache.clear()

    def _get_version(self) -> str:
        """Get server version."""
        from . import __version__

        return __version__

    def _add_to_cache(self, script_id: str, script: Script) -> None:
        """Add a script to cache with size limit management.

        Args:
            script_id: Unique identifier for the script
            script: Script object to cache
        """
        if len(self._scripts_cache) >= self._max_cache_size:
            # Remove oldest entry
            self._scripts_cache.popitem(last=False)
        self._scripts_cache[script_id] = script

    def _validate_script_id(self, script_id: str) -> Script:
        """Validate and retrieve a script from cache.

        Args:
            script_id: Script identifier to validate

        Returns:
            Script object if found

        Raises:
            ValueError: If script_id not found in cache
        """
        if script_id not in self._scripts_cache:
            raise ValueError(f"Script not found: {script_id}")
        return self._scripts_cache[script_id]

    def get_available_tools(self) -> list[dict[str, Any]]:
        """Get list of available MCP tools.

        Returns:
            List of tool definitions
        """
        tools = [
            {
                "name": "parse_script",
                "description": "Parse a screenplay file in Fountain format",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the Fountain file",
                        },
                        "title": {
                            "type": "string",
                            "description": "Optional title for the script",
                        },
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "search_scenes",
                "description": "Search for scenes based on various criteria",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID to search within",
                        },
                        "query": {"type": "string", "description": "Search query text"},
                        "location": {
                            "type": "string",
                            "description": "Filter by location",
                        },
                        "characters": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by character names",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results",
                            "default": 10,
                        },
                    },
                    "required": ["script_id"],
                },
            },
            {
                "name": "get_character_info",
                "description": "Get information about a character",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                        "character_name": {
                            "type": "string",
                            "description": "Character name",
                        },
                    },
                    "required": ["script_id", "character_name"],
                },
            },
            {
                "name": "analyze_timeline",
                "description": "Analyze the timeline and temporal flow of the script",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID to analyze",
                        },
                        "include_flashbacks": {
                            "type": "boolean",
                            "description": "Include flashback analysis",
                            "default": True,
                        },
                    },
                    "required": ["script_id"],
                },
            },
            {
                "name": "list_scripts",
                "description": "List all parsed scripts in the database",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "update_scene",
                "description": "Update a scene with new information",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                        "scene_id": {
                            "type": "integer",
                            "description": "Scene ID to update",
                        },
                        "heading": {
                            "type": "string",
                            "description": "New scene heading",
                        },
                        "action": {"type": "string", "description": "New action text"},
                        "dialogue": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "character": {"type": "string"},
                                    "text": {"type": "string"},
                                    "parenthetical": {"type": "string"},
                                },
                            },
                            "description": "New dialogue entries",
                        },
                    },
                    "required": ["script_id", "scene_id"],
                },
            },
            {
                "name": "delete_scene",
                "description": "Delete a scene from the script",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                        "scene_id": {
                            "type": "integer",
                            "description": "Scene ID to delete",
                        },
                    },
                    "required": ["script_id", "scene_id"],
                },
            },
            {
                "name": "inject_scene",
                "description": "Insert a new scene at a specific position",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                        "position": {
                            "type": "integer",
                            "description": "Position to insert the scene",
                        },
                        "heading": {"type": "string", "description": "Scene heading"},
                        "action": {"type": "string", "description": "Action text"},
                        "dialogue": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "character": {"type": "string"},
                                    "text": {"type": "string"},
                                    "parenthetical": {"type": "string"},
                                },
                            },
                            "description": "Dialogue entries",
                        },
                    },
                    "required": ["script_id", "position", "heading"],
                },
            },
            {
                "name": "get_scene_details",
                "description": "Get detailed information about a specific scene",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                        "scene_id": {"type": "integer", "description": "Scene ID"},
                    },
                    "required": ["script_id", "scene_id"],
                },
            },
            {
                "name": "get_character_relationships",
                "description": "Analyze relationships between characters",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                        "character_name": {
                            "type": "string",
                            "description": "Optional: focus on specific character",
                        },
                    },
                    "required": ["script_id"],
                },
            },
            {
                "name": "export_data",
                "description": "Export script data in various formats",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                        "format": {
                            "type": "string",
                            "enum": ["json", "csv", "graphml", "fountain"],
                            "description": "Export format",
                        },
                        "include_metadata": {
                            "type": "boolean",
                            "description": "Include metadata in export",
                            "default": True,
                        },
                    },
                    "required": ["script_id", "format"],
                },
            },
            # Script Bible and Continuity Management Tools
            {
                "name": "create_series_bible",
                "description": "Create a new script bible for continuity management",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                        "title": {"type": "string", "description": "Bible title"},
                        "description": {
                            "type": "string",
                            "description": "Bible description",
                        },
                        "bible_type": {
                            "type": "string",
                            "enum": ["series", "movie", "anthology"],
                            "description": "Type of bible",
                            "default": "series",
                        },
                        "created_by": {"type": "string", "description": "Creator name"},
                    },
                    "required": ["script_id", "title"],
                },
            },
            {
                "name": "create_character_profile",
                "description": "Create or update a character profile in the bible",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "character_id": {
                            "type": "string",
                            "description": "Character ID",
                        },
                        "script_id": {"type": "string", "description": "Script ID"},
                        "age": {"type": "integer", "description": "Character age"},
                        "occupation": {"type": "string", "description": "Occupation"},
                        "background": {
                            "type": "string",
                            "description": "Background story",
                        },
                        "goals": {"type": "string", "description": "Character goals"},
                        "fears": {"type": "string", "description": "Character fears"},
                        "character_arc": {
                            "type": "string",
                            "description": "Character development arc",
                        },
                    },
                    "required": ["character_id", "script_id"],
                },
            },
            {
                "name": "add_world_element",
                "description": "Add a world-building element to the script bible",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                        "element_type": {
                            "type": "string",
                            "enum": [
                                "location",
                                "technology",
                                "culture",
                                "history",
                                "rule",
                                "other",
                            ],
                            "description": "Type of world element",
                        },
                        "name": {"type": "string", "description": "Element name"},
                        "description": {
                            "type": "string",
                            "description": "Element description",
                        },
                        "importance_level": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5,
                            "description": "Importance level (1-5)",
                        },
                    },
                    "required": ["script_id", "element_type", "name"],
                },
            },
            {
                "name": "create_timeline_event",
                "description": "Add an event to the story timeline",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "timeline_id": {"type": "string", "description": "Timeline ID"},
                        "script_id": {"type": "string", "description": "Script ID"},
                        "event_name": {"type": "string", "description": "Event name"},
                        "event_type": {
                            "type": "string",
                            "enum": [
                                "story",
                                "backstory",
                                "flashback",
                                "flashforward",
                                "parallel",
                            ],
                            "description": "Type of event",
                        },
                        "description": {
                            "type": "string",
                            "description": "Event description",
                        },
                        "story_date": {
                            "type": "string",
                            "description": "Date in story time",
                        },
                        "episode_id": {
                            "type": "string",
                            "description": "Episode ID where event occurs",
                        },
                    },
                    "required": [
                        "timeline_id",
                        "script_id",
                        "event_name",
                        "event_type",
                    ],
                },
            },
            {
                "name": "check_continuity",
                "description": "Run continuity validation checks on the script",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                        "create_notes": {
                            "type": "boolean",
                            "description": "Create continuity notes for issues found",
                            "default": False,
                        },
                    },
                    "required": ["script_id"],
                },
            },
            {
                "name": "add_character_knowledge",
                "description": "Track character knowledge at different story points",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                        "character_name": {
                            "type": "string",
                            "description": "Character name",
                        },
                        "knowledge_type": {
                            "type": "string",
                            "enum": [
                                "fact",
                                "secret",
                                "skill",
                                "relationship",
                                "location",
                                "event",
                            ],
                            "description": "Type of knowledge",
                        },
                        "knowledge_subject": {
                            "type": "string",
                            "description": "What the knowledge is about",
                        },
                        "knowledge_description": {
                            "type": "string",
                            "description": "Detailed description",
                        },
                        "acquired_episode": {
                            "type": "string",
                            "description": "Episode where knowledge was acquired",
                        },
                        "acquisition_method": {
                            "type": "string",
                            "description": "How the knowledge was acquired",
                        },
                    },
                    "required": [
                        "script_id",
                        "character_name",
                        "knowledge_type",
                        "knowledge_subject",
                    ],
                },
            },
            {
                "name": "get_continuity_report",
                "description": "Generate a comprehensive continuity report",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                    },
                    "required": ["script_id"],
                },
            },
            {
                "name": "list_mentors",
                "description": "List all available screenplay analysis mentors",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "analyze_script_with_mentor",
                "description": "Analyze a screenplay using a specific mentor",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID to analyze",
                        },
                        "mentor_name": {
                            "type": "string",
                            "description": "Name of the mentor to use",
                        },
                        "config": {
                            "type": "object",
                            "description": "Optional mentor configuration",
                            "additionalProperties": True,
                        },
                        "save_results": {
                            "type": "boolean",
                            "description": "Whether to save results to database",
                            "default": True,
                        },
                    },
                    "required": ["script_id", "mentor_name"],
                },
            },
            {
                "name": "get_mentor_results",
                "description": "Get previous mentor analysis results for a script",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                        "mentor_name": {
                            "type": "string",
                            "description": "Optional: filter by mentor name",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100,
                        },
                    },
                    "required": ["script_id"],
                },
            },
            {
                "name": "search_mentor_analyses",
                "description": "Search mentor analysis findings",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "mentor_name": {
                            "type": "string",
                            "description": "Optional: filter by mentor name",
                        },
                        "category": {
                            "type": "string",
                            "description": "Optional: filter by analysis category",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["error", "warning", "suggestion", "info"],
                            "description": "Optional: filter by severity level",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_mentor_statistics",
                "description": "Get statistics about mentor analyses for a script",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {"type": "string", "description": "Script ID"},
                    },
                    "required": ["script_id"],
                },
            },
        ]

        # Filter based on configuration
        if not self.config.mcp.enable_all_tools and hasattr(
            self.config.mcp, "enabled_tools"
        ):
            enabled_names = self.config.mcp.enabled_tools
            tools = [t for t in tools if t["name"] in enabled_names]

        return tools

    def get_available_resources(self) -> list[dict[str, Any]]:
        """Get list of available MCP resources.

        Returns:
            List of resource definitions
        """
        return [
            {
                "uri": "screenplay://list",
                "name": "Available Screenplays",
                "description": "List of all parsed screenplays",
                "mimeType": "application/json",
            },
            {
                "uri": "screenplay://{script_id}",
                "name": "Screenplay Details",
                "description": "Full screenplay structure and metadata",
                "mimeType": "application/json",
            },
            {
                "uri": "scene://{script_id}/{scene_id}",
                "name": "Scene Details",
                "description": "Individual scene information",
                "mimeType": "application/json",
            },
            {
                "uri": "character://{script_id}/{character_name}",
                "name": "Character Information",
                "description": "Character details and relationships",
                "mimeType": "application/json",
            },
            {
                "uri": "timeline://{script_id}",
                "name": "Script Timeline",
                "description": "Temporal flow and structure",
                "mimeType": "application/json",
            },
        ]

    async def _handle_list_tools(
        self, _request: types.ListToolsRequest
    ) -> types.ServerResult:
        """Handle list tools request."""
        tools = self.get_available_tools()
        return types.ServerResult(
            types.ListToolsResult(
                tools=[
                    types.Tool(
                        name=tool["name"],
                        description=tool["description"],
                        inputSchema=tool["inputSchema"],
                    )
                    for tool in tools
                ]
            )
        )

    async def _handle_tool_call(
        self, request: types.CallToolRequest
    ) -> types.ServerResult:
        """Handle tool call request."""
        tool_name = request.params.name
        arguments = request.params.arguments or {}

        self.logger.debug("Tool call", tool=tool_name, arguments=arguments)

        try:
            # Map tool names to handler methods
            tool_handlers: dict[
                str, Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
            ] = {
                "parse_script": self._tool_parse_script,
                "search_scenes": self._tool_search_scenes,
                "get_character_info": self._tool_get_character_info,
                "analyze_timeline": self._tool_analyze_timeline,
                "list_scripts": self._tool_list_scripts,
                "update_scene": self._tool_update_scene,
                "delete_scene": self._tool_delete_scene,
                "inject_scene": self._tool_inject_scene,
                "get_scene_details": self._tool_get_scene_details,
                "get_character_relationships": self._tool_get_character_relationships,
                "export_data": self._tool_export_data,
                # Script Bible tools
                "create_series_bible": self._tool_create_series_bible,
                "create_character_profile": self._tool_create_character_profile,
                "add_world_element": self._tool_add_world_element,
                "create_timeline_event": self._tool_create_timeline_event,
                "check_continuity": self._tool_check_continuity,
                "add_character_knowledge": self._tool_add_character_knowledge,
                "get_continuity_report": self._tool_get_continuity_report,
                # Mentor tools
                "list_mentors": self._tool_list_mentors,
                "analyze_script_with_mentor": self._tool_analyze_script_with_mentor,
                "get_mentor_results": self._tool_get_mentor_results,
                "search_mentor_analyses": self._tool_search_mentor_analyses,
                "get_mentor_statistics": self._tool_get_mentor_statistics,
            }

            if tool_name not in tool_handlers:
                raise ValueError(f"Unknown tool: {tool_name}")

            result = await tool_handlers[tool_name](arguments)

            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text=json.dumps(result, indent=2)
                        )
                    ],
                    isError=False,
                )
            )

        except Exception as e:
            self.logger.error("Tool call failed", tool=tool_name, error=str(e))
            return types.ServerResult(
                types.CallToolResult(
                    content=[types.TextContent(type="text", text=str(e))],
                    isError=True,
                )
            )

    async def _tool_parse_script(self, args: dict[str, Any]) -> dict[str, Any]:
        """Parse a screenplay file."""
        path_str = args.get("path")
        if not path_str:
            raise ValueError("path is required")

        # Validate file path for security
        path = Path(path_str).resolve()

        # Check if file exists
        if not path.exists():
            raise ValueError(f"File not found: {path_str}")

        # Check if it's a file (not directory)
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path_str}")

        # Check file extension
        if path.suffix.lower() not in [".fountain", ".spmd", ".txt"]:
            raise ValueError(
                f"Invalid file type: {path.suffix}. Expected .fountain, .spmd, or .txt"
            )

        title = args.get("title")

        # Parse the script
        script = self.scriptrag.parse_fountain(str(path))
        if title:
            script.title = title

        # Cache the script with UUID to prevent collisions
        script_id = f"script_{uuid.uuid4().hex[:8]}"
        self._add_to_cache(script_id, script)

        return {
            "script_id": script_id,
            "title": script.title,
            "source_file": script.source_file,
            "scenes_count": len(script.scenes) if hasattr(script, "scenes") else 0,
            "characters": (
                list(script.characters) if hasattr(script, "characters") else []
            ),
        }

    async def _tool_search_scenes(self, args: dict[str, Any]) -> dict[str, Any]:
        """Search for scenes."""
        script_id = args.get("script_id")
        if not script_id:
            raise ValueError("script_id is required")

        # Validate script exists
        _ = self._validate_script_id(script_id)

        # Get search criteria
        query = args.get("query")
        location = args.get("location")
        characters = args.get("characters", [])
        limit = args.get("limit", 10)

        # Search scenes in database
        from .database.connection import DatabaseConnection

        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            # Build search conditions
            conditions = []
            params = []

            # Base query to find scenes for this script
            base_query = """
                SELECT DISTINCT s.*, n.properties_json as properties
                FROM scenes s
                JOIN nodes n ON n.entity_id = s.id AND n.node_type = 'scene'
                JOIN edges e ON e.to_node_id = n.id AND e.edge_type = 'HAS_SCENE'
                JOIN nodes script_n ON script_n.id = e.from_node_id
                    AND script_n.entity_id = ? AND script_n.node_type = 'script'
                WHERE 1=1
            """
            params.append(script_id)

            # Add text search if query provided
            if query:
                conditions.append("(s.heading LIKE ? OR s.description LIKE ?)")
                params.extend([f"%{query}%", f"%{query}%"])

            # Add location filter
            if location:
                conditions.append("""
                    EXISTS (
                        SELECT 1 FROM edges loc_e
                        JOIN nodes loc_n ON loc_n.id = loc_e.to_node_id
                        WHERE loc_e.from_node_id = n.id
                        AND loc_e.edge_type = 'AT_LOCATION'
                        AND UPPER(loc_n.label) LIKE UPPER(?)
                    )
                """)
                params.append(f"%{location}%")

            # Add character filter
            if characters:
                char_conditions = []
                for char_name in characters:
                    char_conditions.append("""
                        EXISTS (
                            SELECT 1 FROM edges char_e
                            JOIN nodes char_n ON char_n.id = char_e.from_node_id
                            WHERE char_e.to_node_id = n.id
                            AND char_e.edge_type = 'APPEARS_IN'
                            AND char_n.node_type = 'character'
                            AND UPPER(char_n.label) LIKE UPPER(?)
                        )
                    """)
                    params.append(f"%{char_name}%")

                if char_conditions:
                    conditions.append(f"({' OR '.join(char_conditions)})")

            # Combine conditions
            if conditions:
                base_query += " AND " + " AND ".join(conditions)

            # Add ordering and limit
            base_query += " ORDER BY s.script_order LIMIT ?"
            params.append(limit)

            # Execute query
            cursor = connection.execute(base_query, tuple(params))
            rows = cursor.fetchall()

            # Format results
            results = []
            for row in rows:
                scene_data = {
                    "scene_id": row["id"],
                    "heading": row["heading"],
                    "description": row["description"],
                    "script_order": row["script_order"],
                    "temporal_order": row["temporal_order"],
                    "logical_order": row["logical_order"],
                    "time_of_day": row["time_of_day"],
                }

                # Get characters in scene
                char_query = """
                    SELECT DISTINCT c.name
                    FROM characters c
                    JOIN nodes cn
                        ON cn.entity_id = c.id AND cn.node_type = 'character'
                    JOIN edges e
                        ON e.from_node_id = cn.id AND e.edge_type = 'APPEARS_IN'
                    JOIN nodes sn ON sn.id = e.to_node_id AND sn.entity_id = ?
                """
                char_cursor = connection.execute(char_query, (row["id"],))
                scene_data["characters"] = [r["name"] for r in char_cursor.fetchall()]

                # Get location
                loc_query = """
                    SELECT l.label
                    FROM nodes l
                    JOIN edges e
                        ON e.to_node_id = l.id AND e.edge_type = 'AT_LOCATION'
                    JOIN nodes sn ON sn.id = e.from_node_id AND sn.entity_id = ?
                    LIMIT 1
                """
                loc_cursor = connection.execute(loc_query, (row["id"],))
                loc_row = loc_cursor.fetchone()
                scene_data["location"] = loc_row["label"] if loc_row else None

                results.append(scene_data)

            return {
                "script_id": script_id,
                "results": results,
                "total_matches": len(results),
                "search_criteria": {
                    "query": query,
                    "location": location,
                    "characters": characters,
                },
            }

    async def _tool_get_character_info(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get character information."""
        script_id = args.get("script_id")
        character_name = args.get("character_name")

        if not script_id or not character_name:
            raise ValueError("script_id and character_name are required")

        # Validate script exists
        _ = self._validate_script_id(script_id)

        # Get character information from database
        from .database.connection import DatabaseConnection

        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            # Find character in this script
            char_query = """
                SELECT c.*, cn.id as node_id
                FROM characters c
                JOIN nodes cn
                    ON cn.entity_id = c.id AND cn.node_type = 'character'
                JOIN edges e
                    ON e.to_node_id = cn.id AND e.edge_type = 'HAS_CHARACTER'
                JOIN nodes sn ON sn.id = e.from_node_id
                    AND sn.entity_id = ? AND sn.node_type = 'script'
                WHERE UPPER(c.name) LIKE UPPER(?)
                LIMIT 1
            """
            cursor = connection.execute(char_query, (script_id, f"%{character_name}%"))
            char_row = cursor.fetchone()

            if not char_row:
                return {
                    "script_id": script_id,
                    "character_name": character_name,
                    "scenes_count": 0,
                    "dialogue_lines": 0,
                    "relationships": [],
                    "error": f"Character '{character_name}' not found in script",
                }

            character_id = char_row["id"]
            char_node_id = char_row["node_id"]

            # Get scene appearances
            scene_query = """
                SELECT COUNT(DISTINCT s.id) as scene_count
                FROM scenes s
                JOIN nodes sn
                    ON sn.entity_id = s.id AND sn.node_type = 'scene'
                JOIN edges e
                    ON e.to_node_id = sn.id AND e.edge_type = 'APPEARS_IN'
                WHERE e.from_node_id = ?
            """
            scene_cursor = connection.execute(scene_query, (char_node_id,))
            scene_count = scene_cursor.fetchone()["scene_count"]

            # Get dialogue count
            dialogue_query = """
                SELECT COUNT(*) as dialogue_count
                FROM dialogue d
                WHERE d.character_id = ?
            """
            dialogue_cursor = connection.execute(dialogue_query, (character_id,))
            dialogue_count = dialogue_cursor.fetchone()["dialogue_count"]

            # Get character relationships
            relationships = []

            # Get characters this character speaks to
            speaks_to_query = """
                SELECT DISTINCT c2.name, COUNT(*) as interaction_count
                FROM edges e
                JOIN nodes cn2
                    ON cn2.id = e.to_node_id AND cn2.node_type = 'character'
                JOIN characters c2 ON c2.id = cn2.entity_id
                WHERE e.from_node_id = ? AND e.edge_type = 'SPEAKS_TO'
                GROUP BY c2.name
                ORDER BY interaction_count DESC
                LIMIT 10
            """
            speaks_cursor = connection.execute(speaks_to_query, (char_node_id,))
            for row in speaks_cursor:
                relationships.append(
                    {
                        "character": row["name"],
                        "relationship_type": "speaks_to",
                        "interaction_count": row["interaction_count"],
                    }
                )

            # Get characters that speak to this character
            spoken_to_query = """
                SELECT DISTINCT c2.name, COUNT(*) as interaction_count
                FROM edges e
                JOIN nodes cn2
                    ON cn2.id = e.from_node_id AND cn2.node_type = 'character'
                JOIN characters c2 ON c2.id = cn2.entity_id
                WHERE e.to_node_id = ? AND e.edge_type = 'SPEAKS_TO'
                GROUP BY c2.name
                ORDER BY interaction_count DESC
                LIMIT 10
            """
            spoken_cursor = connection.execute(spoken_to_query, (char_node_id,))
            for row in spoken_cursor:
                # Check if we already have this relationship
                existing = next(
                    (r for r in relationships if r["character"] == row["name"]), None
                )
                if existing:
                    existing["relationship_type"] = "mutual_dialogue"
                    existing["interaction_count"] += row["interaction_count"]
                else:
                    relationships.append(
                        {
                            "character": row["name"],
                            "relationship_type": "spoken_to_by",
                            "interaction_count": row["interaction_count"],
                        }
                    )

            # Get co-appearances in scenes
            coappear_query = """
                SELECT c2.name, COUNT(DISTINCT s.id) as shared_scenes
                FROM edges e1
                JOIN nodes sn ON sn.id = e1.to_node_id AND sn.node_type = 'scene'
                JOIN scenes s ON s.id = sn.entity_id
                JOIN edges e2
                    ON e2.to_node_id = sn.id AND e2.edge_type = 'APPEARS_IN'
                JOIN nodes cn2
                    ON cn2.id = e2.from_node_id AND cn2.node_type = 'character'
                JOIN characters c2 ON c2.id = cn2.entity_id
                WHERE e1.from_node_id = ? AND e1.edge_type = 'APPEARS_IN'
                    AND cn2.id != ?
                GROUP BY c2.name
                ORDER BY shared_scenes DESC
                LIMIT 10
            """
            coappear_cursor = connection.execute(
                coappear_query, (char_node_id, char_node_id)
            )
            for row in coappear_cursor:
                # Find existing relationship or create new
                existing = next(
                    (r for r in relationships if r["character"] == row["name"]), None
                )
                if existing:
                    existing["shared_scenes"] = row["shared_scenes"]
                else:
                    relationships.append(
                        {
                            "character": row["name"],
                            "relationship_type": "appears_with",
                            "shared_scenes": row["shared_scenes"],
                        }
                    )

            # Calculate character arc info
            first_last_query = """
                SELECT MIN(s.script_order) as first_appearance,
                       MAX(s.script_order) as last_appearance
                FROM scenes s
                JOIN nodes sn
                    ON sn.entity_id = s.id AND sn.node_type = 'scene'
                JOIN edges e
                    ON e.to_node_id = sn.id AND e.edge_type = 'APPEARS_IN'
                WHERE e.from_node_id = ?
            """
            arc_cursor = connection.execute(first_last_query, (char_node_id,))
            arc_row = arc_cursor.fetchone()

            return {
                "script_id": script_id,
                "character_name": char_row["name"],
                "character_id": character_id,
                "description": char_row["description"],
                "scenes_count": scene_count,
                "dialogue_lines": dialogue_count,
                "first_appearance": arc_row["first_appearance"] if arc_row else None,
                "last_appearance": arc_row["last_appearance"] if arc_row else None,
                "relationships": relationships,
            }

    async def _tool_analyze_timeline(self, args: dict[str, Any]) -> dict[str, Any]:
        """Analyze script timeline."""
        script_id = args.get("script_id")
        if not script_id:
            raise ValueError("script_id is required")

        # Validate script exists
        _ = self._validate_script_id(script_id)

        include_flashbacks = args.get("include_flashbacks", True)

        # Analyze timeline from database
        from .database.connection import DatabaseConnection

        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            # Get all scenes in script
            scenes_query = """
                SELECT s.*, n.properties_json as properties
                FROM scenes s
                JOIN nodes n ON n.entity_id = s.id AND n.node_type = 'scene'
                JOIN edges e ON e.to_node_id = n.id AND e.edge_type = 'HAS_SCENE'
                JOIN nodes sn ON sn.id = e.from_node_id
                    AND sn.entity_id = ? AND sn.node_type = 'script'
                ORDER BY s.script_order
            """
            cursor = connection.execute(scenes_query, (script_id,))
            scenes = cursor.fetchall()

            # Analyze timeline structure
            timeline_type = "linear"
            flashbacks_detected = 0
            flash_forwards_detected = 0
            time_periods = []
            temporal_jumps = []

            # Check if we have temporal ordering different from script ordering
            has_temporal_order = any(s["temporal_order"] is not None for s in scenes)

            if has_temporal_order:
                # Analyze temporal structure
                script_to_temporal = {}
                for scene in scenes:
                    if scene["temporal_order"] is not None:
                        script_to_temporal[scene["script_order"]] = scene[
                            "temporal_order"
                        ]

                # Detect non-linear storytelling
                prev_temporal = None
                for i, scene in enumerate(scenes):
                    if scene["temporal_order"] is not None:
                        curr_temporal = scene["temporal_order"]

                        if prev_temporal is not None:
                            # Check for temporal jumps
                            if curr_temporal < prev_temporal:
                                flashbacks_detected += 1
                                temporal_jumps.append(
                                    {
                                        "type": "flashback",
                                        "from_scene": i,
                                        "temporal_distance": prev_temporal
                                        - curr_temporal,
                                    }
                                )
                            elif curr_temporal > prev_temporal + 1:
                                flash_forwards_detected += 1
                                temporal_jumps.append(
                                    {
                                        "type": "flash_forward",
                                        "from_scene": i,
                                        "temporal_distance": curr_temporal
                                        - prev_temporal,
                                    }
                                )

                        prev_temporal = curr_temporal

                if flashbacks_detected > 0 or flash_forwards_detected > 0:
                    timeline_type = "non_linear"

            # Analyze time periods in the script
            time_distribution: dict[str, int] = {}
            location_timeline = []

            for scene in scenes:
                # Track time of day distribution
                time_of_day = scene["time_of_day"]
                if time_of_day:
                    time_distribution[time_of_day] = (
                        time_distribution.get(time_of_day, 0) + 1
                    )

                # Track location changes over time
                if scene["heading"]:
                    location_timeline.append(
                        {
                            "scene_order": scene["script_order"],
                            "temporal_order": scene["temporal_order"],
                            "heading": scene["heading"],
                            "time_of_day": time_of_day,
                        }
                    )

            # Group consecutive scenes by time period
            current_period = None
            period_start = 0

            for i, scene in enumerate(scenes):
                tod = scene["time_of_day"] or "UNSPECIFIED"

                if current_period != tod:
                    if current_period is not None:
                        time_periods.append(
                            {
                                "time_of_day": current_period,
                                "start_scene": period_start,
                                "end_scene": i - 1,
                                "scene_count": i - period_start,
                            }
                        )
                    current_period = tod
                    period_start = i

            # Add final period
            if current_period is not None:
                time_periods.append(
                    {
                        "time_of_day": current_period,
                        "start_scene": period_start,
                        "end_scene": len(scenes) - 1,
                        "scene_count": len(scenes) - period_start,
                    }
                )

            # Check for flashback sequences using scene dependencies
            flashback_sequences = []
            if include_flashbacks:
                dependency_query = """
                    SELECT sd.*,
                           s1.script_order as from_order, s1.heading as from_heading,
                           s2.script_order as to_order, s2.heading as to_heading
                    FROM scene_dependencies sd
                    JOIN scenes s1 ON s1.id = sd.from_scene_id
                    JOIN scenes s2 ON s2.id = sd.to_scene_id
                    JOIN nodes n1 ON n1.entity_id = s1.id
                    JOIN edges e1
                        ON e1.to_node_id = n1.id AND e1.edge_type = 'HAS_SCENE'
                    JOIN nodes sn ON sn.id = e1.from_node_id AND sn.entity_id = ?
                    WHERE sd.dependency_type = 'flashback_to'
                """
                dep_cursor = connection.execute(dependency_query, (script_id,))
                for dep in dep_cursor:
                    flashback_sequences.append(
                        {
                            "from_scene": dep["from_order"],
                            "to_scene": dep["to_order"],
                            "strength": dep["strength"],
                            "description": dep["description"],
                        }
                    )

            # Build final analysis
            result = {
                "script_id": script_id,
                "timeline_type": timeline_type,
                "total_scenes": len(scenes),
                "has_temporal_ordering": has_temporal_order,
                "time_distribution": time_distribution,
                "time_periods": time_periods,
                "temporal_jumps": temporal_jumps if include_flashbacks else [],
            }

            if include_flashbacks:
                result.update(
                    {
                        "flashbacks_detected": flashbacks_detected,
                        "flash_forwards_detected": flash_forwards_detected,
                        "flashback_sequences": flashback_sequences,
                    }
                )
            else:
                result.update(
                    {
                        "flashbacks_detected": None,
                        "flash_forwards_detected": None,
                        "flashback_sequences": [],
                    }
                )

            # Add narrative structure analysis
            if len(scenes) > 0:
                act_boundaries = {
                    "act_1_end": len(scenes) // 4,
                    "act_2_midpoint": len(scenes) // 2,
                    "act_2_end": (3 * len(scenes)) // 4,
                }

                result["narrative_structure"] = {
                    "estimated_acts": 3,
                    "act_boundaries": act_boundaries,
                    "scenes_per_act": {
                        "act_1": act_boundaries["act_1_end"],
                        "act_2": act_boundaries["act_2_end"]
                        - act_boundaries["act_1_end"],
                        "act_3": len(scenes) - act_boundaries["act_2_end"],
                    },
                }

            return result

    async def _tool_list_scripts(self, _args: dict[str, Any]) -> dict[str, Any]:
        """List all scripts."""
        scripts = []
        for script_id, script in self._scripts_cache.items():
            scripts.append(
                {
                    "script_id": script_id,
                    "title": script.title,
                    "source_file": script.source_file,
                }
            )

        return {
            "scripts": scripts,
            "total": len(scripts),
        }

    async def _tool_update_scene(self, args: dict[str, Any]) -> dict[str, Any]:
        """Update a scene."""
        script_id = args.get("script_id")
        scene_id = args.get("scene_id")

        if not script_id or scene_id is None:
            raise ValueError("script_id and scene_id are required")

        # Update scene in database
        from .database.connection import DatabaseConnection
        from .database.operations import GraphOperations

        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            graph_ops = GraphOperations(connection)

            # First verify the scene belongs to this script
            verify_query = """
                SELECT s.id, n.id as node_id
                FROM scenes s
                JOIN nodes n ON n.entity_id = s.id AND n.node_type = 'scene'
                JOIN edges e ON e.to_node_id = n.id AND e.edge_type = 'HAS_SCENE'
                JOIN nodes sn ON sn.id = e.from_node_id
                    AND sn.entity_id = ? AND sn.node_type = 'script'
                WHERE s.id = ?
            """
            cursor = connection.execute(verify_query, (script_id, scene_id))
            scene_row = cursor.fetchone()

            if not scene_row:
                raise ValueError(f"Scene {scene_id} not found in script {script_id}")

            scene_node_id = scene_row["node_id"]

            # Get update parameters
            heading = args.get("heading")
            action = args.get("action")
            dialogue_entries = args.get("dialogue", [])

            # Track changes made
            changes = {}

            # Update scene metadata using graph operations
            if heading or action:
                success = graph_ops.update_scene_metadata(
                    scene_node_id=scene_node_id,
                    heading=heading,
                    description=action,
                    propagate_to_graph=True,
                )
                if success:
                    if heading:
                        changes["heading"] = heading
                    if action:
                        changes["action"] = action

            # Handle dialogue updates
            if dialogue_entries:
                # Delete existing dialogue for this scene
                delete_dialogue_query = """
                    DELETE FROM dialogue
                    WHERE scene_id = ?
                """
                connection.execute(delete_dialogue_query, (scene_id,))

                # Insert new dialogue entries
                dialogue_count = 0
                for entry in dialogue_entries:
                    character_name = entry.get("character")
                    text = entry.get("text")
                    parenthetical = entry.get("parenthetical")

                    if character_name and text:
                        # Find or create character
                        char_query = """
                            SELECT c.id FROM characters c
                            JOIN nodes cn ON cn.entity_id = c.id
                            JOIN edges e
                                ON e.to_node_id = cn.id
                                AND e.edge_type = 'HAS_CHARACTER'
                            JOIN nodes sn
                                ON sn.id = e.from_node_id AND sn.entity_id = ?
                            WHERE UPPER(c.name) = UPPER(?)
                        """
                        char_cursor = connection.execute(
                            char_query, (script_id, character_name)
                        )
                        char_row = char_cursor.fetchone()

                        if char_row:
                            character_id = char_row["id"]
                        else:
                            # Create new character
                            from uuid import uuid4

                            character_id = str(uuid4())

                            insert_char_query = """
                                INSERT INTO characters (
                                    id, name, description, created_at, updated_at
                                ) VALUES (?, ?, '', datetime('now'), datetime('now'))
                            """
                            connection.execute(
                                insert_char_query,
                                (character_id, character_name.upper()),
                            )

                            # Add to graph
                            from uuid import UUID

                            from .models import Character

                            # Get script node ID
                            script_nodes = graph_ops.graph.find_nodes(
                                node_type="script", entity_id=script_id
                            )
                            if not script_nodes:
                                raise ValueError(f"Script {script_id} not found")

                            script_node_id = script_nodes[0].id

                            graph_ops.create_character_node(
                                Character(
                                    id=UUID(character_id),
                                    name=character_name.upper(),
                                    description="",
                                ),
                                script_node_id,
                            )

                        # Insert dialogue
                        from uuid import uuid4

                        dialogue_id = str(uuid4())

                        insert_dialogue_query = """
                            INSERT INTO dialogue (
                                id, element_type, text, raw_text, scene_id,
                                order_in_scene, character_id, character_name,
                                created_at, updated_at
                            ) VALUES (
                                ?, 'dialogue', ?, ?, ?, ?, ?, ?,
                                datetime('now'), datetime('now')
                            )
                        """
                        connection.execute(
                            insert_dialogue_query,
                            (
                                dialogue_id,
                                text,
                                text,  # raw_text
                                scene_id,
                                dialogue_count,
                                character_id,
                                character_name.upper(),
                            ),
                        )
                        dialogue_count += 1

                        # Insert parenthetical if provided
                        if parenthetical:
                            paren_id = str(uuid4())
                            insert_paren_query = """
                                INSERT INTO parentheticals (
                                    id, element_type, text, raw_text, scene_id,
                                    order_in_scene, associated_dialogue_id,
                                    created_at, updated_at
                                ) VALUES (
                                    ?, 'parenthetical', ?, ?, ?, ?, ?,
                                    datetime('now'), datetime('now')
                                )
                            """
                            connection.execute(
                                insert_paren_query,
                                (
                                    paren_id,
                                    parenthetical,
                                    f"({parenthetical})",
                                    scene_id,
                                    dialogue_count,
                                    dialogue_id,
                                ),
                            )
                            dialogue_count += 1

                changes["dialogue"] = f"Updated with {len(dialogue_entries)} entries"

                # Update character appearances in graph
                graph_ops._update_character_appearances(scene_node_id, action or "")

            return {
                "script_id": script_id,
                "scene_id": scene_id,
                "updated": True,
                "changes": changes,
            }

    async def _tool_delete_scene(self, args: dict[str, Any]) -> dict[str, Any]:
        """Delete a scene."""
        script_id = args.get("script_id")
        scene_id = args.get("scene_id")

        if not script_id or scene_id is None:
            raise ValueError("script_id and scene_id are required")

        # Delete scene from database
        from .database.connection import DatabaseConnection
        from .database.operations import GraphOperations

        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            graph_ops = GraphOperations(connection)

            # First verify the scene belongs to this script
            verify_query = """
                SELECT s.id, s.script_order, n.id as node_id
                FROM scenes s
                JOIN nodes n ON n.entity_id = s.id AND n.node_type = 'scene'
                JOIN edges e ON e.to_node_id = n.id AND e.edge_type = 'HAS_SCENE'
                JOIN nodes sn ON sn.id = e.from_node_id
                    AND sn.entity_id = ? AND sn.node_type = 'script'
                WHERE s.id = ?
            """
            cursor = connection.execute(verify_query, (script_id, scene_id))
            scene_row = cursor.fetchone()

            if not scene_row:
                raise ValueError(f"Scene {scene_id} not found in script {script_id}")

            scene_node_id = scene_row["node_id"]
            deleted_script_order = scene_row["script_order"]

            # Use graph operations to delete with reference integrity
            success = graph_ops.delete_scene_with_references(scene_node_id)

            if not success:
                raise ValueError(f"Failed to delete scene {scene_id}")

            # Get remaining scenes that need reordering
            reorder_query = """
                SELECT s.id, s.script_order, n.id as node_id
                FROM scenes s
                JOIN nodes n ON n.entity_id = s.id AND n.node_type = 'scene'
                JOIN edges e ON e.to_node_id = n.id AND e.edge_type = 'HAS_SCENE'
                JOIN nodes sn ON sn.id = e.from_node_id
                    AND sn.entity_id = ? AND sn.node_type = 'script'
                WHERE s.script_order > ?
                ORDER BY s.script_order
            """
            reorder_cursor = connection.execute(
                reorder_query, (script_id, deleted_script_order)
            )
            scenes_to_reorder = reorder_cursor.fetchall()

            # Update script_order for remaining scenes
            for i, scene in enumerate(scenes_to_reorder):
                new_order = deleted_script_order + i
                update_query = """
                    UPDATE scenes
                    SET script_order = ?, updated_at = datetime('now')
                    WHERE id = ?
                """
                connection.execute(update_query, (new_order, scene["id"]))

            return {
                "script_id": script_id,
                "scene_id": scene_id,
                "deleted": True,
                "scenes_reordered": len(scenes_to_reorder),
            }

    async def _tool_inject_scene(self, args: dict[str, Any]) -> dict[str, Any]:
        """Inject a new scene."""
        script_id = args.get("script_id")
        position = args.get("position")
        heading = args.get("heading")

        if not script_id or position is None or not heading:
            raise ValueError("script_id, position, and heading are required")

        # Inject scene into database
        from uuid import uuid4

        from .database.connection import DatabaseConnection
        from .database.operations import GraphOperations
        from .models import Location, Scene

        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            graph_ops = GraphOperations(connection)

            # Verify script exists
            script_query = """
                SELECT n.id as node_id
                FROM nodes n
                WHERE n.entity_id = ? AND n.node_type = 'script'
            """
            cursor = connection.execute(script_query, (script_id,))
            script_row = cursor.fetchone()

            if not script_row:
                raise ValueError(f"Script {script_id} not found")

            script_node_id = script_row["node_id"]

            # Count existing scenes to validate position
            count_query = """
                SELECT COUNT(*) as scene_count
                FROM scenes s
                JOIN nodes n ON n.entity_id = s.id AND n.node_type = 'scene'
                JOIN edges e ON e.to_node_id = n.id AND e.edge_type = 'HAS_SCENE'
                WHERE e.from_node_id = ?
            """
            count_cursor = connection.execute(count_query, (script_node_id,))
            scene_count = count_cursor.fetchone()["scene_count"]

            # Validate position
            if position < 0 or position > scene_count:
                raise ValueError(
                    f"Invalid position {position}. Must be between 0 and {scene_count}"
                )

            # Parse scene heading to extract location info
            location = None
            time_of_day = None

            # Simple parsing of scene heading (e.g., "INT. COFFEE SHOP - DAY")
            import re

            heading_pattern = r"^(INT\.|EXT\.)\s+(.+?)(?:\s*-\s*(.+))?$"
            match = re.match(heading_pattern, heading.upper())

            if match:
                int_ext = match.group(1)
                location_name = match.group(2).strip()
                time_of_day = match.group(3).strip() if match.group(3) else None

                location = Location(
                    interior=int_ext == "INT.",
                    name=location_name,
                    time=time_of_day,
                    raw_text=heading,
                )

            # Create new scene
            scene_id = uuid4()
            scene = Scene(
                id=scene_id,
                location=location,
                heading=heading,
                description=args.get("action", ""),
                script_order=position,  # Will be adjusted after reordering
                script_id=script_id,
                time_of_day=time_of_day,
            )

            # Get dialogue entries if provided
            dialogue_entries = args.get("dialogue", [])
            characters = []

            # Extract character names from dialogue
            for entry in dialogue_entries:
                char_name = entry.get("character")
                if char_name and char_name not in characters:
                    characters.append(char_name)

            # Use graph operations to inject the scene
            success = graph_ops.inject_scene_at_position(
                script_node_id=script_node_id,
                scene=scene,
                position=position,
                characters=characters,
                location=location_name if location else None,
            )

            if not success:
                raise ValueError(f"Failed to inject scene at position {position}")

            # Add dialogue entries if provided
            if dialogue_entries:
                dialogue_count = 0
                for entry in dialogue_entries:
                    character_name = entry.get("character")
                    text = entry.get("text")
                    parenthetical = entry.get("parenthetical")

                    if character_name and text:
                        # Find character
                        char_query = """
                            SELECT c.id FROM characters c
                            JOIN nodes cn ON cn.entity_id = c.id
                            JOIN edges e
                                ON e.to_node_id = cn.id
                                AND e.edge_type = 'HAS_CHARACTER'
                            JOIN nodes sn
                                ON sn.id = e.from_node_id AND sn.entity_id = ?
                            WHERE UPPER(c.name) = UPPER(?)
                        """
                        char_cursor = connection.execute(
                            char_query, (script_id, character_name)
                        )
                        char_row = char_cursor.fetchone()

                        if char_row:
                            character_id = char_row["id"]

                            # Insert dialogue
                            dialogue_id = str(uuid4())

                            insert_dialogue_query = """
                                INSERT INTO dialogue (
                                    id, element_type, text, raw_text, scene_id,
                                    order_in_scene, character_id, character_name,
                                    created_at, updated_at
                                ) VALUES (
                                    ?, 'dialogue', ?, ?, ?, ?, ?, ?,
                                    datetime('now'), datetime('now')
                                )
                            """
                            connection.execute(
                                insert_dialogue_query,
                                (
                                    dialogue_id,
                                    text,
                                    text,
                                    str(scene_id),
                                    dialogue_count,
                                    character_id,
                                    character_name.upper(),
                                ),
                            )
                            dialogue_count += 1

                            # Insert parenthetical if provided
                            if parenthetical:
                                paren_id = str(uuid4())
                                insert_paren_query = """
                                    INSERT INTO parentheticals (
                                        id, element_type, text, raw_text, scene_id,
                                        order_in_scene, associated_dialogue_id,
                                        created_at, updated_at
                                    ) VALUES (
                                        ?, 'parenthetical', ?, ?, ?, ?, ?,
                                        datetime('now'), datetime('now')
                                    )
                                """
                                connection.execute(
                                    insert_paren_query,
                                    (
                                        paren_id,
                                        parenthetical,
                                        f"({parenthetical})",
                                        str(scene_id),
                                        dialogue_count,
                                        dialogue_id,
                                    ),
                                )
                                dialogue_count += 1

            return {
                "script_id": script_id,
                "scene_id": str(scene_id),
                "position": position,
                "heading": heading,
                "injected": True,
                "characters_added": len(characters),
                "dialogue_entries": len(dialogue_entries),
            }

    async def _tool_get_scene_details(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get scene details."""
        script_id = args.get("script_id")
        scene_id = args.get("scene_id")

        if not script_id or scene_id is None:
            raise ValueError("script_id and scene_id are required")

        # Validate script exists
        _ = self._validate_script_id(script_id)

        from .database.connection import DatabaseConnection

        db_connection = DatabaseConnection(str(self.config.get_database_path()))
        with db_connection.get_connection() as connection:
            # Query scene data
            scene_query = """
                SELECT s.*, l.name as location_name, l.interior, l.time_of_day
                FROM scenes s
                LEFT JOIN locations l ON s.location_id = l.id
                WHERE s.id = ? AND s.script_id = ?
            """
            cursor = connection.execute(scene_query, (scene_id, script_id))
            scene_row = cursor.fetchone()

            if not scene_row:
                raise ValueError(f"Scene not found: {scene_id}")

            # Extract scene elements (action, dialogue, parentheticals)
            elements_query = """
                SELECT se.*, c.name as character_name
                FROM scene_elements se
                LEFT JOIN characters c ON se.character_id = c.id
                WHERE se.scene_id = ?
                ORDER BY se.order_in_scene
            """
            cursor = connection.execute(elements_query, (scene_id,))
            elements = cursor.fetchall()

            # Build action text and dialogue array
            action_parts = []
            dialogue_entries = []
            current_character = None
            current_dialogue = None

            for element in elements:
                element_type = element["element_type"]
                text = element["text"]

                if element_type == "action":
                    action_parts.append(text)
                elif element_type == "dialogue":
                    # If we have a previous dialogue entry, add it
                    if current_dialogue:
                        dialogue_entries.append(current_dialogue)

                    current_character = (
                        element["character_name"] or element["character_id"]
                    )
                    current_dialogue = {
                        "character": current_character,
                        "text": text,
                        "parentheticals": [],
                    }
                elif element_type == "parenthetical" and current_dialogue:
                    current_dialogue["parentheticals"].append(text)
                elif element_type == "character":
                    # Character cue - already handled in dialogue
                    pass

            # Add the last dialogue entry if exists
            if current_dialogue:
                dialogue_entries.append(current_dialogue)

            # Get unique characters in the scene
            char_query = """
                SELECT DISTINCT c.name, COUNT(se.id) as line_count
                FROM characters c
                JOIN scene_elements se ON se.character_id = c.id
                WHERE se.scene_id = ? AND se.element_type = 'dialogue'
                GROUP BY c.id, c.name
            """
            cursor = connection.execute(char_query, (scene_id,))
            character_stats = cursor.fetchall()

            characters = []
            for char_row in character_stats:
                characters.append(
                    {"name": char_row["name"], "line_count": char_row["line_count"]}
                )

            # Format response
            return {
                "script_id": script_id,
                "scene_id": scene_id,
                "heading": scene_row["heading"] or "",
                "action": "\n\n".join(action_parts) if action_parts else "",
                "dialogue": dialogue_entries,
                "characters": characters,
                "page_number": scene_row["script_order"] or 1,
                "location": {
                    "name": scene_row["location_name"] or "",
                    "interior": (
                        scene_row["interior"]
                        if scene_row["interior"] is not None
                        else True
                    ),
                    "time_of_day": scene_row["time_of_day"] or "",
                }
                if scene_row["location_id"]
                else None,
                "temporal_order": scene_row["temporal_order"],
                "logical_order": scene_row["logical_order"],
                "estimated_duration_minutes": scene_row["estimated_duration_minutes"],
                "time_of_day": scene_row["time_of_day"],
                "date_in_story": scene_row["date_in_story"],
                "description": scene_row["description"] or "",
            }

    async def _tool_get_character_relationships(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Get character relationships."""
        script_id = args.get("script_id")
        if not script_id:
            raise ValueError("script_id is required")

        character_name = args.get("character_name")

        # TODO: Implement relationship analysis
        return {
            "script_id": script_id,
            "character_name": character_name,
            "relationships": [],
            "total_characters": 0,
        }

    async def _tool_export_data(self, args: dict[str, Any]) -> dict[str, Any]:
        """Export script data."""
        script_id = args.get("script_id")
        export_format = args.get("format")

        if not script_id or not export_format:
            raise ValueError("script_id and format are required")

        include_metadata = args.get("include_metadata", True)

        # TODO: Implement actual export functionality
        return {
            "script_id": script_id,
            "format": export_format,
            "exported": True,
            "file_path": f"exports/{script_id}.{export_format}",
            "include_metadata": include_metadata,
        }

    # Script Bible Tool Implementations

    async def _tool_create_series_bible(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create a new script bible."""
        from .database.bible import ScriptBibleOperations
        from .database.connection import DatabaseConnection

        script_id = args["script_id"]
        title = args["title"]
        description = args.get("description")
        bible_type = args.get("bible_type", "series")
        created_by = args.get("created_by")

        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            bible_ops = ScriptBibleOperations(connection)

            bible_id = bible_ops.create_series_bible(
                script_id=script_id,
                title=title,
                description=description,
                bible_type=bible_type,
                created_by=created_by,
            )

            return {
                "bible_id": bible_id,
                "script_id": script_id,
                "title": title,
                "created": True,
            }

    async def _tool_create_character_profile(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a character profile."""
        from .database.bible import ScriptBibleOperations
        from .database.connection import DatabaseConnection

        character_id = args["character_id"]
        script_id = args["script_id"]

        profile_data = {
            k: v
            for k, v in args.items()
            if k not in ["character_id", "script_id"] and v is not None
        }

        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            bible_ops = ScriptBibleOperations(connection)

            profile_id = bible_ops.create_character_profile(
                character_id=character_id, script_id=script_id, **profile_data
            )

            return {
                "profile_id": profile_id,
                "character_id": character_id,
                "script_id": script_id,
                "created": True,
            }

    async def _tool_add_world_element(self, args: dict[str, Any]) -> dict[str, Any]:
        """Add a world-building element."""
        from .database.bible import ScriptBibleOperations
        from .database.connection import DatabaseConnection

        script_id = args["script_id"]
        element_type = args["element_type"]
        name = args["name"]

        element_data = {
            k: v
            for k, v in args.items()
            if k not in ["script_id", "element_type", "name"] and v is not None
        }

        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            bible_ops = ScriptBibleOperations(connection)

            element_id = bible_ops.create_world_element(
                script_id=script_id,
                element_type=element_type,
                name=name,
                **element_data,
            )

            return {
                "element_id": element_id,
                "script_id": script_id,
                "element_type": element_type,
                "name": name,
                "created": True,
            }

    async def _tool_create_timeline_event(self, args: dict[str, Any]) -> dict[str, Any]:
        """Create a timeline event."""
        from .database.bible import ScriptBibleOperations
        from .database.connection import DatabaseConnection

        timeline_id = args["timeline_id"]
        script_id = args["script_id"]
        event_name = args["event_name"]
        event_type = args["event_type"]

        event_data = {
            k: v
            for k, v in args.items()
            if k not in ["timeline_id", "script_id", "event_name", "event_type"]
            and v is not None
        }

        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            bible_ops = ScriptBibleOperations(connection)

            event_id = bible_ops.add_timeline_event(
                timeline_id=timeline_id,
                script_id=script_id,
                event_name=event_name,
                event_type=event_type,
                **event_data,
            )

            return {
                "event_id": event_id,
                "timeline_id": timeline_id,
                "event_name": event_name,
                "created": True,
            }

    async def _tool_check_continuity(self, args: dict[str, Any]) -> dict[str, Any]:
        """Check script continuity."""
        from .database.connection import DatabaseConnection
        from .database.continuity import ContinuityValidator

        script_id = args["script_id"]
        create_notes = args.get("create_notes", False)

        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            validator = ContinuityValidator(connection)

            issues = validator.validate_script_continuity(script_id)

            note_ids = []
            if create_notes and issues:
                note_ids = validator.create_continuity_notes_from_issues(
                    script_id, issues, "MCP Server"
                )

            # Group issues by severity
            by_severity = {"low": 0, "medium": 0, "high": 0, "critical": 0}
            for issue in issues:
                if issue.severity in by_severity:
                    by_severity[issue.severity] += 1

            return {
                "script_id": script_id,
                "total_issues": len(issues),
                "by_severity": by_severity,
                "notes_created": len(note_ids),
                "issues": [
                    {
                        "type": issue.issue_type,
                        "severity": issue.severity,
                        "title": issue.title,
                        "description": issue.description,
                    }
                    for issue in issues[:10]  # First 10 issues
                ],
            }

    async def _tool_add_character_knowledge(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Add character knowledge."""
        from .database.bible import ScriptBibleOperations
        from .database.connection import DatabaseConnection

        script_id = args["script_id"]
        character_name = args["character_name"]
        knowledge_type = args["knowledge_type"]
        knowledge_subject = args["knowledge_subject"]

        # Type narrowing after validation - we know these are strings now
        # Use runtime type checks to satisfy both mypy and linter
        if not isinstance(script_id, str):
            raise TypeError("script_id must be a string")
        if not isinstance(character_name, str):
            raise TypeError("character_name must be a string")
        if not isinstance(knowledge_type, str):
            raise TypeError("knowledge_type must be a string")
        if not isinstance(knowledge_subject, str):
            raise TypeError("knowledge_subject must be a string")

        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            # Find character by name
            char_row = connection.fetch_one(
                "SELECT id FROM characters WHERE script_id = ? AND name LIKE ?",
                (script_id, f"%{character_name}%"),
            )

            if not char_row:
                raise ValueError(f"Character '{character_name}' not found")

            character_id = char_row["id"]

            # Get optional fields
            knowledge_description = args.get("knowledge_description")
            acquired_episode = args.get("acquired_episode")
            acquisition_method = args.get("acquisition_method")

            # Handle episode lookup if provided
            acquired_episode_id = None
            if acquired_episode:
                ep_row = connection.fetch_one(
                    "SELECT id FROM episodes WHERE script_id = ? "
                    "AND (title LIKE ? OR number = ?)",
                    (script_id, f"%{acquired_episode}%", acquired_episode),
                )
                if ep_row:
                    acquired_episode_id = ep_row["id"]

            bible_ops = ScriptBibleOperations(connection)
            knowledge_id = bible_ops.add_character_knowledge(
                character_id=character_id,
                script_id=script_id,
                knowledge_type=knowledge_type,
                knowledge_subject=knowledge_subject,
                knowledge_description=knowledge_description,
                acquired_episode_id=acquired_episode_id,
                acquisition_method=acquisition_method,
            )

            return {
                "knowledge_id": knowledge_id,
                "character_id": character_id,
                "character_name": character_name,
                "knowledge_type": knowledge_type,
                "knowledge_subject": knowledge_subject,
                "created": True,
            }

    async def _tool_get_continuity_report(self, args: dict[str, Any]) -> dict[str, Any]:
        """Generate continuity report."""
        from .database.connection import DatabaseConnection
        from .database.continuity import ContinuityValidator

        script_id = args["script_id"]

        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            validator = ContinuityValidator(connection)
            report = validator.generate_continuity_report(script_id)

            # Simplify the report for MCP response
            return {
                "script_id": script_id,
                "script_title": report["script_title"],
                "is_series": report["is_series"],
                "total_issues": report["validation_results"]["issue_statistics"][
                    "total_issues"
                ],
                "by_severity": report["validation_results"]["issue_statistics"][
                    "by_severity"
                ],
                "open_notes": report["existing_notes"]["note_statistics"][
                    "by_status"
                ].get("open", 0),
                "recommendations": report["recommendations"],
            }

    async def _tool_list_mentors(
        self,
        _args: dict[str, Any],
    ) -> dict[str, Any]:
        """List all available mentors."""
        from .mentors import get_mentor_registry

        try:
            registry = get_mentor_registry()
            mentors = registry.list_mentors()

            return {
                "mentors": mentors,
                "total_count": len(mentors),
            }

        except Exception as e:
            self.logger.error("Failed to list mentors", error=str(e))
            raise ValueError(f"Failed to list mentors: {e}") from e

    async def _tool_analyze_script_with_mentor(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Analyze a script with a specific mentor."""
        from uuid import UUID

        from .database.connection import DatabaseConnection
        from .database.operations import GraphOperations
        from .mentors import MentorDatabaseOperations, get_mentor_registry

        script_id = args.get("script_id")
        mentor_name = args.get("mentor_name")
        config = args.get("config", {})
        save_results = args.get("save_results", True)

        if not script_id or not mentor_name:
            raise ValueError("script_id and mentor_name are required")

        try:
            # Get mentor
            registry = get_mentor_registry()
            if not registry.is_registered(mentor_name):
                available: list[str] = list(registry)
                raise ValueError(
                    f"Mentor '{mentor_name}' not found. Available: {available}"
                )

            mentor = registry.get_mentor(mentor_name, config)

            # Setup database operations
            db_path = Path(self.config.database.path)
            connection = DatabaseConnection(str(db_path))
            graph_ops = GraphOperations(connection)

            # Run analysis
            result = await mentor.analyze_script(
                script_id=UUID(script_id),
                db_operations=graph_ops,
                progress_callback=None,  # MCP doesn't support progress callbacks yet
            )

            # Save results if requested
            if save_results:
                mentor_db = MentorDatabaseOperations(connection)
                mentor_db.store_mentor_result(result)

            # Convert to serializable format
            return {
                "result_id": str(result.id),
                "mentor_name": result.mentor_name,
                "mentor_version": result.mentor_version,
                "script_id": str(result.script_id),
                "summary": result.summary,
                "score": result.score,
                "analysis_date": result.analysis_date.isoformat(),
                "execution_time_ms": result.execution_time_ms,
                "analyses_count": len(result.analyses),
                "error_count": result.error_count,
                "warning_count": result.warning_count,
                "suggestion_count": result.suggestion_count,
                "analyses": [
                    {
                        "id": str(analysis.id),
                        "title": analysis.title,
                        "description": analysis.description,
                        "severity": analysis.severity.value,
                        "category": analysis.category,
                        "confidence": analysis.confidence,
                        "recommendations": analysis.recommendations,
                        "scene_id": (
                            str(analysis.scene_id) if analysis.scene_id else None
                        ),
                        "character_id": (
                            str(analysis.character_id)
                            if analysis.character_id
                            else None
                        ),
                    }
                    for analysis in result.analyses
                ],
                "saved_to_database": save_results,
            }

        except Exception as e:
            self.logger.error(
                "Mentor analysis failed",
                mentor=mentor_name,
                script_id=script_id,
                error=str(e),
            )
            raise ValueError(f"Mentor analysis failed: {e}") from e

    async def _tool_get_mentor_results(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get previous mentor analysis results."""
        from uuid import UUID

        from .database.connection import DatabaseConnection
        from .mentors import MentorDatabaseOperations

        script_id = args.get("script_id")
        mentor_name = args.get("mentor_name")
        limit = args.get("limit", 10)

        if not script_id:
            raise ValueError("script_id is required")

        try:
            db_path = Path(self.config.database.path)
            connection = DatabaseConnection(str(db_path))
            mentor_db = MentorDatabaseOperations(connection)

            results = mentor_db.get_script_mentor_results(UUID(script_id), mentor_name)[
                :limit
            ]

            return {
                "script_id": script_id,
                "mentor_filter": mentor_name,
                "results_count": len(results),
                "results": [
                    {
                        "result_id": str(result.id),
                        "mentor_name": result.mentor_name,
                        "mentor_version": result.mentor_version,
                        "summary": result.summary,
                        "score": result.score,
                        "analysis_date": result.analysis_date.isoformat(),
                        "analyses_count": len(result.analyses),
                        "error_count": result.error_count,
                        "warning_count": result.warning_count,
                        "suggestion_count": result.suggestion_count,
                    }
                    for result in results
                ],
            }

        except Exception as e:
            self.logger.error(
                "Failed to get mentor results", script_id=script_id, error=str(e)
            )
            raise ValueError(f"Failed to get mentor results: {e}") from e

    async def _tool_search_mentor_analyses(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Search mentor analysis findings."""
        from .database.connection import DatabaseConnection
        from .mentors import AnalysisSeverity, MentorDatabaseOperations

        query = args.get("query")
        mentor_name = args.get("mentor_name")
        category = args.get("category")
        severity = args.get("severity")
        limit = args.get("limit", 20)

        if not query:
            raise ValueError("query is required")

        try:
            db_path = Path(self.config.database.path)
            connection = DatabaseConnection(str(db_path))
            mentor_db = MentorDatabaseOperations(connection)

            # Parse severity
            severity_enum = None
            if severity:
                severity_enum = AnalysisSeverity(severity.lower())

            results = mentor_db.search_analyses(
                query=query,
                mentor_name=mentor_name,
                category=category,
                severity=severity_enum,
                limit=limit,
            )

            return {
                "query": query,
                "filters": {
                    "mentor_name": mentor_name,
                    "category": category,
                    "severity": severity,
                },
                "results_count": len(results),
                "results": [
                    {
                        "id": str(analysis.id),
                        "title": analysis.title,
                        "description": analysis.description,
                        "severity": analysis.severity.value,
                        "category": analysis.category,
                        "mentor_name": analysis.mentor_name,
                        "confidence": analysis.confidence,
                        "recommendations": analysis.recommendations,
                        "examples": analysis.examples,
                        "scene_id": (
                            str(analysis.scene_id) if analysis.scene_id else None
                        ),
                        "character_id": (
                            str(analysis.character_id)
                            if analysis.character_id
                            else None
                        ),
                    }
                    for analysis in results
                ],
            }

        except Exception as e:
            self.logger.error(
                "Failed to search mentor analyses", query=query, error=str(e)
            )
            raise ValueError(f"Failed to search mentor analyses: {e}") from e

    async def _tool_get_mentor_statistics(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get mentor analysis statistics for a script."""
        from uuid import UUID

        from .database.connection import DatabaseConnection
        from .mentors import MentorDatabaseOperations

        script_id = args.get("script_id")

        if not script_id:
            raise ValueError("script_id is required")

        try:
            db_path = Path(self.config.database.path)
            connection = DatabaseConnection(str(db_path))
            mentor_db = MentorDatabaseOperations(connection)

            stats = mentor_db.get_mentor_statistics(UUID(script_id))

            return {
                "script_id": script_id,
                "statistics": stats,
            }

        except Exception as e:
            self.logger.error(
                "Failed to get mentor statistics", script_id=script_id, error=str(e)
            )
            raise ValueError(f"Failed to get mentor statistics: {e}") from e

    async def _handle_list_resources(
        self, _request: types.ListResourcesRequest
    ) -> types.ServerResult:
        """Handle list resources request."""
        resources = []

        # Add screenplay list resource
        resources.append(
            types.Resource(
                uri=AnyUrl("screenplay://list"),
                name="Available Screenplays",
                description="List of all parsed screenplays",
                mimeType="application/json",
            )
        )

        # Add resources for each cached script
        for script_id in self._scripts_cache:
            resources.append(
                types.Resource(
                    uri=AnyUrl(f"screenplay://{script_id}"),
                    name=f"Screenplay: {self._scripts_cache[script_id].title}",
                    description="Full screenplay structure and metadata",
                    mimeType="application/json",
                )
            )

        return types.ServerResult(types.ListResourcesResult(resources=resources))

    async def _handle_read_resource(
        self, request: types.ReadResourceRequest
    ) -> types.ServerResult:
        """Handle read resource request."""
        uri = request.params.uri
        uri_str = str(uri)

        if uri_str == "screenplay://list":
            # Return list of all scripts
            scripts = []
            for script_id, script in self._scripts_cache.items():
                scripts.append(
                    {
                        "script_id": script_id,
                        "title": script.title,
                        "source_file": script.source_file,
                    }
                )
            content = json.dumps({"scripts": scripts}, indent=2)

        elif uri_str.startswith("screenplay://"):
            # Return specific script
            script_id = uri_str.replace("screenplay://", "")
            if script_id not in self._scripts_cache:
                raise ValueError(f"Script not found: {script_id}")

            script = self._scripts_cache[script_id]

            # Fetch scenes for this script
            scenes_data = []
            characters_data = {}  # Use dict to track unique characters

            from .database.connection import DatabaseConnection

            db_path = str(self.config.get_database_path())
            with (
                DatabaseConnection(db_path) as connection,
                connection.get_connection() as conn,
            ):
                # Query scenes for this script
                cursor = conn.execute(
                    """
                    SELECT
                        s.id, s.heading, s.description, s.script_order,
                        s.temporal_order, s.logical_order, s.time_of_day,
                        s.date_in_story, s.estimated_duration_minutes,
                        l.name as location_name, l.interior
                    FROM scenes s
                    LEFT JOIN locations l ON s.location_id = l.id
                    WHERE s.script_id = ?
                    ORDER BY s.script_order
                """,
                    (script_id,),
                )

                for row in cursor:
                    scene_data = {
                        "id": row["id"],
                        "heading": row["heading"],
                        "description": row["description"],
                        "script_order": row["script_order"],
                        "temporal_order": row["temporal_order"],
                        "logical_order": row["logical_order"],
                        "time_of_day": row["time_of_day"],
                        "date_in_story": row["date_in_story"],
                        "duration_minutes": row["estimated_duration_minutes"],
                        "location": {
                            "name": row["location_name"],
                            "interior": (
                                bool(row["interior"])
                                if row["interior"] is not None
                                else None
                            ),
                        }
                        if row["location_name"]
                        else None,
                        "characters": [],
                        "dialogue_count": 0,
                    }

                    # Get characters in this scene
                    char_cursor = conn.execute(
                        """
                            SELECT DISTINCT
                                c.id, c.name, c.description,
                                COUNT(DISTINCT se.id) as dialogue_count
                            FROM scene_elements se
                            JOIN characters c ON se.character_id = c.id
                            WHERE se.scene_id = ? AND se.element_type = 'dialogue'
                            GROUP BY c.id, c.name, c.description
                        """,
                        (row["id"],),
                    )

                    for char_row in char_cursor:
                        scene_data["characters"].append(
                            {
                                "id": char_row["id"],
                                "name": char_row["name"],
                                "dialogue_count": char_row["dialogue_count"],
                            }
                        )
                        scene_data["dialogue_count"] += char_row["dialogue_count"]

                        # Track character for overall stats
                        if char_row["id"] not in characters_data:
                            characters_data[char_row["id"]] = {
                                "id": char_row["id"],
                                "name": char_row["name"],
                                "description": char_row["description"],
                                "scene_count": 0,
                                "dialogue_count": 0,
                                "scenes": [],
                            }

                        characters_data[char_row["id"]]["scene_count"] += 1
                        characters_data[char_row["id"]]["dialogue_count"] += char_row[
                            "dialogue_count"
                        ]
                        characters_data[char_row["id"]]["scenes"].append(row["id"])

                    scenes_data.append(scene_data)

                # Get scene dependencies/relationships
                for scene in scenes_data:
                    dep_cursor = conn.execute(
                        """
                            SELECT
                            sd.to_scene_id, sd.dependency_type,
                            sd.description, sd.strength,
                            s.heading as to_scene_heading
                            FROM scene_dependencies sd
                            JOIN scenes s ON sd.to_scene_id = s.id
                            WHERE sd.from_scene_id = ?
                        """,
                        (scene["id"],),
                    )

                    scene["relationships"] = []
                    for dep_row in dep_cursor:
                        scene["relationships"].append(
                            {
                                "to_scene_id": dep_row["to_scene_id"],
                                "type": dep_row["dependency_type"],
                                "description": dep_row["description"],
                                "strength": dep_row["strength"],
                                "to_scene_heading": dep_row["to_scene_heading"],
                            }
                        )

                # Get character profiles if they exist
                for char_id in characters_data:
                    profile_cursor = conn.execute(
                        """
                            SELECT
                            full_name, age, occupation, background,
                            personality_traits, motivations, fears, goals,
                            physical_description, character_arc
                            FROM character_profiles
                            WHERE character_id = ? AND script_id = ?
                        """,
                        (char_id, script_id),
                    )

                    profile_row = profile_cursor.fetchone()
                    if profile_row:
                        characters_data[char_id].update(
                            {
                                "full_name": profile_row["full_name"],
                                "age": profile_row["age"],
                                "occupation": profile_row["occupation"],
                                "background": profile_row["background"],
                                "personality_traits": profile_row["personality_traits"],
                                "motivations": profile_row["motivations"],
                                "fears": profile_row["fears"],
                                "goals": profile_row["goals"],
                                "physical_description": profile_row[
                                    "physical_description"
                                ],
                                "character_arc": profile_row["character_arc"],
                            }
                        )

                # Get character relationships
                for char_id in characters_data:
                    # Get edges where this character interacts with others
                    rel_cursor = conn.execute(
                        """
                            SELECT DISTINCT
                                e.to_node_id, e.edge_type, e.weight,
                                c2.name as other_character_name,
                                COUNT(DISTINCT se1.scene_id) as shared_scenes
                            FROM nodes n1
                            JOIN edges e ON n1.id = e.from_node_id
                            JOIN nodes n2 ON e.to_node_id = n2.id
                            JOIN characters c1 ON n1.entity_id = c1.id
                            JOIN characters c2 ON n2.entity_id = c2.id
                            LEFT JOIN scene_elements se1 ON se1.character_id = c1.id
                            LEFT JOIN scene_elements se2 ON se2.character_id = c2.id
                                AND se1.scene_id = se2.scene_id
                            WHERE n1.node_type = 'character'
                                AND n2.node_type = 'character'
                                AND c1.id = ?
                                AND e.edge_type IN (
                                    'INTERACTS_WITH', 'SPEAKS_TO', 'RELATED_TO'
                                )
                            GROUP BY e.to_node_id, e.edge_type, e.weight, c2.name
                        """,
                        (char_id,),
                    )

                    relationships = []
                    for rel_row in rel_cursor:
                        relationships.append(
                            {
                                "character_name": rel_row["other_character_name"],
                                "relationship_type": rel_row["edge_type"],
                                "strength": rel_row["weight"],
                                "shared_scenes": rel_row["shared_scenes"],
                            }
                        )

                    if relationships:
                        characters_data[char_id]["relationships"] = relationships

            # Convert characters dict to sorted list
            characters_list = sorted(
                characters_data.values(),
                key=lambda x: x["dialogue_count"],
                reverse=True,
            )

            # Get plot threads and story arcs
            plot_threads = []
            with connection.get_connection() as conn:
                thread_cursor = conn.execute(
                    """
                    SELECT
                        id, name, thread_type, priority, description,
                        status, introduced_episode_id, resolved_episode_id,
                        primary_characters_json, key_scenes_json
                    FROM plot_threads
                    WHERE script_id = ? AND status IN ('active', 'resolved')
                    ORDER BY priority DESC, name
                """,
                    (script_id,),
                )

                for thread_row in thread_cursor:
                    plot_threads.append(
                        {
                            "id": thread_row["id"],
                            "name": thread_row["name"],
                            "type": thread_row["thread_type"],
                            "priority": thread_row["priority"],
                            "description": thread_row["description"],
                            "status": thread_row["status"],
                            "primary_characters": json.loads(
                                thread_row["primary_characters_json"] or "[]"
                            ),
                            "key_scenes": json.loads(
                                thread_row["key_scenes_json"] or "[]"
                            ),
                        }
                    )

            # Create scene timeline with grouping
            timeline: dict[str, Any] = {
                "chronological": [],  # Scenes by temporal order
                "by_location": {},  # Scenes grouped by location
                "by_act": {  # Traditional three-act structure
                    "act_1": [],
                    "act_2": [],
                    "act_3": [],
                },
            }

            # Group scenes for timeline
            for scene in scenes_data:
                # Chronological timeline
                timeline["chronological"].append(
                    {
                        "scene_id": scene["id"],
                        "heading": scene["heading"],
                        "order": scene["temporal_order"] or scene["script_order"],
                        "time_of_day": scene["time_of_day"],
                        "date_in_story": scene["date_in_story"],
                    }
                )

                # By location
                if scene["location"]:
                    loc_name = scene["location"]["name"]
                    if loc_name not in timeline["by_location"]:
                        timeline["by_location"][loc_name] = []
                    timeline["by_location"][loc_name].append(scene["id"])

                # By act (rough approximation based on script position)
                total_scenes = len(scenes_data)
                if scene["script_order"] <= total_scenes * 0.25:
                    timeline["by_act"]["act_1"].append(scene["id"])
                elif scene["script_order"] <= total_scenes * 0.75:
                    timeline["by_act"]["act_2"].append(scene["id"])
                else:
                    timeline["by_act"]["act_3"].append(scene["id"])

            # Sort chronological timeline
            timeline["chronological"].sort(key=lambda x: x["order"])

            content = json.dumps(
                {
                    "script_id": script_id,
                    "title": script.title,
                    "source_file": script.source_file,
                    "scenes": scenes_data,
                    "characters": characters_list,
                    "plot_threads": plot_threads,
                    "timeline": timeline,
                    "stats": {
                        "total_scenes": len(scenes_data),
                        "total_characters": len(characters_list),
                        "total_dialogue": sum(s["dialogue_count"] for s in scenes_data),
                        "estimated_runtime_minutes": sum(
                            s["duration_minutes"] or 0 for s in scenes_data
                        ),
                        "locations": len(timeline["by_location"]),
                        "active_plot_threads": len(
                            [t for t in plot_threads if t["status"] == "active"]
                        ),
                    },
                },
                indent=2,
            )

        else:
            raise ValueError(f"Unknown resource URI: {uri_str}")

        return types.ServerResult(
            types.ReadResourceResult(
                contents=[
                    types.TextResourceContents(
                        uri=uri, mimeType="application/json", text=content
                    )
                ]
            )
        )

    async def _handle_list_prompts(
        self, _request: types.ListPromptsRequest
    ) -> types.ServerResult:
        """Handle list prompts request."""
        prompts = [
            types.Prompt(
                name="analyze_script_structure",
                description="Analyze the three-act structure of a screenplay",
                arguments=[
                    types.PromptArgument(
                        name="script_id",
                        description="ID of the script to analyze",
                        required=True,
                    )
                ],
            ),
            types.Prompt(
                name="character_arc_analysis",
                description="Analyze a character's arc throughout the screenplay",
                arguments=[
                    types.PromptArgument(
                        name="script_id",
                        description="ID of the script",
                        required=True,
                    ),
                    types.PromptArgument(
                        name="character_name",
                        description="Name of the character to analyze",
                        required=True,
                    ),
                ],
            ),
            types.Prompt(
                name="scene_improvement_suggestions",
                description="Get suggestions for improving a specific scene",
                arguments=[
                    types.PromptArgument(
                        name="script_id",
                        description="ID of the script",
                        required=True,
                    ),
                    types.PromptArgument(
                        name="scene_number",
                        description="Scene number to analyze",
                        required=True,
                    ),
                ],
            ),
        ]

        return types.ServerResult(types.ListPromptsResult(prompts=prompts))

    async def _handle_get_prompt(
        self, request: types.GetPromptRequest
    ) -> types.ServerResult:
        """Handle get prompt request."""
        prompt_name = request.params.name
        arguments = request.params.arguments or {}

        if prompt_name == "analyze_script_structure":
            script_id = arguments.get("script_id", "<script_id>")
            messages = [
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=(
                            f"Please analyze the three-act structure of the screenplay "
                            f"with ID {script_id}. Identify the key plot points, "
                            "turning points, and how well the script follows "
                            "traditional screenplay structure."
                        ),
                    ),
                )
            ]

        elif prompt_name == "character_arc_analysis":
            script_id = arguments.get("script_id", "<script_id>")
            character_name = arguments.get("character_name", "<character_name>")
            messages = [
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=(
                            f"Analyze the character arc of {character_name} in "
                            f"script {script_id}. Examine their journey, growth, "
                            "conflicts, and relationships throughout the story."
                        ),
                    ),
                )
            ]

        elif prompt_name == "scene_improvement_suggestions":
            script_id = arguments.get("script_id", "<script_id>")
            scene_number = arguments.get("scene_number", "<scene_number>")
            messages = [
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=(
                            f"Provide specific suggestions for improving scene "
                            f"{scene_number} in script {script_id}. Consider pacing, "
                            "dialogue, character motivation, and visual storytelling."
                        ),
                    ),
                )
            ]

        else:
            raise ValueError(f"Unknown prompt: {prompt_name}")

        return types.ServerResult(
            types.GetPromptResult(
                description=f"Prompt for {prompt_name}",
                messages=messages,
            )
        )


async def run_server(
    config: ScriptRAGSettings | None = None,
    config_file: Path | None = None,
) -> None:
    """Run the MCP server.

    Args:
        config: ScriptRAG configuration
        config_file: Path to configuration file
    """
    # Load configuration
    if config:
        settings = config
    elif config_file:
        settings = load_settings(config_file)
    else:
        settings = get_settings()

    # Set up logging
    setup_logging_for_environment(
        environment=settings.environment,
        log_file=settings.get_log_file_path(),
    )

    logger = get_logger(__name__)

    server = None
    try:
        # Create and start server
        server = ScriptRAGMCPServer(settings)
        await server.start()

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error("MCP server error", error=str(e), exc_info=True)
        raise
    finally:
        if server is not None:
            await server.stop()


def main(
    config_file: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Main entry point for the MCP server.

    Args:
        config_file: Path to configuration file
        host: Override server host
        port: Override server port
    """
    logger = get_logger(__name__)

    try:
        # Load settings
        settings = load_settings(Path(config_file)) if config_file else get_settings()

        # Apply command line overrides
        if host:
            settings.mcp.host = host
        if port:
            settings.mcp.port = port

        # Run the server
        asyncio.run(run_server(config=settings))

    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error("Error starting MCP server", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
