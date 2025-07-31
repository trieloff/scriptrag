"""Tests for database management CLI commands."""

import sqlite3
from unittest.mock import MagicMock, Mock, patch

import pytest
from typer.testing import CliRunner

from scriptrag.cli import app


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_settings():
    """Create mock settings for CLI tests."""
    mock_database_settings = Mock()
    mock_database_settings.path = "/test/db.sqlite"

    mock_logging_settings = Mock()
    mock_logging_settings.file_path = None

    mock_paths_settings = Mock()
    mock_paths_settings.logs_dir = "/test/logs"

    mock_settings = Mock()
    mock_settings.database = mock_database_settings
    mock_settings.logging = mock_logging_settings
    mock_settings.paths = mock_paths_settings
    mock_settings.get_log_file_path.return_value = None
    mock_settings.get_database_path.return_value = "/test/db.sqlite"

    return mock_settings


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test.db"


class TestDbInit:
    """Test database initialization command."""

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.cli.get_logger")
    @patch("scriptrag.database.migrations.initialize_database")
    def test_db_init_success(
        self,
        mock_initialize_database,
        mock_get_logger,
        mock_get_settings,
        cli_runner,
        mock_settings,
        temp_db_path,
    ):
        """Test successful database initialization."""
        mock_get_settings.return_value = mock_settings
        mock_settings.database.path = str(temp_db_path)
        mock_initialize_database.return_value = True
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        result = cli_runner.invoke(app, ["db", "init"])

        assert result.exit_code == 0
        assert "Database initialized successfully" in result.stdout
        mock_initialize_database.assert_called_once_with(temp_db_path)
        mock_logger.info.assert_called_once()

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.cli.get_logger")
    def test_db_init_already_exists(
        self,
        mock_get_logger,
        mock_get_settings,
        cli_runner,
        mock_settings,
        temp_db_path,
    ):
        """Test database initialization when database already exists."""
        mock_get_settings.return_value = mock_settings
        mock_settings.database.path = str(temp_db_path)
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Create the database file
        temp_db_path.parent.mkdir(parents=True, exist_ok=True)
        temp_db_path.touch()

        result = cli_runner.invoke(app, ["db", "init"])

        assert result.exit_code == 1
        assert "Database already exists" in result.stdout
        assert "Use --force to reinitialize" in result.stdout

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.cli.get_logger")
    @patch("scriptrag.database.migrations.initialize_database")
    def test_db_init_force(
        self,
        mock_initialize_database,
        mock_get_logger,
        mock_get_settings,
        cli_runner,
        mock_settings,
        temp_db_path,
    ):
        """Test forced database initialization."""
        mock_get_settings.return_value = mock_settings
        mock_settings.database.path = str(temp_db_path)
        mock_initialize_database.return_value = True
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Create the database file
        temp_db_path.parent.mkdir(parents=True, exist_ok=True)
        temp_db_path.touch()

        result = cli_runner.invoke(app, ["db", "init", "--force"])

        assert result.exit_code == 0
        assert "Database initialized successfully" in result.stdout
        mock_initialize_database.assert_called_once_with(temp_db_path)

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.cli.get_logger")
    @patch("scriptrag.database.migrations.initialize_database")
    def test_db_init_custom_path(
        self,
        mock_initialize_database,
        mock_get_logger,
        mock_get_settings,
        cli_runner,
        mock_settings,
        tmp_path,
    ):
        """Test database initialization with custom path."""
        mock_get_settings.return_value = mock_settings
        mock_initialize_database.return_value = True
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        custom_db_path = tmp_path / "custom" / "database.db"

        result = cli_runner.invoke(app, ["db", "init", "--path", str(custom_db_path)])

        assert result.exit_code == 0
        assert "Database initialized successfully" in result.stdout
        mock_initialize_database.assert_called_once_with(custom_db_path)

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.cli.get_logger")
    @patch("scriptrag.database.migrations.initialize_database")
    def test_db_init_failure(
        self,
        mock_initialize_database,
        mock_get_logger,
        mock_get_settings,
        cli_runner,
        mock_settings,
        temp_db_path,
    ):
        """Test database initialization failure."""
        mock_get_settings.return_value = mock_settings
        mock_settings.database.path = str(temp_db_path)
        mock_initialize_database.return_value = False
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        result = cli_runner.invoke(app, ["db", "init"])

        assert result.exit_code == 1
        assert "Database initialization failed" in result.stdout
        mock_logger.error.assert_called()

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.cli.get_logger")
    @patch("scriptrag.database.migrations.initialize_database")
    def test_db_init_exception(
        self,
        mock_initialize_database,
        mock_get_logger,
        mock_get_settings,
        cli_runner,
        mock_settings,
        temp_db_path,
    ):
        """Test database initialization with exception."""
        mock_get_settings.return_value = mock_settings
        mock_settings.database.path = str(temp_db_path)
        mock_initialize_database.side_effect = Exception("Test error")
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        result = cli_runner.invoke(app, ["db", "init"])

        assert result.exit_code == 1
        assert "Error initializing database" in result.stdout
        assert "Test error" in result.stdout


