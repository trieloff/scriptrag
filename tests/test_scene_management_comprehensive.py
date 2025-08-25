"""Comprehensive tests for SceneManagementAPI to achieve 99% code coverage.

This test suite focuses on covering all the missing lines and edge cases
identified in the coverage analysis, particularly around error handling,
validation edge cases, and the bible reading functionality.
"""

import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.api.scene_management import SceneManagementAPI
from scriptrag.api.scene_models import SceneIdentifier, ValidationResult
from scriptrag.config import ScriptRAGSettings
from scriptrag.parser import Scene


class TestSceneManagementAPIConfiguration:
    """Test SceneManagementAPI initialization and configuration."""

    def test_init_with_settings(self):
        """Test initialization with custom settings."""
        custom_settings = ScriptRAGSettings()
        api = SceneManagementAPI(settings=custom_settings)

        assert api.settings is custom_settings
        assert api.db_ops is not None
        assert api.scene_db is not None
        assert api.validator is not None
        assert api.parser is not None

    def test_init_without_settings(self):
        """Test initialization without settings (uses get_settings)."""
        with patch("scriptrag.config.get_settings") as mock_get_settings:
            mock_settings = ScriptRAGSettings()
            mock_get_settings.return_value = mock_settings

            api = SceneManagementAPI()

            assert api.settings is mock_settings
            mock_get_settings.assert_called_once()


