"""Integration test: analyze relationships and persist to scenes metadata."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from scriptrag.api.analyze import AnalyzeCommand
from scriptrag.api.database import DatabaseInitializer
from scriptrag.api.index import IndexCommand
from scriptrag.config import ScriptRAGSettings, set_settings


def _script_with_mentions(tmp_path: Path) -> Path:
    content = (
        "Title: Relationships Test\n"
        "Author: Tester\n\n"
        "INT. LOBBY - DAY\n\n"
        "/* SCRIPTRAG-META-START\n{}\nSCRIPTRAG-META-END */\n\n"
        "JANE (O.S.)\nHe'll be here soon.\n\n"
        "Action: Mr. Johnson enters.\n"
    )
    p = tmp_path / "relationships.fountain"
    p.write_text(content)
    return p


@pytest.mark.asyncio
async def test_analyze_relationships_persists_scene_metadata(tmp_path: Path) -> None:
    # Init DB and settings
    db_path = tmp_path / "test.db"
    settings = ScriptRAGSettings(database_path=db_path)
    set_settings(settings)

    # Force close any existing connection manager to ensure clean state
    from scriptrag.database.connection_manager import close_connection_manager

    close_connection_manager()

    DatabaseInitializer().initialize_database(db_path, settings=settings, force=True)

    # Create script and index it
    script_path = _script_with_mentions(tmp_path)
    index_cmd = IndexCommand(settings=settings)
    res = await index_cmd.index(script_path.parent, recursive=False)
    assert res.total_scripts_indexed == 1

    # Seed bible alias map in scripts.metadata
    import sqlite3

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, metadata FROM scripts WHERE file_path = ?",
            (str(script_path),),
        ).fetchone()
        assert row is not None
        script_id = row["id"]
        meta = json.loads(row["metadata"]) if row["metadata"] else {}
        meta["bible.characters"] = {
            "version": 1,
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "characters": [
                {"canonical": "JANE SMITH", "aliases": ["JANE", "MS. SMITH"]},
                {"canonical": "BOB JOHNSON", "aliases": ["BOB", "MR. JOHNSON"]},
            ],
        }
        conn.execute(
            "UPDATE scripts SET metadata = ? WHERE id = ?",
            (json.dumps(meta), script_id),
        )
        conn.commit()

    # Run analyze with relationships analyzer
    analyze_cmd = AnalyzeCommand.from_config(auto_load_analyzers=False)
    analyze_cmd.load_analyzer("relationships")
    res2 = await analyze_cmd.analyze(script_path.parent, recursive=False, brittle=True)
    assert res2.total_files_updated >= 1

    # Re-index to persist scene metadata into DB
    await index_cmd.index(script_path.parent, recursive=False)

    # Verify scenes.metadata contains relationships under boneyard analyzers
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, metadata FROM scenes WHERE script_id = ?",
            (script_id,),
        ).fetchone()
        assert row is not None
        smeta = json.loads(row["metadata"]) if row["metadata"] else {}
        rel = smeta.get("boneyard", {}).get("analyzers", {}).get("relationships", {})
        assert rel
        # At least Jane speaking and Mr. Johnson mentioned
        assert "JANE SMITH" in rel.get("speaking", [])
        assert set(rel.get("present", [])) >= {"JANE SMITH", "BOB JOHNSON"}
