# ScriptRAG v2 Architecture

This document describes the architecture of ScriptRAG v2 using Fundamental Modeling Concepts (FMC).

## Overview

ScriptRAG v2 is a Git-native screenplay analysis system that combines version control with intelligent content extraction and search capabilities. All screenplay content and metadata are stored in Fountain files with structured data in boneyard sections, while embeddings are managed through Git LFS.

## System Components (Actors and Places)

### Actors (Active Components)

#### 1. **Fountain Parser**

- **Purpose**: Extracts scenes, dialogue, and boneyard metadata from Fountain files
- **Input**: Raw Fountain text
- **Output**: Structured scene objects with metadata
- **Responsibilities**:
  - Parse standard Fountain syntax
  - Extract boneyard JSON metadata
  - Calculate content hashes for scenes

#### 2. **Content Extractor**

- **Purpose**: Analyzes scene content to extract semantic information
- **Input**: Parsed scene objects
- **Output**: Structured metadata (characters, props, emotions, themes)
- **Responsibilities**:
  - Interface with LLM for content analysis
  - Generate structured extraction prompts
  - Validate and normalize extracted data

#### 3. **Embedding Generator**

- **Purpose**: Creates vector representations of scenes
- **Input**: Scene text and metadata
- **Output**: Numpy arrays of embeddings
- **Responsibilities**:
  - Generate embeddings via LLM API
  - Compress and optimize vector storage
  - Handle batching for efficiency

#### 4. **Git Synchronizer**

- **Purpose**: Manages Git operations and hooks
- **Input**: File system events, Git hooks
- **Output**: Updated Fountain files with boneyard data
- **Responsibilities**:
  - Detect changed scenes in commits
  - Trigger processing pipeline
  - Manage Git LFS for embeddings

#### 5. **Database Indexer**

- **Purpose**: Maintains searchable database from Fountain files
- **Input**: Fountain files with boneyard metadata
- **Output**: Updated SQLite database
- **Responsibilities**:
  - Parse all Fountain files in repository
  - Update only changed content (via hash comparison)
  - Maintain search indices

#### 6. **Query Engine**

- **Purpose**: Enables semantic and structured search
- **Input**: User queries
- **Output**: Ranked search results
- **Responsibilities**:
  - Vector similarity search
  - Structured metadata filtering
  - Result ranking and presentation

### Places (Storage Components)

#### 1. **Git Repository**

- **Content**:
  - Fountain files with boneyard metadata
  - Git LFS pointers for embeddings
  - Configuration files
- **Characteristics**:
  - Version controlled
  - Branch-aware
  - Merge-friendly

#### 2. **Embedding Storage (Git LFS)**

- **Content**:
  - Numpy arrays of scene embeddings
  - Named by content hash
- **Format**: `embeddings/{content_hash}.npy`
- **Characteristics**:
  - Immutable (content-addressed)
  - Deduplicated
  - Efficiently stored

#### 3. **Local Database**

- **Content**:
  - Parsed scene data
  - Metadata indices
  - Vector indices (via SQLite-vss)
- **Location**: `.scriptrag/cache.db` (outside Git)
- **Characteristics**:
  - Branch-specific
  - Reconstructible from Fountain files
  - Optimized for search

#### 4. **Boneyard Metadata**

- **Content**: JSON structures within Fountain comments
- **Format**: `/* SCRIPTRAG-META-START ... SCRIPTRAG-META-END */`
- **Stored Data**:
  - Content hash
  - Extracted metadata
  - Embedding references
  - Processing timestamp

## Data Model

### Core Entities

#### Scene

- **Attributes**:
  - content_hash (primary identifier)
  - type (INT/EXT)
  - location
  - time_of_day
  - action_text
  - dialogue_lines
- **Relations**:
  - belongs_to → Script
  - has_many → Character Appearances
  - has_one → Embedding
  - follows/precedes → Scene (sequence)

#### Script

- **Attributes**:
  - file_path (relative to repo root)
  - title
  - format_type (feature/tv)
  - season_number (for TV series)
  - episode_number (for TV series)
  - movie_number (for feature series, e.g., Bond films)
  - last_modified
