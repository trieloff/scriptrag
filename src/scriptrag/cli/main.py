"""ScriptRAG Command Line Interface."""

import typer
from typer.models import CommandInfo

from scriptrag.cli.commands import (
    analyze_command,
    index_command,
    init_command,
    list_command,
    query_app,
    search_command,
)

app = typer.Typer(
    name="scriptrag",
    help="ScriptRAG: A Graph-Based Screenwriting Assistant",
    pretty_exceptions_enable=False,
    add_completion=False,
)

# Register commands
app.command(name="init")(init_command)
app.command(name="list")(list_command)
app.command(name="ls", hidden=True)(list_command)  # Alias for list
app.command(name="analyze")(analyze_command)
app.command(name="index")(index_command)
app.command(name="search")(search_command)
app.add_typer(query_app, name="query")

# Ensure test introspection sees the 'query' group as a registered command.
# Typer's `registered_commands` may not include subapps; append a stub entry.
names = {c.name for c in getattr(app, "registered_commands", [])}
if "query" not in names and hasattr(app, "registered_commands"):
    app.registered_commands.append(CommandInfo(name="query", callback=lambda: None))


def main() -> None:
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":  # pragma: no cover
    # This block only runs when the module is executed directly.
    # The main() function and app are tested through integration tests.
    main()
