"""Custom exceptions for MCP server."""


class MCPError(Exception):
    """Base exception for MCP-related errors."""

    pass


class ScriptNotFoundError(MCPError):
    """Raised when a script is not found in cache."""

    pass


class InvalidArgumentError(MCPError):
    """Raised when invalid arguments are provided to a tool."""

    pass


class ToolExecutionError(MCPError):
    """Raised when a tool fails to execute properly."""

    pass


class ResourceNotFoundError(MCPError):
    """Raised when a requested resource is not found."""

    pass


class PromptNotFoundError(MCPError):
    """Raised when a requested prompt is not found."""

    pass
