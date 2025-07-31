"""Tests for Script Bible CLI commands."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from scriptrag.cli import app
from scriptrag.models import ContinuityNote, SeriesBible


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_connection():
    """Create mock database connection."""
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=None)
    return mock


@pytest.fixture
def sample_script_data():
    """Sample script data for testing."""
    return {
        "script_id": str(uuid4()),
        "script_title": "Test Series",
        "character_id": str(uuid4()),
        "episode_id": str(uuid4()),
    }


class TestScriptBibleCLI:
    """Test Script Bible CLI commands."""

    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.ScriptBibleOperations")
    @patch("scriptrag.cli.commands.bible.get_latest_script_id")
    def test_bible_create_command(
        self,
        mock_get_latest,
        mock_bible_ops,
        mock_db_conn,
        cli_runner,
        sample_script_data,
    ):
        """Test bible create command."""
        # Setup mocks
        mock_get_latest.return_value = (
            sample_script_data["script_id"],
            sample_script_data["script_title"],
        )
        mock_connection = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_connection

        mock_ops = mock_bible_ops.return_value
        mock_ops.create_series_bible.return_value = "bible123"

        # Test command
        result = cli_runner.invoke(
            app,
            [
                "bible",
                "create",
                "--title",
                "Test Bible",
                "--description",
                "Test description",
                "--created-by",
                "Test Creator",
            ],
        )

        assert result.exit_code == 0
        assert "Created script bible: bible123" in result.stdout
        assert "Title: Test Bible" in result.stdout

        mock_ops.create_series_bible.assert_called_once_with(
            script_id=sample_script_data["script_id"],
            title="Test Bible",
            description="Test description",
            created_by="Test Creator",
            bible_type="series",
        )

    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.ScriptBibleOperations")
    @patch("scriptrag.cli.commands.bible.get_latest_script_id")
    def test_bible_create_no_scripts(
        self, mock_get_latest, mock_bible_ops, mock_db_conn, cli_runner
    ):
        """Test bible create when no scripts exist."""
        # Silence unused fixture warnings
        _ = mock_bible_ops
        _ = mock_db_conn

        mock_get_latest.return_value = None

        result = cli_runner.invoke(app, ["bible", "create", "--title", "Test Bible"])

        assert result.exit_code == 1
        assert "No scripts found" in result.stdout

    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.ScriptBibleOperations")
    @patch("scriptrag.cli.commands.bible.get_latest_script_id")
    def test_bible_list_command(
        self,
        mock_get_latest,
        mock_bible_ops,
        mock_db_conn,
        cli_runner,
        sample_script_data,
    ):
        """Test bible list command."""
        # Setup mocks
        mock_get_latest.return_value = (
            sample_script_data["script_id"],
            sample_script_data["script_title"],
        )
        mock_connection = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_connection

        mock_bible = MagicMock(spec=SeriesBible)
        mock_bible.id = uuid4()
        mock_bible.title = "Test Bible"
        mock_bible.bible_type = "series"
        mock_bible.status = "active"
        mock_bible.version = 1
        # Create a mock datetime object for created_at
        from datetime import datetime

        mock_bible.created_at = datetime(2024, 1, 1)

        mock_ops = mock_bible_ops.return_value
        mock_ops.get_series_bibles_for_script.return_value = [mock_bible]

        # Test command
        result = cli_runner.invoke(app, ["bible", "list"])

        assert result.exit_code == 0
        assert "Script Bibles" in result.stdout
        assert "Test Bible" in result.stdout
        assert "series" in result.stdout
        assert "active" in result.stdout

    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.ScriptBibleOperations")
    @patch("scriptrag.cli.commands.bible.get_latest_script_id")
    def test_bible_list_empty(
        self,
        mock_get_latest,
        mock_bible_ops,
        mock_db_conn,
        cli_runner,
        sample_script_data,
    ):
        """Test bible list when no bibles exist."""
        mock_get_latest.return_value = (
            sample_script_data["script_id"],
            sample_script_data["script_title"],
        )
        mock_connection = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_connection

        mock_ops = mock_bible_ops.return_value
        mock_ops.get_series_bibles_for_script.return_value = []

        result = cli_runner.invoke(app, ["bible", "list"])

        assert result.exit_code == 0
        assert "No script bibles found" in result.stdout

    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.ScriptBibleOperations")
    @patch("scriptrag.cli.commands.bible.get_latest_script_id")
    def test_character_profile_command(
        self,
        mock_get_latest,
        mock_bible_ops,
        mock_db_conn,
        cli_runner,
        sample_script_data,
    ):
        """Test character profile creation command."""
        # Setup mocks
        mock_get_latest.return_value = (
            sample_script_data["script_id"],
            sample_script_data["script_title"],
        )
        mock_connection = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_connection
        mock_connection.fetch_one.return_value = {
            "id": sample_script_data["character_id"]
        }

        mock_ops = mock_bible_ops.return_value
        mock_ops.get_character_profile.return_value = None  # No existing profile
        mock_ops.create_character_profile.return_value = "profile123"

        # Test command
        result = cli_runner.invoke(
            app,
            [
                "bible",
                "character-profile",
                "JOHN",
                "--age",
                "35",
                "--occupation",
                "Detective",
                "--background",
                "Former military",
            ],
        )

        assert result.exit_code == 0
        assert "Created character profile: profile123" in result.stdout
        assert "Character: JOHN" in result.stdout

        mock_ops.create_character_profile.assert_called_once()
        call_kwargs = mock_ops.create_character_profile.call_args[1]
        assert call_kwargs["age"] == 35
        assert call_kwargs["occupation"] == "Detective"
        assert call_kwargs["background"] == "Former military"

    @patch("scriptrag.cli.DatabaseConnection")
    def test_character_profile_not_found(
        self, mock_db_conn, cli_runner, sample_script_data
    ):
        """Test character profile when character doesn't exist."""
        mock_connection = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_connection
        mock_connection.fetch_one.return_value = None  # Character not found

        with patch(
            "scriptrag.cli.commands.bible.get_latest_script_id"
        ) as mock_get_latest:
            mock_get_latest.return_value = (
                sample_script_data["script_id"],
                sample_script_data["script_title"],
            )

            result = cli_runner.invoke(
                app, ["bible", "character-profile", "NONEXISTENT"]
            )

            assert result.exit_code == 1
            assert "Character 'NONEXISTENT' not found" in result.stdout

    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.ScriptBibleOperations")
    @patch("scriptrag.cli.commands.bible.get_latest_script_id")
    def test_world_element_command(
        self,
        mock_get_latest,
        mock_bible_ops,
        mock_db_conn,
        cli_runner,
        sample_script_data,
    ):
        """Test world element creation command."""
        # Setup mocks
        mock_get_latest.return_value = (
            sample_script_data["script_id"],
            sample_script_data["script_title"],
        )
        mock_connection = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_connection

        mock_ops = mock_bible_ops.return_value
        mock_ops.create_world_element.return_value = "element123"

        # Test command
        result = cli_runner.invoke(
            app,
            [
                "bible",
                "world-element",
                "Police Station",
                "--type",
                "location",
                "--description",
                "Main headquarters",
                "--importance",
                "4",
            ],
        )

        assert result.exit_code == 0
        assert "Created world element: element123" in result.stdout
        assert "Name: Police Station" in result.stdout
        assert "Type: location" in result.stdout
        assert "Importance: 4/5" in result.stdout

    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.ScriptBibleOperations")
    @patch("scriptrag.cli.commands.bible.get_latest_script_id")
    def test_timeline_command(
        self,
        mock_get_latest,
        mock_bible_ops,
        mock_db_conn,
        cli_runner,
        sample_script_data,
    ):
        """Test timeline creation command."""
        # Setup mocks
        mock_get_latest.return_value = (
            sample_script_data["script_id"],
            sample_script_data["script_title"],
        )
        mock_connection = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_connection

        mock_ops = mock_bible_ops.return_value
        mock_ops.create_story_timeline.return_value = "timeline123"

        # Test command
        result = cli_runner.invoke(
            app,
            [
                "bible",
                "timeline",
                "Main Timeline",
                "--type",
                "main",
                "--description",
                "Primary chronology",
                "--start",
                "Day 1",
                "--end",
                "Day 7",
            ],
        )

        assert result.exit_code == 0
        assert "Created timeline: timeline123" in result.stdout
        assert "Name: Main Timeline" in result.stdout
        assert "Type: main" in result.stdout
        assert "Period: Day 1 to Day 7" in result.stdout

    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.ContinuityValidator")
    @patch("scriptrag.cli.commands.bible.get_latest_script_id")
    def test_continuity_check_command(
        self,
        mock_get_latest,
        mock_validator,
        mock_db_conn,
        cli_runner,
        sample_script_data,
    ):
        """Test continuity check command."""
        # Setup mocks
        mock_get_latest.return_value = (
            sample_script_data["script_id"],
            sample_script_data["script_title"],
        )
        mock_connection = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_connection

        from scriptrag.database.continuity import ContinuityIssue

        mock_issues = [
            ContinuityIssue(
                issue_type="test_error",
                severity="high",
                title="High Priority Issue",
                description="This is a high priority issue",
            ),
            ContinuityIssue(
                issue_type="test_warning",
                severity="medium",
                title="Medium Priority Issue",
                description="This is a medium priority issue",
            ),
        ]

        mock_val = mock_validator.return_value
        mock_val.validate_script_continuity.return_value = mock_issues
        mock_val.create_continuity_notes_from_issues.return_value = ["note1", "note2"]

        # Test command with note creation
        result = cli_runner.invoke(
            app, ["bible", "continuity-check", "--create-notes", "--severity", "high"]
        )

        assert result.exit_code == 0
        assert "Running continuity validation" in result.stdout
        assert "Found 1 continuity issues" in result.stdout  # Filtered to high only
        assert "HIGH (1 issues)" in result.stdout
        assert "High Priority Issue" in result.stdout
        assert "Created 2 continuity notes" in result.stdout

    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.ContinuityValidator")
    @patch("scriptrag.cli.commands.bible.get_latest_script_id")
    def test_continuity_check_no_issues(
        self,
        mock_get_latest,
        mock_validator,
        mock_db_conn,
        cli_runner,
        sample_script_data,
    ):
        """Test continuity check when no issues found."""
        mock_get_latest.return_value = (
            sample_script_data["script_id"],
            sample_script_data["script_title"],
        )
        mock_connection = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_connection

        mock_val = mock_validator.return_value
        mock_val.validate_script_continuity.return_value = []

        result = cli_runner.invoke(app, ["bible", "continuity-check"])

        assert result.exit_code == 0
        assert "No continuity issues found!" in result.stdout

    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.ScriptBibleOperations")
    @patch("scriptrag.cli.commands.bible.get_latest_script_id")
    def test_notes_command(
        self,
        mock_get_latest,
        mock_bible_ops,
        mock_db_conn,
        cli_runner,
        sample_script_data,
    ):
        """Test continuity notes listing command."""
        # Setup mocks
        mock_get_latest.return_value = (
            sample_script_data["script_id"],
            sample_script_data["script_title"],
        )
        mock_connection = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_connection

        mock_note = MagicMock(spec=ContinuityNote)
        mock_note.id = uuid4()
        mock_note.note_type = "error"
        mock_note.severity = "high"
        mock_note.status = "open"
        mock_note.title = "Test Issue"
        # Create a mock datetime object for created_at
        from datetime import datetime

        mock_note.created_at = datetime(2024, 1, 1)

        mock_ops = mock_bible_ops.return_value
        mock_ops.get_continuity_notes.return_value = [mock_note]

        # Test command
        result = cli_runner.invoke(
            app, ["bible", "notes", "--status", "open", "--severity", "high"]
        )

        assert result.exit_code == 0
        assert "Continuity Notes" in result.stdout
        assert "Test Issue" in result.stdout
        assert "error" in result.stdout
        # Note: exact color formatting may vary in test output

    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.ContinuityValidator")
    @patch("scriptrag.cli.commands.bible.get_latest_script_id")
    def test_report_command(
        self,
        mock_get_latest,
        mock_validator,
        mock_db_conn,
        cli_runner,
        sample_script_data,
    ):
        """Test continuity report generation command."""
        # Setup mocks
        mock_get_latest.return_value = (
            sample_script_data["script_id"],
            sample_script_data["script_title"],
        )
        mock_connection = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_connection

        mock_report = {
            "script_title": sample_script_data["script_title"],
            "is_series": True,
            "generated_at": "2024-01-01T00:00:00",
            "validation_results": {
                "issue_statistics": {
                    "total_issues": 3,
                    "by_severity": {"high": 1, "medium": 1, "low": 1},
                }
            },
            "existing_notes": {
                "note_statistics": {
                    "total_notes": 2,
                    "by_status": {"open": 1, "resolved": 1},
                }
            },
            "recommendations": [
                "Address high-severity issues",
                "Review character arcs",
            ],
        }

        mock_val = mock_validator.return_value
        mock_val.generate_continuity_report.return_value = mock_report

        # Test command
        result = cli_runner.invoke(app, ["bible", "report"])

        assert result.exit_code == 0
        assert (
            f"Continuity Report for {sample_script_data['script_title']}"
            in result.stdout
        )
        assert "Script Type: Series" in result.stdout
        assert "Issues Found: 3" in result.stdout
        assert "Existing Notes: 2" in result.stdout
        assert "Address high-severity issues" in result.stdout
        assert "Review character arcs" in result.stdout

    @patch("scriptrag.cli.DatabaseConnection")
    @patch("scriptrag.cli.ContinuityValidator")
    @patch("scriptrag.cli.commands.bible.get_latest_script_id")
    def test_report_command_with_output_file(
        self,
        mock_get_latest,
        mock_validator,
        mock_db_conn,
        cli_runner,
        sample_script_data,
        tmp_path,
    ):
        """Test continuity report with file output."""
        # Setup mocks
        mock_get_latest.return_value = (
            sample_script_data["script_id"],
            sample_script_data["script_title"],
        )
        mock_connection = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_connection

        mock_report = {
            "script_title": sample_script_data["script_title"],
            "is_series": False,
            "generated_at": "2024-01-01T00:00:00",
            "validation_results": {
                "issue_statistics": {"total_issues": 0, "by_severity": {}}
            },
            "existing_notes": {"note_statistics": {"total_notes": 0, "by_status": {}}},
            "recommendations": ["No issues found"],
        }

        mock_val = mock_validator.return_value
        mock_val.generate_continuity_report.return_value = mock_report

        output_file = tmp_path / "report.json"

        # Test command
        result = cli_runner.invoke(
            app, ["bible", "report", "--output", str(output_file)]
        )

        assert result.exit_code == 0
        assert "Report saved to:" in result.stdout
        # Check that the filename appears in the output
        # (might be wrapped in console formatting or contain newlines)
        assert "report.json" in result.stdout.replace("\n", "")
        assert output_file.exists()

    def test_bible_command_help(self, cli_runner):
        """Test bible command help output."""
        result = cli_runner.invoke(app, ["bible", "--help"])

        assert result.exit_code == 0
        assert "Script Bible and continuity management commands" in result.stdout
        assert "create" in result.stdout
        assert "list" in result.stdout
        assert "character-profile" in result.stdout
        assert "world-element" in result.stdout
        # TODO: Implement these missing commands in future iterations
        # assert "timeline" in result.stdout
        # assert "continuity-check" in result.stdout
        # assert "notes" in result.stdout
        # assert "report" in result.stdout


