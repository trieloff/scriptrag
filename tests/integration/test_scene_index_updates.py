"""Integration tests for scene index updates when scripts are modified."""

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

    # Initialize database schema
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            author TEXT,
            file_path TEXT UNIQUE NOT NULL,
            metadata JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            version INTEGER DEFAULT 1,
            is_current BOOLEAN DEFAULT TRUE,
            CHECK (is_current IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_id INTEGER NOT NULL,
            scene_number INTEGER NOT NULL,
            heading TEXT NOT NULL,
            location TEXT,
            time_of_day TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSON,
            FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
            UNIQUE(script_id, scene_number)
        );

        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            first_appearance_scene_id INTEGER,
            metadata JSON,
            FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
            FOREIGN KEY (first_appearance_scene_id) REFERENCES scenes(id),
            UNIQUE(script_id, name)
        );

        CREATE TABLE IF NOT EXISTS dialogues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            dialogue_text TEXT NOT NULL,
            order_in_scene INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSON,
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            action_text TEXT NOT NULL,
            order_in_scene INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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


def create_script_v1(script_path: Path):
    """Create initial version of script with 3 scenes."""
    content = """Title: Test Script
Author: Test Author

INT. SCENE ONE - DAY

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-01T00:00:00", "version": 1}
SCRIPTRAG-META-END */

Action in scene one.

CHARACTER_A
Dialogue in scene one.

INT. SCENE TWO - NIGHT

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-01T00:00:00", "version": 1}
SCRIPTRAG-META-END */

Action in scene two.

CHARACTER_B
Dialogue in scene two.

INT. SCENE THREE - DAY

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-01T00:00:00", "version": 1}
SCRIPTRAG-META-END */

Action in scene three.

CHARACTER_A
Dialogue in scene three.
"""
    script_path.write_text(content)


def create_script_v2_with_insertion(script_path: Path):
    """Create version 2 with a new scene inserted between scenes 1 and 2."""
    content = """Title: Test Script
Author: Test Author

INT. SCENE ONE - DAY

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-02T00:00:00", "version": 2}
SCRIPTRAG-META-END */

Action in scene one - updated.

CHARACTER_A
Dialogue in scene one - updated.

INT. NEW SCENE INSERTED - MORNING

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-02T00:00:00", "version": 2}
SCRIPTRAG-META-END */

This is a newly inserted scene.

CHARACTER_C
New character dialogue.

INT. SCENE TWO - NIGHT

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-02T00:00:00", "version": 2}
SCRIPTRAG-META-END */

Action in scene two.

CHARACTER_B
Dialogue in scene two.

INT. SCENE THREE - DAY

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-02T00:00:00", "version": 2}
SCRIPTRAG-META-END */

Action in scene three.

CHARACTER_A
Dialogue in scene three.
"""
    script_path.write_text(content)


def create_script_v3_with_removal(script_path: Path):
    """Create version 3 with the middle scene removed."""
    content = """Title: Test Script
Author: Test Author

INT. SCENE ONE - DAY

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-03T00:00:00", "version": 3}
SCRIPTRAG-META-END */

Action in scene one - updated again.

CHARACTER_A
Dialogue in scene one - updated again.

INT. SCENE THREE - DAY

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-03T00:00:00", "version": 3}
SCRIPTRAG-META-END */

Action in scene three - now scene two.

CHARACTER_A
Dialogue in scene three - now scene two.
"""
    script_path.write_text(content)


def create_script_v4_reordered(script_path: Path):
    """Create version 4 with scenes reordered."""
    content = """Title: Test Script
Author: Test Author

INT. SCENE THREE - DAY

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-04T00:00:00", "version": 4}
SCRIPTRAG-META-END */

Scene three is now first.

CHARACTER_A
Dialogue from former scene three.

INT. SCENE ONE - DAY

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-04T00:00:00", "version": 4}
SCRIPTRAG-META-END */

Scene one is now second.

CHARACTER_A
Dialogue from former scene one.

INT. SCENE TWO - NIGHT

/* SCRIPTRAG-META-START
{"analyzed_at": "2024-01-04T00:00:00", "version": 4}
SCRIPTRAG-META-END */

Scene two is now third.

CHARACTER_B
Dialogue from former scene two.
"""
    script_path.write_text(content)


def query_scenes(db_path: Path) -> list[tuple]:
    """Query all scenes from the database."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("""
        SELECT scene_number, heading, content
        FROM scenes
        ORDER BY scene_number
    """)
    results = cursor.fetchall()
    conn.close()
    return results


def query_characters(db_path: Path) -> list[str]:
    """Query all character names from the database."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT name FROM characters ORDER BY name")
    results = [row[0] for row in cursor.fetchall()]
    conn.close()
    return results


