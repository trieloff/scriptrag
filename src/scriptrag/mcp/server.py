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
        return [
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
            }

            if tool_name not in tool_handlers:
                raise ValueError(f"Unknown tool: {tool_name}")

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
            raise ValueError(f"Unknown resource scheme: {uri}")

        parts = uri.replace("scriptrag://", "").split("/")

        if len(parts) < 2:
            raise ValueError(f"Invalid resource URI: {uri}")

        resource_type = parts[0]
        script_id = parts[1]

        if resource_type == "scripts":
            if script_id not in self._scripts_cache:
                raise ValueError(f"Script not found: {script_id}")

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

        raise ValueError(f"Unknown resource type: {resource_type}")

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
                raise ValueError(f"Script not found: {script_id}")

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

        raise ValueError(f"Unknown prompt: {prompt_name}")
