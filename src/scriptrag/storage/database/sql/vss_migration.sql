-- SQLite VSS Migration using sqlite-vec
-- This migration transforms the embeddings table to use virtual tables
-- for vector similarity search
-- Version: 4.0.0

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Enable WAL mode for better concurrency
PRAGMA journal_mode = WAL;

-- Load sqlite-vec extension (must be done at runtime in Python)
-- .load sqlite_vec

-- Drop the old embeddings table (we'll recreate it with VSS)
DROP TABLE IF EXISTS embeddings_old;
ALTER TABLE embeddings RENAME TO embeddings_old;

-- Create virtual table for scene embeddings using vec0
CREATE VIRTUAL TABLE IF NOT EXISTS scene_embeddings USING vec0(
    scene_id INTEGER PRIMARY KEY,
    embedding_model TEXT,
    embedding FLOAT[1536]  -- Default dimension for text-embedding-3-small
);

-- Create virtual table for bible chunk embeddings
CREATE VIRTUAL TABLE IF NOT EXISTS bible_embeddings USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    embedding_model TEXT,
    embedding FLOAT[1536]
);

-- Create virtual table for character embeddings
CREATE VIRTUAL TABLE IF NOT EXISTS character_embeddings USING vec0(
    character_id INTEGER PRIMARY KEY,
    embedding_model TEXT,
    embedding FLOAT[1536]
);

-- Create metadata table for tracking embedding information
CREATE TABLE IF NOT EXISTS embedding_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,  -- 'scene', 'bible_chunk', 'character'
    entity_id INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    lfs_path TEXT,  -- Optional path to Git LFS storage
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (entity_type, entity_id, embedding_model)
);

-- Create indexes for metadata lookups
CREATE INDEX IF NOT EXISTS idx_embedding_metadata_entity
ON embedding_metadata (entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_embedding_metadata_model
ON embedding_metadata (embedding_model);

-- Update schema version
UPDATE schema_version
SET version = 4,
    description = 'Added SQLite VSS support with sqlite-vec virtual tables',
    applied_at = CURRENT_TIMESTAMP
WHERE version = (SELECT MAX(version) FROM schema_version);

-- If no schema version exists, insert it
INSERT OR IGNORE INTO schema_version (version, description)
VALUES (4, 'Added SQLite VSS support with sqlite-vec virtual tables');

-- Create trigger to update metadata timestamps
CREATE TRIGGER IF NOT EXISTS update_embedding_metadata_timestamp
AFTER UPDATE ON embedding_metadata
BEGIN
    UPDATE embedding_metadata SET updated_at = CURRENT_TIMESTAMP
    WHERE id = new.id;
END;