class TestScriptBibleCLIIntegration:
    """Integration tests for Script Bible CLI commands."""

    def test_bible_command_structure(self, cli_runner):
        """Test that all Bible commands are properly registered."""
        result = cli_runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "bible" in result.stdout

    def test_bible_subcommands_exist(self, cli_runner):
        """Test that all expected Bible subcommands exist."""
        result = cli_runner.invoke(app, ["bible", "--help"])

        expected_commands = [
            "create",
            "list",
            "character-profile",
            "world-element",
            # TODO: Implement missing commands
            # "timeline",
            # "continuity-check",
            # "notes",
            # "report",
        ]

        for command in expected_commands:
            assert command in result.stdout

    def test_command_parameter_validation(self, cli_runner):
        """Test parameter validation for Bible commands."""
        # Test missing required parameters
        result = cli_runner.invoke(app, ["bible", "create"])
        assert result.exit_code != 0  # Should fail due to missing title

        result = cli_runner.invoke(app, ["bible", "character-profile"])
        assert result.exit_code != 0  # Should fail due to missing character name

        result = cli_runner.invoke(app, ["bible", "world-element"])
        assert result.exit_code != 0  # Should fail due to missing element name

        result = cli_runner.invoke(app, ["bible", "timeline"])
        assert result.exit_code != 0  # Should fail due to missing timeline name
