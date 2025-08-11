-- Script Bible Database Schema Extension
-- This file extends the ScriptRAG database with script bible content
-- Version: 1.0.0

-- Script Bibles table: stores metadata about script bible documents
CREATE TABLE IF NOT EXISTS script_bibles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_hash TEXT NOT NULL, -- Hash of the file content for change detection
    metadata JSON,
    FOREIGN KEY (script_id) REFERENCES scripts (id) ON DELETE CASCADE,
    UNIQUE (script_id, file_path)
);

-- Create indexes for bible queries
CREATE INDEX IF NOT EXISTS idx_script_bibles_script_id ON script_bibles (
    script_id
);
CREATE INDEX IF NOT EXISTS idx_script_bibles_file_hash ON script_bibles (
    file_hash
);

-- Bible Chunks table: stores individual sections/chunks from bible documents
CREATE TABLE IF NOT EXISTS bible_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bible_id INTEGER NOT NULL,
    chunk_number INTEGER NOT NULL, -- Order within the document
    heading TEXT, -- Section heading (from markdown headers)
    level INTEGER, -- Heading level (1-6 for H1-H6)
    content TEXT NOT NULL, -- The actual text content
    content_hash TEXT NOT NULL, -- Hash for embedding lookup
    parent_chunk_id INTEGER, -- For hierarchical structure
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON, -- Additional metadata (word count, etc.)
    FOREIGN KEY (bible_id) REFERENCES script_bibles (id) ON DELETE CASCADE,
    FOREIGN KEY (parent_chunk_id) REFERENCES bible_chunks (
        id
    ) ON DELETE SET NULL,
    UNIQUE (bible_id, chunk_number)
);

-- Create indexes for chunk queries
CREATE INDEX IF NOT EXISTS idx_bible_chunks_bible_id ON bible_chunks (bible_id);
CREATE INDEX IF NOT EXISTS idx_bible_chunks_content_hash ON bible_chunks (
    content_hash
);
CREATE INDEX IF NOT EXISTS idx_bible_chunks_parent ON bible_chunks (
    parent_chunk_id
);

-- Bible Embeddings table: stores embeddings for bible chunks
CREATE TABLE IF NOT EXISTS bible_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_path TEXT NOT NULL, -- Path to .npy file in Git LFS
    dimensions INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chunk_id) REFERENCES bible_chunks (id) ON DELETE CASCADE,
    UNIQUE (chunk_id, embedding_model)
);

-- Create indexes for embedding queries
CREATE INDEX IF NOT EXISTS idx_bible_embeddings_chunk_id ON bible_embeddings (
    chunk_id
);

-- Bible Cross-References table: links bible content to scenes/characters
CREATE TABLE IF NOT EXISTS bible_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL,
    reference_type TEXT NOT NULL, -- 'scene', 'character', 'location', etc.
    reference_id INTEGER NOT NULL, -- ID in the referenced table
    confidence REAL DEFAULT 1.0, -- Relevance/confidence score
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (chunk_id) REFERENCES bible_chunks (id) ON DELETE CASCADE,
    UNIQUE (chunk_id, reference_type, reference_id)
);

-- Create indexes for reference queries
CREATE INDEX IF NOT EXISTS idx_bible_references_chunk_id ON bible_references (
    chunk_id
);
CREATE INDEX IF NOT EXISTS idx_bible_references_type ON bible_references (
    reference_type, reference_id
);

-- Update triggers for timestamps
CREATE TRIGGER IF NOT EXISTS update_script_bibles_timestamp
AFTER UPDATE ON script_bibles
BEGIN
UPDATE script_bibles SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS update_bible_chunks_timestamp
AFTER UPDATE ON bible_chunks
BEGIN
UPDATE bible_chunks SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS update_bible_embeddings_timestamp
AFTER UPDATE ON bible_embeddings
BEGIN
UPDATE bible_embeddings SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS update_bible_references_timestamp
AFTER UPDATE ON bible_references
BEGIN
UPDATE bible_references SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;
