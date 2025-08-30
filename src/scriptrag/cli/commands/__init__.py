"""ScriptRAG CLI commands."""

from __future__ import annotations

from scriptrag.cli.commands.analyze import analyze_command
from scriptrag.cli.commands.index import index_command
from scriptrag.cli.commands.init import init_command
from scriptrag.cli.commands.list import list_command
from scriptrag.cli.commands.mcp import mcp_command
from scriptrag.cli.commands.pull import pull_command
from scriptrag.cli.commands.query import create_query_app, get_query_app
from scriptrag.cli.commands.search import search_command
from scriptrag.cli.commands.watch import watch_command

__all__ = [
    "analyze_command",
    "create_query_app",
    "get_query_app",
    "index_command",
    "init_command",
    "list_command",
    "mcp_command",
    "pull_command",
    "search_command",
    "watch_command",
]
