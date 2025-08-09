"""Tests for search engine."""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import SearchMode, SearchQuery, SearchResponse


class TestSearchEngine:
    """Test SearchEngine class."""

    @pytest.fixture
    def mock_settings(self, tmp_path):
        """Create mock settings."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = tmp_path / "test.db"
        settings.database_timeout = 30.0
        settings.database_cache_size = 2000
        settings.database_temp_store = "MEMORY"
        return settings

    @pytest.fixture
    def mock_db(self, tmp_path):
        """Create a mock database file."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        # Create minimal schema
        conn.execute("""
            CREATE TABLE scripts (
                id INTEGER PRIMARY KEY,
                title TEXT,
                author TEXT,
                metadata TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE scenes (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                scene_number INTEGER,
                heading TEXT,
                location TEXT,
                time_of_day TEXT,
                content TEXT,
                FOREIGN KEY (script_id) REFERENCES scripts(id)
            )
        """)

        conn.execute("""
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE dialogues (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                character_id INTEGER,
                dialogue_text TEXT,
                metadata TEXT,
                FOREIGN KEY (scene_id) REFERENCES scenes(id),
                FOREIGN KEY (character_id) REFERENCES characters(id)
            )
        """)

        conn.execute("""
            CREATE TABLE actions (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                action_text TEXT,
                FOREIGN KEY (scene_id) REFERENCES scenes(id)
            )
        """)

        # Insert test data
        conn.execute(
            "INSERT INTO scripts (id, title, author, metadata) VALUES (?, ?, ?, ?)",
            (1, "Test Script", "Test Author", '{"season": 1, "episode": 1}'),
        )

        conn.execute(
            """INSERT INTO scenes
            (id, script_id, scene_number, heading, location, time_of_day, content)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (1, 1, 1, "INT. OFFICE - DAY", "OFFICE", "DAY", "Office scene content"),
        )

        conn.execute(
            "INSERT INTO characters (id, name) VALUES (?, ?)",
            (1, "JOHN"),
        )

        conn.execute(
            """INSERT INTO dialogues
            (id, scene_id, character_id, dialogue_text, metadata)
            VALUES (?, ?, ?, ?, ?)""",
            (1, 1, 1, "Hello world", '{"parenthetical": "softly"}'),
        )

        conn.execute(
            "INSERT INTO actions (id, scene_id, action_text) VALUES (?, ?, ?)",
            (1, 1, "John enters the room"),
        )

        conn.commit()
        conn.close()

        return db_path

    def test_init(self, mock_settings):
        """Test engine initialization."""
        engine = SearchEngine(mock_settings)
        assert engine.settings == mock_settings
        assert engine.db_path == mock_settings.database_path
        assert engine.query_builder is not None

    def test_init_without_settings(self):
        """Test engine initialization without settings."""
        with patch("scriptrag.config.get_settings") as mock_get_settings:
            mock_settings = MagicMock(spec=ScriptRAGSettings)
            mock_settings.database_path = MagicMock()
            mock_get_settings.return_value = mock_settings
            engine = SearchEngine()
            assert engine.settings is not None
            mock_get_settings.assert_called_once()

    def test_get_read_only_connection(self, mock_settings, mock_db):
        """Test getting read-only database connection."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        with engine.get_read_only_connection() as conn:
            assert conn is not None
            # Try to write - should fail due to read-only mode
            with pytest.raises(sqlite3.OperationalError):
                conn.execute("INSERT INTO scripts (title) VALUES ('Test')")

    def test_get_read_only_connection_path_traversal(self, mock_settings, tmp_path):
        """Test path traversal prevention."""
        # Set expected database path to tmp_path
        safe_path = tmp_path / "safe.db"
        mock_settings.database_path = safe_path

        # Create engine with evil path that tries to escape
        engine = SearchEngine(mock_settings)
        evil_path = tmp_path / ".." / "evil.db"
        engine.db_path = evil_path  # Override with evil path

        with (
            pytest.raises(ValueError, match="Invalid database path"),
            engine.get_read_only_connection(),
        ):
            pass

    def test_search_database_not_found(self, mock_settings):
        """Test search when database doesn't exist."""
        engine = SearchEngine(mock_settings)
        query = SearchQuery(raw_query="test")

        with pytest.raises(FileNotFoundError, match="Database not found"):
            engine.search(query)

    def test_search_simple_query(self, mock_settings, mock_db):
        """Test simple search query."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(raw_query="hello", dialogue="hello")
        response = engine.search(query)

        assert isinstance(response, SearchResponse)
        assert response.total_count == 1
        assert len(response.results) == 1
        assert response.results[0].script_title == "Test Script"
        assert response.results[0].scene_heading == "INT. OFFICE - DAY"

    def test_search_with_json_metadata(self, mock_settings, mock_db):
        """Test search with JSON metadata parsing."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(raw_query="hello", dialogue="hello")
        response = engine.search(query)

        assert response.results[0].season == 1
        assert response.results[0].episode == 1

    def test_search_with_invalid_json_metadata(self, mock_settings, tmp_path):
        """Test search with invalid JSON metadata."""
        # Create database with invalid JSON
        db_path = tmp_path / "invalid.db"
        conn = sqlite3.connect(str(db_path))

        conn.execute("""
            CREATE TABLE scripts (
                id INTEGER PRIMARY KEY,
                title TEXT,
                author TEXT,
                metadata TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE scenes (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                scene_number INTEGER,
                heading TEXT,
                location TEXT,
                time_of_day TEXT,
                content TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE dialogues (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                character_id INTEGER,
                dialogue_text TEXT,
                metadata TEXT,
                FOREIGN KEY (scene_id) REFERENCES scenes(id),
                FOREIGN KEY (character_id) REFERENCES characters(id)
            )
        """)

        conn.execute("""
            CREATE TABLE actions (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                action_text TEXT,
                FOREIGN KEY (scene_id) REFERENCES scenes(id)
            )
        """)

        # Insert invalid JSON
        conn.execute(
            "INSERT INTO scripts (id, title, author, metadata) VALUES (?, ?, ?, ?)",
            (1, "Test", "Author", "not valid json"),
        )

        conn.execute(
            """INSERT INTO scenes
            (id, script_id, scene_number, heading, location, time_of_day, content)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (1, 1, 1, "INT. ROOM - DAY", "ROOM", "DAY", "Content"),
        )

        conn.commit()
        conn.close()

        mock_settings.database_path = db_path
        engine = SearchEngine(mock_settings)

        query = SearchQuery(raw_query="test", text_query="content")
        response = engine.search(query)

        # Should handle invalid JSON gracefully
        assert len(response.results) == 1
        assert response.results[0].season is None
        assert response.results[0].episode is None

    def test_search_with_pagination(self, mock_settings, mock_db):
        """Test search with pagination."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(
            raw_query="hello",
            dialogue="hello",
            limit=10,
            offset=0,
        )
        response = engine.search(query)

        assert response.query.limit == 10
        assert response.query.offset == 0
        assert response.has_more is False

    def test_search_with_vector_mode(self, mock_settings, mock_db):
        """Test search with vector mode."""
        mock_settings.database_path = mock_db
        mock_settings.search_vector_threshold = 5
        engine = SearchEngine(mock_settings)

        # Long query that should trigger vector search
        long_query = "This long query has more than ten words and will trigger vector"
        query = SearchQuery(
            raw_query=long_query,
            text_query=long_query,
            mode=SearchMode.AUTO,
        )

        response = engine.search(query)

        assert "sql" in response.search_methods
        # Vector search is marked but not implemented yet
        assert "vector" in response.search_methods

    def test_determine_match_type(self, mock_settings):
        """Test match type determination."""
        engine = SearchEngine(mock_settings)

        # Dialogue match
        query = SearchQuery(raw_query="test", dialogue="hello")
        assert engine._determine_match_type(query) == "dialogue"

        # Action match
        query = SearchQuery(raw_query="test", action="fight")
        assert engine._determine_match_type(query) == "action"

        # Text match
        query = SearchQuery(raw_query="test", text_query="general")
        assert engine._determine_match_type(query) == "text"

        # Character match
        query = SearchQuery(raw_query="test", characters=["JOHN"])
        assert engine._determine_match_type(query) == "character"

        # Location match
        query = SearchQuery(raw_query="test", locations=["OFFICE"])
        assert engine._determine_match_type(query) == "location"

        # Default
        query = SearchQuery(raw_query="test")
        assert engine._determine_match_type(query) == "text"

    def test_search_no_results(self, mock_settings, mock_db):
        """Test search with no results."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(raw_query="nonexistent", dialogue="nonexistent")
        response = engine.search(query)

        assert response.total_count == 0
        assert len(response.results) == 0
        assert response.has_more is False

    def test_search_execution_time(self, mock_settings, mock_db):
        """Test that execution time is tracked."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(raw_query="test", dialogue="hello")
        response = engine.search(query)

        assert response.execution_time_ms > 0
        assert isinstance(response.execution_time_ms, float)

    @patch("scriptrag.search.engine.logger")
    def test_search_logging(self, mock_logger, mock_settings, mock_db):
        """Test that search operations are logged."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(raw_query="test", dialogue="hello")
        engine.search(query)

        # Check that appropriate logs were made
        mock_logger.debug.assert_called()
        mock_logger.info.assert_called()

    def test_search_complex_query(self, mock_settings, mock_db):
        """Test search with complex query parameters."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(
            raw_query="complex",
            dialogue="hello",
            characters=["JOHN"],
            locations=["OFFICE"],
            project="Test",
            season_start=1,
            season_end=1,
            episode_start=1,
            episode_end=1,
            mode=SearchMode.STRICT,
            limit=5,
            offset=0,
        )

        response = engine.search(query)

        assert isinstance(response, SearchResponse)
        assert response.query == query
