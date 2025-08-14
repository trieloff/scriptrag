"""Database migration module for ScriptRAG."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from scriptrag.config import ScriptRAGSettings, get_logger

logger = get_logger(__name__)


class MigrationError(Exception):
    """Base exception for migration errors."""


class DatabaseMigrator:
    """Handles database schema migrations."""

    def __init__(self, settings: ScriptRAGSettings | None = None):
        """Initialize the migrator.

        Args:
            settings: Configuration settings. If None, uses global settings.
        """
        if settings is None:
            from scriptrag.config import get_settings

            settings = get_settings()
        self.settings = settings
        self.db_path = settings.database_path
        self.sql_dir = Path(__file__).parent.parent / "storage" / "database" / "sql"

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with proper error handling and cleanup.

        Yields:
            Database connection

        Raises:
            MigrationError: If database connection fails
        """
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path))
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise MigrationError(f"Failed to connect to database: {e}") from e
        finally:
            if conn:
                conn.close()

    def get_current_schema_version(self) -> int:
        """Get the current schema version from the database.

        Returns:
            The current schema version, or 0 if not set.
        """
        if not self.db_path.exists():
            return 0

        try:
            with self._get_connection() as conn:
                try:
                    cursor = conn.execute("SELECT MAX(version) FROM schema_version")
                    result = cursor.fetchone()
                    return result[0] if result and result[0] is not None else 1
                except sqlite3.OperationalError:
                    # schema_version table doesn't exist, assume version 1
                    return 1
        except MigrationError:
            logger.error("Failed to determine schema version")
            return 0

    def get_available_migrations(self) -> list[tuple[int, Path]]:
        """Get list of available migration files.

        Returns:
            List of (version, path) tuples for available migrations.
        """
        migrations = []
        for path in self.sql_dir.glob("migration_*.sql"):
            # Extract version from filename (e.g., migration_002_duplicate_scripts.sql)
            parts = path.stem.split("_")
            if len(parts) >= 2 and parts[1].isdigit():
                version = int(parts[1])
                migrations.append((version, path))

        return sorted(migrations, key=lambda x: x[0])

    def apply_migration(self, version: int, migration_path: Path) -> None:
        """Apply a single migration to the database.

        Args:
            version: The migration version number.
            migration_path: Path to the migration SQL file.

        Raises:
            MigrationError: If migration fails
        """
        logger.info(f"Applying migration {version} from {migration_path.name}")

        # Check if migration file is readable
        if not migration_path.exists():
            raise MigrationError(f"Migration file not found: {migration_path}")
        if not migration_path.is_file():
            raise MigrationError(f"Migration path is not a file: {migration_path}")

        try:
            # Read migration SQL with error handling
            try:
                migration_sql = migration_path.read_text(encoding="utf-8")
            except OSError as e:
                logger.error(f"Failed to read migration file {migration_path}: {e}")
                raise MigrationError(
                    f"Cannot read migration file {migration_path.name}: {e}"
                ) from e

            # Apply migration with context manager
            with self._get_connection() as conn:
                try:
                    conn.executescript(migration_sql)
                    conn.commit()
                    logger.info(f"Successfully applied migration {version}")
                except sqlite3.Error as e:
                    conn.rollback()
                    logger.error(f"Failed to apply migration {version}: {e}")
                    raise MigrationError(
                        f"Database error during migration {version}: {e}"
                    ) from e
        except MigrationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during migration {version}: {e}")
            raise MigrationError(
                f"Unexpected error during migration {version}: {e}"
            ) from e

    def migrate(self) -> int:
        """Run all pending migrations.

        Returns:
            The number of migrations applied.
        """
        if not self.db_path.exists():
            logger.info("Database does not exist, skipping migration")
            return 0

        current_version = self.get_current_schema_version()
        logger.info(f"Current database schema version: {current_version}")

        available_migrations = self.get_available_migrations()
        pending_migrations = [
            (v, p) for v, p in available_migrations if v > current_version
        ]

        if not pending_migrations:
            logger.info("Database schema is up to date")
            return 0

        logger.info(f"Found {len(pending_migrations)} pending migration(s)")

        for version, path in pending_migrations:
            self.apply_migration(version, path)

        new_version = self.get_current_schema_version()
        logger.info(f"Database schema updated to version {new_version}")

        return len(pending_migrations)

    def check_migration_needed(self) -> bool:
        """Check if any migrations are needed.

        Returns:
            True if migrations are needed, False otherwise.
        """
        if not self.db_path.exists():
            return False

        current_version = self.get_current_schema_version()
        available_migrations = self.get_available_migrations()

        return any(v > current_version for v, _ in available_migrations)
