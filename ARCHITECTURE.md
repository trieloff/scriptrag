# ScriptRAG v2 Architecture

This document describes the architecture of ScriptRAG v2 using Fundamental Modeling Concepts (FMC).

## Overview

ScriptRAG v2 is a Git-native screenplay analysis system that combines version control with intelligent content extraction and search capabilities. All screenplay content and metadata are stored in Fountain files with structured data in boneyard sections, while embeddings are managed through Git LFS.

## System Architecture Overview

```mermaid
graph TB
    subgraph "User Interface"
        CLI[CLI Interface]
        MCP[MCP Server]
    end

    subgraph "Core"
        FP[Fountain Parser]
        CE[Content Extractor]
        EG[Embedding Generator]
        GS[Git Synchronizer]
        DI[Database Indexer]
        QE[Query Engine]
        BIA(Built-in Insight Agents)

        %% Channels (circles with triangles)
        ch1((▶))
        ch2((▶))
        ch3((▼))
        ch4((▶))
        ch5((▼))
        ch6((▶))
        ch7((▼))
        ch8((▶))
        ch9((▶))
        ch10((▼))
        ch11((▶))
        ch12((▶))
    end

    subgraph "Storage Layer"
        subgraph GR["Git Repository"]
            FF(Fountain Files)
            SB(Script Bible)
            CIA(Custom Insight Agents)
        end

        LFS(Git LFS)

        DB[(SQLite Database)]
        subgraph DB_contents["(Database Contents)"]
            Scenes(Scenes)
            Scripts(Scripts)
            Characters(Characters)
            Series(Series)
        end
    end

    subgraph "External Services"
        LLM[LLM API<br/>OpenAI REST / Claude Code SDK]
        ch_llm1((◀))
        ch_llm2((◀))
    end

    %% UI to Core channels
    CLI --> ch1
    ch1 --> FP
    CLI --> ch2
    ch2 --> QE
    CLI --> ch3
    ch3 --> GS
    MCP --> ch10
    ch10 --> FP
    MCP --> ch11
    ch11 --> QE

    %% Core actor-to-actor channels
    GS --> ch4
    ch4 --> FP
    FP --> ch5
    ch5 --> CE
    CE --> ch6
    ch6 --> EG
    GS --> ch7
    ch7 --> DI

    %% Actor to LLM channels
    CE --> ch_llm1
    ch_llm1 --> LLM
    EG --> ch_llm2
    ch_llm2 --> LLM

    %% Actor to Place connections (no channels needed)
    FF --> GS
    GS --> LFS
    BIA --> CE
    CIA --> CE
    EG --> LFS
    DI --> DB
    FF --> DI
    LFS --> DI
    DB --> QE

    %% Actor styling (rectangular boxes)
    style CLI fill:#b3d9ff,stroke:#333,stroke-width:4px
    style MCP fill:#b3d9ff,stroke:#333,stroke-width:4px
    style FP fill:#fff,stroke:#333,stroke-width:4px
    style CE fill:#fff,stroke:#333,stroke-width:4px
    style EG fill:#fff,stroke:#333,stroke-width:4px
    style GS fill:#fff,stroke:#333,stroke-width:4px
    style DI fill:#fff,stroke:#333,stroke-width:4px
    style QE fill:#fff,stroke:#333,stroke-width:4px
    style LLM fill:#ffccb3,stroke:#333,stroke-width:4px

    %% Place styling (pill-shaped with rounded corners)
    style BIA fill:#e6f3ff,stroke:#333,stroke-width:4px,rx:50,ry:50
    style LFS fill:#d4f1d4,stroke:#333,stroke-width:4px,rx:50,ry:50
    style DB fill:#fff5e6,stroke:#333,stroke-width:4px,rx:50,ry:50
    style FF fill:#e8f5e8,stroke:#333,stroke-width:4px,rx:40,ry:40
    style SB fill:#e8f5e8,stroke:#333,stroke-width:4px,rx:40,ry:40
    style CIA fill:#e8f5e8,stroke:#333,stroke-width:4px,rx:40,ry:40
    style Scenes fill:#ffe6cc,stroke:#333,stroke-width:4px,rx:30,ry:30
    style Scripts fill:#ffe6cc,stroke:#333,stroke-width:4px,rx:30,ry:30
    style Characters fill:#ffe6cc,stroke:#333,stroke-width:4px,rx:30,ry:30
    style Series fill:#ffe6cc,stroke:#333,stroke-width:4px,rx:30,ry:30

    %% Channel styling (small circles)
    style ch1 fill:#fff,stroke:#333,stroke-width:2px
    style ch2 fill:#fff,stroke:#333,stroke-width:2px
    style ch3 fill:#fff,stroke:#333,stroke-width:2px
    style ch4 fill:#fff,stroke:#333,stroke-width:2px
    style ch5 fill:#fff,stroke:#333,stroke-width:2px
    style ch6 fill:#fff,stroke:#333,stroke-width:2px
    style ch7 fill:#fff,stroke:#333,stroke-width:2px
    style ch8 fill:#fff,stroke:#333,stroke-width:2px
    style ch9 fill:#fff,stroke:#333,stroke-width:2px
    style ch10 fill:#fff,stroke:#333,stroke-width:2px
    style ch11 fill:#fff,stroke:#333,stroke-width:2px
    style ch12 fill:#fff,stroke:#333,stroke-width:2px
    style ch_llm1 fill:#fff,stroke:#333,stroke-width:2px
    style ch_llm2 fill:#fff,stroke:#333,stroke-width:2px

    %% Edge styling
    linkStyle default stroke:#333,stroke-width:2px
```

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
  - Load and execute Insight Agents
  - Validate output against JSON schemas
  - Aggregate results from multiple agents

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

