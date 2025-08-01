"""Initial schema creation migration."""

import sqlite3

from scriptrag.config import get_logger

from .base import Migration

logger = get_logger(__name__)


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
