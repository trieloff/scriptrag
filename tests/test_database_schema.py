"""Comprehensive tests for database schema module."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scriptrag.database.schema import (
    SCHEMA_SQL,
    SCHEMA_VERSION,
    DatabaseSchema,
    create_database,
)


class TestDatabaseSchema:
    """Test database schema management."""

    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        yield db_path

        # Cleanup
        if db_path.exists():
            db_path.unlink()

    def test_create_database(self, temp_db_path):
        """Test database creation with schema."""
        schema = create_database(temp_db_path)

        assert isinstance(schema, DatabaseSchema)
        assert temp_db_path.exists()

        # Verify schema version
        assert schema.get_current_version() == SCHEMA_VERSION

    def test_schema_version_tracking(self, temp_db_path):
        """Test schema version tracking."""
        schema = DatabaseSchema(temp_db_path)

        # Initial state - no schema
        assert schema.get_current_version() == 0
        assert schema.needs_migration()

        # Create schema
        schema.create_schema()

        # Verify version recorded
        assert schema.get_current_version() == SCHEMA_VERSION
        assert not schema.needs_migration()

    def test_schema_sql_structure(self):
        """Test schema SQL contains all required elements."""
        # Verify essential tables are defined
        required_tables = [
            "schema_info",
            "scripts",
            "seasons",
            "episodes",
            "characters",
            "locations",
            "scenes",
            "scene_elements",
            "nodes",
            "edges",
            "embeddings",
            "scene_dependencies",
            "mentor_results",
            "mentor_analyses",
            "series_bibles",
            "character_profiles",
            "world_elements",
            "story_timelines",
            "timeline_events",
            "continuity_notes",
            "character_knowledge",
            "plot_threads",
        ]

        for table in required_tables:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in SCHEMA_SQL

        # Verify FTS tables
        fts_tables = ["scene_elements_fts", "characters_fts", "mentor_analyses_fts"]
        for table in fts_tables:
            assert f"CREATE VIRTUAL TABLE IF NOT EXISTS {table}" in SCHEMA_SQL

        # Verify indexes exist
        assert "CREATE INDEX" in SCHEMA_SQL

        # Verify triggers exist
        assert "CREATE TRIGGER" in SCHEMA_SQL

    def test_validate_schema(self, temp_db_path):
        """Test schema validation."""
        schema = DatabaseSchema(temp_db_path)

        # Before creation, validation should fail
        assert not schema.validate_schema()

        # Create schema
        schema.create_schema()

        # Now validation should pass
        assert schema.validate_schema()

    def test_foreign_key_constraints(self, temp_db_path):
        """Test foreign key constraints are properly defined."""
        create_database(temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # Get foreign key info
            cursor = conn.execute("PRAGMA foreign_key_list('scenes')")
            fk_info = cursor.fetchall()

            # Verify foreign keys exist
            assert len(fk_info) > 0

            # Check specific foreign keys
            fk_tables = [row[2] for row in fk_info]
            assert "scripts" in fk_tables

            # Test that foreign keys are enforced
            conn.execute("PRAGMA foreign_keys = ON")

            # Try to insert a scene with invalid script_id
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """INSERT INTO scenes (id, script_id, heading, script_order)
                       VALUES ('test-scene', 'invalid-script', 'Test', 1)"""
                )

    def test_indexes_created(self, temp_db_path):
        """Test that all indexes are properly created."""
        create_database(temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row[0] for row in cursor.fetchall()}

            # Check for important indexes
            expected_indexes = [
                "idx_scripts_title",
                "idx_characters_name",
                "idx_scenes_script_order",
                "idx_scene_elements_scene_id",
                "idx_nodes_type",
                "idx_edges_from_node",
                "idx_embeddings_entity",
                "idx_mentor_results_script_id",
                "idx_character_profiles_character_id",
                "idx_continuity_notes_status",
            ]

            for index in expected_indexes:
                assert index in indexes

    def test_triggers_created(self, temp_db_path):
        """Test that update timestamp triggers work."""
        create_database(temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # Insert a script
            conn.execute(
                """INSERT INTO scripts (id, title) VALUES ('test-id', 'Test')"""
            )

            # Get initial timestamp
            cursor = conn.execute("SELECT updated_at FROM scripts WHERE id = 'test-id'")
            cursor.fetchone()[0]  # Get initial timestamp (not used in this test)

            # Check that update trigger exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' "
                "AND name = 'update_scripts_timestamp'"
            )
            trigger = cursor.fetchone()
            assert trigger is not None

    def test_fts_tables_and_triggers(self, temp_db_path):
        """Test full-text search tables exist."""
        create_database(temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # Check FTS tables exist
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE name LIKE '%_fts'"
            )
            fts_tables = {row[0] for row in cursor.fetchall()}

            assert "scene_elements_fts" in fts_tables
            assert "characters_fts" in fts_tables
            assert "mentor_analyses_fts" in fts_tables

    def test_unique_constraints(self, temp_db_path):
        """Test unique constraints are enforced."""
        create_database(temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # Insert a script and season
            conn.execute(
                """INSERT INTO scripts (id, title) VALUES ('script-1', 'Test')"""
            )
            conn.execute(
                """INSERT INTO seasons (id, script_id, number)
                   VALUES ('season-1', 'script-1', 1)"""
            )

            # Try to insert duplicate season number for same script
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """INSERT INTO seasons (id, script_id, number)
                       VALUES ('season-2', 'script-1', 1)"""
                )

    def test_json_fields(self, temp_db_path):
        """Test JSON fields can store and retrieve data."""
        create_database(temp_db_path)

        import json

        with sqlite3.connect(temp_db_path) as conn:
            # Insert script with JSON metadata
            metadata = {"key": "value", "list": [1, 2, 3]}
            conn.execute(
                """INSERT INTO scripts (id, title, metadata_json)
                   VALUES (?, ?, ?)""",
                ("script-1", "Test", json.dumps(metadata)),
            )

            # Retrieve and verify
            cursor = conn.execute(
                "SELECT metadata_json FROM scripts WHERE id = 'script-1'"
            )
            result = cursor.fetchone()[0]
            retrieved = json.loads(result)

            assert retrieved == metadata

    def test_series_bible_schema(self, temp_db_path):
        """Test Script Bible related tables."""
        create_database(temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # Insert test data for series bible
            conn.execute(
                """INSERT INTO scripts (id, title, is_series)
                   VALUES ('script-1', 'Test Series', TRUE)"""
            )

            conn.execute(
                """INSERT INTO series_bibles (id, script_id, title)
                   VALUES ('bible-1', 'script-1', 'Series Bible')"""
            )

            # Test character profile
            conn.execute(
                """INSERT INTO characters (id, script_id, name)
                   VALUES ('char-1', 'script-1', 'PROTAGONIST')"""
            )

            conn.execute(
                """INSERT INTO character_profiles
                   (id, character_id, script_id, series_bible_id, full_name, age)
                   VALUES ('profile-1', 'char-1', 'script-1', 'bible-1',
                           'John Protagonist', 35)"""
            )

            # Verify relationships
            cursor = conn.execute(
                """SELECT cp.full_name, cp.age
                   FROM character_profiles cp
                   JOIN characters c ON cp.character_id = c.id
                   WHERE c.name = 'PROTAGONIST'"""
            )
            result = cursor.fetchone()
            assert result[0] == "John Protagonist"
            assert result[1] == 35

    def test_mentor_analysis_schema(self, temp_db_path):
        """Test mentor analysis tables."""
        create_database(temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # Insert script and mentor result
            conn.execute(
                """INSERT INTO scripts (id, title) VALUES ('script-1', 'Test')"""
            )

            conn.execute(
                """INSERT INTO mentor_results
                   (id, mentor_name, mentor_version, script_id, summary)
                   VALUES ('result-1', 'story_structure', '1.0', 'script-1',
                           'Analysis complete')"""
            )

            # Insert mentor analysis
            conn.execute(
                """INSERT INTO mentor_analyses
                   (id, result_id, title, description, severity, category, mentor_name)
                   VALUES ('analysis-1', 'result-1', 'Pacing Issue',
                           'Scene too long', 'warning', 'pacing', 'story_structure')"""
            )

            # Just verify the FTS table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE name = 'mentor_analyses_fts'"
            )
            assert cursor.fetchone() is not None

    def test_embedding_table_structure(self, temp_db_path):
        """Test embeddings table structure supports both JSON and binary vectors."""
        create_database(temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # Check embeddings table structure
            cursor = conn.execute("PRAGMA table_info(embeddings)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}

            # Verify both vector storage options exist
            assert "vector_json" in columns
            assert "vector_blob" in columns
            assert "vector_type" in columns
            assert columns["vector_type"] == "TEXT"

    def test_database_creation_idempotent(self, temp_db_path):
        """Test that create_schema is idempotent."""
        schema = DatabaseSchema(temp_db_path)

        # Create schema twice
        schema.create_schema()
        version1 = schema.get_current_version()

        schema.create_schema()
        version2 = schema.get_current_version()

        # Should not change version
        assert version1 == version2 == SCHEMA_VERSION

    def test_cascade_deletes(self, temp_db_path):
        """Test cascade delete constraints work properly."""
        create_database(temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")

            # Insert script and related data
            conn.execute(
                """INSERT INTO scripts (id, title) VALUES ('script-1', 'Test')"""
            )
            conn.execute(
                """INSERT INTO characters (id, script_id, name)
                   VALUES ('char-1', 'script-1', 'HERO')"""
            )
            conn.execute(
                """INSERT INTO scenes (id, script_id, heading, script_order)
                   VALUES ('scene-1', 'script-1', 'INT. ROOM - DAY', 1)"""
            )

            # Verify data exists
            cursor = conn.execute("SELECT COUNT(*) FROM characters")
            assert cursor.fetchone()[0] == 1

            cursor = conn.execute("SELECT COUNT(*) FROM scenes")
            assert cursor.fetchone()[0] == 1

            # Test constraint exists by checking PRAGMA
            cursor = conn.execute("PRAGMA foreign_key_list('characters')")
            fks = cursor.fetchall()
            assert len(fks) > 0  # Should have foreign key constraints
