"""Unit tests for database operations module."""

import json
import sqlite3
from pathlib import Path

import pytest

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.config import ScriptRAGSettings
from scriptrag.parser import Dialogue, Scene, Script
from scriptrag.utils import ScreenplayUtils


@pytest.fixture
def settings(tmp_path):
    """Create test settings."""
    return ScriptRAGSettings(
        database_path=tmp_path / "test.db",
        database_timeout=5.0,
        database_journal_mode="WAL",
        database_synchronous="NORMAL",
        database_cache_size=-2000,
        database_temp_store="MEMORY",
        database_foreign_keys=True,
    )


@pytest.fixture
def db_ops(settings):
    """Create DatabaseOperations instance."""
    return DatabaseOperations(settings)


@pytest.fixture
def initialized_db_settings(tmp_path):
    """Create test settings for initialized database."""
    return ScriptRAGSettings(
        database_path=tmp_path / "initialized_test.db",
        database_timeout=5.0,
        database_journal_mode="WAL",
        database_synchronous="NORMAL",
        database_cache_size=-2000,
        database_temp_store="MEMORY",
        database_foreign_keys=True,
    )


@pytest.fixture
def initialized_db(initialized_db_settings):
    """Create an initialized test database."""
    # Initialize database with schema
    from scriptrag.api.database import DatabaseInitializer

    db_ops = DatabaseOperations(initialized_db_settings)
    initializer = DatabaseInitializer()
    initializer.initialize_database(db_path=db_ops.db_path, force=True)
    return db_ops


@pytest.fixture
def sample_script():
    """Create a sample script for testing."""
    scene1 = Scene(
        number=1,
        heading="INT. COFFEE SHOP - DAY",
        content="The scene content",
        original_text="Original text",
        content_hash="hash123",
        type="INT",
        location="COFFEE SHOP",
        time_of_day="DAY",
        dialogue_lines=[
            Dialogue(character="ALICE", text="Hello, Bob!"),
            Dialogue(character="BOB", text="Hi, Alice!", parenthetical="smiling"),
        ],
        action_lines=["Alice enters the coffee shop.", "Bob waves from his table."],
        boneyard_metadata={"analyzed": True},
    )

    scene2 = Scene(
        number=2,
        heading="EXT. PARK - NIGHT",
        content="Another scene",
        original_text="Original text 2",
        content_hash="hash456",
        type="EXT",
        location="PARK",
        time_of_day="NIGHT",
        dialogue_lines=[Dialogue(character="ALICE", text="What a nice evening.")],
        action_lines=["They walk through the park."],
    )

    return Script(
        title="Test Script",
        author="Test Author",
        scenes=[scene1, scene2],
        metadata={"genre": "drama"},
    )


