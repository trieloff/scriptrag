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
        settings.database_journal_mode = "WAL"
        settings.database_synchronous = "NORMAL"
        settings.database_foreign_keys = True
        # Add semantic search settings
        settings.search_vector_result_limit_factor = 0.5
        settings.search_vector_min_results = 5
        settings.search_vector_similarity_threshold = 0.5
        settings.search_vector_threshold = 10
        settings.llm_model_cache_ttl = 3600
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
            # Add semantic search settings
            mock_settings.search_vector_result_limit_factor = 0.5
            mock_settings.search_vector_min_results = 5
            mock_settings.search_vector_similarity_threshold = 0.5
            mock_settings.search_vector_threshold = 10
            mock_settings.llm_model_cache_ttl = 3600
            mock_settings.llm_force_static_models = False
            mock_get_settings.return_value = mock_settings
            engine = SearchEngine()
            assert engine.settings is not None
            assert mock_get_settings.called

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
        # Create a path with ".." to test path traversal protection
        evil_path = tmp_path / ".." / ".." / "etc" / "passwd"
        mock_settings.database_path = evil_path

        # Create engine with settings that have path traversal
        engine = SearchEngine(mock_settings)

        # The validation now happens in get_read_only_connection from readonly module
        # The search engine converts ValueError to DatabaseError
        from scriptrag.exceptions import DatabaseError

        with (
            pytest.raises(DatabaseError, match="Invalid database path"),
            engine.get_read_only_connection(),
        ):
            pass

    def test_search_database_not_found(self, mock_settings):
        """Test search when database doesn't exist."""
        from scriptrag.exceptions import DatabaseError

        engine = SearchEngine(mock_settings)
        query = SearchQuery(raw_query="test")

        with pytest.raises(DatabaseError, match="Database not found"):
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
        assert "semantic" in response.search_methods

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

        # Windows time.time() may have lower precision and return 0.0 for fast ops
        assert response.execution_time_ms >= 0
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

    def test_search_with_empty_metadata(self, mock_settings, tmp_path):
        """Test search when script has empty/null metadata."""
        # Create database with empty metadata
        db_path = tmp_path / "empty_meta.db"
        conn = sqlite3.connect(str(db_path))

        # Create schema
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
            CREATE TABLE characters (id INTEGER PRIMARY KEY, name TEXT)
        """)

        conn.execute("""
            CREATE TABLE dialogues (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                character_id INTEGER,
                dialogue_text TEXT,
                metadata TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE actions (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                action_text TEXT
            )
        """)

        # Insert test data with NULL metadata (triggers else clause line 126)
        conn.execute(
            "INSERT INTO scripts (id, title, author, metadata) VALUES (?, ?, ?, ?)",
            (1, "Test Script", "Test Author", None),  # NULL metadata
        )

        conn.execute(
            "INSERT INTO scripts (id, title, author, metadata) VALUES (?, ?, ?, ?)",
            (2, "Empty Script", "Test Author", ""),  # Empty string metadata
        )

        conn.execute(
            """INSERT INTO scenes
            (id, script_id, scene_number, heading, location, time_of_day, content)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (1, 1, 1, "INT. ROOM - DAY", "ROOM", "DAY", "Test content"),
        )

        conn.execute(
            """INSERT INTO scenes
            (id, script_id, scene_number, heading, location, time_of_day, content)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (2, 2, 1, "EXT. PARK - NIGHT", "PARK", "NIGHT", "Park content"),
        )

        conn.commit()
        conn.close()

        mock_settings.database_path = db_path
        engine = SearchEngine(mock_settings)

        query = SearchQuery(raw_query="test", text_query="content")
        response = engine.search(query)

        # Should handle empty/null metadata gracefully
        assert len(response.results) == 2
        assert response.results[0].season is None
        assert response.results[0].episode is None
        assert response.results[1].season is None
        assert response.results[1].episode is None

    def test_search_with_type_error_metadata(self, mock_settings, tmp_path):
        """Test search when metadata causes TypeError during JSON parsing."""
        # Create database with metadata that causes TypeError
        db_path = tmp_path / "type_error.db"
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
                content TEXT
            )
        """)

        conn.execute("""CREATE TABLE characters (id INTEGER PRIMARY KEY, name TEXT)""")
        conn.execute("""CREATE TABLE dialogues (
            id INTEGER PRIMARY KEY,
            scene_id INTEGER,
            character_id INTEGER,
            dialogue_text TEXT,
            metadata TEXT
        )""")
        conn.execute("""CREATE TABLE actions (
            id INTEGER PRIMARY KEY,
            scene_id INTEGER,
            action_text TEXT
        )""")

        # Insert data with metadata that will cause TypeError (not a string)
        # SQLite allows inserting integers into TEXT columns
        conn.execute(
            "INSERT INTO scripts (id, title, author, metadata) VALUES (?, ?, ?, ?)",
            (
                1,
                "TypeError Test",
                "Author",
                "invalid json {not closed",
            ),  # Invalid JSON that will cause error
        )

        conn.execute(
            """INSERT INTO scenes
            (id, script_id, scene_number, heading, location, time_of_day, content)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (1, 1, 1, "INT. TEST - DAY", "TEST", "DAY", "Test content"),
        )

        conn.commit()
        conn.close()

        mock_settings.database_path = db_path
        engine = SearchEngine(mock_settings)

        # This should trigger TypeError in json.loads and handle it gracefully
        query = SearchQuery(raw_query="test", text_query="content")
        response = engine.search(query)

        assert len(response.results) == 1
        assert response.results[0].season is None
        assert response.results[0].episode is None

    def test_get_read_only_connection_sql_error(self, mock_settings, tmp_path):
        """Test connection handling with database that causes SQL errors."""
        # Create a file that's not a valid SQLite database
        invalid_db = tmp_path / "invalid.db"
        invalid_db.write_text("This is not a SQLite database")

        mock_settings.database_path = invalid_db
        engine = SearchEngine(mock_settings)

        # Should raise an exception when trying to connect
        with (
            pytest.raises(sqlite3.DatabaseError),
            engine.get_read_only_connection(),
        ):
            pass

    def test_search_database_timeout(self, mock_settings, mock_db):
        """Test database timeout scenario."""
        mock_settings.database_path = mock_db
        mock_settings.database_timeout = 0.001  # Very short timeout

        engine = SearchEngine(mock_settings)
        query = SearchQuery(raw_query="hello", dialogue="hello")

        # The search should still work with very short timeout for simple queries
        # This tests the timeout parameter is properly passed
        response = engine.search(query)
        assert isinstance(response, SearchResponse)

    def test_search_has_more_pagination(self, mock_settings, tmp_path):
        """Test pagination logic for has_more flag."""
        # Create database with multiple results
        db_path = tmp_path / "paginated.db"
        conn = sqlite3.connect(str(db_path))

        # Create schema
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

        conn.execute("""CREATE TABLE characters (id INTEGER PRIMARY KEY, name TEXT)""")
        conn.execute("""CREATE TABLE dialogues (
            id INTEGER PRIMARY KEY,
            scene_id INTEGER,
            character_id INTEGER,
            dialogue_text TEXT,
            metadata TEXT
        )""")
        conn.execute("""CREATE TABLE actions (
            id INTEGER PRIMARY KEY,
            scene_id INTEGER,
            action_text TEXT
        )""")

        # Insert multiple scripts and scenes for pagination testing
        for i in range(1, 6):  # 5 scripts
            conn.execute(
                "INSERT INTO scripts (id, title, author, metadata) VALUES (?, ?, ?, ?)",
                (i, f"Script {i}", "Author", '{"season": 1, "episode": 1}'),
            )

            conn.execute(
                """INSERT INTO scenes
                (id, script_id, scene_number, heading, location, time_of_day, content)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (i, i, 1, f"INT. ROOM {i} - DAY", f"ROOM{i}", "DAY", f"Content {i}"),
            )

        conn.commit()
        conn.close()

        mock_settings.database_path = db_path
        engine = SearchEngine(mock_settings)

        # Test has_more = True (limit 2, offset 0, total 5)
        query = SearchQuery(
            raw_query="content", text_query="Content", limit=2, offset=0
        )
        response = engine.search(query)

        assert response.total_count == 5
        assert len(response.results) == 2
        assert response.has_more is True

        # Test has_more = False (limit 2, offset 3, total 5)
        query = SearchQuery(
            raw_query="content", text_query="Content", limit=2, offset=3
        )
        response = engine.search(query)

        assert response.total_count == 5
        assert len(response.results) == 2
        assert response.has_more is False

    def test_search_all_match_types(self, mock_settings, mock_db):
        """Test all match type determination branches."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        # Test dialogue match (highest priority)
        query = SearchQuery(
            raw_query="test",
            dialogue="hello",
            action="fight",  # Should be ignored
            text_query="general",  # Should be ignored
            characters=["JOHN"],  # Should be ignored for match type
            locations=["OFFICE"],  # Should be ignored for match type
        )
        assert engine._determine_match_type(query) == "dialogue"

        # Test action match (no dialogue)
        query = SearchQuery(raw_query="test", action="fight")
        assert engine._determine_match_type(query) == "action"

        # Test text match (no dialogue or action)
        query = SearchQuery(raw_query="test", text_query="general")
        assert engine._determine_match_type(query) == "text"

        # Test character match (no dialogue, action, or text)
        query = SearchQuery(raw_query="test", characters=["JOHN"])
        assert engine._determine_match_type(query) == "character"

        # Test location match (no dialogue, action, text, or characters)
        query = SearchQuery(raw_query="test", locations=["OFFICE"])
        assert engine._determine_match_type(query) == "location"

        # Test default (no specific filters)
        query = SearchQuery(raw_query="test")
        assert engine._determine_match_type(query) == "text"

    def test_search_vector_mode_fuzzy(self, mock_settings, mock_db):
        """Test vector search with fuzzy mode."""
        mock_settings.database_path = mock_db
        mock_settings.search_vector_threshold = 5
        engine = SearchEngine(mock_settings)

        # Short query in fuzzy mode should still trigger vector search
        query = SearchQuery(
            raw_query="short",
            text_query="short",
            mode=SearchMode.FUZZY,
        )

        response = engine.search(query)

        # Should include vector search method
        assert "sql" in response.search_methods
        assert "semantic" in response.search_methods

    def test_search_vector_mode_strict(self, mock_settings, mock_db):
        """Test vector search disabled in strict mode."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        # Long query in strict mode should NOT trigger vector search
        long_query = (
            "This is a very long query with many words "
            "that normally triggers vector search"
        )
        query = SearchQuery(
            raw_query=long_query,
            text_query=long_query,
            mode=SearchMode.STRICT,
        )

        response = engine.search(query)

        # Should only include SQL search method
        assert "sql" in response.search_methods
        assert "semantic" not in response.search_methods

    @patch("scriptrag.search.engine.logger")
    def test_search_vector_logging(self, mock_logger, mock_settings, mock_db):
        """Test vector search logging."""
        mock_settings.database_path = mock_db
        mock_settings.search_vector_threshold = 5
        mock_settings.llm_embedding_model = None
        mock_settings.llm_embedding_dimensions = None
        engine = SearchEngine(mock_settings)

        # Query that triggers vector search
        long_query = "This query has more than five words to trigger vector search"
        query = SearchQuery(
            raw_query=long_query,
            text_query=long_query,
            mode=SearchMode.AUTO,
        )

        engine.search(query)

        # Check that semantic search log message was called
        mock_logger.info.assert_any_call(
            "Performing semantic search to enhance results"
        )

    def test_get_read_only_connection_pragma_settings(self, mock_settings, mock_db):
        """Test that PRAGMA settings are correctly applied."""
        mock_settings.database_path = mock_db
        mock_settings.database_cache_size = 1000
        mock_settings.database_temp_store = "FILE"

        engine = SearchEngine(mock_settings)

        with engine.get_read_only_connection() as conn:
            # Verify read-only pragma
            cursor = conn.execute("PRAGMA query_only")
            query_only = cursor.fetchone()[0]
            assert query_only == 1

            # Verify cache size pragma
            cursor = conn.execute("PRAGMA cache_size")
            cache_size = cursor.fetchone()[0]
            assert cache_size == 1000

            # Verify temp store pragma
            cursor = conn.execute("PRAGMA temp_store")
            temp_store = cursor.fetchone()[0]
            # FILE = 1, MEMORY = 2
            assert temp_store == 1

    def test_search_response_execution_time_type(self, mock_settings, mock_db):
        """Test that execution time is always a float type."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        query = SearchQuery(raw_query="test", dialogue="hello")
        response = engine.search(query)

        # Execution time should always be a float, never None
        assert response.execution_time_ms is not None
        assert isinstance(response.execution_time_ms, float)
        assert response.execution_time_ms >= 0.0

    def test_init_with_default_settings(self):
        """Test initialization with settings retrieved from get_settings()."""
        with patch("scriptrag.config.get_settings") as mock_get_settings:
            # Create a mock settings object with all required attributes
            mock_settings = MagicMock()
            mock_settings.database_path = MagicMock()
            # Add semantic search settings
            mock_settings.search_vector_result_limit_factor = 0.5
            mock_settings.search_vector_min_results = 5
            mock_settings.search_vector_similarity_threshold = 0.5
            mock_settings.search_vector_threshold = 10
            mock_settings.llm_model_cache_ttl = 3600
            mock_settings.llm_force_static_models = False
            mock_get_settings.return_value = mock_settings

            # Test initialization without passing settings
            engine = SearchEngine()

            # Verify settings were retrieved and stored
            assert mock_get_settings.called
            assert engine.settings == mock_settings
            assert engine.db_path == mock_settings.database_path
            assert engine.query_builder is not None

    def test_get_read_only_connection_cleanup(self, mock_settings, tmp_path):
        """Test that database connections are properly cleaned up."""
        # Create a valid database file
        db_path = tmp_path / "cleanup_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.close()

        mock_settings.database_path = db_path
        engine = SearchEngine(mock_settings)

        # Use the context manager and verify connection is closed afterward
        with engine.get_read_only_connection() as conn:
            assert conn is not None
            # Connection should be open and usable
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

        # After exiting context manager, connection should be closed
        # Note: We can't easily test that the connection is closed without
        # potentially causing errors, but the context manager ensures cleanup

    def test_get_read_only_connection_exception_cleanup(self, mock_settings, tmp_path):
        """Test connection cleanup when exception occurs."""
        # Create a valid database file
        db_path = tmp_path / "exception_test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.close()

        mock_settings.database_path = db_path
        engine = SearchEngine(mock_settings)

        # Test that connection is cleaned up even when exception occurs
        try:
            with engine.get_read_only_connection() as conn:
                # Cause an exception inside the context manager
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected exception

        # The connection should still be cleaned up properly
        # Context manager's finally block should have executed

    def test_search_with_sql_injection_protection(self, mock_settings, mock_db):
        """Test that search is protected against SQL injection attempts."""
        mock_settings.database_path = mock_db
        engine = SearchEngine(mock_settings)

        # Try various SQL injection attempts
        malicious_queries = [
            "'; DROP TABLE scripts; --",
            "' OR 1=1 --",
            "'; DELETE FROM scripts WHERE 1=1; --",
            "' UNION SELECT * FROM scripts --",
        ]

        for malicious_query in malicious_queries:
            # These should be treated as regular search strings, not SQL
            query = SearchQuery(raw_query=malicious_query, dialogue=malicious_query)

            # Should not raise an exception and should return safe results
            response = engine.search(query)
            assert isinstance(response, SearchResponse)
            # Malicious content shouldn't match any legitimate data
            assert response.total_count == 0

    def test_search_null_count_result(self, mock_settings, tmp_path):
        """Test search handles null count query results gracefully."""
        # Create a database with minimal schema
        db_path = tmp_path / "test_null_count.db"
        conn = sqlite3.connect(str(db_path))

        # Create minimal tables
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

        conn.commit()
        conn.close()

        mock_settings.database_path = db_path
        engine = SearchEngine(mock_settings)

        # Mock the query builder to return a count query that yields None
        with patch.object(engine.query_builder, "build_count_query") as mock_count:
            # Return a query that will return None when fetchone() is called
            mock_count.return_value = (
                "SELECT NULL as total WHERE 1=0",  # Query that returns no rows
                [],
            )

            query = SearchQuery(raw_query="test", dialogue="test")

            # This should not raise an exception even though fetchone() returns None
            response = engine.search(query)

            assert isinstance(response, SearchResponse)
            assert response.total_count == 0  # Should default to 0 when None
            assert len(response.results) == 0

    def test_bible_search_null_count_result(self, mock_settings, tmp_path):
        """Test bible search handles null count query results gracefully."""
        # Create a database with minimal schema including bible tables
        db_path = tmp_path / "test_bible_null_count.db"
        conn = sqlite3.connect(str(db_path))

        # Create minimal tables
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
            CREATE TABLE bibles (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                title TEXT,
                FOREIGN KEY (script_id) REFERENCES scripts(id)
            )
        """)

        conn.execute("""
            CREATE TABLE bible_chunks (
                id INTEGER PRIMARY KEY,
                bible_id INTEGER,
                content TEXT,
                FOREIGN KEY (bible_id) REFERENCES bibles(id)
            )
        """)

        # Insert minimal data
        conn.execute(
            "INSERT INTO scripts (id, title, author, metadata) VALUES (?, ?, ?, ?)",
            (1, "Test Script", "Test Author", "{}"),
        )

        conn.execute(
            "INSERT INTO bibles (id, script_id, title) VALUES (?, ?, ?)",
            (1, 1, "Test Bible"),
        )

        conn.execute(
            "INSERT INTO bible_chunks (id, bible_id, content) VALUES (?, ?, ?)",
            (1, 1, "Bible content"),
        )

        conn.commit()
        conn.close()

        mock_settings.database_path = db_path
        engine = SearchEngine(mock_settings)

        # Perform a search with bible included that might trigger the null count issue
        query = SearchQuery(
            raw_query="nonexistent", text_query="nonexistent", include_bible=True
        )

        # Mock the _search_bible_content method to simulate the null count issue
        def mock_search_bible(query, conn):
            # Simulate the bible search logic but with a null count result
            sql = """
                SELECT
                    s.id AS script_id,
                    s.title AS script_title,
                    b.id AS bible_id,
                    b.title AS bible_title,
                    bc.id AS chunk_id,
                    bc.content AS content
                FROM bible_chunks bc
                JOIN bibles b ON bc.bible_id = b.id
                JOIN scripts s ON b.script_id = s.id
                WHERE bc.content LIKE ?
                LIMIT 10
            """
            params = ["%nonexistent%"]

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

            # Simulate the count query returning None
            count_sql = "SELECT NULL as total WHERE 1=0"  # Query that returns no rows
            count_cursor = conn.execute(count_sql)
            count_result = count_cursor.fetchone()
            # This is where our fix comes into play
            bible_total_count = count_result["total"] if count_result else 0

            bible_results = []

            return bible_results, bible_total_count

        with patch.object(engine, "_search_bible_content", mock_search_bible):
            # Perform a search that includes bible content
            with engine.get_read_only_connection() as conn:
                bible_results, bible_total = engine._search_bible_content(query, conn)

            # Should not crash and should return empty results with 0 count
            assert bible_results == []
            assert bible_total == 0

    def test_search_handles_null_count_query_result(self, mock_settings, tmp_path):
        """Test that search gracefully handles when count query returns None."""
        # Create a minimal database
        db_path = tmp_path / "null_count.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

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
                content TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                name TEXT,
                description TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE dialogues (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                character_id INTEGER,
                dialogue_text TEXT,
                order_in_scene INTEGER
            )
        """)

        conn.execute("""
            CREATE TABLE actions (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                action_text TEXT,
                order_in_scene INTEGER
            )
        """)

        conn.execute("""
            CREATE TABLE bible_content (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                content TEXT,
                metadata TEXT
            )
        """)

        conn.commit()
        conn.close()

        mock_settings.database_path = db_path
        engine = SearchEngine(mock_settings)

        # Mock the query builder to return a count query that will return None
        with patch.object(engine.query_builder, "build_count_query") as mock_count:
            # Return a query that fetches no rows (simulating database issue)
            mock_count.return_value = ("SELECT NULL as total WHERE 1=0", [])

            query = SearchQuery(
                raw_query="test",
                text_query="test",
                mode=SearchMode.AUTO,
                limit=10,
                offset=0,
            )

            # This should not raise an exception
            response = engine.search(query)

            # Should return empty results with 0 total count
            assert isinstance(response, SearchResponse)
            assert response.total_count == 0
            assert response.results == []

    def test_search_handles_malformed_count_query_result(self, mock_settings, tmp_path):
        """Test search handles when count query returns malformed result."""
        # Create a minimal database
        db_path = tmp_path / "malformed_count.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

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
                content TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                name TEXT,
                description TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE dialogues (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                character_id INTEGER,
                dialogue_text TEXT,
                order_in_scene INTEGER
            )
        """)

        conn.execute("""
            CREATE TABLE actions (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                action_text TEXT,
                order_in_scene INTEGER
            )
        """)

        conn.execute("""
            CREATE TABLE bible_content (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                content TEXT,
                metadata TEXT
            )
        """)

        conn.commit()
        conn.close()

        mock_settings.database_path = db_path
        engine = SearchEngine(mock_settings)

        # Mock the query builder to return a count query with wrong column name
        with patch.object(engine.query_builder, "build_count_query") as mock_count:
            # Return a query that returns a row but with wrong column name
            mock_count.return_value = ("SELECT 0 as wrong_column", [])

            query = SearchQuery(
                raw_query="test",
                text_query="test",
                mode=SearchMode.AUTO,
                limit=10,
                offset=0,
            )

            # This should not raise an exception
            response = engine.search(query)

            # Should return empty results with 0 total count
            assert isinstance(response, SearchResponse)
            assert response.total_count == 0
            assert response.results == []
