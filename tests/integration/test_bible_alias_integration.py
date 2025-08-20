"""Integration tests for Bible alias map attaching to characters."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from scriptrag.api.database import DatabaseInitializer
from scriptrag.api.index import IndexCommand
from scriptrag.config import ScriptRAGSettings, set_settings


def _make_script(tmp_path: Path) -> Path:
    content = (
        "Title: Alias Test\n"
        "Author: Tester\n\n"
        "INT. TEST ROOM - DAY\n\n"
        "/* SCRIPTRAG-META-START\n{}\nSCRIPTRAG-META-END */\n\n"
        "JANE\nWe need a plan.\n\n"
        "BOB\nAgreed.\n"
    )
    p = tmp_path / "alias_test.fountain"
    p.write_text(content)
    return p


@pytest.mark.asyncio
async def test_index_attaches_aliases_to_characters(tmp_path: Path) -> None:
    # Initialize DB
    db_path = tmp_path / "test.db"
    DatabaseInitializer().initialize_database(db_path, force=True)

    # Prepare settings for commands
    settings = ScriptRAGSettings(database_path=db_path)
    set_settings(settings)

    # Create and index script
    script_path = _make_script(tmp_path)
    cmd = IndexCommand(settings=settings)
    res = await cmd.index(script_path.parent, recursive=False)
    assert res.total_scripts_indexed == 1

    # Fetch the script_id
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
        # Store Bible characters data using dotted key format expected by index.py
        meta["bible.characters"] = {
            "version": 1,
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "characters": [
                {"canonical": "JANE", "aliases": ["JANE", "MS. SMITH"]},
                {"canonical": "BOB", "aliases": ["BOB", "MR. JOHNSON"]},
            ],
        }
        conn.execute(
            "UPDATE scripts SET metadata = ? WHERE id = ?",
            (json.dumps(meta), script_id),
        )
        conn.commit()

    # Re-index to trigger alias attachment in characters table
    res2 = await cmd.index(script_path.parent, recursive=False)
    assert res2.total_scripts_updated == 1

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT name, aliases FROM characters WHERE script_id = ?",
            (script_id,),
        ).fetchall()
        # Expect aliases JSON stored for both characters
        assert len(rows) == 2
        by_name = {
            row["name"].strip().upper(): (
                json.loads(row["aliases"]) if row["aliases"] else []
            )
            for row in rows
        }
        assert "JANE" in by_name.get("JANE", [])
        assert "BOB" in by_name.get("BOB", [])
