"""Database migration system for ScriptRAG.

This module provides a comprehensive migration system for managing database
schema changes over time. It supports versioned migrations, rollbacks,
and automatic schema upgrades.
"""

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from scriptrag.config import get_logger

logger = get_logger(__name__)


class Migration(ABC):
    """Base class for database migrations."""

    def __init__(self) -> None:
        """Initialize migration."""
        self.version: int = 0
        self.description: str = ""
        self.applied_at: datetime | None = None

    @abstractmethod
    def up(self, connection: sqlite3.Connection) -> None:
        """Apply the migration.

        Args:
            connection: Database connection
        """
        pass

    @abstractmethod
    def down(self, connection: sqlite3.Connection) -> None:
        """Rollback the migration.

        Args:
            connection: Database connection
        """
        pass

    def __str__(self) -> str:
        """String representation of migration."""
        return f"Migration {self.version}: {self.description}"


class InitialSchemaMigration(Migration):
    """Initial schema creation migration."""

    def __init__(self) -> None:
        """Initialize initial schema migration."""
        super().__init__()
        self.version = 1
        self.description = "Create initial database schema"

    def up(self, connection: sqlite3.Connection) -> None:
        """Create initial schema."""
        logger.info("Applying initial schema migration")

        # Schema version tracking
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_info (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        """
        )

        # Core entity tables
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scripts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                format TEXT DEFAULT 'screenplay',
                author TEXT,
                description TEXT,
                genre TEXT,
                logline TEXT,
                fountain_source TEXT,
                source_file TEXT,
                is_series BOOLEAN DEFAULT FALSE,
                title_page_json TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS seasons (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                number INTEGER NOT NULL,
                title TEXT,
                description TEXT,
                year INTEGER,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
                UNIQUE(script_id, number)
            )
        """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS episodes (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                season_id TEXT,
                number INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                air_date TIMESTAMP,
                writer TEXT,
                director TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
                FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE
            )
        """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                aliases_json TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
            )
        """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS locations (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                interior BOOLEAN DEFAULT TRUE,
                name TEXT NOT NULL,
                time_of_day TEXT,
                raw_text TEXT NOT NULL,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
            )
        """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scenes (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                episode_id TEXT,
                season_id TEXT,
                location_id TEXT,
                heading TEXT,
                description TEXT,
                script_order INTEGER NOT NULL,
                temporal_order INTEGER,
                logical_order INTEGER,
                estimated_duration_minutes REAL,
                time_of_day TEXT,
                date_in_story TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
                FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE,
                FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE,
                FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL
            )
        """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scene_elements (
                id TEXT PRIMARY KEY,
                scene_id TEXT NOT NULL,
                element_type TEXT NOT NULL,
                text TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                order_in_scene INTEGER NOT NULL,
                character_id TEXT,
                character_name TEXT,
                associated_dialogue_id TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE SET NULL,
                FOREIGN KEY (associated_dialogue_id)
                    REFERENCES scene_elements(id) ON DELETE SET NULL
            )
        """
        )

        # Graph database layer
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                entity_id TEXT,
                label TEXT,
                properties_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                from_node_id TEXT NOT NULL,
                to_node_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                properties_json TEXT,
                weight REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_node_id) REFERENCES nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (to_node_id) REFERENCES nodes(id) ON DELETE CASCADE
            )
        """
        )

        # Embeddings for semantic search
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                dimension INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(entity_type, entity_id, embedding_model)
            )
        """
        )

        # Create indexes
        self._create_indexes(connection)

        # Create triggers
        self._create_triggers(connection)

        # Create FTS tables
        self._create_fts_tables(connection)

        logger.info("Initial schema migration completed")

    def down(self, connection: sqlite3.Connection) -> None:
        """Drop all tables (destructive rollback)."""
        logger.warning("Rolling back initial schema - this will drop all data!")

        tables = [
            "scene_elements_fts",
            "characters_fts",
            "embeddings",
            "edges",
            "nodes",
            "scene_elements",
            "scenes",
            "locations",
            "characters",
            "episodes",
            "seasons",
            "scripts",
            "schema_info",
        ]

        for table in tables:
            connection.execute(f"DROP TABLE IF EXISTS {table}")

        logger.info("Initial schema rollback completed")

    def _create_indexes(self, connection: sqlite3.Connection) -> None:
        """Create database indexes."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_scripts_title ON scripts(title)",
            "CREATE INDEX IF NOT EXISTS idx_scripts_author ON scripts(author)",
            "CREATE INDEX IF NOT EXISTS idx_scripts_genre ON scripts(genre)",
            "CREATE INDEX IF NOT EXISTS idx_seasons_script_id ON seasons(script_id)",
            """CREATE INDEX IF NOT EXISTS idx_seasons_number
                ON seasons(script_id, number)""",
            "CREATE INDEX IF NOT EXISTS idx_episodes_script_id ON episodes(script_id)",
            "CREATE INDEX IF NOT EXISTS idx_episodes_season_id ON episodes(season_id)",
            """CREATE INDEX IF NOT EXISTS idx_episodes_number
                ON episodes(season_id, number)""",
            """CREATE INDEX IF NOT EXISTS idx_characters_script_id
                ON characters(script_id)""",
            """CREATE INDEX IF NOT EXISTS idx_characters_name
                ON characters(script_id, name)""",
            """CREATE INDEX IF NOT EXISTS idx_locations_script_id
                ON locations(script_id)""",
            """CREATE INDEX IF NOT EXISTS idx_locations_name
                ON locations(script_id, name)""",
            "CREATE INDEX IF NOT EXISTS idx_scenes_script_id ON scenes(script_id)",
            "CREATE INDEX IF NOT EXISTS idx_scenes_episode_id ON scenes(episode_id)",
            "CREATE INDEX IF NOT EXISTS idx_scenes_season_id ON scenes(season_id)",
            "CREATE INDEX IF NOT EXISTS idx_scenes_location_id ON scenes(location_id)",
            """CREATE INDEX IF NOT EXISTS idx_scenes_script_order
                ON scenes(script_id, script_order)""",
            """CREATE INDEX IF NOT EXISTS idx_scenes_temporal_order
                ON scenes(script_id, temporal_order)""",
            """CREATE INDEX IF NOT EXISTS idx_scenes_logical_order
                ON scenes(script_id, logical_order)""",
            """CREATE INDEX IF NOT EXISTS idx_scene_elements_scene_id
                ON scene_elements(scene_id)""",
            """CREATE INDEX IF NOT EXISTS idx_scene_elements_character_id
                ON scene_elements(character_id)""",
            """CREATE INDEX IF NOT EXISTS idx_scene_elements_order
                ON scene_elements(scene_id, order_in_scene)""",
            """CREATE INDEX IF NOT EXISTS idx_scene_elements_type
                ON scene_elements(element_type)""",
            "CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type)",
            "CREATE INDEX IF NOT EXISTS idx_nodes_entity_id ON nodes(entity_id)",
            """CREATE INDEX IF NOT EXISTS idx_nodes_type_entity
                ON nodes(node_type, entity_id)""",
            "CREATE INDEX IF NOT EXISTS idx_edges_from_node ON edges(from_node_id)",
            "CREATE INDEX IF NOT EXISTS idx_edges_to_node ON edges(to_node_id)",
            "CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type)",
            """CREATE INDEX IF NOT EXISTS idx_edges_from_to
                ON edges(from_node_id, to_node_id)""",
            """CREATE INDEX IF NOT EXISTS idx_edges_type_from
                ON edges(edge_type, from_node_id)""",
            """CREATE INDEX IF NOT EXISTS idx_embeddings_entity
                ON embeddings(entity_type, entity_id)""",
            """CREATE INDEX IF NOT EXISTS idx_embeddings_model
                ON embeddings(embedding_model)""",
        ]

        for index_sql in indexes:
            connection.execute(index_sql)

    def _create_triggers(self, connection: sqlite3.Connection) -> None:
        """Create database triggers."""
        triggers = [
            """CREATE TRIGGER IF NOT EXISTS update_scripts_timestamp
                AFTER UPDATE ON scripts
                BEGIN
                    UPDATE scripts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END""",
            """CREATE TRIGGER IF NOT EXISTS update_seasons_timestamp
                AFTER UPDATE ON seasons
                BEGIN
                    UPDATE seasons SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END""",
            """CREATE TRIGGER IF NOT EXISTS update_episodes_timestamp
                AFTER UPDATE ON episodes
                BEGIN
                    UPDATE episodes SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = NEW.id;
                END""",
            """CREATE TRIGGER IF NOT EXISTS update_characters_timestamp
                AFTER UPDATE ON characters
                BEGIN
                    UPDATE characters SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = NEW.id;
                END""",
            """CREATE TRIGGER IF NOT EXISTS update_locations_timestamp
                AFTER UPDATE ON locations
                BEGIN
                    UPDATE locations SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = NEW.id;
                END""",
            """CREATE TRIGGER IF NOT EXISTS update_scenes_timestamp
                AFTER UPDATE ON scenes
                BEGIN
                    UPDATE scenes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END""",
            """CREATE TRIGGER IF NOT EXISTS update_scene_elements_timestamp
                AFTER UPDATE ON scene_elements
                BEGIN
                    UPDATE scene_elements SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = NEW.id;
                END""",
            """CREATE TRIGGER IF NOT EXISTS update_nodes_timestamp
                AFTER UPDATE ON nodes
                BEGIN
                    UPDATE nodes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END""",
            """CREATE TRIGGER IF NOT EXISTS update_edges_timestamp
                AFTER UPDATE ON edges
                BEGIN
                    UPDATE edges SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END""",
        ]

        for trigger_sql in triggers:
            connection.execute(trigger_sql)

    def _create_fts_tables(self, connection: sqlite3.Connection) -> None:
        """Create full-text search tables and triggers."""
        # Create FTS tables
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS scene_elements_fts USING fts5(
                element_id,
                text,
                character_name,
                scene_id,
                content='scene_elements',
                content_rowid='rowid'
            )
        """
        )

        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS characters_fts USING fts5(
                character_id,
                name,
                description,
                content='characters',
                content_rowid='rowid'
            )
        """
        )

        # Create FTS triggers
        fts_triggers = [
            """CREATE TRIGGER IF NOT EXISTS scene_elements_fts_insert
                AFTER INSERT ON scene_elements
                BEGIN
                    INSERT INTO scene_elements_fts(
                        element_id, text, character_name, scene_id)
                    VALUES (NEW.id, NEW.text, COALESCE(NEW.character_name, ''),
                            NEW.scene_id);
                END""",
            """CREATE TRIGGER IF NOT EXISTS scene_elements_fts_update
                AFTER UPDATE ON scene_elements
                BEGIN
                    UPDATE scene_elements_fts
                    SET text = NEW.text,
                        character_name = COALESCE(NEW.character_name, ''),
                        scene_id = NEW.scene_id
                    WHERE element_id = NEW.id;
                END""",
            """CREATE TRIGGER IF NOT EXISTS scene_elements_fts_delete
                AFTER DELETE ON scene_elements
                BEGIN
                    DELETE FROM scene_elements_fts WHERE element_id = OLD.id;
                END""",
            """CREATE TRIGGER IF NOT EXISTS characters_fts_insert
                AFTER INSERT ON characters
                BEGIN
                    INSERT INTO characters_fts(character_id, name, description)
                    VALUES (NEW.id, NEW.name, COALESCE(NEW.description, ''));
                END""",
            """CREATE TRIGGER IF NOT EXISTS characters_fts_update
                AFTER UPDATE ON characters
                BEGIN
                    UPDATE characters_fts
                    SET name = NEW.name, description = COALESCE(NEW.description, '')
                    WHERE character_id = NEW.id;
                END""",
            """CREATE TRIGGER IF NOT EXISTS characters_fts_delete
                AFTER DELETE ON characters
                BEGIN
                    DELETE FROM characters_fts WHERE character_id = OLD.id;
                END""",
        ]

        for trigger_sql in fts_triggers:
            connection.execute(trigger_sql)


