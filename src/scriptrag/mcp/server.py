"""MCP (Model Context Protocol) server for ScriptRAG."""

import json
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl

from scriptrag import ScriptRAG
from scriptrag.config import (
    ScriptRAGSettings,
    get_logger,
)
from scriptrag.models import Script

# Import custom exceptions
from .exceptions import (
    InvalidArgumentError,
    PromptNotFoundError,
    ResourceNotFoundError,
    ScriptNotFoundError,
)

# Import tool modules
from .tools_analysis import AnalysisTools
from .tools_bible import BibleTools
from .tools_character import CharacterTools
from .tools_mentor import MentorTools
from .tools_scene import SceneTools
from .tools_script import ScriptTools


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

        # Initialize tool modules
        self._script_tools = ScriptTools(self)
        self._scene_tools = SceneTools(self)
        self._character_tools = CharacterTools(self)
        self._analysis_tools = AnalysisTools(self)
        self._bible_tools = BibleTools(self)
        self._mentor_tools = MentorTools(self)

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
        from scriptrag import __version__

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
            ScriptNotFoundError: If script_id not found in cache
        """
        if script_id not in self._scripts_cache:
            raise ScriptNotFoundError(f"Script not found: {script_id}")
        return self._scripts_cache[script_id]

    def get_available_tools(self) -> list[dict[str, Any]]:
        """Get list of available MCP tools.

        Returns:
            List of tool definitions
        """
        all_tools = [
            # Script tools
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
                "name": "list_scripts",
                "description": "List all parsed scripts in cache",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "export_data",
                "description": "Export script data in various formats",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "ID of the script to export",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["json", "csv", "markdown"],
                            "description": "Export format",
                        },
                        "include_analysis": {
                            "type": "boolean",
                            "description": "Include analysis data",
                            "default": False,
                        },
                    },
                    "required": ["script_id", "format"],
                },
            },
            # Scene tools
            {
                "name": "search_scenes",
                "description": "Search for scenes in parsed scripts",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Optional script ID to search within",
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "location": {
                            "type": "string",
                            "description": "Filter by location",
                        },
                        "character": {
                            "type": "string",
                            "description": "Filter by character",
                        },
                        "time_of_day": {
                            "type": "string",
                            "description": "Filter by time of day",
                        },
                        "act": {
                            "type": "integer",
                            "description": "Filter by act number",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results",
                            "default": 10,
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "get_scene_details",
                "description": "Get detailed information about a specific scene",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID",
                        },
                        "scene_number": {
                            "type": "integer",
                            "description": "Scene number",
                        },
                        "include_dialogue": {
                            "type": "boolean",
                            "description": "Include full dialogue",
                            "default": True,
                        },
                        "include_actions": {
                            "type": "boolean",
                            "description": "Include action lines",
                            "default": True,
                        },
                    },
                    "required": ["script_id", "scene_number"],
                },
            },
            {
                "name": "update_scene",
                "description": "Update scene information",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID",
                        },
                        "scene_number": {
                            "type": "integer",
                            "description": "Scene number",
                        },
                        "updates": {
                            "type": "object",
                            "description": "Fields to update",
                        },
                    },
                    "required": ["script_id", "scene_number", "updates"],
                },
            },
            {
                "name": "delete_scene",
                "description": "Delete a scene from script",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID",
                        },
                        "scene_number": {
                            "type": "integer",
                            "description": "Scene number",
                        },
                    },
                    "required": ["script_id", "scene_number"],
                },
            },
            {
                "name": "inject_scene",
                "description": "Inject a new scene into script",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID",
                        },
                        "after_scene": {
                            "type": "integer",
                            "description": "Scene number to inject after",
                        },
                        "scene_data": {
                            "type": "object",
                            "description": "New scene data",
                        },
                    },
                    "required": ["script_id", "after_scene", "scene_data"],
                },
            },
            # Character tools
            {
                "name": "get_character_info",
                "description": "Get information about a character",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID",
                        },
                        "character_name": {
                            "type": "string",
                            "description": "Character name",
                        },
                        "include_scenes": {
                            "type": "boolean",
                            "description": "Include scene appearances",
                            "default": True,
                        },
                        "include_dialogue": {
                            "type": "boolean",
                            "description": "Include dialogue samples",
                            "default": True,
                        },
                        "include_relationships": {
                            "type": "boolean",
                            "description": "Include relationships",
                            "default": True,
                        },
                    },
                    "required": ["script_id", "character_name"],
                },
            },
            {
                "name": "get_character_relationships",
                "description": "Analyze relationships between characters",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID",
                        },
                        "character1": {
                            "type": "string",
                            "description": "First character",
                        },
                        "character2": {
                            "type": "string",
                            "description": "Second character (optional)",
                        },
                    },
                    "required": ["script_id", "character1"],
                },
            },
            # Analysis tools
            {
                "name": "analyze_timeline",
                "description": "Analyze script timeline and temporal flow",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID",
                        },
                    },
                    "required": ["script_id"],
                },
            },
            {
                "name": "check_continuity",
                "description": "Check script for continuity issues",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID",
                        },
                        "check_temporal": {
                            "type": "boolean",
                            "description": "Check temporal continuity",
                            "default": True,
                        },
                        "check_spatial": {
                            "type": "boolean",
                            "description": "Check spatial continuity",
                            "default": True,
                        },
                        "check_character": {
                            "type": "boolean",
                            "description": "Check character continuity",
                            "default": True,
                        },
                        "check_props": {
                            "type": "boolean",
                            "description": "Check prop continuity",
                            "default": True,
                        },
                    },
                    "required": ["script_id"],
                },
            },
            {
                "name": "get_continuity_report",
                "description": "Get detailed continuity report",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID",
                        },
                    },
                    "required": ["script_id"],
                },
            },
            # Bible tools
            {
                "name": "create_series_bible",
                "description": "Create a series bible document",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Script IDs to include",
                        },
                        "title": {
                            "type": "string",
                            "description": "Series title",
                        },
                        "description": {
                            "type": "string",
                            "description": "Series description",
                        },
                    },
                    "required": ["script_ids", "title"],
                },
            },
            {
                "name": "create_character_profile",
                "description": "Create detailed character profile",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID",
                        },
                        "character_name": {
                            "type": "string",
                            "description": "Character name",
                        },
                        "profile_data": {
                            "type": "object",
                            "description": "Profile information",
                        },
                    },
                    "required": ["script_id", "character_name"],
                },
            },
            {
                "name": "add_world_element",
                "description": "Add world-building element to bible",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "bible_id": {
                            "type": "string",
                            "description": "Bible ID",
                        },
                        "element_type": {
                            "type": "string",
                            "enum": ["location", "prop", "rule", "history"],
                            "description": "Type of world element",
                        },
                        "element_data": {
                            "type": "object",
                            "description": "Element details",
                        },
                    },
                    "required": ["bible_id", "element_type", "element_data"],
                },
            },
            {
                "name": "create_timeline_event",
                "description": "Add timeline event to bible",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "bible_id": {
                            "type": "string",
                            "description": "Bible ID",
                        },
                        "event_data": {
                            "type": "object",
                            "description": "Event details",
                        },
                    },
                    "required": ["bible_id", "event_data"],
                },
            },
            {
                "name": "add_character_knowledge",
                "description": "Track what characters know",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "bible_id": {
                            "type": "string",
                            "description": "Bible ID",
                        },
                        "character_name": {
                            "type": "string",
                            "description": "Character name",
                        },
                        "knowledge_item": {
                            "type": "object",
                            "description": "Knowledge details",
                        },
                    },
                    "required": ["bible_id", "character_name", "knowledge_item"],
                },
            },
            # Mentor tools
            {
                "name": "list_mentors",
                "description": "List available screenplay mentors",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "analyze_script_with_mentor",
                "description": "Analyze script with specific mentor perspective",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID",
                        },
                        "mentor_id": {
                            "type": "string",
                            "description": "Mentor ID",
                        },
                        "focus_areas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Areas to focus on",
                        },
                    },
                    "required": ["script_id", "mentor_id"],
                },
            },
            {
                "name": "get_mentor_results",
                "description": "Get mentor analysis results",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "analysis_id": {
                            "type": "string",
                            "description": "Analysis ID",
                        },
                    },
                    "required": ["analysis_id"],
                },
            },
            {
                "name": "search_mentor_analyses",
                "description": "Search through mentor analyses",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Filter by script",
                        },
                        "mentor_id": {
                            "type": "string",
                            "description": "Filter by mentor",
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "get_mentor_statistics",
                "description": "Get statistics about mentor analyses",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "script_id": {
                            "type": "string",
                            "description": "Script ID",
                        },
                    },
                    "required": [],
                },
            },
        ]

        # Apply filtering if not all tools are enabled
        if not self.config.mcp.enable_all_tools:
            enabled_tools = self.config.mcp.enabled_tools or []
            all_tools = [tool for tool in all_tools if tool["name"] in enabled_tools]

        return all_tools

    def get_available_resources(self) -> list[dict[str, Any]]:
        """Get list of available MCP resources.

        Returns:
            List of resource definitions
        """
        return [
            {
                "uri": "screenplay://list",
                "name": "List Parsed Scripts",
                "description": "List all parsed scripts",
                "mimeType": "application/json",
            },
            {
                "uri": "screenplay://{script_id}",
                "name": "Script Details",
                "description": "Get details about a specific script",
                "mimeType": "application/json",
            },
            {
                "uri": "scene://{script_id}/{scene_id}",
                "name": "Scene Details",
                "description": "Get details about a specific scene",
                "mimeType": "application/json",
            },
            {
                "uri": "character://{script_id}/{character_name}",
                "name": "Character Details",
                "description": "Get details about a specific character",
                "mimeType": "application/json",
            },
            {
                "uri": "timeline://{script_id}",
                "name": "Script Timeline",
                "description": "Get timeline information for a script",
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
                # Script tools
                "parse_script": self._script_tools.parse_fountain,
                "list_scripts": self._script_tools.list_scripts,
                "export_data": self._script_tools.export_data,
                # Scene tools
                "search_scenes": self._scene_tools.search_scenes,
                "get_scene_details": self._scene_tools.get_scene_details,
                "update_scene": self._scene_tools.update_scene,
                "delete_scene": self._scene_tools.delete_scene,
                "inject_scene": self._scene_tools.inject_scene,
                # Character tools
                "get_character_info": self._character_tools.get_character_info,
                "get_character_relationships": (
                    self._character_tools.get_character_relationships
                ),
                # Analysis tools
                "analyze_timeline": self._analysis_tools.analyze_timeline,
                "check_continuity": self._analysis_tools.check_continuity,
                "get_continuity_report": self._analysis_tools.get_continuity_report,
                # Bible tools
                "create_series_bible": self._bible_tools.create_series_bible,
                "create_character_profile": self._bible_tools.create_character_profile,
                "add_world_element": self._bible_tools.add_world_element,
                "create_timeline_event": self._bible_tools.create_timeline_event,
                "add_character_knowledge": self._bible_tools.add_character_knowledge,
                # Mentor tools
                "list_mentors": self._mentor_tools.list_mentors,
                "analyze_script_with_mentor": (
                    self._mentor_tools.analyze_script_with_mentor
                ),
                "get_mentor_results": self._mentor_tools.get_mentor_results,
                "search_mentor_analyses": self._mentor_tools.search_mentor_analyses,
                "get_mentor_statistics": self._mentor_tools.get_mentor_statistics,
            }

            if tool_name not in tool_handlers:
                raise InvalidArgumentError(f"Unknown tool: {tool_name}")

            result = await tool_handlers[tool_name](arguments)

            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=json.dumps(result, indent=2),
                        )
                    ]
                )
            )

        except Exception as e:
            self.logger.error(
                "Tool call failed",
                tool=tool_name,
                error=str(e),
                exc_info=True,
            )
            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "error": str(e),
                                    "tool": tool_name,
                                }
                            ),
                        )
                    ],
                    isError=True,
                )
            )

    async def _handle_list_resources(
        self, _request: types.ListResourcesRequest
    ) -> types.ServerResult:
        """Handle list resources request."""
        resources = []

        # Add parsed scripts as resources
        for script_id, script in self._scripts_cache.items():
            resources.append(
                types.Resource(
                    uri=AnyUrl(f"scriptrag://scripts/{script_id}"),
                    name=script.title,
                    description=(
                        f"Script by {script.author or 'Unknown'} "
                        f"({len(script.scenes)} scenes)"
                    ),
                    mimeType="application/json",
                )
            )

        return types.ServerResult(types.ListResourcesResult(resources=resources))

    async def _handle_read_resource(
        self, request: types.ReadResourceRequest
    ) -> types.ServerResult:
        """Handle read resource request."""
        uri = str(request.params.uri)

        if not uri.startswith("scriptrag://"):
            raise InvalidArgumentError(f"Unknown resource scheme: {uri}")

        parts = uri.replace("scriptrag://", "").split("/")

        if len(parts) < 2:
            raise InvalidArgumentError(f"Invalid resource URI: {uri}")

        resource_type = parts[0]
        script_id = parts[1]

        if resource_type == "scripts":
            if script_id not in self._scripts_cache:
                raise ScriptNotFoundError(f"Script not found: {script_id}")

            script = self._scripts_cache[script_id]

            content: dict[str, Any] = {
                "title": script.title,
                "author": script.author,
                "scene_count": len(script.scenes),
                "character_count": len(script.characters),
            }

            return types.ServerResult(
                types.ReadResourceResult(
                    contents=[
                        types.TextContent(
                            type="text",
                            text=json.dumps(content, indent=2),
                        )
                    ]
                )
            )

        raise ResourceNotFoundError(f"Unknown resource type: {resource_type}")

    def get_available_prompts(self) -> list[dict[str, Any]]:
        """Get list of available MCP prompts.

        Returns:
            List of prompt definitions
        """
        return [
            {
                "name": "analyze_structure",
                "description": "Analyze the structure of a screenplay",
                "arguments": [
                    {
                        "name": "script_id",
                        "description": "ID of the script to analyze",
                        "required": True,
                    }
                ],
            },
        ]

    async def _handle_list_prompts(
        self, _request: types.ListPromptsRequest
    ) -> types.ServerResult:
        """Handle list prompts request."""
        prompts = self.get_available_prompts()
        return types.ServerResult(
            types.ListPromptsResult(
                prompts=[
                    types.Prompt(
                        name=prompt["name"],
                        description=prompt["description"],
                        arguments=[
                            types.PromptArgument(
                                name=arg["name"],
                                description=arg["description"],
                                required=arg["required"],
                            )
                            for arg in prompt["arguments"]
                        ],
                    )
                    for prompt in prompts
                ]
            )
        )

    async def _handle_get_prompt(
        self, request: types.GetPromptRequest
    ) -> types.ServerResult:
        """Handle get prompt request."""
        prompt_name = request.params.name
        arguments = request.params.arguments or {}

        if prompt_name == "analyze_structure":
            script_id = arguments.get("script_id")
            if not script_id or script_id not in self._scripts_cache:
                raise ScriptNotFoundError(f"Script not found: {script_id}")

            script = self._scripts_cache[script_id]
            prompt = f'Analyze the structure of the screenplay "{script.title}".'

            return types.ServerResult(
                types.GetPromptResult(
                    messages=[
                        types.PromptMessage(
                            role="user",
                            content=types.TextContent(
                                type="text",
                                text=prompt,
                            ),
                        )
                    ]
                )
            )

        raise PromptNotFoundError(f"Unknown prompt: {prompt_name}")
