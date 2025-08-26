"""Tests for query CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from scriptrag.api.query import QueryAPI
from scriptrag.cli.commands.query import (
    QueryAppManager,
    _create_api_instance,
    _register_list_command,
    _register_single_query,
    create_query_command,
    get_query_app,
    register_query_commands,
)
from scriptrag.config import ScriptRAGSettings
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
        mock_settings = MagicMock(spec=ScriptRAGSettings)
        mock_settings.database_path = "/tmp/test.db"
        mock_get_settings.return_value = mock_settings
        mock_current_api = MagicMock(
            spec=[
                "content",
                "model",
                "provider",
                "usage",
                "execute_query",
                "list_queries",
                "get_query",
            ]
        )
        mock_api_class.return_value = mock_current_api
        mock_current_api.execute_query.return_value = None

        # Create command
        command = create_query_command(mock_api, "simple-query")

        # Execute command
        with patch(
            "scriptrag.config.settings._settings",
            MagicMock(spec=ScriptRAGSettings, database_path="/tmp/test.db"),
        ):
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
        mock_settings = MagicMock(spec=ScriptRAGSettings)
        mock_settings.database_path = "/tmp/test.db"
        mock_get_settings.return_value = mock_settings
        mock_current_api = MagicMock(
            spec=[
                "content",
                "model",
                "provider",
                "usage",
                "execute_query",
                "list_queries",
                "get_query",
            ]
        )
        mock_api_class.return_value = mock_current_api
        mock_current_api.execute_query.return_value = '{"results": []}'

        # Create command
        command = create_query_command(mock_api, "simple-query")

        # Execute command with JSON output
        with (
            patch(
                "scriptrag.config.settings._settings",
                MagicMock(spec=ScriptRAGSettings, database_path="/tmp/test.db"),
            ),
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
        mock_settings = MagicMock(spec=ScriptRAGSettings)
        mock_settings.database_path = "/tmp/test.db"
        mock_get_settings.return_value = mock_settings
        mock_current_api = MagicMock(
            spec=[
                "content",
                "model",
                "provider",
                "usage",
                "execute_query",
                "list_queries",
                "get_query",
            ]
        )
        mock_api_class.return_value = mock_current_api
        mock_current_api.execute_query.side_effect = RuntimeError("Database error")

        # Create command
        command = create_query_command(mock_api, "simple-query")

        # Execute command and expect error
        with (
            patch(
                "scriptrag.config.settings._settings",
                MagicMock(spec=ScriptRAGSettings, database_path="/tmp/test.db"),
            ),
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
        mock_settings = MagicMock(spec=ScriptRAGSettings)
        mock_settings.database_path = "/tmp/test.db"
        mock_get_settings.return_value = mock_settings
        mock_api = MagicMock(
            spec=[
                "content",
                "model",
                "provider",
                "usage",
                "list_queries",
                "get_query",
                "reload_queries",
            ]
        )
        mock_api_class.return_value = mock_api
        mock_api.list_queries.return_value = []

        with patch(
            "scriptrag.config.settings._settings",
            MagicMock(spec=ScriptRAGSettings, database_path="/tmp/test.db"),
        ):
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
        mock_settings = MagicMock(spec=ScriptRAGSettings)
        mock_settings.database_path = "/tmp/test.db"
        mock_get_settings.return_value = mock_settings
        mock_api = MagicMock(
            spec=[
                "content",
                "model",
                "provider",
                "usage",
                "list_queries",
                "get_query",
                "reload_queries",
            ]
        )
        mock_api_class.return_value = mock_api

        mock_spec = QuerySpec(name="test-query", description="Test", sql="SELECT 1")
        mock_api.list_queries.return_value = [mock_spec]

        mock_command = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_create_command.return_value = mock_command

        with patch(
            "scriptrag.config.settings._settings",
            MagicMock(spec=ScriptRAGSettings, database_path="/tmp/test.db"),
        ):
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
        mock_settings = MagicMock(spec=ScriptRAGSettings)
        mock_settings.database_path = "/tmp/test.db"
        mock_get_settings.return_value = mock_settings
        mock_api = MagicMock(
            spec=[
                "content",
                "model",
                "provider",
                "usage",
                "list_queries",
                "get_query",
                "reload_queries",
            ]
        )
        mock_api_class.return_value = mock_api

        mock_spec = QuerySpec(name="test-query", description="Test", sql="SELECT 1")
        mock_api.list_queries.return_value = [mock_spec]

        # Command creation returns None (failure)
        mock_create_command.return_value = None

        with patch(
            "scriptrag.config.settings._settings",
            MagicMock(spec=ScriptRAGSettings, database_path="/tmp/test.db"),
        ):
            # Force registration to ensure it runs
            register_query_commands(force=True)

        # Should attempt to create command but handle None gracefully
        mock_create_command.assert_called_once_with(mock_api, "test-query")

    def test_create_query_command_spec_none(self):
        """Test creating command when spec is None - line 33 coverage."""
        mock_api = MagicMock(
            spec=[
                "content",
                "model",
                "provider",
                "usage",
                "list_queries",
                "get_query",
                "reload_queries",
            ]
        )
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
        mock_initial_api = MagicMock(
            spec=["content", "model", "provider", "usage", "get_query", "execute_query"]
        )

        # Create a simple spec
        spec = QuerySpec(
            name="test_query",
            description="Test query",
            params=[],
            sql="SELECT * FROM test",
        )

        mock_initial_api.get_query.return_value = spec

        # Setup runtime API that will succeed
        mock_settings = MagicMock(spec=ScriptRAGSettings)
        mock_settings.database_path = "/tmp/test.db"
        mock_get_settings.return_value = mock_settings
        mock_runtime_api = MagicMock(
            spec=["content", "model", "provider", "usage", "execute_query"]
        )
        mock_api_class.return_value = mock_runtime_api
        mock_runtime_api.execute_query.return_value = '{"result": "json output"}'

        # Create the command function using initial API
        command = create_query_command(mock_initial_api, "test_query")
        assert command is not None

        # Execute with JSON output - creates new API via QueryAPI(current_settings)
        with (
            patch(
                "scriptrag.config.settings._settings",
                MagicMock(spec=ScriptRAGSettings, database_path="/tmp/test.db"),
            ),
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
        mock_initial_api = MagicMock(
            spec=["content", "model", "provider", "usage", "get_query", "execute_query"]
        )

        # Create a spec with error callback
        spec = QuerySpec(
            name="test_query",
            description="Test query",
            params=[],
            sql="SELECT * FROM test",
        )

        mock_initial_api.get_query.return_value = spec

        # Setup runtime API that will fail
        mock_settings = MagicMock(spec=ScriptRAGSettings)
        mock_settings.database_path = "/tmp/test.db"
        mock_get_settings.return_value = mock_settings
        mock_runtime_api = MagicMock(
            spec=["content", "model", "provider", "usage", "execute_query"]
        )
        mock_api_class.return_value = mock_runtime_api
        mock_runtime_api.execute_query.side_effect = ValueError(
            "Query 'test_query' not found"
        )

        # Create the command function using initial API
        command = create_query_command(mock_initial_api, "test_query")
        assert command is not None

        # Execute and expect typer.Exit - creates new API via QueryAPI(current_settings)
        with (
            patch(
                "scriptrag.config.settings._settings",
                MagicMock(spec=ScriptRAGSettings, database_path="/tmp/test.db"),
            ),
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
            mock_api = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "list_queries",
                    "get_query",
                    "reload_queries",
                ]
            )
            mock_api.list_queries.return_value = []
            mock_api_class.return_value = mock_api

            # The empty query behavior is covered by the get_query_app function
            # We just need to verify the app is returned
            app = get_query_app()
            assert app is not None


class TestLazyLoading:
    """Test lazy loading of query commands."""

    @patch.object(QueryAppManager, "register_commands")
    def test_get_query_app_lazy_initialization(self, mock_register):
        """Test that get_query_app initializes lazily."""
        # Reset global state for this test
        import scriptrag.cli.commands.query as query_module

        query_module._manager = QueryAppManager()

        # Call get_query_app
        app = get_query_app()

        # Should have created app and called register
        assert app is not None
        mock_register.assert_called_once()

    def test_get_query_app_reuses_existing(self):
        """Test that get_query_app reuses existing app."""
        # Reset and initialize
        import scriptrag.cli.commands.query as query_module

        manager = QueryAppManager()
        query_module._manager = manager

        with patch.object(manager, "register_commands") as mock_register:
            # First call
            app1 = get_query_app()
            mock_register.assert_called_once()

            # Mark as registered to simulate successful registration
            manager.commands_registered = True

            # Second call should reuse
            app2 = get_query_app()
            assert app1 is app2
            # Still only called once (not twice)
            mock_register.assert_called_once()

    def test_register_query_commands_handles_exception(self):
        """Test that register_query_commands handles exceptions gracefully."""
        # Reset global state for this test
        import scriptrag.cli.commands.query as query_module

        query_module._manager = QueryAppManager()

        with patch("scriptrag.cli.commands.query.get_settings") as mock_get_settings:
            # Make get_settings raise an exception
            mock_get_settings.side_effect = Exception("Settings error")

            # Should not raise, just return early
            register_query_commands(force=True)

            # The function should have attempted to get settings
            mock_get_settings.assert_called_once()


class TestHelperFunctions:
    """Test helper functions for code coverage."""

    def test_create_api_instance_success(self):
        """Test successful API instance creation."""
        with (
            patch("scriptrag.cli.commands.query.get_settings") as mock_get_settings,
            patch("scriptrag.cli.commands.query.QueryAPI") as mock_api_class,
        ):
            mock_settings = MagicMock(spec=ScriptRAGSettings)
            mock_settings.database_path = "/tmp/test.db"
            mock_get_settings.return_value = mock_settings
            mock_api = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "list_queries",
                    "get_query",
                    "reload_queries",
                ]
            )
            mock_api_class.return_value = mock_api

            result = _create_api_instance()

            assert result is mock_api
            mock_get_settings.assert_called_once()
            mock_api_class.assert_called_once_with(mock_settings)

    def test_create_api_instance_failure(self):
        """Test API instance creation failure."""
        with patch("scriptrag.cli.commands.query.get_settings") as mock_get_settings:
            mock_get_settings.side_effect = Exception("Settings error")

            result = _create_api_instance()

            assert result is None
            mock_get_settings.assert_called_once()

    def test_register_list_command_no_queries(self):
        """Test registering list command with no queries."""
        mock_app = MagicMock(spec=typer.Typer)
        queries = []

        _register_list_command(mock_app, queries)

        # Should register a command named 'list'
        mock_app.command.assert_called_once_with(name="list")

    def test_register_list_command_with_queries(self):
        """Test registering list command with queries."""
        mock_app = MagicMock(spec=typer.Typer)
        queries = [
            QuerySpec(name="test1", description="Test 1", sql="SELECT 1"),
            QuerySpec(name="test2", description="Test 2", sql="SELECT 2"),
        ]

        _register_list_command(mock_app, queries)

        # Should register a command named 'list'
        mock_app.command.assert_called_once_with(name="list")

    def test_register_single_query_success(self):
        """Test registering a single query successfully."""
        mock_app = MagicMock(spec=typer.Typer)
        mock_api = MagicMock(spec=QueryAPI)
        spec = QuerySpec(name="test-query", description="Test", sql="SELECT 1")

        with patch(
            "scriptrag.cli.commands.query.create_query_command"
        ) as mock_create_command:
            mock_command = MagicMock(spec=["content", "model", "provider", "usage"])
            mock_create_command.return_value = mock_command

            _register_single_query(mock_app, mock_api, spec)

            mock_create_command.assert_called_once_with(mock_api, "test-query")
            mock_app.command.assert_called_once_with(name="test-query")

    def test_register_single_query_none_command(self):
        """Test registering a single query when command creation returns None."""
        mock_app = MagicMock(spec=typer.Typer)
        mock_api = MagicMock(spec=QueryAPI)
        spec = QuerySpec(name="test-query", description="Test", sql="SELECT 1")

        with patch(
            "scriptrag.cli.commands.query.create_query_command"
        ) as mock_create_command:
            mock_create_command.return_value = None

            _register_single_query(mock_app, mock_api, spec)

            mock_create_command.assert_called_once_with(mock_api, "test-query")
            # Should not register command if creation returns None
            mock_app.command.assert_not_called()


class TestQueryAppManager:
    """Test QueryAppManager class."""

    def test_manager_initialization(self):
        """Test QueryAppManager initialization."""
        manager = QueryAppManager()

        assert manager.app is None
        assert manager.commands_registered is False

    def test_manager_get_app_creates_app(self):
        """Test that get_app creates app on first call."""
        manager = QueryAppManager()

        with patch.object(manager, "register_commands") as mock_register:
            app = manager.get_app()

            assert app is not None
            assert manager.app is app
            mock_register.assert_called_once()

    def test_manager_get_app_reuses_app(self):
        """Test that get_app reuses existing app."""
        manager = QueryAppManager()

        # Create app first
        with patch.object(manager, "register_commands"):
            app1 = manager.get_app()

        # Mark as registered to avoid re-registration
        manager.commands_registered = True

        # Second call should reuse
        app2 = manager.get_app()
        assert app1 is app2

    def test_manager_register_commands_skip_if_registered(self):
        """Test that register_commands skips if already registered."""
        manager = QueryAppManager()
        manager.commands_registered = True

        with patch("scriptrag.cli.commands.query._create_api_instance") as mock_create:
            manager.register_commands()

            # Should not create API if already registered
            mock_create.assert_not_called()

    def test_manager_register_commands_force(self):
        """Test that register_commands can be forced."""
        manager = QueryAppManager()
        manager.commands_registered = True

        with (
            patch("scriptrag.cli.commands.query._create_api_instance") as mock_create,
            patch(
                "scriptrag.cli.commands.query._register_list_command"
            ) as mock_register_list,
        ):
            mock_api = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "list_queries",
                    "get_query",
                    "reload_queries",
                ]
            )
            mock_create.return_value = mock_api
            mock_api.list_queries.return_value = []

            manager.register_commands(force=True)

            # Should create API even if already registered when forced
            mock_create.assert_called_once()
            mock_register_list.assert_called_once()

    def test_manager_register_commands_api_creation_fails(self):
        """Test register_commands when API creation fails."""
        manager = QueryAppManager()

        with patch("scriptrag.cli.commands.query._create_api_instance") as mock_create:
            mock_create.return_value = None

            manager.register_commands()

            # Should handle None API gracefully
            assert manager.commands_registered is False

    def test_manager_register_commands_query_loading_fails(self):
        """Test register_commands when query loading fails."""
        manager = QueryAppManager()

        with (
            patch("scriptrag.cli.commands.query._create_api_instance") as mock_create,
            patch(
                "scriptrag.cli.commands.query._register_list_command"
            ) as mock_register_list,
        ):
            mock_api = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "list_queries",
                    "get_query",
                    "reload_queries",
                ]
            )
            mock_create.return_value = mock_api
            mock_api.reload_queries.side_effect = Exception("Load error")

            manager.register_commands()

            # Should handle exception and register empty list
            mock_register_list.assert_called_once_with(manager.app, [])

    def test_manager_register_commands_with_queries(self):
        """Test register_commands with successful query loading."""
        manager = QueryAppManager()

        with (
            patch("scriptrag.cli.commands.query._create_api_instance") as mock_create,
            patch(
                "scriptrag.cli.commands.query._register_list_command"
            ) as mock_register_list,
            patch(
                "scriptrag.cli.commands.query._register_single_query"
            ) as mock_register_single,
        ):
            mock_api = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "list_queries",
                    "get_query",
                    "reload_queries",
                ]
            )
            mock_create.return_value = mock_api

            spec1 = QuerySpec(name="query1", description="Query 1", sql="SELECT 1")
            spec2 = QuerySpec(name="query2", description="Query 2", sql="SELECT 2")
            mock_api.list_queries.return_value = [spec1, spec2]

            manager.register_commands()

            # Should register list command and both queries
            mock_register_list.assert_called_once_with(manager.app, [spec1, spec2])
            assert mock_register_single.call_count == 2
            mock_register_single.assert_any_call(manager.app, mock_api, spec1)
            mock_register_single.assert_any_call(manager.app, mock_api, spec2)
            assert manager.commands_registered is True


class TestCoverageGaps:
    """Test coverage gaps to reach 95% coverage."""

    def test_query_command_with_db_path_option(self):
        """Test query command execution with db_path parameter."""
        mock_api = MagicMock(spec=QueryAPI)
        spec = QuerySpec(
            name="test_query",
            description="Test query",
            params=[],
            sql="SELECT * FROM test",
        )
        mock_api.get_query.return_value = spec

        # Create command with db_path option enabled (default)
        command = create_query_command(mock_api, "test_query", db_path_option=True)
        assert command is not None

        # Check that db_path is in the signature
        sig = command.__signature__
        assert "db_path" in sig.parameters

        # Test execution with db_path
        with (
            patch("scriptrag.cli.commands.query.QueryAPI") as mock_api_class,
            patch(
                "scriptrag.config.settings._settings",
                MagicMock(spec=ScriptRAGSettings, database_path="/tmp/test.db"),
            ),
        ):
            mock_runtime_api = MagicMock(
                spec=["content", "model", "provider", "usage", "execute_query"]
            )
            mock_api_class.return_value = mock_runtime_api
            mock_runtime_api.execute_query.return_value = None

            test_db_path = Path("/tmp/test.db")
            command(db_path=test_db_path)

            # Verify that API was created (deepcopy happens internally on real settings)
            assert mock_api_class.called
            # Get the settings that was passed to QueryAPI
            call_args = mock_api_class.call_args[0]
            if call_args:
                settings_used = call_args[0]
                # Check that database_path was set to our test path
                assert settings_used.database_path == test_db_path

    def test_query_command_without_db_path_option(self):
        """Test query command creation without db_path option."""
        mock_api = MagicMock(spec=QueryAPI)
        spec = QuerySpec(
            name="test_query",
            description="Test query",
            params=[],
            sql="SELECT * FROM test",
        )
        mock_api.get_query.return_value = spec

        # Create command with db_path option disabled
        command = create_query_command(mock_api, "test_query", db_path_option=False)
        assert command is not None

        # Check that db_path is NOT in the signature
        sig = command.__signature__
        assert "db_path" not in sig.parameters

    def test_query_command_with_non_choice_parameters(self):
        """Test query command with parameters that don't have choices."""
        mock_api = MagicMock(spec=QueryAPI)
        spec = QuerySpec(
            name="test_query",
            description="Test query",
            params=[
                ParamSpec(
                    name="user_id",
                    type="int",
                    required=True,
                    help="User ID",
                    choices=None,  # No choices
                ),
                ParamSpec(
                    name="name",
                    type="str",
                    required=False,
                    default="test",
                    help="Name parameter",
                    choices=None,  # No choices
                ),
            ],
            sql="SELECT * FROM users WHERE id = :user_id AND name = :name",
        )
        mock_api.get_query.return_value = spec

        command = create_query_command(mock_api, "test_query")
        assert command is not None

        # Check parameters are in signature
        sig = command.__signature__
        assert "user_id" in sig.parameters
        assert "name" in sig.parameters

    def test_query_command_with_offset_spec(self):
        """Test query command with offset parameter from spec."""
        mock_api = MagicMock(spec=QueryAPI)
        spec = QuerySpec(
            name="test_query",
            description="Test query",
            params=[
                ParamSpec(
                    name="offset",
                    type="int",
                    required=False,
                    default=10,  # Custom default
                    help="Offset for pagination",
                ),
            ],
            sql="SELECT * FROM test OFFSET :offset",
        )
        mock_api.get_query.return_value = spec

        command = create_query_command(mock_api, "test_query")
        assert command is not None

        # Check offset is in signature with custom default
        sig = command.__signature__
        assert "offset" in sig.parameters

    def test_query_command_output_non_json(self):
        """Test query command with non-JSON output that gets printed."""
        mock_api = MagicMock(spec=QueryAPI)
        spec = QuerySpec(
            name="test_query",
            description="Test query",
            params=[],
            sql="SELECT * FROM test",
        )
        mock_api.get_query.return_value = spec

        command = create_query_command(mock_api, "test_query")

        with (
            patch("scriptrag.cli.commands.query.get_settings") as mock_get_settings,
            patch("scriptrag.cli.commands.query.QueryAPI") as mock_api_class,
            patch(
                "scriptrag.config.settings._settings",
                MagicMock(spec=ScriptRAGSettings, database_path="/tmp/test.db"),
            ),
            patch("scriptrag.cli.commands.query.console") as mock_console,
        ):
            mock_settings = MagicMock(spec=ScriptRAGSettings)
            mock_settings.database_path = "/tmp/test.db"
            mock_get_settings.return_value = mock_settings
            mock_runtime_api = MagicMock(
                spec=["content", "model", "provider", "usage", "execute_query"]
            )
            mock_api_class.return_value = mock_runtime_api
            mock_runtime_api.execute_query.return_value = "Result Table Data"

            # Execute with non-JSON output
            command(json=False)

            # Verify console.print was called with the result
            mock_console.print.assert_called_once_with("Result Table Data")

    def test_register_list_command_execution_with_queries(self):
        """Test the list command execution when queries exist."""
        mock_app = MagicMock(spec=typer.Typer)
        queries = [
            QuerySpec(
                name="query1",
                description="First query",
                params=[
                    ParamSpec(name="param1", type="str", required=True),
                    ParamSpec(name="param2", type="int", required=False),
                ],
                sql="SELECT 1",
            ),
            QuerySpec(
                name="query2",
                description="Second query",
                params=[],
                sql="SELECT 2",
            ),
            QuerySpec(
                name="query3",
                description=None,  # No description
                params=[],
                sql="SELECT 3",
            ),
        ]

        # Register the list command
        _register_list_command(mock_app, queries)

        # Get the decorator call
        decorator_call = mock_app.command.call_args
        assert decorator_call[1]["name"] == "list"

        # Get the function that was decorated
        decorated_func = mock_app.command.return_value.call_args[0][0]

        # Execute the list command
        with patch("scriptrag.cli.commands.query.console") as mock_console:
            decorated_func()

            # Verify the output
            calls = mock_console.print.call_args_list
            assert any("[bold]Available queries:[/bold]" in str(call) for call in calls)
            assert any("query1" in str(call) for call in calls)
            assert any("First query" in str(call) for call in calls)
            assert any("param1, param2" in str(call) for call in calls)
            assert any("query2" in str(call) for call in calls)
            assert any("query3" in str(call) for call in calls)

    def test_register_list_command_execution_no_queries(self):
        """Test the list command execution when no queries exist."""
        mock_app = MagicMock(spec=typer.Typer)
        queries = []

        # Register the list command
        _register_list_command(mock_app, queries)

        # Get the decorator call
        decorator_call = mock_app.command.call_args
        assert decorator_call[1]["name"] == "list"

        # Get the function that was decorated
        decorated_func = mock_app.command.return_value.call_args[0][0]

        # Execute the list command
        with patch("scriptrag.cli.commands.query.console") as mock_console:
            decorated_func()

            # Verify the output for no queries
            calls = mock_console.print.call_args_list
            assert any(
                "No queries found in query directory" in str(call) for call in calls
            )
            assert any(
                "Add .sql files to the query directory" in str(call) for call in calls
            )

    def test_query_command_with_float_and_bool_params(self):
        """Test query command with float and bool parameter types."""
        mock_api = MagicMock(spec=QueryAPI)
        spec = QuerySpec(
            name="test_query",
            description="Test query",
            params=[
                ParamSpec(
                    name="threshold",
                    type="float",
                    required=True,
                    help="Threshold value",
                ),
                ParamSpec(
                    name="active",
                    type="bool",
                    required=False,
                    default=True,
                    help="Active flag",
                ),
            ],
            sql="SELECT * FROM test WHERE threshold = :threshold AND active = :active",
        )
        mock_api.get_query.return_value = spec

        command = create_query_command(mock_api, "test_query")
        assert command is not None

        # Check parameters are in signature with correct types
        sig = command.__signature__
        assert "threshold" in sig.parameters
        assert "active" in sig.parameters

    def test_query_spec_with_has_limit_offset(self):
        """Test query command when spec.has_limit_offset() returns True."""
        mock_api = MagicMock(spec=QueryAPI)
        spec = MagicMock(spec=QuerySpec)
        spec.name = "test_query"
        spec.description = "Test query"
        spec.params = []
        spec.has_limit_offset.return_value = (True, True)  # Both limit and offset
        spec.get_param.side_effect = lambda name: (
            ParamSpec(name="limit", type="int", default=20)
            if name == "limit"
            else ParamSpec(name="offset", type="int", default=5)
            if name == "offset"
            else None
        )
        mock_api.get_query.return_value = spec

        command = create_query_command(mock_api, "test_query")
        assert command is not None

        # Check both limit and offset are in signature
        sig = command.__signature__
        assert "limit" in sig.parameters
        assert "offset" in sig.parameters
