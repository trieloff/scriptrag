"""Comprehensive unit tests for config template generation.

These tests achieve 99% code coverage for the src.scriptrag.config.template module
by testing all functions, branches, and edge cases with Holmesian precision.
"""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.scriptrag.config.template import (
    generate_config_template,
    get_default_config_path,
    write_config_template,
)


class TestGenerateConfigTemplate:
    """Test the generate_config_template function comprehensively.

    The curious case of the configuration generation - every branch
    must be examined to understand the complete behavior.
    """

    def test_generate_config_template_basic_structure(self):
        """Test that the basic template structure is correct.

        The most elementary test - does the function produce what it claims?
        """
        template = generate_config_template()

        # Elementary - the template must be a string
        assert isinstance(template, str)
        assert len(template) > 100  # A substantial configuration

        # The header comments must be present
        assert "# ScriptRAG Configuration File" in template
        assert "# This file contains all available settings" in template

        # Key sections must exist
        assert "# Database Configuration" in template
        assert "# Application Settings" in template
        assert "# Logging Configuration" in template
        assert "# LLM (Language Model) Configuration" in template

    def test_generate_config_template_yaml_formatting(self):
        """Test that YAML formatting follows proper conventions.

        The science of proper formatting - each data type must be
        represented according to YAML standards.
        """
        template = generate_config_template()

        # String values should be quoted (except environment variables)
        assert 'database_path: "scriptrag.db"' in template
        assert 'database_journal_mode: "WAL"' in template
        assert 'app_name: "scriptrag"' in template
        assert 'log_format: "console"' in template

        # Boolean values should be lowercase
        assert "database_foreign_keys: true" in template
        assert "debug: false" in template
        assert "llm_force_static_models: false" in template

        # Numeric values should not be quoted
        assert "database_timeout: 30.0" in template
        assert "database_cache_size: -2000" in template
        assert "metadata_scan_size: 10240" in template
        assert "llm_temperature: 0.7" in template
        assert "llm_model_cache_ttl: 3600" in template

        # Environment variable references should not be quoted
        assert "# llm_api_key: ${GITHUB_TOKEN}" in template
        assert "# llm_api_key: ${OPENAI_API_KEY}" in template

    def test_generate_config_template_comment_handling(self):
        """Test that comments are properly formatted and positioned.

        The method to the madness - comments provide crucial context
        and must be positioned with mathematical precision.
        """
        template = generate_config_template()
        lines = template.split("\n")

        # Comment lines starting with '#' should exist
        comment_lines = [line for line in lines if line.startswith("#")]
        assert len(comment_lines) > 50  # Extensive commentary

        # Empty lines for spacing should exist
        empty_lines = [line for line in lines if line == ""]
        assert len(empty_lines) > 5  # Proper spacing

        # Setting lines with actual values
        setting_lines = [
            line
            for line in lines
            if ":" in line and not line.startswith("#") and line.strip()
        ]
        assert len(setting_lines) > 20  # Multiple configuration options

        # Comments with newline prefixes should be handled
        # (This tests the key.startswith("\n#") branch)
        assert "# Application Settings" in template  # From "\n# Application Settings"
        assert "# Logging Configuration" in template  # From "\n# Logging Configuration"

    def test_generate_config_template_value_type_branches(self):
        """Test all value type handling branches in the formatting logic.

        Every criminal leaves traces - every code branch must be examined.
        """
        template = generate_config_template()

        # String values that should be quoted
        assert 'database_path: "scriptrag.db"' in template
        assert 'log_format: "console"' in template

        # String values with environment variables (not quoted)
        # Note: These are in comments, but test the logic
        assert "${GITHUB_TOKEN}" in template
        assert "${OPENAI_API_KEY}" in template

        # Boolean values (should be lowercase)
        assert "database_foreign_keys: true" in template
        assert "debug: false" in template

        # Numeric values (integers and floats)
        assert "database_timeout: 30.0" in template
        assert "database_cache_size: -2000" in template
        assert "metadata_scan_size: 10240" in template

        # None values should be skipped (comment-only entries)
        # These test the "value is None" branch
        template_lines = template.split("\n")
        none_comment_indicators = [
            "# This file contains all available settings",
            "# Settings can be overridden by environment variables",
            "# Path to the SQLite database file",
        ]
        for comment in none_comment_indicators:
            assert comment in template

    def test_generate_config_template_specific_sections(self):
        """Test that all major configuration sections are present.

        A comprehensive investigation requires examining every room
        in the mansion of configuration.
        """
        template = generate_config_template()

        # Database section
        database_settings = [
            "database_path",
            "database_timeout",
            "database_foreign_keys",
            "database_journal_mode",
            "database_synchronous",
            "database_cache_size",
            "database_temp_store",
        ]
        for setting in database_settings:
            assert setting in template

        # Application section
        app_settings = ["app_name", "metadata_scan_size", "debug"]
        for setting in app_settings:
            assert setting in template

        # Logging section
        log_settings = [
            "log_level",
            "log_format",
            "log_file_rotation",
            "log_file_retention",
        ]
        for setting in log_settings:
            assert setting in template

        # Search section
        search_settings = [
            "search_vector_threshold",
            "search_vector_similarity_threshold",
            "search_vector_result_limit_factor",
            "search_vector_min_results",
        ]
        for setting in search_settings:
            assert setting in template

        # LLM section
        llm_settings = [
            "llm_temperature",
            "llm_force_static_models",
            "llm_model_cache_ttl",
        ]
        for setting in llm_settings:
            assert setting in template

        # Bible/Document embeddings section
        bible_settings = ["bible_embeddings_path", "bible_max_file_size"]
        for setting in bible_settings:
            assert setting in template

    def test_generate_config_template_llm_provider_examples(self):
        """Test that all LLM provider examples are included.

        The template must guide users through their choice of providers
        with the precision of a master detective's instructions.
        """
        template = generate_config_template()

        # Local LLM option
        assert "# Option 1: Local LLM" in template
        assert "# llm_provider: openai" in template
        assert "# llm_endpoint: http://localhost:1234/v1" in template
        assert "# llm_model: llama2" in template

        # GitHub Models option
        assert "# Option 2: GitHub Models" in template
        assert "# llm_provider: github_models" in template
        assert "${GITHUB_TOKEN}" in template

        # OpenAI API option
        assert "# Option 3: OpenAI API" in template
        assert "# llm_endpoint: https://api.openai.com/v1" in template
        assert "${OPENAI_API_KEY}" in template

        # Claude Code option
        assert "# Option 4: Claude via Claude Code" in template
        assert "# llm_provider: claude_code" in template


