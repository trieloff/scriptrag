"""ScriptRAG CLI commands."""

from scriptrag.cli.commands.analyze import analyze_command
from scriptrag.cli.commands.index import index_command
from scriptrag.cli.commands.init import init_command
from scriptrag.cli.commands.list import list_command
from scriptrag.cli.commands.pull import pull_command
from scriptrag.cli.commands.query import query_app
from scriptrag.cli.commands.search import search_command
from scriptrag.cli.commands.watch import watch_command

__all__ = [
    "analyze_command",
    "index_command",
    "init_command",
    "list_command",
    "pull_command",
    "query_app",
    "search_command",
    "watch_command",
]
