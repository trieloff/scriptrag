-- ScriptRAG Database Schema Initialization
-- This file creates the initial database schema for ScriptRAG
-- Version: 1.0.0

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Enable WAL mode for better concurrency
PRAGMA journal_mode = WAL;

-- Scripts table: stores screenplay metadata
CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT UNIQUE,
    format TEXT DEFAULT 'fountain',
    metadata JSON,
    UNIQUE (title, author)
);

-- Create index on title for faster searches
CREATE INDEX IF NOT EXISTS idx_scripts_title ON scripts (title);

-- Scenes table: stores individual scenes
CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id INTEGER NOT NULL,
    scene_number INTEGER NOT NULL,
    heading TEXT NOT NULL,
    location TEXT,
    time_of_day TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (script_id) REFERENCES scripts (id) ON DELETE CASCADE,
    UNIQUE (script_id, scene_number)
);

-- Create indexes for scene queries
CREATE INDEX IF NOT EXISTS idx_scenes_script_id ON scenes (script_id);
CREATE INDEX IF NOT EXISTS idx_scenes_location ON scenes (location);

-- Characters table: stores character information
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (script_id) REFERENCES scripts (id) ON DELETE CASCADE,
    UNIQUE (script_id, name)
);

-- Create index for character lookups
CREATE INDEX IF NOT EXISTS idx_characters_script_id ON characters (script_id);
CREATE INDEX IF NOT EXISTS idx_characters_name ON characters (name);

-- Dialogues table: stores character dialogues
CREATE TABLE IF NOT EXISTS dialogues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    dialogue_text TEXT NOT NULL,
    order_in_scene INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (scene_id) REFERENCES scenes (id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE CASCADE
);

-- Create indexes for dialogue queries
CREATE INDEX IF NOT EXISTS idx_dialogues_scene_id ON dialogues (scene_id);
CREATE INDEX IF NOT EXISTS idx_dialogues_character_id ON dialogues (
    character_id
);

-- Actions table: stores action lines
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL,
    action_text TEXT NOT NULL,
    order_in_scene INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (scene_id) REFERENCES scenes (id) ON DELETE CASCADE
);

-- Create index for action queries
CREATE INDEX IF NOT EXISTS idx_actions_scene_id ON actions (scene_id);

-- Character relationships table: stores relationships between characters
CREATE TABLE IF NOT EXISTS character_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id_1 INTEGER NOT NULL,
    character_id_2 INTEGER NOT NULL,
    relationship_type TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (character_id_1) REFERENCES characters (id) ON DELETE CASCADE,
    FOREIGN KEY (character_id_2) REFERENCES characters (id) ON DELETE CASCADE,
    CHECK (character_id_1 < character_id_2),
    UNIQUE (character_id_1, character_id_2, relationship_type)
);

-- Create indexes for relationship queries
CREATE INDEX IF NOT EXISTS idx_relationships_char1 ON character_relationships (
    character_id_1
);
CREATE INDEX IF NOT EXISTS idx_relationships_char2 ON character_relationships (
    character_id_2
);

-- Scene graph edges table: stores connections between scenes
CREATE TABLE IF NOT EXISTS scene_graph_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_scene_id INTEGER NOT NULL,
    to_scene_id INTEGER NOT NULL,
    edge_type TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (from_scene_id) REFERENCES scenes (id) ON DELETE CASCADE,
    FOREIGN KEY (to_scene_id) REFERENCES scenes (id) ON DELETE CASCADE,
    UNIQUE (from_scene_id, to_scene_id, edge_type)
);

-- Create indexes for graph queries
CREATE INDEX IF NOT EXISTS idx_scene_edges_from ON scene_graph_edges (
    from_scene_id
);
CREATE INDEX IF NOT EXISTS idx_scene_edges_to ON scene_graph_edges (
    to_scene_id
);

-- Embeddings table: stores vector embeddings for various entities
CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL, -- 'scene', 'character', 'dialogue', 'action'
    entity_id INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding BLOB NOT NULL, -- Store as binary for efficiency
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (entity_type, entity_id, embedding_model)
);

-- Create indexes for embedding queries
CREATE INDEX IF NOT EXISTS idx_embeddings_entity ON embeddings (
    entity_type, entity_id
);

-- Schema version table: track database schema version
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Insert initial schema version
INSERT INTO schema_version (version, description)
VALUES (1, 'Initial ScriptRAG database schema');

-- Create triggers to update timestamps
CREATE TRIGGER IF NOT EXISTS update_scripts_timestamp
AFTER UPDATE ON scripts
BEGIN
UPDATE scripts SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS update_scenes_timestamp
AFTER UPDATE ON scenes
BEGIN
UPDATE scenes SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS update_characters_timestamp
AFTER UPDATE ON characters
BEGIN
UPDATE characters SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS update_dialogues_timestamp
AFTER UPDATE ON dialogues
BEGIN
UPDATE dialogues SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS update_actions_timestamp
AFTER UPDATE ON actions
BEGIN
UPDATE actions SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS update_relationships_timestamp
AFTER UPDATE ON character_relationships
BEGIN
UPDATE character_relationships SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS update_scene_edges_timestamp
AFTER UPDATE ON scene_graph_edges
BEGIN
UPDATE scene_graph_edges SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS update_embeddings_timestamp
AFTER UPDATE ON embeddings
BEGIN
UPDATE embeddings SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;
