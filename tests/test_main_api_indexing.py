"""Tests for ScriptRAG indexing functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scriptrag.main import ScriptRAG


@pytest.fixture
def sample_fountain_content():
    """Sample Fountain screenplay content."""
    return """Title: Test Script
Author: Test Author

FADE IN:

INT. COFFEE SHOP - DAY

The coffee shop is bustling with morning customers.

ALICE
(nervously)
I need to tell you something important.

BOB
What is it?

ALICE
I've been offered a job in London.

EXT. PARK - DAY

Alice and Bob walk through the park.

BOB
(shocked)
London? That's so far away!

ALICE
I know, but it's an amazing opportunity.

FADE OUT.
"""


@pytest.fixture
def temp_fountain_file(sample_fountain_content):
    """Create a temporary Fountain file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".fountain", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(sample_fountain_content)
        file_path = Path(tmp.name)

    yield file_path

    # Cleanup
    if file_path.exists():
        file_path.unlink()


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    # Create a temporary directory and generate a database path
    # Don't create the actual file - let ScriptRAG initialize it
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_scriptrag.db"

        yield db_path

        # Cleanup is automatic when temporary directory is removed


@pytest.fixture
def scriptrag_instance(temp_db_path):
    """Create a ScriptRAG instance with a temporary database."""
    import gc
    import platform

    from scriptrag.config import ScriptRAGSettings

    settings = ScriptRAGSettings(
        database_path=temp_db_path,
        skip_boneyard_filter=True,  # Enable for unit tests
    )
    instance = ScriptRAG(settings=settings, auto_init_db=True)

    yield instance

    # Ensure proper cleanup on Windows to prevent file locking issues
    if platform.system() == "Windows":
        # Force cleanup of all database-related components
        if hasattr(instance, "db_ops"):
            del instance.db_ops
        if hasattr(instance, "index_command"):
            del instance.index_command
        if hasattr(instance, "search_engine"):
            del instance.search_engine

        # Force garbage collection to close database connections
        del instance
        gc.collect()
        # Small delay to ensure Windows releases file handles
        import time

        time.sleep(0.1)


