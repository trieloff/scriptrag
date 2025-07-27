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

-- Indexes for Script Bible tables
CREATE INDEX IF NOT EXISTS idx_series_bibles_script_id ON series_bibles(script_id);
CREATE INDEX IF NOT EXISTS idx_series_bibles_status ON series_bibles(status);
CREATE INDEX IF NOT EXISTS idx_series_bibles_type ON series_bibles(bible_type);

CREATE INDEX IF NOT EXISTS idx_character_profiles_character_id ON character_profiles(character_id);
CREATE INDEX IF NOT EXISTS idx_character_profiles_script_id ON character_profiles(script_id);
CREATE INDEX IF NOT EXISTS idx_character_profiles_bible_id ON character_profiles(series_bible_id);

CREATE INDEX IF NOT EXISTS idx_world_elements_script_id ON world_elements(script_id);
CREATE INDEX IF NOT EXISTS idx_world_elements_bible_id ON world_elements(series_bible_id);
CREATE INDEX IF NOT EXISTS idx_world_elements_type ON world_elements(element_type);
CREATE INDEX IF NOT EXISTS idx_world_elements_category ON world_elements(element_type, category);

CREATE INDEX IF NOT EXISTS idx_story_timelines_script_id ON story_timelines(script_id);
CREATE INDEX IF NOT EXISTS idx_story_timelines_bible_id ON story_timelines(series_bible_id);
CREATE INDEX IF NOT EXISTS idx_story_timelines_type ON story_timelines(timeline_type);

CREATE INDEX IF NOT EXISTS idx_timeline_events_timeline_id ON timeline_events(timeline_id);
CREATE INDEX IF NOT EXISTS idx_timeline_events_script_id ON timeline_events(script_id);
CREATE INDEX IF NOT EXISTS idx_timeline_events_scene_id ON timeline_events(scene_id);
CREATE INDEX IF NOT EXISTS idx_timeline_events_episode_id ON timeline_events(episode_id);
CREATE INDEX IF NOT EXISTS idx_timeline_events_order ON timeline_events(timeline_id, relative_order);

CREATE INDEX IF NOT EXISTS idx_continuity_notes_script_id ON continuity_notes(script_id);
CREATE INDEX IF NOT EXISTS idx_continuity_notes_bible_id ON continuity_notes(series_bible_id);
CREATE INDEX IF NOT EXISTS idx_continuity_notes_type ON continuity_notes(note_type);
CREATE INDEX IF NOT EXISTS idx_continuity_notes_severity ON continuity_notes(severity);
CREATE INDEX IF NOT EXISTS idx_continuity_notes_status ON continuity_notes(status);
CREATE INDEX IF NOT EXISTS idx_continuity_notes_episode_id ON continuity_notes(episode_id);
CREATE INDEX IF NOT EXISTS idx_continuity_notes_scene_id ON continuity_notes(scene_id);

CREATE INDEX IF NOT EXISTS idx_character_knowledge_character_id ON character_knowledge(character_id);
CREATE INDEX IF NOT EXISTS idx_character_knowledge_script_id ON character_knowledge(script_id);
CREATE INDEX IF NOT EXISTS idx_character_knowledge_type ON character_knowledge(knowledge_type);
CREATE INDEX IF NOT EXISTS idx_character_knowledge_acquired_episode ON character_knowledge(acquired_episode_id);
CREATE INDEX IF NOT EXISTS idx_character_knowledge_verification ON character_knowledge(verification_status);

CREATE INDEX IF NOT EXISTS idx_plot_threads_script_id ON plot_threads(script_id);
CREATE INDEX IF NOT EXISTS idx_plot_threads_bible_id ON plot_threads(series_bible_id);
CREATE INDEX IF NOT EXISTS idx_plot_threads_type ON plot_threads(thread_type);
CREATE INDEX IF NOT EXISTS idx_plot_threads_status ON plot_threads(status);
CREATE INDEX IF NOT EXISTS idx_plot_threads_priority ON plot_threads(priority);

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