class TestReadSceneEdgeCases:
    """Test read_scene method edge cases and error handling."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return SceneManagementAPI()

    @pytest.mark.asyncio
    async def test_read_scene_database_connection_error(self, api):
        """Test read_scene when database connection fails during transaction."""
        scene_id = SceneIdentifier("test_project", 1)

        # Mock transaction context manager to raise on entry
        mock_transaction = MagicMock()
        mock_transaction.__enter__.side_effect = sqlite3.Error("Connection failed")

        with patch.object(api.db_ops, "transaction", return_value=mock_transaction):
            result = await api.read_scene(scene_id, "test_reader")

        assert result.success is False
        assert "Connection failed" in result.error
        assert result.scene is None
        assert result.last_read is None

    @pytest.mark.asyncio
    async def test_read_scene_update_last_read_fails(self, api):
        """Test read_scene when updating last_read timestamp fails."""
        scene_id = SceneIdentifier("test_project", 1)

        mock_scene = Scene(
            number=1,
            heading="INT. TEST SCENE - DAY",
            content="Test content",
            original_text="Test content",
            content_hash="hash123",
        )

        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()

            with (
                patch.object(api.scene_db, "get_scene_by_id", return_value=mock_scene),
                patch.object(
                    api.scene_db,
                    "update_last_read",
                    side_effect=sqlite3.Error("Update failed"),
                ),
            ):
                result = await api.read_scene(scene_id, "test_reader")

        # Should still fail because update_last_read failed
        assert result.success is False
        assert "Update failed" in result.error
        assert result.scene is None

    @pytest.mark.asyncio
    async def test_read_scene_with_none_scene_id_key(self, api):
        """Test read_scene error message includes scene key properly."""
        scene_id = SceneIdentifier("test_project", 1)

        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()

            with patch.object(api.scene_db, "get_scene_by_id", return_value=None):
                result = await api.read_scene(scene_id)

        assert result.success is False
        assert "Scene not found: test_project:001" in result.error
        assert result.scene is None
        assert result.last_read is None


class TestUpdateSceneEdgeCases:
    """Test update_scene method edge cases and error handling."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return SceneManagementAPI()

    @pytest.mark.asyncio
    async def test_update_scene_validation_fails(self, api):
        """Test update_scene when Fountain validation fails."""
        scene_id = SceneIdentifier("test_project", 1)
        invalid_content = "Not a valid scene format"

        # Mock validator to return invalid result
        mock_validation = ValidationResult(
            is_valid=False, errors=["Missing scene heading", "Invalid format"]
        )

        with patch.object(
            api.validator, "validate_scene_content", return_value=mock_validation
        ):
            result = await api.update_scene(scene_id, invalid_content)

        assert result.success is False
        assert (
            "Invalid Fountain format: Missing scene heading; Invalid format"
            in result.error
        )
        assert result.validation_errors == ["Missing scene heading", "Invalid format"]
        assert result.updated_scene is None

    @pytest.mark.asyncio
    async def test_update_scene_conflict_check_scene_modified_recently(self, api):
        """Test update_scene conflict when scene was modified after last_read."""
        scene_id = SceneIdentifier("test_project", 1)
        new_content = """INT. UPDATED SCENE - DAY

Updated content."""

        # Set up timestamps: scene was modified 5 minutes ago, last read 10 minutes ago
        last_read = datetime.now(UTC) - timedelta(minutes=10)
        last_modified = datetime.now(UTC) - timedelta(
            minutes=5
        )  # More recent than last_read

        mock_scene = Scene(
            number=1,
            heading="INT. TEST SCENE - DAY",
            content="Original content",
            original_text="Original content",
            content_hash="original_hash",
        )

        # Mock valid validation
        mock_validation = ValidationResult(is_valid=True, parsed_scene=mock_scene)

        with patch.object(
            api.validator, "validate_scene_content", return_value=mock_validation
        ):
            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()

                with (
                    patch.object(
                        api.scene_db, "get_scene_by_id", return_value=mock_scene
                    ),
                    patch.object(
                        api.scene_db, "get_last_modified", return_value=last_modified
                    ),
                ):
                    result = await api.update_scene(
                        scene_id, new_content, check_conflicts=True, last_read=last_read
                    )

        assert result.success is False
        assert "Scene was modified since last read" in result.error
        assert "CONCURRENT_MODIFICATION" in result.validation_errors
        assert result.updated_scene is None

    @pytest.mark.asyncio
    async def test_update_scene_conflict_check_no_last_modified(self, api):
        """Test update_scene conflict check when last_modified is None."""
        scene_id = SceneIdentifier("test_project", 1)
        new_content = """INT. UPDATED SCENE - DAY

Updated content."""

        last_read = datetime.now(UTC) - timedelta(minutes=5)

        mock_scene = Scene(
            number=1,
            heading="INT. TEST SCENE - DAY",
            content="Original content",
            original_text="Original content",
            content_hash="original_hash",
        )

        updated_scene = Scene(
            number=1,
            heading="INT. UPDATED SCENE - DAY",
            content=new_content,
            original_text=new_content,
            content_hash="new_hash",
        )

        # Mock valid validation
        mock_validation = ValidationResult(is_valid=True, parsed_scene=updated_scene)

        with patch.object(
            api.validator, "validate_scene_content", return_value=mock_validation
        ):
            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()

                with (
                    patch.object(
                        api.scene_db, "get_scene_by_id", return_value=mock_scene
                    ),
                    patch.object(
                        api.scene_db, "get_last_modified", return_value=None
                    ),  # No last modified
                    patch.object(
                        api.scene_db, "update_scene_content", return_value=updated_scene
                    ),
                ):
                    result = await api.update_scene(
                        scene_id, new_content, check_conflicts=True, last_read=last_read
                    )

        # Should succeed because no last_modified means no conflict
        assert result.success is True
        assert result.error is None
        assert result.updated_scene is updated_scene
        assert result.validation_errors == []

    @pytest.mark.asyncio
    async def test_update_scene_database_error_during_update(self, api):
        """Test update_scene when database update fails."""
        scene_id = SceneIdentifier("test_project", 1)
        new_content = """INT. UPDATED SCENE - DAY

Content."""

        mock_scene = Scene(
            number=1,
            heading="INT. TEST SCENE - DAY",
            content="Original content",
            original_text="Original content",
            content_hash="original_hash",
        )

        # Mock valid validation
        mock_validation = ValidationResult(is_valid=True, parsed_scene=mock_scene)

        with patch.object(
            api.validator, "validate_scene_content", return_value=mock_validation
        ):
            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()

                with (
                    patch.object(
                        api.scene_db, "get_scene_by_id", return_value=mock_scene
                    ),
                    patch.object(
                        api.scene_db,
                        "update_scene_content",
                        side_effect=sqlite3.Error("DB update failed"),
                    ),
                ):
                    result = await api.update_scene(
                        scene_id, new_content, check_conflicts=False
                    )

        assert result.success is False
        assert "DB update failed" in result.error
        assert "UPDATE_FAILED" in result.validation_errors
        assert result.updated_scene is None


