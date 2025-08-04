"""Database API module for ScriptRAG initialization."""

import sqlite3
from pathlib import Path
from typing import Protocol

from scriptrag.api.sql_validator import SQLValidationError, SQLValidator
from scriptrag.config import ScriptRAGSettings, get_logger

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
        self.validator = SQLValidator()

    def _read_sql_file(self, filename: str) -> str:
        """Read SQL file content with validation.

        Args:
            filename: Name of the SQL file to read.

        Returns:
            SQL file content.

        Raises:
            FileNotFoundError: If SQL file not found.
            SQLValidationError: If SQL file fails validation.
        """
        sql_path = self.sql_dir / filename
        if not sql_path.exists():
            raise FileNotFoundError(f"SQL file not found: {sql_path}")

        # Validate file size
        self.validator.validate_file_size(sql_path)

        # Read content
        content = sql_path.read_text(encoding="utf-8")

        # Validate SQL content
        self.validator.validate_sql_content(content, filename)

        return content

    def initialize_database(
        self,
        db_path: Path | None = None,
        force: bool = False,
        settings: ScriptRAGSettings | None = None,
        connection: DatabaseConnection | None = None,
    ) -> Path:
        """Initialize SQLite database with schema.

        Args:
            db_path: Path to the SQLite database file. If None, uses settings.
            force: If True, overwrite existing database.
            settings: Configuration settings. If None, uses global settings.
            connection: Optional database connection for testing.

        Returns:
            Path to the initialized database.

        Raises:
            FileExistsError: If database exists and force is False.
            RuntimeError: If database initialization fails.
        """
        # Get settings if not provided
        if settings is None:
            from scriptrag.config import get_settings

            settings = get_settings()

        # Determine database path from precedence:
        # 1. CLI argument (db_path)
        # 2. Settings (from config file/env vars)
        # 3. Default (already in settings)
        if db_path is None:
            db_path = settings.database_path

        # Validate database path for security
        try:
            self.validator.validate_database_path(db_path)
        except SQLValidationError as e:
            raise RuntimeError(f"Invalid database path: {e}") from e

        # Resolve to absolute path
        db_path = db_path.resolve()
        # Check if database exists
        if db_path.exists() and not force:
            raise FileExistsError(
                f"Database already exists at {db_path}. Use --force to overwrite."
            )

        # Handle force with confirmation
        if db_path.exists() and force:
            # In API layer, we don't do interactive confirmation
            # That's the CLI's responsibility
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
            return db_path

        except SQLValidationError as e:
            # SQL validation error - don't clean up database
            logger.error("SQL validation failed", error=str(e))
            raise RuntimeError(f"SQL validation error: {e}") from e
        except FileNotFoundError as e:
            # SQL file not found
            logger.error("SQL file not found", error=str(e))
            raise RuntimeError(f"Missing SQL file: {e}") from e
        except sqlite3.Error as e:
            # SQLite-specific error
            logger.error("SQLite error during initialization", error=str(e))
            if db_path.exists() and connection is None:
                db_path.unlink()
            raise RuntimeError(f"Database error: {e}") from e
        except Exception as e:
            # Other unexpected errors
            logger.error("Unexpected error during initialization", error=str(e))
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