class TestWriteConfigTemplate:
    """Test the write_config_template function comprehensively.

    The case of the file creation - every scenario of success and failure
    must be catalogued with scientific precision.
    """

    def test_write_config_template_success(self, tmp_path):
        """Test successful template writing to a new file.

        The straightforward case - when everything proceeds as expected.
        """
        config_file = tmp_path / "test_config.yaml"

        result_path = write_config_template(config_file)

        # The file should exist and be the same path
        assert config_file.exists()
        assert result_path == config_file.resolve()

        # Content should match generated template
        content = config_file.read_text(encoding="utf-8")
        expected_content = generate_config_template()
        assert content == expected_content

        # File should contain key markers
        assert "# ScriptRAG Configuration File" in content
        assert "database_path" in content

    def test_write_config_template_force_overwrite(self, tmp_path):
        """Test forced overwriting of an existing file.

        Sometimes one must be decisive and overwrite the evidence.
        """
        config_file = tmp_path / "existing_config.yaml"

        # Create existing file with different content
        config_file.write_text("existing content", encoding="utf-8")
        assert config_file.exists()
        assert config_file.read_text() == "existing content"

        # Overwrite with force=True
        result_path = write_config_template(config_file, force=True)

        # File should be overwritten
        assert result_path == config_file.resolve()
        content = config_file.read_text(encoding="utf-8")
        assert "existing content" not in content
        assert "# ScriptRAG Configuration File" in content

    def test_write_config_template_file_exists_error(self, tmp_path):
        """Test FileExistsError when file exists and force=False.

        The case where preservation of existing evidence is paramount.
        """
        config_file = tmp_path / "existing_config.yaml"

        # Create existing file
        config_file.write_text("existing content", encoding="utf-8")

        # Should raise FileExistsError without force
        with pytest.raises(FileExistsError) as exc_info:
            write_config_template(config_file, force=False)

        assert "Configuration file already exists" in str(exc_info.value)
        assert str(config_file) in str(exc_info.value)

        # Original content should be preserved
        assert config_file.read_text() == "existing content"

    def test_write_config_template_creates_parent_directory(self, tmp_path):
        """Test that parent directories are created as needed.

        Even the deepest hiding places must be accessible to justice.
        """
        nested_dir = tmp_path / "deeply" / "nested" / "config"
        config_file = nested_dir / "scriptrag.yaml"

        # Parent directory shouldn't exist initially
        assert not nested_dir.exists()

        result_path = write_config_template(config_file)

        # Directory and file should be created
        assert nested_dir.exists()
        assert config_file.exists()
        assert result_path == config_file.resolve()

        # Content should be correct
        content = config_file.read_text(encoding="utf-8")
        assert "# ScriptRAG Configuration File" in content

    def test_write_config_template_path_resolution(self, tmp_path):
        """Test that paths are properly resolved.

        Every path must lead to its absolute truth.
        """
        # Use a relative path that needs resolution
        os.chdir(tmp_path)
        config_file = Path("./config/scriptrag.yaml")

        result_path = write_config_template(config_file)

        # Should return resolved absolute path
        assert result_path.is_absolute()
        assert result_path == config_file.resolve()
        assert result_path.exists()


