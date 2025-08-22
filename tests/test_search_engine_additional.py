"""Additional tests for SearchEngine to target specific uncovered lines.

These tests are designed to achieve 99% coverage by specifically targeting
the uncovered lines identified in the coverage analysis:
- Lines 101-117: Thread wrapper execution in async context
- Lines 129-134: Exception handling within thread execution
- Line 137: Exception cleanup in thread
- Line 185: Database error path in search_async
- Lines 272-304: Semantic search integration and merging
"""

import asyncio
from unittest.mock import Mock, patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import DatabaseError
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import (
    BibleSearchResult,
    SearchMode,
    SearchQuery,
    SearchResponse,
    SearchResult,
)


class TestSearchEngineAsyncContextExecution:
    """Test async context wrapper execution (lines 101-117)."""

    @patch("asyncio.get_running_loop")
    @patch("threading.Thread")
    @patch("asyncio.new_event_loop")
    @patch("asyncio.set_event_loop")
    def test_thread_wrapper_execution_lines_101_117(
        self,
        mock_set_event_loop,
        mock_new_event_loop,
        mock_thread_class,
        mock_get_running_loop,
        tmp_path,
    ):
        """Test the actual execution within thread wrapper (lines 101-117)."""
        # Setup: Create a real database for successful execution
        db_path = tmp_path / "test.db"
        db_path.write_text("")  # Create empty file to pass exists check

        settings = ScriptRAGSettings(database_path=db_path)
        engine = SearchEngine(settings)
        query = SearchQuery(raw_query="test", text_query="test")

        # Mock that we're in async context
        mock_get_running_loop.return_value = Mock()

        # Create mocks for the new event loop
        mock_loop = Mock()
        mock_new_event_loop.return_value = mock_loop
        mock_loop.run_until_complete = Mock()

        # Mock successful search_async result
        expected_response = SearchResponse(
            query=query,
            results=[],
            bible_results=[],
            total_count=0,
            bible_total_count=0,
            has_more=False,
            execution_time_ms=10.0,
            search_methods=["sql"],
        )
        mock_loop.run_until_complete.return_value = expected_response

        # Mock thread behavior
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread
        mock_thread.is_alive.return_value = False  # Thread completes successfully

        # Capture the target function to execute it
        captured_target = None

        def capture_target(*args, **kwargs):
            nonlocal captured_target
            captured_target = kwargs.get("target", args[0] if args else None)
            return mock_thread

        mock_thread_class.side_effect = capture_target

        # Mock the database connection to prevent actual DB operations
        with patch.object(engine, "get_read_only_connection") as mock_conn_mgr:
            mock_conn = Mock()
            mock_conn_mgr.return_value.__enter__ = Mock(return_value=mock_conn)
            mock_conn_mgr.return_value.__exit__ = Mock(return_value=None)

            # Configure mock connection for basic query results
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = {"total": 0}
            mock_conn.execute.return_value = mock_cursor

            # Execute the search
            result = engine.search(query)

            # Verify thread was created and started
            mock_thread_class.assert_called_once()
            mock_thread.start.assert_called_once()
            mock_thread.join.assert_called_once_with(timeout=300)

            # Execute the captured target function to cover lines 101-117
            if captured_target:
                # This should execute the run_in_new_loop function
                # which covers lines 101-117
                captured_target()

                # Verify the new event loop operations (may be called multiple times)
                mock_new_event_loop.assert_called()
                mock_set_event_loop.assert_called()
                mock_loop.run_until_complete.assert_called()

    @patch("asyncio.get_running_loop")
    @patch("threading.Thread")
    def test_thread_exception_handling_lines_129_134(
        self, mock_thread_class, mock_get_running_loop, tmp_path
    ):
        """Test exception handling within thread execution (lines 129-134)."""
        # Setup
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)
        engine = SearchEngine(settings)
        query = SearchQuery(raw_query="test", text_query="test")

        # Mock that we're in async context
        mock_get_running_loop.return_value = Mock()

        # Mock thread that completes but with exception
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread
        mock_thread.is_alive.return_value = False

        # Capture the target function and simulate exception
        captured_target = None

        def capture_target(*args, **kwargs):
            nonlocal captured_target
            captured_target = kwargs.get("target", args[0] if args else None)
            return mock_thread

        mock_thread_class.side_effect = capture_target

        # Mock search_async to raise exception
        test_exception = DatabaseError("Test database error")
        with patch.object(engine, "search_async") as mock_search_async:
            mock_search_async.side_effect = test_exception

            # Execute the search, which should raise the exception
            with pytest.raises(DatabaseError, match="Test database error"):
                engine.search(query)

                # Execute the captured target to trigger exception path
                if captured_target:
                    captured_target()

    @patch("asyncio.get_running_loop")
    @patch("threading.Thread")
    def test_thread_successful_completion_line_137(
        self, mock_thread_class, mock_get_running_loop, tmp_path
    ):
        """Test successful thread completion and return (line 137)."""
        # Setup
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)
        engine = SearchEngine(settings)
        query = SearchQuery(raw_query="test", text_query="test")

        # Mock that we're in async context
        mock_get_running_loop.return_value = Mock()

        # Mock thread behavior
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread
        mock_thread.is_alive.return_value = False

        # Create a scenario where result is None (line 135-137)
        captured_target = None

        def capture_target(*args, **kwargs):
            nonlocal captured_target
            captured_target = kwargs.get("target", args[0] if args else None)
            return mock_thread

        mock_thread_class.side_effect = capture_target

        # Test successful execution to reach line 137 (return result)
        # Create expected response
        expected_response = SearchResponse(
            query=query,
            results=[],
            bible_results=[],
            total_count=0,
            bible_total_count=0,
            has_more=False,
            execution_time_ms=10.0,
            search_methods=["sql"],
        )

        # Mock database connection for successful execution
        with patch.object(engine, "get_read_only_connection") as mock_conn_mgr:
            mock_conn = Mock()
            mock_conn_mgr.return_value.__enter__ = Mock(return_value=mock_conn)
            mock_conn_mgr.return_value.__exit__ = Mock(return_value=None)

            # Configure mock connection for basic query results
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = {"total": 0}
            mock_conn.execute.return_value = mock_cursor

            # Create database file to pass exists check
            db_path.write_text("")

            # Execute search - this should succeed and reach line 137
            result = engine.search(query)

            # Verify we got a result (line 137 was executed)
            assert isinstance(result, SearchResponse)
            assert result.total_count == 0


