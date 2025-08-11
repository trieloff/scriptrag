"""Common test fixtures for ScriptRAG tests."""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from scriptrag.config import ScriptRAGSettings, set_settings


@pytest.fixture
def isolated_test_dir(tmp_path: Path) -> Iterator[Path]:
    """Create an isolated test directory with clean fixture copies.

    This fixture ensures that:
    1. Tests run in an isolated temporary directory
    2. Fixture files are copied (not linked) to prevent contamination
    3. Database is created in the temp directory, not repo root

    Yields:
        Path to the isolated test directory containing copies of fixtures.
    """
    # Create test directory structure
    test_dir = tmp_path / "test_workspace"
    test_dir.mkdir()

    # Copy fixture files if needed
    fixtures_source = Path(__file__).parent / "fixtures"
    if fixtures_source.exists():
        fixtures_dest = test_dir / "fixtures"
        shutil.copytree(fixtures_source, fixtures_dest)

    yield test_dir

    # Cleanup is automatic with tmp_path


@pytest.fixture
def test_settings(tmp_path: Path, monkeypatch) -> ScriptRAGSettings:
    """Create test settings with isolated paths.

    This fixture ensures:
    1. Database is created in temp directory
    2. Environment variables are properly isolated
    3. Global settings are updated for the test

    Args:
        tmp_path: Pytest temp directory fixture
        monkeypatch: Pytest monkeypatch fixture

    Returns:
        Configured test settings
    """
    # Create isolated database path
    db_path = tmp_path / "test_scriptrag.db"

    # Set environment variable to ensure isolation
    monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

    # Create and set test settings
    settings = ScriptRAGSettings(database_path=db_path)
    set_settings(settings)

    return settings


@pytest.fixture
def clean_fountain_fixture(tmp_path: Path) -> Iterator[Path]:
    """Provide clean fountain test files in an isolated directory.

    This fixture:
    1. Copies fountain test files to a temp directory
    2. Ensures files are not contaminated with metadata
    3. Returns path to the temp directory with clean files

    Yields:
        Path to directory containing clean fountain files.
    """
    # Source fixture files
    fixtures_dir = Path(__file__).parent / "fixtures" / "fountain" / "test_data"

    # Create temp directory for test files
    test_files_dir = tmp_path / "fountain_files"
    test_files_dir.mkdir()

    # Copy only the clean fountain files (not the ones with metadata)
    clean_files = [
        "coffee_shop.fountain",
        "nested_script.fountain",
        "parser_test.fountain",
        "simple_script.fountain",
        "test_script.fountain",
    ]

    for filename in clean_files:
        src = fixtures_dir / filename
        if src.exists():
            dst = test_files_dir / filename
            shutil.copy2(src, dst)

            # Verify file is clean (no metadata)
            content = dst.read_text(encoding="utf-8")
            if "SCRIPTRAG-META-START" in content:
                # Remove any metadata that shouldn't be there
                import re

                clean_content = re.sub(
                    r"/\*\s*SCRIPTRAG-META-START.*?SCRIPTRAG-META-END\s*\*/",
                    "",
                    content,
                    flags=re.DOTALL,
                ).strip()
                dst.write_text(clean_content, encoding="utf-8")

    yield test_files_dir

    # Cleanup is automatic with tmp_path


@pytest.fixture
def fountain_with_metadata(tmp_path: Path) -> Iterator[Path]:
    """Provide fountain files that already have metadata.

    This fixture:
    1. Copies fountain files with existing metadata
    2. Returns path to temp directory with these files

    Yields:
        Path to directory containing fountain files with metadata.
    """
    # Source fixture files
    fixtures_dir = Path(__file__).parent / "fixtures" / "fountain" / "test_data"

    # Create temp directory
    test_files_dir = tmp_path / "fountain_with_meta"
    test_files_dir.mkdir()

    # Copy files that should have metadata
    metadata_files = [
        "coffee_shop_with_metadata.fountain",
        "script_with_metadata.fountain",
        "props_test_script.fountain",
    ]

    for filename in metadata_files:
        src = fixtures_dir / filename
        if src.exists():
            dst = test_files_dir / filename
            shutil.copy2(src, dst)

    yield test_files_dir

    # Cleanup is automatic with tmp_path
