"""Public API facade for dynamic SQL queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scriptrag.config import ScriptRAGSettings, get_settings
from scriptrag.query.engine import QueryResult, execute_query
from scriptrag.query.loader import discover_queries
from scriptrag.query.spec import QuerySpec


@dataclass
class QueryAPI:
    """Thin facade to orchestrate discovery and execution of queries."""

    settings: ScriptRAGSettings

    @classmethod
    def from_config(cls) -> QueryAPI:
        """Instantiate using global settings singleton."""
        return cls(get_settings())

    def list_queries(self) -> dict[str, QuerySpec]:
        """Discover and return all available query specs by name."""
        return discover_queries(self.settings)

    def run(self, name: str, params: dict[str, Any] | None = None) -> QueryResult:
        """Run a discovered query by name with validated parameters."""
        specs = self.list_queries()
        if name not in specs:
            raise ValueError(f"Unknown query: {name}")
        spec = specs[name]
        return execute_query(self.settings, spec, params or {})
