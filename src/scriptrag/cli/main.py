"""ScriptRAG Command Line Interface."""

import typer

from scriptrag.cli.commands import init_command, list_command, pull

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
app.command(name="pull")(pull)


def main() -> None:
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":  # pragma: no cover
    # This block only runs when the module is executed directly.
    # The main() function and app are tested through integration tests.
    main()
