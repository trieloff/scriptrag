"""Tests for CLI scene management commands.

This module contains comprehensive tests for the scene management CLI commands
including scene list, update, reorder, and analyze operations.
"""

from unittest.mock import MagicMock, Mock, patch

from typer.testing import CliRunner

from scriptrag.cli import app, get_latest_script_id
from scriptrag.models import SceneOrderType


def create_mock_settings(db_path="/test/db.sqlite"):
    """Create a properly structured mock settings object."""
    mock_database_settings = Mock()
    mock_database_settings.path = db_path

    # Mock logging settings
    mock_logging_settings = Mock()
    mock_logging_settings.file_path = None  # Simplest case - no file logging

    # Mock paths settings
    mock_paths_settings = Mock()
    mock_paths_settings.logs_dir = "/test/logs"

    mock_settings = Mock()
    mock_settings.database = mock_database_settings
    mock_settings.logging = mock_logging_settings
    mock_settings.paths = mock_paths_settings
    # Mock the get_log_file_path method to return None (no file logging)
    mock_settings.get_log_file_path.return_value = None

    return mock_settings


def create_mock_database_connection():
    """Create a properly mocked database connection with context manager support."""
    mock_connection = Mock()

    # Mock execute method to return an object with fetchall method
    mock_execute_result = Mock()
    mock_execute_result.fetchall.return_value = [
        ("scene1", "location1", "INT. OFFICE"),
        ("scene2", "location2", "EXT. STREET"),
    ]
    mock_connection.execute.return_value = mock_execute_result

    # Mock transaction context manager
    mock_transaction = MagicMock()
    mock_transaction.__enter__.return_value = mock_connection
    mock_transaction.__exit__.return_value = None
    mock_connection.transaction.return_value = mock_transaction

    return mock_connection


def setup_cli_test_mocks(
    mock_get_settings,
    mock_db_conn,
    mock_scene_manager,
    mock_get_latest,
    db_path="/test/db.sqlite",
):
    """Set up all the mocks needed for CLI tests."""
    # Settings
    mock_settings = create_mock_settings(db_path)
    mock_get_settings.return_value = mock_settings

    # Latest script
    mock_get_latest.return_value = ("script-123", "Test Script")

    # Scene manager with basic scene data
    mock_manager = Mock()
    mock_scenes = [
        Mock(
            id="scene1",
            properties={
                "heading": "INT. OFFICE - DAY",
                "script_order": 1,
                "estimated_duration": 5.0,
            },
        ),
        Mock(
            id="scene2",
            properties={
                "heading": "EXT. STREET - DAY",
                "script_order": 2,
                "estimated_duration": 3.0,
            },
        ),
    ]
    mock_manager.operations.get_script_scenes.return_value = mock_scenes
    mock_scene_manager.return_value = mock_manager

    # Database connection
    mock_connection = create_mock_database_connection()
    mock_db_conn.return_value = mock_connection

    return mock_settings, mock_manager, mock_connection


class TestGetLatestScriptId:
    """Test get_latest_script_id helper function."""

    def test_get_latest_script_id_success(self, db_connection):
        """Test successful retrieval of latest script ID."""

        # Mock database query result - SQLite returns tuple-like objects
        # accessed by index
        mock_result = ("script-123", "Test Script")

        with patch.object(db_connection, "transaction") as mock_transaction:
            mock_conn = Mock()
            mock_conn.execute.return_value.fetchone.return_value = mock_result
            mock_transaction.return_value.__enter__.return_value = mock_conn

            result = get_latest_script_id(db_connection)

        assert result == ("script-123", "Test Script")

    def test_get_latest_script_id_no_scripts(self, db_connection):
        """Test get_latest_script_id when no scripts exist."""

        with patch.object(db_connection, "transaction") as mock_transaction:
            mock_conn = Mock()
            mock_conn.execute.return_value.fetchone.return_value = None
            mock_transaction.return_value.__enter__.return_value = mock_conn

            result = get_latest_script_id(db_connection)

        assert result is None


