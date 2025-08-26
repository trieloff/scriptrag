"""Base class for CLI integration tests."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner


class CLITestBase:
    """Base class for CLI integration tests with common setup."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path: Path, monkeypatch):
        """Set up test environment."""
        # Set up temporary paths
        self.tmp_path = tmp_path
        self.db_path = tmp_path / "test.db"
        self.config_path = tmp_path / "config.yaml"
        self.scripts_path = tmp_path / "scripts"
        self.scripts_path.mkdir()

        # Set environment variables
        monkeypatch.setenv("SCRIPTRAG_DB_PATH", str(self.db_path))
        monkeypatch.setenv("SCRIPTRAG_CONFIG_PATH", str(self.config_path))
        monkeypatch.setenv("SCRIPTRAG_LOG_LEVEL", "ERROR")  # Quiet logs in tests

        # Store monkeypatch for use in tests
        self.monkeypatch = monkeypatch

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        settings = MagicMock()
        settings.database.path = self.db_path
        settings.llm.provider = "mock"
        settings.llm.api_key = "test-key"  # pragma: allowlist secret

        with patch("scriptrag.config.get_settings", return_value=settings):
            yield settings

    @pytest.fixture
    def cli_runner(self, cli_helper: CliRunner) -> CliRunner:
        """Get CLI runner with proper setup."""
        return cli_helper

    def create_test_script(self, name: str = "test.fountain") -> Path:
        """Create a test screenplay file.

        Args:
            name: Name of the file to create

        Returns:
            Path to the created file
        """
        script_path = self.scripts_path / name
        script_path.write_text("""Title: Test Script
Author: Test Author

FADE IN:

INT. COFFEE SHOP - DAY

JOHN enters and looks around.

JOHN
Has anyone seen my coffee?

FADE OUT.
""")
        return script_path

    def create_config_file(self, content: dict[str, Any] | None = None) -> Path:
        """Create a test configuration file.

        Args:
            content: Configuration content (will be converted to YAML)

        Returns:
            Path to the created config file
        """
        if content is None:
            content = {
                "database": {
                    "path": str(self.db_path),
                },
                "llm": {
                    "provider": "openai",
                    "api_key": "test-key",  # pragma: allowlist secret
                },
            }

        import yaml

        self.config_path.write_text(yaml.dump(content))
        return self.config_path

    def assert_success(self, result):
        """Assert that a CLI command succeeded.

        Args:
            result: The CliRunner result
        """
        assert result.exit_code == 0, f"Command failed with: {result.output}"

    def assert_failure(self, result, expected_error: str | None = None):
        """Assert that a CLI command failed.

        Args:
            result: The CliRunner result
            expected_error: Optional error message to check for
        """
        assert result.exit_code != 0, f"Command succeeded unexpectedly: {result.output}"
        if expected_error:
            assert expected_error in result.output, (
                f"Expected error '{expected_error}' not found in: {result.output}"
            )

    def assert_json_output(self, result):
        """Assert that output is valid JSON.

        Args:
            result: The CliRunner result

        Returns:
            Parsed JSON data
        """
        import json

        self.assert_success(result)
        try:
            return json.loads(result.output)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON output: {e}\nOutput: {result.output}")
