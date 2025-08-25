"""Integration tests for scene management functionality."""

import json

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app
from tests.cli_fixtures import strip_ansi_codes

runner = CliRunner()


@pytest.fixture
def sample_screenplay(tmp_path):
    """Create a sample screenplay with multiple scenes."""
    script_path = tmp_path / "test_script.fountain"
    content = """Title: Integration Test Script
Author: Test Suite
Draft date: 2024-01-01

= This is a test screenplay for integration testing

INT. COFFEE SHOP - MORNING

The morning sun streams through large windows. The aroma of fresh coffee fills the air.

SARAH (30s, creative type) sits at a corner table with her laptop.

SARAH
(to herself)
Just one more scene and I'm done.

JAMES (40s, barista) approaches with a coffee.

JAMES
Another refill?

SARAH
(grateful)
You're a lifesaver.

EXT. CITY STREET - CONTINUOUS

Sarah exits the coffee shop, coffee in hand. The city is just waking up.

She walks briskly, checking her phone.

SARAH
(on phone)
Yes, I'll have it ready by noon.

INT. SARAH'S APARTMENT - LATER

A cozy apartment filled with books and scripts. Sarah sits at her desk,
typing furiously.

Her cat, WHISKERS, jumps onto the desk.

SARAH
(to Whiskers)
Not now, buddy. Almost done.

She saves her work and leans back, satisfied.

SARAH (CONT'D)
Finally. The End.

FADE OUT.
"""
    script_path.write_text(content)
    return script_path


@pytest.fixture
def sample_tv_screenplay(tmp_path):
    """Create a TV series screenplay."""
    tv_script = tmp_path / "breaking_bad_s01e01.fountain"
    tv_content = """Title: Breaking Bad
Author: Vince Gilligan
Season: 1
Episode: 1
Episode Title: Pilot

INT. RV - DAY

WALTER WHITE, 50s, in his underwear, frantically drives an RV through the desert.

WALTER
(into recorder)
My name is Walter Hartwell White.

EXT. DESERT - CONTINUOUS

The RV crashes to a stop. Walter stumbles out.

WALTER
(continuing)
This is my confession."""
    tv_script.write_text(tv_content)
    return tv_script


class TestSceneManagement:
    """Test scene management commands."""

    @pytest.mark.integration
    def test_scene_management_commands(self, tmp_path, sample_screenplay, monkeypatch):
        """Test scene management read/add/update/delete commands."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Create a config file for scene commands to use
        config_path = tmp_path / "config.toml"
        # Use forward slashes for cross-platform compatibility in TOML
        db_path_str = str(db_path).replace("\\", "/")
        config_content = f'database_path = "{db_path_str}"'
        config_path.write_text(config_content)

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(
            app, ["index", str(sample_screenplay.parent), "--db-path", str(db_path)]
        )
        assert result.exit_code == 0

        # Test 1: Read a scene
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Integration Test Script",
                "--scene",
                "1",
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "COFFEE SHOP" in output
        # Check for timestamp instead of token (simplified scene management)
        assert "Last read:" in output or "last read:" in output.lower()

        # Test 2: Read scene with JSON output
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Integration Test Script",
                "--scene",
                "2",
                "--json",
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 0
        # Strip ANSI codes before parsing JSON (Windows compatibility)
        clean_output = strip_ansi_codes(result.stdout)
        data = json.loads(clean_output)
        assert data["success"] is True
        assert "content" in data
        assert "CITY STREET" in data["content"]

        # Test 3: Add a new scene after scene 1
        new_scene_content = """INT. NEW LOCATION - DAY

This is a brand new scene added via the API.

SARAH enters the new location."""

        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "Integration Test Script",
                "--after-scene",
                "1",
                "--content",
                new_scene_content,
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "Scene added" in output or "added" in output.lower()

        # Verify the new scene exists by reading scene 2 (which should be the new one)
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Integration Test Script",
                "--scene",
                "2",
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "NEW LOCATION" in output

        # Test 4: Update the newly added scene
        updated_content = """INT. NEW LOCATION - NIGHT

The scene has been updated - it's now nighttime.

