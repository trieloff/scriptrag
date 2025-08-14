-- Migration 002: Handle duplicate scripts (TV series episodes)
-- This migration removes the unique constraint on (title, author) and adds
-- a new constraint that includes file_path to support multiple episodes
-- of the same TV series or different versions of the same script.

-- Step 1: Create new scripts table with updated constraints
CREATE TABLE scripts_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT UNIQUE,
    format TEXT DEFAULT 'fountain',
    metadata JSON,
    version INTEGER DEFAULT 1,
    is_current BOOLEAN DEFAULT TRUE,
    -- Remove the problematic unique constraint on (title, author)
    -- Now only file_path is unique, allowing multiple scripts
    CHECK (is_current IN (0, 1))
);

-- Step 2: Create indexes for the new table
CREATE INDEX idx_scripts_new_title ON scripts_new (title);
CREATE INDEX idx_scripts_new_title_author ON scripts_new (title, author);
CREATE INDEX idx_scripts_new_version ON scripts_new (title, author, version);
CREATE INDEX idx_scripts_new_current ON scripts_new (is_current);

-- Step 3: Copy data from old table to new table
INSERT INTO scripts_new (
    id, title, author, created_at, updated_at,
    file_path, format, metadata, version, is_current
)
SELECT
    scripts.id,
    scripts.title,
    scripts.author,
    scripts.created_at,
    scripts.updated_at,
    scripts.file_path,
    scripts.format,
    scripts.metadata,
    1, -- noqa: AL03
    1  -- noqa: AL03
FROM scripts;

-- Step 4: Drop the old table and rename the new one
DROP TABLE scripts;
ALTER TABLE scripts_new RENAME TO scripts;

-- Step 5: Recreate triggers for the scripts table
CREATE TRIGGER update_scripts_timestamp
AFTER UPDATE ON scripts
BEGIN
UPDATE scripts SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;

-- Step 6: Update schema version
INSERT INTO schema_version (version, description)
VALUES (
    2,
    'Remove unique constraint on (title, author) to support duplicate scripts'
);
