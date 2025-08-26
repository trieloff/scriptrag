"""Tests for query CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
import typer

from scriptrag.api.query import QueryAPI
from scriptrag.cli.commands.query import (
    QueryAppManager,
    QueryCommandBuilder,
    create_query_app,
    get_query_app,
    reset_query_app,
)
from scriptrag.config import ScriptRAGSettings
from scriptrag.query.spec import QuerySpec


class TestQueryCommandBuilder:
    """Test query command builder."""

    @pytest.fixture
    def mock_api(self):
        """Create mock QueryAPI."""
        api = MagicMock(spec=QueryAPI)
        api.reload_queries = MagicMock()
        api.list_queries = MagicMock(return_value=[])
        return api

    @pytest.fixture
    def simple_spec(self):
        """Create simple query spec."""
        return QuerySpec(
            name="simple-query", description="A simple query", sql="SELECT * FROM users"
        )

    def test_create_query_app_no_queries(self, mock_api):
        """Test creating query app when no queries exist."""
        mock_api.list_queries.return_value = []

        builder = QueryCommandBuilder(mock_api)
        app = builder.create_query_app()

        assert app is not None
        assert isinstance(app, typer.Typer)
        mock_api.reload_queries.assert_called_once()

    def test_create_query_app_with_queries(self, mock_api, simple_spec):
        """Test creating query app with queries."""
        mock_api.list_queries.return_value = [simple_spec]

        builder = QueryCommandBuilder(mock_api)
        app = builder.create_query_app()

        assert app is not None
        assert isinstance(app, typer.Typer)
        mock_api.reload_queries.assert_called_once()

    def test_create_query_app_reload_failure(self, mock_api):
        """Test query app creation when reload fails."""
        mock_api.reload_queries.side_effect = Exception("Failed to reload")

        builder = QueryCommandBuilder(mock_api)
        app = builder.create_query_app()

        # Should still create app even if reload fails
        assert app is not None


class TestQueryAppManager:
    """Test query app manager."""

    def test_get_app_creates_app(self):
        """Test that get_app creates app on first call."""
        manager = QueryAppManager()

        with patch("scriptrag.cli.commands.query.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=ScriptRAGSettings)
            app = manager.get_app()

            assert app is not None
            assert manager.app is app

    def test_get_app_reuses_app(self):
        """Test that get_app reuses existing app."""
        manager = QueryAppManager()

        with patch("scriptrag.cli.commands.query.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(spec=ScriptRAGSettings)
            app1 = manager.get_app()
            app2 = manager.get_app()

            assert app1 is app2


class TestQueryAppFunctions:
    """Test module-level query app functions."""

    @patch("scriptrag.cli.commands.query.get_settings")
    @patch("scriptrag.cli.commands.query.QueryAPI")
    def test_create_query_app(self, mock_api_class, mock_get_settings):
        """Test create_query_app function."""
        mock_settings = MagicMock(spec=ScriptRAGSettings)
        mock_get_settings.return_value = mock_settings
        mock_api = MagicMock(spec=QueryAPI)
        mock_api.reload_queries = MagicMock()
        mock_api.list_queries = MagicMock(return_value=[])
        mock_api_class.return_value = mock_api

        app = create_query_app()

        assert app is not None
        assert isinstance(app, typer.Typer)

    def test_get_query_app(self):
        """Test get_query_app function."""
        with patch("scriptrag.cli.commands.query._query_app_manager") as mock_manager:
            mock_app = MagicMock(spec=typer.Typer)
            mock_manager.get_app.return_value = mock_app

            app = get_query_app()

            assert app is mock_app
            mock_manager.get_app.assert_called_once()

    def test_reset_query_app(self):
        """Test reset_query_app function."""
        with patch("scriptrag.cli.commands.query._query_app_manager") as mock_manager:
            reset_query_app()
            mock_manager.reset.assert_called_once()