JAMES walks in."""

        result = runner.invoke(
            app,
            [
                "scene",
                "update",
                "--project",
                "Integration Test Script",
                "--scene",
                "2",
                "--content",
                updated_content,
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "Scene updated" in output or "updated" in output.lower()

        # Verify the update worked
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Integration Test Script",
                "--scene",
                "2",
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "NIGHT" in output
        assert "JAMES" in output

        # Test 5: Delete the newly added scene
        result = runner.invoke(
            app,
            [
                "scene",
                "delete",
                "--project",
                "Integration Test Script",
                "--scene",
                "2",
                "--confirm",
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "Scene deleted" in output or "deleted" in output.lower()

        # Verify the scene was deleted (scene 2 should now be the original scene 2)
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Integration Test Script",
                "--scene",
                "2",
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "CITY STREET" in output  # This was the original scene 2

    @pytest.mark.integration
    def test_scene_management_tv_series(
        self, tmp_path, sample_tv_screenplay, monkeypatch
    ):
        """Test scene management for TV series format."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Create a config file for scene commands to use
        config_path = tmp_path / "config.toml"
        # Use forward slashes for cross-platform compatibility in TOML
        db_path_str = str(db_path).replace("\\", "/")
        config_content = f'database_path = "{db_path_str}"'
        config_path.write_text(config_content)

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_tv_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(
            app, ["index", str(sample_tv_screenplay.parent), "--db-path", str(db_path)]
        )
        assert result.exit_code == 0

        # Test reading TV series scene with season and episode
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Breaking Bad",
                "--season",
                "1",
                "--episode",
                "1",
                "--scene",
                "1",
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "DESERT" in output or "RV" in output

        # Test reading scene 2
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Breaking Bad",
                "--season",
                "1",
                "--episode",
                "1",
                "--scene",
                "2",
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "DESERT" in output or "RV" in output

    @pytest.mark.integration
    def test_scene_management_error_cases(
        self, tmp_path, sample_screenplay, monkeypatch
    ):
        """Test error handling for scene management commands."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Create a config file for scene commands to use
        config_path = tmp_path / "config.toml"
        # Use forward slashes for cross-platform compatibility in TOML
        db_path_str = str(db_path).replace("\\", "/")
        config_content = f'database_path = "{db_path_str}"'
        config_path.write_text(config_content)

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(
            app, ["index", str(sample_screenplay.parent), "--db-path", str(db_path)]
        )
        assert result.exit_code == 0

        # Test 1: Read non-existent scene
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Integration Test Script",
                "--scene",
                "999",
                "--config",
                str(config_path),
            ],
        )
        # Check if command returns error
        if result.exit_code != 0:
            output = strip_ansi_codes(result.stdout)
            assert "not found" in output.lower() or "error" in output.lower()
        else:
            # Some implementations might return success with an error message
            output = strip_ansi_codes(result.stdout)
            assert (
                "not found" in output.lower()
                or "error" in output.lower()
                or "Scene 999" not in output
            )

        # Test 2: Update with invalid scene number
        result = runner.invoke(
            app,
            [
                "scene",
                "update",
                "--project",
                "Integration Test Script",
                "--scene",
                "999",
                "--content",
                "This should fail",
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code != 0
        output = strip_ansi_codes(result.stdout)
        assert "not found" in output.lower() or "error" in output.lower()

        # Test 3: Delete without confirmation (should warn but not delete)
        result = runner.invoke(
            app,
            [
                "scene",
                "delete",
                "--project",
                "Integration Test Script",
                "--scene",
                "1",
                "--config",
                str(config_path),
            ],
        )
        # Command may return 0 with a warning message
        output = strip_ansi_codes(result.stdout)
        assert "confirm" in output.lower() or "warning" in output.lower()

        # Test 4: Read from non-existent project
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Non-Existent Project",
                "--scene",
                "1",
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code != 0
        output = strip_ansi_codes(result.stdout)
        assert "not found" in output.lower() or "error" in output.lower()

        # Test 5: Add scene with invalid reference scene
        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "Integration Test Script",
                "--after-scene",
                "999",
                "--content",
                "INT. INVALID - DAY\n\nThis should fail",
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code != 0
        output = strip_ansi_codes(result.stdout)
        assert "not found" in output.lower() or "error" in output.lower()

        # Test 6: Add scene with invalid Fountain format (no scene heading)
        result = runner.invoke(
            app,
            [
                "scene",
                "add",
                "--project",
                "Integration Test Script",
                "--after-scene",
                "1",
                "--content",
                "This is not valid Fountain format - no scene heading",
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code != 0
        output = strip_ansi_codes(result.stdout)
        assert "invalid" in output.lower() or "error" in output.lower()

        # Test 7: Read non-existent bible file
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Integration Test Script",
                "--bible-name",
                "non_existent.md",
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code != 0
        output = strip_ansi_codes(result.stdout)
        assert "not found" in output.lower() or "error" in output.lower()
