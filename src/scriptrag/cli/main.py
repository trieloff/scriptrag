"""ScriptRAG Command Line Interface."""

from pathlib import Path
from typing import Annotated

import typer

from scriptrag.cli.commands import (
    analyze_command,
    index_command,
    init_command,
    list_command,
    pull_command,
    query_app,
    search_command,
    watch_command,
)
from scriptrag.cli.commands.mcp import mcp_command
from scriptrag.cli.commands.scene import scene_app

app = typer.Typer(
    name="scriptrag",
    help="ScriptRAG: A Graph-Based Screenwriting Assistant",
    pretty_exceptions_enable=False,
    add_completion=False,
)


@app.callback()
def main_callback(
    ctx: typer.Context,
    db_path: Annotated[
        Path | None,
        typer.Option(
            "--db-path",
            help="Path to the SQLite database file (overrides default)",
            envvar="SCRIPTRAG_DATABASE_PATH",
        ),
    ] = None,
) -> None:
    """ScriptRAG CLI with global database path option."""
    # Store the db_path in context for all commands to access
    if ctx.obj is None:
        ctx.obj = {}
    if db_path is not None:
        ctx.obj["db_path"] = db_path


# Register commands
app.command(name="init")(init_command)
app.command(name="list")(list_command)
app.command(name="ls", hidden=True)(list_command)  # Alias for list
app.command(name="analyze")(analyze_command)
app.command(name="index")(index_command)
app.command(name="pull")(pull_command)
app.command(name="search")(search_command)
app.command(name="watch")(watch_command)
app.command(name="mcp")(mcp_command)

# Register query subapp
app.add_typer(query_app, name="query")

# Register scene subapp
app.add_typer(scene_app, name="scene")


def main() -> None:
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":  # pragma: no cover
    # This block only runs when the module is executed directly.
    # The main() function and app are tested through integration tests.
    main()
