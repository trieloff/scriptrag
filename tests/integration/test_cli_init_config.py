"""Test init command with config generation functionality."""

from pathlib import Path
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

    def test_generate_config_with_permission_error(self, tmp_path, monkeypatch):
        """Test fallback when config directory cannot be created."""
        from scriptrag.config import template

        # Mock Path.mkdir to raise PermissionError
        def mock_mkdir(*args, **kwargs):
            raise PermissionError("Permission denied")

        with patch("pathlib.Path.mkdir", side_effect=mock_mkdir):
            # Should fall back to current directory
            default_path = template.get_default_config_path()
            assert default_path == Path.cwd() / "scriptrag.yaml"

    def test_generate_config_with_os_error(self, tmp_path, monkeypatch):
        """Test fallback when config directory has OSError."""
        from scriptrag.config import template

        # Mock Path.mkdir to raise OSError
        def mock_mkdir(*args, **kwargs):
            raise OSError("OS error")

        with patch("pathlib.Path.mkdir", side_effect=mock_mkdir):
            # Should fall back to current directory
            default_path = template.get_default_config_path()
            assert default_path == Path.cwd() / "scriptrag.yaml"

    def test_generate_config_exception_handling(self, tmp_path):
        """Test exception handling during config generation."""
        with patch("scriptrag.cli.commands.init.write_config_template") as mock_write:
            mock_write.side_effect = Exception("Test error")

            result = self.runner.invoke(
                app, ["init", "--generate-config", "-o", str(tmp_path / "test.yaml")]
            )

            assert result.exit_code == 1
            assert "Failed to generate config: Test error" in result.output

    def test_init_with_missing_config_file(self, tmp_path):
        """Test init command when specified config file doesn't exist."""
        missing_config = tmp_path / "missing_config.yaml"
        db_path = tmp_path / "test.db"

        result = self.runner.invoke(
            app,
            ["init", "--config", str(missing_config), "--db-path", str(db_path)],
        )

        assert result.exit_code == 1
        assert "Config file not found" in result.output

    def test_generate_config_with_confirm_yes(self):
        """Test that existing config is overwritten when user confirms."""
        # Create existing file
        self.config_file.write_text("existing content")

        # Mock user input to say yes to overwrite
        result = self.runner.invoke(
            app,
            ["init", "--generate-config", "-o", str(self.config_file)],
            input="y\n",
        )

        assert result.exit_code == 0
        assert "Configuration template generated" in result.output

        # Check file was overwritten
        content = self.config_file.read_text()
        assert "existing content" not in content
        assert "# ScriptRAG Configuration File" in content

    def test_config_template_value_formatting(self):
        """Test that config values are properly formatted in YAML."""
        from scriptrag.config.template import generate_config_template

        # Generate the template
        template = generate_config_template()

        # Check various value types are formatted correctly
        assert 'database_path: "scriptrag.db"' in template  # String with quotes
        assert "database_timeout: 30.0" in template  # Float
        assert "database_wal_mode: true" in template  # Boolean lowercase
        assert "database_cache_size: -2000" in template  # Negative integer
        assert "# llm_api_key: ${GITHUB_TOKEN}" in template  # Env var without quotes

    def test_init_database_file_exists_error(self, tmp_path, monkeypatch):
        """Test handling of FileExistsError during database initialization."""
        from scriptrag.api import DatabaseInitializer

        db_path = tmp_path / "test.db"

        # Mock the initializer to raise FileExistsError
        with patch.object(
            DatabaseInitializer,
            "initialize_database",
            side_effect=FileExistsError("Database already exists"),
        ):
            result = self.runner.invoke(
                app,
                ["init", "--db-path", str(db_path)],
            )

            assert result.exit_code == 1
            assert "Database already exists" in result.output

    def test_init_database_general_exception(self, tmp_path):
        """Test handling of general exceptions during database initialization."""
        from scriptrag.api import DatabaseInitializer

        db_path = tmp_path / "test.db"

        # Mock the initializer to raise an exception
        with patch.object(
            DatabaseInitializer,
            "initialize_database",
            side_effect=Exception("Unexpected error"),
        ):
            result = self.runner.invoke(
                app,
                ["init", "--db-path", str(db_path)],
            )

            assert result.exit_code == 1
            assert "Failed to initialize database" in result.output
            assert "Unexpected error" in result.output

    def test_init_force_cancel_database_overwrite(self, tmp_path):
        """Test cancelling database overwrite with force flag."""
        # Create existing database
        db_path = tmp_path / "test.db"
        db_path.touch()

        # Mock user input to say no to overwrite
        result = self.runner.invoke(
            app,
            ["init", "--db-path", str(db_path), "--force"],
            input="n\n",
        )

        assert result.exit_code == 0
        assert "Initialization cancelled" in result.output

    def test_config_template_dict_building(self):
        """Test the dictionary building logic in generate_config_template."""
        from scriptrag.config.template import generate_config_template

        # This exercises the value handling branches
        template = generate_config_template()

        # Verify all branches of value handling are covered
        lines = template.split("\n")

        # Check we have comments (lines starting with #)
        comment_lines = [line for line in lines if line.startswith("#")]
        assert len(comment_lines) > 50  # We have many comment lines

        # Check we have settings with various value types
        setting_lines = [
            line for line in lines if ":" in line and not line.startswith("#")
        ]
        assert len(setting_lines) > 20  # We have many settings

        # Check blank lines for spacing
        blank_lines = [line for line in lines if line == ""]
        assert len(blank_lines) > 5  # We have blank lines for readability
