"""Database API module for ScriptRAG initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.exceptions import DatabaseError

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

    def _update_gitignore(self, db_path: Path) -> None:
        """Update .gitignore to exclude database files.

        Args:
            db_path: Path to the database file.
        """
        # Get the directory containing the database
        db_dir = db_path.parent

        # Database patterns to ignore
        db_patterns = [
            "scriptrag.db",
            "scriptrag.db-shm",
            "scriptrag.db-wal",
            "*.db",
            "*.db-shm",
            "*.db-wal",
        ]

        # Find the nearest .gitignore file or create one in the current directory
        gitignore_path = db_dir / ".gitignore"

        # If database is in a subdirectory, also check parent directories for .gitignore
        current_dir = db_dir
        while current_dir != current_dir.parent:
            if (current_dir / ".git").exists():
                # Found git repo root, use .gitignore here
                gitignore_path = current_dir / ".gitignore"
                break
            current_dir = current_dir.parent

        # Read existing .gitignore content if it exists
        existing_patterns = set()
        negated_patterns = set()
        if gitignore_path.exists():
            try:
                content = gitignore_path.read_text(encoding="utf-8")
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if line.startswith("!"):
                            # Track negation patterns (without the ! prefix)
                            negated_patterns.add(line[1:])
                        else:
                            existing_patterns.add(line)
            except Exception as e:
                logger.warning(
                    "Failed to read existing .gitignore",
                    path=str(gitignore_path),
                    error=str(e),
                )
                return

        # Determine which patterns need to be added
        # Skip patterns that are already present OR have a negation pattern
        patterns_to_add = []
        for pattern in db_patterns:
            if pattern not in existing_patterns and pattern not in negated_patterns:
                patterns_to_add.append(pattern)
            elif pattern in negated_patterns:
                logger.warning(
                    "Skipping pattern due to existing negation rule",
                    pattern=pattern,
                    negation_rule=f"!{pattern}",
                    gitignore_path=str(gitignore_path),
                )

        if not patterns_to_add:
            logger.debug(".gitignore already contains database patterns")
            return

        # Prepare the new content to append
        new_content = []

        # Add section header if we're adding patterns
        if patterns_to_add:
            # Check if file exists and doesn't end with newline
            if gitignore_path.exists():
                try:
                    with gitignore_path.open("rb") as f:
                        f.seek(-1, 2)  # Go to last byte
                        last_char = f.read(1)
                        if last_char != b"\n":
                            new_content.append("")  # Add blank line
                except OSError:
                    # File might be empty or inaccessible - treat as needing newline
                    pass

            new_content.append("")  # Blank line before section
            new_content.append("# ScriptRAG database files")
            new_content.extend(patterns_to_add)
            new_content.append("")  # Blank line after section

        # Write or append to .gitignore
        try:
            mode = "a" if gitignore_path.exists() else "w"
            with gitignore_path.open(mode, encoding="utf-8") as f:
                f.write("\n".join(new_content))

            logger.info(
                ".gitignore updated with database patterns",
                path=str(gitignore_path),
                patterns_added=len(patterns_to_add),
            )
        except Exception as e:
            logger.warning(
                "Failed to update .gitignore",
                path=str(gitignore_path),
                error=str(e),
            )

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

        # Check if database exists WITH a valid schema
        # Empty database file (created by connection manager) doesn't count
        has_schema = False
        if db_path.exists():
            try:
                from scriptrag.database.connection_manager import get_connection_manager

                manager = get_connection_manager(settings)
                has_schema = manager.check_database_exists()
            except Exception as e:
                # Log the error but continue - database might not be initialized yet
                logger.warning(
                    "Could not check database schema",
                    error=str(e),
                    path=str(db_path),
                )
                has_schema = False

        if has_schema and not force:
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

            # Windows-specific file deletion with retry logic
            import platform

            if platform.system() == "Windows":
                import time

                for attempt in range(3):
                    try:
                        db_path.unlink()
                        break
                    except PermissionError:
                        if attempt == 2:
                            raise
                        time.sleep(0.1 * (attempt + 1))  # Progressive backoff
            else:
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
                    self._initialize_with_connection(conn, settings)  # type: ignore[arg-type]
                finally:
                    manager.release_connection(conn)
            else:
                # Use provided connection (for testing)
                self._initialize_with_connection(connection, settings)

            # Update .gitignore to exclude database files
            self._update_gitignore(db_path)

            logger.info("Database initialized successfully", path=str(db_path))
            return db_path

        except (OSError, sqlite3.Error, ValueError) as e:
            # Clean up on failure
            if db_path.exists() and connection is None:
                # First, ensure the connection manager is properly closed
                # This is critical on Windows to release all file handles
                from scriptrag.database.connection_manager import (
                    close_connection_manager,
                )

                # Force close to ensure all connections are released
                close_connection_manager(force=True)

                # Windows-specific file deletion with retry logic for cleanup
                import platform

                if platform.system() == "Windows":
                    import gc
                    import time

                    # Force garbage collection to help release file handles
                    gc.collect()
                    time.sleep(0.1)  # Give Windows time to release handles

                    for attempt in range(5):  # Increase attempts from 3 to 5
                        try:
                            db_path.unlink()
                            break
                        except PermissionError:
                            if attempt == 4:
                                # Log but don't re-raise since this is cleanup
                                logger.warning(
                                    "Failed to cleanup database file on Windows",
                                    path=str(db_path),
                                )
                                break
                            # Progressive backoff with longer waits
                            gc.collect()  # Try gc again
                            time.sleep(0.2 * (attempt + 1))
                else:
                    db_path.unlink()
            raise DatabaseError(
                message=f"Failed to initialize database: {e}",
                hint="Check disk space and file permissions",
                details={"path": str(db_path), "error_type": type(e).__name__},
            ) from e

    def _initialize_with_connection(
        self, conn: DatabaseConnection, settings: ScriptRAGSettings | None = None
    ) -> None:
        """Initialize database using provided connection.

        Args:
            conn: Database connection to use.
            settings: Configuration settings to apply after initialization.
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
        except sqlite3.Error as e:
            # Re-raise SQLite errors as DatabaseError for consistency
            raise DatabaseError(
                message=f"Failed to initialize VSS schema: {e}",
                hint="Check that required tables exist before initializing VSS schema",
                details={"error_type": type(e).__name__},
            ) from e

        # Re-apply foreign key setting after initialization scripts
        # This ensures our settings override any hardcoded PRAGMA in the SQL files
        if settings is not None:
            if settings.database_foreign_keys:
                conn.execute("PRAGMA foreign_keys = ON")
            else:
                conn.execute("PRAGMA foreign_keys = OFF")

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
        else:
            pragmas.append("PRAGMA foreign_keys = OFF")

        for pragma in pragmas:
            conn.execute(pragma)

        logger.debug(
            "Database connection configured",
            journal_mode=settings.database_journal_mode,
            synchronous=settings.database_synchronous,
            cache_size=settings.database_cache_size,
            foreign_keys=settings.database_foreign_keys,
        )