class VectorStorageMigration(Migration):
    """Migration to add sqlite-vec support to embeddings table."""

    def __init__(self) -> None:
        """Initialize vector storage migration."""
        super().__init__()
        self.version = 2
        self.description = "Add sqlite-vec vector storage support to embeddings table"

    def up(self, connection: sqlite3.Connection) -> None:
        """Apply vector storage migration.

        Adds vector_blob and vector_type columns to embeddings table
        and converts existing JSON vectors to binary format.

        Args:
            connection: Database connection
        """
        cursor = connection.cursor()

        try:
            # Add new columns for sqlite-vec support
            cursor.execute(
                """
                ALTER TABLE embeddings
                ADD COLUMN vector_blob BLOB
            """
            )

            cursor.execute(
                """
                ALTER TABLE embeddings
                ADD COLUMN vector_type TEXT DEFAULT 'float32'
            """
            )

            # Make vector_json nullable since we're adding vector_blob
            cursor.execute(
                """
                CREATE TABLE embeddings_new (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    vector_blob BLOB,
                    vector_type TEXT DEFAULT 'float32',
                    vector_json TEXT,
                    dimension INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(entity_type, entity_id, embedding_model)
                )
            """
            )

            # Copy existing data
            cursor.execute(
                """
                INSERT INTO embeddings_new (
                    id, entity_type, entity_id, content, embedding_model,
                    vector_json, dimension, created_at
                )
                SELECT
                    id, entity_type, entity_id, content, embedding_model,
                    vector_json, dimension, created_at
                FROM embeddings
            """
            )

            # Replace old table
            cursor.execute("DROP TABLE embeddings")
            cursor.execute("ALTER TABLE embeddings_new RENAME TO embeddings")

            # Recreate index
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_embeddings_entity
                ON embeddings(entity_type, entity_id)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_embeddings_model
                ON embeddings(embedding_model)
            """
            )

            connection.commit()
            logger.info("Vector storage migration applied successfully")

        except Exception as e:
            connection.rollback()
            logger.error(f"Failed to apply vector storage migration: {e}")
            raise

    def down(self, connection: sqlite3.Connection) -> None:
        """Rollback vector storage migration.

        Removes vector_blob and vector_type columns from embeddings table.

        Args:
            connection: Database connection
        """
        cursor = connection.cursor()

        try:
            # Recreate original table structure
            cursor.execute(
                """
                CREATE TABLE embeddings_rollback (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(entity_type, entity_id, embedding_model)
                )
            """
            )

            # Copy data back (only records with vector_json)
            cursor.execute(
                """
                INSERT INTO embeddings_rollback (
                    id, entity_type, entity_id, content, embedding_model,
                    vector_json, dimension, created_at
                )
                SELECT
                    id, entity_type, entity_id, content, embedding_model,
                    vector_json, dimension, created_at
                FROM embeddings
                WHERE vector_json IS NOT NULL
            """
            )

            # Replace table
            cursor.execute("DROP TABLE embeddings")
            cursor.execute("ALTER TABLE embeddings_rollback RENAME TO embeddings")

            # Recreate indexes
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_embeddings_entity
                ON embeddings(entity_type, entity_id)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_embeddings_model
                ON embeddings(embedding_model)
            """
            )

            connection.commit()
            logger.info("Vector storage migration rolled back successfully")

        except Exception as e:
            connection.rollback()
            logger.error(f"Failed to rollback vector storage migration: {e}")
            raise


