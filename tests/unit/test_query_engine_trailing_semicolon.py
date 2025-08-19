import sqlite3
from pathlib import Path

import pytest

from scriptrag.config.settings import ScriptRAGSettings
from scriptrag.query.engine import QueryEngine
from scriptrag.query.spec import ParamSpec, QuerySpec


@pytest.mark.unit
def test_query_engine_strips_trailing_semicolon_and_wraps(tmp_path: Path):
    """Ensure trailing semicolons are stripped before wrapping for LIMIT/OFFSET.

    This covers the logic that normalizes SQL (removes trailing ';') so that
    wrapping with a subquery does not produce a syntax error in SQLite.
    """
    db_path = tmp_path / "test.db"

    # Prepare a simple database with a table and a few rows
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.executemany("INSERT INTO t (v) VALUES (?)", [("a",), ("b",), ("c",)])
        conn.commit()

    # Engine configured to open the file in read-only mode
    settings = ScriptRAGSettings(database_path=db_path)
    engine = QueryEngine(settings)

    # Note the trailing semicolon in SQL; engine should strip it and wrap
    spec = QuerySpec(
        name="test",
        description="test",
        sql="SELECT id, v FROM t;",
        # No explicit limit/offset params; engine should add defaults and wrap
        params=[
            ParamSpec(name="limit", type="int", required=False, default=None),
            ParamSpec(name="offset", type="int", required=False, default=None),
        ],
    )

    rows, _ = engine.execute(spec, params={})

    # Expect all three rows (default limit is 10, table has 3)
    assert len(rows) == 3
    assert [r["v"] for r in rows] == ["a", "b", "c"]