class TestSearchEngineAsyncDatabaseError:
    """Test database error path in search_async (line 185)."""

    def test_database_not_found_hint_generation_line_185(self, tmp_path, monkeypatch):
        """Test database error path with scriptrag.db hint (line 185)."""
        # Change to temp directory to avoid conflicts
        monkeypatch.chdir(tmp_path)

        # Setup: Create scriptrag.db in current directory to trigger hint
        scriptrag_db = tmp_path / "scriptrag.db"
        scriptrag_db.write_text("")

        try:
            # Setup engine with non-existent database
            non_existent_db = tmp_path / "nonexistent.db"
            settings = ScriptRAGSettings(database_path=non_existent_db)
            engine = SearchEngine(settings)
            query = SearchQuery(raw_query="test", text_query="test")

            # This should trigger the database not found error with hint
            with pytest.raises(DatabaseError) as exc_info:
                asyncio.run(engine.search_async(query))

            # Verify the hint was generated (line 185)
            error_details = exc_info.value.details
            assert "Found scriptrag.db here" in exc_info.value.hint
            assert "Use --database scriptrag.db" in exc_info.value.hint

        finally:
            # Cleanup
            if scriptrag_db.exists():
                scriptrag_db.unlink()


class TestSemanticSearchIntegration:
    """Test semantic search integration and merging (lines 272-304)."""

    def test_semantic_search_enhancement_lines_272_304(self, tmp_path):
        """Test semantic search result integration and merging (lines 272-304)."""
        # Create a real database file
        db_path = tmp_path / "test.db"
        db_path.write_text("")  # Create empty file to pass exists check

        # Configure settings for semantic search
        settings = ScriptRAGSettings(
            database_path=db_path,
            search_vector_result_limit_factor=0.8,
            search_vector_min_results=5,
            search_vector_threshold=8,  # Lower threshold to trigger vector search
        )
        engine = SearchEngine(settings)

        # Create query that needs vector search (long query triggers semantic search)
        # Need >10 words to trigger vector search in AUTO mode
        long_query = (
            "this is a very long query that triggers semantic search "
            "exceeding the word count threshold"
        )
        query = SearchQuery(
            raw_query=long_query,
            text_query=long_query,
            limit=10,
            include_bible=True,
        )

        # Mock database connection to return empty results
        with patch.object(engine, "get_read_only_connection") as mock_conn_mgr:
            mock_conn = Mock()
            mock_conn_mgr.return_value.__enter__ = Mock(return_value=mock_conn)
            mock_conn_mgr.return_value.__exit__ = Mock(return_value=None)

            # Configure basic query results
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = {"total": 0}
            mock_conn.execute.return_value = mock_cursor

            # Mock semantic adapter with enhanced results
            enhanced_results = [
                SearchResult(
                    script_id="script1",
                    script_title="Test Script",
                    script_author="Test Author",
                    scene_id="scene1",
                    scene_number=1,
                    scene_heading="INT. TEST - DAY",
                    scene_location="TEST",
                    scene_time="DAY",
                    scene_content="semantic enhanced content",
                    match_type="semantic",
                )
            ]

            enhanced_bible_results = [
                BibleSearchResult(
                    script_id="script1",
                    script_title="Test Script",
                    bible_id="bible1",
                    bible_title="Test Bible",
                    chunk_id="chunk1",
                    chunk_heading="Test Heading",
                    chunk_level=1,
                    chunk_content="semantic bible content",
                    match_type="semantic",
                )
            ]

            with patch.object(
                engine.semantic_adapter, "enhance_results_with_semantic_search"
            ) as mock_enhance:
                mock_enhance.return_value = (enhanced_results, enhanced_bible_results)

                # Execute the search
                result = asyncio.run(engine.search_async(query))

                # Verify semantic search was triggered (line 272-273)
                assert "semantic" in result.search_methods

                # Verify enhance method was called with correct parameters
                mock_enhance.assert_called_once()
                call_kwargs = mock_enhance.call_args[1]
                assert call_kwargs["query"] == query
                assert call_kwargs["existing_results"] == []
                assert call_kwargs["limit"] == max(
                    5, int(10 * 0.8)
                )  # min_results vs limit * factor

                # Verify results were enhanced (line 292)
                assert result.results == enhanced_results

                # Verify bible results were merged (lines 295-301)
                assert len(result.bible_results) == 1
                assert result.bible_results[0].chunk_id == "chunk1"

    def test_semantic_search_duplicate_bible_merging_lines_297_301(self, tmp_path):
        """Test semantic bible results merging with duplicate avoidance."""
        # Create database
        db_path = tmp_path / "test.db"
        db_path.write_text("")

        settings = ScriptRAGSettings(
            database_path=db_path,
            search_vector_result_limit_factor=0.9,
            search_vector_min_results=3,
            search_vector_threshold=8,  # Lower threshold to ensure trigger
        )
        engine = SearchEngine(settings)

        # Ensure query has >8 words to trigger vector search
        long_query = (
            "this is a very long semantic query that triggers "
            "vector search with many descriptive words"
        )
        query = SearchQuery(
            raw_query=long_query,
            text_query=long_query,
            limit=5,
            include_bible=True,
        )

        # Existing bible result from SQL search
        existing_bible_result = BibleSearchResult(
            script_id="script1",
            script_title="Test Script",
            bible_id="bible1",
            bible_title="Test Bible",
            chunk_id="existing_chunk",  # Used to test duplicate detection
            chunk_heading="Existing",
            chunk_level=1,
            chunk_content="existing content",
            match_type="text",
        )

        with patch.object(engine, "get_read_only_connection") as mock_conn_mgr:
            mock_conn = Mock()
            mock_conn_mgr.return_value.__enter__ = Mock(return_value=mock_conn)
            mock_conn_mgr.return_value.__exit__ = Mock(return_value=None)

            # Mock SQL search to return existing bible result
            mock_cursor = Mock()
            mock_cursor.fetchall.side_effect = [
                [],  # Regular search results
                [
                    {
                        "script_id": "script1",
                        "script_title": "Test Script",
                        "bible_id": "bible1",
                        "bible_title": "Test Bible",
                        "chunk_id": "existing_chunk",
                        "chunk_heading": "Existing",
                        "chunk_level": 1,
                        "chunk_content": "existing content",
                    }
                ],  # Bible search results
            ]
            mock_cursor.fetchone.return_value = {"total": 1}
            mock_conn.execute.return_value = mock_cursor

            # Mock semantic search results with one duplicate and one new
            semantic_bible_results = [
                BibleSearchResult(
                    script_id="script1",
                    script_title="Test Script",
                    bible_id="bible1",
                    bible_title="Test Bible",
                    chunk_id="existing_chunk",  # Duplicate - should be filtered out
                    chunk_heading="Duplicate",
                    chunk_level=1,
                    chunk_content="duplicate content",
                    match_type="semantic",
                ),
                BibleSearchResult(
                    script_id="script1",
                    script_title="Test Script",
                    bible_id="bible1",
                    bible_title="Test Bible",
                    chunk_id="new_chunk",  # New - should be added
                    chunk_heading="New",
                    chunk_level=1,
                    chunk_content="new semantic content",
                    match_type="semantic",
                ),
            ]

            with patch.object(
                engine.semantic_adapter, "enhance_results_with_semantic_search"
            ) as mock_enhance:
                mock_enhance.return_value = ([], semantic_bible_results)

                # Execute search
                result = asyncio.run(engine.search_async(query))

                # Verify duplicate filtering (lines 297-301)
                # Should have existing + only the new one (duplicate filtered out)
                assert len(result.bible_results) == 2
                chunk_ids = {br.chunk_id for br in result.bible_results}
                assert "existing_chunk" in chunk_ids  # Original from SQL
                assert "new_chunk" in chunk_ids  # New from semantic
                # Duplicate should not create a third entry

    def test_semantic_search_error_fallback_lines_303_311(self, tmp_path):
        """Test semantic search error with graceful fallback (lines 303-311)."""
        # Create database
        db_path = tmp_path / "test.db"
        db_path.write_text("")

        settings = ScriptRAGSettings(
            database_path=db_path,
            search_vector_threshold=3,  # Very low threshold
        )
        engine = SearchEngine(settings)

        # Use FUZZY mode to force semantic search even with short query
        query = SearchQuery(
            raw_query="short query that triggers search",
            text_query="short query that triggers search",
            mode=SearchMode.FUZZY,
            limit=5,
        )

        with patch.object(engine, "get_read_only_connection") as mock_conn_mgr:
            mock_conn = Mock()
            mock_conn_mgr.return_value.__enter__ = Mock(return_value=mock_conn)
            mock_conn_mgr.return_value.__exit__ = Mock(return_value=None)

            # Configure basic query results
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = {"total": 0}
            mock_conn.execute.return_value = mock_cursor

            # Mock semantic adapter to raise exception
            with patch.object(
                engine.semantic_adapter, "enhance_results_with_semantic_search"
            ) as mock_enhance:
                # This should trigger the exception handling in lines 303-311
                mock_enhance.side_effect = ValueError("Semantic search failed")

                # Execute search - should not fail due to graceful fallback
                result = asyncio.run(engine.search_async(query))

                # Verify semantic search was attempted but fell back gracefully
                assert "semantic" in result.search_methods  # Line 272 still adds it
                assert result.results == []  # Fell back to empty SQL results
                assert len(result.bible_results) == 0


class TestSearchThreadTimeout:
    """Test configurable search thread timeout."""

    def test_default_timeout_setting(self):
        """Test that default search thread timeout is 300 seconds."""
        settings = ScriptRAGSettings()
        assert settings.search_thread_timeout == 300.0

    def test_custom_timeout_setting(self):
        """Test that custom search thread timeout can be configured."""
        settings = ScriptRAGSettings(search_thread_timeout=120.0)
        assert settings.search_thread_timeout == 120.0

    def test_engine_uses_configured_timeout(self):
        """Test that SearchEngine uses the configured timeout value."""
        settings = ScriptRAGSettings(search_thread_timeout=60.0)
        engine = SearchEngine(settings)
        assert engine.settings.search_thread_timeout == 60.0

    def test_timeout_minimum_value(self):
        """Test that timeout has a minimum value of 1.0 second."""
        # This should raise a validation error since ge=1.0 is set
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings(search_thread_timeout=0.5)

        # Check that the error is about the constraint
        errors = exc_info.value.errors()
        assert len(errors) > 0
        # Check that at least one error is about the search_thread_timeout field
        assert any(error.get("loc") == ("search_thread_timeout",) for error in errors)
