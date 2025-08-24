"""Database API module for ScriptRAG initialization."""

import sqlite3
from pathlib import Path
from typing import Protocol

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
        else:
            # If db_path is provided and different from settings, update settings
            if db_path != settings.database_path:
                # Create new settings with the updated database path
                settings_dict = settings.model_dump()
                settings_dict["database_path"] = db_path
                settings = type(settings)(**settings_dict)

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

            # Close the connection manager to release any open connections
            # before deleting the database file
            from scriptrag.database.connection_manager import close_connection_manager

            close_connection_manager()

            db_path.unlink()

        # Create parent directories if needed
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        try:
            if connection is None:
                # Use centralized connection manager for initialization
                # Note: We get a raw connection for schema creation, not a transaction
                from scriptrag.database.connection_manager import (
                    close_connection_manager,
                    get_connection_manager,
                )

                # If we're initializing a database at a different path than the
                # current manager is using, close existing manager and create new one
                existing_manager = get_connection_manager(settings, force_new=False)
                if existing_manager.db_path != db_path:
                    close_connection_manager()

                # Now get the manager (will create new one if we just closed it)
                manager = get_connection_manager(settings)
                conn = manager.get_connection()
                try:
                    # Configure connection with settings
                    self._configure_connection(conn, settings)
                    self._initialize_with_connection(conn)  # type: ignore[arg-type]
                finally:
                    manager.release_connection(conn)
            else:
                # Use provided connection (for testing)
                self._initialize_with_connection(connection)

            logger.info("Database initialized successfully", path=str(db_path))
            return db_path

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

        # Read and execute bible schema SQL if it exists
        try:
            bible_sql = self._read_sql_file("bible_schema.sql")
            conn.executescript(bible_sql)
            logger.info("Bible schema initialized successfully")
        except FileNotFoundError:
            logger.debug("No bible schema file found, skipping")

        # Read and execute VSS schema SQL if it exists
        try:
            vss_sql = self._read_sql_file("vss_schema.sql")
            conn.executescript(vss_sql)
            logger.info("VSS schema initialized successfully")
        except FileNotFoundError:
            logger.debug("No VSS schema file found, skipping")

        conn.commit()

        logger.debug("Database schema created successfully")

    def _configure_connection(
        self, conn: sqlite3.Connection, settings: ScriptRAGSettings
    ) -> None:
        """Configure SQLite connection with settings.

        Args:
            conn: SQLite connection to configure.
            settings: Configuration settings.
        """
        # Set pragmas based on settings
        pragmas = [
            f"PRAGMA journal_mode = {settings.database_journal_mode}",
            f"PRAGMA synchronous = {settings.database_synchronous}",
            f"PRAGMA cache_size = {settings.database_cache_size}",
            f"PRAGMA temp_store = {settings.database_temp_store}",
        ]

        if settings.database_foreign_keys:
            pragmas.append("PRAGMA foreign_keys = ON")

        for pragma in pragmas:
            conn.execute(pragma)

        logger.debug(
            "Database connection configured",
            journal_mode=settings.database_journal_mode,
            synchronous=settings.database_synchronous,
            cache_size=settings.database_cache_size,
            foreign_keys=settings.database_foreign_keys,
        )
