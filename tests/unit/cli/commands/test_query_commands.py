"""Tests for query CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
import typer

from scriptrag.api.query import QueryAPI
from scriptrag.cli.commands.query import (
    create_query_command,
    get_query_app,
    register_query_commands,
)
from scriptrag.query.spec import ParamSpec, QuerySpec


class TestCreateQueryCommand:
    """Test dynamic query command creation."""

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

    def test_create_query_command_none_spec(self, mock_api):
        """Test creating command when spec doesn't exist."""
        mock_api.get_query.return_value = None

        result = create_query_command(mock_api, "nonexistent")

        assert result is None
        mock_api.get_query.assert_called_once_with("nonexistent")

    def test_create_query_command_simple(self, mock_api, simple_spec):
        """Test creating command for simple query."""
        mock_api.get_query.return_value = simple_spec

        command = create_query_command(mock_api, "simple-query")

        assert command is not None
        assert command.__name__ == "simple_query"
        assert command.__doc__ == "A simple query"
        mock_api.get_query.assert_called_once_with("simple-query")

    def test_create_query_command_complex(self, mock_api, complex_spec):
        """Test creating command for complex query with parameters."""
        mock_api.get_query.return_value = complex_spec

        command = create_query_command(mock_api, "complex-query")

        assert command is not None
        assert command.__name__ == "complex_query"
        assert hasattr(command, "__signature__")

        # Check signature has expected parameters
        sig = command.__signature__
        param_names = list(sig.parameters.keys())

        # Should have query params plus standard options
        assert "user_id" in param_names
        assert "active" in param_names
        assert "status" in param_names
        assert "limit" in param_names
        assert "offset" in param_names
        assert "json" in param_names

    @patch("scriptrag.cli.commands.query.get_settings")
    @patch("scriptrag.cli.commands.query.QueryAPI")
    def test_query_command_execution_success(
        self, mock_api_class, mock_get_settings, mock_api, simple_spec
    ):
        """Test successful query command execution."""
        # Setup mocks
        mock_api.get_query.return_value = simple_spec
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings
        mock_current_api = MagicMock()
        mock_api_class.return_value = mock_current_api
        mock_current_api.execute_query.return_value = None

        # Create command
        command = create_query_command(mock_api, "simple-query")

        # Execute command
        with patch("scriptrag.config.settings._settings", None):
            command(json=False, limit=None, offset=None)

        # Verify execution
        mock_current_api.execute_query.assert_called_once_with(
            name="simple-query", params={}, limit=None, offset=None, output_json=False
        )

    @patch("scriptrag.cli.commands.query.get_settings")
    @patch("scriptrag.cli.commands.query.QueryAPI")
    def test_query_command_execution_json_output(
        self, mock_api_class, mock_get_settings, mock_api, simple_spec
    ):
        """Test query command execution with JSON output."""
        # Setup mocks
        mock_api.get_query.return_value = simple_spec
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings
        mock_current_api = MagicMock()
        mock_api_class.return_value = mock_current_api
        mock_current_api.execute_query.return_value = '{"results": []}'

        # Create command
        command = create_query_command(mock_api, "simple-query")

        # Execute command with JSON output
        with (
            patch("scriptrag.config.settings._settings", None),
            patch("builtins.print") as mock_print,
        ):
            command(json=True, limit=10, offset=5)

        # Verify JSON output is printed directly
        mock_print.assert_called_once_with('{"results": []}')
        mock_current_api.execute_query.assert_called_once_with(
            name="simple-query", params={}, limit=10, offset=5, output_json=True
        )

    @patch("scriptrag.cli.commands.query.get_settings")
    @patch("scriptrag.cli.commands.query.QueryAPI")
    def test_query_command_execution_error(
        self, mock_api_class, mock_get_settings, mock_api, simple_spec
    ):
        """Test query command execution with error."""
        # Setup mocks
        mock_api.get_query.return_value = simple_spec
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings
        mock_current_api = MagicMock()
        mock_api_class.return_value = mock_current_api
        mock_current_api.execute_query.side_effect = RuntimeError("Database error")

        # Create command
        command = create_query_command(mock_api, "simple-query")

        # Execute command and expect error
        with (
            patch("scriptrag.config.settings._settings", None),
            pytest.raises(typer.Exit),
        ):
            command(json=False, limit=None, offset=None)

    def test_create_query_command_skip_limit_offset_params(self, mock_api):
        """Test that limit/offset params in spec are skipped in command creation."""
        spec_with_limit_offset = QuerySpec(
            name="test",
            description="Test",
            params=[
                ParamSpec(name="user_id", type="int", required=True),
                ParamSpec(name="limit", type="int", required=False),
                ParamSpec(name="offset", type="int", required=False),
            ],
            sql="SELECT * FROM users WHERE user_id = :user_id "
            "LIMIT :limit OFFSET :offset",
        )

        mock_api.get_query.return_value = spec_with_limit_offset

        command = create_query_command(mock_api, "test")

        # Check that limit/offset from spec are not in command signature
        # (they should be handled separately as standard options)
        sig = command.__signature__
        param_names = list(sig.parameters.keys())

        assert "user_id" in param_names
        assert "limit" in param_names  # But this comes from standard options
        assert "offset" in param_names  # But this comes from standard options
        assert "json" in param_names