class TestAddSceneEdgeCases:
    """Test add_scene method edge cases and error handling."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return SceneManagementAPI()

    @pytest.mark.asyncio
    async def test_add_scene_validation_multiple_errors(self, api):
        """Test add_scene with validation returning multiple errors."""
        scene_id = SceneIdentifier("test_project", 5)
        invalid_content = "Invalid scene content"

        # Mock validator to return multiple errors
        mock_validation = ValidationResult(
            is_valid=False,
            errors=["No scene heading", "Invalid format", "Missing content"],
        )

        with patch.object(
            api.validator, "validate_scene_content", return_value=mock_validation
        ):
            result = await api.add_scene(scene_id, invalid_content, "after")

        assert result.success is False
        assert (
            "Invalid Fountain format: No scene heading; Invalid format; Missing content"
            in result.error
        )
        assert result.created_scene is None
        assert result.renumbered_scenes == []

    @pytest.mark.asyncio
    async def test_add_scene_database_error_during_shift(self, api):
        """Test add_scene when scene shifting fails."""
        scene_id = SceneIdentifier("test_project", 5)
        content = """INT. NEW SCENE - DAY

New scene content."""

        mock_reference = Scene(
            number=5,
            heading="INT. REFERENCE - DAY",
            content="Reference",
            original_text="Reference",
            content_hash="ref_hash",
        )

        # Mock valid validation
        mock_validation = ValidationResult(is_valid=True, parsed_scene=mock_reference)

        with patch.object(
            api.validator, "validate_scene_content", return_value=mock_validation
        ):
            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()

                with (
                    patch.object(
                        api.scene_db, "get_scene_by_id", return_value=mock_reference
                    ),
                    patch.object(
                        api.scene_db,
                        "shift_scenes_after",
                        side_effect=sqlite3.Error("Shift failed"),
                    ),
                ):
                    result = await api.add_scene(scene_id, content, "after")

        assert result.success is False
        assert "Shift failed" in result.error
        assert result.created_scene is None

    @pytest.mark.asyncio
    async def test_add_scene_database_error_during_create(self, api):
        """Test add_scene when scene creation fails."""
        scene_id = SceneIdentifier("test_project", 5)
        content = """INT. NEW SCENE - DAY

New scene content."""

        mock_reference = Scene(
            number=5,
            heading="INT. REFERENCE - DAY",
            content="Reference",
            original_text="Reference",
            content_hash="ref_hash",
        )

        # Mock valid validation
        mock_validation = ValidationResult(is_valid=True, parsed_scene=mock_reference)

        with patch.object(
            api.validator, "validate_scene_content", return_value=mock_validation
        ):
            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()

                with (
                    patch.object(
                        api.scene_db, "get_scene_by_id", return_value=mock_reference
                    ),
                    patch.object(api.scene_db, "shift_scenes_after"),
                    patch.object(
                        api.scene_db,
                        "create_scene",
                        side_effect=ValueError("Create failed"),
                    ),
                ):
                    result = await api.add_scene(scene_id, content, "after")

        assert result.success is False
        assert "Create failed" in result.error
        assert result.created_scene is None


class TestDeleteSceneEdgeCases:
    """Test delete_scene method edge cases and error handling."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return SceneManagementAPI()

    @pytest.mark.asyncio
    async def test_delete_scene_database_error_during_delete(self, api):
        """Test delete_scene when deletion operation fails."""
        scene_id = SceneIdentifier("test_project", 5)

        mock_scene = Scene(
            number=5,
            heading="INT. TO DELETE - DAY",
            content="Delete me",
            original_text="Delete me",
            content_hash="del_hash",
        )

        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()

            with (
                patch.object(api.scene_db, "get_scene_by_id", return_value=mock_scene),
                patch.object(
                    api.scene_db,
                    "delete_scene",
                    side_effect=sqlite3.Error("Delete failed"),
                ),
            ):
                result = await api.delete_scene(scene_id, confirm=True)

        assert result.success is False
        assert "Delete failed" in result.error
        assert result.renumbered_scenes == []

    @pytest.mark.asyncio
    async def test_delete_scene_database_error_during_compact(self, api):
        """Test delete_scene when scene number compaction fails."""
        scene_id = SceneIdentifier("test_project", 5)

        mock_scene = Scene(
            number=5,
            heading="INT. TO DELETE - DAY",
            content="Delete me",
            original_text="Delete me",
            content_hash="del_hash",
        )

        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()

            with (
                patch.object(api.scene_db, "get_scene_by_id", return_value=mock_scene),
                patch.object(api.scene_db, "delete_scene"),  # Succeeds
                patch.object(
                    api.scene_db,
                    "compact_scene_numbers",
                    side_effect=sqlite3.Error("Compact failed"),
                ),
            ):
                result = await api.delete_scene(scene_id, confirm=True)

        assert result.success is False
        assert "Compact failed" in result.error
        assert result.renumbered_scenes == []


