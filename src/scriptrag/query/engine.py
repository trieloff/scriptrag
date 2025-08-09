"""Dynamic SQL query execution engine (read-only, parameterized)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from scriptrag.api.db_readonly import get_read_only_connection
from scriptrag.config import ScriptRAGSettings
from scriptrag.query.spec import ParamSpec, QuerySpec


@dataclass
class QueryResult:
    """Container for executed query results.

    Attributes:
        rows: List of result rows as dictionaries (column -> value).
    """

    rows: list[dict[str, Any]]


def execute_query(
    settings: ScriptRAGSettings,
    spec: QuerySpec,
    provided_params: dict[str, Any] | None = None,
) -> QueryResult:
    """Validate/cast params, execute SQL safely in read-only mode, return rows."""
    provided_params = provided_params or {}
    bound = _validate_and_cast_params(spec.params, provided_params)

    sql = spec.sql

    # Handle limit/offset wrapping if declared but not present in SQL
    needs_limit = "limit" in bound and ":limit" not in sql.lower()
    needs_offset = "offset" in bound and ":offset" not in sql.lower()
    if needs_limit or needs_offset:
        # Wrap the statement to apply LIMIT/OFFSET
        limit_clause = " LIMIT :limit" if "limit" in bound else ""
        offset_clause = " OFFSET :offset" if "offset" in bound else ""
        sql = f"SELECT * FROM (\n{sql}\n) AS sub{limit_clause}{offset_clause}"

    with get_read_only_connection(settings) as conn:
        try:
            cur = conn.execute(sql, bound)
            fetched = cur.fetchall()
        except sqlite3.OperationalError as e:  # writes or bad SQL in ro mode
            raise ValueError(str(e)) from e

        rows = [dict(r) for r in fetched]

    return QueryResult(rows=rows)


def _validate_and_cast_params(
    params: list[ParamSpec], provided: dict[str, Any]
) -> dict[str, Any]:
    bound: dict[str, Any] = {}

    # Prepare defaults for optional params
    for p in params:
        if p.default is not None:
            bound[p.name] = p.default

    # Overlay provided values after casting
    for p in params:
        if p.name in provided and provided[p.name] is not None:
            bound[p.name] = _cast_value(provided[p.name], p)

    # Fill in None for unspecified optionals (ensures placeholders are bound)
    for p in params:
        if p.name not in bound:
            bound[p.name] = None

    # Check required
    missing = [p.name for p in params if p.required and bound.get(p.name) is None]
    if missing:
        raise ValueError(f"Missing required parameters: {', '.join(missing)}")

    # Validate choices
    for p in params:
        if p.choices and p.name in bound and bound[p.name] is not None:
            val = str(bound[p.name])
            if val not in p.choices:
                raise ValueError(
                    f"Invalid value for {p.name}: {val}. Choices: {p.choices}"
                )

    return bound


def _cast_value(value: Any, spec: ParamSpec) -> Any:
    t = spec.type
    if t == "int":
        return int(value)
    if t == "float":
        return float(value)
    if t == "bool":
        return _to_bool(value)
    # str
    return str(value)


def _to_bool(v: Any) -> bool:
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    # Fallback to Python truthiness
    return bool(v)
