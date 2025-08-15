"""Query command for executing SQL queries."""

import copy
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
from click import Choice
from rich.console import Console

import scriptrag.config.settings as settings_module
from scriptrag.api.query import QueryAPI
from scriptrag.config import get_settings

console = Console()


class QueryAppManager:
    """Manages the query Typer app and command registration state."""

    def __init__(self) -> None:
        """Initialize the query app manager."""
        self.app: typer.Typer | None = None
        self.commands_registered: bool = False

    def get_app(self) -> typer.Typer:
        """Get or create the query app with registered commands.

        This method uses lazy initialization to avoid issues with
        import-time registration in test environments.

        Returns:
            Typer app with registered query commands
        """
        # Initialize app if needed
        if self.app is None:
            self.app = typer.Typer(
                name="query",
                help="Execute SQL queries from the query library",
                no_args_is_help=True,
            )

        # Register commands if not already done
        if not self.commands_registered:
            self.register_commands()

        return self.app

    def register_commands(self, force: bool = False) -> None:
        """Register all discovered queries as subcommands.

        Args:
            force: Force re-registration even if already registered
        """
        # Skip if already registered (unless forced)
        if self.commands_registered and not force:
            return

        # Create new app instance
        self.app = typer.Typer(
            name="query",
            help="Execute SQL queries from the query library",
            no_args_is_help=True,
        )

        # Create API instance
        api = _create_api_instance()
        if api is None:
            return

        # Load queries
        try:
            # Force reload queries from (possibly new) directory
            api.reload_queries()
            # Discover and register queries
            queries = api.list_queries()
        except Exception:
            # If we can't list queries, create empty app
            queries = []

        # Register list command
        _register_list_command(self.app, queries)

        if not queries:
            return

        # Register each query as a subcommand
        for spec in queries:
            _register_single_query(self.app, api, spec)

        # Mark as registered
        self.commands_registered = True


# Create singleton instance
_manager = QueryAppManager()


def create_query_command(
    api: QueryAPI, spec_name: str, db_path_option: bool = True
) -> Callable[..., None] | None:
    """Create a dynamic command for a query specification.

    Args:
        api: Query API instance
        spec_name: Name of the query spec
        db_path_option: Whether to include --db-path option

    Returns:
        Typer command function
    """
    spec = api.get_query(spec_name)
    if not spec:
        return None

    # Build function signature dynamically
    def query_command(**kwargs: Any) -> None:
        """Execute the query."""
        # Extract standard options
        output_json = kwargs.pop("json", False)
        limit = kwargs.pop("limit", None)
        offset = kwargs.pop("offset", None)
        config = kwargs.pop("config", None)
        db_path = kwargs.pop("db_path", None) if db_path_option else None

        # Remaining kwargs are query parameters
        params = kwargs

        try:
            from scriptrag.config.settings import ScriptRAGSettings

            # Load settings with proper precedence
            if config:
                if not config.exists():
                    console.print(f"[red]Error: Config file not found: {config}[/red]")
                    raise typer.Exit(1)

                current_settings = ScriptRAGSettings.from_multiple_sources(
                    config_files=[config],
                )
            else:
                # Force fresh settings to pick up environment variable changes
                settings_module._settings = None  # Clear cached settings
                from scriptrag.config import get_settings as get_settings_func

                current_settings = get_settings_func()

            # Apply db_path override if provided
            if db_path:
                # Create a copy with the new db_path
                current_settings = copy.deepcopy(current_settings)
                current_settings.database_path = db_path

            current_api = QueryAPI(current_settings)

            result = current_api.execute_query(
                name=spec_name,
                params=params,
                limit=limit,
                offset=offset,
                output_json=output_json,
            )

            if result:
                # Use plain print for JSON to avoid Rich text wrapping
                if output_json:
                    print(result)
                else:
                    console.print(result)

        except Exception as e:
            console.print(f"[red]Error executing query '{spec_name}': {e}[/red]")
            raise typer.Exit(1) from e

    # Set function metadata
    query_command.__name__ = spec_name.replace("-", "_")
    query_command.__doc__ = spec.description or f"Execute {spec_name} query"

    # Create Typer command with dynamic parameters
    params: list[tuple[str, Any, Any]] = []

    # Add query-specific parameters
    for param_spec in spec.params:
        # Skip limit/offset as they're handled separately
        if param_spec.name in ("limit", "offset"):
            continue

        # Determine parameter type
        param_type: type[int] | type[float] | type[bool] | type[str]
        if param_spec.type == "int":
            param_type = int
        elif param_spec.type == "float":
            param_type = float
        elif param_spec.type == "bool":
            param_type = bool
        else:
            param_type = str

        # Create Typer parameter
        if param_spec.choices:
            # Use Choice for enumerated options
            param = typer.Option(
                default=param_spec.default if not param_spec.required else ...,
                help=param_spec.help,
                click_type=Choice(param_spec.choices),
            )
        else:
            param = typer.Option(
                default=param_spec.default if not param_spec.required else ...,
                help=param_spec.help,
            )

        params.append((param_spec.name, param_type, param))

    # Add standard options
    has_limit, has_offset = spec.has_limit_offset()

    # Get limit/offset from spec or use defaults
    limit_spec = spec.get_param("limit")
    offset_spec = spec.get_param("offset")

    if has_limit or limit_spec:
        default_limit = limit_spec.default if limit_spec else 10
        params.append(
            (
                "limit",
                int | None,
                typer.Option(
                    default=default_limit,
                    help="Maximum number of rows to return",
                ),
            )
        )

    if has_offset or offset_spec:
        default_offset = offset_spec.default if offset_spec else 0
        params.append(
            (
                "offset",
                int | None,
                typer.Option(
                    default=default_offset,
                    help="Number of rows to skip",
                ),
            )
        )

    # Always add JSON option
    params.append(
        (
            "json",
            bool,
            typer.Option(
                default=False,
                help="Output results as JSON",
            ),
        )
    )

    # Add config option
    params.append(
        (
            "config",
            Path | None,
            typer.Option(
                default=None,
                help="Path to configuration file (YAML, TOML, or JSON)",
            ),
        )
    )

    # Add db_path option if requested
    if db_path_option:
        params.append(
            (
                "db_path",
                Path | None,
                typer.Option(
                    default=None,
                    help="Path to the SQLite database file",
                ),
            )
        )

    # Create wrapper with proper signature
    # Build parameter signature
    sig_params = []
    annotations = {}
    defaults = {}

    for param_name, param_type, param_default in params:
        sig_params.append(
            inspect.Parameter(
                param_name,
                inspect.Parameter.KEYWORD_ONLY,
                default=param_default,
                annotation=param_type,
            )
        )
        annotations[param_name] = param_type
        if param_default is not ...:
            defaults[param_name] = param_default

    # Create new function with proper signature
    sig = inspect.Signature(sig_params)

    def wrapper(**kwargs: Any) -> None:
        return query_command(**kwargs)

    wrapper.__signature__ = sig  # type: ignore[attr-defined]
    wrapper.__annotations__ = annotations
    wrapper.__name__ = query_command.__name__
    wrapper.__doc__ = query_command.__doc__

    return wrapper


