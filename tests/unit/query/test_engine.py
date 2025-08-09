"""Unit tests for dynamic query engine."""

from pathlib import Path

import pytest

from scriptrag.api.database import DatabaseInitializer
from scriptrag.config import ScriptRAGSettings
from scriptrag.query.engine import execute_query
from scriptrag.query.spec import ParamSpec, QuerySpec


@pytest.fixture()
def initialized_settings(tmp_path: Path) -> ScriptRAGSettings:
    settings = ScriptRAGSettings(database_path=tmp_path / "q.db")
    DatabaseInitializer().initialize_database(
        db_path=settings.database_path, force=True
    )
    return settings


def _seed_sample(conn):
    conn.execute(
        "INSERT INTO scripts (id, title, author, metadata) VALUES ("
        "1,'Proj','A','{season:1,episode:2}')"
    )
    conn.execute(
        "INSERT INTO "
        "scenes (id, script_id, scene_number, heading, location, time_of_day, content) "
        "VALUES (10,1,1,'INT. TEST - DAY','TEST','DAY','hello world')"
    )


def test_execute_named_params_and_wrapping(initialized_settings: ScriptRAGSettings):
    spec = QuerySpec(
        name="q",
        description="",
        params=[
            ParamSpec(name="limit", type="int", required=False, default=1),
            ParamSpec(name="offset", type="int", required=False, default=0),
        ],
        sql=(
            "SELECT sc.title as script_title, "
            "s.scene_number, s.heading as scene_heading, "
            "s.content as scene_content "
            "FROM scenes s JOIN scripts sc ON sc.id = s.script_id"
        ),
        source_path=Path("/virtual.sql"),
    )

    import sqlite3

    conn = sqlite3.connect(initialized_settings.database_path)
    try:
        conn.row_factory = sqlite3.Row
        _seed_sample(conn)
        conn.commit()
    finally:
        conn.close()

    res = execute_query(initialized_settings, spec, {})
    assert len(res.rows) == 1
    assert res.rows[0]["script_title"] == "Proj"


def test_required_param_validation(initialized_settings: ScriptRAGSettings):
    spec = QuerySpec(
        name="q",
        description="",
        params=[ParamSpec(name="x", type="str", required=True)],
        sql="SELECT :x as x",
        source_path=Path("/v.sql"),
    )
    with pytest.raises(ValueError):
        execute_query(initialized_settings, spec, {})


def test_choices_validation(initialized_settings: ScriptRAGSettings):
    spec = QuerySpec(
        name="q",
        description="",
        params=[ParamSpec(name="x", type="str", required=True, choices=["a", "b"])],
        sql="SELECT :x as x",
        source_path=Path("/v.sql"),
    )
    with pytest.raises(ValueError):
        execute_query(initialized_settings, spec, {"x": "c"})
    res = execute_query(initialized_settings, spec, {"x": "a"})
    assert res.rows[0]["x"] == "a"


def test_read_only_enforced(initialized_settings: ScriptRAGSettings):
    # Attempt a write should fail in read-only mode
    spec = QuerySpec(
        name="q",
        description="",
        params=[],
        sql="CREATE TABLE x(id INT)",
        source_path=Path("/v.sql"),
    )
    with pytest.raises(ValueError):
        execute_query(initialized_settings, spec, {})
