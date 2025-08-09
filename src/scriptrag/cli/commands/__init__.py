"""ScriptRAG CLI commands."""

# Re-export command functions for convenient imports
from scriptrag.cli.commands.analyze import analyze_command
from scriptrag.cli.commands.index import index_command
from scriptrag.cli.commands.init import init_command
from scriptrag.cli.commands.list import list_command
from scriptrag.cli.commands.search import search_command

# Also expose submodules for tests and star-import ergonomics
from . import analyze, index, init, list, search  # noqa: F401, A004

__all__ = [
    "analyze_command",
    "index_command",
    "init_command",
    "list_command",
    "search_command",
]