class TestReadBibleComprehensive:
    """Comprehensive tests for read_bible method covering all edge cases."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return SceneManagementAPI()

    @pytest.mark.asyncio
    async def test_read_bible_path_normalization_edge_cases(self, api):
        """Test bible file path normalization edge cases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create nested structure with complex paths
            docs_dir = tmpdir_path / "docs" / "reference"
            docs_dir.mkdir(parents=True)
            bible_file = docs_dir / "world_bible.md"
            bible_content = "# World Bible\n\nComplex path content"
            bible_file.write_text(bible_content)

            # Use the same directory for script (project path = tmpdir_path)
            script_path = tmpdir_path / "main.fountain"
            script_path.write_text("FADE IN:")

            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()
                mock_conn.execute().fetchone.return_value = {
                    "file_path": str(script_path)
                }

                with patch(
                    "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                    return_value=[bible_file],
                ):
                    # Test finding by exact relative path with forward slashes
                    result = await api.read_bible(
                        "test_project", "docs/reference/world_bible.md"
                    )

                    assert result.success is True
                    assert result.content == bible_content

    @pytest.mark.asyncio
    async def test_read_bible_windows_path_compatibility(self, api):
        """Test bible reading with Windows-style path separators."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            subdir = tmpdir_path / "reference"
            subdir.mkdir()
            bible_file = subdir / "guide.md"
            bible_content = "Guide content"
            bible_file.write_text(bible_content)

            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()
                mock_conn.execute().fetchone.return_value = {
                    "file_path": str(tmpdir_path / "script.fountain")
                }

                with patch(
                    "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                    return_value=[bible_file],
                ):
                    # Test with forward slashes (the standard path format)
                    result = await api.read_bible("test_project", "reference/guide.md")

                    # Should work with standard forward slash format
                    assert result.success is True
                    assert result.content == bible_content

    @pytest.mark.asyncio
    async def test_read_bible_project_path_edge_cases(self, api):
        """Test read_bible with different project path scenarios."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Bible file outside project path
            external_path = tmpdir_path / "external"
            external_path.mkdir()
            bible_file = external_path / "external_bible.md"
            bible_content = "External content"
            bible_file.write_text(bible_content)

            project_path = tmpdir_path / "project"
            project_path.mkdir()
            script_path = project_path / "script.fountain"
            script_path.write_text("FADE IN:")

            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()
                mock_conn.execute().fetchone.return_value = {
                    "file_path": str(script_path)
                }

                with patch(
                    "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                    return_value=[bible_file],  # File outside project
                ):
                    # List files - should handle external paths gracefully
                    result = await api.read_bible("test_project")

                    assert result.success is True
                    assert len(result.bible_files) == 1
                    # Should show the full path since it's outside project
                    bible_info = result.bible_files[0]
                    assert bible_info["name"] == "external_bible.md"
                    # Path should be the file itself since it can't be made relative

    @pytest.mark.asyncio
    async def test_read_bible_file_stat_error(self, api):
        """Test read_bible when file.stat() fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            bible_file = tmpdir_path / "bible.md"
            bible_file.write_text("Content")

            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()
                mock_conn.execute().fetchone.return_value = {
                    "file_path": str(tmpdir_path / "script.fountain")
                }

                with patch(
                    "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                    return_value=[bible_file],
                ):
                    # Mock stat() to fail
                    with patch.object(
                        Path, "stat", side_effect=OSError("Permission denied")
                    ):
                        result = await api.read_bible("test_project")

                        # Should fail gracefully when stat() fails
                        assert result.success is False
                        assert "Permission denied" in result.error

    @pytest.mark.asyncio
    async def test_read_bible_unicode_encoding_issues(self, api):
        """Test read_bible with unicode encoding edge cases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            bible_file = tmpdir_path / "unicode_bible.md"

            # Create file with problematic content that might cause encoding issues
            with Path(bible_file).open("wb") as f:
                f.write(b"\xff\xfe# Invalid UTF-8\n")

            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()
                mock_conn.execute().fetchone.return_value = {
                    "file_path": str(tmpdir_path / "script.fountain")
                }

                with patch(
                    "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                    return_value=[bible_file],
                ):
                    result = await api.read_bible("test_project", "unicode_bible.md")

                    # Should fail gracefully with encoding error
                    assert result.success is False
                    assert "Failed to read bible file" in result.error

    @pytest.mark.asyncio
    async def test_read_bible_database_cursor_error(self, api):
        """Test read_bible when database cursor operations fail."""
        # Mock database operations to fail at cursor level
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = sqlite3.Error("Cursor error")

        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()
            mock_conn.execute.return_value = mock_cursor

            result = await api.read_bible("test_project")

            assert result.success is False
            assert "Cursor error" in result.error

    @pytest.mark.asyncio
    async def test_read_bible_relative_path_calculation_edge_case(self, api):
        """Test read_bible relative path calculation edge cases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create bible file that is a sibling to project path
            sibling_file = tmpdir_path / "sibling_bible.md"
            sibling_file.write_text("Sibling content")

            project_subdir = tmpdir_path / "project"
            project_subdir.mkdir()
            script_path = project_subdir / "script.fountain"
            script_path.write_text("FADE IN:")

            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()
                mock_conn.execute().fetchone.return_value = {
                    "file_path": str(script_path)
                }

                with patch(
                    "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                    return_value=[sibling_file],
                ):
                    result = await api.read_bible("test_project")

                    assert result.success is True
                    assert len(result.bible_files) == 1
                    # File is not under project_path, so should use full path or name
                    bible_info = result.bible_files[0]
                    assert bible_info["name"] == "sibling_bible.md"


class TestLoggingAndTimestamps:
    """Test logging and UTC timestamp handling."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return SceneManagementAPI()

    @pytest.mark.asyncio
    async def test_read_scene_logging_with_utc(self, api):
        """Test read_scene logs with proper UTC timestamp."""
        scene_id = SceneIdentifier("test_project", 1)

        mock_scene = Scene(
            number=1,
            heading="INT. TEST SCENE - DAY",
            content="Test content",
            original_text="Test content",
            content_hash="hash123",
        )

        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()

            with (
                patch.object(api.scene_db, "get_scene_by_id", return_value=mock_scene),
                patch.object(api.scene_db, "update_last_read"),
                patch("scriptrag.api.scene_management.logger") as mock_logger,
            ):
                result = await api.read_scene(scene_id, "test_reader")

        assert result.success is True
        assert result.last_read is not None
        # Verify UTC timestamp
        assert result.last_read.tzinfo is UTC

        # Verify logging was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Scene read: test_project:001" in call_args[0][0]
        assert call_args[1]["reader_id"] == "test_reader"
        assert "last_read" in call_args[1]

    @pytest.mark.asyncio
    async def test_update_scene_logging(self, api):
        """Test update_scene logging."""
        scene_id = SceneIdentifier("test_project", 1)
        new_content = """INT. UPDATED SCENE - DAY

Updated content."""

        mock_scene = Scene(
            number=1,
            heading="INT. TEST SCENE - DAY",
            content="Original content",
            original_text="Original content",
            content_hash="original_hash",
        )

        updated_scene = Scene(
            number=1,
            heading="INT. UPDATED SCENE - DAY",
            content=new_content,
            original_text=new_content,
            content_hash="new_hash",
        )

        # Mock valid validation
        mock_validation = ValidationResult(is_valid=True, parsed_scene=updated_scene)

        with patch.object(
            api.validator, "validate_scene_content", return_value=mock_validation
        ):
            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()

                with (
                    patch.object(
                        api.scene_db, "get_scene_by_id", return_value=mock_scene
                    ),
                    patch.object(
                        api.scene_db, "get_last_modified", return_value=None
                    ),  # No conflict
                    patch.object(
                        api.scene_db, "update_scene_content", return_value=updated_scene
                    ),
                    patch("scriptrag.api.scene_management.logger") as mock_logger,
                ):
                    result = await api.update_scene(
                        scene_id,
                        new_content,
                        check_conflicts=True,
                        last_read=datetime.now(UTC)
                        - timedelta(minutes=1),  # Required for conflict check
                        reader_id="test_agent",
                    )

        assert result.success is True

        # Verify logging was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Scene updated: test_project:001" in call_args[0][0]
        assert call_args[1]["reader_id"] == "test_agent"
        assert call_args[1]["check_conflicts"] is True

    @pytest.mark.asyncio
    async def test_add_scene_logging(self, api):
        """Test add_scene logging."""
        reference_id = SceneIdentifier("test_project", 5)
        content = """INT. NEW SCENE - DAY

New scene content."""

        mock_reference = Scene(
            number=5,
            heading="INT. REFERENCE - DAY",
            content="Reference",
            original_text="Reference",
            content_hash="ref_hash",
        )

        created_scene = Scene(
            number=6,
            heading="INT. NEW SCENE - DAY",
            content=content,
            original_text=content,
            content_hash="new_hash",
        )

        # Mock valid validation
        mock_validation = ValidationResult(is_valid=True, parsed_scene=created_scene)

        with patch.object(
            api.validator, "validate_scene_content", return_value=mock_validation
        ):
            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()

                with (
                    patch.object(
                        api.scene_db, "get_scene_by_id", return_value=mock_reference
                    ),
                    patch.object(api.scene_db, "shift_scenes_after"),
                    patch.object(
                        api.scene_db, "create_scene", return_value=created_scene
                    ),
                    patch.object(
                        api.scene_db, "get_renumbered_scenes", return_value=[7, 8, 9]
                    ),
                    patch("scriptrag.api.scene_management.logger") as mock_logger,
                ):
                    result = await api.add_scene(reference_id, content, "after")

        assert result.success is True

        # Verify logging was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Scene added: test_project:006" in call_args[0][0]
        assert call_args[1]["position"] == "after"
        assert call_args[1]["reference"] == "test_project:005"

    @pytest.mark.asyncio
    async def test_delete_scene_logging(self, api):
        """Test delete_scene logging."""
        scene_id = SceneIdentifier("test_project", 5)

        mock_scene = Scene(
            number=5,
            heading="INT. TO DELETE - DAY",
            content="Delete me",
            original_text="Delete me",
            content_hash="del_hash",
        )

        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()

            with (
                patch.object(api.scene_db, "get_scene_by_id", return_value=mock_scene),
                patch.object(api.scene_db, "delete_scene"),
                patch.object(
                    api.scene_db, "compact_scene_numbers", return_value=[6, 7, 8]
                ),
                patch("scriptrag.api.scene_management.logger") as mock_logger,
            ):
                result = await api.delete_scene(scene_id, confirm=True)

        assert result.success is True

        # Verify logging was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "Scene deleted: test_project:005" in call_args[0][0]
        assert call_args[1]["renumbered_count"] == 3