- **Relations**:
  - has_many → Scenes
  - belongs_to → Series (optional)

#### Series

- **Attributes**:
  - series_id (unique identifier)
  - title
  - type (tv/feature)
  - created_at
- **Relations**:
  - has_many → Scripts
  - has_many → Characters

#### Character

- **Attributes**:
  - character_id (series + name composite)
  - name (normalized)
  - aliases (array)
  - bible_path (relative path to .md file)
  - bible_embedding (Git LFS reference)
- **Relations**:
  - belongs_to → Series (unique per series)
  - appears_in → Scenes
  - speaks → Dialogue Lines
  - has_one → Character Bible (markdown file)

#### Dialogue Line

- **Attributes**:
  - text
  - character_name
  - parenthetical (optional)
- **Relations**:
  - belongs_to → Scene
  - spoken_by → Character

#### Extracted Metadata

- **Attributes**:
  - content_hash (links to Scene)
  - characters_present (array)
  - props (array)
  - emotional_tone
  - themes (array)
  - story_function
- **Relations**:
  - describes → Scene

#### Embedding

- **Attributes**:
  - content_hash (links to Scene)
  - file_path (Git LFS reference)
  - dimensions
  - model_version
- **Relations**:
  - represents → Scene

### Relationships Flow

```text
Series ←──has_many──→ Script
   ↓                     ↓
has_many             has_many
   ↓                     ↓
Character              Scene
   ↓                     ↓
has_one              has_one
   ↓                     ↓
Bible               Embedding
   ↓                     ↓
stored_in           stored_in
   ↓                     ↓
Git Repo            Git LFS

Scene ←──appears_in──→ Character
  ↓                        ↓
has_many                speaks
  ↓                        ↓
Dialogue ←────spoken_by────┘

Scene ←───described_by───→ Metadata
  ↓
follows/precedes
  ↓
Scene
```

## Required Integrations

### 1. **Git Integration**

- **Git Hooks**:
  - `pre-commit`: Process changed scenes
  - `post-checkout`: Switch database context
  - `post-merge`: Reindex affected files
- **Git LFS**: Store and track embedding files
- **Git Library**: For programmatic repository access

### 2. **LLM Integration**

- **API Requirements**:
  - OpenAI-compatible endpoint
  - Embedding generation capability
  - Text completion for extraction
- **Supported Providers**:
  - Local: LMStudio, Ollama
  - Cloud: OpenAI, Anthropic

### 3. **Database Integration**

- **SQLite**: Primary storage with JSON support
- **SQLite-vss**: Vector similarity search extension
- **Requirements**:
  - SQLite 3.38+ (JSON operators)
  - Vector index support

### 4. **File System Integration**

- **Watch Capabilities**: Monitor Fountain file changes
- **Path Management**: Handle cross-platform paths
- **Atomic Operations**: Ensure data consistency

## Processing Flow

```text
1. User edits scene in Fountain file
     ↓
2. Git pre-commit hook activates
     ↓
3. Changed scenes detected (via content hash)
     ↓
4. For each changed scene:
   a. Content Extractor → LLM → Metadata
   b. Embedding Generator → LLM → Vectors
   c. Store embeddings in Git LFS
   d. Update boneyard in Fountain file
     ↓
5. Commit proceeds with updated files
     ↓
6. Database Indexer updates local cache
     ↓
7. Scene ready for search/analysis
```

## Design Principles

1. **Git-Native**: Everything versioned, branch-aware, merge-friendly
2. **Progressive Enhancement**: Fountain files remain valid without ScriptRAG
3. **Content-Addressed**: Hashes as identifiers prevent duplication
4. **Lazy Processing**: Only process what changes
5. **Reconstructible**: Database can be rebuilt from Fountain files
6. **Local-First**: No required cloud dependencies

## SQLite JSON Storage

SQLite provides robust JSON support that enables storing complete scene structures as documents while maintaining query performance.

### Database Schema

