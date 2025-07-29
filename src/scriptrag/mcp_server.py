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
        _ = args.get("limit", 10)  # Will be used when search is implemented

        # For now, return mock data
        # TODO: Implement actual search when database is ready
        return {
            "script_id": script_id,
            "results": [],
            "total_matches": 0,
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

        # TODO: Implement when character analysis is ready
        return {
            "script_id": script_id,
            "character_name": character_name,
            "scenes_count": 0,
            "dialogue_lines": 0,
            "relationships": [],
        }

    async def _tool_analyze_timeline(self, args: dict[str, Any]) -> dict[str, Any]:
        """Analyze script timeline."""
        script_id = args.get("script_id")
        if not script_id:
            raise ValueError("script_id is required")

        # Validate script exists
        _ = self._validate_script_id(script_id)

        include_flashbacks = args.get("include_flashbacks", True)

        # TODO: Implement timeline analysis
        return {
            "script_id": script_id,
            "timeline_type": "linear",
            "flashbacks_detected": 0 if include_flashbacks else None,
            "time_periods": [],
        }

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

        # TODO: Implement actual scene update when database is ready
        return {
            "script_id": script_id,
            "scene_id": scene_id,
            "updated": True,
            "changes": {
                "heading": args.get("heading"),
                "action": args.get("action"),
                "dialogue": args.get("dialogue"),
            },
        }

    async def _tool_delete_scene(self, args: dict[str, Any]) -> dict[str, Any]:
        """Delete a scene."""
        script_id = args.get("script_id")
        scene_id = args.get("scene_id")

        if not script_id or scene_id is None:
            raise ValueError("script_id and scene_id are required")

        # TODO: Implement actual scene deletion when database is ready
        return {
            "script_id": script_id,
            "scene_id": scene_id,
            "deleted": True,
        }

    async def _tool_inject_scene(self, args: dict[str, Any]) -> dict[str, Any]:
        """Inject a new scene."""
        script_id = args.get("script_id")
        position = args.get("position")
        heading = args.get("heading")

        if not script_id or position is None or not heading:
            raise ValueError("script_id, position, and heading are required")

        # TODO: Implement actual scene injection when database is ready
        return {
            "script_id": script_id,
            "scene_id": f"scene_{position}",
            "position": position,
            "heading": heading,
            "injected": True,
        }

    async def _tool_get_scene_details(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get scene details."""
        script_id = args.get("script_id")
        scene_id = args.get("scene_id")

        if not script_id or scene_id is None:
            raise ValueError("script_id and scene_id are required")

        # TODO: Implement when scene data is available
        return {
            "script_id": script_id,
            "scene_id": scene_id,
            "heading": "INT. LOCATION - DAY",
            "action": "Scene action goes here.",
            "dialogue": [],
            "characters": [],
            "page_number": 1,
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
            content = json.dumps(
                {
                    "script_id": script_id,
                    "title": script.title,
                    "source_file": script.source_file,
                    "scenes": [],  # TODO: Add scene data when available
                    "characters": [],  # TODO: Add character data
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