class MigrationRunner:
    """Manages database migrations."""

    def __init__(self, db_path: str | Path) -> None:
        """Initialize migration runner.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.migrations: dict[int, type[Migration]] = {
            1: InitialSchemaMigration,
            2: VectorStorageMigration,
        }

    def get_current_version(self) -> int:
        """Get current database schema version.

        Returns:
            Current schema version, 0 if not initialized
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT MAX(version) FROM schema_info")
                result = cursor.fetchone()
                return result[0] if result[0] is not None else 0
        except sqlite3.OperationalError:
            return 0

    def get_target_version(self) -> int:
        """Get the target (latest) migration version.

        Returns:
            Latest available migration version
        """
        return max(self.migrations.keys()) if self.migrations else 0

    def needs_migration(self) -> bool:
        """Check if database needs migration.

        Returns:
            True if migration is needed
        """
        return self.get_current_version() < self.get_target_version()

    def get_pending_migrations(self) -> list[int]:
        """Get list of pending migration versions.

        Returns:
            List of migration versions that need to be applied
        """
        current = self.get_current_version()
        target = self.get_target_version()
        return [v for v in range(current + 1, target + 1) if v in self.migrations]

    def apply_migration(self, version: int) -> bool:
        """Apply a specific migration.

        Args:
            version: Migration version to apply

        Returns:
            True if successful
        """
        if version not in self.migrations:
            logger.error(f"Migration version {version} not found")
            return False

        migration_class = self.migrations[version]
        migration = migration_class()

        logger.info(f"Applying {migration}")

        try:
            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.db_path) as conn:
                # Enable foreign key constraints
                conn.execute("PRAGMA foreign_keys = ON")

                # Apply migration
                migration.up(conn)

                # Record migration
                conn.execute(
                    "INSERT INTO schema_info (version, description) VALUES (?, ?)",
                    (version, migration.description),
                )

                conn.commit()

            logger.info(f"Successfully applied migration {version}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            return False

    def rollback_migration(self, version: int) -> bool:
        """Rollback a specific migration.

        Args:
            version: Migration version to rollback

        Returns:
            True if successful
        """
        if version not in self.migrations:
            logger.error(f"Migration version {version} not found")
            return False

        current = self.get_current_version()
        if current < version:
            logger.error(f"Cannot rollback migration {version}: not applied")
            return False

        migration_class = self.migrations[version]
        migration = migration_class()

        logger.warning(f"Rolling back {migration}")

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Enable foreign key constraints
                conn.execute("PRAGMA foreign_keys = ON")

                # Rollback migration
                migration.down(conn)

                # Remove migration record
                conn.execute("DELETE FROM schema_info WHERE version = ?", (version,))

                conn.commit()

            logger.info(f"Successfully rolled back migration {version}")
            return True

        except Exception as e:
            logger.error(f"Failed to rollback migration {version}: {e}")
            return False

    def migrate_to_latest(self) -> bool:
        """Migrate database to latest version.

        Returns:
            True if successful
        """
        if not self.needs_migration():
            logger.info("Database is already at latest version")
            return True

        pending = self.get_pending_migrations()
        logger.info(f"Applying {len(pending)} pending migrations")

        for version in pending:
            if not self.apply_migration(version):
                logger.error(f"Migration failed at version {version}")
                return False

        logger.info("Database migration completed successfully")
        return True

    def migrate_to_version(self, target_version: int) -> bool:
        """Migrate database to specific version.

        Args:
            target_version: Target migration version

        Returns:
            True if successful
        """
        current = self.get_current_version()

        if current == target_version:
            logger.info(f"Database is already at version {target_version}")
            return True

        if target_version > current:
            # Apply migrations
            versions = [
                v
                for v in range(current + 1, target_version + 1)
                if v in self.migrations
            ]
            for version in versions:
                if not self.apply_migration(version):
                    return False
        else:
            # Rollback migrations
            versions = [
                v for v in range(current, target_version, -1) if v in self.migrations
            ]
            for version in versions:
                if not self.rollback_migration(version):
                    return False

        logger.info(f"Database migrated to version {target_version}")
        return True

    def reset_database(self) -> bool:
        """Reset database by rolling back all migrations.

        Returns:
            True if successful
        """
        current = self.get_current_version()
        versions = [v for v in range(current, 0, -1) if v in self.migrations]

        for version in versions:
            if not self.rollback_migration(version):
                logger.error(f"Failed to rollback migration {version}")
                return False

        logger.info("Database reset completed")
        return True

    def get_migration_history(self) -> list[dict[str, any]]:
        """Get migration history.

        Returns:
            List of applied migrations with metadata
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """SELECT version, applied_at, description
                       FROM schema_info ORDER BY version"""
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            return []

    def validate_migrations(self) -> bool:
        """Validate migration sequence.

        Returns:
            True if migration sequence is valid
        """
        versions = sorted(self.migrations.keys())

        # Check for gaps in version sequence
        for i, version in enumerate(versions):
            if i > 0 and version != versions[i - 1] + 1:
                logger.error(
                    f"Gap in migration sequence: {versions[i - 1]} -> {version}"
                )
                return False

        logger.info("Migration sequence is valid")
        return True


def initialize_database(db_path: str | Path) -> bool:
    """Initialize a new database with latest schema.

    Args:
        db_path: Path to database file

    Returns:
        True if successful
    """
    runner = MigrationRunner(db_path)

    # Validate migrations first
    if not runner.validate_migrations():
        logger.error("Migration validation failed")
        return False

    # Apply all migrations
    return runner.migrate_to_latest()


def migrate_database(db_path: str | Path, target_version: int | None = None) -> bool:
    """Migrate database to target version.

    Args:
        db_path: Path to database file
        target_version: Target version (latest if None)

    Returns:
        True if successful
    """
    runner = MigrationRunner(db_path)

    if target_version is None:
        return runner.migrate_to_latest()
    return runner.migrate_to_version(target_version)