class TestDbWipe:
    """Test database wipe command."""

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.cli.get_logger")
    def test_db_wipe_database_not_exists(
        self,
        mock_get_logger,
        mock_get_settings,
        cli_runner,
        mock_settings,
        temp_db_path,
    ):
        """Test wiping non-existent database."""
        mock_get_settings.return_value = mock_settings
        mock_settings.database.path = str(temp_db_path)
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        result = cli_runner.invoke(app, ["db", "wipe"])

        assert result.exit_code == 1
        assert "Database does not exist" in result.stdout

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.cli.get_logger")
    def test_db_wipe_cancelled(
        self,
        mock_get_logger,
        mock_get_settings,
        cli_runner,
        mock_settings,
        temp_db_path,
    ):
        """Test cancelling database wipe."""
        mock_get_settings.return_value = mock_settings
        mock_settings.database.path = str(temp_db_path)
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Create the database file
        temp_db_path.parent.mkdir(parents=True, exist_ok=True)
        temp_db_path.touch()

        # User responds "n" to confirmation
        result = cli_runner.invoke(app, ["db", "wipe"], input="n\n")

        assert result.exit_code == 0
        assert "Operation cancelled" in result.stdout

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.cli.get_logger")
    def test_db_wipe_success_with_confirmation(
        self,
        mock_get_logger,
        mock_get_settings,
        cli_runner,
        mock_settings,
        temp_db_path,
    ):
        """Test successful database wipe with confirmation."""
        mock_get_settings.return_value = mock_settings
        mock_settings.database.path = str(temp_db_path)
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Create a simple database with a table
        temp_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(temp_db_path) as conn:
            conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
            conn.commit()

        # User responds "y" to confirmation
        result = cli_runner.invoke(app, ["db", "wipe"], input="y\n")

        assert result.exit_code == 0
        assert "Database wiped successfully" in result.stdout
        assert "Dropped table: test_table" in result.stdout

        # Verify table was dropped
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='test_table'"
            )
            assert cursor.fetchone() is None

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.cli.get_logger")
    def test_db_wipe_force(
        self,
        mock_get_logger,
        mock_get_settings,
        cli_runner,
        mock_settings,
        temp_db_path,
    ):
        """Test database wipe with --force flag."""
        mock_get_settings.return_value = mock_settings
        mock_settings.database.path = str(temp_db_path)
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Create a simple database with tables
        temp_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(temp_db_path) as conn:
            conn.execute("CREATE TABLE test_table1 (id INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE test_table2 (id INTEGER PRIMARY KEY)")
            conn.commit()

        result = cli_runner.invoke(app, ["db", "wipe", "--force"])

        assert result.exit_code == 0
        assert "Database wiped successfully" in result.stdout
        assert "Dropping 2 tables" in result.stdout

        # Verify tables were dropped
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            assert cursor.fetchone()[0] == 0

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.cli.get_logger")
    def test_db_wipe_empty_database(
        self,
        mock_get_logger,
        mock_get_settings,
        cli_runner,
        mock_settings,
        temp_db_path,
    ):
        """Test wiping already empty database."""
        mock_get_settings.return_value = mock_settings
        mock_settings.database.path = str(temp_db_path)
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Create an empty database
        temp_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(temp_db_path) as conn:
            conn.execute("PRAGMA user_version=0")

        result = cli_runner.invoke(app, ["db", "wipe", "--force"])

        assert result.exit_code == 0
        assert "Database is already empty" in result.stdout

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.cli.get_logger")
    def test_db_wipe_custom_path(
        self, mock_get_logger, mock_get_settings, cli_runner, mock_settings, tmp_path
    ):
        """Test database wipe with custom path."""
        mock_get_settings.return_value = mock_settings
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        custom_db_path = tmp_path / "custom.db"

        # Create a simple database with a table
        custom_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(custom_db_path) as conn:
            conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
            conn.commit()

        result = cli_runner.invoke(
            app, ["db", "wipe", "--path", str(custom_db_path), "--force"]
        )

        assert result.exit_code == 0
        assert "Database wiped successfully" in result.stdout

    @patch("scriptrag.config.settings.get_settings")
    @patch("scriptrag.cli.get_logger")
    def test_db_wipe_sql_injection_protection(
        self,
        mock_get_logger,
        mock_get_settings,
        cli_runner,
        mock_settings,
        temp_db_path,
    ):
        """Test SQL injection protection in database wipe."""
        mock_get_settings.return_value = mock_settings
        mock_settings.database.path = str(temp_db_path)
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Create a database with tables that have potentially malicious names
        temp_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(temp_db_path) as conn:
            # Create a normal table
            conn.execute("CREATE TABLE normal_table (id INTEGER PRIMARY KEY)")

            # Create tables with special characters that could be SQL injection attempts
            # SQLite allows these names when properly quoted
            conn.execute(
                'CREATE TABLE "table; DROP TABLE users; --" (id INTEGER PRIMARY KEY)'
            )
            conn.execute('CREATE TABLE "table`with`backticks" (id INTEGER PRIMARY KEY)')
            conn.execute("CREATE TABLE \"table'with'quotes\" (id INTEGER PRIMARY KEY)")
            conn.commit()

        result = cli_runner.invoke(app, ["db", "wipe", "--force"])

        assert result.exit_code == 0
        assert "Database wiped successfully" in result.stdout
        assert "Dropped table: normal_table" in result.stdout

        # These tables should be skipped due to invalid names
        assert (
            "Skipped invalid table name: table; DROP TABLE users; --" in result.stdout
        )
        assert "Skipped invalid table name: table`with`backticks" in result.stdout
        assert "Skipped invalid table name: table'with'quotes" in result.stdout

        # Verify only the normal table was dropped
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            remaining_tables = [row[0] for row in cursor.fetchall()]
            # The tables with special characters should still exist
            assert len(remaining_tables) == 3
            assert "normal_table" not in remaining_tables