-- Script Bible tables for continuity management and series tracking

-- Series information and bible metadata
CREATE TABLE IF NOT EXISTS series_bibles (
    id TEXT PRIMARY KEY,
    script_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    version INTEGER DEFAULT 1,
    created_by TEXT,
    status TEXT DEFAULT 'active', -- active, archived, draft
    bible_type TEXT DEFAULT 'series', -- series, movie, anthology
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
);

-- Character development profiles and arcs
CREATE TABLE IF NOT EXISTS character_profiles (
    id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    script_id TEXT NOT NULL,
    series_bible_id TEXT,

    -- Core character information
    full_name TEXT,
    age INTEGER,
    occupation TEXT,
    background TEXT,
    personality_traits TEXT,
    motivations TEXT,
    fears TEXT,
    goals TEXT,

    -- Physical description
    physical_description TEXT,
    distinguishing_features TEXT,

    -- Relationships
    family_background TEXT,
    relationship_status TEXT,

    -- Character arc tracking
    initial_state TEXT,
    character_arc TEXT,
    growth_trajectory TEXT,

    -- Continuity tracking
    first_appearance_episode_id TEXT,
    last_appearance_episode_id TEXT,
    total_appearances INTEGER DEFAULT 0,

    -- Metadata
    notes TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
    FOREIGN KEY (series_bible_id) REFERENCES series_bibles(id) ON DELETE CASCADE,
    FOREIGN KEY (first_appearance_episode_id) REFERENCES episodes(id) ON DELETE SET NULL,
    FOREIGN KEY (last_appearance_episode_id) REFERENCES episodes(id) ON DELETE SET NULL,
    UNIQUE(character_id, script_id)
);

-- World building and setting elements
CREATE TABLE IF NOT EXISTS world_elements (
    id TEXT PRIMARY KEY,
    script_id TEXT NOT NULL,
    series_bible_id TEXT,

    -- Element classification
    element_type TEXT NOT NULL, -- location, prop, concept, rule, technology, culture
    name TEXT NOT NULL,
    category TEXT, -- subcategory within type

    -- Description and rules
    description TEXT,
    rules_and_constraints TEXT,
    visual_description TEXT,

    -- Usage tracking
    first_introduced_episode_id TEXT,
    first_introduced_scene_id TEXT,
    usage_frequency INTEGER DEFAULT 0,
    importance_level INTEGER DEFAULT 1, -- 1-5 scale

    -- Relationships to other elements
    related_locations_json TEXT, -- JSON array of location IDs
    related_characters_json TEXT, -- JSON array of character IDs

    -- Continuity tracking
    continuity_notes TEXT,
    established_rules_json TEXT, -- JSON object of established rules/constraints

    -- Metadata
    notes TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
    FOREIGN KEY (series_bible_id) REFERENCES series_bibles(id) ON DELETE CASCADE,
    FOREIGN KEY (first_introduced_episode_id) REFERENCES episodes(id) ON DELETE SET NULL,
    FOREIGN KEY (first_introduced_scene_id) REFERENCES scenes(id) ON DELETE SET NULL
);

-- Timeline and chronology tracking
CREATE TABLE IF NOT EXISTS story_timelines (
    id TEXT PRIMARY KEY,
    script_id TEXT NOT NULL,
    series_bible_id TEXT,

    -- Timeline identification
    name TEXT NOT NULL,
    timeline_type TEXT DEFAULT 'main', -- main, flashback, alternate, parallel
    description TEXT,

    -- Temporal boundaries
    start_date TEXT, -- Story date (can be relative like "Day 1")
    end_date TEXT,
    duration_description TEXT,

    -- Reference information
    reference_episodes_json TEXT, -- JSON array of episode IDs covered
    reference_scenes_json TEXT, -- JSON array of scene IDs in this timeline

    -- Metadata
    notes TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
    FOREIGN KEY (series_bible_id) REFERENCES series_bibles(id) ON DELETE CASCADE
);

