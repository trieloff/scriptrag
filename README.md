# ScriptRAG: A Graph-Based Screenwriting Assistant

[![42% Vibe_Coded](https://img.shields.io/badge/42%25-Vibe_Coded-ff69b4?style=for-the-badge&logo=claude&logoColor=white)](https://github.com/trieloff/vibe-coded-badge-action)

ScriptRAG is a novel screenwriting tool that combines Fountain parsing, graph databases, and local LLMs
to create an intelligent screenplay assistant using the GraphRAG (Graph + Retrieval-Augmented
Generation) pattern.

## 📚 Documentation

### For Users

- **[Installation Guide](docs/installation.md)** - Get ScriptRAG up and running
- **[User Guide](docs/user-guide.md)** - Complete guide for screenwriters
- **[Usage Examples](docs/usage.md)** - Common workflows and examples
- **[Bulk Import Guide](docs/bulk_import_guide.md)** - Import multiple screenplays
- **[MCP Usage Examples](examples/mcp_usage_examples.md)** - Using with AI assistants

### For Developers

- **[Developer Guide](docs/developer-guide.md)** - Contributing to ScriptRAG
- **[Architecture Overview](docs/architecture.md)** - System design and patterns
- **[API Reference](docs/api-reference.md)** - Complete API documentation
- **[MCP Server Documentation](docs/mcp_server.md)** - Model Context Protocol integration
- **[AI Agent Guidelines](AGENTS.md)** - Guidelines for AI contributors
- **[Claude Coding Guidelines](CLAUDE.md)** - Coding standards and workflows

### For Project Managers

- **Development Roadmap** - 10-phase development plan (see below)
- **Story Points Summary** - Progress tracking (see below)
- **[Weekly Status Report](WEEKLY_STATUS_REPORT.md)** - Current sprint status

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- uv package manager
- SQLite 3.38+ (for vector support)
- LMStudio running at <http://localhost:1234>

### Installation

```bash
# Clone the repository
git clone https://github.com/trieloff/scriptrag.git
cd scriptrag

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies (uv will automatically create virtual environment)
uv sync
```

### Command Line Usage

**Note:** Run these commands from the project root directory after installation.

```bash
# Parse a screenplay
uv run scriptrag parse screenplay.fountain

# Search for dialogue
uv run scriptrag search dialogue "I love you"

# Find scenes with specific characters
uv run scriptrag search character "PROTAGONIST"

# Import entire TV series
uv run scriptrag script import "Breaking Bad/**/*.fountain"

# Run mentor analysis
uv run scriptrag mentor analyze my_script.fountain --mentor save-the-cat
```

### Python API Usage

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

# Semantic search for similar scenes
similar_scenes = await srag.search_similar_scenes(
    query="emotional confrontation between friends",
    limit=5
)
```

## Features

### Core Features

- **Fountain Parser**: Read and parse screenplays in Fountain format
- **Graph Database**: SQLite-based lightweight graph database for screenplay structure
- **Local LLM Integration**: Uses LMStudio for text generation and embeddings
- **Advanced Search**: Find shows, seasons, episodes, scenes, characters, locations, and more
- **Scene Management**: Full CRUD operations with temporal and logical ordering
- **Script Bible Support**: Comprehensive continuity management and world-building
- **Bulk Import**: Import multiple Fountain files with TV series detection

### Advanced Features

- **Screenplay Mentors**: Automated analysis with industry-standard methodologies
  - Save the Cat structure analysis
  - Hero's Journey tracking
  - Character Arc development
- **MCP Server**: Model Context Protocol integration with 23+ tools for AI assistants
- **Embedding Pipeline**: Semantic analysis and similarity search
- **Knowledge Graph**: Entity extraction and relationship building

## 🎭 Screenplay Mentors

ScriptRAG includes built-in screenplay analysis mentors:

- **Save the Cat**: Blake Snyder's 15-beat structure analysis
- **Hero's Journey**: Joseph Campbell's monomyth tracking
- **Character Arc**: Character development and transformation analysis

See the [Mentor System Documentation](MENTOR_SYSTEM.md) for details.

## Tech Stack

- **Language**: Python with uv package manager
- **Database**: SQLite as a graph database
- **LLM**: Local LLMs via LMStudio (OpenAI-compatible API)
- **Parser**: Fountain screenplay format parser
- **Pattern**: GraphRAG (Graph + Retrieval-Augmented Generation)
- **Interface**: MCP (Model Context Protocol) server

## 🚀 Recent Major Progress

**Significant development milestones achieved with 15+ merged PRs and 13,000+ lines of new code:**

- **✅ Phase 11: Script Bible & Continuity Management - COMPLETE!**
- **✅ Phase 8: Pluggable Mentors System - COMPLETE!**
- **✅ Phase 7.3: MCP Server Implementation - COMPLETE!**
- **✅ Phase 6: Search and Query Interface - COMPLETE!**
- **✅ Phase 5.2: Scene Operations - COMPLETE!**
- **✅ Phase 4: GraphRAG Implementation - COMPLETE!**

## Contributing

Contributions are welcome! Please see our [Developer Guide](docs/developer-guide.md) and [AI Agent Guidelines](AGENTS.md) for more details.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## References

- [Fountain Format](https://fountain.io/)
- [GraphRAG with SQLite Example](https://deepwiki.com/stephenc222/example-graphrag-with-sqlite/1-overview)
- [LMStudio](https://lmstudio.ai/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

---

<details>
<summary>📊 Story Point Summary - By Bill Lumbergh</summary>

**Yeah, so I've been tracking our velocity and story points, mmm'kay?**

- **Total Project Estimate**: 1,593 story points (updated with Story Shape Mentor)
- **Points Completed**: 906 points (56.9%)
- **Current Sprint Velocity**: 55 points (Character Arc mentor completion)
- **Projected Completion**: Q3 2025 (at current velocity)

**Phase Completion Status:**

- Phase 1-3: ✅ Complete (173 points)
- Phase 4: ✅ Complete (89 points)
- Phase 6: ✅ Complete (134 points)
- Phase 7.3: ✅ Complete (98 points)
- Phase 8: ✅ Complete (291 points)
- Phase 11: ✅ Complete (268 points)
- Remaining Phases: 511 points

*If everyone could just keep up this velocity, that'd be great.*

</details>

<details>
<summary>📋 Project Plan & Tasks</summary>

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

- [x] **3.2 Embedding Pipeline** *(5/5 complete)*
  - [x] Design embedding strategy for screenplay elements
  - [x] Implement batch embedding generation
  - [x] Create embedding storage in SQLite
  - [x] Build similarity search functionality
  - [x] Optimize for performance (chunking, async processing)

### Phase 4: GraphRAG Implementation

- [x] **4.1 Knowledge Graph Construction** *(5/5 complete)*
  - [x] Parse screenplays into graph structure
  - [x] Extract entities and relationships
  - [x] Enrich nodes with LLM-generated metadata
  - [x] Build temporal graph layer
  - [x] Create logical dependency graph

- [x] **4.1.1 PR #17 Feedback Resolution** *(7/7 complete)*
  - [x] Make demo limits configurable in build_knowledge_graph.py example
  - [x] Complete mock implementation of _get_character_dialogue_samples
  - [x] Add confirmation for file deletion in example script
  - [x] Optimize character mentions extraction
  - [x] Fix all linting issues
  - [x] Maintain test coverage
  - [x] Pass type checking

- [x] **4.2 Graph Indexing** *(5/5 complete)*
  - [x] Implement hierarchical indexing
  - [x] Create character relationship graphs
  - [x] Build location-based scene graphs
  - [x] Index temporal relationships
  - [x] Generate concept and theme graphs

- [x] **4.3 RAG Query Engine** *(5/5 complete)*
  - [x] Design query language for screenplay searches
  - [x] Implement multi-hop graph traversal
  - [x] Create context assembly from graph neighborhoods
  - [x] Build prompt templates for different query types
  - [x] Integrate LLM for answer generation

### Phase 5: Scene Management Features

- [x] **5.1 Scene Ordering** *(34 points - Complete)*
  - [x] Implement script order tracking
  - [x] Build temporal order inference engine
  - [x] Create logical dependency analyzer
  - [x] Design UI/API for reordering scenes
  - [x] Maintain consistency across orderings

- [x] **5.2 Scene Operations** *(34 points - Complete)*
  - [x] Update Scene functionality
  - [x] Delete Scene with reference maintenance
  - [x] Inject Scene at specified positions
  - [x] Graph integration for all operations

### Phase 6: Search and Query Interface

- [x] **6.1 Search Implementation** *(5/5 complete)*
  - [x] Text-based search
  - [x] Entity search
  - [x] Temporal search
  - [x] Concept/theme search
  - [x] Relationship search

- [x] **6.2 Advanced Queries** *(5/5 complete)*
  - [x] Multi-criteria search
  - [x] Graph pattern matching
  - [x] Semantic similarity search
  - [x] Timeline visualization queries
  - [x] Character arc analysis

### Phase 7: API and Interface

- [x] **7.1 REST API** *(5/5 complete)*
  - [x] Design OpenAPI specification
  - [x] Implement FastAPI backend
  - [x] Create endpoints for all operations

- [x] **7.2 CLI Interface** *(4/4 complete)*
  - [x] Create command-line tool using Typer
  - [x] Implement commands for all operations
  - [x] Add interactive mode
  - [x] Create batch processing

- [x] **7.3 MCP Server** *(11/11 complete)*
  - [x] Implement Model Context Protocol server
  - [x] Create 23 MCP tools
  - [x] Define MCP resource schemas
  - [x] Implement MCP prompts
  - [x] Full Claude integration

### Phase 8: Pluggable Mentors System 🎭 ✅ COMPLETE! (291 story points)

📋 **[Detailed Mentor System Documentation](MENTOR_SYSTEM.md)**

- [x] **8.1 Mentor Infrastructure** *(34 points - Complete)*
- [x] **8.2 Built-in Mentors** *(191 points - Complete)*
  - [x] Save the Cat mentor (47 points)
  - [x] Hero's Journey mentor (89 points)
  - [x] Character Arc mentor (55 points)
  - [ ] Story Shape mentor (84 points - Planned)
- [x] **8.3 Mentor Execution System** *(50 points - Complete)*
- [x] **8.4 Advanced Mentor Features** *(27 points - Partial)*

### Phase 9: Testing and Optimization

- [ ] **9.1 Testing Suite**
  - [ ] Unit tests for all components
  - [ ] Integration tests
  - [ ] Performance benchmarks
  - [ ] Test data generation
  - [ ] End-to-end testing

- [ ] **9.2 Performance Optimization**
  - [ ] Query optimization
  - [ ] Embedding cache optimization
  - [ ] Async processing
  - [ ] Database indexing
  - [ ] Memory profiling

### Phase 10: Documentation and Deployment

- [ ] **10.1 Documentation**
  - [ ] API documentation
  - [ ] User guide completion
  - [ ] Developer documentation
  - [ ] Example notebooks
  - [ ] Architecture diagrams

- [ ] **10.2 Deployment**
  - [ ] Create uv/uvx deployment
  - [ ] Deployment scripts
  - [ ] Backup/restore procedures
  - [ ] Performance monitoring
  - [ ] Installation guide

### Phase 11: Script Bible and Continuity Management ✅

- [x] **11.1 Script Bible Foundation** *(Complete)*
- [x] **11.2 Character Development System** *(Complete)*
- [x] **11.3 World-Building and Lore Management** *(Complete)*
- [x] **11.4 Timeline and Continuity System** *(Complete)*
- [x] **11.5 Script Bible Interface and Tools** *(Complete)*
- [x] **11.6 Advanced Continuity Features** *(Complete)*

### Phase 8.5: Story Shape Mentor Implementation (NEW)

- [ ] **8.5.1 Research & Design** *(21 points)*
- [ ] **8.5.2 Core Implementation** *(34 points)*
- [ ] **8.5.3 Advanced Features** *(21 points)*
- [ ] **8.5.4 Integration & Testing** *(21 points)*
- [ ] **8.5.5 Documentation & Polish** *(8 points)*

### Phase 12: Advanced Features (Future)

- [ ] **12.1 Git-based Collaboration**
  - [ ] Export to git-friendly format
  - [ ] Import/restore from git
  - [ ] Merge-friendly formats
  - [ ] Diff visualization

- [ ] **12.2 AI-Assisted Writing**
  - [ ] Scene generation
  - [ ] Dialogue improvement
  - [ ] Plot consistency
  - [ ] Character voice
  - [ ] Theme development
  - [ ] Bible-driven assistance

</details>

<details>
<summary>🔧 Setup Documentation</summary>

- **[Terragon Setup Guide](TERRAGON_SETUP.md)** - Complete Terragon environment configuration
- **[Setup Summary](SETUP_SUMMARY.md)** - Overview of setup process and scripts
- **[Setup Complete Guide](SETUP_COMPLETE.md)** - Phase 1.2 completion details

</details>