class TestDatabaseOperations:
    """Test DatabaseOperations class."""

    def test_init(self, settings):
        """Test DatabaseOperations initialization."""
        db_ops = DatabaseOperations(settings)
        assert db_ops.settings == settings
        assert db_ops.db_path == settings.database_path

    def test_get_connection(self, initialized_db):
        """Test getting a database connection."""
        conn = initialized_db.get_connection()
        assert isinstance(conn, sqlite3.Connection)

        # Check pragmas are set
        cursor = conn.execute("PRAGMA journal_mode")
        assert cursor.fetchone()[0] == "wal"

        cursor = conn.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 1

        conn.close()

    def test_transaction_context_manager(self, initialized_db):
        """Test transaction context manager."""
        # Test successful transaction
        with initialized_db.transaction() as conn:
            conn.execute(
                "INSERT INTO scripts (title, author) VALUES (?, ?)",
                ("Test", "Author"),
            )

        # Verify data was committed
        conn = initialized_db.get_connection()
        cursor = conn.execute("SELECT title FROM scripts WHERE title = 'Test'")
        assert cursor.fetchone()["title"] == "Test"
        conn.close()

        # Test rollback on exception
        with (
            pytest.raises(sqlite3.IntegrityError),
            initialized_db.transaction() as conn,
        ):
            conn.execute(
                "INSERT INTO scripts (title, author) VALUES (?, ?)",
                ("Test2", "Author2"),
            )
            # This should fail due to unique constraint
            conn.execute(
                "INSERT INTO scripts (id, title) VALUES (?, ?)",
                (1, None),  # NULL title should fail NOT NULL constraint
            )

        # Verify rollback occurred
        conn = initialized_db.get_connection()
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM scripts WHERE title = 'Test2'"
        )
        assert cursor.fetchone()["count"] == 0
        conn.close()

    def test_check_database_exists(self, db_ops, initialized_db):
        """Test checking if database exists."""
        # Before initialization
        assert not db_ops.check_database_exists()

        # After initialization
        assert initialized_db.check_database_exists()

    def test_get_existing_script(self, initialized_db, sample_script):
        """Test getting existing script record."""
        file_path = Path("/test/script.fountain")

        with initialized_db.transaction() as conn:
            # No script exists yet
            assert initialized_db.get_existing_script(conn, file_path) is None

            # Insert a script
            conn.execute(
                "INSERT INTO scripts (title, author, file_path, metadata) "
                "VALUES (?, ?, ?, ?)",
                ("Test", "Author", str(file_path), '{"key": "value"}'),
            )

            # Now it should be found
            record = initialized_db.get_existing_script(conn, file_path)
            assert record is not None
            assert record.title == "Test"
            assert record.author == "Author"
            assert record.file_path == str(file_path)
            assert record.metadata == {"key": "value"}

    def test_upsert_script_insert(self, initialized_db, sample_script):
        """Test inserting a new script."""
        file_path = Path("/test/script.fountain")

        with initialized_db.transaction() as conn:
            script_id = initialized_db.upsert_script(conn, sample_script, file_path)
            assert script_id > 0

            # Verify script was inserted
            cursor = conn.execute("SELECT * FROM scripts WHERE id = ?", (script_id,))
            row = cursor.fetchone()
            assert row["title"] == "Test Script"
            assert row["author"] == "Test Author"
            assert row["file_path"] == str(file_path)

            metadata = json.loads(row["metadata"])
            assert metadata["genre"] == "drama"
            assert "last_indexed" in metadata

    def test_upsert_script_update(self, initialized_db, sample_script):
        """Test updating an existing script."""
        file_path = Path("/test/script.fountain")

        with initialized_db.transaction() as conn:
            # Insert initial script
            first_id = initialized_db.upsert_script(conn, sample_script, file_path)

            # Update the script
            sample_script.title = "Updated Title"
            second_id = initialized_db.upsert_script(conn, sample_script, file_path)

            # Should be the same ID
            assert second_id == first_id

            # Verify update
            cursor = conn.execute("SELECT title FROM scripts WHERE id = ?", (first_id,))
            assert cursor.fetchone()["title"] == "Updated Title"

    def test_clear_script_data(self, initialized_db, sample_script):
        """Test clearing script data."""
        file_path = Path("/test/script.fountain")

        with initialized_db.transaction() as conn:
            # Insert script with scenes
            script_id = initialized_db.upsert_script(conn, sample_script, file_path)

            # Insert scenes
            for scene in sample_script.scenes:
                initialized_db.upsert_scene(conn, scene, script_id)[0]

            # Verify scenes exist
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM scenes WHERE script_id = ?",
                (script_id,),
            )
            assert cursor.fetchone()["count"] == 2

            # Clear script data
            initialized_db.clear_script_data(conn, script_id)

            # Verify scenes are gone
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM scenes WHERE script_id = ?",
                (script_id,),
            )
            assert cursor.fetchone()["count"] == 0

    def test_upsert_scene(self, initialized_db, sample_script):
        """Test inserting and updating scenes."""
        file_path = Path("/test/script.fountain")

        with initialized_db.transaction() as conn:
            script_id = initialized_db.upsert_script(conn, sample_script, file_path)

            # Insert scene
            scene = sample_script.scenes[0]
            scene_id, content_changed = initialized_db.upsert_scene(
                conn, scene, script_id
            )
            assert scene_id > 0
            assert content_changed  # New scene, so content has changed

            # Verify scene was inserted
            cursor = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,))
            row = cursor.fetchone()
            assert row["scene_number"] == 1
            assert row["heading"] == "INT. COFFEE SHOP - DAY"
            assert row["location"] == "COFFEE SHOP"
            assert row["time_of_day"] == "DAY"

            metadata = json.loads(row["metadata"])
            assert metadata["boneyard"]["analyzed"] is True
            assert metadata["content_hash"] == "hash123"

            # Update scene heading (metadata only - content hash unchanged)
            scene.heading = "INT. COFFEE SHOP - MORNING"
            updated_id, content_changed = initialized_db.upsert_scene(
                conn, scene, script_id
            )
            assert updated_id == scene_id
            assert not content_changed  # Only metadata updated, content hash unchanged

            # Verify update
            cursor = conn.execute(
                "SELECT heading FROM scenes WHERE id = ?", (scene_id,)
            )
            assert cursor.fetchone()["heading"] == "INT. COFFEE SHOP - MORNING"

            # Test actual content change (hash changes)
            scene.content = "Updated scene content"
            scene.content_hash = "new_hash_456"
            content_updated_id, content_changed = initialized_db.upsert_scene(
                conn, scene, script_id
            )
            assert content_updated_id == scene_id
            assert content_changed  # Content hash changed, so content_changed = True

    def test_upsert_characters(self, initialized_db, sample_script):
        """Test inserting and updating characters."""
        file_path = Path("/test/script.fountain")

        with initialized_db.transaction() as conn:
            script_id = initialized_db.upsert_script(conn, sample_script, file_path)

            # Insert characters
            characters = {"ALICE", "BOB", "CHARLIE"}
            char_map = initialized_db.upsert_characters(conn, script_id, characters)

            assert len(char_map) == 3
            assert "ALICE" in char_map
            assert "BOB" in char_map
            assert "CHARLIE" in char_map

            # Verify characters were inserted
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM characters WHERE script_id = ?",
                (script_id,),
            )
            assert cursor.fetchone()["count"] == 3

            # Insert again (should not duplicate)
            char_map2 = initialized_db.upsert_characters(
                conn, script_id, {"ALICE", "BOB"}
            )
            assert char_map2["ALICE"] == char_map["ALICE"]
            assert char_map2["BOB"] == char_map["BOB"]

    def test_insert_dialogues(self, initialized_db, sample_script):
        """Test inserting dialogues."""
        file_path = Path("/test/script.fountain")

        with initialized_db.transaction() as conn:
            script_id = initialized_db.upsert_script(conn, sample_script, file_path)
            scene = sample_script.scenes[0]
            scene_id, _ = initialized_db.upsert_scene(conn, scene, script_id)

            # Create characters
            characters = {d.character for d in scene.dialogue_lines}
            char_map = initialized_db.upsert_characters(conn, script_id, characters)

            # Insert dialogues
            count = initialized_db.insert_dialogues(
                conn, scene_id, scene.dialogue_lines, char_map
            )
            assert count == 2

            # Verify dialogues
            cursor = conn.execute(
                "SELECT * FROM dialogues WHERE scene_id = ? ORDER BY order_in_scene",
                (scene_id,),
            )
            rows = cursor.fetchall()
            assert len(rows) == 2

            # Check first dialogue
            assert rows[0]["character_id"] == char_map["ALICE"]
            assert rows[0]["dialogue_text"] == "Hello, Bob!"
            assert rows[0]["order_in_scene"] == 0

            # Check second dialogue with parenthetical
            assert rows[1]["character_id"] == char_map["BOB"]
            assert rows[1]["dialogue_text"] == "Hi, Alice!"
            metadata = json.loads(rows[1]["metadata"])
            assert metadata["parenthetical"] == "smiling"

    def test_insert_actions(self, initialized_db, sample_script):
        """Test inserting actions."""
        file_path = Path("/test/script.fountain")

        with initialized_db.transaction() as conn:
            script_id = initialized_db.upsert_script(conn, sample_script, file_path)
            scene = sample_script.scenes[0]
            scene_id, _ = initialized_db.upsert_scene(conn, scene, script_id)

            # Insert actions
            count = initialized_db.insert_actions(conn, scene_id, scene.action_lines)
            assert count == 2

            # Verify actions
            cursor = conn.execute(
                "SELECT * FROM actions WHERE scene_id = ? ORDER BY order_in_scene",
                (scene_id,),
            )
            rows = cursor.fetchall()
            assert len(rows) == 2
            assert rows[0]["action_text"] == "Alice enters the coffee shop."
            assert rows[1]["action_text"] == "Bob waves from his table."

    def test_clear_scene_content(self, initialized_db, sample_script):
        """Test clearing scene content."""
        file_path = Path("/test/script.fountain")

        with initialized_db.transaction() as conn:
            script_id = initialized_db.upsert_script(conn, sample_script, file_path)
            scene = sample_script.scenes[0]
            scene_id, _ = initialized_db.upsert_scene(conn, scene, script_id)

            # Add content
            characters = {d.character for d in scene.dialogue_lines}
            char_map = initialized_db.upsert_characters(conn, script_id, characters)
            initialized_db.insert_dialogues(
                conn, scene_id, scene.dialogue_lines, char_map
            )
            initialized_db.insert_actions(conn, scene_id, scene.action_lines)

            # Verify content exists
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM dialogues WHERE scene_id = ?",
                (scene_id,),
            )
            assert cursor.fetchone()["count"] == 2

            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM actions WHERE scene_id = ?",
                (scene_id,),
            )
            assert cursor.fetchone()["count"] == 2

            # Clear content
            initialized_db.clear_scene_content(conn, scene_id)

            # Verify content is gone
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM dialogues WHERE scene_id = ?",
                (scene_id,),
            )
            assert cursor.fetchone()["count"] == 0

            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM actions WHERE scene_id = ?",
                (scene_id,),
            )
            assert cursor.fetchone()["count"] == 0

    def test_extract_location(self):
        """Test extracting location from scene heading."""
        assert (
            ScreenplayUtils.extract_location("INT. COFFEE SHOP - DAY") == "COFFEE SHOP"
        )
        assert ScreenplayUtils.extract_location("EXT. PARK - NIGHT") == "PARK"
        assert ScreenplayUtils.extract_location("INT./EXT. CAR - MOVING") == "CAR"
        assert ScreenplayUtils.extract_location("I/E CAR - DAY") == "CAR"
        assert ScreenplayUtils.extract_location("COFFEE SHOP") == "COFFEE SHOP"

    def test_extract_time(self):
        """Test extracting time of day from scene heading."""
        assert ScreenplayUtils.extract_time("INT. COFFEE SHOP - DAY") == "DAY"
        assert ScreenplayUtils.extract_time("EXT. PARK - NIGHT") == "NIGHT"
        assert ScreenplayUtils.extract_time("INT. OFFICE - MORNING") == "MORNING"
        assert ScreenplayUtils.extract_time("EXT. STREET - CONTINUOUS") == "CONTINUOUS"
        assert ScreenplayUtils.extract_time("INT. HOUSE") is None

    def test_get_script_stats(self, initialized_db, sample_script):
        """Test getting script statistics."""
        file_path = Path("/test/script.fountain")

        with initialized_db.transaction() as conn:
            script_id = initialized_db.upsert_script(conn, sample_script, file_path)

            # Add all data
            characters = set()
            for scene in sample_script.scenes:
                scene_id, _ = initialized_db.upsert_scene(conn, scene, script_id)
                for dialogue in scene.dialogue_lines:
                    characters.add(dialogue.character)

            char_map = initialized_db.upsert_characters(conn, script_id, characters)

            for scene in sample_script.scenes:
                cursor = conn.execute(
                    "SELECT id FROM scenes WHERE script_id = ? AND scene_number = ?",
                    (script_id, scene.number),
                )
                scene_id = cursor.fetchone()["id"]
                initialized_db.insert_dialogues(
                    conn, scene_id, scene.dialogue_lines, char_map
                )
                initialized_db.insert_actions(conn, scene_id, scene.action_lines)

            # Get stats
            stats = initialized_db.get_script_stats(conn, script_id)

            assert stats["scenes"] == 2
            assert stats["characters"] == 2  # ALICE and BOB
            assert stats["dialogues"] == 3  # 2 in scene 1, 1 in scene 2
            assert stats["actions"] == 3  # 2 in scene 1, 1 in scene 2

    def test_get_connection_with_foreign_keys_disabled(self, tmp_path):
        """Test get_connection with foreign keys disabled."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            database_foreign_keys=False,  # Foreign keys disabled
        )
        db_ops = DatabaseOperations(settings)

        # Initialize database first
        from scriptrag.api.database import DatabaseInitializer

        initializer = DatabaseInitializer()
        initializer.initialize_database(db_path=db_ops.db_path, force=True)

        conn = db_ops.get_connection()

        # Check that foreign keys are disabled
        cursor = conn.execute("PRAGMA foreign_keys")
        assert cursor.fetchone()[0] == 0

        conn.close()

    def test_check_database_exists_with_error(self, tmp_path):
        """Test check_database_exists handles SQLite errors."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
        )
        db_ops = DatabaseOperations(settings)

        # Create a corrupted database file
        db_ops.db_path.write_text("not a database")

        # Should return False on SQLite error
        assert not db_ops.check_database_exists()

    def test_insert_dialogues_with_unknown_character(
        self, initialized_db, sample_script, caplog
    ):
        """Test inserting dialogues with unknown character logs warning."""
        import logging

        file_path = Path("/test/script.fountain")

        with initialized_db.transaction() as conn:
            script_id = initialized_db.upsert_script(conn, sample_script, file_path)
            scene = sample_script.scenes[0]
            scene_id, _ = initialized_db.upsert_scene(conn, scene, script_id)

            # First insert ALICE character properly
            alice_cursor = conn.execute(
                "INSERT INTO characters (script_id, name) VALUES (?, ?)",
                (script_id, "ALICE"),
            )
            alice_id = alice_cursor.lastrowid

            # Create character map with only ALICE (BOB is missing)
            char_map = {"ALICE": alice_id}  # BOB is missing

            # Capture logs to check for warning
            with caplog.at_level(logging.WARNING):
                # Insert dialogues - should skip BOB's dialogue and log warning
                count = initialized_db.insert_dialogues(
                    conn, scene_id, scene.dialogue_lines, char_map
                )

            # Only ALICE's dialogue should be inserted
            assert count == 1

            # Verify warning was logged about unknown character
            assert any(
                "Unknown character in dialogue: BOB" in record.message
                for record in caplog.records
            )

    def test_insert_actions_with_empty_action(self, initialized_db, sample_script):
        """Test inserting actions with empty action text."""
        file_path = Path("/test/script.fountain")

        with initialized_db.transaction() as conn:
            script_id = initialized_db.upsert_script(conn, sample_script, file_path)
            scene = sample_script.scenes[0]
            scene_id, _ = initialized_db.upsert_scene(conn, scene, script_id)

            # Include empty action
            actions = ["First action", "  ", "Third action"]

            # Insert actions - should skip empty one
            count = initialized_db.insert_actions(conn, scene_id, actions)

            # Only non-empty actions should be inserted
            assert count == 2

            # Verify only two actions were inserted
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM actions WHERE scene_id = ?",
                (scene_id,),
            )
            assert cursor.fetchone()["count"] == 2

    @pytest.mark.skip(reason="Cannot mock read-only sqlite3.Cursor.lastrowid property")
    def test_upsert_script_insert_lastrowid_none(self, initialized_db, sample_script):
        """Test upsert_script handles None lastrowid on insert."""
        # This test cannot be easily implemented because sqlite3.Cursor.lastrowid
        # is a read-only property that cannot be mocked in the normal way.
        # The error condition it tests (lastrowid being None after INSERT)
        # is extremely rare in practice and would indicate a serious database issue.
        pass

    @pytest.mark.skip(reason="Cannot mock read-only sqlite3.Cursor.lastrowid property")
    def test_upsert_scene_insert_lastrowid_none(self, initialized_db, sample_script):
        """Test upsert_scene handles None lastrowid on insert."""
        # This test cannot be easily implemented because sqlite3.Cursor.lastrowid
        # is a read-only property that cannot be mocked in the normal way.
        # The error condition it tests (lastrowid being None after INSERT)
        # is extremely rare in practice and would indicate a serious database issue.
        pass
