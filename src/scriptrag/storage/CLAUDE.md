# Storage Components

This directory contains the data storage components for ScriptRAG. Each subdirectory represents a different storage responsibility aligned with the project's Git-native architecture.

## Storage Organization

- **database/**: SQLite database schemas and SQL queries for structured data (scenes, scripts, characters, series)
- **git/**: Git repository integration for Fountain files and version control
- **lfs/**: Git LFS management for large binary files (embeddings)

## Architecture Context

ScriptRAG uses a hybrid storage approach optimized for screenplay analysis:

1. **Git Repository**: Primary storage for Fountain screenplay files with boneyard metadata
2. **SQLite Database**: Indexed, queryable storage for scene analysis and search
3. **Git LFS**: Efficient storage for large embedding vectors

## Design Philosophy

Rather than abstracting over multiple storage backends, ScriptRAG embraces direct integration with specific storage technologies:

- **SQLite** for its embedded nature and excellent full-text search
- **Git** for native version control and collaboration features
- **Git LFS** for handling large binary data without bloating repositories

This approach provides:
- Clear, predictable behavior
- Optimal performance for each storage type
- Simplified debugging and maintenance
- Direct access to storage-specific features

## Storage Responsibilities

### Database (SQLite)
- Scene and script indexing
- Character relationship graphs
- Full-text and semantic search
- Query optimization

### Git Integration
- Fountain file version control
- Boneyard metadata injection/extraction
- Change detection and synchronization
- Collaboration workflows

### Git LFS
- Embedding vector storage
- Large file deduplication
- Bandwidth optimization
- Repository size management
