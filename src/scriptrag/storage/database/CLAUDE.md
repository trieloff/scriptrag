# SQLite Database Storage Component

This directory implements SQLite database operations for storing and querying scenes, scripts, characters, and series data with JSON support.

## Architecture Role

Database Storage is a **storage backend** that:

- Stores structured scene data with JSON documents
- Maintains relationships between entities
- Provides full-text and vector search capabilities
- Ensures ACID compliance for data integrity

## Key Responsibilities

1. **Data Persistence**
   - Store scenes as JSON documents
   - Maintain script/series/character relationships
   - Handle metadata and search indices

2. **Query Support**
   - Full-text search with FTS5
   - JSON path queries
   - Vector similarity search (with SQLite-vss)

3. **Performance**
   - Connection pooling
   - Query optimization
   - Index management

## Pre-Release Status & Migration Strategy

**IMPORTANT**: ScriptRAG is currently in pre-release. The database schema is subject to change, and **database migrations are NOT implemented**.

### Migration Philosophy

1. **No Migration Support**: During pre-release, breaking schema changes may occur without migration paths
2. **Rebuild on Change**: Users should expect to rebuild their database when upgrading
3. **Cache Database**: The SQLite database is a cache that can be regenerated from Fountain files
4. **Source of Truth**: Git repository with Fountain files is always the source of truth

### Handling Schema Changes

When the schema changes:

```bash
# Delete the old database
rm -rf .scriptrag/cache.db

# Rebuild from fountain files
scriptrag index --all
```

This approach is acceptable because:

- The database is a derived cache, not primary storage
- All data can be regenerated from Fountain files
- Simplifies pre-release development
- Avoids migration complexity before schema stabilizes

### Future Considerations

Once ScriptRAG reaches 1.0:

- Schema will be stabilized
- Migration system may be implemented
- Backward compatibility will be maintained

## Implementation Guidelines

```python
import sqlite3
from typing import List, Dict, Any, Optional
from pathlib import Path
from contextlib import contextmanager
import json
from datetime import datetime

from ...models import Scene, Script, Character, Series
from ...exceptions import StorageError, NotFoundError


class DatabaseStorage:
    """SQLite database operations with JSON support."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path(".scriptrag/cache.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_connection()
        self._init_schema()

    def _init_connection(self):
        """Initialize database connection with optimal settings."""
        self.conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,  # Allow multi-threaded access
            isolation_level=None  # Autocommit mode
        )

        # Enable optimizations
        self.conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=10000")  # 10MB cache
        self.conn.execute("PRAGMA temp_store=MEMORY")

        # Enable JSON functions
        self.conn.row_factory = sqlite3.Row

    @contextmanager
    def transaction(self):
        """Provide transaction context."""
        self.conn.execute("BEGIN")
        try:
            yield
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
```

## Schema Implementation

```python
def _init_schema(self):
    """Initialize database schema."""
    self.conn.executescript("""
        -- Scenes table with JSON document
        CREATE TABLE IF NOT EXISTS scenes (
            content_hash TEXT PRIMARY KEY,
            script_path TEXT NOT NULL,
            scene_number INTEGER,
            scene_data JSON NOT NULL,
            embedding_vector BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Generated columns for indexing
            location TEXT GENERATED ALWAYS AS
                (json_extract(scene_data, '$.location')) STORED,
            scene_type TEXT GENERATED ALWAYS AS
                (json_extract(scene_data, '$.type')) STORED,
            characters TEXT GENERATED ALWAYS AS
                (json_extract(scene_data, '$.extracted.characters')) STORED
        );

        -- Scripts table
        CREATE TABLE IF NOT EXISTS scripts (
            file_path TEXT PRIMARY KEY,
            title TEXT,
            series_id TEXT,
            metadata JSON,
            last_synced TIMESTAMP,
            FOREIGN KEY (series_id) REFERENCES series(series_id)
        );

        -- Series table
        CREATE TABLE IF NOT EXISTS series (
            series_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            type TEXT CHECK (type IN ('tv', 'feature')),
            metadata JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Characters table
        CREATE TABLE IF NOT EXISTS characters (
            character_id TEXT PRIMARY KEY,
            series_id TEXT NOT NULL,
            name TEXT NOT NULL,
            aliases JSON,
            bible_path TEXT,
            bible_embedding_path TEXT,
            metadata JSON,
            FOREIGN KEY (series_id) REFERENCES series(series_id),
            UNIQUE (series_id, name)
        );

        -- Full-text search
        CREATE VIRTUAL TABLE IF NOT EXISTS scenes_fts
        USING fts5(
            content_hash UNINDEXED,
            search_text,
            content=scenes,
            content_rowid=rowid
        );

        -- Indices
        CREATE INDEX IF NOT EXISTS idx_scenes_script
            ON scenes(script_path);
        CREATE INDEX IF NOT EXISTS idx_scenes_location
            ON scenes(location);
        CREATE INDEX IF NOT EXISTS idx_scenes_characters
            ON scenes(characters);
        CREATE INDEX IF NOT EXISTS idx_characters_series
            ON characters(series_id);
    """)
```

## Scene Operations