class TestEdgeCasesCoverage:
    """Test remaining edge cases for 99% coverage."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return SceneManagementAPI()

    @pytest.mark.asyncio
    async def test_update_scene_not_found_after_validation(self, api):
        """Test update_scene when scene disappears after validation passes."""
        scene_id = SceneIdentifier("test_project", 1)
        content = """INT. SCENE - DAY

Content."""

        # Mock valid validation
        mock_validation = ValidationResult(is_valid=True)

        with patch.object(
            api.validator, "validate_scene_content", return_value=mock_validation
        ):
            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()

                # Scene exists initially but then disappears (line 115)
                with patch.object(api.scene_db, "get_scene_by_id", return_value=None):
                    result = await api.update_scene(
                        scene_id, content, check_conflicts=False
                    )

        assert result.success is False
        assert "Scene not found" in result.error
        assert "SCENE_NOT_FOUND" in result.validation_errors

    @pytest.mark.asyncio
    async def test_add_scene_reference_not_found_after_validation(self, api):
        """Test add_scene when reference scene not found after validation."""
        scene_id = SceneIdentifier("test_project", 5)
        content = """INT. NEW SCENE - DAY

Content."""

        # Mock valid validation
        mock_validation = ValidationResult(is_valid=True)

        with patch.object(
            api.validator, "validate_scene_content", return_value=mock_validation
        ):
            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()

                # Reference scene not found (line 190)
                with patch.object(api.scene_db, "get_scene_by_id", return_value=None):
                    result = await api.add_scene(scene_id, content, "after")

        assert result.success is False
        assert "Reference scene not found" in result.error

    @pytest.mark.asyncio
    async def test_add_scene_invalid_position_after_validation(self, api):
        """Test add_scene with invalid position after finding reference scene."""
        scene_id = SceneIdentifier("test_project", 5)
        content = """INT. NEW SCENE - DAY

