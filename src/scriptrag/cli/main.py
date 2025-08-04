"""ScriptRAG Command Line Interface."""

import typer

from scriptrag.cli.commands import init_command

app = typer.Typer(
    name="scriptrag",
    help="ScriptRAG: A Graph-Based Screenwriting Assistant",
    pretty_exceptions_enable=False,
    add_completion=False,
)

# Register commands
app.command(name="init")(init_command)


def main() -> None:
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