#### 5. **Insight Agents Directory**

- **Content**: Markdown files defining extraction agents
- **Location**: `insight-agents/` in Git repository
- **Format**: Markdown with YAML frontmatter
- **Components**:
  - Agent metadata (name, property)
  - SQL context query
  - JSON output schema
  - LLM prompt template

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

```mermaid
erDiagram
    Series ||--o{ Script : "has_many"
    Series ||--o{ Character : "has_many"
    Script ||--o{ Scene : "has_many"
    Scene ||--|| Embedding : "has_one"
    Scene }o--o{ Character : "appears_in"
    Scene ||--o{ Dialogue : "has_many"
    Scene ||--|| Metadata : "described_by"
    Scene ||--o| Scene : "follows/precedes"
    Character ||--|| Bible : "has_one"
    Character ||--o{ Dialogue : "speaks"
    Dialogue }o--|| Character : "spoken_by"
    Bible ||--|| GitRepo : "stored_in"
    Embedding ||--|| GitLFS : "stored_in"

    Series {
        string series_id PK
        string title
        string type
        timestamp created_at
    }

    Script {
        string file_path PK
        string title
        string series_id FK
        string format_type
        int season_number
        int episode_number
        int movie_number
        timestamp last_modified
    }

    Scene {
        string content_hash PK
        string type
        string location
        string time_of_day
        text action_text
        array dialogue_lines
    }

    Character {
        string character_id PK
        string series_id FK
        string name
        array aliases
        string bible_path
        string bible_embedding
    }

    Dialogue {
        text text
        string character_name
        string parenthetical
    }

    Metadata {
        string content_hash FK
        array characters_present
        array props
        string emotional_tone
        array themes
        string story_function
    }

    Embedding {
        string content_hash FK
        string file_path
        int dimensions
        string model_version
    }

    Bible {
        string path
        text content
    }

    GitRepo {
        type storage
    }

    GitLFS {
        type storage
    }
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

- **API Endpoints** (two options):
  - **OpenAI-compatible REST API**: Direct HTTP calls to OpenAI or compatible endpoints
  - **Claude Code SDK**: Native integration when running within Claude Code environment
- **API Requirements**:
  - Embedding generation capability
  - Text completion for extraction
  - Structured output support (JSON mode)
- **Supported Providers**:
  - Local: LMStudio, Ollama (via OpenAI-compatible API)
  - Cloud: OpenAI, Anthropic (via REST API or Claude Code SDK)

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

```mermaid
flowchart TD
    A[User edits scene in Fountain file] --> B[Git pre-commit hook activates]
    B --> C[Changed scenes detected via content hash]
    C --> D{For each changed scene}

    D --> E[Content Extractor]
    E --> F[LLM Analysis]
    F --> G[Metadata Generated]

    D --> H[Embedding Generator]
    H --> I[LLM Embedding]
    I --> J[Vectors Generated]

    G --> K[Update boneyard in Fountain file]
    J --> L[Store embeddings in Git LFS]

    K --> M[Commit proceeds with updated files]
    L --> M

    M --> N[Database Indexer updates local cache]
    N --> O[Scene ready for search/analysis]

    style A fill:#e1f5e1
    style O fill:#e1f5e1
    style F fill:#ffe4b5
    style I fill:#ffe4b5
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

The database uses SQLite with JSON support to store complete scene structures as documents while maintaining query performance. The schema includes:

- **scenes**: Stores scene data with JSON documents, content hashes, and generated columns for frequently queried fields
- **scripts**: Tracks screenplay files with metadata including series associations
- **series**: Manages TV series or feature film franchises
- **characters**: Maintains character information with links to character bibles and embeddings

All tables use appropriate indexes for performance optimization.

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

The system supports various query patterns using SQLite's JSON functions:

- **Character search**: Find scenes containing specific characters using JSON path expressions
- **Location queries**: Search for scenes by location metadata
- **Emotional tone filtering**: Query scenes by their extracted emotional characteristics
- **Complex joins**: Combine scene data with character information through JSON relationships

## Configuration Points