-- Timeline events for detailed chronology
CREATE TABLE IF NOT EXISTS timeline_events (
    id TEXT PRIMARY KEY,
    timeline_id TEXT NOT NULL,
    script_id TEXT NOT NULL,

    -- Event identification
    event_name TEXT NOT NULL,
    event_type TEXT DEFAULT 'plot', -- plot, character, world, backstory
    description TEXT,

    -- Temporal positioning
    story_date TEXT, -- Date within the story world
    relative_order INTEGER, -- Order within timeline
    duration_minutes INTEGER, -- Event duration

    -- References
    scene_id TEXT,
    episode_id TEXT,
    related_characters_json TEXT, -- JSON array of character IDs

    -- Continuity tracking
    establishes_json TEXT, -- JSON array of what this event establishes
    requires_json TEXT, -- JSON array of what this event requires
    affects_json TEXT, -- JSON array of what this event affects

    -- Metadata
    notes TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (timeline_id) REFERENCES story_timelines(id) ON DELETE CASCADE,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE SET NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE SET NULL
);

-- Continuity notes and tracking
CREATE TABLE IF NOT EXISTS continuity_notes (
    id TEXT PRIMARY KEY,
    script_id TEXT NOT NULL,
    series_bible_id TEXT,

    -- Note classification
    note_type TEXT NOT NULL, -- error, inconsistency, rule, reminder, question
    severity TEXT DEFAULT 'medium', -- low, medium, high, critical
    status TEXT DEFAULT 'open', -- open, resolved, ignored, deferred

    -- Content
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    suggested_resolution TEXT,

    -- References
    episode_id TEXT,
    scene_id TEXT,
    character_id TEXT,
    world_element_id TEXT,
    timeline_event_id TEXT,

    -- Related references (for cross-references)
    related_episodes_json TEXT, -- JSON array of episode IDs
    related_scenes_json TEXT, -- JSON array of scene IDs
    related_characters_json TEXT, -- JSON array of character IDs

    -- Tracking
    reported_by TEXT,
    assigned_to TEXT,
    resolution_notes TEXT,
    resolved_at TIMESTAMP,

    -- Metadata
    tags_json TEXT, -- JSON array of tags
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
    FOREIGN KEY (series_bible_id) REFERENCES series_bibles(id) ON DELETE CASCADE,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE SET NULL,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE SET NULL,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE SET NULL,
    FOREIGN KEY (world_element_id) REFERENCES world_elements(id) ON DELETE SET NULL,
    FOREIGN KEY (timeline_event_id) REFERENCES timeline_events(id) ON DELETE SET NULL
);

-- Character knowledge tracking for continuity
CREATE TABLE IF NOT EXISTS character_knowledge (
    id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    script_id TEXT NOT NULL,

    -- Knowledge details
    knowledge_type TEXT NOT NULL, -- fact, secret, skill, relationship, location, event
    knowledge_subject TEXT NOT NULL, -- What the knowledge is about
    knowledge_description TEXT,

    -- Acquisition tracking
    acquired_episode_id TEXT,
    acquired_scene_id TEXT,
    acquisition_method TEXT, -- witnessed, told, discovered, assumed

    -- Usage tracking
    first_used_episode_id TEXT,
    first_used_scene_id TEXT,
    usage_count INTEGER DEFAULT 0,

    -- Continuity validation
    should_know_before TEXT, -- Episode/scene where character should know this
    verification_status TEXT DEFAULT 'unverified', -- verified, unverified, violated

    -- Metadata
    confidence_level REAL DEFAULT 1.0, -- 0.0 to 1.0
    notes TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
    FOREIGN KEY (acquired_episode_id) REFERENCES episodes(id) ON DELETE SET NULL,
    FOREIGN KEY (acquired_scene_id) REFERENCES scenes(id) ON DELETE SET NULL,
    FOREIGN KEY (first_used_episode_id) REFERENCES episodes(id) ON DELETE SET NULL,
    FOREIGN KEY (first_used_scene_id) REFERENCES scenes(id) ON DELETE SET NULL
);

