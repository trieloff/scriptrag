"""Database schema definitions for ScriptRAG graph database.

This module defines the SQLite schema for storing screenplay data in a graph format.
The schema supports both structured data for core entities and flexible graph
relationships for complex queries and analysis.
"""

import sqlite3
from pathlib import Path

from scriptrag.config import get_logger

logger = get_logger(__name__)

# Schema version for migrations
SCHEMA_VERSION = 5

# SQL DDL statements for creating tables
SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_info (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Core entity tables
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
    title_page_json TEXT, -- JSON string
    metadata_json TEXT,   -- JSON string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
);

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
);

CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    script_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    aliases_json TEXT, -- JSON array of aliases
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
);

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
);

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
);

CREATE TABLE IF NOT EXISTS scene_elements (
    id TEXT PRIMARY KEY,
    scene_id TEXT NOT NULL,
    element_type TEXT NOT NULL, -- action, dialogue, parenthetical, etc.
    text TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    order_in_scene INTEGER NOT NULL,
    character_id TEXT, -- For dialogue elements
    character_name TEXT, -- Denormalized character name
    associated_dialogue_id TEXT, -- For parentheticals
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE SET NULL,
    FOREIGN KEY (associated_dialogue_id)
        REFERENCES scene_elements(id) ON DELETE SET NULL
);

