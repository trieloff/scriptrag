"""Extended tests for query CLI commands to improve coverage."""

import json
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from scriptrag.api.query import QueryAPI
from scriptrag.cli.commands.query import QueryCommandBuilder, get_query_app
from scriptrag.query.spec import ParamSpec, QuerySpec


class TestQueryCommandExtended:
    """Extended tests for query command coverage."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_api(self):
        """Create mock QueryAPI."""
        api = MagicMock(spec=QueryAPI)
        api.reload_queries.return_value = None
        return api

    @pytest.fixture
    def sample_queries(self):
        """Create sample query specs."""
        return [
            QuerySpec(
                name="scene-count",
                description="Count scenes per script",
                sql="SELECT script_id, COUNT(*) FROM scenes GROUP BY script_id",
            ),
            QuerySpec(
                name="character-lines",
                description="Get character dialogue",
                params=[
                    ParamSpec(
                        name="character",
                        type="str",
                        required=True,
                        help="Character name",
                    ),
                    ParamSpec(name="limit", type="int", required=False, default=10),
                ],
                sql="SELECT * FROM dialogue WHERE character = :character LIMIT :limit",
            ),
        ]

    def test_list_queries_json_output(self, mock_api, sample_queries, runner):
        """Test list command with JSON output."""
        mock_api.list_queries.return_value = sample_queries

        builder = QueryCommandBuilder(mock_api)
        list_command = builder._create_list_command()

        # Create a test context and execute
        with patch("scriptrag.cli.commands.query.console") as mock_console:
            list_command(json_output=True, verbose=False)

            # Check that JSON was printed
            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            data = json.loads(call_args)

            assert len(data) == 2
            assert data[0]["name"] == "scene-count"
            assert data[1]["name"] == "character-lines"
            assert len(data[1]["parameters"]) == 2

    def test_list_queries_verbose_table(self, mock_api, sample_queries):
        """Test list command with verbose table output."""
        mock_api.list_queries.return_value = sample_queries

        builder = QueryCommandBuilder(mock_api)
        list_command = builder._create_list_command()

        with patch("scriptrag.cli.commands.query.console") as mock_console:
            list_command(json_output=False, verbose=True)

            # Should print header and query info
            assert mock_console.print.call_count >= 3

    def test_list_queries_empty(self, mock_api):
        """Test list command with no queries available."""
        mock_api.list_queries.return_value = []

        builder = QueryCommandBuilder(mock_api)
        list_command = builder._create_list_command()

        with patch("scriptrag.cli.commands.query.console") as mock_console:
            list_command(json_output=False, verbose=False)

            mock_console.print.assert_called_with("[dim]No queries available[/dim]")

    def test_list_queries_error_handling(self, mock_api):
        """Test list command error handling."""
        mock_api.list_queries.side_effect = Exception("Database error")

        builder = QueryCommandBuilder(mock_api)
        list_command = builder._create_list_command()

        with patch("scriptrag.cli.commands.query.console"):
            with patch.object(builder.handler, "handle_error") as mock_handler:
                list_command(json_output=False, verbose=False)

                mock_handler.assert_called_once()
                error = mock_handler.call_args[0][0]
                assert str(error) == "Database error"

    def test_query_command_execution_json(self, mock_api):
        """Test query command execution with JSON output."""
        spec = QuerySpec(
            name="test-query",
            description="Test query",
            sql="SELECT * FROM test",
        )
        mock_api.list_queries.return_value = [spec]
        mock_api.execute_query.return_value = [{"id": 1, "name": "Test"}]

        builder = QueryCommandBuilder(mock_api)
        app = builder.create_query_app()

        # Find the registered command
        command_func = None
        for cmd in app.registered_commands:
            if cmd.name == "test-query":
                command_func = cmd.callback
                break

        assert command_func is not None

        # Execute with JSON output
        with patch("scriptrag.cli.commands.query.console") as mock_console:
            command_func(json=True, csv=False, markdown=False)

            mock_api.execute_query.assert_called_with(
                "test-query",
                {"json": True, "csv": False, "markdown": False},
                output_json=True,
            )
            mock_console.print.assert_called_once()

    def test_query_command_execution_csv(self, mock_api):
        """Test query command execution with CSV output."""
        spec = QuerySpec(
            name="test-query",
            description="Test query",
            sql="SELECT * FROM test",
        )
        mock_api.list_queries.return_value = [spec]
        mock_api.execute_query.return_value = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]

        builder = QueryCommandBuilder(mock_api)

        # Register the command
        with patch("typer.Typer.command") as mock_command:
            builder._register_query_command(MagicMock(), spec)

            # Get the created command function
            command_func = mock_command.call_args[0][0]

            # Execute with CSV output
            with patch("scriptrag.cli.commands.query.console"):
                with patch.object(builder.formatter, "format") as mock_format:
                    command_func(json=False, csv=True, markdown=False)

                    # Check formatter was called
                    assert mock_format.called

    def test_query_command_execution_markdown(self, mock_api):
        """Test query command execution with Markdown output."""
        spec = QuerySpec(
            name="test-query",
            description="Test query",
            params=[ParamSpec(name="id", type="int", required=True)],
            sql="SELECT * FROM test WHERE id = :id",
        )

        mock_api.list_queries.return_value = [spec]
        mock_api.execute_query.return_value = [{"id": 1, "name": "Test"}]

        builder = QueryCommandBuilder(mock_api)
        app = builder.create_query_app()

        # Find the registered command
        command_func = None
        for cmd in app.registered_commands:
            if cmd.name == "test-query":
                command_func = cmd.callback
                break

        assert command_func is not None

        with patch("scriptrag.cli.commands.query.console"):
            command_func(id=1, json=False, csv=False, markdown=True)

            mock_api.execute_query.assert_called_once()

    def test_query_command_error_handling(self, mock_api):
        """Test query command error handling."""
        spec = QuerySpec(name="failing-query", description="Fails", sql="SELECT")
        mock_api.list_queries.return_value = [spec]
        mock_api.execute_query.side_effect = Exception("SQL error")

        builder = QueryCommandBuilder(mock_api)
        app = builder.create_query_app()

        # Find the registered command
        command_func = None
        for cmd in app.registered_commands:
            if cmd.name == "failing-query":
                command_func = cmd.callback
                break

        assert command_func is not None

        with patch("scriptrag.cli.commands.query.console"):
            # The command should handle the error gracefully
            command_func(json=False, csv=False, markdown=False)

    def test_get_query_app_function(self):
        """Test the get_query_app lazy loading function."""
        with patch("scriptrag.cli.commands.query.get_settings") as mock_settings:
            with patch("scriptrag.cli.commands.query.QueryAPI") as mock_api_class:
                mock_api = MagicMock()
                mock_api.list_queries.return_value = []
                mock_api_class.return_value = mock_api

                app = get_query_app()

                assert isinstance(app, typer.Typer)
                mock_api_class.assert_called_once()

    def test_register_query_with_parameters(self, mock_api):
        """Test registering a query with multiple parameter types."""
        spec = QuerySpec(
            name="complex-query",
            description="Complex query with params",
            params=[
                ParamSpec(name="text", type="str", required=True, help="Text param"),
                ParamSpec(name="number", type="int", required=False, default=42),
                ParamSpec(name="flag", type="bool", required=False, default=False),
                ParamSpec(
                    name="choice",
                    type="str",
                    required=False,
                    choices=["a", "b", "c"],
                    default="a",
                ),
            ],
            sql="SELECT :text, :number, :flag, :choice",
        )

        builder = QueryCommandBuilder(mock_api)
        app = typer.Typer()

        # Register the command
        builder._register_query_command(app, spec)

        # Check command was registered
        assert len(app.registered_commands) == 1
        cmd = app.registered_commands[0]
        assert cmd.name == "complex-query"
        assert cmd.help == "Complex query with params"
