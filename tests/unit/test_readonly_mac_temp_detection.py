import pytest

from scriptrag.database.readonly import _is_temp_directory


@pytest.mark.unit
def test_is_temp_directory_detects_macos_private_var_folders():
    # Simulate a macOS private temp path used on runners
    path = "/private/var/folders/xy/abcdefgh/T/test.db"
    assert _is_temp_directory(path) is True


@pytest.mark.unit
def test_is_temp_directory_detects_macos_private_var_tmp():
    path = "/private/var/tmp/test.db"
    assert _is_temp_directory(path) is True


@pytest.mark.unit
def test_is_temp_directory_detects_ci_runner_path():
    """Test that CI runner paths are correctly detected."""
    path = "/home/runner/work/project/test.db"
    assert _is_temp_directory(path) is True


@pytest.mark.unit
def test_is_temp_directory_detects_github_workspace():
    """Test that GitHub workspace paths are correctly detected."""
    path = "/github/workspace/test.db"
    assert _is_temp_directory(path) is True


@pytest.mark.unit
def test_is_temp_directory_rejects_ci_path_in_middle():
    """Test that CI paths embedded in the middle of a path are not detected.

    This is a regression test for a bug where 'in' was used instead of 'startswith'
    for CI path detection, causing false positives.
    """
    # This path contains '/home/runner/work/' but not at the start
    path = "/var/data/home/runner/work/test.db"
    assert _is_temp_directory(path) is False


@pytest.mark.unit
def test_is_temp_directory_rejects_github_workspace_in_middle():
    """Test that GitHub workspace paths embedded in the middle are not detected.

    This is a regression test for a bug where 'in' was used instead of 'startswith'
    for CI path detection, causing false positives.
    """
    # This path contains '/github/workspace/' but not at the start
    path = "/data/github/workspace/test.db"
    assert _is_temp_directory(path) is False


@pytest.mark.unit
def test_is_temp_directory_detects_temp_indicators():
    """Test that general temp indicators are detected anywhere in path."""
    # These should be detected anywhere in the path
    paths = [
        "/var/tmp/test.db",
        "/home/user/temp/test.db",
        "/data/pytest/test.db",
        "/cache/.pytest_cache/test.db",
    ]
    for path in paths:
        assert _is_temp_directory(path) is True


@pytest.mark.unit
def test_is_temp_directory_rejects_non_temp_paths():
    """Test that non-temp paths are not detected as temp."""
    paths = [
        "/var/lib/database.db",
        "/home/user/data/production.db",
        "/opt/application/db.sqlite",
    ]
    for path in paths:
        assert _is_temp_directory(path) is False
