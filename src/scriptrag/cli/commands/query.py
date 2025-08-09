"""Query command for executing SQL queries."""

from typing import Any

import typer
from rich.console import Console

from scriptrag.api.query import QueryAPI
from scriptrag.config import get_settings

# Create query app
query_app = typer.Typer(
    name="query",
    help="Execute SQL queries from the query library",
    no_args_is_help=True,
)

console = Console()


def create_query_command(api: QueryAPI, spec_name: str) -> Any:
    """Create a dynamic command for a query specification.

    Args:
        api: Query API instance
        spec_name: Name of the query spec

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

        # Remaining kwargs are query parameters
        params = kwargs

        try:
            # Get fresh API instance with current settings at execution time
            # Force fresh settings to pick up environment variable changes
            import scriptrag.config.settings as settings_module

            settings_module._settings = None  # Clear cached settings
            current_settings = get_settings()
            current_api = QueryAPI(current_settings)

            result = current_api.execute_query(
                name=spec_name,
                params=params,
                limit=limit,
                offset=offset,
                output_json=output_json,
            )

            if result:
                console.print(result)

        except Exception as e:
            console.print(f"[red]Error executing query '{spec_name}': {e}[/red]")
            raise typer.Exit(1) from e

    # Set function metadata
    query_command.__name__ = spec_name.replace("-", "_")
    query_command.__doc__ = spec.description or f"Execute {spec_name} query"

    # Create Typer command with dynamic parameters
    params = []

    # Add query-specific parameters
    for param_spec in spec.params:
        # Skip limit/offset as they're handled separately
        if param_spec.name in ("limit", "offset"):
            continue

        # Determine parameter type
        param_type: Any
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
            from click import Choice

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

    # Create wrapper with proper signature
    import inspect

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


def register_query_commands() -> None:
    """Register all discovered queries as subcommands."""
    # Clear any existing commands to prevent stale cache issues
    if hasattr(query_app, "registered_commands"):
        query_app.registered_commands.clear()
    if hasattr(query_app, "registered_groups"):
        query_app.registered_groups.clear()

    # Force fresh settings to pick up environment variable changes
    import scriptrag.config.settings as settings_module

    settings_module._settings = None  # Clear cached settings
    settings = get_settings()
    api = QueryAPI(settings)

    # Discover and register queries
    queries = api.list_queries()

    if not queries:
        # Add a placeholder command if no queries found
        @query_app.command(name="list")
        def list_no_queries() -> None:
            """List available queries (none found)."""
            console.print("[yellow]No queries found in query directory.[/yellow]")
            console.print(
                "Add .sql files to the query directory to make them available."
            )

        return

    # Register each query as a subcommand
    for spec in queries:
        command_func = create_query_command(api, spec.name)
        if command_func:
            query_app.command(name=spec.name)(command_func)

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


# Register commands on module import
register_query_commands()
