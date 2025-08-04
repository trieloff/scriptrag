"""Tests for database initialization with settings integration."""

import sqlite3
from unittest.mock import MagicMock, patch

from scriptrag.api import DatabaseInitializer
from scriptrag.config import ScriptRAGSettings


class TestDatabaseSettingsIntegration:
    """Test database initialization with settings."""

    def test_database_init_uses_settings_timeout(self, tmp_path):
        """Test that database initialization uses timeout from settings."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            database_timeout=5.0,
        )

        initializer = DatabaseInitializer()

        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            initializer.initialize_database(settings=settings)

            # Check that connect was called with correct timeout
            mock_connect.assert_called_once_with(str(tmp_path / "test.db"), timeout=5.0)

    def test_database_init_configures_pragmas(self, tmp_path):
        """Test that database initialization configures pragmas from settings."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            database_journal_mode="DELETE",
            database_synchronous="FULL",
            database_cache_size=-4000,
            database_temp_store="FILE",
            database_foreign_keys=True,
        )

        initializer = DatabaseInitializer()

        # Mock the SQL file reading
        with patch.object(initializer, "_read_sql_file") as mock_read:
            mock_read.return_value = "CREATE TABLE test (id INTEGER PRIMARY KEY);"

            # Initialize database
            db_path = initializer.initialize_database(settings=settings)

            # Connect and check pragmas
            conn = sqlite3.connect(str(db_path))
            try:
                # Check journal mode
                result = conn.execute("PRAGMA journal_mode").fetchone()
                assert result[0].upper() == "DELETE"

                # Check synchronous mode
                result = conn.execute("PRAGMA synchronous").fetchone()
                assert result[0] == 2  # FULL = 2

                # Check cache size
                result = conn.execute("PRAGMA cache_size").fetchone()
                assert result[0] == -4000

                # Check temp store
                result = conn.execute("PRAGMA temp_store").fetchone()
                assert result[0] == 1  # FILE = 1

                # Check foreign keys
                result = conn.execute("PRAGMA foreign_keys").fetchone()
                assert result[0] == 1  # ON = 1
            finally:
                conn.close()

    def test_database_init_with_wal_mode(self, tmp_path):
        """Test database initialization with WAL mode."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            database_wal_mode=True,
            database_journal_mode="WAL",
        )

        initializer = DatabaseInitializer()

        # Mock the SQL file reading
        with patch.object(initializer, "_read_sql_file") as mock_read:
            mock_read.return_value = "CREATE TABLE test (id INTEGER PRIMARY KEY);"

            # Initialize database
            db_path = initializer.initialize_database(settings=settings)

            # Connect and check WAL mode
            conn = sqlite3.connect(str(db_path))
            try:
                result = conn.execute("PRAGMA journal_mode").fetchone()
                assert result[0].upper() == "WAL"
            finally:
                conn.close()

    def test_database_init_without_foreign_keys(self, tmp_path):
        """Test database initialization without foreign key constraints."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            database_foreign_keys=False,
        )

        initializer = DatabaseInitializer()

        # Mock the SQL file reading
        with patch.object(initializer, "_read_sql_file") as mock_read:
            mock_read.return_value = "CREATE TABLE test (id INTEGER PRIMARY KEY);"

            # Initialize database
            db_path = initializer.initialize_database(settings=settings)

            # Connect and check foreign keys are off
            conn = sqlite3.connect(str(db_path))
            try:
                result = conn.execute("PRAGMA foreign_keys").fetchone()
                assert result[0] == 0  # OFF = 0
            finally:
                conn.close()

    def test_database_init_cli_override(self, tmp_path):
        """Test that CLI path overrides settings path."""
        settings = ScriptRAGSettings(database_path=tmp_path / "settings.db")

        cli_path = tmp_path / "cli.db"

        initializer = DatabaseInitializer()

        # Mock the SQL file reading
        with patch.object(initializer, "_read_sql_file") as mock_read:
            mock_read.return_value = "CREATE TABLE test (id INTEGER PRIMARY KEY);"

            # Initialize with CLI path
            db_path = initializer.initialize_database(
                db_path=cli_path, settings=settings
            )

            # Should use CLI path, not settings path
            assert db_path == cli_path
            assert cli_path.exists()
            assert not (tmp_path / "settings.db").exists()

    def test_database_init_logging(self, tmp_path, caplog):
        """Test that database initialization logs configuration."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            database_journal_mode="WAL",
            database_synchronous="NORMAL",
            database_cache_size=-2000,
            database_foreign_keys=True,
        )

        initializer = DatabaseInitializer()

        # Mock the SQL file reading
        with patch.object(initializer, "_read_sql_file") as mock_read:
            mock_read.return_value = "CREATE TABLE test (id INTEGER PRIMARY KEY);"

            # Initialize database with debug logging
            with caplog.at_level("DEBUG"):
                initializer.initialize_database(settings=settings)

            # Check that configuration was logged
            assert any(
                "Database connection configured" in record.message
                for record in caplog.records
            )
            assert any(
                "journal_mode" in str(record.__dict__) for record in caplog.records
            )
