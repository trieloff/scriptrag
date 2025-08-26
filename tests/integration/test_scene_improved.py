"""Improved integration tests for scene CLI command using test infrastructure."""

from unittest.mock import patch

from scriptrag.cli.main import app
from tests.cli.base import CLITestBase
from tests.factories import (
    BibleReadResultFactory,
    ReadSceneResultFactory,
    SceneFactory,
    UpdateSceneResultFactory,
)
from tests.utils.async_helpers import async_raise, async_return


class TestSceneCLIImproved(CLITestBase):
    """Improved scene CLI tests using test infrastructure."""

    async def test_read_scene_success(self, cli_runner):
        """Test successful scene reading."""
        # Create test data using factories
        scene = SceneFactory.create_with_dialogue(
            number=5,
            character="WALTER",
            dialogue_text="I am the one who knocks!",
        )

        # Mock the API using our utilities
        with patch("scriptrag.cli.commands.scene.SceneManagementAPI") as mock_api:
            mock_api.return_value.read_scene = async_return(
                ReadSceneResultFactory.success(scene)
            )

            # Run the command
            result = cli_runner.invoke(
                app,
                ["scene", "read", "--project", "breaking_bad", "--scene", "5"],
            )

            # Assert success
            self.assert_success(result)
            assert "WALTER" in result.output
            assert "I am the one who knocks!" in result.output

    async def test_read_scene_not_found(self, cli_runner):
        """Test scene not found error."""
        with patch("scriptrag.cli.commands.scene.SceneManagementAPI") as mock_api:
            mock_api.return_value.read_scene = async_raise(
                Exception("Scene 999 not found")
            )

            result = cli_runner.invoke(
                app,
                ["scene", "read", "--project", "test", "--scene", "999"],
            )

            self.assert_failure(result, "Scene 999 not found")

    async def test_read_bible_files(self, cli_runner):
        """Test reading script bible files."""
        bible_content = {
            "world_bible.md": "# World Bible\n\nDesert locations...",
            "character_bible.md": "# Characters\n\nWalter White - Chemistry teacher",
        }

        with patch("scriptrag.cli.commands.scene.SceneManagementAPI") as mock_api:
            mock_api.return_value.read_bible = async_return(
                BibleReadResultFactory.success(bible_content)
            )

            result = cli_runner.invoke(
                app,
                ["scene", "read", "--project", "breaking_bad", "--bible"],
            )

            self.assert_success(result)
            assert "Bible Files Found: 2" in result.output

    async def test_update_scene_with_file(self, cli_runner):
        """Test updating a scene from a file."""
        # Create content file
        content_file = self.tmp_path / "new_content.txt"
        content_file.write_text("INT. UPDATED LOCATION - NIGHT\n\nNew scene content.")

        with patch("scriptrag.cli.commands.scene.SceneManagementAPI") as mock_api:
            mock_api.return_value.update_scene = async_return(
                UpdateSceneResultFactory.success("Scene 10 updated successfully")
            )

            result = cli_runner.invoke(
                app,
                [
                    "scene",
                    "update",
                    "--project",
                    "test",
                    "--scene",
                    "10",
                    "--content-file",
                    str(content_file),
                ],
            )

            self.assert_success(result)
            assert "Scene 10 updated successfully" in result.output

    async def test_scene_json_output(self, cli_runner):
        """Test JSON output format."""
        scene = SceneFactory.create_exterior(
            number=1,
            location="DESERT",
            time_of_day="DAWN",
        )

        with patch("scriptrag.cli.commands.scene.SceneManagementAPI") as mock_api:
            mock_api.return_value.read_scene = async_return(
                ReadSceneResultFactory.success(scene)
            )

            result = cli_runner.invoke(
                app,
                ["scene", "read", "--project", "test", "--scene", "1", "--json"],
            )

            # Verify JSON output
            data = self.assert_json_output(result)
            assert data["scene"]["number"] == 1
            assert data["scene"]["location"] == "DESERT"

    async def test_add_scene_workflow(self, cli_runner):
        """Test complete workflow of adding a new scene."""
        # Create a screenplay file
        script_file = self.create_test_script()

        # Create new scene content
        new_scene_file = self.tmp_path / "new_scene.txt"
        new_scene_file.write_text("""INT. NEW LOCATION - DAY

This is a new scene to be added.

JOHN
This is new dialogue.
""")

        with patch("scriptrag.cli.commands.scene.SceneManagementAPI") as mock_api:
            mock_api.return_value.add_scene = async_return(
                UpdateSceneResultFactory.success("Scene added after scene 5")
            )

            result = cli_runner.invoke(
                app,
                [
                    "scene",
                    "add",
                    "--project",
                    "test",
                    "--after",
                    "5",
                    "--content-file",
                    str(new_scene_file),
                ],
            )

            self.assert_success(result)
            assert "Scene added after scene 5" in result.output

    async def test_delete_scene_requires_force(self, cli_runner):
        """Test that delete requires --force flag."""
        result = cli_runner.invoke(
            app,
            ["scene", "delete", "--project", "test", "--scene", "5"],
        )

        self.assert_failure(result, "requires --force")

    async def test_scene_with_config_file(self, cli_runner, mock_settings):
        """Test using a configuration file."""
        # Create config file
        config_file = self.create_config_file(
            {
                "database": {"path": str(self.db_path)},
                "llm": {"provider": "openai", "model": "gpt-4"},
            }
        )

        scene = SceneFactory.create()

        with patch("scriptrag.cli.commands.scene.SceneManagementAPI") as mock_api:
            mock_api.return_value.read_scene = async_return(
                ReadSceneResultFactory.success(scene)
            )

            result = cli_runner.invoke(
                app,
                [
                    "scene",
                    "read",
                    "--project",
                    "test",
                    "--scene",
                    "1",
                    "--config",
                    str(config_file),
                ],
            )

            self.assert_success(result)