- **LLM Endpoint**: Configurable API URL and credentials
- **Processing Rules**: Which scenes to process, extraction prompts
- **Storage Paths**: Database location, embedding directory
- **Git Hooks**: Enable/disable automatic processing
- **Model Selection**: Embedding model, extraction model

## System Surfaces

### Insight Agents - Extensible Content Extraction

Insight Agents provide a flexible, declarative way to extend the Content Extractor's capabilities without modifying code. Each agent is defined as a Markdown file that specifies what information to extract and how.

#### Agent File Structure

Insight Agents are Markdown files with:

- **YAML frontmatter**: Agent metadata (name, property, description)
- **Context Query section**: SQL to gather scene data
- **Output Schema section**: JSON Schema for validation
- **Analysis Prompt section**: Instructions for the LLM

See [Example Insight Agent: Emotional Beats](docs/example-insight-agent.md) for a complete example.

#### Agent Execution Flow

```mermaid
flowchart LR
    A[Content Extractor] --> B[Scan insight-agents/]
    B --> C[Load Agent Files]
    C --> D[Execute SQL Context Query]
    D --> E[Gather Scene Data]
    E --> F[Build LLM Prompt]
    F --> G[Send to LLM]
    G --> H[Receive Response]
    H --> I{Validate JSON Schema}
    I -->|Valid| J[Store in Metadata]
    I -->|Invalid| K[Log Error]
    J --> L[Return Results]
    K --> L

    style A fill:#b3d9ff
    style G fill:#ffccb3
    style J fill:#d4f1d4
```

#### Benefits

- **No Code Changes**: Add new extraction capabilities via markdown files
- **Domain Expertise**: Screenplay experts can contribute without coding
- **Testable**: Each agent can be tested independently
- **Versioned**: Agents are version-controlled with the project

### API Layer - Unified Interface

The API layer provides a consistent interface to ScriptRAG's capabilities, exposed through both CLI and MCP (Model Context Protocol). This layer enforces access control and ensures all operations go through validated pathways.

#### Core API Operations

```python
class ScriptRAGAPI:
    """Public API surface for ScriptRAG operations."""

    # Script Management
    def import_script(self, fountain_path: Path) -> ScriptID
    def list_scripts(self, series_id: Optional[str] = None) -> List[Script]
    def get_script(self, script_id: str) -> Script

    # Scene Operations  
    def list_scenes(self, script_id: str) -> List[Scene]
    def get_scene(self, content_hash: str) -> Scene
    def reprocess_scene(self, content_hash: str) -> Scene

    # Search
    def search_dialogue(self, query: str, limit: int = 10) -> List[SearchResult]
    def search_by_character(self, character: str) -> List[Scene]
    def semantic_search(self, query: str, limit: int = 10) -> List[Scene]

    # Character Management
    def list_characters(self, series_id: str) -> List[Character]
    def get_character(self, character_id: str) -> Character
    def update_character_bible(self, character_id: str, bible_path: Path) -> None

    # Series Management
    def create_series(self, title: str, type: str) -> Series
    def list_series(self) -> List[Series]

    # Insight Agents
    def list_agents(self) -> List[InsightAgent]
    def run_agent(self, agent_name: str, scene_hash: str) -> Dict[str, Any]
```

### CLI Interface

```bash
# Script operations
scriptrag script import path/to/script.fountain
scriptrag script list --series breaking-bad
scriptrag script show s01e01

# Scene operations
scriptrag scene list s01e01
scriptrag scene show <content-hash>
scriptrag scene reprocess <content-hash>

# Search operations
scriptrag search dialogue "I am the one who knocks"
scriptrag search character WALTER
scriptrag search semantic "tense confrontation"

# Character operations
scriptrag character list breaking-bad
scriptrag character show breaking-bad:WALTER
scriptrag character update-bible breaking-bad:WALTER docs/walter-white.md

# Agent operations
scriptrag agent list
scriptrag agent run emotional_beats <content-hash>
```

### MCP Protocol Interface

The MCP server exposes the same operations through the Model Context Protocol:

```typescript
// MCP Tools
{
  name: "scriptrag_import_script",
  description: "Import a Fountain screenplay",
  parameters: {
    fountain_path: { type: "string", description: "Path to fountain file" }
  }
}

{
  name: "scriptrag_search_dialogue",
  description: "Search for dialogue in scripts",
  parameters: {
    query: { type: "string", description: "Search query" },
    limit: { type: "number", description: "Max results", default: 10 }
  }
}

// MCP Resources
{
  name: "scriptrag://series/breaking-bad",
  description: "Breaking Bad series information",
  mimeType: "application/json"
}

{
  name: "scriptrag://character/breaking-bad:WALTER",
  description: "Walter White character bible",
  mimeType: "text/markdown"
}
```

### Design Principles

1. **Consistency**: CLI and MCP expose identical functionality
2. **Validation**: All inputs validated before processing
3. **Error Handling**: Graceful errors with actionable messages
4. **Discoverability**: Operations are self-documenting
5. **Security**: No direct database access, only through API
