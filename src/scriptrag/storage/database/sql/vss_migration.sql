-- Migration SQL for SQLite-vec VSS support
-- Creates embedding storage tables for scenes and bible chunks

-- Scene embeddings table
CREATE TABLE IF NOT EXISTS scene_embeddings (
    scene_id INTEGER PRIMARY KEY,
    embedding_model TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);

-- Bible embeddings table (main storage)
CREATE TABLE IF NOT EXISTS bible_embeddings (
    chunk_id INTEGER PRIMARY KEY,
    embedding_model TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chunk_id) REFERENCES bible_chunks(id) ON DELETE CASCADE
);

-- Bible chunk embeddings table (for compatibility)
CREATE TABLE IF NOT EXISTS bible_chunk_embeddings (
    chunk_id INTEGER PRIMARY KEY,
    embedding_model TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chunk_id) REFERENCES bible_chunks(id) ON DELETE CASCADE
);

-- Metadata table for tracking embeddings
CREATE TABLE IF NOT EXISTS embedding_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id, embedding_model)
);

-- Indexes for efficient querying by model
CREATE INDEX IF NOT EXISTS idx_scene_embeddings_model
    ON scene_embeddings(embedding_model);

CREATE INDEX IF NOT EXISTS idx_bible_embeddings_model
    ON bible_embeddings(embedding_model);

CREATE INDEX IF NOT EXISTS idx_bible_chunk_embeddings_model
    ON bible_chunk_embeddings(embedding_model);

CREATE INDEX IF NOT EXISTS idx_embedding_metadata_entity
    ON embedding_metadata(entity_type, entity_id);
