-- Add last_read_at column to scenes table for timestamp-based validation
-- This replaces the complex token system with simple timestamp tracking

ALTER TABLE scenes ADD COLUMN last_read_at TIMESTAMP;

-- Update schema version
INSERT INTO schema_version (version, description)
VALUES (2, 'Added last_read_at to scenes table for simplified validation');
