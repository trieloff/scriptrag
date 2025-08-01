"""Fix FTS table column naming to match base tables."""

import sqlite3

from scriptrag.config import get_logger

from .base import Migration

logger = get_logger(__name__)


class FixFTSColumnsMigration(Migration):
    """Fix FTS table column naming to match base tables."""

    def __init__(self) -> None:
        """Initialize FTS fix migration."""
        super().__init__()
        self.version = 3
        self.description = "Fix FTS table column naming to match base tables"

    def up(self, connection: sqlite3.Connection) -> None:
        """Fix FTS column naming.

        Args:
            connection: Database connection
        """
        logger.info("Applying FTS column naming fix migration")

        # Drop existing FTS tables and triggers
        drop_statements = [
            "DROP TRIGGER IF EXISTS scene_elements_fts_insert",
            "DROP TRIGGER IF EXISTS scene_elements_fts_update",
            "DROP TRIGGER IF EXISTS scene_elements_fts_delete",
            "DROP TRIGGER IF EXISTS characters_fts_insert",
            "DROP TRIGGER IF EXISTS characters_fts_update",
            "DROP TRIGGER IF EXISTS characters_fts_delete",
            "DROP TABLE IF EXISTS scene_elements_fts",
            "DROP TABLE IF EXISTS characters_fts",
        ]

        for statement in drop_statements:
            connection.execute(statement)

        # Recreate FTS tables with correct column names
        connection.execute(
            """
            CREATE VIRTUAL TABLE scene_elements_fts USING fts5(
                id,
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
            CREATE VIRTUAL TABLE characters_fts USING fts5(
                id,
                name,
                description,
                content='characters',
                content_rowid='rowid'
            )
            """
        )

        # Recreate triggers with correct column names
        fts_triggers = [
            """CREATE TRIGGER scene_elements_fts_insert
                AFTER INSERT ON scene_elements
                BEGIN
                    INSERT INTO scene_elements_fts(id, text, character_name, scene_id)
                    VALUES (NEW.id, NEW.text,
                            COALESCE(NEW.character_name, ''), NEW.scene_id);
                END""",
            """CREATE TRIGGER scene_elements_fts_update
                AFTER UPDATE ON scene_elements
                BEGIN
                    UPDATE scene_elements_fts
                    SET text = NEW.text,
                        character_name = COALESCE(NEW.character_name, ''),
                        scene_id = NEW.scene_id
                    WHERE id = NEW.id;
                END""",
            """CREATE TRIGGER scene_elements_fts_delete
                AFTER DELETE ON scene_elements
                BEGIN
                    DELETE FROM scene_elements_fts WHERE id = OLD.id;
                END""",
            """CREATE TRIGGER characters_fts_insert
                AFTER INSERT ON characters
                BEGIN
                    INSERT INTO characters_fts(id, name, description)
                    VALUES (NEW.id, NEW.name, COALESCE(NEW.description, ''));
                END""",
            """CREATE TRIGGER characters_fts_update
                AFTER UPDATE ON characters
                BEGIN
                    UPDATE characters_fts
                    SET name = NEW.name,
                        description = COALESCE(NEW.description, '')
                    WHERE id = NEW.id;
                END""",
            """CREATE TRIGGER characters_fts_delete
                AFTER DELETE ON characters
                BEGIN
                    DELETE FROM characters_fts WHERE id = OLD.id;
                END""",
        ]

        for trigger in fts_triggers:
            connection.execute(trigger)

        logger.info("FTS column naming fix migration applied successfully")

    def down(self, connection: sqlite3.Connection) -> None:
        """Rollback FTS column fix.

        Args:
            connection: Database connection
        """
        logger.info("Rolling back FTS column naming fix migration")

        try:
            # Drop the fixed FTS tables and triggers
            drop_statements = [
                "DROP TRIGGER IF EXISTS scene_elements_fts_insert",
                "DROP TRIGGER IF EXISTS scene_elements_fts_update",
                "DROP TRIGGER IF EXISTS scene_elements_fts_delete",
                "DROP TRIGGER IF EXISTS characters_fts_insert",
                "DROP TRIGGER IF EXISTS characters_fts_update",
                "DROP TRIGGER IF EXISTS characters_fts_delete",
                "DROP TABLE IF EXISTS scene_elements_fts",
                "DROP TABLE IF EXISTS characters_fts",
            ]

            for statement in drop_statements:
                connection.execute(statement)

            # Recreate the original (broken) FTS tables with element_id/character_id
            connection.execute(
                """
                CREATE VIRTUAL TABLE scene_elements_fts USING fts5(
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
                CREATE VIRTUAL TABLE characters_fts USING fts5(
                    character_id,
                    name,
                    description,
                    content='characters',
                    content_rowid='rowid'
                )
                """
            )

            # Recreate original triggers
            original_triggers = [
                """CREATE TRIGGER scene_elements_fts_insert
                    AFTER INSERT ON scene_elements
                    BEGIN
                        INSERT INTO scene_elements_fts(element_id, text,
                                                     character_name, scene_id)
                        VALUES (NEW.id, NEW.text,
                                COALESCE(NEW.character_name, ''), NEW.scene_id);
                    END""",
                """CREATE TRIGGER scene_elements_fts_update
                    AFTER UPDATE ON scene_elements
                    BEGIN
                        UPDATE scene_elements_fts
                        SET text = NEW.text,
                            character_name = COALESCE(NEW.character_name, ''),
                            scene_id = NEW.scene_id
                        WHERE element_id = NEW.id;
                    END""",
                """CREATE TRIGGER scene_elements_fts_delete
                    AFTER DELETE ON scene_elements
                    BEGIN
                        DELETE FROM scene_elements_fts WHERE element_id = OLD.id;
                    END""",
                """CREATE TRIGGER characters_fts_insert
                    AFTER INSERT ON characters
                    BEGIN
                        INSERT INTO characters_fts(character_id, name, description)
                        VALUES (NEW.id, NEW.name, COALESCE(NEW.description, ''));
                    END""",
                """CREATE TRIGGER characters_fts_update
                    AFTER UPDATE ON characters
                    BEGIN
                        UPDATE characters_fts
                        SET name = NEW.name,
                            description = COALESCE(NEW.description, '')
                        WHERE character_id = NEW.id;
                    END""",
                """CREATE TRIGGER characters_fts_delete
                    AFTER DELETE ON characters
                    BEGIN
                        DELETE FROM characters_fts WHERE character_id = OLD.id;
                    END""",
            ]

            for trigger in original_triggers:
                connection.execute(trigger)

            connection.commit()
            logger.info("FTS column naming fix migration rolled back successfully")

        except Exception as e:
            connection.rollback()
            logger.error(f"Failed to rollback FTS column naming fix migration: {e}")
            raise
