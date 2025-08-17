"""Tests for search engine."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import DatabaseError
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import SearchMode, SearchQuery


class TestSearchEngine:
    """Test search engine functionality."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary test database."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        # Create minimal test schema
        conn.executescript("""
            CREATE TABLE scripts (
                id INTEGER PRIMARY KEY,
                title TEXT,
                author TEXT,
                metadata TEXT
            );

            CREATE TABLE scenes (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                number INTEGER,
                heading TEXT,
                location TEXT,
                time TEXT,
                content TEXT,
                FOREIGN KEY (script_id) REFERENCES scripts(id)
            );

            INSERT INTO scripts (id, title, author, metadata) VALUES
                (1, 'Test Script', 'Test Author', '{"season": 1, "episode": 1}'),
                (2, 'Another Script', 'Other Author', '{"invalid_json');

            INSERT INTO scenes (id, script_id, number, heading, location, time, content)
            VALUES
                (1, 1, 1, 'INT. OFFICE - DAY', 'OFFICE', 'DAY', 'Character speaks.'),
                (2, 1, 2, 'EXT. STREET - NIGHT', 'STREET', 'NIGHT', 'Another line.'),
                (3, 2, 1, 'INT. HOME - DAY', 'HOME', 'DAY', 'Third scene.');
        """)
        conn.commit()
        conn.close()

        return db_path

    @pytest.fixture
    def settings(self, temp_db):
        """Create test settings."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = temp_db
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"
        # Add semantic search settings
        settings.search_vector_result_limit_factor = 0.5
        settings.search_vector_min_results = 5
        settings.search_vector_similarity_threshold = 0.5
        settings.search_vector_threshold = 10
        settings.llm_model_cache_ttl = 3600
        return settings

    @pytest.fixture
    def engine(self, settings):
        """Create search engine with test settings."""
        return SearchEngine(settings)

    def test_init_with_settings(self, settings):
        """Test initialization with provided settings."""
        engine = SearchEngine(settings)

        assert engine.settings == settings
        assert engine.db_path == settings.database_path
        assert engine.query_builder is not None

    def test_init_without_settings(self):
        """Test initialization without settings - uses get_settings()."""
        with patch("scriptrag.config.get_settings") as mock_get_settings:
            mock_settings = MagicMock(spec=ScriptRAGSettings)
            mock_settings.database_path = Path("/test/db.sqlite")
            # Add semantic search settings
            mock_settings.search_vector_result_limit_factor = 0.5
            mock_settings.search_vector_min_results = 5
            mock_settings.search_vector_similarity_threshold = 0.5
            mock_settings.search_vector_threshold = 10
            mock_get_settings.return_value = mock_settings

            engine = SearchEngine()

            assert engine.settings == mock_settings
            assert engine.db_path == mock_settings.database_path
            mock_get_settings.assert_called_once()

    def test_get_read_only_connection_valid(self, engine, tmp_path):
        """Test getting read-only connection with valid path."""
        # Create a valid database
        db_path = tmp_path / "valid.db"
        sqlite3.connect(db_path).close()

        engine.settings.database_path = db_path

        with patch("scriptrag.search.engine.get_read_only_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            with engine.get_read_only_connection() as conn:
                assert conn == mock_conn

            mock_get_conn.assert_called_once_with(engine.settings)

    def test_get_read_only_connection_path_traversal(self, settings):
        """Test path traversal protection."""
        # Create a mock path that simulates traversal
        mock_traversal_path = MagicMock()
        mock_traversal_path.resolve.return_value = Path("/etc/passwd")
        mock_traversal_path.parent.resolve.return_value = Path("/safe/dir")

        settings.database_path = mock_traversal_path
        engine = SearchEngine(settings)

        with (
            pytest.raises(DatabaseError, match="Invalid database path"),
            engine.get_read_only_connection(),
        ):
            pass

    def test_search_database_not_found(self, engine):
        """Test search with non-existent database."""
        # Point to non-existent database
        engine.db_path = Path("/nonexistent/db.sqlite")

        query = SearchQuery(raw_query="test", text_query="test")

        with pytest.raises(DatabaseError, match="Database not found"):
            engine.search(query)

    @patch("scriptrag.search.engine.get_read_only_connection")
    def test_search_success(self, mock_conn, engine):
        """Test successful search execution."""
        # Mock database connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "script_id": 1,
                "script_title": "Test Script",
                "script_author": "Test Author",
                "script_metadata": '{"season": 1, "episode": 1}',
                "scene_id": 1,
                "scene_number": 1,
                "scene_heading": "INT. OFFICE - DAY",
                "scene_location": "OFFICE",
                "scene_time": "DAY",
                "scene_content": "Character speaks.",
            }
        ]

        mock_count_cursor = MagicMock()
        mock_count_cursor.fetchone.return_value = {"total": 1}

        mock_db_conn = MagicMock()
        mock_db_conn.execute.side_effect = [mock_cursor, mock_count_cursor]
        mock_conn.return_value.__enter__.return_value = mock_db_conn

        # Mock query builder
        engine.query_builder.build_search_query = MagicMock(
            return_value=("SELECT * FROM test", {})
        )
        engine.query_builder.build_count_query = MagicMock(
            return_value=("SELECT COUNT(*) as total", {})
        )

        # Mock database exists but ensure path validation passes
        engine.db_path = engine.settings.database_path

        query = SearchQuery(raw_query="test", text_query="test", limit=10, offset=0)
        response = engine.search(query)

        assert len(response.results) == 1
        assert response.total_count == 1
        assert response.query == query
        assert not response.has_more
        assert response.execution_time_ms >= 0  # Allow 0 on very fast systems
        assert "sql" in response.search_methods

        result = response.results[0]
        assert result.script_id == 1
        assert result.script_title == "Test Script"
        assert result.scene_id == 1
        assert result.season == 1
        assert result.episode == 1
        assert result.match_type == "text"

    @patch("scriptrag.search.engine.get_read_only_connection")
    def test_search_with_invalid_metadata(self, mock_conn, engine):
        """Test search with invalid JSON metadata."""
        # Mock database connection with invalid JSON metadata
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "script_id": 1,
                "script_title": "Test Script",
                "script_author": "Test Author",
                "script_metadata": '{"invalid_json',  # Invalid JSON
                "scene_id": 1,
                "scene_number": 1,
                "scene_heading": "INT. OFFICE - DAY",
                "scene_location": "OFFICE",
                "scene_time": "DAY",
                "scene_content": "Character speaks.",
            }
        ]

        mock_count_cursor = MagicMock()
        mock_count_cursor.fetchone.return_value = {"total": 1}

        mock_db_conn = MagicMock()
        mock_db_conn.execute.side_effect = [mock_cursor, mock_count_cursor]
        mock_conn.return_value.__enter__.return_value = mock_db_conn

        # Mock query builder
        engine.query_builder.build_search_query = MagicMock(
            return_value=("SELECT * FROM test", {})
        )
        engine.query_builder.build_count_query = MagicMock(
            return_value=("SELECT COUNT(*) as total", {})
        )

        # Mock database exists but ensure path validation passes
        engine.db_path = engine.settings.database_path

        query = SearchQuery(raw_query="test", text_query="test")

        with patch("scriptrag.search.engine.logger") as mock_logger:
            response = engine.search(query)

            # Should log warning but continue
            mock_logger.warning.assert_called()

            # Result should have empty metadata
            result = response.results[0]
            assert result.season is None
            assert result.episode is None

    @patch("scriptrag.search.engine.get_read_only_connection")
    def test_search_with_vector_search_needed(self, mock_conn, engine):
        """Test search when vector search is needed."""
        # Mock database connection
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_count_cursor = MagicMock()
        mock_count_cursor.fetchone.return_value = {"total": 0}

        mock_db_conn = MagicMock()
        mock_db_conn.execute.side_effect = [mock_cursor, mock_count_cursor]
        mock_conn.return_value.__enter__.return_value = mock_db_conn

        # Mock query builder
        engine.query_builder.build_search_query = MagicMock(
            return_value=("SELECT * FROM test", {})
        )
        engine.query_builder.build_count_query = MagicMock(
            return_value=("SELECT COUNT(*) as total", {})
        )

        # Mock database exists but ensure path validation passes
        engine.db_path = engine.settings.database_path

        # Query that needs vector search (force fuzzy mode)
        query = SearchQuery(raw_query="test", text_query="test", mode=SearchMode.FUZZY)

        with patch("scriptrag.search.engine.logger") as mock_logger:
            response = engine.search(query)

            # Should include vector in search methods and log info
            assert "semantic" in response.search_methods
            assert "sql" in response.search_methods
            mock_logger.info.assert_called()

    def test_determine_match_type_dialogue(self, engine):
        """Test match type determination for dialogue queries."""
        query = SearchQuery(raw_query="dialogue:Hello", dialogue="Hello")
        match_type = engine._determine_match_type(query)
        assert match_type == "dialogue"

    def test_determine_match_type_action(self, engine):
        """Test match type determination for action queries."""
        query = SearchQuery(raw_query="action:runs", action="runs")
        match_type = engine._determine_match_type(query)
        assert match_type == "action"

    def test_determine_match_type_text(self, engine):
        """Test match type determination for text queries."""
        query = SearchQuery(raw_query="something", text_query="something")
        match_type = engine._determine_match_type(query)
        assert match_type == "text"

    @patch("scriptrag.search.engine.get_read_only_connection")
    def test_search_with_invalid_metadata_json_warning(self, mock_conn, engine):
        """Test search with invalid metadata JSON logs warning."""
        # Mock database connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "script_id": 2,
                "script_title": "Another Script",
                "script_author": "Other Author",
                "script_metadata": '{"invalid_json',  # Invalid JSON
                "scene_id": 1,
                "scene_number": 1,
                "scene_heading": "INT. OFFICE - DAY",
                "scene_location": "OFFICE",
                "scene_time": "DAY",
                "scene_content": "Character speaks.",
            }
        ]

        mock_count_cursor = MagicMock()
        mock_count_cursor.fetchone.return_value = {"total": 1}

        mock_db_conn = MagicMock()
        mock_db_conn.execute.side_effect = [mock_cursor, mock_count_cursor]
        mock_conn.return_value.__enter__.return_value = mock_db_conn

        # Mock query builder
        engine.query_builder.build_search_query = MagicMock(
            return_value=("SELECT * FROM test", {})
        )
        engine.query_builder.build_count_query = MagicMock(
            return_value=("SELECT COUNT(*) as total", {})
        )

        # Mock database exists but ensure path validation passes
        engine.db_path = engine.settings.database_path

        query = SearchQuery(raw_query="test", text_query="test")

        with patch("scriptrag.search.engine.logger") as mock_logger:
            response = engine.search(query)

            # Should log warning about invalid JSON
            mock_logger.warning.assert_called()
            warning_call = mock_logger.warning.call_args[0][0]
            assert "Failed to parse metadata" in warning_call

            # Result should have None metadata values
            result = response.results[0]
            assert result.season is None
            assert result.episode is None

    def test_determine_match_type_character(self, engine):
        """Test match type determination for character queries."""
        query = SearchQuery(raw_query="character:ALICE", characters=["ALICE"])
        match_type = engine._determine_match_type(query)
        assert match_type == "character"

    def test_determine_match_type_location(self, engine):
        """Test match type determination for location queries."""
        query = SearchQuery(raw_query="location:OFFICE", locations=["OFFICE"])
        match_type = engine._determine_match_type(query)
        assert match_type == "location"

    def test_determine_match_type_default(self, engine):
        """Test match type determination fallback."""
        query = SearchQuery(raw_query="")
        match_type = engine._determine_match_type(query)
        assert match_type == "text"
