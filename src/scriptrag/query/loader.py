"""Discovery and loading of parameterized SQL query specs."""

from __future__ import annotations

from pathlib import Path

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.query.spec import QuerySpec, parse_query_file

logger = get_logger(__name__)

# Simple in-process cache keyed by file path + mtime
_cache: dict[tuple[Path, float], QuerySpec] = {}


def discover_queries(settings: ScriptRAGSettings) -> dict[str, QuerySpec]:
    """Discover .sql files under the configured query directory.

    Returns a mapping of query name to QuerySpec. If duplicate names are
    found, later files override earlier ones with a warning.
    """
    base = settings.query_dir
    results: dict[str, QuerySpec] = {}

    if not base.exists():
        return results

    for path in sorted(base.rglob("*.sql")):
        try:
            key = (path, path.stat().st_mtime)
            spec = _cache.get(key)
            if spec is None:
                spec = parse_query_file(path)
                _cache[key] = spec

            if spec.name in results:
                logger.warning(
                    "Duplicate query name discovered; overriding",
                    extra={"name": spec.name, "path": str(path)},
                )
            results[spec.name] = spec
        except Exception as e:  # pragma: no cover - defensive
            logger.error(
                "Failed to load query spec",
                extra={"path": str(path), "error": str(e)},
            )

    return results
