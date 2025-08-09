"""Unit tests for query loader discovery."""

from pathlib import Path

from scriptrag.config import ScriptRAGSettings
from scriptrag.query.loader import discover_queries


def test_discover_queries(tmp_path: Path):
    qdir = tmp_path / "queries"
    qdir.mkdir()
    (qdir / "a.sql").write_text("-- name: one\nSELECT 1;\n", encoding="utf-8")
    (qdir / "b.sql").write_text("-- name: two\nSELECT 2;\n", encoding="utf-8")

    settings = ScriptRAGSettings(query_dir=qdir)
    found = discover_queries(settings)
    assert set(found.keys()) == {"one", "two"}

    # Duplicate name should override
    (qdir / "c.sql").write_text("-- name: one\nSELECT 3;\n", encoding="utf-8")
    found2 = discover_queries(settings)
    assert set(found2.keys()) == {"one", "two"}