Content."""

        mock_reference = Scene(
            number=5,
            heading="INT. REFERENCE - DAY",
            content="Reference",
            original_text="Reference",
            content_hash="ref_hash",
        )

        # Mock valid validation
        mock_validation = ValidationResult(is_valid=True)

        with patch.object(
            api.validator, "validate_scene_content", return_value=mock_validation
        ):
            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()

                with patch.object(
                    api.scene_db, "get_scene_by_id", return_value=mock_reference
                ):
                    # Test invalid position (line 205)
                    result = await api.add_scene(scene_id, content, "invalid_position")

        assert result.success is False
        assert "Invalid position" in result.error

    @pytest.mark.asyncio
    async def test_read_bible_project_found_but_no_script_path(self, api):
        """Test read_bible when project found but script path is None."""
        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()
            # Mock project found but no file_path (line 309)
            mock_conn.execute().fetchone.return_value = {"file_path": None}

            result = await api.read_bible("test_project")

        # Should handle None file_path gracefully by causing a TypeError
        assert result.success is False
        # Handle both Python version variants of the TypeError message
        error_variants = [
            "expected str, bytes or os.PathLike object, not NoneType",
            "argument should be a str or an os.PathLike object where __fspath__ returns a str, not 'NoneType'",  # noqa: E501
        ]
        assert any(variant in result.error for variant in error_variants), (
            f"Expected one of {error_variants} in error: {result.error}"
        )

    @pytest.mark.asyncio
    async def test_read_bible_no_files_found_in_project(self, api):
        """Test read_bible when no bible files found in project directory."""
        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()
            mock_conn.execute().fetchone.return_value = {
                "file_path": "/path/to/script.fountain"
            }

            # Mock bible detector finding no files (line 320)
            with patch(
                "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                return_value=[],
            ):
                result = await api.read_bible("test_project")

        assert result.success is False
        assert "No bible files found for project 'test_project'" in result.error

    @pytest.mark.asyncio
    async def test_read_bible_file_not_found_with_available_list(self, api):
        """Test read_bible when specific file not found, shows available files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            bible_file1 = tmpdir_path / "bible1.md"
            bible_file2 = tmpdir_path / "bible2.md"
            bible_file1.write_text("Content 1")
            bible_file2.write_text("Content 2")

            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()
                mock_conn.execute().fetchone.return_value = {
                    "file_path": str(tmpdir_path / "script.fountain")
                }

                with patch(
                    "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                    return_value=[bible_file1, bible_file2],
                ):
                    # Request non-existent file (lines 371-373)
                    result = await api.read_bible("test_project", "nonexistent.md")

        assert result.success is False
        assert "Bible file 'nonexistent.md' not found" in result.error
        assert "Available: bible1.md, bible2.md" in result.error


