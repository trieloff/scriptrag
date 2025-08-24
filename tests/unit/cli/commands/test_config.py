"""Unit tests for configuration management CLI commands."""

import json
from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from scriptrag.cli.commands.config import config_app
from scriptrag.cli.commands.config.templates import (
    get_template_config,
)

runner = CliRunner()


class TestConfigInit:
    """Test config init command."""

    def test_init_default_config(self, tmp_path):
        """Test generating default configuration."""
        output_path = tmp_path / "config.yaml"

        result = runner.invoke(
            config_app,
            ["init", "--output", str(output_path)],
        )

        assert result.exit_code == 0
        assert output_path.exists()
        assert "Configuration file generated" in result.output

        # Verify it's valid YAML with security warning
        content = output_path.read_text()
        assert "SECURITY WARNING" in content
        config = yaml.safe_load(content)
        assert "database_path" in config

    def test_init_dev_config(self, tmp_path):
        """Test generating development configuration."""
        output_path = tmp_path / "config-dev.yaml"

        result = runner.invoke(
            config_app,
            ["init", "--output", str(output_path), "--env", "dev"],
        )

        assert result.exit_code == 0
        assert output_path.exists()

        config = yaml.safe_load(output_path.read_text())
        assert config["app_name"] == "scriptrag-dev"
        assert config["debug"] is True

    def test_init_prod_config(self, tmp_path):
        """Test generating production configuration."""
        output_path = tmp_path / "config-prod.yaml"

        result = runner.invoke(
            config_app,
            ["init", "--output", str(output_path), "--env", "prod"],
        )

        assert result.exit_code == 0
        assert output_path.exists()

        config = yaml.safe_load(output_path.read_text())
        assert config["app_name"] == "scriptrag"
        assert config["debug"] is False
        assert config["log_level"] == "WARNING"

    def test_init_ci_config(self, tmp_path):
        """Test generating CI configuration."""
        output_path = tmp_path / "config-ci.yaml"

        result = runner.invoke(
            config_app,
            ["init", "--output", str(output_path), "--env", "ci"],
        )

        assert result.exit_code == 0
        assert output_path.exists()

        config = yaml.safe_load(output_path.read_text())
        assert config["database_path"] == ":memory:"
        assert config["app_name"] == "scriptrag-test"

    def test_init_json_format(self, tmp_path):
        """Test generating JSON format configuration."""
        output_path = tmp_path / "config.json"

        result = runner.invoke(
            config_app,
            ["init", "--output", str(output_path), "--format", "json"],
        )

        assert result.exit_code == 0
        assert output_path.exists()

        # Verify it's valid JSON
        config = json.loads(output_path.read_text())
        assert "database_path" in config

    def test_init_toml_format_without_tomli_w(self, tmp_path):
        """Test TOML format error when tomli_w is not available."""
        output_path = tmp_path / "config.toml"

        with patch("scriptrag.cli.commands.config.init.tomli_w", None):
            # Simulate ImportError
            with patch(
                "scriptrag.cli.commands.config.init.import",
                side_effect=ImportError("No module named 'tomli_w'"),
            ):
                result = runner.invoke(
                    config_app,
                    ["init", "--output", str(output_path), "--format", "toml"],
                )

                assert result.exit_code == 1
                assert "tomli_w package required" in result.output

    def test_init_existing_file_prompt(self, tmp_path):
        """Test prompt when file already exists."""
        output_path = tmp_path / "config.yaml"
        output_path.write_text("existing: content")

        # Simulate user declining overwrite
        result = runner.invoke(
            config_app,
            ["init", "--output", str(output_path)],
            input="n\n",
        )

        assert result.exit_code == 0
        assert "Config generation cancelled" in result.output
        assert output_path.read_text() == "existing: content"  # Unchanged

    def test_init_force_overwrite(self, tmp_path):
        """Test force overwrite of existing file."""
        output_path = tmp_path / "config.yaml"
        output_path.write_text("existing: content")

        result = runner.invoke(
            config_app,
            ["init", "--output", str(output_path), "--force"],
        )

        assert result.exit_code == 0
        assert "Configuration file generated" in result.output
        assert "existing: content" not in output_path.read_text()

    def test_init_invalid_path(self):
        """Test error with invalid output path."""
        result = runner.invoke(
            config_app,
            ["init", "--output", "/invalid/path/config.yaml", "--force"],
        )

        assert result.exit_code == 1
        assert "Error" in result.output


class TestConfigValidate:
    """Test config validate command."""

    def test_validate_default(self):
        """Test validating default configuration."""
        result = runner.invoke(config_app, ["validate"])

        assert result.exit_code == 0
        assert "Configuration is valid" in result.output

    def test_validate_specific_file(self, tmp_path):
        """Test validating specific config file."""
        config_path = tmp_path / "test.yaml"
        config_path.write_text(
            """
database_path: /tmp/test.db
log_level: DEBUG
"""
        )

        result = runner.invoke(
            config_app,
            ["validate", "--config", str(config_path)],
        )

        assert result.exit_code == 0
        assert "Configuration is valid" in result.output

    def test_validate_invalid_file(self):
        """Test error with non-existent config file."""
        result = runner.invoke(
            config_app,
            ["validate", "--config", "/nonexistent/config.yaml"],
        )

        assert result.exit_code == 1
        assert "Config file not found" in result.output

    def test_validate_json_output(self):
        """Test JSON output format."""
        result = runner.invoke(
            config_app,
            ["validate", "--format", "json"],
        )

        assert result.exit_code == 0
        # Output should be valid JSON (empty or with config)
        output_lines = result.output.strip().split("\n")
        # Find the JSON output (after status messages)
        for line in output_lines:
            if line.startswith("{"):
                json.loads(line)  # Should not raise
                break

    def test_validate_yaml_output(self):
        """Test YAML output format."""
        result = runner.invoke(
            config_app,
            ["validate", "--format", "yaml"],
        )

        assert result.exit_code == 0
        assert "Configuration is valid" in result.output

    def test_validate_with_defaults(self):
        """Test showing all defaults."""
        result = runner.invoke(
            config_app,
            ["validate", "--show-defaults"],
        )

        assert result.exit_code == 0
        assert "Configuration is valid" in result.output


