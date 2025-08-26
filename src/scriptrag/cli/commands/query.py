"""Refactored query command with clean separation of concerns."""

import inspect
from collections.abc import Callable
from typing import Any

import typer
from rich.console import Console

from scriptrag.api.query import QueryAPI
from scriptrag.cli.formatters.base import OutputFormat
from scriptrag.cli.formatters.query_formatter import QueryResultFormatter
from scriptrag.cli.utils.cli_handler import CLIHandler
from scriptrag.config import get_logger, get_settings

logger = get_logger(__name__)
console = Console()


class QueryCommandBuilder:
    """Builds query commands dynamically from available queries."""

    def __init__(self, api: QueryAPI) -> None:
        """Initialize query command builder.

        Args:
            api: Query API instance
        """
        self.api = api
        self.formatter = QueryResultFormatter()
        self.handler = CLIHandler(console)

    def create_query_app(self) -> typer.Typer:
        """Create Typer app with dynamically registered query commands.

        Returns:
            Configured Typer app
        """
        app = typer.Typer(
            name="query",
            help="Execute SQL queries from the query library",
            no_args_is_help=True,
        )

        # Register list command
        app.command(name="list")(self._create_list_command())

        # Load and register queries
        try:
            self.api.reload_queries()
            queries = self.api.list_queries()

            for spec in queries:
                self._register_query_command(app, spec)

        except Exception as e:
            logger.warning(f"Failed to load queries: {e}")

        return app

    def _create_list_command(self) -> Callable[..., None]:
        """Create the list command."""

        def list_queries(
            json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
            verbose: bool = typer.Option(
                False, "--verbose", "-v", help="Show query details"
            ),
        ) -> None:
            """List all available queries."""
            try:
                queries = self.api.list_queries()

                if json_output:
                    # JSON output
                    import json

                    output = [
                        {
                            "name": q.name,
                            "description": q.description,
                            "parameters": [
                                {"name": p.name, "type": p.type, "required": p.required}
                                for p in q.params
                            ],
                        }
                        for q in queries
                    ]
                    console.print(json.dumps(output, indent=2))
                else:
                    # Table output
                    if not queries:
                        console.print("[dim]No queries available[/dim]")
                        return

                    console.print("[bold]Available queries:[/bold]\n")

                    for query in queries:
                        info = self.formatter.format_query_info(
                            query.name,
                            query.description,
                            [f"{p.name} ({p.type})" for p in query.params]
                            if verbose
                            else None,
                        )
                        console.print(info)
                        console.print()

            except Exception as e:
                self.handler.handle_error(e, json_output)

        return list_queries

    def _register_query_command(self, app: typer.Typer, spec: Any) -> None:
        """Register a single query as a command.

        Args:
            app: Typer app to register to
            spec: Query specification
        """

        def create_command() -> Callable[..., None]:
            """Create command function for the query."""

            def query_command(**kwargs: Any) -> None:
                """Execute the query with provided parameters."""
                # Extract output format options
                json_output = kwargs.pop("json", False)
                csv_output = kwargs.pop("csv", False)
                markdown_output = kwargs.pop("markdown", False)

                # Determine output format
                if json_output:
                    output_format = OutputFormat.JSON
                elif csv_output:
                    output_format = OutputFormat.CSV
                elif markdown_output:
                    output_format = OutputFormat.MARKDOWN
                else:
                    output_format = OutputFormat.TABLE
                    _ = output_format  # Used to determine output handling

                try:
                    # Execute query through API
                    import time

                    start_time = time.time()
                    results = self.api.execute_query(
                        spec.name, kwargs, output_json=json_output
                    )
                    execution_time = time.time() - start_time
                    _ = execution_time  # Track for potential stats

                    # Query API returns formatted string, just print it
                    if results is not None:
                        console.print(results)

                    # Execution stats are handled by the API formatter

                except Exception as e:
                    self.handler.handle_error(e, json_output)

            # Build command signature dynamically

            # Create parameter annotations
            params = {}

            # Add query-specific parameters
            for param_spec in spec.params:
                param_type = getattr(__builtins__, param_spec.type, str)
                param_help = param_spec.help or f"Parameter: {param_spec.name}"
                param_default = param_spec.default if not param_spec.required else ...

                if param_default == ...:
                    # Required parameter
                    params[param_spec.name] = (
                        param_type,
                        typer.Option(..., help=param_help),
                    )
                else:
                    # Optional parameter with default
                    params[param_spec.name] = (
                        param_type,
                        typer.Option(param_default, help=param_help),
                    )

            # Add output format options
            params["json"] = (
                bool,
                typer.Option(False, "--json", help="Output as JSON"),
            )
            params["csv"] = (bool, typer.Option(False, "--csv", help="Output as CSV"))
            params["markdown"] = (
                bool,
                typer.Option(False, "--markdown", help="Output as Markdown"),
            )

            # Create function with dynamic signature
            sig = inspect.signature(query_command)
            new_params = []
            for name, (type_, default) in params.items():
                new_params.append(
                    inspect.Parameter(
                        name,
                        inspect.Parameter.KEYWORD_ONLY,
                        annotation=type_,
                        default=default,
                    )
                )

            # Fix signature assignment with proper type handling
            import contextlib

            with contextlib.suppress(AttributeError):
                query_command.__signature__ = sig.replace(parameters=new_params)  # type: ignore[attr-defined]
            query_command.__doc__ = spec.description

            return query_command

        # Register the command
        app.command(name=spec.name)(create_command())


class QueryAppManager:
    """Manages the query Typer app and command registration state."""

    def __init__(self) -> None:
        """Initialize the query app manager."""
        self.app: typer.Typer | None = None

    def get_app(self) -> typer.Typer:
        """Get or create the query app with registered commands.

        This method uses lazy initialization to avoid issues with
        import-time registration in test environments.

        Returns:
            Typer app with registered query commands
        """
        if self.app is None:
            # Get or create API instance
            settings = get_settings()
            api = QueryAPI(settings)

            # Build and return app
            builder = QueryCommandBuilder(api)
            self.app = builder.create_query_app()

        return self.app

    def reset(self) -> None:
        """Reset the app to force recreation on next access.

        This is useful for tests that modify environment variables
        and need a fresh app with updated settings.
        """
        self.app = None


def create_query_app() -> typer.Typer:
    """Create the query Typer app with all commands.

    Returns:
        Configured Typer app
    """
    # Get or create API instance
    settings = get_settings()
    api = QueryAPI(settings)

    # Build and return app
    builder = QueryCommandBuilder(api)
    return builder.create_query_app()


# Manager instance for lazy initialization
_query_app_manager = QueryAppManager()


def get_query_app() -> typer.Typer:
    """Get the query Typer app with lazy initialization.

    Returns:
        Configured Typer app
    """
    return _query_app_manager.get_app()


def reset_query_app() -> None:
    """Reset the query app manager.

    This forces recreation of the app with fresh settings,
    useful for tests that modify environment variables.
    """
    global _query_app_manager
    _query_app_manager.reset()


# Export the lazy-loaded app getter
query_app = get_query_app