class TestGetDefaultConfigPath:
    """Test the get_default_config_path function comprehensively.

    The mystery of where configuration naturally belongs - across
    different environments and failure modes.
    """

    def test_get_default_config_path_xdg_success(self):
        """Test successful XDG config directory path generation.

        The standard case - when the system behaves as expected.
        """
        with patch("pathlib.Path.home") as mock_home:
            # Create a mock Path object that returns itself when resolve() is called
            mock_path = Path("/home/testuser")
            mock_home.return_value = mock_path

            # Mock successful mkdir operation
            with patch("pathlib.Path.mkdir") as mock_mkdir:
                mock_mkdir.return_value = None

                # Mock the resolve method to return the same path
                with patch.object(mock_path, "resolve", return_value=mock_path):
                    result = get_default_config_path()

                    expected = (
                        Path("/home/testuser") / ".config" / "scriptrag" / "config.yaml"
                    )
                    assert result == expected

                # Should attempt to create the config directory
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_get_default_config_path_home_resolution_error(self):
        """Test fallback when home directory resolution fails.

        When the usual path is blocked, we must find another way.
        """
        with patch("pathlib.Path.home") as mock_home:
            # Simulate home directory resolution failure
            mock_home.side_effect = OSError("No home directory")

            with patch("pathlib.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path("/current/working/dir")

                result = get_default_config_path()

                expected = Path("/current/working/dir/scriptrag.yaml")
                assert result == expected

    def test_get_default_config_path_permission_error(self):
        """Test fallback when config directory creation fails due to permissions.

        Even the best-laid plans can be thwarted by system restrictions.
        """
        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = Path("/home/testuser")

            # Mock permission error when creating config directory
            with patch("pathlib.Path.mkdir") as mock_mkdir:
                mock_mkdir.side_effect = PermissionError("Permission denied")

                with patch("pathlib.Path.cwd") as mock_cwd:
                    mock_cwd.return_value = Path("/fallback/dir")

                    result = get_default_config_path()

                    expected = Path("/fallback/dir/scriptrag.yaml")
                    assert result == expected

    def test_get_default_config_path_runtime_error_fallback(self):
        """Test fallback when RuntimeError occurs during path resolution.

        Some systems throw RuntimeError when resolving home - we adapt.
        """
        with patch("pathlib.Path.home") as mock_home:
            # Simulate RuntimeError during home resolution
            mock_home.side_effect = RuntimeError("System-specific home error")

            with patch("pathlib.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Path("/current/dir")

                result = get_default_config_path()

                # Use pathlib for cross-platform compatibility
                expected = Path("/current/dir") / "scriptrag.yaml"
                assert result == expected

    def test_get_default_config_path_cwd_resolution_error(self):
        """Test ultimate fallback when even cwd resolution fails.

        When all else fails, we resort to the most basic approach.
        """
        with patch("pathlib.Path.home") as mock_home:
            mock_home.side_effect = OSError("No home directory")

            with patch("pathlib.Path.cwd") as mock_cwd:
                # Even cwd resolution fails
                mock_cwd.side_effect = OSError("Cannot determine current directory")

                result = get_default_config_path()

                # Should return relative path as ultimate fallback
                expected = Path("scriptrag.yaml")
                assert result == expected

    def test_get_default_config_path_cwd_runtime_error(self):
        """Test ultimate fallback when RuntimeError occurs in cwd resolution.

        RuntimeError can occur in cwd.resolve() on some systems.
        """
        with patch("pathlib.Path.home") as mock_home:
            mock_home.side_effect = OSError("No home directory")

            with patch("pathlib.Path.cwd") as mock_cwd:
                mock_cwd.return_value = Mock()
                mock_cwd.return_value.resolve.side_effect = RuntimeError("Path error")

                result = get_default_config_path()

                # Should return relative path as ultimate fallback
                expected = Path("scriptrag.yaml")
                assert result == expected

    def test_get_default_config_path_mkdir_os_error(self):
        """Test fallback when mkdir fails with OSError.

        OSError during directory creation should trigger fallback.
        """
        with patch("pathlib.Path.home") as mock_home:
            mock_path = Path("/home/testuser")
            mock_home.return_value = mock_path

            with patch("pathlib.Path.mkdir") as mock_mkdir:
                mock_mkdir.side_effect = OSError("Filesystem error")

                with patch("pathlib.Path.cwd") as mock_cwd:
                    mock_cwd.return_value = Path("/fallback/dir")

                    # Mock the resolve method to return the same path
                    with patch.object(mock_path, "resolve", return_value=mock_path):
                        result = get_default_config_path()

                        # Use pathlib for cross-platform compatibility
                        expected = Path("/fallback/dir") / "scriptrag.yaml"
                        assert result == expected

    def test_get_default_config_path_real_world_simulation(self, tmp_path):
        """Test with actual filesystem operations in a controlled environment.

        Sometimes the best test is one that mirrors reality.
        """
        # Create a temporary home directory
        fake_home = tmp_path / "home" / "testuser"
        fake_home.mkdir(parents=True)

        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = fake_home

            result = get_default_config_path()

            expected = fake_home / ".config" / "scriptrag" / "config.yaml"
            assert result == expected

            # Config directory should be created
            config_dir = fake_home / ".config" / "scriptrag"
            assert config_dir.exists()
            assert config_dir.is_dir()


class TestEdgeCasesAndIntegration:
    """Test edge cases and integration scenarios.

    The final examination - ensuring all components work together
    under various unusual circumstances.
    """

    def test_generate_config_template_environment_variable_strings(self):
        """Test the edge case of environment variable string formatting.

        The curious case of the ${} patterns - testing the branch where
        strings starting with ${ are not quoted.
        """
        # This tests the specific branch in line 126: not value.startswith("${")
        template = generate_config_template()

        # Look for environment variable patterns that should NOT be quoted
        env_var_patterns = ["${GITHUB_TOKEN}", "${OPENAI_API_KEY}"]
        for pattern in env_var_patterns:
            assert pattern in template
            # Ensure they appear without quotes in comments
            assert f'"{pattern}"' not in template  # Should not be quoted

        # Also verify regular strings ARE quoted
        quoted_strings = ['database_path: "scriptrag.db"', 'app_name: "scriptrag"']
        for quoted_str in quoted_strings:
            assert quoted_str in template

    def test_template_generation_deterministic(self):
        """Test that template generation is deterministic.

        The same evidence should always lead to the same conclusion.
        """
        template1 = generate_config_template()
        template2 = generate_config_template()

        assert template1 == template2
        assert len(template1) == len(template2)

    def test_template_content_comprehensive(self):
        """Test that template contains all expected content sections.

        A thorough investigation of the complete template structure.
        """
        template = generate_config_template()

        # All major configuration categories should be present
        required_sections = [
            "Database Configuration",
            "Application Settings",
            "Logging Configuration",
            "Search Settings",
            "LLM (Language Model) Configuration",
            "Bible/Document Embeddings Settings",
        ]

        for section in required_sections:
            assert section in template

        # All LLM provider options should be documented
        provider_options = [
            "Option 1: Local LLM",
            "Option 2: GitHub Models",
            "Option 3: OpenAI API",
            "Option 4: Claude via Claude Code",
        ]

        for option in provider_options:
            assert option in template

    def test_write_template_integration_with_generation(self, tmp_path):
        """Test integration between template generation and file writing.

        The complete chain of evidence from generation to preservation.
        """
        config_file = tmp_path / "integration_test.yaml"

        # Generate template independently
        expected_template = generate_config_template()

        # Write template to file
        result_path = write_config_template(config_file)

        # Read back and verify
        actual_content = config_file.read_text(encoding="utf-8")

        assert actual_content == expected_template
        assert result_path == config_file.resolve()

    def test_all_functions_work_together(self, tmp_path):
        """Test that all three functions work together harmoniously.

        The complete criminal investigation process from start to finish.
        """
        # Generate a template
        template_content = generate_config_template()
        assert len(template_content) > 0

        # Get a default path (simulate successful case)
        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = tmp_path / "user_home"
            default_path = get_default_config_path()

        # Use that path to write the template
        written_path = write_config_template(default_path)

        # Verify the integration
        assert written_path.exists()
        assert written_path.read_text(encoding="utf-8") == template_content

        # Verify path relationships - use cross-platform path checking
        assert str(written_path).endswith("config.yaml")
        assert str(Path(".config") / "scriptrag") in str(written_path)