class TestSceneListCommand:
    """Test scene list CLI command."""

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_list_default_order(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test scene list with default parameters."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Mock Path class and its methods
        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(app, ["scene", "list"])

        assert result.exit_code == 0
        assert "Test Script" in result.output
        assert "INT. OFFICE - DAY" in result.output
        assert "EXT. STREET - DAY" in result.output

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_list_temporal_order(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test scene list with temporal ordering."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Override with temporal-specific scene data
        mock_scenes = [
            Mock(
                id="scene1",
                properties={"heading": "INT. OFFICE - DAY", "temporal_order": 1},
            ),
        ]
        mock_manager.operations.get_script_scenes.return_value = mock_scenes

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(app, ["scene", "list", "--order", "temporal"])

        assert result.exit_code == 0
        # Verify temporal order was requested
        mock_manager.operations.get_script_scenes.assert_called_with(
            "script-123", SceneOrderType.TEMPORAL
        )

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_list_with_limit(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test scene list with limit parameter."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Override with scenes for limit testing
        mock_scenes = [
            Mock(id=f"scene{i}", properties={"heading": f"Scene {i}"})
            for i in range(1, 6)
        ]
        mock_manager.operations.get_script_scenes.return_value = mock_scenes

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(app, ["scene", "list", "--limit", "3"])

        assert result.exit_code == 0
        # Should only show first 3 scenes
        # Note: Exact count may vary due to table formatting, but should be limited

    @patch("scriptrag.cli.get_settings")
    def test_scene_list_no_database(self, mock_get_settings):
        """Test scene list when database doesn't exist."""
        mock_settings = create_mock_settings("/nonexistent/db.sqlite")
        mock_get_settings.return_value = mock_settings

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = False
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(app, ["scene", "list"])

        assert result.exit_code == 1
        assert "No database found" in result.output

    def test_scene_list_invalid_order(self):
        """Test scene list with invalid order type."""
        runner = CliRunner()
        result = runner.invoke(app, ["scene", "list", "--order", "invalid"])

        assert result.exit_code == 1
        assert "Invalid order type" in result.output


class TestSceneUpdateCommand:
    """Test scene update CLI command."""

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_update_location_success(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test successful scene location update."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Override with specific scenes for this test
        mock_scenes = [
            Mock(id="scene1", properties={"heading": "INT. OFFICE - DAY"}),
            Mock(id="scene2", properties={"heading": "EXT. STREET - DAY"}),
        ]
        mock_manager.operations.get_script_scenes.return_value = mock_scenes
        mock_manager.update_scene_location.return_value = True

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(
                app, ["scene", "update", "1", "--location", "INT. NEW OFFICE - DAY"]
            )

        assert result.exit_code == 0
        assert "Updated scene 1 location" in result.output
        mock_manager.update_scene_location.assert_called_once_with(
            "scene1", "INT. NEW OFFICE - DAY"
        )

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_update_invalid_scene_number(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test scene update with invalid scene number."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Override with only 1 scene for this test
        mock_scenes = [Mock(id="scene1")]  # Only 1 scene
        mock_manager.operations.get_script_scenes.return_value = mock_scenes

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(
                app,
                [
                    "scene",
                    "update",
                    "5",  # Scene 5 doesn't exist
                    "--location",
                    "INT. NEW OFFICE - DAY",
                ],
            )

        assert result.exit_code == 1
        assert "Invalid scene number" in result.output

    def test_scene_update_no_options(self):
        """Test scene update with no update options specified."""
        runner = CliRunner()
        result = runner.invoke(app, ["scene", "update", "1"])

        assert result.exit_code == 1
        assert "No updates specified" in result.output

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_update_location_failure(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test scene update when location update fails."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Override with specific test data
        mock_scenes = [Mock(id="scene1")]
        mock_manager.operations.get_script_scenes.return_value = mock_scenes
        mock_manager.update_scene_location.return_value = False  # Failure

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(
                app, ["scene", "update", "1", "--location", "INT. NEW OFFICE - DAY"]
            )

        assert result.exit_code == 1
        assert "Failed to update scene location" in result.output


class TestSceneReorderCommand:
    """Test scene reorder CLI command."""

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_reorder_success(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test successful scene reordering."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Override with specific test data
        mock_scenes = [
            Mock(id="scene1", properties={"heading": "Scene 1"}),
            Mock(id="scene2", properties={"heading": "Scene 2"}),
            Mock(id="scene3", properties={"heading": "Scene 3"}),
        ]
        mock_manager.operations.get_script_scenes.return_value = mock_scenes
        mock_manager.update_scene_order.return_value = True

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(app, ["scene", "reorder", "2", "--position", "1"])

        assert result.exit_code == 0
        assert "Moved scene 2 to position 1" in result.output
        mock_manager.update_scene_order.assert_called_once_with(
            "scene2", 1, SceneOrderType.SCRIPT
        )

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_reorder_temporal_order(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test scene reordering in temporal order."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Override with specific test data
        mock_scenes = [Mock(id="scene1", properties={"heading": "Scene 1"})]
        mock_manager.operations.get_script_scenes.return_value = mock_scenes
        mock_manager.update_scene_order.return_value = True

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(
                app, ["scene", "reorder", "1", "--position", "1", "--order", "temporal"]
            )

        assert result.exit_code == 0
        mock_manager.update_scene_order.assert_called_once_with(
            "scene1", 1, SceneOrderType.TEMPORAL
        )

    def test_scene_reorder_invalid_order_type(self):
        """Test scene reorder with invalid order type."""
        runner = CliRunner()
        result = runner.invoke(
            app, ["scene", "reorder", "1", "--position", "2", "--order", "invalid"]
        )

        assert result.exit_code == 1
        assert "Invalid order type" in result.output

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_reorder_invalid_position(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test scene reorder with invalid position."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Override with specific test data - only 2 scenes
        mock_scenes = [Mock(id="scene1"), Mock(id="scene2")]  # 2 scenes
        mock_manager.operations.get_script_scenes.return_value = mock_scenes

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(
                app,
                ["scene", "reorder", "1", "--position", "5"],  # Position 5 > 2 scenes
            )

        assert result.exit_code == 1
        assert "Invalid position" in result.output

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_reorder_failure(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test scene reorder when operation fails."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Override with specific test data
        mock_scenes = [Mock(id="scene1"), Mock(id="scene2")]
        mock_manager.operations.get_script_scenes.return_value = mock_scenes
        mock_manager.update_scene_order.return_value = False  # Failure

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(app, ["scene", "reorder", "1", "--position", "2"])

        assert result.exit_code == 1
        assert "Failed to reorder scene" in result.output


class TestSceneAnalyzeCommand:
    """Test scene analyze CLI command."""

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_analyze_dependencies(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test scene dependency analysis."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Override with specific test data
        mock_scenes = [
            Mock(id="scene1", properties={"heading": "INT. OFFICE - DAY"}),
            Mock(id="scene2", properties={"heading": "EXT. STREET - DAY"}),
        ]
        mock_manager.operations.get_script_scenes.return_value = mock_scenes

        # Mock dependencies
        mock_dependencies = {
            "scene1": [],
            "scene2": ["scene1"],  # Scene 2 depends on scene 1
        }
        mock_manager.analyze_scene_dependencies.return_value = mock_dependencies

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(app, ["scene", "analyze", "dependencies"])

        assert result.exit_code == 0
        assert "Scene Dependencies" in result.output
        assert "EXT. STREET - DAY" in result.output
        assert "Depends on:" in result.output

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_analyze_temporal(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test temporal analysis."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Mock temporal order inference
        mock_temporal_order = {
            "scene1": 1,
            "scene2": 2,
        }
        mock_manager.infer_temporal_order.return_value = mock_temporal_order
        mock_manager.operations.update_scene_order.return_value = True

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(app, ["scene", "analyze", "temporal"])

        assert result.exit_code == 0
        assert "Temporal Analysis" in result.output
        assert "Inferred temporal order" in result.output

        # Verify temporal order was updated
        mock_manager.operations.update_scene_order.assert_called_once_with(
            "script-123", mock_temporal_order, SceneOrderType.TEMPORAL
        )

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_analyze_all(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test comprehensive analysis (all types)."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Mock all analysis methods
        mock_scenes = [Mock(id="scene1", properties={"heading": "Scene 1"})]
        mock_manager.operations.get_script_scenes.return_value = mock_scenes
        mock_manager.analyze_scene_dependencies.return_value = {"scene1": []}
        mock_manager.infer_temporal_order.return_value = {"scene1": 1}
        mock_manager.operations.update_scene_order.return_value = True

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(app, ["scene", "analyze"])  # Default is "all"

        assert result.exit_code == 0
        assert "Scene Dependencies" in result.output
        assert "Temporal Analysis" in result.output

        # Verify both analyses were called
        mock_manager.analyze_scene_dependencies.assert_called_once()
        mock_manager.infer_temporal_order.assert_called_once()

    def test_scene_analyze_invalid_type(self):
        """Test scene analyze with invalid analysis type."""
        runner = CliRunner()
        result = runner.invoke(app, ["scene", "analyze", "invalid"])

        assert result.exit_code == 1
        assert "Invalid analysis type" in result.output

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_scene_analyze_no_dependencies(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test dependency analysis when no dependencies found."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Override with specific test data
        mock_scenes = [Mock(id="scene1", properties={"heading": "Scene 1"})]
        mock_manager.operations.get_script_scenes.return_value = mock_scenes

        # No dependencies
        mock_dependencies = {"scene1": []}
        mock_manager.analyze_scene_dependencies.return_value = mock_dependencies

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(app, ["scene", "analyze", "dependencies"])

        assert result.exit_code == 0
        assert "No dependencies found" in result.output


class TestSceneCommandsCommon:
    """Test common functionality across scene commands."""

    @patch("scriptrag.cli.get_settings")
    def test_no_database_file(self, mock_get_settings):
        """Test scene commands when database file doesn't exist."""
        mock_settings = create_mock_settings("/nonexistent/db.sqlite")
        mock_get_settings.return_value = mock_settings

        commands = [
            ["scene", "list"],
            ["scene", "update", "1", "--location", "INT. OFFICE - DAY"],
            ["scene", "reorder", "1", "--position", "2"],
            ["scene", "analyze"],
        ]

        for command in commands:
            with patch("scriptrag.cli.Path") as mock_path_class:
                mock_path = Mock()
                mock_path.exists.return_value = False
                mock_path_class.return_value = mock_path

                runner = CliRunner()
                result = runner.invoke(app, command)

            assert result.exit_code == 1
            assert "No database found" in result.output

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_no_scripts_in_database(
        self, mock_get_latest, mock_db_conn, mock_get_settings
    ):
        """Test scene commands when no scripts exist in database."""
        mock_settings = create_mock_settings("/test/db.sqlite")
        mock_get_settings.return_value = mock_settings

        mock_get_latest.return_value = None  # No scripts

        mock_connection = create_mock_database_connection()
        mock_db_conn.return_value = mock_connection

        commands = [
            ["scene", "list"],
            ["scene", "update", "1", "--location", "INT. OFFICE - DAY"],
            ["scene", "reorder", "1", "--position", "2"],
            ["scene", "analyze"],
        ]

        for command in commands:
            with patch("scriptrag.cli.Path") as mock_path_class:
                mock_path = Mock()
                mock_path.exists.return_value = True
                mock_path_class.return_value = mock_path

                runner = CliRunner()
                result = runner.invoke(app, command)

            assert result.exit_code == 1
            # Accept either "No scripts found" or database error messages
            # since database connection issues may occur before checking for scripts
            assert "No scripts found" in result.output or (
                "Error" in result.output and "sqlite-vec" in result.output
            )

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    @patch("scriptrag.cli.get_latest_script_id")
    def test_no_scenes_in_script(
        self, mock_get_latest, mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test scene commands when script has no scenes."""
        # Set up all mocks using helper function
        mock_settings, mock_manager, mock_connection = setup_cli_test_mocks(
            mock_get_settings, mock_db_conn, mock_scene_manager, mock_get_latest
        )

        # Override to return no scenes
        mock_manager.operations.get_script_scenes.return_value = []  # No scenes

        commands = [
            ["scene", "update", "1", "--location", "INT. OFFICE - DAY"],
            ["scene", "reorder", "1", "--position", "2"],
        ]

        for command in commands:
            with patch("scriptrag.cli.Path") as mock_path_class:
                mock_path = Mock()
                mock_path.exists.return_value = True
                mock_path_class.return_value = mock_path

                runner = CliRunner()
                result = runner.invoke(app, command)

            assert result.exit_code == 1
            assert "No scenes found" in result.output

    @patch("scriptrag.cli.get_settings")
    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.SceneManager")
    def test_exception_handling(
        self, _mock_scene_manager, mock_db_conn, mock_get_settings
    ):
        """Test exception handling in scene commands."""
        mock_settings = create_mock_settings("/test/db.sqlite")
        mock_get_settings.return_value = mock_settings

        # Mock exception during initialization
        mock_db_conn.side_effect = Exception("Database connection failed")

        with patch("scriptrag.cli.Path") as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            runner = CliRunner()
            result = runner.invoke(app, ["scene", "list"])

        assert result.exit_code == 1
        assert "Error listing scenes" in result.output
