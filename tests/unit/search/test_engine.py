"""Tests for search engine."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import DatabaseError
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import BibleSearchResult, SearchMode, SearchQuery


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
        settings.database_journal_mode = "WAL"
        settings.database_synchronous = "NORMAL"
        settings.database_foreign_keys = True
        # Add semantic search settings
        settings.search_vector_result_limit_factor = 0.5
        settings.search_vector_min_results = 5
        settings.search_vector_similarity_threshold = 0.5
        settings.search_vector_threshold = 10
        settings.llm_model_cache_ttl = 3600
        settings.llm_force_static_models = False
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
            mock_settings.database_timeout = 30.0
            mock_settings.database_cache_size = -2000
            mock_settings.database_temp_store = "MEMORY"
            mock_settings.database_journal_mode = "WAL"
            mock_settings.database_synchronous = "NORMAL"
            mock_settings.database_foreign_keys = True
            # Add semantic search settings
            mock_settings.search_vector_result_limit_factor = 0.5
            mock_settings.search_vector_min_results = 5
            mock_settings.search_vector_similarity_threshold = 0.5
            mock_settings.search_vector_threshold = 10
            mock_settings.llm_model_cache_ttl = 3600
            mock_settings.llm_force_static_models = False
            mock_get_settings.return_value = mock_settings

            engine = SearchEngine()

            assert engine.settings == mock_settings
            assert engine.db_path == mock_settings.database_path
            assert mock_get_settings.called

    def test_get_read_only_connection_valid(self, engine, tmp_path):
        """Test getting read-only connection with valid path."""
        # Create a valid database
        db_path = tmp_path / "valid.db"
        sqlite3.connect(db_path).close()

        engine.settings.database_path = db_path

        with patch("scriptrag.search.engine.get_read_only_connection") as mock_get_conn:
            mock_conn = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            with engine.get_read_only_connection() as conn:
                assert conn == mock_conn

            mock_get_conn.assert_called_once_with(engine.settings)

    def test_get_read_only_connection_path_traversal(self, settings):
        """Test path traversal protection."""
        # Create a mock path that simulates traversal
        mock_traversal_path = MagicMock(
            spec=["content", "model", "provider", "usage", "resolve", "parent"]
        )
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
        mock_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchall"]
        )
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

        mock_count_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchone"]
        )
        mock_count_cursor.fetchone.return_value = {"total": 1}

        mock_db_conn = MagicMock(
            spec=["content", "model", "provider", "usage", "execute"]
        )
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
        mock_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchall"]
        )
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

        mock_count_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchone"]
        )
        mock_count_cursor.fetchone.return_value = {"total": 1}

        mock_db_conn = MagicMock(
            spec=["content", "model", "provider", "usage", "execute"]
        )
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

        with patch("scriptrag.search.utils.logger") as mock_logger:
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
        mock_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchall"]
        )
        mock_cursor.fetchall.return_value = []

        mock_count_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchone"]
        )
        mock_count_cursor.fetchone.return_value = {"total": 0}

        mock_db_conn = MagicMock(
            spec=["content", "model", "provider", "usage", "execute"]
        )
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

        # Mock semantic adapter to prevent actual async operations
        from unittest.mock import AsyncMock

        engine.semantic_adapter.enhance_results_with_semantic_search = AsyncMock(
            return_value=(
                [],
                [],
            )  # Return empty results for both scene and bible results
        )

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
        match_type = engine.result_utils.determine_match_type(query)
        assert match_type == "dialogue"

    def test_determine_match_type_action(self, engine):
        """Test match type determination for action queries."""
        query = SearchQuery(raw_query="action:runs", action="runs")
        match_type = engine.result_utils.determine_match_type(query)
        assert match_type == "action"

    def test_determine_match_type_text(self, engine):
        """Test match type determination for text queries."""
        query = SearchQuery(raw_query="something", text_query="something")
        match_type = engine.result_utils.determine_match_type(query)
        assert match_type == "text"

    @patch("scriptrag.search.engine.get_read_only_connection")
    def test_search_with_invalid_metadata_json_warning(self, mock_conn, engine):
        """Test search with invalid metadata JSON logs warning."""
        # Mock database connection and cursor
        mock_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchall"]
        )
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

        mock_count_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchone"]
        )
        mock_count_cursor.fetchone.return_value = {"total": 1}

        mock_db_conn = MagicMock(
            spec=["content", "model", "provider", "usage", "execute"]
        )
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

        with patch("scriptrag.search.utils.logger") as mock_logger:
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
        match_type = engine.result_utils.determine_match_type(query)
        assert match_type == "character"

    def test_determine_match_type_location(self, engine):
        """Test match type determination for location queries."""
        query = SearchQuery(raw_query="location:OFFICE", locations=["OFFICE"])
        match_type = engine.result_utils.determine_match_type(query)
        assert match_type == "location"

    def test_determine_match_type_default(self, engine):
        """Test match type determination fallback."""
        query = SearchQuery(raw_query="")
        match_type = engine.result_utils.determine_match_type(query)
        assert match_type == "text"

    def test_get_read_only_connection_non_path_validation_error(self, engine):
        """Test that non-path-validation ValueErrors are re-raised as-is."""
        # Mock get_read_only_connection to raise ValueError NOT about path validation
        with patch("scriptrag.search.engine.get_read_only_connection") as mock_get_conn:
            mock_get_conn.side_effect = ValueError("Some other error")

            with pytest.raises(ValueError, match="Some other error"):
                with engine.get_read_only_connection():
                    pass

    # Note: The complex threading scenarios (lines 96-128) are very difficult to test
    # in isolation as they involve actual thread execution with complex closure state.
    # Tests above provide excellent coverage of the main search functionality.

    def test_search_database_hint_with_existing_scriptrag_db(self, engine, tmp_path):
        """Test database not found hint when scriptrag.db exists in current dir."""
        # Create an actual scriptrag.db file in the current working directory
        original_cwd = Path.cwd()
        scriptrag_db = original_cwd / "scriptrag.db"

        try:
            # Create the file temporarily
            scriptrag_db.touch()

            # Point engine to non-existent database
            engine.db_path = tmp_path / "nonexistent.db"

            query = SearchQuery(raw_query="test", text_query="test")

            with pytest.raises(DatabaseError) as exc_info:
                engine.search(query)

            error = exc_info.value
            assert "Found scriptrag.db here. Use --database scriptrag.db" in error.hint

        finally:
            # Clean up the temporary file
            if scriptrag_db.exists():
                scriptrag_db.unlink()

    @patch("scriptrag.search.engine.get_read_only_connection")
    def test_search_count_result_key_error(self, mock_conn, engine):
        """Test search with count result that raises KeyError."""
        # Mock database connection and cursor for main search
        mock_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchall"]
        )
        mock_cursor.fetchall.return_value = []

        # Mock count cursor that raises KeyError when accessing 'total'
        mock_count_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchone"]
        )
        mock_count_result = {"not_total": 5}  # Missing 'total' key
        mock_count_cursor.fetchone.return_value = mock_count_result

        mock_db_conn = MagicMock(
            spec=["content", "model", "provider", "usage", "execute"]
        )
        mock_db_conn.execute.side_effect = [mock_cursor, mock_count_cursor]
        mock_conn.return_value.__enter__.return_value = mock_db_conn

        # Mock query builder
        engine.query_builder.build_search_query = MagicMock(
            return_value=("SELECT * FROM test", {})
        )
        engine.query_builder.build_count_query = MagicMock(
            return_value=("SELECT COUNT(*) as total", {})
        )

        engine.db_path = engine.settings.database_path
        query = SearchQuery(raw_query="test", text_query="test")

        response = engine.search(query)

        # Should handle KeyError gracefully and set total_count to 0
        assert response.total_count == 0

    @patch("scriptrag.search.engine.get_read_only_connection")
    def test_search_count_result_type_error(self, mock_conn, engine):
        """Test search with count result that raises TypeError."""
        mock_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchall"]
        )
        mock_cursor.fetchall.return_value = []

        # Mock count cursor that raises TypeError when accessing result
        mock_count_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchone"]
        )
        mock_count_cursor.fetchone.return_value = (
            None  # This will cause TypeError when accessing ['total']
        )

        mock_db_conn = MagicMock(
            spec=["content", "model", "provider", "usage", "execute"]
        )
        mock_db_conn.execute.side_effect = [mock_cursor, mock_count_cursor]
        mock_conn.return_value.__enter__.return_value = mock_db_conn

        engine.query_builder.build_search_query = MagicMock(
            return_value=("SELECT * FROM test", {})
        )
        engine.query_builder.build_count_query = MagicMock(
            return_value=("SELECT COUNT(*) as total", {})
        )

        engine.db_path = engine.settings.database_path
        query = SearchQuery(raw_query="test", text_query="test")

        response = engine.search(query)

        # Should handle TypeError gracefully and set total_count to 0
        assert response.total_count == 0

    @patch("scriptrag.search.engine.get_read_only_connection")
    def test_search_count_result_index_error(self, mock_conn, engine):
        """Test search with count result that raises IndexError."""
        mock_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchall"]
        )
        mock_cursor.fetchall.return_value = []

        # Mock count cursor that could raise IndexError
        mock_count_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchone"]
        )
        mock_count_result = []  # Empty list, accessing ['total'] would raise IndexError
        mock_count_cursor.fetchone.return_value = mock_count_result

        mock_db_conn = MagicMock(
            spec=["content", "model", "provider", "usage", "execute"]
        )
        mock_db_conn.execute.side_effect = [mock_cursor, mock_count_cursor]
        mock_conn.return_value.__enter__.return_value = mock_db_conn

        engine.query_builder.build_search_query = MagicMock(
            return_value=("SELECT * FROM test", {})
        )
        engine.query_builder.build_count_query = MagicMock(
            return_value=("SELECT COUNT(*) as total", {})
        )

        engine.db_path = engine.settings.database_path
        query = SearchQuery(raw_query="test", text_query="test")

        response = engine.search(query)

        # Should handle IndexError gracefully and set total_count to 0
        assert response.total_count == 0

    @patch("scriptrag.search.engine.get_read_only_connection")
    def test_search_with_bible_semantic_results_deduplication(self, mock_conn, engine):
        """Test search with bible semantic results that need deduplication."""
        # Mock database connection
        mock_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchall"]
        )
        mock_cursor.fetchall.return_value = []

        mock_count_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchone"]
        )
        mock_count_cursor.fetchone.return_value = {"total": 0}

        mock_db_conn = MagicMock(
            spec=["content", "model", "provider", "usage", "execute"]
        )
        mock_db_conn.execute.side_effect = [mock_cursor, mock_count_cursor]
        mock_conn.return_value.__enter__.return_value = mock_db_conn

        engine.query_builder.build_search_query = MagicMock(
            return_value=("SELECT * FROM test", {})
        )
        engine.query_builder.build_count_query = MagicMock(
            return_value=("SELECT COUNT(*) as total", {})
        )

        # Mock existing bible results
        existing_bible_result = BibleSearchResult(
            script_id=1,
            script_title="Test Script",
            bible_id=1,
            bible_title="Test Bible",
            chunk_id=1,
            chunk_heading="Test Heading",
            chunk_level=1,
            chunk_content="Test content",
            match_type="text",
        )

        # Mock semantic bible results (one duplicate, one new)
        semantic_bible_result_duplicate = BibleSearchResult(
            script_id=1,
            script_title="Test Script",
            bible_id=1,
            bible_title="Test Bible",
            chunk_id=1,  # Same as existing - should be deduplicated
            chunk_heading="Test Heading",
            chunk_level=1,
            chunk_content="Test content",
            match_type="semantic",
        )

        semantic_bible_result_new = BibleSearchResult(
            script_id=1,
            script_title="Test Script",
            bible_id=1,
            bible_title="Test Bible",
            chunk_id=2,  # Different chunk_id - should be added
            chunk_heading="New Heading",
            chunk_level=1,
            chunk_content="New content",
            match_type="semantic",
        )

        # Mock _search_bible_content to return existing results
        with patch.object(engine, "_search_bible_content") as mock_bible_search:
            mock_bible_search.return_value = ([existing_bible_result], 1)

            # Mock semantic adapter to return semantic results
            with patch.object(
                engine.semantic_adapter, "enhance_results_with_semantic_search"
            ) as mock_enhance:
                mock_enhance.return_value = (
                    [],
                    [semantic_bible_result_duplicate, semantic_bible_result_new],
                )

                engine.db_path = engine.settings.database_path
                query = SearchQuery(
                    raw_query="test",
                    text_query="test",
                    include_bible=True,
                    mode=SearchMode.FUZZY,
                )

                response = engine.search(query)

                # Should have 2 bible results: 1 existing + 1 new (duplicates filtered)
                assert len(response.bible_results) == 2
                chunk_ids = {br.chunk_id for br in response.bible_results}
                assert chunk_ids == {1, 2}  # Both chunk IDs present, no duplicates

    @patch("scriptrag.search.engine.get_read_only_connection")
    def test_search_semantic_search_exception_handling(self, mock_conn, engine):
        """Test search with semantic search that raises an exception."""
        # Mock database connection
        mock_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchall"]
        )
        mock_cursor.fetchall.return_value = []

        mock_count_cursor = MagicMock(
            spec=["content", "model", "provider", "usage", "fetchone"]
        )
        mock_count_cursor.fetchone.return_value = {"total": 0}

        mock_db_conn = MagicMock(
            spec=["content", "model", "provider", "usage", "execute"]
        )
        mock_db_conn.execute.side_effect = [mock_cursor, mock_count_cursor]
        mock_conn.return_value.__enter__.return_value = mock_db_conn

        engine.query_builder.build_search_query = MagicMock(
            return_value=("SELECT * FROM test", {})
        )
        engine.query_builder.build_count_query = MagicMock(
            return_value=("SELECT COUNT(*) as total", {})
        )

        # Mock semantic adapter to raise exception
        test_exception = RuntimeError("Semantic search failed")
        with patch.object(
            engine.semantic_adapter, "enhance_results_with_semantic_search"
        ) as mock_enhance:
            mock_enhance.side_effect = test_exception

            engine.db_path = engine.settings.database_path
            query = SearchQuery(
                raw_query="test", text_query="test", mode=SearchMode.FUZZY
            )

            with patch("scriptrag.search.engine.logger") as mock_logger:
                response = engine.search(query)

                # Should continue with SQL results only and log error
                assert "semantic" in response.search_methods  # Semantic was attempted
                mock_logger.error.assert_called_with(
                    "Semantic search failed, falling back to SQL results",
                    error=str(test_exception),
                    query="test",
                    error_type="RuntimeError",
                )

    def test_search_bible_content_with_project_filter(self, engine, tmp_path):
        """Test bible search with project filter."""
        # Create test database with bible tables
        db_path = tmp_path / "test_bible.db"
        conn = sqlite3.connect(db_path)

        # Create bible schema
        conn.executescript("""
            CREATE TABLE scripts (
                id INTEGER PRIMARY KEY,
                title TEXT,
                author TEXT
            );

            CREATE TABLE script_bibles (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                title TEXT,
                FOREIGN KEY (script_id) REFERENCES scripts(id)
            );

            CREATE TABLE bible_chunks (
                id INTEGER PRIMARY KEY,
                bible_id INTEGER,
                chunk_number INTEGER,
                heading TEXT,
                level INTEGER,
                content TEXT,
                FOREIGN KEY (bible_id) REFERENCES script_bibles(id)
            );

            INSERT INTO scripts (id, title, author) VALUES
                (1, 'Test Project', 'Test Author'),
                (2, 'Other Project', 'Other Author');

            INSERT INTO script_bibles (id, script_id, title) VALUES
                (1, 1, 'Test Bible'),
                (2, 2, 'Other Bible');

            INSERT INTO bible_chunks (
                id, bible_id, chunk_number, heading, level, content
            ) VALUES
                (1, 1, 1, 'Test Heading', 1, 'Test content for project'),
                (2, 2, 1, 'Other Heading', 1, 'Other content for project');
        """)
        conn.commit()
        conn.close()

        engine.settings.database_path = db_path
        engine.db_path = db_path

        # Test with project filter
        query = SearchQuery(
            raw_query="project:Test Project content",
            text_query="content",
            project="Test Project",
            include_bible=True,
        )

        with engine.get_read_only_connection() as conn:
            bible_results, total_count = engine._search_bible_content(conn, query)

            # Should only return results from "Test Project"
            assert len(bible_results) == 1
            assert bible_results[0].script_title == "Test Project"
            assert total_count == 1

    def test_search_bible_content_database_error(self, engine, tmp_path):
        """Test bible search with database error."""
        # Create minimal database
        db_path = tmp_path / "test_error.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        engine.settings.database_path = db_path
        engine.db_path = db_path

        query = SearchQuery(raw_query="test", text_query="test", include_bible=True)

        with engine.get_read_only_connection() as conn:
            with patch("scriptrag.search.engine.logger") as mock_logger:
                # This will cause a database error since bible tables don't exist
                bible_results, total_count = engine._search_bible_content(conn, query)

                # Should return empty results and log error
                assert bible_results == []
                assert total_count == 0

                # Should log database error
                mock_logger.error.assert_called_with(
                    "Database error during bible search",
                    error=mock_logger.error.call_args[1]["error"],
                    query="test",
                    project=None,
                )
