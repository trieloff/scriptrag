-- VSS (Vector Similarity Search) Tables Schema
-- This file creates the VSS-related tables for ScriptRAG
-- Version: 1.0.0

-- Scene Embeddings table: stores vector embeddings for scenes
CREATE TABLE IF NOT EXISTS scene_embeddings (
    scene_id INTEGER PRIMARY KEY,
    embedding_model TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scene_id) REFERENCES scenes (id) ON DELETE CASCADE
);

-- Create index for scene embeddings
CREATE INDEX IF NOT EXISTS idx_scene_embeddings_model
ON scene_embeddings (embedding_model);

-- Bible Embeddings table: stores vector embeddings for bible chunks
-- Note: This is separate from the bible_embeddings table in bible_schema.sql
-- which stores paths to .npy files. This table stores actual embedding BLOBs
-- for VSS operations.
CREATE TABLE IF NOT EXISTS bible_chunk_embeddings (
    chunk_id INTEGER PRIMARY KEY,
    embedding_model TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chunk_id) REFERENCES bible_chunks (id) ON DELETE CASCADE
);

-- Create index for bible chunk embeddings
CREATE INDEX IF NOT EXISTS idx_bible_chunk_embeddings_model
ON bible_chunk_embeddings (embedding_model);

-- Embedding Metadata table: tracks metadata about all embeddings
CREATE TABLE IF NOT EXISTS embedding_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,  -- 'scene', 'bible_chunk', etc.
    entity_id INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (entity_type, entity_id, embedding_model)
);

-- Create indexes for metadata queries
CREATE INDEX IF NOT EXISTS idx_embedding_metadata_entity
ON embedding_metadata (entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_embedding_metadata_model
ON embedding_metadata (embedding_model);

-- Update triggers for VSS timestamps
CREATE TRIGGER IF NOT EXISTS update_scene_embeddings_timestamp
AFTER UPDATE ON scene_embeddings
BEGIN
UPDATE scene_embeddings SET updated_at = CURRENT_TIMESTAMP
WHERE scene_id = new.scene_id;
END;

CREATE TRIGGER IF NOT EXISTS update_bible_chunk_embeddings_timestamp
AFTER UPDATE ON bible_chunk_embeddings
BEGIN
UPDATE bible_chunk_embeddings SET updated_at = CURRENT_TIMESTAMP
WHERE chunk_id = new.chunk_id;
END;

CREATE TRIGGER IF NOT EXISTS update_embedding_metadata_timestamp
AFTER UPDATE ON embedding_metadata
BEGIN
UPDATE embedding_metadata SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;
