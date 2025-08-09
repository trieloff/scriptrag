"""Integration tests for `scriptrag query` CLI."""

from pathlib import Path

from typer.testing import CliRunner

from scriptrag.api.database import DatabaseInitializer
from scriptrag.cli.main import app


def _seed(conn):
    conn.execute(
        "INSERT INTO scripts (id, title, author, metadata) VALUES ("
        "1,'Proj','A','{season:1,episode:1}')"
    )
    conn.execute(
        "INSERT INTO "
        "scenes (id, script_id, scene_number, heading, location, time_of_day, content) "
        "VALUES (10,1,1,'INT. TEST - DAY','TEST','DAY','hello world')"
    )


def test_query_help_lists_discovered_queries(tmp_path: Path, monkeypatch):
    # set DB path for CLI
    dbp = tmp_path / "cli.db"
    monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(dbp))
    DatabaseInitializer().initialize_database(db_path=dbp, force=True)

    runner = CliRunner()
    result = runner.invoke(app, ["query", "--help"])
    assert result.exit_code == 0
    output = result.output
    assert "list_scenes" in output
    assert "character_lines" in output


def test_run_list_scenes_query(tmp_path: Path, monkeypatch):
    dbp = tmp_path / "cli2.db"
    monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(dbp))
    DatabaseInitializer().initialize_database(db_path=dbp, force=True)

    import sqlite3

    conn = sqlite3.connect(dbp)
    try:
        conn.row_factory = sqlite3.Row
        _seed(conn)
        conn.commit()
    finally:
        conn.close()

    # Ensure settings singleton points to our temp DB
    from scriptrag.config import ScriptRAGSettings, set_settings

    set_settings(ScriptRAGSettings(database_path=dbp))

    runner = CliRunner()
    result = runner.invoke(app, ["query", "list_scenes", "--limit", "1"])
    assert result.exit_code == 0
    assert "INT. TEST - DAY" in result.output

    json_result = runner.invoke(app, ["query", "list_scenes", "--limit", "1", "--json"])
    assert json_result.exit_code == 0
    assert "script_title" in json_result.output
