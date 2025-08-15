"""Integration tests for simplified duplicate handling using file_path as unique key."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.index import IndexCommand
from scriptrag.config import ScriptRAGSettings


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Initialize database with new schema
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT,
            file_path TEXT UNIQUE NOT NULL,
            project_title TEXT,
            series_title TEXT,
            season INTEGER,
            episode INTEGER,
            metadata JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_id INTEGER NOT NULL,
            scene_number INTEGER NOT NULL,
            heading TEXT NOT NULL,
            location TEXT,
            time_of_day TEXT,
            content TEXT,
            metadata JSON,
            FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
            UNIQUE(script_id, scene_number)
        );

        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            metadata JSON,
            FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
            UNIQUE(script_id, name)
        );

        CREATE TABLE IF NOT EXISTS dialogues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            dialogue_text TEXT NOT NULL,
            order_in_scene INTEGER NOT NULL,
            metadata JSON,
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            action_text TEXT NOT NULL,
            order_in_scene INTEGER NOT NULL,
            metadata JSON,
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
        );
    """)
    conn.close()

    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def index_command(temp_db):
    """Create an IndexCommand with a temporary database."""
    settings = ScriptRAGSettings(database_path=temp_db)
    db_ops = DatabaseOperations(settings)
    return IndexCommand(settings=settings, db_ops=db_ops)


def create_script_with_metadata(
    script_path: Path, title: str, series: str | None = None
):
    """Create a script with metadata."""
    series_metadata = ""
    if series:
        series_metadata = f"""Series: {series}
Season: 1
Episode: 1
"""

    content = f"""Title: {title}
Author: Test Author
{series_metadata}
INT. SCENE ONE - DAY

/* SCRIPTRAG-META-START
{{"analyzed_at": "2024-01-01T00:00:00"}}
SCRIPTRAG-META-END */

Action in scene one.

CHARACTER_A
Dialogue in scene one.
"""
    script_path.write_text(content)


class TestDuplicateHandling:
    """Test duplicate handling with file_path as unique key."""

    @pytest.mark.asyncio
    async def test_file_path_uniqueness(self, index_command, tmp_path):
        """Test that file_path is the unique identifier for scripts."""
        # Create a script
        script1 = tmp_path / "script1.fountain"
        create_script_with_metadata(script1, "My Script")

        # Index it once
        result1 = await index_command.index(path=tmp_path)
        assert result1.total_scripts_indexed == 1

        # Index it again - should update, not create duplicate
        result2 = await index_command.index(path=tmp_path)
        assert result2.total_scripts_updated == 1
        assert result2.total_scripts_indexed == 0  # No new scripts

        # Verify only one script in database
        with index_command.db_ops.transaction() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM scripts")
            count = cursor.fetchone()[0]
            assert count == 1

    @pytest.mark.asyncio
    async def test_same_title_different_files(self, index_command, tmp_path):
        """Test that same title in different files creates separate entries."""
        # Create two scripts with same title but different paths
        script1 = tmp_path / "draft1.fountain"
        script2 = tmp_path / "draft2.fountain"

        create_script_with_metadata(script1, "Same Title")
        create_script_with_metadata(script2, "Same Title")

        # Index both
        result = await index_command.index(path=tmp_path)
        assert result.total_scripts_indexed == 2

        # Verify two scripts in database
        with index_command.db_ops.transaction() as conn:
            cursor = conn.execute("SELECT file_path FROM scripts ORDER BY file_path")
            files = [row[0] for row in cursor.fetchall()]
            assert len(files) == 2
            assert str(script1) in files[0]
            assert str(script2) in files[1]

    @pytest.mark.asyncio
    async def test_series_metadata_extraction(self, index_command, tmp_path):
        """Test that series metadata is properly extracted and stored."""
        # Create a TV series script
        script = tmp_path / "episode.fountain"
        create_script_with_metadata(script, "Episode Title", series="My Series")

        # Index it
        result = await index_command.index(path=tmp_path)
        assert result.total_scripts_indexed == 1

        # Verify series metadata in database
        with index_command.db_ops.transaction() as conn:
            cursor = conn.execute(
                "SELECT series_title, season, episode FROM scripts WHERE file_path = ?",
                (str(script),),
            )
            row = cursor.fetchone()
            assert row[0] == "My Series"  # series_title
            assert row[1] == 1  # season
            assert row[2] == 1  # episode

    @pytest.mark.asyncio
    async def test_update_preserves_file_path(self, index_command, tmp_path):
        """Test that updating a script preserves the file_path."""
        script = tmp_path / "script.fountain"

        # Create and index initial version
        create_script_with_metadata(script, "Original Title")
        await index_command.index(path=tmp_path)

        # Modify the script (change title)
        create_script_with_metadata(script, "Updated Title")

        # Re-index
        result = await index_command.index(path=tmp_path)
        assert result.total_scripts_updated == 1

        # Verify the file_path is unchanged but title is updated
        with index_command.db_ops.transaction() as conn:
            cursor = conn.execute(
                "SELECT title, file_path FROM scripts WHERE file_path = ?",
                (str(script),),
            )
            row = cursor.fetchone()
            assert row[0] == "Updated Title"
            assert row[1] == str(script)

    @pytest.mark.asyncio
    async def test_no_duplicate_on_reindex(self, index_command, tmp_path):
        """Test that re-indexing doesn't create duplicates."""
        script = tmp_path / "script.fountain"
        create_script_with_metadata(script, "Test Script")

        # Index multiple times
        for _ in range(3):
            await index_command.index(path=tmp_path)

        # Should still have only one script
        with index_command.db_ops.transaction() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM scripts")
            count = cursor.fetchone()[0]
            assert count == 1

            # Check scenes aren't duplicated either
            cursor = conn.execute("SELECT COUNT(*) FROM scenes")
            scene_count = cursor.fetchone()[0]
            assert scene_count == 1  # Only one scene in our test script