class TestConfigShow:
    """Test config show command."""

    def test_show_all(self):
        """Test showing all configuration."""
        result = runner.invoke(config_app, ["show"])

        assert result.exit_code == 0
        # Should show tree structure
        assert "ScriptRAG Configuration" in result.output

    def test_show_database_section(self):
        """Test showing database section."""
        result = runner.invoke(config_app, ["show", "database"])

        assert result.exit_code == 0
        assert "Database Configuration" in result.output
        assert "database_path" in result.output

    def test_show_llm_section(self):
        """Test showing LLM section."""
        result = runner.invoke(config_app, ["show", "llm"])

        # May or may not have LLM settings, but should not error
        assert result.exit_code == 0

    def test_show_invalid_section(self):
        """Test showing non-existent section."""
        result = runner.invoke(config_app, ["show", "nonexistent"])

        assert result.exit_code == 0
        assert "No settings found" in result.output

    def test_show_sources(self):
        """Test showing configuration sources."""
        result = runner.invoke(config_app, ["show", "--sources"])

        assert result.exit_code == 0
        assert "Configuration Sources" in result.output
        assert "Configuration Files" in result.output
        assert "Environment Variables" in result.output


class TestConfigPrecedence:
    """Test config precedence command."""

    def test_precedence_display(self):
        """Test precedence explanation display."""
        result = runner.invoke(config_app, ["precedence"])

        assert result.exit_code == 0
        assert "Configuration Precedence" in result.output
        assert "CLI Arguments" in result.output
        assert "Config Files" in result.output
        assert "Environment Variables" in result.output
        assert ".env File" in result.output
        assert "Default Values" in result.output

    def test_precedence_examples(self):
        """Test that examples are shown."""
        result = runner.invoke(config_app, ["precedence"])

        assert result.exit_code == 0
        assert "Examples:" in result.output
        assert "scriptrag init --db-path" in result.output


class TestConfigTemplates:
    """Test template generation functions."""

    def test_get_template_config_default(self):
        """Test getting default template."""
        template = get_template_config(None)
        assert "ScriptRAG Configuration File" in template
        assert "database_path" in template

    def test_get_template_config_dev(self):
        """Test getting dev template."""
        template = get_template_config("dev")
        assert "Development Configuration" in template
        assert "scriptrag-dev" in template

    def test_get_template_config_prod(self):
        """Test getting prod template."""
        template = get_template_config("prod")
        assert "Production Configuration" in template
        assert "SECURITY WARNING" in template

    def test_get_template_config_ci(self):
        """Test getting CI template."""
        template = get_template_config("ci")
        assert "CI/Testing Configuration" in template
        assert ":memory:" in template


class TestPathValidation:
    """Test path validation functionality."""

    def test_validate_path_in_home(self, tmp_path):
        """Test that paths in home directory are allowed."""
        home_path = Path.home() / "test" / "config.yaml"

        with patch(
            "scriptrag.cli.commands.config.init.Path.home", return_value=tmp_path
        ):
            result = runner.invoke(
                config_app,
                ["init", "--output", str(tmp_path / "config.yaml")],
            )

            assert result.exit_code == 0

    def test_validate_system_path_prompt(self, tmp_path):
        """Test prompt for system paths."""
        # Create a path that appears to be outside home
        system_path = Path("/etc/scriptrag/config.yaml")

        with patch(
            "scriptrag.cli.commands.config.init.Path.home", return_value=tmp_path
        ):
            with patch(
                "scriptrag.cli.commands.config.init.Path.resolve",
                return_value=system_path,
            ):
                # Simulate user declining
                result = runner.invoke(
                    config_app,
                    ["init", "--output", str(system_path)],
                    input="n\n",
                )

                assert result.exit_code == 0
                assert "Config generation cancelled" in result.output


class TestConfigIntegration:
    """Integration tests for config commands."""

    def test_init_and_validate_workflow(self, tmp_path):
        """Test complete workflow of init and validate."""
        config_path = tmp_path / "test-config.yaml"

        # Generate config
        result = runner.invoke(
            config_app,
            ["init", "--output", str(config_path), "--env", "dev"],
        )
        assert result.exit_code == 0

        # Validate generated config
        result = runner.invoke(
            config_app,
            ["validate", "--config", str(config_path)],
        )
        assert result.exit_code == 0
        assert "Configuration is valid" in result.output

    def test_all_commands_help(self):
        """Test that all commands have help text."""
        commands = ["init", "validate", "show", "precedence"]

        for cmd in commands:
            result = runner.invoke(config_app, [cmd, "--help"])
            assert result.exit_code == 0
            assert "Usage:" in result.output
            assert "Options" in result.output or "--help" in result.output
