"""Tests for _is_temp_directory function to prevent false positives.

This test module specifically tests the fix for the bug where
directories containing "temp" as a substring (like "temperature" or "attempt")
were incorrectly identified as temp directories.
"""

from __future__ import annotations

from scriptrag.database.readonly import _is_temp_directory


class TestTempDirectoryPrecision:
    """Tests for precise temp directory detection."""

    def test_actual_temp_directories_are_detected(self):
        """Test that actual temp directories are correctly identified."""
        # Standard temp directory paths
        assert _is_temp_directory("/tmp/test.db")
        assert _is_temp_directory("/var/tmp/test.db")
        assert _is_temp_directory("/temp/test.db")
        assert _is_temp_directory("C:\\temp\\test.db")
        assert _is_temp_directory("C:\\Temp\\test.db")
        assert _is_temp_directory("/path/to/tmp/test.db")
        assert _is_temp_directory("/path/to/temp/test.db")

        # pytest cache directories
        assert _is_temp_directory("/project/.pytest_cache/test.db")
        assert _is_temp_directory("/path/to/pytest/test.db")

        # macOS temp directories
        assert _is_temp_directory("/private/var/folders/xyz/test.db")
        assert _is_temp_directory("/private/var/tmp/test.db")

        # CI-specific paths
        assert _is_temp_directory("/home/runner/work/project/test.db")
        assert _is_temp_directory("/github/workspace/test.db")

    def test_false_positive_temperature_not_detected(self):
        """Test that 'temperature' directory is NOT detected as temp."""
        # These should NOT be identified as temp directories
        assert not _is_temp_directory("/home/user/temperature/test.db")
        assert not _is_temp_directory("/projects/temperature_monitor/test.db")
        assert not _is_temp_directory("C:\\Users\\Documents\\temperature\\test.db")
        assert not _is_temp_directory("/data/temperature_readings/test.db")

    def test_false_positive_attempt_not_detected(self):
        """Test that 'attempt' directory is NOT detected as temp."""
        # These should NOT be identified as temp directories
        assert not _is_temp_directory("/home/user/attempt/test.db")
        assert not _is_temp_directory("/projects/attempt_counter/test.db")
        assert not _is_temp_directory("C:\\Users\\Documents\\attempt\\test.db")
        assert not _is_temp_directory("/data/login_attempts/test.db")

    def test_false_positive_tempest_not_detected(self):
        """Test that 'tempest' directory is NOT detected as temp."""
        # These should NOT be identified as temp directories
        assert not _is_temp_directory("/home/user/tempest/test.db")
        assert not _is_temp_directory("/projects/tempest_framework/test.db")
        assert not _is_temp_directory("C:\\Users\\Documents\\tempest\\test.db")
        assert not _is_temp_directory("/data/tempest_analysis/test.db")

    def test_false_positive_contemporary_not_detected(self):
        """Test that 'contemporary' directory is NOT detected as temp."""
        # These should NOT be identified as temp directories
        assert not _is_temp_directory("/home/user/contemporary/test.db")
        assert not _is_temp_directory("/projects/contemporary_art/test.db")
        assert not _is_temp_directory("C:\\Users\\Documents\\contemporary\\test.db")

    def test_false_positive_template_not_detected(self):
        """Test that 'template' directory is NOT detected as temp."""
        # These should NOT be identified as temp directories
        assert not _is_temp_directory("/home/user/template/test.db")
        assert not _is_temp_directory("/projects/template_engine/test.db")
        assert not _is_temp_directory("C:\\Users\\Documents\\template\\test.db")
        assert not _is_temp_directory("/data/templates/test.db")

    def test_mixed_case_temp_directories(self):
        """Test that mixed case temp directories are correctly identified."""
        # These SHOULD be identified as temp directories
        assert _is_temp_directory("/Tmp/test.db")
        assert _is_temp_directory("/TMP/test.db")
        assert _is_temp_directory("/Temp/test.db")
        assert _is_temp_directory("/TEMP/test.db")

    def test_nested_temp_directories(self):
        """Test nested temp directory structures."""
        # Actual temp paths
        assert _is_temp_directory("/projects/myapp/tmp/cache/test.db")
        assert _is_temp_directory("/home/user/work/temp/data/test.db")

        # Not temp paths (contains temp as substring but not as directory name)
        assert not _is_temp_directory("/projects/temperature/data/test.db")
        assert not _is_temp_directory("/home/user/attempt/cache/test.db")

    def test_windows_paths_with_backslashes(self):
        """Test Windows paths with backslashes."""
        # Actual temp directories
        assert _is_temp_directory("C:\\Temp\\test.db")
        assert _is_temp_directory("D:\\tmp\\cache\\test.db")
        assert _is_temp_directory("E:\\Projects\\MyApp\\temp\\test.db")

        # Not temp directories
        assert not _is_temp_directory("C:\\Temperature\\test.db")
        assert not _is_temp_directory("D:\\Attempt\\test.db")
        assert not _is_temp_directory("E:\\Projects\\Template\\test.db")

    def test_edge_cases(self):
        """Test edge cases for temp directory detection."""
        # Empty path components should not cause issues
        assert _is_temp_directory("//tmp//test.db")

        # Trailing slashes
        assert _is_temp_directory("/tmp/")
        assert not _is_temp_directory("/temperature/")

        # Just the temp directory name
        assert _is_temp_directory("tmp")
        assert _is_temp_directory("temp")
        assert not _is_temp_directory("temperature")
        assert not _is_temp_directory("attempt")

    def test_path_component_boundaries(self):
        """Test that temp detection respects path component boundaries."""
        # These have 'temp' or 'tmp' as complete directory names
        assert _is_temp_directory("/path/temp/file.db")
        assert _is_temp_directory("/path/tmp/file.db")

        # These have 'temp' or 'tmp' as part of a directory name, not complete
        assert not _is_temp_directory("/path/temp-data/file.db")
        assert not _is_temp_directory("/path/tmp_backup/file.db")
        assert not _is_temp_directory("/path/oldtemp/file.db")
        assert not _is_temp_directory("/path/tmpold/file.db")

        # However, note that our current implementation still has this limitation:
        # Hyphenated or underscored directory names containing temp/tmp will not match
        # This is intentional to avoid false positives


class TestRegressionForTempDetection:
    """Regression tests to ensure the fix doesn't break existing functionality."""

    def test_existing_temp_detection_still_works(self):
        """Ensure all previously detected temp paths still work."""
        # From existing tests - these should all still pass
        temp_paths = [
            "/tmp/test.db",
            "/var/tmp/test.db",
            "/private/var/folders/abc/def/test.db",
            "/private/var/tmp/test.db",
            "/home/runner/work/project/test.db",
            "/github/workspace/test.db",
            "/path/to/.pytest_cache/test.db",
            "/project/pytest/test.db",
        ]

        for path in temp_paths:
            assert _is_temp_directory(path), f"Failed to detect temp path: {path}"

    def test_production_paths_not_detected_as_temp(self):
        """Ensure production paths are not incorrectly detected as temp."""
        production_paths = [
            "/home/user/production/test.db",
            "/var/lib/myapp/test.db",
            "/usr/local/share/test.db",
            "/opt/myapp/test.db",
            "C:\\Program Files\\MyApp\\test.db",
            "/Applications/MyApp/test.db",
        ]

        for path in production_paths:
            assert not _is_temp_directory(path), f"Incorrectly detected as temp: {path}"
