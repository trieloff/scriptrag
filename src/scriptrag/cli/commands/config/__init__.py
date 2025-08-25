"""Configuration management commands for ScriptRAG."""

import typer

from .init import config_init
from .precedence import config_precedence
from .show import config_show
from .validate import config_validate

# Create config subapp
config_app = typer.Typer(
    name="config",
    help="Manage ScriptRAG configuration",
    pretty_exceptions_enable=False,
)

# Register commands
config_app.command(name="init")(config_init)
config_app.command(name="validate")(config_validate)
config_app.command(name="show")(config_show)
config_app.command(name="precedence")(config_precedence)

__all__ = ["config_app"]
