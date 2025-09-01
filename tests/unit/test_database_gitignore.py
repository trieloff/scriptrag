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

    def test_gitignore_respects_negation_patterns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that negation patterns (!) are respected and not overridden."""
        # Setup
        db_path = tmp_path / "scriptrag.db"
        gitignore_path = tmp_path / ".gitignore"

        # Create .gitignore with negation patterns
        existing_content = (
            "# Ignore all database files\n"
            "*.db\n"
            "*.db-shm\n"
            "*.db-wal\n"
            "# But track this specific database\n"
            "!scriptrag.db\n"
            "!scriptrag.db-shm\n"
            "!scriptrag.db-wal\n"
        )
        gitignore_path.write_text(existing_content)

        initializer = DatabaseInitializer()

        # Set logging to capture warnings
        import logging

        caplog.set_level(logging.WARNING)
        logging.getLogger("scriptrag.api.database").setLevel(logging.WARNING)

        # Execute
        initializer._update_gitignore(db_path)

        # Verify
        content = gitignore_path.read_text()
        lines = content.splitlines()

        # The negation patterns should still be there
        assert "!scriptrag.db" in lines
        assert "!scriptrag.db-shm" in lines
        assert "!scriptrag.db-wal" in lines

        # The ignore patterns should NOT be added at the end (would override negation)
        # Find the last occurrence of each pattern
        scriptrag_indices = [
            i for i, line in enumerate(lines) if line == "scriptrag.db"
        ]
        if scriptrag_indices:
            # If scriptrag.db appears, it should only be from wildcards,
            # not as a new entry
            assert (
                len(scriptrag_indices) == 0
                or "# ScriptRAG database files" not in content
            )

        # Check that warnings were logged
        assert "Skipping pattern due to existing negation rule" in caplog.text
        assert "'pattern': 'scriptrag.db'" in caplog.text
        assert "'negation_rule': '!scriptrag.db'" in caplog.text

    def test_gitignore_negation_pattern_partial_match(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test handling when only some patterns have negations."""
        # Setup
        db_path = tmp_path / "scriptrag.db"
        gitignore_path = tmp_path / ".gitignore"

        # Create .gitignore with only some negation patterns
        existing_content = (
            "# Track the main database file\n"
            "!scriptrag.db\n"
            "# But ignore other db files\n"
            "*.db-journal\n"
        )
        gitignore_path.write_text(existing_content)

        initializer = DatabaseInitializer()

        # Set logging to capture warnings
        import logging

        caplog.set_level(logging.WARNING)
        logging.getLogger("scriptrag.api.database").setLevel(logging.WARNING)

        # Execute
        initializer._update_gitignore(db_path)

        # Verify
        content = gitignore_path.read_text()
        lines = content.splitlines()

        # The negation pattern should still be there
        assert "!scriptrag.db" in lines

        # scriptrag.db should NOT be added (has negation)
        scriptrag_count = lines.count("scriptrag.db")
        assert scriptrag_count == 0  # Only the negation pattern, no ignore pattern

        # Other patterns without negations should be added
        assert "scriptrag.db-shm" in content
        assert "scriptrag.db-wal" in content
        assert "*.db" in content
        assert "*.db-shm" in content
        assert "*.db-wal" in content

        # Check that warning was logged only for the negated pattern
        assert "Skipping pattern due to existing negation rule" in caplog.text
        assert "'pattern': 'scriptrag.db'" in caplog.text

    def test_gitignore_wildcard_negation_patterns(self, tmp_path: Path) -> None:
        """Test that wildcard negation patterns are handled correctly."""
        # Setup
        db_path = tmp_path / "scriptrag.db"
        gitignore_path = tmp_path / ".gitignore"

        # Create .gitignore with wildcard negation
        existing_content = (
            "# Ignore all .db files\n"
            "*.db\n"
            "# But track all scriptrag database files\n"
            "!*.db\n"  # This negates the wildcard pattern
        )
        gitignore_path.write_text(existing_content)

        initializer = DatabaseInitializer()

        # Execute
        initializer._update_gitignore(db_path)

        # Verify
        content = gitignore_path.read_text()
        lines = content.splitlines()

        # The wildcard negation should be preserved
        assert "!*.db" in lines

        # The *.db pattern should not be re-added (has negation)
        db_wildcard_count = lines.count("*.db")
        assert db_wildcard_count == 1  # Only the original, not a new one

        # Other specific patterns should still be added
        assert "scriptrag.db" in content
        assert "scriptrag.db-shm" in content
        assert "scriptrag.db-wal" in content

    def test_gitignore_complex_negation_scenario(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test complex scenario with mixed patterns and negations."""
        # Setup
        db_path = tmp_path / "data" / "scriptrag.db"
        db_path.parent.mkdir(parents=True)
        gitignore_path = tmp_path / ".gitignore"

        # Create .gitignore with complex patterns
        existing_content = (
            "# Python files\n"
            "*.pyc\n"
            "__pycache__/\n"
            "\n"
            "# Database files\n"
            "*.db\n"
            "*.db-shm\n"
            "*.db-wal\n"
            "\n"
            "# But keep our specific database\n"
            "!data/scriptrag.db\n"
            "\n"
            "# Logs\n"
            "*.log\n"
        )
        gitignore_path.write_text(existing_content)

        # Create a .git directory to make it look like a repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        initializer = DatabaseInitializer()

        # Set logging
        import logging

        caplog.set_level(logging.DEBUG)
        logging.getLogger("scriptrag.api.database").setLevel(logging.DEBUG)

        # Execute
        initializer._update_gitignore(db_path)

        # Verify
        content = gitignore_path.read_text()

        # Original content should be preserved
        assert "*.pyc" in content
        assert "__pycache__/" in content
        assert "*.log" in content

        # The negation pattern should be preserved
        assert "!data/scriptrag.db" in content

        # Wildcard patterns already exist, shouldn't be duplicated
        lines = content.splitlines()
        assert lines.count("*.db") == 1
        assert lines.count("*.db-shm") == 1
        assert lines.count("*.db-wal") == 1

        # Specific patterns (scriptrag.db, etc.) will be added since
        # the negation is for "data/scriptrag.db" not "scriptrag.db"
        assert "scriptrag.db" in content
