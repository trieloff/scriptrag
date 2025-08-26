"""Tests for query API facade."""

from unittest.mock import MagicMock, patch

import pytest

from scriptrag.api.query import QueryAPI
from scriptrag.config import ScriptRAGSettings
from scriptrag.query.spec import QuerySpec


class TestQueryAPI:
    """Test query API functionality."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = "/test/db.sqlite"
        settings.database_journal_mode = "WAL"
        settings.database_synchronous = "NORMAL"
        settings.database_foreign_keys = True
        return settings

    @pytest.fixture
    def api(self, settings):
        """Create query API with test settings."""
        return QueryAPI(settings)

    @pytest.fixture
    def mock_spec(self):
        """Create mock query spec."""
        return QuerySpec(
            name="test_query", description="Test query", sql="SELECT * FROM test"
        )

    def test_init_with_settings(self, settings):
        """Test initialization with provided settings."""
        api = QueryAPI(settings)

        assert api.settings == settings
        assert api.loader is not None
        assert api.engine is not None
        assert api.formatter is not None

    def test_init_without_settings(self):
        """Test initialization without settings - uses get_settings()."""
        with patch("scriptrag.config.get_settings") as mock_get_settings:
            mock_settings = MagicMock(spec=ScriptRAGSettings)
            mock_settings.database_path = "/test/db.sqlite"
            mock_get_settings.return_value = mock_settings

            api = QueryAPI()

            assert api.settings == mock_settings
            mock_get_settings.assert_called_once()

    def test_list_queries(self, api, mock_spec):
        """Test listing all queries."""
        api.loader.list_queries = MagicMock(return_value=[mock_spec])

        queries = api.list_queries()

        assert len(queries) == 1
        assert queries[0] == mock_spec
        api.loader.list_queries.assert_called_once()

    def test_get_query_found(self, api, mock_spec):
        """Test getting existing query."""
        api.loader.get_query = MagicMock(return_value=mock_spec)

        query = api.get_query("test_query")

        assert query == mock_spec
        api.loader.get_query.assert_called_once_with("test_query")

    def test_get_query_not_found(self, api):
        """Test getting non-existent query."""
        api.loader.get_query = MagicMock(return_value=None)

        query = api.get_query("nonexistent")

        assert query is None
        api.loader.get_query.assert_called_once_with("nonexistent")

    def test_execute_query_success(self, api, mock_spec):
        """Test successful query execution."""
        # Mock dependencies
        api.loader.get_query = MagicMock(return_value=mock_spec)
        api.engine.execute = MagicMock(return_value=([{"id": 1}], 10.5))
        api.formatter.format_results = MagicMock(return_value=None)

        result = api.execute_query("test_query")

        assert result is None  # Default formatted output
        api.loader.get_query.assert_called_once_with("test_query")
        api.engine.execute.assert_called_once_with(mock_spec, None, None, None)
        api.formatter.format_results.assert_called_once_with(
            rows=[{"id": 1}],
            query_name="test_query",
            execution_time_ms=10.5,
            output_json=False,
            limit=None,
            offset=None,
        )

    def test_execute_query_with_params(self, api, mock_spec):
        """Test query execution with parameters."""
        # Mock dependencies
        api.loader.get_query = MagicMock(return_value=mock_spec)
        api.engine.execute = MagicMock(return_value=([], 5.0))
        api.formatter.format_results = MagicMock(return_value="formatted output")

        params = {"user_id": 123}
        result = api.execute_query(
            "test_query", params=params, limit=10, offset=5, output_json=True
        )

        assert result == "formatted output"
        api.engine.execute.assert_called_once_with(mock_spec, params, 10, 5)
        api.formatter.format_results.assert_called_once_with(
            rows=[],
            query_name="test_query",
            execution_time_ms=5.0,
            output_json=True,
            limit=10,
            offset=5,
        )

    def test_execute_query_not_found(self, api):
        """Test executing non-existent query."""
        api.loader.get_query = MagicMock(return_value=None)

        with pytest.raises(ValueError, match="Query 'nonexistent' not found"):
            api.execute_query("nonexistent")

        api.loader.get_query.assert_called_once_with("nonexistent")

    def test_execute_query_execution_error(self, api, mock_spec):
        """Test query execution error handling."""
        # Mock dependencies
        api.loader.get_query = MagicMock(return_value=mock_spec)
        api.engine.execute = MagicMock(side_effect=RuntimeError("Database error"))

        with patch("scriptrag.api.query.logger") as mock_logger:
            with pytest.raises(RuntimeError, match="Database error"):
                api.execute_query("test_query")

            mock_logger.error.assert_called_with(
                "Query execution failed: Database error"
            )

    def test_reload_queries(self, api):
        """Test reloading queries from disk."""
        api.loader.discover_queries = MagicMock(spec=object)

        api.reload_queries()

        api.loader.discover_queries.assert_called_once_with(force_reload=True)