@pytest.mark.asyncio
class TestSceneIndexUpdates:
    """Test scene index updates when scripts are modified."""

    async def test_initial_indexing(self, index_command, temp_db, tmp_path):
        """Test that initial indexing works correctly."""
        script_path = tmp_path / "test.fountain"
        create_script_v1(script_path)

        # Index the script
        result = await index_command.index(path=tmp_path)

        assert result.total_scripts_indexed == 1
        assert result.total_scenes_indexed == 3

        # Verify scenes in database
        scenes = query_scenes(temp_db)
        assert len(scenes) == 3
        assert scenes[0][1] == "INT. SCENE ONE - DAY"
        assert scenes[1][1] == "INT. SCENE TWO - NIGHT"
        assert scenes[2][1] == "INT. SCENE THREE - DAY"

        # Verify characters
        characters = query_characters(temp_db)
        assert set(characters) == {"CHARACTER_A", "CHARACTER_B"}

    async def test_scene_insertion(self, index_command, temp_db, tmp_path):
        """Test that inserting a new scene updates the index correctly."""
        script_path = tmp_path / "test.fountain"

        # Initial index
        create_script_v1(script_path)
        await index_command.index(path=tmp_path)

        # Update script with inserted scene
        create_script_v2_with_insertion(script_path)
        result = await index_command.index(path=tmp_path)

        assert result.total_scripts_updated == 1
        assert result.total_scenes_indexed == 4

        # Verify scenes in database
        scenes = query_scenes(temp_db)
        assert len(scenes) == 4
        assert scenes[0][1] == "INT. SCENE ONE - DAY"
        assert scenes[1][1] == "INT. NEW SCENE INSERTED - MORNING"
        assert scenes[2][1] == "INT. SCENE TWO - NIGHT"
        assert scenes[3][1] == "INT. SCENE THREE - DAY"

        # Verify new character was added
        characters = query_characters(temp_db)
        assert "CHARACTER_C" in characters

        # Verify scene numbers are correct
        assert scenes[0][0] == 1  # Scene one is still number 1
        assert scenes[1][0] == 2  # New scene is number 2
        assert scenes[2][0] == 3  # Scene two is now number 3
        assert scenes[3][0] == 4  # Scene three is now number 4

    async def test_scene_removal(self, index_command, temp_db, tmp_path):
        """Test that removing a scene updates the index correctly."""
        script_path = tmp_path / "test.fountain"

        # Start with v2 (4 scenes)
        create_script_v2_with_insertion(script_path)
        await index_command.index(path=tmp_path)

        # Verify initial state
        scenes_before = query_scenes(temp_db)
        assert len(scenes_before) == 4

        # Update to v3 (2 scenes) - without force flag to verify it works by default
        create_script_v3_with_removal(script_path)
        result = await index_command.index(path=tmp_path)

        assert result.total_scripts_updated == 1
        assert result.total_scenes_indexed == 2

        # Verify scenes in database
        scenes = query_scenes(temp_db)
        assert len(scenes) == 2
        assert scenes[0][1] == "INT. SCENE ONE - DAY"
        assert scenes[1][1] == "INT. SCENE THREE - DAY"

        # Verify scene numbers are updated
        assert scenes[0][0] == 1  # First scene is number 1
        assert scenes[1][0] == 2  # Second scene is now number 2 (was 3)

        # Verify removed character is gone
        characters = query_characters(temp_db)
        assert "CHARACTER_C" not in characters
        assert "CHARACTER_B" not in characters  # Also removed with scene two

    async def test_scene_reordering(self, index_command, temp_db, tmp_path):
        """Test that reordering scenes updates the index correctly."""
        script_path = tmp_path / "test.fountain"

        # Initial index
        create_script_v1(script_path)
        await index_command.index(path=tmp_path)

        # Reorder scenes
        create_script_v4_reordered(script_path)
        result = await index_command.index(path=tmp_path)

        assert result.total_scripts_updated == 1
        assert result.total_scenes_indexed == 3

        # Verify scenes in database with new order
        scenes = query_scenes(temp_db)
        assert len(scenes) == 3
        assert scenes[0][1] == "INT. SCENE THREE - DAY"
        assert scenes[1][1] == "INT. SCENE ONE - DAY"
        assert scenes[2][1] == "INT. SCENE TWO - NIGHT"

        # Verify scene numbers reflect new order
        assert scenes[0][0] == 1  # Former scene 3 is now 1
        assert scenes[1][0] == 2  # Former scene 1 is now 2
        assert scenes[2][0] == 3  # Former scene 2 is now 3

        # Verify content matches reordered scenes
        assert "Scene three is now first" in scenes[0][2]
        assert "Scene one is now second" in scenes[1][2]
        assert "Scene two is now third" in scenes[2][2]

    async def test_no_stale_scenes_after_removal(
        self, index_command, temp_db, tmp_path
    ):
        """Test that old scenes don't remain in database after removal."""
        script_path = tmp_path / "test.fountain"

        # Start with 4 scenes
        create_script_v2_with_insertion(script_path)
        await index_command.index(path=tmp_path)

        # Query all scene IDs before update
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT id, heading FROM scenes ORDER BY scene_number")
        scenes_before = cursor.fetchall()
        conn.close()
        assert len(scenes_before) == 4

        # Reduce to 2 scenes
        create_script_v3_with_removal(script_path)
        await index_command.index(path=tmp_path)

        # Query all scenes after update
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT id, heading FROM scenes ORDER BY scene_number")
        scenes_after = cursor.fetchall()
        conn.close()

        # Should only have 2 scenes, no stale data
        assert len(scenes_after) == 2

        # Verify no orphaned dialogues or actions
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT COUNT(*) FROM dialogues")
        dialogue_count = cursor.fetchone()[0]
        cursor = conn.execute("SELECT COUNT(*) FROM actions")
        action_count = cursor.fetchone()[0]
        conn.close()

        # Should only have dialogues/actions for remaining 2 scenes
        assert dialogue_count == 2  # One dialogue per remaining scene
        assert action_count == 2  # One action per remaining scene

    async def test_multiple_rapid_updates(self, index_command, temp_db, tmp_path):
        """Test that multiple rapid updates don't cause inconsistencies."""
        script_path = tmp_path / "test.fountain"

        # Cycle through all versions
        create_script_v1(script_path)
        await index_command.index(path=tmp_path)

        create_script_v2_with_insertion(script_path)
        await index_command.index(path=tmp_path)

        create_script_v3_with_removal(script_path)
        await index_command.index(path=tmp_path)

        create_script_v4_reordered(script_path)
        await index_command.index(path=tmp_path)

        # Final state should match v4
        scenes = query_scenes(temp_db)
        assert len(scenes) == 3
        assert scenes[0][1] == "INT. SCENE THREE - DAY"
        assert scenes[1][1] == "INT. SCENE ONE - DAY"
        assert scenes[2][1] == "INT. SCENE TWO - NIGHT"

        # Verify no duplicate scripts
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT COUNT(*) FROM scripts")
        script_count = cursor.fetchone()[0]
        conn.close()
        assert script_count == 1

    async def test_scene_updates_without_force(self, index_command, temp_db, tmp_path):
        """Test that scene updates now work correctly without force flag."""
        script_path = tmp_path / "test.fountain"

        # Initial index with 3 scenes
        create_script_v1(script_path)
        await index_command.index(path=tmp_path)

        # Verify initial state
        scenes = query_scenes(temp_db)
        assert len(scenes) == 3
        assert scenes[0][1] == "INT. SCENE ONE - DAY"
        assert scenes[1][1] == "INT. SCENE TWO - NIGHT"
        assert scenes[2][1] == "INT. SCENE THREE - DAY"

        # Update to v2 with inserted scene WITHOUT force flag
        create_script_v2_with_insertion(script_path)
        result = await index_command.index(path=tmp_path)

        # Now it should update automatically without force
        assert result.total_scripts_updated == 1
        assert result.total_scenes_indexed == 4

        # The database should have the new data
        scenes = query_scenes(temp_db)
        assert len(scenes) == 4  # Now has 4 scenes
        assert scenes[1][1] == "INT. NEW SCENE INSERTED - MORNING"

        # Verify the force flag still works (for backward compatibility)
        create_script_v3_with_removal(script_path)
        result = await index_command.index(path=tmp_path)
        assert result.total_scripts_updated == 1

        # Should now have 2 scenes
        scenes = query_scenes(temp_db)
        assert len(scenes) == 2

    async def test_scene_content_hash_updates(self, index_command, temp_db, tmp_path):
        """Test that scene content hashes are properly updated."""
        script_path = tmp_path / "test.fountain"

        # Initial index
        create_script_v1(script_path)
        await index_command.index(path=tmp_path)

        # Get initial content hashes
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("""
            SELECT scene_number, metadata
            FROM scenes
            ORDER BY scene_number
        """)
        import json

        initial_hashes = {}
        for row in cursor.fetchall():
            metadata = json.loads(row[1]) if row[1] else {}
            initial_hashes[row[0]] = metadata.get("content_hash")
        conn.close()

        # Update with modified content
        create_script_v2_with_insertion(script_path)
        await index_command.index(path=tmp_path)

        # Get updated content hashes
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("""
            SELECT scene_number, heading, metadata
            FROM scenes
            ORDER BY scene_number
        """)
        for row in cursor.fetchall():
            metadata = json.loads(row[2]) if row[2] else {}
            new_hash = metadata.get("content_hash")

            # Scene 1 content changed, so hash should be different
            if row[1] == "INT. SCENE ONE - DAY":
                assert new_hash != initial_hashes.get(1)

            # New scene should have a hash
            if row[1] == "INT. NEW SCENE INSERTED - MORNING":
                assert new_hash is not None
        conn.close()
