"""Migration v006: Add Missing Columns for Search Functionality.

This migration adds critical columns that were missing from the database schema
but are required by the search functionality:

1. scenes table: location_type, story_time columns
2. characters table: first_appearance_scene_id, location_type, description columns
3. locations table: description, location_type, first_appearance_scene_id columns

These columns are referenced in the search code but were not present in the schema,
causing database operation failures.
"""

import sqlite3

from scriptrag.config import get_logger

from .base import Migration

logger = get_logger(__name__)


class AddMissingColumnsMigration(Migration):
    """Migration to add missing columns for search functionality."""

    version = 6
    description = (
        "Add missing columns: location_type, story_time, "
        "first_appearance_scene_id, description"
    )

    def up(self, connection: sqlite3.Connection) -> None:
        """Apply the migration - add missing columns."""
        logger.info("Applying missing columns migration")

        # Add missing columns to scenes table
        try:
            connection.execute("ALTER TABLE scenes ADD COLUMN location_type TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        try:
            connection.execute("ALTER TABLE scenes ADD COLUMN story_time TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Add missing columns to characters table
        try:
            connection.execute(
                "ALTER TABLE characters ADD COLUMN first_appearance_scene_id TEXT"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        try:
            connection.execute("ALTER TABLE characters ADD COLUMN location_type TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Add missing columns to locations table
        try:
            connection.execute("ALTER TABLE locations ADD COLUMN description TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        try:
            connection.execute("ALTER TABLE locations ADD COLUMN location_type TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        try:
            connection.execute(
                "ALTER TABLE locations ADD COLUMN first_appearance_scene_id TEXT"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Create indexes for better query performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_scenes_location_type "
            "ON scenes(location_type)",
            "CREATE INDEX IF NOT EXISTS idx_scenes_story_time ON scenes(story_time)",
            "CREATE INDEX IF NOT EXISTS idx_characters_first_appearance "
            "ON characters(first_appearance_scene_id)",
            "CREATE INDEX IF NOT EXISTS idx_characters_location_type "
            "ON characters(location_type)",
            "CREATE INDEX IF NOT EXISTS idx_locations_location_type "
            "ON locations(location_type)",
            "CREATE INDEX IF NOT EXISTS idx_locations_first_appearance "
            "ON locations(first_appearance_scene_id)",
        ]

        for index_sql in indexes:
            connection.execute(index_sql)

        connection.commit()
        logger.info("Missing columns migration completed successfully")

    def down(self, _connection: sqlite3.Connection) -> None:
        """Rollback the migration."""
        logger.warning(
            "SQLite does not support DROP COLUMN. "
            "Manual table recreation would be required to rollback this migration."
        )
        # SQLite doesn't support DROP COLUMN, so rollback is not implemented
        # This would require:
        # 1. Create new tables without the columns
        # 2. Copy data from old tables
        # 3. Drop old tables
        # 4. Rename new tables
