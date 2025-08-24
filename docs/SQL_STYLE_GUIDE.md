# SQL Style Guide for ScriptRAG

This document outlines the SQL formatting and style standards for the ScriptRAG project. All SQL files are automatically formatted using SQLFluff with these standards.

## Quick Reference

- **Dialect**: SQLite
- **Keywords**: UPPERCASE (SELECT, FROM, WHERE, etc.)
- **Functions**: UPPERCASE (COUNT, MAX, SUM, etc.)
- **Identifiers**: lowercase (table_name, column_name)
- **Line Length**: Maximum 120 characters
- **Indentation**: 4 spaces

## Auto-Formatting

### Command Line

```bash
# Check SQL formatting
make sql-lint

# Auto-format SQL files
make sql-fix
```

### Automatic Formatting

SQL files are automatically formatted in three ways:

1. **Pre-commit hooks**: Run on git commit
2. **Claude Code hooks**: Run after file edits in Claude Code
3. **CI/CD**: Validates formatting on pull requests

## Style Rules

### 1. Capitalization

```sql
-- ✅ GOOD: Keywords and functions in UPPERCASE
SELECT COUNT(*) AS total_scenes
FROM scenes
WHERE location IS NOT NULL;

-- ❌ BAD: Mixed or lowercase keywords
select count(*) as total_scenes
from scenes
where location is not null;
```

### 2. Table and Column Names

```sql
-- ✅ GOOD: Lowercase with underscores
CREATE TABLE character_relationships (
    character_id_1 INTEGER NOT NULL,
    character_id_2 INTEGER NOT NULL
);

-- ❌ BAD: CamelCase or mixed case
CREATE TABLE CharacterRelationships (
    CharacterID1 INTEGER NOT NULL,
    CharacterID2 INTEGER NOT NULL
);
```

### 3. Indentation

```sql
-- ✅ GOOD: Consistent 4-space indentation
CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id INTEGER NOT NULL,
    scene_number INTEGER NOT NULL,
    FOREIGN KEY (script_id) REFERENCES scripts (id)
);

-- ✅ GOOD: Multi-line SELECT with proper indentation
SELECT
    s.title,
    COUNT(sc.id) AS scene_count,
    COUNT(DISTINCT c.id) AS character_count
FROM scripts s
    LEFT JOIN scenes sc ON s.id = sc.script_id
    LEFT JOIN characters c ON s.id = c.script_id
WHERE s.format = 'fountain'
GROUP BY s.id, s.title
ORDER BY scene_count DESC;
```

### 4. Line Length

Keep lines under 120 characters. Break long lines logically:

```sql
-- ✅ GOOD: Long index name split appropriately
CREATE INDEX IF NOT EXISTS idx_relationships_char1
ON character_relationships (character_id_1);

-- ✅ GOOD: Long constraint split logically
CREATE TABLE dialogues (
    id INTEGER PRIMARY KEY,
    scene_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    FOREIGN KEY (scene_id) REFERENCES scenes (id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters (id)
        ON DELETE CASCADE
);
```

### 5. Commas

Trailing commas in column lists:

```sql
-- ✅ GOOD: Trailing comma positioning
SELECT
    title,
    author,
    created_at
FROM scripts;
```

### 6. Comments

```sql
-- ✅ GOOD: Clear, concise comments
-- Scripts table: stores screenplay metadata
CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    -- Using file_path as the unique constraint instead of (title, author)
    file_path TEXT UNIQUE NOT NULL
);
```

### 7. Foreign Keys

```sql
-- ✅ GOOD: Clear foreign key definitions
CREATE TABLE scenes (
    id INTEGER PRIMARY KEY,
    script_id INTEGER NOT NULL,
    FOREIGN KEY (script_id) REFERENCES scripts (id) ON DELETE CASCADE
);
```

### 8. Indexes

```sql
-- ✅ GOOD: Descriptive index names
CREATE INDEX IF NOT EXISTS idx_scripts_title ON scripts (title);
CREATE INDEX IF NOT EXISTS idx_scenes_script_id ON scenes (script_id);
```

## Common Patterns

### Creating Tables

```sql
CREATE TABLE IF NOT EXISTS table_name (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    column1 TEXT NOT NULL,
    column2 INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (column2) REFERENCES other_table (id) ON DELETE CASCADE
);
```

### Update Triggers

```sql
CREATE TRIGGER IF NOT EXISTS update_table_timestamp
AFTER UPDATE ON table_name
BEGIN
UPDATE table_name SET updated_at = CURRENT_TIMESTAMP
WHERE id = new.id;
END;
```

### Complex Queries

```sql
WITH scene_stats AS (
    SELECT
        script_id,
        COUNT(*) AS scene_count,
        COUNT(DISTINCT location) AS location_count
    FROM scenes
    GROUP BY script_id
)
SELECT
    s.title,
    s.author,
    ss.scene_count,
    ss.location_count
FROM scripts s
    JOIN scene_stats ss ON s.id = ss.script_id
WHERE ss.scene_count > 10
ORDER BY ss.scene_count DESC;
```

## SQLFluff Configuration

The project uses SQLFluff with the following key rules:

- **Dialect**: SQLite
- **Excluded Rules**: L034 (select wildcards), L044 (ambiguous column references)
- **Line Length**: 120 characters
- **Keyword Capitalization**: UPPERCASE
- **Function Capitalization**: UPPERCASE
- **Identifier Capitalization**: lowercase

Full configuration in `.sqlfluff` at project root.

## Enforcement

SQL formatting is enforced at multiple levels:

1. **Development**: `make sql-fix` auto-formats files
2. **Pre-commit**: Checks and fixes on commit
3. **CI/CD**: Blocks PRs with formatting violations
4. **Claude Code**: Auto-formats on file edit

## Migration and Schema Changes

When modifying database schema:

1. Follow the style guide for new SQL
2. Run `make sql-fix` before committing
3. Update schema version in `schema_version` table
4. Document changes in migration comments

## Examples from ScriptRAG

### Character Statistics Query

```sql
SELECT
    c.name AS character_name,
    COUNT(DISTINCT s.id) AS scene_count,
    COUNT(d.id) AS dialogue_count
FROM characters c
    LEFT JOIN dialogues d ON c.id = d.character_id
    LEFT JOIN scenes s ON d.scene_id = s.id
WHERE c.script_id = ?
GROUP BY c.id, c.name
ORDER BY dialogue_count DESC;
```

### Scene List Query

```sql
SELECT
    s.scene_number,
    s.heading,
    s.location,
    s.time_of_day,
    GROUP_CONCAT(DISTINCT c.name) AS characters
FROM scenes s
    LEFT JOIN dialogues d ON s.id = d.scene_id
    LEFT JOIN characters c ON d.character_id = c.id
WHERE s.script_id = ?
GROUP BY s.id
ORDER BY s.scene_number;
```

## Resources

- [SQLFluff Documentation](https://docs.sqlfluff.com/)
- [SQLite SQL Syntax](https://www.sqlite.org/lang.html)
- Project configuration: `.sqlfluff`
