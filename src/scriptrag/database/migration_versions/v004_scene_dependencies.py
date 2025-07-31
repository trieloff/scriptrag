"""Add scene dependencies table for logical ordering."""

import sqlite3

from scriptrag.config import get_logger

from .base import Migration

logger = get_logger(__name__)


class SceneDependenciesMigration(Migration):
    """Add scene dependencies table for logical ordering."""

    def __init__(self) -> None:
        """Initialize scene dependencies migration."""
        super().__init__()
        self.version = 4
        self.description = "Add scene dependencies table for logical ordering"

    def up(self, connection: sqlite3.Connection) -> None:
        """Apply scene dependencies migration.

        Args:
            connection: Database connection
        """
        logger.info("Applying scene dependencies migration")

        # Create scene dependencies table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scene_dependencies (
                id TEXT PRIMARY KEY,
                from_scene_id TEXT NOT NULL,
                to_scene_id TEXT NOT NULL,
                dependency_type TEXT NOT NULL,
                description TEXT,
                strength REAL DEFAULT 1.0,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
                FOREIGN KEY (to_scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
                UNIQUE(from_scene_id, to_scene_id, dependency_type)
            )
            """
        )

        # Create indexes
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scene_dependencies_from
                ON scene_dependencies(from_scene_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scene_dependencies_to
                ON scene_dependencies(to_scene_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scene_dependencies_type
                ON scene_dependencies(dependency_type)
            """
        )

        # Create trigger for updating timestamp
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS update_scene_dependencies_timestamp
                AFTER UPDATE ON scene_dependencies
                BEGIN
                    UPDATE scene_dependencies
                    SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END
            """
        )

        logger.info("Scene dependencies migration applied successfully")

    def down(self, connection: sqlite3.Connection) -> None:
        """Rollback scene dependencies migration.

        Args:
            connection: Database connection
        """
        logger.info("Rolling back scene dependencies migration")

        # Drop trigger first
        connection.execute("DROP TRIGGER IF EXISTS update_scene_dependencies_timestamp")

        # Drop indexes
        connection.execute("DROP INDEX IF EXISTS idx_scene_dependencies_from")
        connection.execute("DROP INDEX IF EXISTS idx_scene_dependencies_to")
        connection.execute("DROP INDEX IF EXISTS idx_scene_dependencies_type")

        # Drop table
        connection.execute("DROP TABLE IF EXISTS scene_dependencies")

        logger.info("Scene dependencies migration rolled back successfully")
