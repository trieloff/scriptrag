# ScriptRAG: A Graph-Based Screenwriting Assistant

[![81% Vibe_Coded](https://img.shields.io/badge/81%25-Vibe_Coded-ff69b4?style=for-the-badge&logo=zedindustries&logoColor=white)](https://github.com/trieloff/vibe-coded-badge-action)

![Vibe](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Ftrieloff%2Fscriptrag2%2Fmain%2Fvibe.json&query=%24.vibe&style=for-the-badge&logo=github&label=Vibe&color=ff69b4)

ScriptRAG is a novel screenwriting tool that combines Fountain parsing, graph databases, and local LLMs
to create an intelligent screenplay assistant using the GraphRAG (Graph + Retrieval-Augmented
Generation) pattern.

## Features

- **Fountain Parser**: Read and parse screenplays in Fountain format
- **Graph Database**: SQLite-based lightweight graph database for screenplay structure
- **Local LLM Integration**: Uses LMStudio for text generation and embeddings
- **Advanced Search**: Find shows, seasons, episodes, scenes, characters, locations, concepts, objects,
  and temporal points
- **Scene Management**: Order scenes by script order, temporal order, or logical dependencies
- **Scene Editing**: Update, delete, or inject new scenes while maintaining screenplay integrity
- **Script Bible Support**: Comprehensive continuity management with character development tracking,
  world-building documentation, timeline management, and cross-episode consistency validation

## Tech Stack

- **Language**: Python with uv package manager
- **Database**: SQLite as a graph database
- **LLM**: Local LLMs via LMStudio (OpenAI-compatible API at <http://localhost:1234/v1>)
- **Parser**: Fountain screenplay format parser
- **Pattern**: GraphRAG (Graph + Retrieval-Augmented Generation)
- **Interface**: MCP (Model Context Protocol) server for AI assistant integration

## Project Plan & Tasks

### Phase 1: Project Setup and Foundation

- [x] **1.1 Initialize Project Structure**
  - [x] Set up Python project with uv
  - [x] Create directory structure (src/, tests/, data/, docs/)
  - [x] Initialize git repository
  - [x] Create .gitignore for Python/uv projects
  - [x] Set up pyproject.TOML with dependencies

- [x] **1.2 Development Environment** *(5/5 complete)*
  - [x] Configure uv virtual environment
  - [x] Create requirements files (dev, prod)
  - [x] Set up pre-commit hooks
  - [x] Configure logging framework
  - [x] Create configuration management (config.YAML/env)

### Phase 2: Core Components

- [x] **2.1 Fountain Parser Integration**
  - [x] Research and evaluate Fountain parsing libraries
  - [x] Integrate Fountain parser (using Jouvence)
  - [x] Create data models for screenplay elements:
    - [x] Script/Show
    - [x] Season
    - [x] Episode
    - [x] Scene
    - [x] Character
    - [x] Location
    - [x] Action
    - [x] Dialogue
    - [x] Parenthetical
  - [x] Write unit tests for parser

- [x] **2.2 SQLite Graph Database Design**
  - [x] Design graph schema for screenplay structure
  - [x] Create tables for:
    - [x] Nodes (entities: scenes, characters, locations, etc.)
    - [x] Edges (relationships: FOLLOWS, APPEARS_IN, SPEAKS_TO, etc.)
    - [x] Properties (metadata for nodes and edges)
    - [x] Embeddings (vector storage for semantic search)
  - [x] Implement database initialization scripts
  - [x] Create database migration system

- [x] **2.3 Graph Database Interface**
  - [x] Implement graph operations:
    - [x] Add/update/delete nodes
    - [x] Add/update/delete edges
    - [x] Traverse graph (BFS/DFS)
    - [x] Find paths between nodes
    - [x] Calculate node centrality
  - [x] Create query builder for complex graph queries
  - [x] Implement transaction support

### Phase 3: LLM Integration

- [x] **3.1 LMStudio Client** *(5/5 complete)*
  - [x] Create OpenAI-compatible API client for any OpenAI-compatible endpoint
  - [x] Implement model listing and selection
  - [x] Create abstraction layer for:
    - [x] Text generation (with reasoning model support)
    - [x] Embeddings generation
  - [x] Add retry logic and error handling
  - [x] Implement factory functions and configuration integration

- [ ] **3.2 Embedding Pipeline**
  - [ ] Design embedding strategy for screenplay elements
  - [ ] Implement batch embedding generation
  - [ ] Create embedding storage in SQLite
  - [ ] Build similarity search functionality
  - [ ] Optimize for performance (chunking, async processing)

### Phase 4: GraphRAG Implementation

- [ ] **4.1 Knowledge Graph Construction**
  - [ ] Parse screenplays into graph structure
  - [ ] Extract entities and relationships
  - [ ] Enrich nodes with LLM-generated metadata
  - [ ] Build temporal graph layer
  - [ ] Create logical dependency graph

- [ ] **4.2 Graph Indexing**
  - [ ] Implement hierarchical indexing (show → season → episode → scene)
  - [ ] Create character relationship graphs
  - [ ] Build location-based scene graphs
  - [ ] Index temporal relationships
  - [ ] Generate concept and theme graphs

- [ ] **4.3 RAG Query Engine**
  - [ ] Design query language for screenplay searches
  - [ ] Implement multi-hop graph traversal
  - [ ] Create context assembly from graph neighborhoods
  - [ ] Build prompt templates for different query types
  - [ ] Integrate LLM for answer generation

### Phase 5: Scene Management Features

- [ ] **5.1 Scene Ordering**
  - [ ] Implement script order tracking
  - [ ] Build temporal order inference engine
  - [ ] Create logical dependency analyzer
  - [ ] Design UI/API for reordering scenes
  - [ ] Maintain consistency across orderings

- [ ] **5.2 Scene Operations**
  - [ ] **Update Scene**
    - [ ] Modify time/location metadata
    - [ ] Edit dialogue and action
    - [ ] Update character appearances
    - [ ] Propagate changes through graph
  - [ ] **Delete Scene**
    - [ ] Remove scene and update references
    - [ ] Handle dependency resolution
    - [ ] Maintain story continuity
  - [ ] **Inject Scene**
    - [ ] Insert new scenes at specified positions
    - [ ] Update all ordering systems
    - [ ] Validate logical consistency
    - [ ] Re-embed and index new content

### Phase 6: Search and Query Interface

- [ ] **6.1 Search Implementation**
  - [ ] Text-based search (dialogue, action)
  - [ ] Entity search (characters, locations)
  - [ ] Temporal search (time ranges, sequences)
  - [ ] Concept/theme search
  - [ ] Relationship search (character interactions)

- [ ] **6.2 Advanced Queries**
  - [ ] Multi-criteria search
  - [ ] Graph pattern matching
  - [ ] Semantic similarity search
  - [ ] Timeline visualization queries
  - [ ] Character arc analysis

### Phase 7: API and Interface

- [ ] **7.1 REST API**
  - [ ] Design OpenAPI specification
  - [ ] Implement FastAPI backend
  - [ ] Create endpoints for:
    - [ ] Script upload/parsing
    - [ ] Search operations
    - [ ] Scene management
    - [ ] Graph visualization
    - [ ] Export functionality

- [ ] **7.2 CLI Interface**
  - [ ] Create command-line tool using Click/Typer
  - [ ] Implement commands for all major operations
  - [ ] Add interactive mode for complex queries
  - [ ] Create batch processing capabilities

- [ ] **7.3 MCP Server**
  - [ ] Implement Model Context Protocol server
  - [ ] Create MCP tools for:
    - [ ] Script parsing and analysis
    - [ ] Scene search and retrieval
    - [ ] Character/location queries
    - [ ] Scene manipulation operations
    - [ ] Graph traversal and analysis
  - [ ] Define MCP resource schemas for:
    - [ ] Screenplay structure
    - [ ] Scene metadata
    - [ ] Character relationships
    - [ ] Timeline information
  - [ ] Implement MCP prompts for common tasks
  - [ ] Create MCP server configuration
  - [ ] Write MCP client examples
  - [ ] Integration with Claude and other MCP-compatible assistants

### Phase 8: Pluggable Mentors System 🎭

📋 **[Detailed Mentor System Documentation](MENTOR_SYSTEM.md)**
- [ ] **8.1 Mentor Infrastructure**
  - [ ] Mentor base classes and interfaces
  - [ ] Mentor registry and discovery system
  - [ ] Database schema extensions for mentor results
  - [ ] Mentor file format parsing and validation

- [ ] **8.2 Built-in Mentors**
  - [ ] Save the Cat mentor implementation
  - [ ] Hero's Journey mentor implementation
  - [ ] Three-Act structure mentor
  - [ ] Character Arc analysis mentor

- [ ] **8.3 Mentor Execution System**
  - [ ] CLI commands for mentor management
  - [ ] LLM integration for mentor analysis
  - [ ] Automated trigger system (script updates, manual requests)
  - [ ] Mentor result storage and history tracking

- [ ] **8.4 Advanced Mentor Features**
  - [ ] Custom mentor installation system
  - [ ] Mentor result visualization and trends
  - [ ] Collaborative mentor sharing
  - [ ] MCP server integration for mentors

### Phase 9: Testing and Optimization

- [ ] **9.1 Testing Suite**
  - [ ] Unit tests for all components
  - [ ] Integration tests for GraphRAG pipeline
  - [ ] Performance benchmarks
  - [ ] Test data generation (sample screenplays)
  - [ ] End-to-end testing scenarios

- [ ] **9.2 Performance Optimization**
  - [ ] Query optimization for graph traversals
  - [ ] Embedding cache optimization
  - [ ] Async processing for LLM calls
  - [ ] Database indexing strategy
  - [ ] Memory usage profiling

### Phase 10: Documentation and Deployment

- [ ] **10.1 Documentation**
  - [ ] API documentation
  - [ ] User guide for scriptwriters
  - [ ] Developer documentation
  - [ ] Example notebooks/tutorials
  - [ ] Architecture diagrams

- [ ] **10.2 Deployment**
  - [ ] Create Docker containerization
  - [ ] Write deployment scripts
  - [ ] Create backup/restore procedures
  - [ ] Performance monitoring setup
  - [ ] Create installation guide

### Phase 11: Script Bible and Continuity Management

- [ ] **11.1 Script Bible Foundation**
  - [ ] Design script bible data models:
    - [ ] Series/show overview and premise
    - [ ] Character development arcs and progression
    - [ ] World-building elements and rules
    - [ ] Timeline and continuity tracking
    - [ ] Tone and style guidelines
  - [ ] Create script bible database schema:
    - [ ] Bible metadata table (series info, premise, logline)
    - [ ] Character profiles table (backstory, traits, relationships)
    - [ ] World elements table (locations, rules, lore, concepts)
    - [ ] Timeline events table (chronological story events)
    - [ ] Continuity notes table (episode-by-episode tracking)
    - [ ] Style guidelines table (tone, voice, creative vision)
  - [ ] Implement script bible CRUD operations
  - [ ] Add script bible versioning and change tracking

- [ ] **11.2 Character Development System**
  - [ ] Enhanced character models:
    - [ ] Detailed backstory and history
    - [ ] Personality traits and psychological profiles
    - [ ] Character arc milestones and development tracking
    - [ ] Relationship matrices and dynamics
    - [ ] Dialogue voice patterns and speech characteristics
    - [ ] Goals, motivations, and internal conflicts
  - [ ] Character relationship tracking:
    - [ ] Dynamic relationship status changes
    - [ ] Conflict history between characters
    - [ ] Shared secrets and revelation tracking
    - [ ] Power dynamic evolution
    - [ ] Romantic relationship timelines
  - [ ] Character consistency validation:
    - [ ] Voice pattern analysis across scenes
    - [ ] Behavioral consistency checking
    - [ ] Knowledge progression validation
    - [ ] Character arc coherence analysis

- [ ] **11.3 World-Building and Lore Management**
  - [ ] World element models:
    - [ ] Location hierarchies and spatial relationships
    - [ ] Cultural and social structure documentation
    - [ ] Genre-specific rules (sci-fi tech, fantasy magic, etc.)
    - [ ] Historical events and background timeline
    - [ ] Mythology and legend documentation
  - [ ] Concept and object tracking:
    - [ ] Important objects and their significance
    - [ ] Recurring themes and motifs
    - [ ] Symbolic elements and meanings
    - [ ] Easter eggs and hidden connections
  - [ ] World consistency validation:
    - [ ] Rule adherence checking
    - [ ] Geographic continuity validation
    - [ ] Timeline consistency analysis
    - [ ] Cultural element coherence

- [ ] **11.4 Timeline and Continuity System**
  - [ ] Enhanced timeline management:
    - [ ] Chronological event ordering
    - [ ] Flashback/flash-forward documentation
    - [ ] Character age progression tracking
    - [ ] Seasonal/holiday continuity
    - [ ] Real-world time correlation
  - [ ] Continuity tracking:
    - [ ] Episode-by-episode continuity notes
    - [ ] Props and costume continuity
    - [ ] Character knowledge progression
    - [ ] Plot thread resolution tracking
    - [ ] Callback and reference opportunities
  - [ ] Consistency validation:
    - [ ] Timeline conflict detection
    - [ ] Character knowledge inconsistency alerts
    - [ ] Continuity error identification
    - [ ] Plot hole detection and reporting

- [ ] **11.5 Script Bible Interface and Tools**
  - [ ] CLI commands for script bible management:
    - [ ] Create and initialize script bible
    - [ ] Add/edit character profiles and arcs
    - [ ] Manage world elements and lore
    - [ ] Track timeline events and continuity
    - [ ] Generate continuity reports
  - [ ] MCP server integration:
    - [ ] Script bible query and search tools
    - [ ] Character development tracking
    - [ ] Continuity validation services
    - [ ] World-building assistance
  - [ ] Script bible export formats:
    - [ ] PDF series bible document
    - [ ] Character relationship charts
    - [ ] Timeline visualization
    - [ ] World map and location guides

- [ ] **11.6 Advanced Continuity Features**
  - [ ] Cross-episode analysis:
    - [ ] Character arc progression validation
    - [ ] Relationship development consistency
    - [ ] World rule adherence checking
    - [ ] Timeline continuity verification
  - [ ] Bible-driven scene validation:
    - [ ] Character behavior consistency alerts
    - [ ] Location accuracy validation
    - [ ] Timeline placement verification
    - [ ] Knowledge progression checks
  - [ ] Collaborative bible management:
    - [ ] Multi-writer bible access and editing
    - [ ] Change tracking and approval workflows
    - [ ] Writer room integration features
    - [ ] Producer oversight and approval

### Phase 12: Advanced Features (Future)

- [ ] **12.1 Collaborative Features**
  - [ ] Multi-user support
  - [ ] Version control for scripts
  - [ ] Merge conflict resolution
  - [ ] Real-time collaboration

- [ ] **12.2 AI-Assisted Writing**
  - [ ] Scene generation suggestions
  - [ ] Dialogue improvement
  - [ ] Plot consistency checking
  - [ ] Character voice consistency
  - [ ] Theme development assistance
  - [ ] Bible-driven writing assistance:
    - [ ] Character-appropriate dialogue suggestions
    - [ ] World rule compliance checking
    - [ ] Timeline-aware scene placement
    - [ ] Continuity-conscious plot development

## Getting Started

### Prerequisites

- Python 3.11+
- uv package manager
- SQLite 3.35+
- LMStudio running at <http://localhost:1234>

### Setup Documentation

- **[Terragon Setup Guide](TERRAGON_SETUP.md)** - Complete Terragon environment configuration
- **[Setup Summary](SETUP_SUMMARY.md)** - Overview of setup process and scripts
- **[Setup Complete Guide](SETUP_COMPLETE.md)** - Phase 1.2 completion details

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/scriptrag.git
cd scriptrag

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### Quick Start

```python
from scriptrag import ScriptRAG

# Initialize ScriptRAG
srag = ScriptRAG(
    llm_endpoint="http://localhost:1234/v1",
    db_path="./screenplay.db"
)

# Parse a screenplay
script = srag.parse_fountain("path/to/screenplay.fountain")

# Search for scenes with a character
scenes = srag.search_scenes(character="PROTAGONIST")

# Update a scene
srag.update_scene(
    scene_id=123,
    new_location="INT. COFFEE SHOP - DAY"
)
```

### Using the MCP Server

```bash
# Start the MCP server
scriptrag-mcp serve --config mcp_config.json

# The MCP server will be available for AI assistants
# Example MCP tool usage from an AI assistant:
# - scriptrag.parse_script(path="screenplay.fountain")
# - scriptrag.search_scenes(character="PROTAGONIST", location="COFFEE SHOP")
# - scriptrag.analyze_timeline(episode_id=1)
# - scriptrag.get_character_graph(character="PROTAGONIST")
```

## References

- [Fountain Format](https://fountain.io/)
- [Tagirijus/Fountain](https://deepwiki.com/Tagirijus/fountain)
- [GraphRAG with SQLite Example](https://deepwiki.com/stephenc222/example-graphrag-with-sqlite/1-overview)
- [LMStudio](https://lmstudio.ai/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

## Development Guidelines

### For AI Agents and Contributors

- **[AI Agent Guidelines](AGENTS.md)** - Commit message format with movie quotes and project rules
- **[Claude Coding Guidelines](CLAUDE.md)** - Comprehensive coding standards and development workflow

## Contributing

Contributions are welcome! Please see our contributing guidelines for more details.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