class TestRegisterQueryCommands:
    """Test query command registration."""

    @patch("scriptrag.cli.commands.query.get_settings")
    @patch("scriptrag.cli.commands.query.QueryAPI")
    def test_register_query_commands_no_queries(
        self, mock_api_class, mock_get_settings
    ):
        """Test registering commands when no queries found."""
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api
        mock_api.list_queries.return_value = []

        with patch("scriptrag.config.settings._settings", None):
            # Force registration to ensure it runs
            register_query_commands(force=True)

        # Should create API and reload queries
        mock_api_class.assert_called_once_with(mock_settings)
        mock_api.reload_queries.assert_called_once()
        mock_api.list_queries.assert_called_once()

    @patch("scriptrag.cli.commands.query.get_settings")
    @patch("scriptrag.cli.commands.query.QueryAPI")
    @patch("scriptrag.cli.commands.query.create_query_command")
    def test_register_query_commands_with_queries(
        self, mock_create_command, mock_api_class, mock_get_settings
    ):
        """Test registering commands with queries."""
        # Setup mocks
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api

        mock_spec = QuerySpec(name="test-query", description="Test", sql="SELECT 1")
        mock_api.list_queries.return_value = [mock_spec]

        mock_command = MagicMock()
        mock_create_command.return_value = mock_command

        with patch("scriptrag.config.settings._settings", None):
            # Force registration to ensure it runs
            register_query_commands(force=True)

        # Should create command for each query
        mock_create_command.assert_called_once_with(mock_api, "test-query")

    @patch("scriptrag.cli.commands.query.get_settings")
    @patch("scriptrag.cli.commands.query.QueryAPI")
    @patch("scriptrag.cli.commands.query.create_query_command")
    def test_register_query_commands_command_creation_fails(
        self, mock_create_command, mock_api_class, mock_get_settings
    ):
        """Test registering commands when command creation fails."""
        # Setup mocks
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings
        mock_api = MagicMock()
        mock_api_class.return_value = mock_api

        mock_spec = QuerySpec(name="test-query", description="Test", sql="SELECT 1")
        mock_api.list_queries.return_value = [mock_spec]

        # Command creation returns None (failure)
        mock_create_command.return_value = None

        with patch("scriptrag.config.settings._settings", None):
            # Force registration to ensure it runs
            register_query_commands(force=True)

        # Should attempt to create command but handle None gracefully
        mock_create_command.assert_called_once_with(mock_api, "test-query")

    def test_create_query_command_spec_none(self):
        """Test creating command when spec is None - line 33 coverage."""
        mock_api = MagicMock()
        # get_query returns None
        mock_api.get_query.return_value = None

        result = create_query_command(mock_api, "nonexistent")

        assert result is None
        mock_api.get_query.assert_called_once_with("nonexistent")

    @patch("scriptrag.cli.commands.query.get_settings")
    @patch("scriptrag.cli.commands.query.QueryAPI")
    def test_query_command_json_output_path(self, mock_api_class, mock_get_settings):
        """Test query command JSON output path - line 68 coverage."""
        # Setup initial mock API for command creation
        mock_initial_api = MagicMock()

        # Create a simple spec
        spec = QuerySpec(
            name="test_query",
            description="Test query",
            params=[],
            sql="SELECT * FROM test",
        )

        mock_initial_api.get_query.return_value = spec

        # Setup runtime API that will succeed
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings
        mock_runtime_api = MagicMock()
        mock_api_class.return_value = mock_runtime_api
        mock_runtime_api.execute_query.return_value = '{"result": "json output"}'

        # Create the command function using initial API
        command = create_query_command(mock_initial_api, "test_query")
        assert command is not None

        # Execute with JSON output - creates new API via QueryAPI(current_settings)
        with (
            patch("scriptrag.config.settings._settings", None),
            patch("builtins.print") as mock_print,
        ):
            command(json=True)

        # Should print JSON result
        mock_print.assert_called_once_with('{"result": "json output"}')

    @patch("scriptrag.cli.commands.query.get_settings")
    @patch("scriptrag.cli.commands.query.QueryAPI")
    def test_query_command_error_handling_paths(
        self, mock_api_class, mock_get_settings
    ):
        """Test query command error handling - lines 92, 94, 101-103 coverage."""
        # Setup initial mock API for command creation
        mock_initial_api = MagicMock()

        # Create a spec with error callback
        spec = QuerySpec(
            name="test_query",
            description="Test query",
            params=[],
            sql="SELECT * FROM test",
        )

        mock_initial_api.get_query.return_value = spec

        # Setup runtime API that will fail
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings
        mock_runtime_api = MagicMock()
        mock_api_class.return_value = mock_runtime_api
        mock_runtime_api.execute_query.side_effect = ValueError(
            "Query 'test_query' not found"
        )

        # Create the command function using initial API
        command = create_query_command(mock_initial_api, "test_query")
        assert command is not None

        # Execute and expect typer.Exit - creates new API via QueryAPI(current_settings)
        with (
            patch("scriptrag.config.settings._settings", None),
            patch("scriptrag.cli.commands.query.console") as mock_console,
            pytest.raises(typer.Exit) as exc_info,
        ):
            command()

        assert exc_info.value.exit_code == 1
        expected_msg = (
            "[red]Error executing query 'test_query': "
            "Query 'test_query' not found[/red]"
        )
        mock_console.print.assert_called_with(expected_msg)

    def test_empty_query_list_command(self):
        """Test empty query list command - lines 221-229 coverage."""
        # Test the case when no queries are found
        with patch("scriptrag.cli.commands.query.QueryAPI") as mock_api_class:
            mock_api = MagicMock()
            mock_api.list_queries.return_value = []
            mock_api_class.return_value = mock_api

            # The empty query behavior is covered by the get_query_app function
            # We just need to verify the app is returned
            app = get_query_app()
            assert app is not None


