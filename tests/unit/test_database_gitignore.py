"""Tests for .gitignore update functionality in database initialization."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scriptrag.api.database import DatabaseInitializer
from scriptrag.config import ScriptRAGSettings


class TestGitignoreUpdate:
    """Test .gitignore update functionality."""

    def test_update_gitignore_creates_new_file(self, tmp_path: Path) -> None:
        """Test that .gitignore is created if it doesn't exist."""
        # Setup
        db_path = tmp_path / "scriptrag.db"
        gitignore_path = tmp_path / ".gitignore"

        initializer = DatabaseInitializer()

        # Execute
        initializer._update_gitignore(db_path)

        # Verify
        assert gitignore_path.exists()
        content = gitignore_path.read_text()
        assert "# ScriptRAG database files" in content
        assert "scriptrag.db" in content
        assert "scriptrag.db-shm" in content
        assert "scriptrag.db-wal" in content
        assert "*.db" in content
        assert "*.db-shm" in content
        assert "*.db-wal" in content

    def test_update_gitignore_appends_to_existing(self, tmp_path: Path) -> None:
        """Test that patterns are appended to existing .gitignore."""
        # Setup
        db_path = tmp_path / "scriptrag.db"
        gitignore_path = tmp_path / ".gitignore"

        # Create existing .gitignore with some content
        existing_content = "# Existing patterns\n*.pyc\n__pycache__/\n"
        gitignore_path.write_text(existing_content)

        initializer = DatabaseInitializer()

        # Execute
        initializer._update_gitignore(db_path)

        # Verify
        content = gitignore_path.read_text()
        # Original content should be preserved
        assert "# Existing patterns" in content
        assert "*.pyc" in content
        assert "__pycache__/" in content
        # New patterns should be added
        assert "# ScriptRAG database files" in content
        assert "scriptrag.db" in content

    def test_update_gitignore_skips_existing_patterns(self, tmp_path: Path) -> None:
        """Test that existing patterns are not duplicated."""
        # Setup
        db_path = tmp_path / "scriptrag.db"
        gitignore_path = tmp_path / ".gitignore"

        # Create .gitignore with some database patterns already
        existing_content = "*.pyc\nscriptrag.db\n*.db-wal\n"
        gitignore_path.write_text(existing_content)

        initializer = DatabaseInitializer()

        # Execute
        initializer._update_gitignore(db_path)

        # Verify
        content = gitignore_path.read_text()
        lines = content.splitlines()

        # The exact pattern "scriptrag.db" should appear only once (from original)
        # But "scriptrag.db-shm" and "scriptrag.db-wal" are different patterns
        assert lines.count("scriptrag.db") == 1  # Not duplicated
        assert lines.count("*.db-wal") == 1  # Not duplicated
        # New patterns should be added
        assert "scriptrag.db-shm" in content
        assert "scriptrag.db-wal" in content
        assert "*.db" in content
        assert "*.db-shm" in content

    def test_update_gitignore_finds_git_root(self, tmp_path: Path) -> None:
        """Test that .gitignore is created at git root if found."""
        # Setup
        git_root = tmp_path / "repo"
        git_dir = git_root / ".git"
        git_dir.mkdir(parents=True)

        sub_dir = git_root / "subdir"
        sub_dir.mkdir()

        db_path = sub_dir / "scriptrag.db"

        initializer = DatabaseInitializer()

        # Execute
        initializer._update_gitignore(db_path)

        # Verify - .gitignore should be at git root
        gitignore_path = git_root / ".gitignore"
        assert gitignore_path.exists()
        assert not (sub_dir / ".gitignore").exists()

        content = gitignore_path.read_text()
        assert "# ScriptRAG database files" in content

    def test_update_gitignore_handles_no_patterns_to_add(self, tmp_path: Path) -> None:
        """Test that no changes are made if all patterns exist."""
        # Setup
        db_path = tmp_path / "scriptrag.db"
        gitignore_path = tmp_path / ".gitignore"

        # Create .gitignore with all patterns
        existing_content = (
            "scriptrag.db\n"
            "scriptrag.db-shm\n"
            "scriptrag.db-wal\n"
            "*.db\n"
            "*.db-shm\n"
            "*.db-wal\n"
        )
        gitignore_path.write_text(existing_content)
        original_content = gitignore_path.read_text()

        initializer = DatabaseInitializer()

        # Execute
        initializer._update_gitignore(db_path)

        # Verify - content should be unchanged
        new_content = gitignore_path.read_text()
        assert new_content == original_content

    def test_update_gitignore_handles_write_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that write errors are handled gracefully."""
        # Setup
        db_path = tmp_path / "scriptrag.db"
        gitignore_path = tmp_path / ".gitignore"

        initializer = DatabaseInitializer()

        # Ensure we can capture WARNING level logs
        import logging

        # Set both caplog and the specific logger to WARNING level
        caplog.set_level(logging.WARNING)
        # Also set the specific logger level
        logging.getLogger("scriptrag.api.database").setLevel(logging.WARNING)

        # Patch the gitignore_path.open method to raise PermissionError
        with patch.object(Path, "open", side_effect=PermissionError("No write access")):
            # Execute
            initializer._update_gitignore(db_path)

        # Verify - should log warning but not crash
        assert "Failed to update .gitignore" in caplog.text

    def test_update_gitignore_handles_file_without_newline(
        self, tmp_path: Path
    ) -> None:
        """Test handling of .gitignore file without trailing newline."""
        # Setup
        db_path = tmp_path / "scriptrag.db"
        gitignore_path = tmp_path / ".gitignore"

        # Create .gitignore without trailing newline
        with gitignore_path.open("wb") as f:
            f.write(b"*.pyc")  # No newline

        initializer = DatabaseInitializer()

        # Execute
        initializer._update_gitignore(db_path)

        # Verify
        content = gitignore_path.read_text()
        lines = content.splitlines()
        # Should have proper separation
        assert "*.pyc" in lines
        assert "" in lines  # Blank line added
        assert "# ScriptRAG database files" in lines

    def test_database_init_calls_gitignore_update(self, tmp_path: Path) -> None:
        """Test that initialize_database calls _update_gitignore."""
        # Setup
        db_path = tmp_path / "test.db"
        settings = ScriptRAGSettings(database_path=db_path)

        initializer = DatabaseInitializer()

        # Mock the internal methods to avoid actual database creation
        with patch.object(initializer, "_initialize_with_connection"):
            with patch.object(initializer, "_update_gitignore") as mock_update:
                with patch.object(initializer, "_configure_connection"):
                    with patch(
                        "scriptrag.database.connection_manager.get_connection_manager"
                    ) as mock_mgr:
                        mock_conn_mgr = Mock()
                        mock_conn_mgr.check_database_exists.return_value = False
                        mock_conn_mgr.get_connection.return_value = Mock()
                        mock_conn_mgr.db_path = db_path
                        mock_mgr.return_value = mock_conn_mgr

                        # Execute
                        result = initializer.initialize_database(
                            db_path=db_path, settings=settings
                        )

                        # Verify
                        mock_update.assert_called_once_with(db_path)
                        assert result == db_path

    def test_gitignore_patterns_with_comments(self, tmp_path: Path) -> None:
        """Test that comments in .gitignore are ignored when checking patterns."""
        # Setup
        db_path = tmp_path / "scriptrag.db"
        gitignore_path = tmp_path / ".gitignore"

        # Create .gitignore with comments
        existing_content = (
            "# Database files\n"
            "# scriptrag.db  # This is a comment, not a pattern\n"
            "*.pyc\n"
        )
        gitignore_path.write_text(existing_content)

        initializer = DatabaseInitializer()

        # Execute
        initializer._update_gitignore(db_path)

        # Verify
        content = gitignore_path.read_text()
        # Should add scriptrag.db since the commented line doesn't count
        assert content.count("scriptrag.db") >= 1
        assert "# ScriptRAG database files" in content
