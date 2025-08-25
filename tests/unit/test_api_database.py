"""Unit tests for database API module."""

from unittest.mock import Mock, patch

import pytest

from scriptrag.api.database import DatabaseInitializer


class MockConnection:
    """Mock database connection for testing."""

    def __init__(self):
        """Initialize mock connection."""
        self.executed = []
        self.executed_scripts = []
        self.committed = False
        self.closed = False

    def execute(self, sql):
        """Mock execute method."""
        self.executed.append(sql)

    def executescript(self, sql):
        """Mock executescript method."""
        self.executed_scripts.append(sql)

    def commit(self):
        """Mock commit method."""
        self.committed = True

    def close(self):
        """Mock close method."""
        self.closed = True


class TestDatabaseInitializer:
    """Test DatabaseInitializer class."""

    def test_init_default_sql_dir(self):
        """Test that default SQL directory is set correctly."""
        initializer = DatabaseInitializer()
        assert initializer.sql_dir.name == "sql"
        assert initializer.sql_dir.parent.name == "database"

    def test_init_custom_sql_dir(self, tmp_path):
        """Test that custom SQL directory can be set."""
        custom_dir = tmp_path / "custom_sql"
        custom_dir.mkdir()
        initializer = DatabaseInitializer(sql_dir=custom_dir)
        assert initializer.sql_dir == custom_dir

    def test_read_sql_file(self, tmp_path):
        """Test reading SQL file."""
        # Create SQL directory and file
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        sql_file = sql_dir / "test.sql"
        sql_content = "CREATE TABLE test (id INTEGER);"
        sql_file.write_text(sql_content)

        # Test reading
        initializer = DatabaseInitializer(sql_dir=sql_dir)
        content = initializer._read_sql_file("test.sql")
        assert content == sql_content

    def test_read_sql_file_not_found(self, tmp_path):
        """Test reading non-existent SQL file raises error."""
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()

        initializer = DatabaseInitializer(sql_dir=sql_dir)
        with pytest.raises(FileNotFoundError) as exc_info:
            initializer._read_sql_file("nonexistent.sql")
        assert "SQL file not found" in str(exc_info.value)

    def test_initialize_database_creates_file(self, tmp_path):
        """Test that initialize_database creates database file."""
        # Setup
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        sql_file = sql_dir / "init_database.sql"
        sql_file.write_text("CREATE TABLE test (id INTEGER);")

        db_path = tmp_path / "test.db"
        initializer = DatabaseInitializer(sql_dir=sql_dir)

        # Let it create the real database since mocking connection manager
        # is complex and the test is mainly checking the flow
        result_path = initializer.initialize_database(db_path)

        # Verify
        assert result_path == db_path
        assert db_path.exists()

        # Verify the table was created
        import sqlite3

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        assert any("test" in table[0] for table in tables)

    def test_initialize_database_exists_no_force(self, tmp_path):
        """Test that existing database without force raises error."""
        db_path = tmp_path / "existing.db"
        # Create a database with a schema
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE scripts (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        initializer = DatabaseInitializer()
        with pytest.raises(FileExistsError) as exc_info:
            initializer.initialize_database(db_path, force=False)
        assert "Database already exists" in str(exc_info.value)
        assert "Use --force to overwrite" in str(exc_info.value)

    def test_initialize_database_exists_with_force(self, tmp_path):
        """Test that existing database with force is overwritten."""
        # Setup
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        sql_file = sql_dir / "init_database.sql"
        sql_file.write_text("CREATE TABLE test (id INTEGER);")

        db_path = tmp_path / "existing.db"
        db_path.write_text("existing content")

        initializer = DatabaseInitializer(sql_dir=sql_dir)

        # Initialize with force
        result_path = initializer.initialize_database(db_path, force=True)

        # Verify database was recreated
        assert result_path == db_path
        assert db_path.exists()

        # Verify the new table was created
        import sqlite3

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        assert any("test" in table[0] for table in tables)

    def test_initialize_database_creates_parent_dirs(self, tmp_path):
        """Test that parent directories are created if needed."""
        # Setup
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        sql_file = sql_dir / "init_database.sql"
        sql_file.write_text("CREATE TABLE test (id INTEGER);")

        db_path = tmp_path / "nested" / "dir" / "test.db"
        initializer = DatabaseInitializer(sql_dir=sql_dir)

        # Initialize database
        result_path = initializer.initialize_database(db_path)

        # Verify parent directories were created
        assert result_path == db_path
        assert db_path.parent.exists()
        assert db_path.exists()

    def test_initialize_database_with_connection(self, tmp_path):
        """Test initialization with provided connection."""
        # Setup
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        sql_file = sql_dir / "init_database.sql"
        sql_file.write_text("CREATE TABLE test (id INTEGER);")

        db_path = tmp_path / "test.db"
        initializer = DatabaseInitializer(sql_dir=sql_dir)

        # Use mock connection
        mock_conn = MockConnection()
        result_path = initializer.initialize_database(db_path, connection=mock_conn)

        # Verify - should not create/close connection
        assert result_path == db_path
        assert mock_conn.executed_scripts == ["CREATE TABLE test (id INTEGER);"]
        assert mock_conn.committed
        assert not mock_conn.closed  # Should not close provided connection

    def test_initialize_database_sql_error(self, tmp_path):
        """Test that SQL errors are handled properly."""
        # Setup
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        sql_file = sql_dir / "init_database.sql"
        sql_file.write_text("INVALID SQL;")

        db_path = tmp_path / "test.db"
        initializer = DatabaseInitializer(sql_dir=sql_dir)

        # Mock sqlite3.connect to raise error
        mock_conn = Mock()
        mock_conn.executescript.side_effect = Exception("SQL error")

        with patch("sqlite3.connect") as mock_connect:
            mock_connect.return_value = mock_conn
            with pytest.raises(Exception) as exc_info:
                initializer.initialize_database(db_path)

        # Verify error message - should be the raw exception
        assert "SQL error" in str(exc_info.value)

        # Verify cleanup - database should not exist
        assert not db_path.exists()

    def test_initialize_with_connection_no_cleanup(self, tmp_path):
        """Test that provided connection is not closed after initialization."""
        # Setup
        sql_dir = tmp_path / "sql"
        sql_dir.mkdir()
        sql_file = sql_dir / "init_database.sql"
        sql_file.write_text("CREATE TABLE test (id INTEGER);")

        db_path = tmp_path / "test.db"
        initializer = DatabaseInitializer(sql_dir=sql_dir)

        # Use mock connection
        mock_conn = MockConnection()

        # Initialize with provided connection
        result_path = initializer.initialize_database(db_path, connection=mock_conn)

        # Verify connection was used but not closed
        assert result_path == db_path
        assert mock_conn.executed_scripts == ["CREATE TABLE test (id INTEGER);"]
        assert mock_conn.committed
        assert not mock_conn.closed  # Should not close provided connection
