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
  - last_modified
- **Relations**:
  - has_many → Scenes
  - belongs_to → Series (optional)

#### Character

- **Attributes**:
  - name (normalized)
  - aliases (array)
- **Relations**:
  - appears_in → Scenes
  - speaks → Dialogue Lines

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
Script ←──has_many──→ Scene
   ↓                     ↓
belongs_to           has_one
   ↓                     ↓
Series              Embedding
                        ↓
                   stored_in
                        ↓
                   Git LFS

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

## Configuration Points

- **LLM Endpoint**: Configurable API URL and credentials
- **Processing Rules**: Which scenes to process, extraction prompts
- **Storage Paths**: Database location, embedding directory
- **Git Hooks**: Enable/disable automatic processing
- **Model Selection**: Embedding model, extraction model
