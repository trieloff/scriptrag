"""Generic formatter for dynamic query results.

Uses the Search ResultFormatter when rows look like scene records,
otherwise renders a simple table or JSON.
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from scriptrag.search.formatter import ResultFormatter as SceneResultFormatter
from scriptrag.search.models import SearchQuery, SearchResponse, SearchResult


def format_rows(
    rows: list[dict[str, Any]],
    *,
    json_output: bool = False,
    console: Console | None = None,
    title: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> str | None:
    """Format and print rows. Returns JSON string when json_output is True.

    For scene-like rows, delegates to Scene ResultFormatter.
    """
    console = console or Console()

    if json_output:
        return json.dumps(rows, indent=2)

    if _looks_like_scene_rows(rows):
        # Map dict rows to SearchResult and delegate to the existing formatter
        results: list[SearchResult] = []
        for r in rows:
            results.append(
                SearchResult(
                    script_id=int(r.get("script_id", 0) or 0),
                    script_title=str(r.get("script_title", "")),
                    script_author=(r.get("script_author")),
                    scene_id=int(r.get("scene_id", 0) or 0),
                    scene_number=int(r.get("scene_number", 0) or 0),
                    scene_heading=str(r.get("scene_heading", "")),
                    scene_location=r.get("scene_location"),
                    scene_time=r.get("scene_time"),
                    scene_content=str(r.get("scene_content", "")),
                    season=_safe_int_or_none(r.get("season")),
                    episode=_safe_int_or_none(r.get("episode")),
                )
            )

        q = SearchQuery(
            raw_query=title or "query", limit=limit or 0, offset=offset or 0
        )
        resp = SearchResponse(
            query=q,
            results=results,
            total_count=(len(results)),
            has_more=False if limit is None else len(results) >= (limit or 0),
        )
        SceneResultFormatter(console).format_results(resp, verbose=False)
        return None

    # Generic table rendering
    if not rows:
        console.print("[yellow]No rows returned.[/yellow]")
        return None

    columns = list(rows[0].keys())
    table = Table(show_lines=False)
    for c in columns:
        table.add_column(str(c))
    for r in rows:
        table.add_row(*[str(r.get(c, "")) for c in columns])
    if title:
        console.print(f"[bold]{title}[/bold]")
    console.print(table)
    return None


def _looks_like_scene_rows(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return False
    keys = set(rows[0].keys())
    required = {"script_title", "scene_number", "scene_heading", "scene_content"}
    return required.issubset(keys)


def _safe_int_or_none(v: Any) -> int | None:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None
