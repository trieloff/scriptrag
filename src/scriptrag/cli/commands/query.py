"""Dynamic SQL query runner CLI."""

from __future__ import annotations

from typing import Annotated, Any

import typer
from rich.console import Console

from scriptrag.api.query import QueryAPI
from scriptrag.config import get_logger
from scriptrag.query.formatter import format_rows

logger = get_logger(__name__)

query_app = typer.Typer(
    name="query",
    help=(
        "Run parameterized SQL queries discovered in the queries directory. "
        "Use 'scriptrag query --help' to see available queries."
    ),
    pretty_exceptions_enable=False,
    add_completion=False,
)

# A Click group hosting the dynamic commands, mounted into the main app.
# Note: A pure Click group was explored to avoid exec, but Typer currently
# doesn't expose a supported way to mount a runtime-built click.Group while
# keeping help/UX consistent. The dynamic Typer command approach below keeps
# behavior correct and secure (no SQL interpolation; CLI options validated).


@query_app.callback(invoke_without_command=True)
def query_root(ctx: typer.Context) -> None:
    """When invoked without a subcommand, list discovered queries."""
    if ctx.invoked_subcommand is not None:
        return

    console = Console()
    api = QueryAPI.from_config()
    specs = api.list_queries()
    if not specs:
        console.print("[yellow]No queries found.[/yellow]")
        raise typer.Exit(0)

    console.print("[bold]Available queries:[/bold]")
    for name, spec in sorted(specs.items()):
        desc = f" - {spec.description}" if spec.description else ""
        console.print(f" • [cyan]{name}[/cyan]{desc}")
    console.print(
        "\nRun: scriptrag query <name> --help for parameter details (if any)."
    )


def _register_dynamic_commands() -> None:
    """Discover queries and register Typer commands using dynamic functions."""
    api = QueryAPI.from_config()
    specs = api.list_queries()

    for name, spec in specs.items():
        # Build function source with proper Typer options via annotations.
        params_src: list[str] = []
        body: list[str] = [
            "    try:",
            "        _api = QueryAPI.from_config()",
            "        _params: dict[str, Any] = {}",
        ]

        for p in spec.params:
            py_type = {
                "str": "str",
                "int": "int",
                "float": "float",
                "bool": "bool",
            }[p.type]
            opt = "typer.Option(help=" + repr(p.help if p.help else "") + ")"
            default_str = (
                repr(p.default)
                if p.default is not None
                else ("..." if p.required else "None")
            )
            params_src.append(
                f"    {p.name}: Annotated[{py_type} | None, {opt}] = {default_str},"
            )
            body.append(f"        _params['{p.name}'] = {p.name}")

        declared_names = {p.name for p in spec.params}
        if "limit" not in declared_names:
            params_src.append(
                "    limit: Annotated[int | None, "
                "typer.Option(help='Limit rows')] = None,",
            )
        if "offset" not in declared_names:
            params_src.append(
                "    offset: Annotated[int | None, "
                "typer.Option(help='Offset rows')] = None,",
            )
        params_src.append(
            "    json_output: Annotated[bool, "
            "typer.Option('--json', help='Output JSON')] = False,",
        )

        body.extend(
            [
                "        if limit is not None:",
                "            _params['limit'] = limit",
                "        if offset is not None:",
                "            _params['offset'] = offset",
                (
                    f"        _res = _api.run('{name}', "
                    "{k: v for k, v in _params.items() if v is not None})"
                ),
                (
                    "        out = format_rows(_res.rows, json_output=json_output, "
                    f"title='{name}', limit=_params.get('limit'), "
                    "offset=_params.get('offset'))"
                ),
                "        if out is not None:",
                "            Console().print(out)",
                "    except Exception as e:",
                "        logger.error('Query failed: %s', str(e))",
                "        Console().print('[red]Error:[/red] ' + str(e))",
                "        raise typer.Exit(1) from e",
            ]
        )

        fn_src = (
            "def _cmd(\n" + "\n".join(params_src) + "\n):\n" + "\n".join(body) + "\n"
        )
        ns: dict[str, Any] = {
            "Annotated": Annotated,
            "typer": typer,
            "Console": Console,
            "QueryAPI": QueryAPI,
            "format_rows": format_rows,
            "logger": logger,
            "Any": Any,
        }
        exec(fn_src, ns)  # nosec B102: dynamic CLI generation is intended  # noqa: S102
        cmd_fn = ns["_cmd"]
        query_app.command(name=name, help=spec.description)(cmd_fn)


# Register commands at import time
try:  # pragma: no cover - behavior validated via CLI tests
    _register_dynamic_commands()
except Exception as _e:  # pragma: no cover
    # If discovery fails at import, keep the subapp usable for help
    logger.warning("Query command registration skipped: %s", str(_e))