def get_query_app() -> typer.Typer:
    """Get or create the query app with registered commands.

    This function uses lazy initialization to avoid issues with
    import-time registration in test environments.

    Returns:
        Typer app with registered query commands
    """
    return _manager.get_app()


def _create_api_instance() -> QueryAPI | None:
    """Create API instance with error handling.

    Returns:
        QueryAPI instance or None if creation fails
    """
    try:
        # Force fresh settings to pick up environment variable changes
        settings_module._settings = None  # Clear cached settings
        settings = get_settings()
        return QueryAPI(settings)
    except Exception:
        # If we can't get settings/API during import, skip registration
        # This allows tests to set up mocks before registration
        return None


def _register_list_command(query_app: typer.Typer, queries: list[Any]) -> None:
    """Register the list command based on available queries.

    Args:
        query_app: Typer app to register command on
        queries: List of available query specifications
    """
    if not queries:
        # Add a placeholder command if no queries found
        @query_app.command(name="list")
        def list_no_queries() -> None:
            """List available queries (none found)."""
            console.print("[yellow]No queries found in query directory.[/yellow]")
            console.print(
                "Add .sql files to the query directory to make them available."
            )
    else:
        # Add list command to show available queries
        @query_app.command(name="list")
        def list_all_queries() -> None:
            """List all available queries."""
            console.print("[bold]Available queries:[/bold]\n")
            for spec in queries:
                console.print(f"  [cyan]{spec.name}[/cyan]")
                if spec.description:
                    console.print(f"    {spec.description}")
                if spec.params:
                    param_names = ", ".join(p.name for p in spec.params)
                    console.print(f"    Parameters: {param_names}")
                console.print()


def _register_single_query(query_app: typer.Typer, api: QueryAPI, spec: Any) -> None:
    """Register a single query as a command.

    Args:
        query_app: Typer app to register command on
        api: Query API instance
        spec: Query specification
    """
    command_func = create_query_command(api, spec.name)
    if command_func:
        query_app.command(name=spec.name)(command_func)


def register_query_commands(force: bool = False) -> None:
    """Register all discovered queries as subcommands.

    This is a convenience function that delegates to the manager.

    Args:
        force: Force re-registration even if already registered
    """
    _manager.register_commands(force=force)
