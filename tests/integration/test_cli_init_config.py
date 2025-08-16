"""Test init command with config generation functionality."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app


class TestInitConfigGeneration:
    """Test init command config generation functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test environment."""
        self.runner = CliRunner()
        self.tmp_path = tmp_path
        self.config_file = tmp_path / "test_config.yaml"

    def test_generate_config_default_location(self, tmp_path):
        """Test generating config file at default location."""
        # Patch at the import location in init.py
        with patch("scriptrag.cli.commands.init.get_default_config_path") as mock_path:
            mock_path.return_value = tmp_path / "config.yaml"
            result = self.runner.invoke(app, ["init", "--generate-config"])

            assert result.exit_code == 0
            assert "Configuration template generated" in result.output
            assert (tmp_path / "config.yaml").exists()

            # Check content
            content = (tmp_path / "config.yaml").read_text()
            assert "# ScriptRAG Configuration File" in content
            assert "database_path:" in content
            assert "llm_provider:" in content

    def test_generate_config_custom_location(self):
        """Test generating config file at custom location."""
        result = self.runner.invoke(
            app, ["init", "--generate-config", "-o", str(self.config_file)]
        )

        assert result.exit_code == 0
        assert "Configuration template generated" in result.output
        assert self.config_file.exists()

        # Check content structure
        content = self.config_file.read_text()
        assert "# ScriptRAG Configuration File" in content
        assert "# Database Configuration" in content
        assert "# LLM (Language Model) Configuration" in content
        assert "# Option 1: Local LLM" in content
        assert "# Option 2: GitHub Models" in content
        assert "# Option 3: OpenAI API" in content

    def test_generate_config_with_force(self):
        """Test overwriting existing config with force flag."""
        # Create existing file
        self.config_file.write_text("existing content")

        result = self.runner.invoke(
            app, ["init", "--generate-config", "-o", str(self.config_file), "--force"]
        )

        assert result.exit_code == 0
        assert "Configuration template generated" in result.output
        assert self.config_file.exists()

        # Check it was overwritten
        content = self.config_file.read_text()
        assert "existing content" not in content
        assert "# ScriptRAG Configuration File" in content

    def test_generate_config_exists_no_force(self):
        """Test that existing config is not overwritten without force."""
        # Create existing file
        self.config_file.write_text("existing content")

        # Mock user input to say no to overwrite
        result = self.runner.invoke(
            app,
            ["init", "--generate-config", "-o", str(self.config_file)],
            input="n\n",
        )

        assert result.exit_code == 0
        assert "Config generation cancelled" in result.output

        # Check file wasn't changed
        content = self.config_file.read_text()
        assert content == "existing content"

    def test_generate_config_and_init_database(self, tmp_path):
        """Test generating config and initializing database in same command."""
        db_path = tmp_path / "test.db"
        config_path = tmp_path / "config.yaml"

        result = self.runner.invoke(
            app,
            [
                "init",
                "--generate-config",
                "-o",
                str(config_path),
                "--db-path",
                str(db_path),
            ],
        )

        assert result.exit_code == 0
        assert "Configuration template generated" in result.output
        assert "Database initialized successfully" in result.output
        assert config_path.exists()
        assert db_path.exists()

    def test_config_yaml_format(self):
        """Test that generated config is valid YAML."""
        import yaml

        result = self.runner.invoke(
            app, ["init", "--generate-config", "-o", str(self.config_file)]
        )

        assert result.exit_code == 0
        assert self.config_file.exists()

        # Parse YAML to ensure it's valid
        content = self.config_file.read_text()

        # Remove comments for parsing (YAML parser handles inline comments)
        lines = []
        for line in content.split("\n"):
            # Skip pure comment lines
            if not line.strip().startswith("#"):
                lines.append(line)

        yaml_content = "\n".join(lines)

        # This should not raise an exception
        parsed = yaml.safe_load(yaml_content)

        # Check some expected keys
        assert "database_path" in parsed
        assert "log_level" in parsed
        assert "llm_temperature" in parsed

    def test_config_content_completeness(self):
        """Test that generated config contains all expected settings."""
        result = self.runner.invoke(
            app, ["init", "--generate-config", "-o", str(self.config_file)]
        )

        assert result.exit_code == 0
        content = self.config_file.read_text()

        # Check all major sections are present
        expected_sections = [
            "# Database Configuration",
            "# Application Settings",
            "# Logging Configuration",
            "# Search Settings",
            "# LLM (Language Model) Configuration",
            "# Bible/Document Embeddings Settings",
        ]

        for section in expected_sections:
            assert section in content, f"Missing section: {section}"

        # Check key settings are present
        expected_settings = [
            "database_path:",
            "database_timeout:",
            "log_level:",
            "search_vector_threshold:",
            "llm_temperature:",
            "bible_embeddings_path:",
        ]

        for setting in expected_settings:
            assert setting in content, f"Missing setting: {setting}"
