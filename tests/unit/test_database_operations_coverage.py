"""Additional tests for database operations to improve coverage."""

from pathlib import Path

import pytest

from scriptrag.api.database_operations import DatabaseOperations, ScriptRecord
from scriptrag.config import ScriptRAGSettings


class TestDatabaseOperationsCoverage:
    """Tests for database operations to improve coverage."""

    @pytest.fixture
    def initialized_db_ops(self, tmp_path):
        """Create initialized database operations."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")
        db_ops = DatabaseOperations(settings)

        # Initialize database
        from scriptrag.api.database import DatabaseInitializer

        initializer = DatabaseInitializer()
        initializer.initialize_database(db_path=db_ops.db_path, force=True)

        return db_ops

    def test_script_record_with_none_metadata(self):
        """Test ScriptRecord with None metadata."""
        record = ScriptRecord(
            id=1,
            title="Test Script",
            author="Test Author",
            file_path="/path/to/script.fountain",
            metadata=None,
        )

        assert record.id == 1
        assert record.title == "Test Script"
        assert record.author == "Test Author"
        assert record.file_path == "/path/to/script.fountain"
        assert record.metadata is None

    def test_get_existing_script_with_none_metadata(self, initialized_db_ops):
        """Test get_existing_script when metadata is None."""
        file_path = Path("/test/script.fountain")

        with initialized_db_ops.transaction() as conn:
            # Insert script with NULL metadata
            conn.execute(
                "INSERT INTO scripts (title, author, file_path, metadata) "
                "VALUES (?, ?, ?, ?)",
                ("Test", "Author", str(file_path), None),
            )

            record = initialized_db_ops.get_existing_script(conn, file_path)

            assert record is not None
            assert record.title == "Test"
            assert record.metadata is None

    def test_upsert_embedding_insert_new(self, initialized_db_ops):
        """Test inserting a new embedding."""
        with initialized_db_ops.transaction() as conn:
            # Insert a script and scene first
            cursor = conn.execute(
                "INSERT INTO scripts (title, author, file_path) VALUES (?, ?, ?)",
                ("Test Script", "Test Author", "/test/script.fountain"),
            )
            script_id = cursor.lastrowid

            cursor = conn.execute(
                "INSERT INTO scenes (script_id, scene_number, heading) "
                "VALUES (?, ?, ?)",
                (script_id, 1, "INT. ROOM - DAY"),
            )
            scene_id = cursor.lastrowid

            # Test inserting new embedding
            embedding_data = b"fake_embedding_bytes"
            embedding_id = initialized_db_ops.upsert_embedding(
                conn,
                entity_type="scene",
                entity_id=scene_id,
                embedding_model="test-model",
                embedding_data=embedding_data,
                embedding_path="path/to/embedding.npy",
            )

            assert embedding_id > 0

            # Verify embedding was inserted
            cursor = conn.execute(
                "SELECT * FROM embeddings WHERE id = ?", (embedding_id,)
            )
            row = cursor.fetchone()
            assert row["entity_type"] == "scene"
            assert row["entity_id"] == scene_id
            assert row["embedding_model"] == "test-model"
            assert row["embedding"] == embedding_data

    def test_upsert_embedding_update_existing(self, initialized_db_ops):
        """Test updating an existing embedding."""
        with initialized_db_ops.transaction() as conn:
            # Insert a script and scene first
            cursor = conn.execute(
                "INSERT INTO scripts (title, author, file_path) VALUES (?, ?, ?)",
                ("Test Script", "Test Author", "/test/script.fountain"),
            )
            script_id = cursor.lastrowid

            cursor = conn.execute(
                "INSERT INTO scenes (script_id, scene_number, heading) "
                "VALUES (?, ?, ?)",
                (script_id, 1, "INT. ROOM - DAY"),
            )
            scene_id = cursor.lastrowid

            # Insert initial embedding
            embedding_data_1 = b"original_embedding"
            embedding_id_1 = initialized_db_ops.upsert_embedding(
                conn,
                entity_type="scene",
                entity_id=scene_id,
                embedding_model="test-model",
                embedding_data=embedding_data_1,
            )

            # Update the same embedding
            embedding_data_2 = b"updated_embedding"
            embedding_id_2 = initialized_db_ops.upsert_embedding(
                conn,
                entity_type="scene",
                entity_id=scene_id,
                embedding_model="test-model",  # Same model
                embedding_data=embedding_data_2,
            )

            # Should be the same ID
            assert embedding_id_2 == embedding_id_1

            # Verify embedding was updated
            cursor = conn.execute(
                "SELECT embedding FROM embeddings WHERE id = ?", (embedding_id_1,)
            )
            row = cursor.fetchone()
            assert row["embedding"] == embedding_data_2

    def test_upsert_embedding_no_data(self, initialized_db_ops):
        """Test upserting embedding with no embedding data."""
        with initialized_db_ops.transaction() as conn:
            # Insert a script and scene first
            cursor = conn.execute(
                "INSERT INTO scripts (title, author, file_path) VALUES (?, ?, ?)",
                ("Test Script", "Test Author", "/test/script.fountain"),
            )
            script_id = cursor.lastrowid

            cursor = conn.execute(
                "INSERT INTO scenes (script_id, scene_number, heading) "
                "VALUES (?, ?, ?)",
                (script_id, 1, "INT. ROOM - DAY"),
            )
            scene_id = cursor.lastrowid

            # Test inserting embedding without data
            embedding_id = initialized_db_ops.upsert_embedding(
                conn,
                entity_type="scene",
                entity_id=scene_id,
                embedding_model="test-model",
                embedding_data=None,  # No data
                embedding_path="path/to/embedding.npy",
            )

            assert embedding_id > 0

            # Verify embedding was inserted with empty blob
            cursor = conn.execute(
                "SELECT * FROM embeddings WHERE id = ?", (embedding_id,)
            )
            row = cursor.fetchone()
            assert row["entity_type"] == "scene"
            assert row["entity_id"] == scene_id
            assert row["embedding_model"] == "test-model"
            assert row["embedding"] == b""  # Empty blob

    def test_upsert_embedding_different_models(self, initialized_db_ops):
        """Test upserting embeddings for same entity with different models."""
        with initialized_db_ops.transaction() as conn:
            # Insert a script and scene first
            cursor = conn.execute(
                "INSERT INTO scripts (title, author, file_path) VALUES (?, ?, ?)",
                ("Test Script", "Test Author", "/test/script.fountain"),
            )
            script_id = cursor.lastrowid

            cursor = conn.execute(
                "INSERT INTO scenes (script_id, scene_number, heading) "
                "VALUES (?, ?, ?)",
                (script_id, 1, "INT. ROOM - DAY"),
            )
            scene_id = cursor.lastrowid

            # Insert embedding with first model
            embedding_id_1 = initialized_db_ops.upsert_embedding(
                conn,
                entity_type="scene",
                entity_id=scene_id,
                embedding_model="model-1",
                embedding_data=b"embedding_1",
            )

            # Insert embedding with second model for same scene
            embedding_id_2 = initialized_db_ops.upsert_embedding(
                conn,
                entity_type="scene",
                entity_id=scene_id,
                embedding_model="model-2",  # Different model
                embedding_data=b"embedding_2",
            )

            # Should create different embeddings
            assert embedding_id_2 != embedding_id_1

            # Verify both embeddings exist
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM embeddings WHERE entity_type = ? "
                "AND entity_id = ?",
                ("scene", scene_id),
            )
            assert cursor.fetchone()["count"] == 2

    def test_upsert_embedding_character_entity(self, initialized_db_ops):
        """Test upserting embedding for character entity."""
        with initialized_db_ops.transaction() as conn:
            # Insert a script and character first
            cursor = conn.execute(
                "INSERT INTO scripts (title, author, file_path) VALUES (?, ?, ?)",
                ("Test Script", "Test Author", "/test/script.fountain"),
            )
            script_id = cursor.lastrowid

            cursor = conn.execute(
                "INSERT INTO characters (script_id, name) VALUES (?, ?)",
                (script_id, "ALICE"),
            )
            character_id = cursor.lastrowid

            # Test inserting embedding for character
            embedding_id = initialized_db_ops.upsert_embedding(
                conn,
                entity_type="character",
                entity_id=character_id,
                embedding_model="test-model",
                embedding_data=b"character_embedding",
            )

            assert embedding_id > 0

            # Verify embedding was inserted
            cursor = conn.execute(
                "SELECT * FROM embeddings WHERE id = ?", (embedding_id,)
            )
            row = cursor.fetchone()
            assert row["entity_type"] == "character"
            assert row["entity_id"] == character_id
            assert row["embedding_model"] == "test-model"
            assert row["embedding"] == b"character_embedding"

    def test_upsert_scene_no_boneyard_metadata(self, initialized_db_ops):
        """Test upserting scene without boneyard metadata."""
        from scriptrag.parser import Scene

        with initialized_db_ops.transaction() as conn:
            # Insert a script first
            cursor = conn.execute(
                "INSERT INTO scripts (title, author, file_path) VALUES (?, ?, ?)",
                ("Test Script", "Test Author", "/test/script.fountain"),
            )
            script_id = cursor.lastrowid

            # Create scene without boneyard metadata
            scene = Scene(
                number=1,
                heading="INT. ROOM - DAY",
                content="Scene content",
                original_text="Original text",
                content_hash="hash123",
                dialogue_lines=[],
                action_lines=[],
                boneyard_metadata=None,  # No metadata
            )

            scene_id, content_changed = initialized_db_ops.upsert_scene(
                conn, scene, script_id
            )

            assert scene_id > 0
            assert content_changed is True  # New scene

            # Verify metadata field
            cursor = conn.execute(
                "SELECT metadata FROM scenes WHERE id = ?", (scene_id,)
            )
            row = cursor.fetchone()
            import json

            metadata = json.loads(row["metadata"])
            assert "boneyard" not in metadata
            assert metadata["content_hash"] == "hash123"

    def test_upsert_scene_with_none_location_and_time(self, initialized_db_ops):
        """Test upserting scene when extracted location and time are None."""
        from unittest.mock import patch

        from scriptrag.parser import Scene

        with initialized_db_ops.transaction() as conn:
            # Insert a script first
            cursor = conn.execute(
                "INSERT INTO scripts (title, author, file_path) VALUES (?, ?, ?)",
                ("Test Script", "Test Author", "/test/script.fountain"),
            )
            script_id = cursor.lastrowid

            # Create scene with location and time_of_day as None
            scene = Scene(
                number=1,
                heading="FADE IN:",  # Heading that won't extract location/time
                content="Scene content",
                original_text="Original text",
                content_hash="hash123",
                dialogue_lines=[],
                action_lines=[],
                location=None,
                time_of_day=None,
            )

            # Mock the utility methods to return None
            with (
                patch(
                    "scriptrag.utils.ScreenplayUtils.extract_location",
                    return_value=None,
                ),
                patch(
                    "scriptrag.utils.ScreenplayUtils.extract_time", return_value=None
                ),
            ):
                scene_id, content_changed = initialized_db_ops.upsert_scene(
                    conn, scene, script_id
                )

                assert scene_id > 0
                assert content_changed is True  # New scene

                # Verify location and time are None
                cursor = conn.execute(
                    "SELECT location, time_of_day FROM scenes WHERE id = ?", (scene_id,)
                )
                row = cursor.fetchone()
                assert row["location"] is None
                assert row["time_of_day"] is None

    def test_upsert_script_with_metadata_fields(self, initialized_db_ops):
        """Test upsert script with new metadata fields (series, project, etc)."""
        import json
        from pathlib import Path

        from scriptrag.parser import Script

        script = Script(
            title="Test Episode",
            author="Writer Name",
            scenes=[],
            metadata={
                "season": 2,
                "episode": 5,
                "series_title": "Great Show",
                "project_title": "Season 2 Project",
            },
        )

        file_path = Path("/test/path.fountain")

        with initialized_db_ops.transaction() as conn:
            # Test insert with new metadata fields
            script_id = initialized_db_ops.upsert_script(conn, script, file_path)
            assert script_id is not None

            # Verify all fields were saved correctly
            cursor = conn.execute(
                """SELECT title, author, project_title, series_title,
                   season, episode, metadata FROM scripts WHERE id = ?""",
                (script_id,),
            )
            result = cursor.fetchone()
            assert result is not None
            assert result["title"] == "Test Episode"
            assert result["author"] == "Writer Name"
            assert result["project_title"] == "Season 2 Project"
            assert result["series_title"] == "Great Show"
            assert result["season"] == 2
            assert result["episode"] == 5

            # Verify metadata JSON
            metadata = json.loads(result["metadata"])
            assert "last_indexed" in metadata
            assert metadata["season"] == 2
            assert metadata["episode"] == 5

    def test_upsert_script_update_with_new_fields(self, initialized_db_ops):
        """Test updating existing script with new metadata structure."""
        from pathlib import Path

        from scriptrag.parser import Script

        file_path = Path("/test/path.fountain")

        # First script (minimal metadata)
        script1 = Script(title="Original Title", author="Original Author", scenes=[])

        with initialized_db_ops.transaction() as conn:
            # Insert original script
            script_id1 = initialized_db_ops.upsert_script(conn, script1, file_path)

            # Updated script with full metadata
            script2 = Script(
                title="Updated Title",
                author="Updated Author",
                scenes=[],
                metadata={
                    "series_title": "TV Series",
                    "project_title": "Project Name",
                    "season": 3,
                    "episode": 7,
                },
            )

            # Update the same file path
            script_id2 = initialized_db_ops.upsert_script(conn, script2, file_path)

            # Should be same script ID (update, not insert)
            assert script_id1 == script_id2

            # Verify all fields were updated
            cursor = conn.execute(
                """SELECT title, author, project_title, series_title,
                   season, episode FROM scripts WHERE id = ?""",
                (script_id2,),
            )
            result = cursor.fetchone()
            assert result is not None
            assert result["title"] == "Updated Title"
            assert result["author"] == "Updated Author"
            assert result["project_title"] == "Project Name"
            assert result["series_title"] == "TV Series"
            assert result["season"] == 3
            assert result["episode"] == 7

    def test_upsert_script_defaults_for_none_values(self, initialized_db_ops):
        """Test upsert script handles None values with safe defaults."""
        from pathlib import Path

        from scriptrag.parser import Script

        script = Script(title=None, author=None, scenes=[], metadata=None)
        file_path = Path("/test/path.fountain")

        with initialized_db_ops.transaction() as conn:
            # Test insert with None values
            script_id = initialized_db_ops.upsert_script(conn, script, file_path)
            assert script_id is not None

            # Verify defaults were applied
            cursor = conn.execute(
                "SELECT title, author, project_title FROM scripts WHERE id = ?",
                (script_id,),
            )
            result = cursor.fetchone()
            assert result is not None
            assert result["title"] == "Untitled"  # Default title
            assert result["author"] == "Unknown"  # Default author
            assert (
                result["project_title"] == "Untitled"
            )  # project_title defaults to title
