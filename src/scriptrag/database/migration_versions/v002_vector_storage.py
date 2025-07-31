"""Migration to add sqlite-vec support to embeddings table."""

import sqlite3

from scriptrag.config import get_logger

from .base import Migration

logger = get_logger(__name__)


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