```python
def upsert_scene(self, scene_data: Dict[str, Any]) -> None:
    """Insert or update a scene."""
    self.conn.execute("""
        INSERT OR REPLACE INTO scenes (
            content_hash,
            script_path,
            scene_number,
            scene_data
        ) VALUES (?, ?, ?, json(?))
    """, (
        scene_data['content_hash'],
        scene_data['script_path'],
        scene_data.get('scene_number'),
        json.dumps(scene_data)
    ))

    # Update FTS index
    self._update_fts_index(scene_data)

def get_scene(self, content_hash: str) -> Dict[str, Any]:
    """Get scene by content hash."""
    result = self.conn.execute("""
        SELECT scene_data FROM scenes
        WHERE content_hash = ?
    """, (content_hash,)).fetchone()

    if not result:
        raise NotFoundError(f"Scene not found: {content_hash}")

    return json.loads(result['scene_data'])

def search_scenes(
    self,
    query: Optional[str] = None,
    filters: Optional[Dict] = None,
    limit: int = 10,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Search scenes with optional filters."""
    sql_parts = ["SELECT scene_data FROM scenes"]
    params = []

    # Add search condition
    if query:
        sql_parts.append("""
            JOIN scenes_fts ON scenes.rowid = scenes_fts.rowid
            WHERE scenes_fts MATCH ?
        """)
        params.append(query)
    else:
        sql_parts.append("WHERE 1=1")

    # Add filters
    if filters:
        filter_sql, filter_params = self._build_filters(filters)
        sql_parts.append(f"AND {filter_sql}")
        params.extend(filter_params)

    # Add pagination
    sql_parts.append("LIMIT ? OFFSET ?")
    params.extend([limit, offset])

    sql = " ".join(sql_parts)
    results = self.conn.execute(sql, params).fetchall()

    return [json.loads(row['scene_data']) for row in results]
```

## JSON Query Support

```python
def query_by_character(self, character_name: str) -> List[Dict]:
    """Find all scenes with a specific character."""
    results = self.conn.execute("""
        SELECT scene_data FROM scenes
        WHERE EXISTS (
            SELECT 1 FROM json_each(
                scene_data,
                '$.extracted.characters'
            )
            WHERE value = ?
        )
    """, (character_name,)).fetchall()

    return [json.loads(row['scene_data']) for row in results]

def query_by_metadata(
    self,
    json_path: str,
    value: Any
) -> List[Dict]:
    """Query by arbitrary JSON path."""
    results = self.conn.execute("""
        SELECT scene_data FROM scenes
        WHERE json_extract(scene_data, ?) = ?
    """, (json_path, value)).fetchall()

    return [json.loads(row['scene_data']) for row in results]

def aggregate_by_character(self) -> Dict[str, int]:
    """Count scenes per character."""
    results = self.conn.execute("""
        SELECT
            je.value as character_name,
            COUNT(*) as scene_count
        FROM scenes s,
        json_each(s.scene_data, '$.extracted.characters') je
        GROUP BY je.value
        ORDER BY scene_count DESC
    """).fetchall()

    return {row['character_name']: row['scene_count']
            for row in results}
```

## Transaction Management

```python
def bulk_upsert_scenes(
    self,
    scenes: List[Dict[str, Any]]
) -> None:
    """Bulk insert/update scenes in a transaction."""
    with self.transaction():
        for scene_data in scenes:
            self.upsert_scene(scene_data)

def update_script_metadata(
    self,
    file_path: str,
    metadata: Dict[str, Any]
) -> None:
    """Update script metadata atomically."""
    with self.transaction():
        # Update script
        self.conn.execute("""
            UPDATE scripts
            SET metadata = json(?),
                last_synced = CURRENT_TIMESTAMP
            WHERE file_path = ?
        """, (json.dumps(metadata), file_path))

        # Update related scenes if needed
        if 'series_id' in metadata:
            self.conn.execute("""
                UPDATE scenes
                SET scene_data = json_set(
                    scene_data,
                    '$.series_id',
                    ?
                )
                WHERE script_path = ?
            """, (metadata['series_id'], file_path))
```

## Performance Optimization

```python
def _update_fts_index(self, scene_data: Dict) -> None:
    """Update full-text search index."""
    # Combine searchable text
    search_text = " ".join([
        scene_data.get('location', ''),
        scene_data.get('content', {}).get('action', ''),
        " ".join(
            d.get('lines', '')
            for d in scene_data.get('content', {}).get('dialogue', [])
        )
    ])

    self.conn.execute("""
        INSERT OR REPLACE INTO scenes_fts (
            content_hash,
            search_text
        ) VALUES (?, ?)
    """, (scene_data['content_hash'], search_text))

def analyze_and_optimize(self) -> None:
    """Run database optimization."""
    self.conn.execute("ANALYZE")
    self.conn.execute("VACUUM")

def get_stats(self) -> Dict[str, Any]:
    """Get database statistics."""
    stats = {}

    # Table sizes
    for table in ['scenes', 'scripts', 'characters', 'series']:
        count = self.conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
        stats[f"{table}_count"] = count

    # Database size
    stats['size_mb'] = self.db_path.stat().st_size / (1024 * 1024)

    return stats
```

## Error Handling

```python
def _handle_db_error(self, error: sqlite3.Error) -> None:
    """Convert SQLite errors to storage errors."""
    if isinstance(error, sqlite3.IntegrityError):
        raise StorageError(f"Integrity constraint violated: {error}")
    elif isinstance(error, sqlite3.OperationalError):
        raise StorageError(f"Database operation failed: {error}")
    else:
        raise StorageError(f"Database error: {error}")
```

## Testing

Key test scenarios:

- CRUD operations for all entities
- JSON query functionality
- Transaction rollback
- Concurrent access
- Performance with large datasets
- FTS search accuracy
- Schema migrations