```sql
-- Main scenes table with full JSON document
CREATE TABLE scenes (
    content_hash TEXT PRIMARY KEY,
    script_path TEXT NOT NULL,
    scene_number INTEGER,
    scene_data JSON NOT NULL,  -- Complete scene structure
    embedding_vector BLOB,     -- Vector data (or use separate table)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Generated columns for frequently queried fields
    location TEXT GENERATED ALWAYS AS (json_extract(scene_data, '$.location')) STORED,
    scene_type TEXT GENERATED ALWAYS AS (json_extract(scene_data, '$.type')) STORED,
    characters TEXT GENERATED ALWAYS AS (json_extract(scene_data, '$.extracted.characters')) STORED
);

-- Scripts table
CREATE TABLE scripts (
    file_path TEXT PRIMARY KEY,
    title TEXT,
    series_id TEXT,
    metadata JSON,  -- Includes season/episode/movie numbers
    last_synced TIMESTAMP,
    FOREIGN KEY (series_id) REFERENCES series(series_id)
);

-- Series table
CREATE TABLE series (
    series_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    type TEXT CHECK (type IN ('tv', 'feature')),
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Characters table
CREATE TABLE characters (
    character_id TEXT PRIMARY KEY,  -- {series_id}:{character_name}
    series_id TEXT NOT NULL,
    name TEXT NOT NULL,
    aliases JSON,  -- Array of alternate names
    bible_path TEXT,  -- Path to markdown file
    bible_embedding_path TEXT,  -- Git LFS reference
    metadata JSON,
    FOREIGN KEY (series_id) REFERENCES series(series_id),
    UNIQUE (series_id, name)
);

-- Indexes for performance
CREATE INDEX idx_scenes_script ON scenes(script_path);
CREATE INDEX idx_scenes_location ON scenes(location);
CREATE INDEX idx_scenes_characters ON scenes(characters);
CREATE INDEX idx_characters_series ON characters(series_id);
```

### Example Scene JSON Structure

```json
{
    "content_hash": "a3f5c9b8d7e2f1a4",  // pragma: allowlist secret
    "type": "INT",
    "location": "COFFEE SHOP",
    "time": "DAY",
    "scene_number": 1,
    "page_number": 1,
    "content": {
        "action": "The shop buzzes with morning energy. SARAH (30s, exhausted) stumbles to the counter.",
        "dialogue": [
            {
                "character": "SARAH",
                "lines": "Triple shot, no questions.",
                "parenthetical": "desperate"
            }
        ]
    },
    "extracted": {
        "characters": ["SARAH", "BARISTA"],
        "character_details": {
            "SARAH": {
                "age": "30s",
                "traits": ["exhausted", "desperate"]
            }
        },
        "props": ["coffee cup", "counter"],
        "emotional_tone": "comedic desperation",
        "themes": ["exhaustion", "routine"],
        "story_function": "character introduction"
    },
    "embeddings": {
        "scene": "embeddings/a3f5c9b8d7e2f1a4.npy"
    },
    "metadata": {
        "last_processed": "2024-01-15T10:30:00Z",
        "llm_model": "gpt-4",
        "extractor_version": "1.0"
    }
}
```

### JSON Query Examples

```sql
-- Find all scenes with a specific character
SELECT scene_data FROM scenes
WHERE json_extract(scene_data, '$.extracted.characters') LIKE '%SARAH%';

-- Get all coffee shop scenes
SELECT * FROM scenes
WHERE json_extract(scene_data, '$.location') LIKE '%COFFEE%';

-- Find scenes by emotional tone
SELECT * FROM scenes
WHERE json_extract(scene_data, '$.extracted.emotional_tone') = 'comedic desperation';

-- Join scenes with characters
SELECT
    s.content_hash,
    s.location,
    c.name,
    c.bible_path
FROM scenes s, json_each(s.scene_data, '$.extracted.characters') je
JOIN characters c ON c.name = je.value
WHERE c.series_id = 'breaking-bad';
```

## Configuration Points

- **LLM Endpoint**: Configurable API URL and credentials
- **Processing Rules**: Which scenes to process, extraction prompts
- **Storage Paths**: Database location, embedding directory
- **Git Hooks**: Enable/disable automatic processing
- **Model Selection**: Embedding model, extraction model
