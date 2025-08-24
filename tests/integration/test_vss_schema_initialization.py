"""Integration tests for VSS schema initialization with foreign key validation.

These tests ensure that:
1. VSS schema initializes correctly when parent tables exist
2. Foreign key constraints are properly enforced
3. CASCADE deletion works as expected
4. Schema initialization order is correct
"""

import sqlite3
from unittest.mock import patch

import pytest

from scriptrag.api import DatabaseInitializer
from scriptrag.config import ScriptRAGSettings


class TestVSSSchemaInitialization:
    """Test VSS schema initialization with foreign key dependencies."""

    def test_vss_schema_succeeds_with_scenes_table(self, tmp_path):
        """Test that VSS schema initialization succeeds when scenes table exists."""
        settings = ScriptRAGSettings(
            _env_file=None,
            database_path=tmp_path / "test.db",
            database_foreign_keys=True,
        )

        initializer = DatabaseInitializer()
        db_path = initializer.initialize_database(settings=settings)

        # Verify tables were created
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()

            # Check that scenes table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='scenes'"
            )
            assert cursor.fetchone() is not None, "scenes table should exist"

            # Check that scene_embeddings table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='scene_embeddings'"
            )
            assert cursor.fetchone() is not None, "scene_embeddings table should exist"

            # Check that bible_chunks table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='bible_chunks'"
            )
            assert cursor.fetchone() is not None, "bible_chunks table should exist"

            # Check that bible_chunk_embeddings table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='bible_chunk_embeddings'"
            )
            assert cursor.fetchone() is not None, (
                "bible_chunk_embeddings table should exist"
            )

            # Verify foreign key constraint exists on scene_embeddings
            cursor.execute("PRAGMA foreign_key_list(scene_embeddings)")
            foreign_keys = cursor.fetchall()
            assert len(foreign_keys) > 0, "scene_embeddings should have foreign keys"

            # Check specific foreign key to scenes table
            scene_fk = [fk for fk in foreign_keys if fk[2] == "scenes"]
            assert len(scene_fk) == 1, "Should have exactly one FK to scenes table"
            assert scene_fk[0][3] == "scene_id", "FK should be on scene_id column"
            assert scene_fk[0][4] == "id", "FK should reference id column"

        finally:
            conn.close()

    def test_vss_schema_creates_without_parent_tables(self, tmp_path):
        """Test VSS schema tables can be created without parent tables.

        SQLite allows creating tables with FK constraints to non-existent tables.
        The constraint is only enforced during data insertion, not table creation.
        """
        settings = ScriptRAGSettings(
            _env_file=None,
            database_path=tmp_path / "test.db",
            database_foreign_keys=True,
        )

        # Create a custom initializer that only executes VSS schema
        initializer = DatabaseInitializer()

        # Mock to skip main schema but execute VSS schema
        # First read the actual VSS schema content
        actual_vss_schema = initializer._read_sql_file("vss_schema.sql")

        def mock_read_side_effect(filename):
            if filename == "init_database.sql":
                # Return empty schema - no tables created
                return "PRAGMA foreign_keys = ON;"
            if filename == "bible_schema.sql":
                # Return empty schema
                return "-- No bible schema"
            if filename == "vss_schema.sql":
                # Return actual VSS schema that depends on scenes
                return actual_vss_schema
            return ""

        with patch.object(initializer, "_read_sql_file") as mock_read:
            mock_read.side_effect = mock_read_side_effect

            # VSS schema creation should succeed (SQLite allows FK to missing tables)
            db_path = initializer.initialize_database(settings=settings)

            # Verify the VSS tables were created
            conn = sqlite3.connect(str(db_path))
            try:
                cursor = conn.cursor()

                # Check that scene_embeddings table exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='scene_embeddings'"
                )
                assert cursor.fetchone() is not None, (
                    "scene_embeddings table should exist"
                )

                # But inserting data should fail due to FK constraint
                cursor.execute("PRAGMA foreign_keys = ON")
                with pytest.raises(sqlite3.OperationalError) as exc_info:
                    cursor.execute(
                        "INSERT INTO scene_embeddings "
                        "(scene_id, embedding_model, embedding) VALUES (?, ?, ?)",
                        (1, "test-model", b"fake_data"),  # scene_id 1 doesn't exist
                    )

                assert "no such table" in str(exc_info.value)

            finally:
                conn.close()

    def test_cascade_deletion_from_scenes(self, tmp_path):
        """Test that CASCADE deletion works when scenes are deleted."""
        settings = ScriptRAGSettings(
            _env_file=None,
            database_path=tmp_path / "test.db",
            database_foreign_keys=True,
        )

        initializer = DatabaseInitializer()
        db_path = initializer.initialize_database(settings=settings)

        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()

            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON")

            # Insert test data
            cursor.execute(
                "INSERT INTO scripts (title, file_path) VALUES (?, ?)",
                ("Test Script", "/path/to/script.fountain"),
            )
            script_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO scenes (script_id, scene_number, heading, content) "
                "VALUES (?, ?, ?, ?)",
                (script_id, 1, "INT. HOUSE - DAY", "Test scene content"),
            )
            scene_id = cursor.lastrowid

            # Insert embedding for the scene
            cursor.execute(
                "INSERT INTO scene_embeddings (scene_id, embedding_model, embedding) "
                "VALUES (?, ?, ?)",
                (scene_id, "test-model", b"fake_embedding_data"),
            )

            conn.commit()

            # Verify embedding exists
            cursor.execute(
                "SELECT COUNT(*) FROM scene_embeddings WHERE scene_id = ?", (scene_id,)
            )
            assert cursor.fetchone()[0] == 1, "Embedding should exist"

            # Delete the scene
            cursor.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
            conn.commit()

            # Verify embedding was cascaded deleted
            cursor.execute(
                "SELECT COUNT(*) FROM scene_embeddings WHERE scene_id = ?", (scene_id,)
            )
            assert cursor.fetchone()[0] == 0, "Embedding should be deleted via CASCADE"

        finally:
            conn.close()

    def test_cascade_deletion_from_bible_chunks(self, tmp_path):
        """Test that CASCADE deletion works when bible_chunks are deleted."""
        settings = ScriptRAGSettings(
            _env_file=None,
            database_path=tmp_path / "test.db",
            database_foreign_keys=True,
        )

        initializer = DatabaseInitializer()
        db_path = initializer.initialize_database(settings=settings)

        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()

            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON")

            # Insert test data
            cursor.execute(
                "INSERT INTO scripts (title, file_path) VALUES (?, ?)",
                ("Test Script", "/path/to/script.fountain"),
            )
            script_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO script_bibles (script_id, file_path, file_hash) "
                "VALUES (?, ?, ?)",
                (script_id, "/path/to/bible.md", "hash123"),
            )
            bible_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO bible_chunks "
                "(bible_id, chunk_number, content, content_hash) "
                "VALUES (?, ?, ?, ?)",
                (bible_id, 1, "Test chunk content", "chunk_hash"),
            )
            chunk_id = cursor.lastrowid

            # Insert embedding for the bible chunk
            cursor.execute(
                "INSERT INTO bible_chunk_embeddings "
                "(chunk_id, embedding_model, embedding) VALUES (?, ?, ?)",
                (chunk_id, "test-model", b"fake_embedding_data"),
            )

            conn.commit()

            # Verify embedding exists
            cursor.execute(
                "SELECT COUNT(*) FROM bible_chunk_embeddings WHERE chunk_id = ?",
                (chunk_id,),
            )
            assert cursor.fetchone()[0] == 1, "Embedding should exist"

            # Delete the bible chunk
            cursor.execute("DELETE FROM bible_chunks WHERE id = ?", (chunk_id,))
            conn.commit()

            # Verify embedding was cascaded deleted
            cursor.execute(
                "SELECT COUNT(*) FROM bible_chunk_embeddings WHERE chunk_id = ?",
                (chunk_id,),
            )
            assert cursor.fetchone()[0] == 0, "Embedding should be deleted via CASCADE"

        finally:
            conn.close()

    def test_full_initialization_flow_order(self, tmp_path):
        """Test the complete initialization flow: main → bible → VSS schema."""
        settings = ScriptRAGSettings(
            _env_file=None,
            database_path=tmp_path / "test.db",
            database_foreign_keys=True,
        )

        initializer = DatabaseInitializer()

        # Track the order of schema execution
        execution_order = []

        original_read = initializer._read_sql_file

        def track_read(filename):
            execution_order.append(filename)
            return original_read(filename)

        with patch.object(initializer, "_read_sql_file", side_effect=track_read):
            db_path = initializer.initialize_database(settings=settings)

        # Verify execution order
        assert execution_order == [
            "init_database.sql",
            "bible_schema.sql",
            "vss_schema.sql",
        ], "Schemas should be executed in correct order"

        # Verify all tables exist and foreign keys work
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()

            # Check all expected tables exist
            expected_tables = [
                "scripts",
                "scenes",
                "characters",
                "dialogues",
                "actions",  # Main
                "script_bibles",
                "bible_chunks",  # Bible schema
                "scene_embeddings",
                "bible_chunk_embeddings",  # VSS
                "embedding_metadata",  # VSS metadata
            ]

            for table in expected_tables:
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' "
                    f"AND name='{table}'"
                )
                assert cursor.fetchone() is not None, f"{table} table should exist"

            # Test that we can insert data with foreign key constraints
            cursor.execute("PRAGMA foreign_keys = ON")

            # Insert script
            cursor.execute(
                "INSERT INTO scripts (title, file_path) VALUES (?, ?)",
                ("Test", "/test.fountain"),
            )
            script_id = cursor.lastrowid

            # Insert scene
            cursor.execute(
                "INSERT INTO scenes (script_id, scene_number, heading, content) "
                "VALUES (?, ?, ?, ?)",
                (script_id, 1, "INT. TEST", "Content"),
            )
            scene_id = cursor.lastrowid

            # Insert scene embedding (should work with foreign key)
            cursor.execute(
                "INSERT INTO scene_embeddings (scene_id, embedding_model, embedding) "
                "VALUES (?, ?, ?)",
                (scene_id, "model", b"data"),
            )

            # Insert bible
            cursor.execute(
                "INSERT INTO script_bibles (script_id, file_path, file_hash) "
                "VALUES (?, ?, ?)",
                (script_id, "/bible.md", "hash"),
            )
            bible_id = cursor.lastrowid

            # Insert bible chunk
            cursor.execute(
                "INSERT INTO bible_chunks "
                "(bible_id, chunk_number, content, content_hash) "
                "VALUES (?, ?, ?, ?)",
                (bible_id, 1, "Content", "hash"),
            )
            chunk_id = cursor.lastrowid

            # Insert bible chunk embedding (should work with foreign key)
            cursor.execute(
                "INSERT INTO bible_chunk_embeddings "
                "(chunk_id, embedding_model, embedding) VALUES (?, ?, ?)",
                (chunk_id, "model", b"data"),
            )

            conn.commit()

            # Verify all data was inserted
            cursor.execute("SELECT COUNT(*) FROM scene_embeddings")
            assert cursor.fetchone()[0] == 1

            cursor.execute("SELECT COUNT(*) FROM bible_chunk_embeddings")
            assert cursor.fetchone()[0] == 1

        finally:
            conn.close()

    def test_foreign_key_violation_prevented(self, tmp_path):
        """Test that foreign key violations are properly prevented."""
        settings = ScriptRAGSettings(
            _env_file=None,
            database_path=tmp_path / "test.db",
            database_foreign_keys=True,
        )

        initializer = DatabaseInitializer()
        db_path = initializer.initialize_database(settings=settings)

        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()

            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON")

            # Try to insert scene_embedding with non-existent scene_id
            with pytest.raises(sqlite3.IntegrityError) as exc_info:
                cursor.execute(
                    "INSERT INTO scene_embeddings "
                    "(scene_id, embedding_model, embedding) VALUES (?, ?, ?)",
                    (9999, "test-model", b"fake_data"),  # scene_id 9999 missing
                )

            assert "FOREIGN KEY constraint failed" in str(exc_info.value)

            # Try to insert bible_chunk_embedding with non-existent chunk_id
            with pytest.raises(sqlite3.IntegrityError) as exc_info:
                cursor.execute(
                    "INSERT INTO bible_chunk_embeddings "
                    "(chunk_id, embedding_model, embedding) VALUES (?, ?, ?)",
                    (9999, "test-model", b"fake_data"),  # chunk_id 9999 missing
                )

            assert "FOREIGN KEY constraint failed" in str(exc_info.value)

        finally:
            conn.close()

    def test_vss_schema_indexes_created(self, tmp_path):
        """Test that all VSS schema indexes are properly created."""
        settings = ScriptRAGSettings(
            _env_file=None,
            database_path=tmp_path / "test.db",
        )

        initializer = DatabaseInitializer()
        db_path = initializer.initialize_database(settings=settings)

        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()

            # Check for expected indexes
            expected_indexes = [
                "idx_scene_embeddings_model",
                "idx_bible_chunk_embeddings_model",
                "idx_embedding_metadata_entity",
                "idx_embedding_metadata_model",
            ]

            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            actual_indexes = {row[0] for row in cursor.fetchall()}

            for index_name in expected_indexes:
                assert index_name in actual_indexes, f"Index {index_name} should exist"

        finally:
            conn.close()

    def test_vss_schema_triggers_created(self, tmp_path):
        """Test that all VSS schema update triggers are properly created."""
        settings = ScriptRAGSettings(
            _env_file=None,
            database_path=tmp_path / "test.db",
        )

        initializer = DatabaseInitializer()
        db_path = initializer.initialize_database(settings=settings)

        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()

            # Check for expected triggers
            expected_triggers = [
                "update_scene_embeddings_timestamp",
                "update_bible_chunk_embeddings_timestamp",
                "update_embedding_metadata_timestamp",
            ]

            cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
            actual_triggers = {row[0] for row in cursor.fetchall()}

            for trigger_name in expected_triggers:
                assert trigger_name in actual_triggers, (
                    f"Trigger {trigger_name} should exist"
                )

        finally:
            conn.close()
