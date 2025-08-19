import pytest

from scriptrag.database.readonly import _is_temp_directory


@pytest.mark.unit
def test_is_temp_directory_detects_macos_private_var_folders():
    # Simulate a macOS private temp path used on runners
    path = "/private/var/folders/xy/abcdefgh/T/test.db"
    assert _is_temp_directory(path, path.split("/")) is True


@pytest.mark.unit
def test_is_temp_directory_detects_macos_private_var_tmp():
    path = "/private/var/tmp/test.db"
    assert _is_temp_directory(path, path.split("/")) is True