-- Plot threads and storyline tracking
CREATE TABLE IF NOT EXISTS plot_threads (
    id TEXT PRIMARY KEY,
    script_id TEXT NOT NULL,
    series_bible_id TEXT,

    -- Thread identification
    name TEXT NOT NULL,
    thread_type TEXT DEFAULT 'main', -- main, subplot, arc, mystery, romance
    priority INTEGER DEFAULT 1, -- 1-5 scale

    -- Thread details
    description TEXT,
    initial_setup TEXT,
    central_conflict TEXT,
    resolution TEXT,

    -- Status tracking
    status TEXT DEFAULT 'active', -- active, resolved, abandoned, suspended

    -- Episode tracking
    introduced_episode_id TEXT,
    resolved_episode_id TEXT,
    total_episodes_involved INTEGER DEFAULT 0,

    -- Character involvement
    primary_characters_json TEXT, -- JSON array of character IDs
    supporting_characters_json TEXT, -- JSON array of character IDs

    -- Scene tracking
    key_scenes_json TEXT, -- JSON array of scene IDs
    resolution_scenes_json TEXT, -- JSON array of scene IDs

    -- Metadata
    notes TEXT,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
    FOREIGN KEY (series_bible_id) REFERENCES series_bibles(id) ON DELETE CASCADE,
    FOREIGN KEY (introduced_episode_id) REFERENCES episodes(id) ON DELETE SET NULL,
    FOREIGN KEY (resolved_episode_id) REFERENCES episodes(id) ON DELETE SET NULL
);

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

-- Triggers for Script Bible tables
CREATE TRIGGER IF NOT EXISTS update_series_bibles_timestamp
    AFTER UPDATE ON series_bibles
    BEGIN
        UPDATE series_bibles SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_character_profiles_timestamp
    AFTER UPDATE ON character_profiles
    BEGIN
        UPDATE character_profiles SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_world_elements_timestamp
    AFTER UPDATE ON world_elements
    BEGIN
        UPDATE world_elements SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_story_timelines_timestamp
    AFTER UPDATE ON story_timelines
    BEGIN
        UPDATE story_timelines SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_timeline_events_timestamp
    AFTER UPDATE ON timeline_events
    BEGIN
        UPDATE timeline_events SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_continuity_notes_timestamp
    AFTER UPDATE ON continuity_notes
    BEGIN
        UPDATE continuity_notes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_character_knowledge_timestamp
    AFTER UPDATE ON character_knowledge
    BEGIN
        UPDATE character_knowledge SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_plot_threads_timestamp
    AFTER UPDATE ON plot_threads
    BEGIN
        UPDATE plot_threads SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
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
            "series_bibles",
            "character_profiles",
            "world_elements",
            "story_timelines",
            "timeline_events",
            "continuity_notes",
            "character_knowledge",
            "plot_threads",
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
            # Apply migration to version 5 (Script Bible and Continuity Management)
            logger.info(
                "Applying migration to version 5 (Script Bible and Continuity Management)"
            )

            # Use the same SQL from the main schema - extract the Script Bible tables portion
            # Get the Script Bible portion from the schema
            bible_migration_sql = f"""
            -- Script Bible tables for continuity management and series tracking
            {SCHEMA_SQL[SCHEMA_SQL.find("-- Script Bible tables") : SCHEMA_SQL.find("-- FTS triggers")]}
            """

            conn.executescript(bible_migration_sql)

            # Update schema version
            conn.execute(
                "INSERT INTO schema_info (version, description) VALUES (?, ?)",
                (5, "Added Script Bible and Continuity Management tables"),
            )
            conn.commit()

    return True