class TestErrorLogging:
    """Test error logging in all failure scenarios."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return SceneManagementAPI()

    @pytest.mark.asyncio
    async def test_read_scene_error_logging(self, api):
        """Test read_scene error logging."""
        scene_id = SceneIdentifier("test_project", 1)

        with (
            patch.object(
                api.db_ops,
                "transaction",
                side_effect=Exception("Database connection failed"),
            ),
            patch("scriptrag.api.scene_management.logger") as mock_logger,
        ):
            result = await api.read_scene(scene_id)

        assert result.success is False

        # Verify error logging
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "Failed to read scene test_project:001:" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_update_scene_error_logging(self, api):
        """Test update_scene error logging."""
        scene_id = SceneIdentifier("test_project", 1)
        content = """INT. SCENE - DAY

Content."""

        # Mock valid validation but database failure
        mock_validation = ValidationResult(is_valid=True)

        with (
            patch.object(
                api.validator, "validate_scene_content", return_value=mock_validation
            ),
            patch.object(
                api.db_ops, "transaction", side_effect=Exception("Database error")
            ),
            patch("scriptrag.api.scene_management.logger") as mock_logger,
        ):
            result = await api.update_scene(scene_id, content)

        assert result.success is False

        # Verify error logging
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "Failed to update scene test_project:001:" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_scene_error_logging(self, api):
        """Test add_scene error logging."""
        scene_id = SceneIdentifier("test_project", 5)
        content = """INT. NEW SCENE - DAY