-- Graph database layer for relationships and flexible queries
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL, -- script, character, scene, location, concept, etc.
    entity_id TEXT, -- Reference to actual entity table
    label TEXT,
    properties_json TEXT, -- JSON object for flexible properties
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS edges (
    id TEXT PRIMARY KEY,
    from_node_id TEXT NOT NULL,
    to_node_id TEXT NOT NULL,
    edge_type TEXT NOT NULL, -- FOLLOWS, APPEARS_IN, SPEAKS_TO, etc.
    properties_json TEXT, -- JSON object for edge properties
    weight REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_node_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (to_node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

-- Embeddings for semantic search with sqlite-vec support
CREATE TABLE IF NOT EXISTS embeddings (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL, -- Type of entity (scene, character, dialogue, etc.)
    entity_id TEXT NOT NULL, -- ID of the entity
    content TEXT NOT NULL, -- Text content that was embedded
    embedding_model TEXT NOT NULL, -- Model used for embedding
    vector_blob BLOB, -- Binary vector storage for sqlite-vec
    vector_type TEXT DEFAULT 'float32', -- Vector type: float32, int8, bit
    vector_json TEXT, -- JSON array of embedding vector (legacy format)
    dimension INTEGER NOT NULL, -- Dimension of the embedding vector
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id, embedding_model)
);

-- Full-text search tables
CREATE VIRTUAL TABLE IF NOT EXISTS scene_elements_fts USING fts5(
    element_id,
    text,
    character_name,
    scene_id,
    content='scene_elements',
    content_rowid='rowid'
);

CREATE VIRTUAL TABLE IF NOT EXISTS characters_fts USING fts5(
    character_id,
    name,
    description,
    content='characters',
    content_rowid='rowid'
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_scripts_title ON scripts(title);
CREATE INDEX IF NOT EXISTS idx_scripts_author ON scripts(author);
CREATE INDEX IF NOT EXISTS idx_scripts_genre ON scripts(genre);

CREATE INDEX IF NOT EXISTS idx_seasons_script_id ON seasons(script_id);
CREATE INDEX IF NOT EXISTS idx_seasons_number ON seasons(script_id, number);

CREATE INDEX IF NOT EXISTS idx_episodes_script_id ON episodes(script_id);
CREATE INDEX IF NOT EXISTS idx_episodes_season_id ON episodes(season_id);
CREATE INDEX IF NOT EXISTS idx_episodes_number ON episodes(season_id, number);

CREATE INDEX IF NOT EXISTS idx_characters_script_id ON characters(script_id);
CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(script_id, name);

CREATE INDEX IF NOT EXISTS idx_locations_script_id ON locations(script_id);
CREATE INDEX IF NOT EXISTS idx_locations_name ON locations(script_id, name);

CREATE INDEX IF NOT EXISTS idx_scenes_script_id ON scenes(script_id);
CREATE INDEX IF NOT EXISTS idx_scenes_episode_id ON scenes(episode_id);
CREATE INDEX IF NOT EXISTS idx_scenes_season_id ON scenes(season_id);
CREATE INDEX IF NOT EXISTS idx_scenes_location_id ON scenes(location_id);
CREATE INDEX IF NOT EXISTS idx_scenes_script_order ON scenes(script_id, script_order);
CREATE INDEX IF NOT EXISTS idx_scenes_temporal_order
    ON scenes(script_id, temporal_order);
CREATE INDEX IF NOT EXISTS idx_scenes_logical_order ON scenes(script_id, logical_order);

CREATE INDEX IF NOT EXISTS idx_scene_elements_scene_id ON scene_elements(scene_id);
CREATE INDEX IF NOT EXISTS idx_scene_elements_character_id
    ON scene_elements(character_id);
CREATE INDEX IF NOT EXISTS idx_scene_elements_order
    ON scene_elements(scene_id, order_in_scene);
CREATE INDEX IF NOT EXISTS idx_scene_elements_type ON scene_elements(element_type);

CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_entity_id ON nodes(entity_id);
CREATE INDEX IF NOT EXISTS idx_nodes_type_entity ON nodes(node_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_edges_from_node ON edges(from_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_to_node ON edges(to_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_edges_from_to ON edges(from_node_id, to_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_type_from ON edges(edge_type, from_node_id);

CREATE INDEX IF NOT EXISTS idx_embeddings_entity ON embeddings(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_model ON embeddings(embedding_model);

-- Scene dependencies table for logical ordering
CREATE TABLE IF NOT EXISTS scene_dependencies (
    id TEXT PRIMARY KEY,
    from_scene_id TEXT NOT NULL,
    to_scene_id TEXT NOT NULL,
    dependency_type TEXT NOT NULL, -- requires, references, continues, flashback_to
    description TEXT,
    strength REAL DEFAULT 1.0, -- Strength of dependency (0.0 to 1.0)
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
    FOREIGN KEY (to_scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
    UNIQUE(from_scene_id, to_scene_id, dependency_type)
);

-- Indexes for scene dependencies
CREATE INDEX IF NOT EXISTS idx_scene_dependencies_from
    ON scene_dependencies(from_scene_id);
CREATE INDEX IF NOT EXISTS idx_scene_dependencies_to ON scene_dependencies(to_scene_id);
CREATE INDEX IF NOT EXISTS idx_scene_dependencies_type
    ON scene_dependencies(dependency_type);

-- Triggers for maintaining updated_at timestamps
CREATE TRIGGER IF NOT EXISTS update_scripts_timestamp
    AFTER UPDATE ON scripts
    BEGIN
        UPDATE scripts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_seasons_timestamp
    AFTER UPDATE ON seasons
    BEGIN
        UPDATE seasons SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_episodes_timestamp
    AFTER UPDATE ON episodes
    BEGIN
        UPDATE episodes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_characters_timestamp
    AFTER UPDATE ON characters
    BEGIN
        UPDATE characters SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_locations_timestamp
    AFTER UPDATE ON locations
    BEGIN
        UPDATE locations SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_scenes_timestamp
    AFTER UPDATE ON scenes
    BEGIN
        UPDATE scenes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_scene_elements_timestamp
    AFTER UPDATE ON scene_elements
    BEGIN
        UPDATE scene_elements SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_nodes_timestamp
    AFTER UPDATE ON nodes
    BEGIN
        UPDATE nodes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_edges_timestamp
    AFTER UPDATE ON edges
    BEGIN
        UPDATE edges SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_scene_dependencies_timestamp
    AFTER UPDATE ON scene_dependencies
    BEGIN
        UPDATE scene_dependencies SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- FTS triggers to keep search indexes in sync
CREATE TRIGGER IF NOT EXISTS scene_elements_fts_insert
    AFTER INSERT ON scene_elements
    BEGIN
        INSERT INTO scene_elements_fts(element_id, text, character_name, scene_id)
        VALUES (NEW.id, NEW.text, COALESCE(NEW.character_name, ''), NEW.scene_id);
    END;

CREATE TRIGGER IF NOT EXISTS scene_elements_fts_update
    AFTER UPDATE ON scene_elements
    BEGIN
        UPDATE scene_elements_fts
        SET text = NEW.text, character_name = COALESCE(NEW.character_name, ''),
            scene_id = NEW.scene_id
        WHERE element_id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS scene_elements_fts_delete
    AFTER DELETE ON scene_elements
    BEGIN
        DELETE FROM scene_elements_fts WHERE element_id = OLD.id;
    END;

CREATE TRIGGER IF NOT EXISTS characters_fts_insert
    AFTER INSERT ON characters
    BEGIN
        INSERT INTO characters_fts(character_id, name, description)
        VALUES (NEW.id, NEW.name, COALESCE(NEW.description, ''));
    END;

CREATE TRIGGER IF NOT EXISTS characters_fts_update
    AFTER UPDATE ON characters
    BEGIN
        UPDATE characters_fts
        SET name = NEW.name, description = COALESCE(NEW.description, '')
        WHERE character_id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS characters_fts_delete
    AFTER DELETE ON characters
    BEGIN
        DELETE FROM characters_fts WHERE character_id = OLD.id;
    END;

-- Mentor analysis results table
CREATE TABLE IF NOT EXISTS mentor_results (
    id TEXT PRIMARY KEY,
    mentor_name TEXT NOT NULL,
    mentor_version TEXT NOT NULL,
    script_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    score REAL,
    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    execution_time_ms INTEGER,
    config_json TEXT, -- JSON string of configuration used
    metadata_json TEXT, -- JSON string for additional metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
);

-- Individual mentor analyses table
CREATE TABLE IF NOT EXISTS mentor_analyses (
    id TEXT PRIMARY KEY,
    result_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL, -- 'info', 'suggestion', 'warning', 'error'
    scene_id TEXT,
    character_id TEXT,
    element_id TEXT,
    category TEXT NOT NULL,
    mentor_name TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    recommendations_json TEXT, -- JSON array of recommendations
    examples_json TEXT, -- JSON array of examples
    metadata_json TEXT, -- JSON object for mentor-specific data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (result_id) REFERENCES mentor_results(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (element_id) REFERENCES scene_elements(id) ON DELETE CASCADE
);

-- Indexes for mentor tables
CREATE INDEX IF NOT EXISTS idx_mentor_results_script_id
    ON mentor_results(script_id);
CREATE INDEX IF NOT EXISTS idx_mentor_results_mentor_name
    ON mentor_results(mentor_name);
CREATE INDEX IF NOT EXISTS idx_mentor_results_analysis_date
    ON mentor_results(analysis_date);

CREATE INDEX IF NOT EXISTS idx_mentor_analyses_result_id
    ON mentor_analyses(result_id);
CREATE INDEX IF NOT EXISTS idx_mentor_analyses_scene_id
    ON mentor_analyses(scene_id);
CREATE INDEX IF NOT EXISTS idx_mentor_analyses_character_id
    ON mentor_analyses(character_id);
CREATE INDEX IF NOT EXISTS idx_mentor_analyses_element_id
    ON mentor_analyses(element_id);
CREATE INDEX IF NOT EXISTS idx_mentor_analyses_category
    ON mentor_analyses(category);
CREATE INDEX IF NOT EXISTS idx_mentor_analyses_severity
    ON mentor_analyses(severity);
CREATE INDEX IF NOT EXISTS idx_mentor_analyses_mentor_name
    ON mentor_analyses(mentor_name);

-- Triggers for maintaining updated_at timestamps for mentor tables
CREATE TRIGGER IF NOT EXISTS update_mentor_results_timestamp
    AFTER UPDATE ON mentor_results
    BEGIN
        UPDATE mentor_results SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_mentor_analyses_timestamp
    AFTER UPDATE ON mentor_analyses
    BEGIN
        UPDATE mentor_analyses SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- Full-text search for mentor analyses
CREATE VIRTUAL TABLE IF NOT EXISTS mentor_analyses_fts USING fts5(
    analysis_id,
    title,
    description,
    mentor_name,
    category,
    content='mentor_analyses',
    content_rowid='rowid'
);

-- FTS triggers for mentor analyses
CREATE TRIGGER IF NOT EXISTS mentor_analyses_fts_insert
    AFTER INSERT ON mentor_analyses
    BEGIN
        INSERT INTO mentor_analyses_fts(
            analysis_id, title, description, mentor_name, category
        )
        VALUES (NEW.id, NEW.title, NEW.description, NEW.mentor_name, NEW.category);
    END;

CREATE TRIGGER IF NOT EXISTS mentor_analyses_fts_update
    AFTER UPDATE ON mentor_analyses
    BEGIN
        UPDATE mentor_analyses_fts
        SET title = NEW.title, description = NEW.description,
            mentor_name = NEW.mentor_name, category = NEW.category
        WHERE analysis_id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS mentor_analyses_fts_delete
    AFTER DELETE ON mentor_analyses
    BEGIN
        DELETE FROM mentor_analyses_fts WHERE analysis_id = OLD.id;
    END;
"""


class DatabaseSchema:
    """Manages database schema creation and migrations."""

    def __init__(self, db_path: str | Path) -> None:
        """Initialize schema manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)

    def create_schema(self) -> None:
        """Create the complete database schema."""
        logger.info(f"Creating database schema at {self.db_path}")

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Enable foreign key constraints
            conn.execute("PRAGMA foreign_keys = ON")

            # Execute schema creation
            conn.executescript(SCHEMA_SQL)

            # Record schema version
            conn.execute(
                "INSERT OR REPLACE INTO schema_info (version, description) "
                "VALUES (?, ?)",
                (SCHEMA_VERSION, f"Initial schema creation v{SCHEMA_VERSION}"),
            )

            conn.commit()

        logger.info("Database schema created successfully")

    def get_current_version(self) -> int:
        """Get the current schema version from the database.

        Returns:
            Current schema version, or 0 if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT MAX(version) FROM schema_info")
                result = cursor.fetchone()
                return result[0] if result[0] is not None else 0
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            return 0

    def needs_migration(self) -> bool:
        """Check if database needs migration to current schema version.

        Returns:
            True if migration is needed
        """
        return self.get_current_version() < SCHEMA_VERSION

    def validate_schema(self) -> bool:
        """Validate that all required tables exist.

        Returns:
            True if schema is valid
        """
        required_tables = [
            "schema_info",
            "scripts",
            "seasons",
            "episodes",
            "characters",
            "locations",
            "scenes",
            "scene_elements",
            "nodes",
            "edges",
            "embeddings",
            "scene_dependencies",
            "scene_elements_fts",
            "characters_fts",
            "mentor_results",
            "mentor_analyses",
            "mentor_analyses_fts",
        ]

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                existing_tables = {row[0] for row in cursor.fetchall()}

                missing_tables = set(required_tables) - existing_tables
                if missing_tables:
                    logger.error(f"Missing tables: {missing_tables}")
                    return False

                return True

        except sqlite3.Error as e:
            logger.error(f"Error validating schema: {e}")
            return False


def create_database(db_path: str | Path) -> DatabaseSchema:
    """Create a new ScriptRAG database with schema.

    Args:
        db_path: Path to SQLite database file

    Returns:
        DatabaseSchema instance
    """
    schema = DatabaseSchema(db_path)
    schema.create_schema()
    return schema


def migrate_database(db_path: str | Path) -> bool:
    """Migrate database to current schema version.

    Args:
        db_path: Path to SQLite database file

    Returns:
        True if migration was successful
    """
    schema = DatabaseSchema(db_path)

    if not schema.needs_migration():
        logger.info("Database is already at current schema version")
        return True

    current_version = schema.get_current_version()
    logger.info(
        f"Migrating database from version {current_version} to {SCHEMA_VERSION}"
    )

    # Handle migration paths
    if current_version == 0:
        schema.create_schema()
        return True

    # Apply migrations incrementally
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        if current_version < 4:
            # Apply migration to version 4 (scene dependencies)
            logger.info("Applying migration to version 4 (scene dependencies)")

            # Read and execute migration SQL
            migration_sql = """
            -- Scene dependencies table for logical ordering
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
            );

            CREATE INDEX IF NOT EXISTS idx_scene_dependencies_from
                ON scene_dependencies(from_scene_id);
            CREATE INDEX IF NOT EXISTS idx_scene_dependencies_to
                ON scene_dependencies(to_scene_id);
            CREATE INDEX IF NOT EXISTS idx_scene_dependencies_type
                ON scene_dependencies(dependency_type);

            CREATE TRIGGER IF NOT EXISTS update_scene_dependencies_timestamp
                AFTER UPDATE ON scene_dependencies
                BEGIN
                    UPDATE scene_dependencies
                    SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END;
            """

            conn.executescript(migration_sql)

            # Update schema version
            conn.execute(
                "INSERT INTO schema_info (version, description) VALUES (?, ?)",
                (4, "Added scene dependencies table for logical ordering"),
            )
            conn.commit()

        if current_version < 5:
            # Apply migration to version 5 (mentor system)
            logger.info("Applying migration to version 5 (mentor system)")

            # Read and execute migration SQL for mentor system
            migration_sql = """
            -- Mentor analysis results table
            CREATE TABLE IF NOT EXISTS mentor_results (
                id TEXT PRIMARY KEY,
                mentor_name TEXT NOT NULL,
                mentor_version TEXT NOT NULL,
                script_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                score REAL,
                analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                execution_time_ms INTEGER,
                config_json TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
            );

            -- Individual mentor analyses table
            CREATE TABLE IF NOT EXISTS mentor_analyses (
                id TEXT PRIMARY KEY,
                result_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                severity TEXT NOT NULL,
                scene_id TEXT,
                character_id TEXT,
                element_id TEXT,
                category TEXT NOT NULL,
                mentor_name TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                recommendations_json TEXT,
                examples_json TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (result_id) REFERENCES mentor_results(id) ON DELETE CASCADE,
                FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
                FOREIGN KEY (element_id) REFERENCES scene_elements(id) ON DELETE CASCADE
            );

            -- Indexes for mentor tables
            CREATE INDEX IF NOT EXISTS idx_mentor_results_script_id
                ON mentor_results(script_id);
            CREATE INDEX IF NOT EXISTS idx_mentor_results_mentor_name
                ON mentor_results(mentor_name);
            CREATE INDEX IF NOT EXISTS idx_mentor_results_analysis_date
                ON mentor_results(analysis_date);
            CREATE INDEX IF NOT EXISTS idx_mentor_analyses_result_id
                ON mentor_analyses(result_id);
            CREATE INDEX IF NOT EXISTS idx_mentor_analyses_scene_id
                ON mentor_analyses(scene_id);
            CREATE INDEX IF NOT EXISTS idx_mentor_analyses_character_id
                ON mentor_analyses(character_id);
            CREATE INDEX IF NOT EXISTS idx_mentor_analyses_element_id
                ON mentor_analyses(element_id);
            CREATE INDEX IF NOT EXISTS idx_mentor_analyses_category
                ON mentor_analyses(category);
            CREATE INDEX IF NOT EXISTS idx_mentor_analyses_severity
                ON mentor_analyses(severity);
            CREATE INDEX IF NOT EXISTS idx_mentor_analyses_mentor_name
                ON mentor_analyses(mentor_name);

            -- Triggers for mentor tables
            CREATE TRIGGER IF NOT EXISTS update_mentor_results_timestamp
                AFTER UPDATE ON mentor_results
                BEGIN
                    UPDATE mentor_results
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = NEW.id;
                END;

            CREATE TRIGGER IF NOT EXISTS update_mentor_analyses_timestamp
                AFTER UPDATE ON mentor_analyses
                BEGIN
                    UPDATE mentor_analyses
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = NEW.id;
                END;

            -- Full-text search for mentor analyses
            CREATE VIRTUAL TABLE IF NOT EXISTS mentor_analyses_fts USING fts5(
                analysis_id,
                title,
                description,
                mentor_name,
                category,
                content='mentor_analyses',
                content_rowid='rowid'
            );

            CREATE TRIGGER IF NOT EXISTS mentor_analyses_fts_insert
                AFTER INSERT ON mentor_analyses
                BEGIN
                    INSERT INTO mentor_analyses_fts(
                        analysis_id, title, description, mentor_name, category
                    )
                    VALUES (
                        NEW.id,
                        NEW.title,
                        NEW.description,
                        NEW.mentor_name,
                        NEW.category
                    );
                END;

            CREATE TRIGGER IF NOT EXISTS mentor_analyses_fts_update
                AFTER UPDATE ON mentor_analyses
                BEGIN
                    UPDATE mentor_analyses_fts
                    SET title = NEW.title, description = NEW.description,
                        mentor_name = NEW.mentor_name, category = NEW.category
                    WHERE analysis_id = NEW.id;
                END;

            CREATE TRIGGER IF NOT EXISTS mentor_analyses_fts_delete
                AFTER DELETE ON mentor_analyses
                BEGIN
                    DELETE FROM mentor_analyses_fts WHERE analysis_id = OLD.id;
                END;
            """

            conn.executescript(migration_sql)

            # Update schema version
            conn.execute(
                "INSERT INTO schema_info (version, description) VALUES (?, ?)",
                (
                    5,
                    "Added mentor system tables for automated screenplay analysis",
                ),
            )
            conn.commit()

    return True
