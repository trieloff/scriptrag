"""Database API module for ScriptRAG initialization."""

import sqlite3
from pathlib import Path
from typing import Protocol

from scriptrag.config import get_logger

logger = get_logger(__name__)


class DatabaseConnection(Protocol):
    """Protocol for database connection."""

    def execute(self, sql: str) -> None:
        """Execute SQL statement."""
        ...

    def executescript(self, sql: str) -> None:
        """Execute multiple SQL statements."""
        ...

    def commit(self) -> None:
        """Commit transaction."""
        ...

    def close(self) -> None:
        """Close connection."""
        ...


class DatabaseInitializer:
    """Database initialization API with dependency injection."""

    def __init__(self, sql_dir: Path | None = None) -> None:
        """Initialize database initializer.

        Args:
            sql_dir: Directory containing SQL files. Defaults to package SQL directory.
        """
        if sql_dir is None:
            sql_dir = Path(__file__).parent.parent / "storage" / "database" / "sql"
        self.sql_dir = sql_dir

    def _read_sql_file(self, filename: str) -> str:
        """Read SQL file content.

        Args:
            filename: Name of the SQL file to read.

        Returns:
            SQL file content.

        Raises:
            FileNotFoundError: If SQL file not found.
        """
        sql_path = self.sql_dir / filename
        if not sql_path.exists():
            raise FileNotFoundError(f"SQL file not found: {sql_path}")
        return sql_path.read_text(encoding="utf-8")

    def initialize_database(
        self,
        db_path: Path,
        force: bool = False,
        connection: DatabaseConnection | None = None,
    ) -> None:
        """Initialize SQLite database with schema.

        Args:
            db_path: Path to the SQLite database file.
            force: If True, overwrite existing database.
            connection: Optional database connection for testing.

        Raises:
            FileExistsError: If database exists and force is False.
            RuntimeError: If database initialization fails.
        """
        # Check if database exists
        if db_path.exists() and not force:
            raise FileExistsError(
                f"Database already exists at {db_path}. Use --force to overwrite."
            )

        # Remove existing database if force is True
        if db_path.exists() and force:
            logger.warning("Removing existing database", path=str(db_path))
            db_path.unlink()

        # Create parent directories if needed
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        try:
            if connection is None:
                # Create new connection
                conn = sqlite3.connect(str(db_path))
                try:
                    self._initialize_with_connection(conn)  # type: ignore[arg-type]
                finally:
                    conn.close()
            else:
                # Use provided connection (for testing)
                self._initialize_with_connection(connection)

            logger.info("Database initialized successfully", path=str(db_path))

        except Exception as e:
            # Clean up on failure
            if db_path.exists() and connection is None:
                db_path.unlink()
            raise RuntimeError(f"Failed to initialize database: {e}") from e

    def _initialize_with_connection(self, conn: DatabaseConnection) -> None:
        """Initialize database using provided connection.

        Args:
            conn: Database connection to use.
        """
        # Read initialization SQL
        init_sql = self._read_sql_file("init_database.sql")

        # Execute initialization script
        conn.executescript(init_sql)
        conn.commit()

        logger.debug("Database schema created successfully")