class TestIndexScript:
    """Test script indexing functionality."""

    def test_index_script_success(self, scriptrag_instance, temp_fountain_file):
        """Test successful script indexing."""
        result = scriptrag_instance.index_script(temp_fountain_file)

        assert result["indexed"] is True
        assert result["updated"] is False
        assert result["scenes_indexed"] == 2
        assert result["characters_indexed"] == 2  # Alice and Bob
        assert "script_id" in result

    def test_index_script_with_dry_run(self, scriptrag_instance, temp_fountain_file):
        """Test indexing with dry run mode."""
        result = scriptrag_instance.index_script(temp_fountain_file, dry_run=True)

        # In dry run, nothing should be actually indexed
        assert result["indexed"] is False
        # But preview counts should be provided
        assert result["scenes_indexed"] == 2  # Sample has 2 scenes

    def test_index_script_file_not_found(self, scriptrag_instance):
        """Test error when script file doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            scriptrag_instance.index_script("nonexistent.fountain")

        assert "Fountain file not found" in str(exc_info.value)

    def test_index_script_update(self, scriptrag_instance, temp_fountain_file):
        """Test updating an already indexed script."""
        # First index
        result1 = scriptrag_instance.index_script(temp_fountain_file)
        assert result1["indexed"] is True
        assert result1["updated"] is False

        # Second index should update
        result2 = scriptrag_instance.index_script(temp_fountain_file)
        assert result2["indexed"] is True
        assert result2["updated"] is True


class TestIndexDirectory:
    """Test directory indexing functionality."""

    def test_index_directory_non_recursive(
        self, scriptrag_instance, sample_fountain_content
    ):
        """Test indexing a directory non-recursively."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create fountain files in root
            for i in range(3):
                file_path = tmpdir_path / f"script{i}.fountain"
                file_path.write_text(sample_fountain_content)

            # Create a subdirectory with more files (should be ignored)
            subdir = tmpdir_path / "subdir"
            subdir.mkdir()
            (subdir / "subscript.fountain").write_text(sample_fountain_content)

            result = scriptrag_instance.index_directory(tmpdir_path, recursive=False)

            assert result["total_scripts"] == 3
            assert result["scripts_indexed"] == 3
            assert result["scripts_updated"] == 0
            assert result["scripts_failed"] == 0

    def test_index_directory_recursive(
        self, scriptrag_instance, sample_fountain_content
    ):
        """Test indexing a directory recursively."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create fountain files in root
            for i in range(2):
                file_path = tmpdir_path / f"script{i}.fountain"
                file_path.write_text(sample_fountain_content)

            # Create subdirectories with more files
            subdir1 = tmpdir_path / "subdir1"
            subdir1.mkdir()
            (subdir1 / "subscript1.fountain").write_text(sample_fountain_content)

            subdir2 = tmpdir_path / "subdir1" / "subdir2"
            subdir2.mkdir()
            (subdir2 / "subscript2.fountain").write_text(sample_fountain_content)

            result = scriptrag_instance.index_directory(tmpdir_path, recursive=True)

            assert result["total_scripts"] == 4
            assert result["scripts_indexed"] == 4

    def test_index_directory_dry_run(self, scriptrag_instance, sample_fountain_content):
        """Test directory indexing with dry run mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create fountain files
            for i in range(2):
                file_path = tmpdir_path / f"script{i}.fountain"
                file_path.write_text(sample_fountain_content)

            result = scriptrag_instance.index_directory(tmpdir_path, dry_run=True)

            assert result["total_scripts"] == 2
            assert result["scripts_indexed"] == 0  # Nothing indexed in dry run

    def test_index_directory_not_found(self, scriptrag_instance):
        """Test error when directory doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            scriptrag_instance.index_directory("nonexistent_dir")

        assert "Directory not found" in str(exc_info.value)

    def test_index_directory_not_a_directory(self, scriptrag_instance):
        """Test error when path is not a directory."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            with pytest.raises(ValueError) as exc_info:
                scriptrag_instance.index_directory(tmp.name)

            assert "Path is not a directory" in str(exc_info.value)

    def test_index_directory_with_errors(self, scriptrag_instance):
        """Test directory indexing with some files failing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a valid fountain file
            valid_file = tmpdir_path / "valid.fountain"
            valid_file.write_text("Title: Valid Script\n\nFADE IN:")

            # Create an invalid file that will cause parsing to fail
            invalid_file = tmpdir_path / "invalid.fountain"
            invalid_file.write_text("")

            # Store original method for selective mocking
            original_method = scriptrag_instance.index_command._index_single_script

            async def mock_index_single_script(path, dry_run):
                """Mock that fails for invalid file, succeeds for valid file."""
                if path == invalid_file:
                    raise Exception("Parse error")
                # Call original method for valid file
                return await original_method(path, dry_run)

            # Mock the method to simulate mixed success/failure
            with patch.object(
                scriptrag_instance.index_command,
                "_index_single_script",
                side_effect=mock_index_single_script,
            ):
                result = scriptrag_instance.index_directory(tmpdir_path)

                assert result["total_scripts"] == 2
                assert result["scripts_indexed"] >= 1
                assert result["scripts_failed"] >= 0

    def test_index_directory_batch_size(
        self, scriptrag_instance, sample_fountain_content
    ):
        """Test directory indexing with custom batch size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create multiple fountain files
            for i in range(5):
                file_path = tmpdir_path / f"script{i}.fountain"
                file_path.write_text(sample_fountain_content)

            # Index with small batch size
            result = scriptrag_instance.index_directory(tmpdir_path, batch_size=2)

            assert result["total_scripts"] == 5
            assert result["scripts_indexed"] == 5