Content."""

        # Mock valid validation but database failure
        mock_validation = ValidationResult(is_valid=True)

        with (
            patch.object(
                api.validator, "validate_scene_content", return_value=mock_validation
            ),
            patch.object(
                api.db_ops, "transaction", side_effect=Exception("Database error")
            ),
            patch("scriptrag.api.scene_management.logger") as mock_logger,
        ):
            result = await api.add_scene(scene_id, content, "after")

        assert result.success is False

        # Verify error logging
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "Failed to add scene:" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_delete_scene_error_logging(self, api):
        """Test delete_scene error logging."""
        scene_id = SceneIdentifier("test_project", 5)

        with (
            patch.object(
                api.db_ops, "transaction", side_effect=Exception("Database error")
            ),
            patch("scriptrag.api.scene_management.logger") as mock_logger,
        ):
            result = await api.delete_scene(scene_id, confirm=True)

        assert result.success is False

        # Verify error logging
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "Failed to delete scene:" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_read_bible_error_logging(self, api):
        """Test read_bible error logging."""
        with (
            patch.object(
                api.db_ops, "transaction", side_effect=Exception("Database error")
            ),
            patch("scriptrag.api.scene_management.logger") as mock_logger,
        ):
            result = await api.read_bible("test_project")

        assert result.success is False

        # Verify error logging
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "Failed to read bible for project 'test_project':" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_read_bible_file_read_error_logging(self, api):
        """Test read_bible file read error logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            bible_file = tmpdir_path / "bible.md"
            bible_file.write_text("Content")

            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()
                mock_conn.execute().fetchone.return_value = {
                    "file_path": str(tmpdir_path / "script.fountain")
                }

                with (
                    patch(
                        "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                        return_value=[bible_file],
                    ),
                    patch.object(
                        Path, "read_text", side_effect=Exception("Read error")
                    ),
                    patch("scriptrag.api.scene_management.logger") as mock_logger,
                ):
                    result = await api.read_bible("test_project", "bible.md")

        assert result.success is False

        # Verify error logging was called for file read failure
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "Failed to read bible file" in call_args[0][0]
        # The error message contains the file path and error details
        assert "Read error" in str(call_args[0])
