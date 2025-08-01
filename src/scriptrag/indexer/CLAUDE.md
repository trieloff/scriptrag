# Database Indexer Component

This directory contains the database indexing system that maintains a searchable SQLite database from Fountain files and their metadata.

## Architecture Role

The Database Indexer is an **Actor** in the FMC architecture. It:

- Reads from Fountain Files and Git LFS (Places)
- Writes to SQLite Database (Place)
- Called by Git Synchronizer (through a channel)
- Maintains search indices and relationships

## Key Responsibilities

1. **Parse and Index Fountain Files**
   - Extract all scenes with boneyard metadata
   - Build full-text search indices
   - Maintain script/series relationships

2. **Update Only Changed Content**
   - Use content hashes for change detection
   - Incremental updates for performance
   - Handle deletions and moves

3. **Maintain Search Indices**
   - Vector indices for semantic search
   - Text indices for dialogue search
   - Metadata indices for filtering

## Implementation Guidelines

```python
import sqlite3
from typing import List, Dict, Optional, Set
from pathlib import Path
import json

from ..models import Script, Scene, Character, Series
from ..parser import FountainParser
from ..storage.database import DatabaseStorage
from ..exceptions import IndexingError


class DatabaseIndexer:
    """Index Fountain files into searchable database."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        parser: Optional[FountainParser] = None
    ):
        self.db = DatabaseStorage(db_path)
        self.parser = parser or FountainParser()
        self._init_schema()

    def index_all(self, fountain_dir: Path):
        """Full index of all Fountain files."""
        self.logger.info("Starting full index", path=fountain_dir)

        # Find all fountain files
        fountain_files = list(fountain_dir.rglob("*.fountain"))

        with self.db.transaction():
            # Clear existing data
            self.db.clear_all()

            # Index each file
            for file_path in fountain_files:
                try:
                    self.index_file(file_path)
                except Exception as e:
                    self.logger.error(
                        "Failed to index file",
                        file=file_path,
                        error=str(e)
                    )

    def index_file(self, file_path: Path) -> Script:
        """Index a single Fountain file."""
        # Parse file
        script = self.parser.parse_file(file_path)

        # Store script metadata
        self.db.upsert_script(script)

        # Index each scene
        for scene in script.scenes:
            self._index_scene(scene, script.id)

        # Extract and index characters
        self._index_characters(script)

        return script

    def update_incremental(self, changed_files: Set[Path]):
        """Update only changed files."""
        with self.db.transaction():
            for file_path in changed_files:
                if file_path.exists():
                    # Update existing or add new
                    self.index_file(file_path)
                else:
                    # Remove deleted file
                    self.db.delete_script_by_path(file_path)
```

## Scene Indexing

```python
def _index_scene(self, scene: Scene, script_id: str):
    """Index a single scene with all metadata."""
    # Parse boneyard metadata
    metadata = scene.boneyard_metadata or {}

    # Create scene document
    scene_doc = {
        "content_hash": scene.content_hash,
        "script_id": script_id,
        "scene_number": scene.number,
        "type": scene.type,
        "location": scene.location,
        "time": scene.time_of_day,
        "content": {
            "action": scene.action_text,
            "dialogue": [
                {
                    "character": d.character,
                    "lines": d.text,
                    "parenthetical": d.parenthetical
                }
                for d in scene.dialogue_lines
            ]
        },
        "extracted": metadata.get("extracted", {}),
        "embeddings": metadata.get("embeddings", {}),
        "metadata": {
            "last_indexed": datetime.utcnow().isoformat(),
            "version": "2.0"
        }
    }

    # Store in database
    self.db.upsert_scene(scene_doc)

    # Update search indices
    self._update_search_indices(scene)
```

## Character Extraction

```python
def _index_characters(self, script: Script):
    """Extract and index characters from script."""
    characters = {}

    for scene in script.scenes:
        # From dialogue
        for dialogue in scene.dialogue_lines:
            char_name = self._normalize_character_name(
                dialogue.character
            )
            characters[char_name] = characters.get(char_name, 0) + 1

        # From extracted metadata
        metadata = scene.boneyard_metadata or {}
        for char in metadata.get("extracted", {}).get("characters", []):
            char_name = self._normalize_character_name(char)
            characters[char_name] = characters.get(char_name, 0) + 1

    # Store characters
    for char_name, appearance_count in characters.items():
        self.db.upsert_character({
            "character_id": f"{script.series_id}:{char_name}",
            "series_id": script.series_id,
            "name": char_name,
            "appearance_count": appearance_count,
            "scripts": [script.id]
        })
```

## Search Index Management

```python
def _update_search_indices(self, scene: Scene):
    """Update various search indices."""
    # Full-text search index
    self._update_fts_index(scene)

    # Vector search index (if embeddings exist)
    if scene.embedding_path:
        self._update_vector_index(scene)

    # Metadata indices
    self._update_metadata_indices(scene)

def _update_fts_index(self, scene: Scene):
    """Update full-text search index."""
    # Combine searchable text
    search_text = " ".join([
        scene.location or "",
        scene.action_text or "",
        " ".join(d.text for d in scene.dialogue_lines)
    ])

    self.db.execute("""
        INSERT OR REPLACE INTO scenes_fts (
            content_hash,
            search_text
        ) VALUES (?, ?)
    """, (scene.content_hash, search_text))

def _update_vector_index(self, scene: Scene):
    """Update vector similarity index."""
    # Load embedding from LFS
    embedding = self._load_embedding(scene.embedding_path)

    # Store in vector index
    self.db.upsert_vector(
        scene.content_hash,
        embedding
    )
```

## Database Schema Management

```python
def _init_schema(self):
    """Initialize database schema if needed."""
    self.db.execute_script("""
        -- Main tables defined in architecture
        CREATE TABLE IF NOT EXISTS scenes (...);
        CREATE TABLE IF NOT EXISTS scripts (...);
        CREATE TABLE IF NOT EXISTS characters (...);
        CREATE TABLE IF NOT EXISTS series (...);

        -- Full-text search
        CREATE VIRTUAL TABLE IF NOT EXISTS scenes_fts
        USING fts5(
            content_hash UNINDEXED,
            search_text
        );

        -- Indices for performance
        CREATE INDEX IF NOT EXISTS idx_scenes_script
            ON scenes(script_id);
        CREATE INDEX IF NOT EXISTS idx_scenes_location
            ON scenes(location);
        CREATE INDEX IF NOT EXISTS idx_characters_series
            ON characters(series_id);
    """)
```

## Performance Optimizations

1. **Batch Operations**: Insert multiple scenes in one transaction
2. **Prepared Statements**: Reuse SQL statements
3. **Index Strategy**: Index only what's needed for queries
4. **Incremental Updates**: Only process changed content
5. **Connection Pooling**: Reuse database connections

## Error Handling

1. **Parse Errors**: Log and skip invalid files
2. **Database Errors**: Retry with backoff
3. **Missing Embeddings**: Index without vector data
4. **Schema Migrations**: Handle version upgrades

## Testing

Key test scenarios:

- Full indexing of test scripts
- Incremental update accuracy
- Character extraction
- Search index correctness
- Performance benchmarks
- Concurrent access

## Integration Points

- **Called by**: Git Synchronizer (via channel)
- **Reads from**: Fountain Files, Git LFS (Places)
- **Writes to**: SQLite Database (Place)
- **Uses**: Fountain Parser

## Configuration

```yaml
indexer:
  database_path: ".scriptrag/cache.db"
  batch_size: 100
  enable_fts: true
  enable_vector_index: true
  auto_vacuum: true
  wal_mode: true  # For concurrent access
```