class TestLazyLoading:
    """Test lazy loading of query commands."""

    @patch("scriptrag.cli.commands.query.register_query_commands")
    def test_get_query_app_lazy_initialization(self, mock_register):
        """Test that get_query_app initializes lazily."""
        # Reset global state for this test
        import scriptrag.cli.commands.query as query_module

        query_module.query_app = None
        query_module._commands_registered = False

        # Call get_query_app
        app = get_query_app()

        # Should have created app and called register
        assert app is not None
        mock_register.assert_called_once()

    @patch("scriptrag.cli.commands.query.register_query_commands")
    def test_get_query_app_reuses_existing(self, mock_register):
        """Test that get_query_app reuses existing app."""
        # Reset and initialize
        import scriptrag.cli.commands.query as query_module

        query_module.query_app = None
        query_module._commands_registered = False

        # First call
        app1 = get_query_app()
        mock_register.assert_called_once()

        # Second call should reuse
        app2 = get_query_app()
        assert app1 is app2
        # Still only called once
        mock_register.assert_called_once()

    def test_register_query_commands_handles_exception(self):
        """Test that register_query_commands handles exceptions gracefully."""
        # Reset global state for this test
        import scriptrag.cli.commands.query as query_module

        query_module._commands_registered = False

        with patch("scriptrag.cli.commands.query.get_settings") as mock_get_settings:
            # Make get_settings raise an exception
            mock_get_settings.side_effect = Exception("Settings error")

            # Should not raise, just return early
            register_query_commands(force=True)

            # The function should have attempted to get settings
            mock_get_settings.assert_called_once()
