"""Tests for query CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
import typer

from scriptrag.api.query import QueryAPI
from scriptrag.cli.commands.query import (
    QueryCommandBuilder,
    create_query_app,
)
from scriptrag.query.spec import ParamSpec, QuerySpec


class TestQueryCommandBuilder:
    """Test QueryCommandBuilder functionality."""

    @pytest.fixture
    def mock_api(self):
        """Create mock QueryAPI."""
        return MagicMock(spec=QueryAPI)

    @pytest.fixture
    def simple_spec(self):
        """Create simple query spec."""
        return QuerySpec(
            name="simple-query", description="A simple query", sql="SELECT * FROM users"
        )

    @pytest.fixture
    def complex_spec(self):
        """Create complex query spec with parameters."""
        return QuerySpec(
            name="complex-query",
            description="A complex query",
            params=[
                ParamSpec(name="user_id", type="int", required=True, help="User ID"),
                ParamSpec(name="active", type="bool", required=False, default=True),
                ParamSpec(
                    name="status",
                    type="str",
                    required=True,
                    choices=["active", "inactive"],
                ),
                ParamSpec(name="limit", type="int", required=False, default=10),
                ParamSpec(name="offset", type="int", required=False, default=0),
            ],
            sql="SELECT * FROM users WHERE user_id = :user_id AND active = :active "
            "LIMIT :limit OFFSET :offset",
        )

    def test_builder_initialization(self, mock_api):
        """Test QueryCommandBuilder initialization."""
        builder = QueryCommandBuilder(mock_api)

        assert builder.api is mock_api
        assert builder.formatter is not None
        assert builder.handler is not None

    def test_create_query_app(self, mock_api):
        """Test creating query app with no queries."""
        mock_api.list_queries.return_value = []

        builder = QueryCommandBuilder(mock_api)
        app = builder.create_query_app()

        assert app is not None
        mock_api.reload_queries.assert_called_once()
        mock_api.list_queries.assert_called_once()

    def test_create_query_app_with_queries(self, mock_api, simple_spec):
        """Test creating query app with queries."""
        mock_api.list_queries.return_value = [simple_spec]

        builder = QueryCommandBuilder(mock_api)
        app = builder.create_query_app()

        assert app is not None
        mock_api.reload_queries.assert_called_once()
        mock_api.list_queries.assert_called_once()

    def test_create_query_app_with_exception(self, mock_api):
        """Test create_query_app handles exceptions gracefully."""
        mock_api.reload_queries.side_effect = Exception("Load error")

        builder = QueryCommandBuilder(mock_api)
        app = builder.create_query_app()

        # Should still return an app even if query loading fails
        assert app is not None

    def test_create_list_command(self, mock_api):
        """Test creating list command."""
        mock_api.list_queries.return_value = []

        builder = QueryCommandBuilder(mock_api)
        list_command = builder._create_list_command()

        assert list_command is not None
        assert callable(list_command)

    def test_register_query_command(self, mock_api, simple_spec):
        """Test registering a query command."""
        mock_app = MagicMock(spec=typer.Typer)

        builder = QueryCommandBuilder(mock_api)
        builder._register_query_command(mock_app, simple_spec)

        # Should register the command
        mock_app.command.assert_called_once()


class TestCreateQueryApp:
    """Test create_query_app function."""

    @patch("scriptrag.cli.commands.query.get_settings")
    @patch("scriptrag.cli.commands.query.QueryAPI")
    def test_create_query_app_no_queries(self, mock_api_class, mock_get_settings):
        """Test creating app when no queries found."""
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        mock_api.list_queries.return_value = []

        app = create_query_app()

        # Should create API and reload queries
        mock_api_class.assert_called_once_with(mock_settings)
        mock_api.reload_queries.assert_called_once()
        assert app is not None

    @patch("scriptrag.cli.commands.query.get_settings")
    @patch("scriptrag.cli.commands.query.QueryAPI")
    def test_create_query_app_with_queries(self, mock_api_class, mock_get_settings):
        """Test creating app with queries."""
        # Setup mocks
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api

        mock_spec = QuerySpec(name="test-query", description="Test", sql="SELECT 1")
        mock_api.list_queries.return_value = [mock_spec]

        app = create_query_app()

        # Should create API and get queries
        mock_api_class.assert_called_once_with(mock_settings)
        assert app is not None

    @patch("scriptrag.cli.commands.query.get_settings")
    @patch("scriptrag.cli.commands.query.QueryAPI")
    def test_create_query_app_handles_failure(self, mock_api_class, mock_get_settings):
        """Test creating app when query loading fails."""
        # Setup mocks
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api

        # Make queries fail to load
        mock_api.reload_queries.side_effect = Exception("Load error")

        app = create_query_app()

        # Should still create app
        assert app is not None
