"""MCP resource implementations for ScriptRAG."""

# Resources are registered when their modules are imported
from scriptrag.mcp.resources import characters, scenes, scripts

__all__ = ["characters", "scenes", "scripts"]
