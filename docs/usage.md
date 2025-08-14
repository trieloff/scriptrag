# ScriptRAG Usage Guide

This guide provides comprehensive examples of using ScriptRAG from the command line.

## Table of Contents

1. [Installation & Setup](#installation--setup)
2. [Basic Workflow](#basic-workflow)
3. [Command Reference](#command-reference)
4. [Common Use Cases](#common-use-cases)
5. [Troubleshooting](#troubleshooting)

## Installation & Setup

### Prerequisites

- Python 3.11 or higher
- uv package manager
- SQLite 3.38+ (for vector support)

### Initial Setup

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/trieloff/scriptrag.git
cd scriptrag

# Set up development environment
make setup-dev

# Activate virtual environment
source .venv/bin/activate
```

## Basic Workflow

The typical ScriptRAG workflow consists of three main steps:

1. **Initialize** the database
2. **Analyze** Fountain files to extract metadata
3. **Index** the analyzed files into the database

### Quick Start with `pull` Command

The easiest way to get started is using the `pull` command, which combines all three steps:

```bash
# Initialize database and process all Fountain files in current directory
uv run scriptrag pull

# Process files in a specific directory
uv run scriptrag pull /path/to/screenplays

# Process with custom configuration
uv run scriptrag pull --config config.yaml /path/to/screenplays
```

### Step-by-Step Workflow

For more control, you can run each step separately:

```bash
# Step 1: Initialize the database
uv run scriptrag init

# Step 2: Analyze Fountain files (extracts metadata)
uv run scriptrag analyze /path/to/screenplays

# Step 3: Index analyzed files into database
uv run scriptrag index /path/to/screenplays
```

## Command Reference

### `scriptrag init`

Initialize a new ScriptRAG database.

```bash
# Basic initialization
uv run scriptrag init

# Specify custom database path
uv run scriptrag init --db-path /custom/path/scriptrag.db

# Force re-initialization (overwrites existing database)
uv run scriptrag init --force
```

**Options:**

- `--db-path`, `-d`: Path to SQLite database file
- `--force`, `-f`: Force initialization, overwriting existing database
- `--config`, `-c`: Path to configuration file (YAML, TOML, or JSON)

### `scriptrag list`

List all Fountain files in a directory.

```bash
# List files in current directory
uv run scriptrag list

# List files in specific directory
uv run scriptrag list /path/to/screenplays

# List only files in current directory (no subdirectories)
uv run scriptrag list --no-recursive
```

**Options:**

- `--no-recursive`: Don't search subdirectories

**Output Example:**

```text
                               Fountain Scripts  
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Title               ┃ Author        ┃ Episode ┃ Season ┃ File                ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ Mystery Show        │ John Smith    │    1    │   1    │ S01E01_pilot.fountain│
│ Mystery Show        │ John Smith    │    2    │   1    │ S01E02_cont.fountain │
└─────────────────────┴───────────────┴─────────┴────────┴─────────────────────┘
```

### `scriptrag analyze`

Analyze Fountain files and extract metadata. This command parses scenes and prepares them for indexing.

```bash
# Analyze all Fountain files in current directory
uv run scriptrag analyze

# Analyze specific directory
uv run scriptrag analyze /path/to/screenplays

# Force re-analysis of all files
uv run scriptrag analyze --force

# Dry run (show what would be done without making changes)
uv run scriptrag analyze --dry-run

# Run additional analyzers
uv run scriptrag analyze --analyzer scene_embeddings --analyzer props_inventory

# Stop on first error (brittle mode)
uv run scriptrag analyze --brittle
```

**Options:**

- `--force`, `-f`: Force re-processing of all scenes
- `--dry-run`, `-n`: Show what would be updated without making changes
- `--no-recursive`: Don't search subdirectories
- `--analyzer`, `-a`: Additional analyzers to run (can be specified multiple times)
- `--brittle`: Stop processing if any analyzer fails

### `scriptrag index`

Index analyzed Fountain files into the database.

```bash
# Index all analyzed files in current directory
uv run scriptrag index

# Index specific directory
uv run scriptrag index /path/to/screenplays

# Dry run mode
uv run scriptrag index --dry-run

# Process in smaller batches
uv run scriptrag index --batch-size 5

# Show detailed information
uv run scriptrag index --verbose
```

**Options:**

- `--dry-run`, `-n`: Show what would be indexed without making changes
- `--no-recursive`: Don't search subdirectories
- `--batch-size`, `-b`: Number of scripts to process in each batch (default: 10)
- `--verbose`, `-v`: Show detailed information for each script

### `scriptrag pull`

Convenience command that combines init, analyze, and index.

```bash
# Full workflow for current directory
uv run scriptrag pull

# Process specific directory with force re-processing
uv run scriptrag pull --force /path/to/screenplays

# Use custom configuration
uv run scriptrag pull --config config.yaml

# Dry run mode
uv run scriptrag pull --dry-run
```

**Options:**

- `--force`, `-f`: Force re-processing of all scripts
- `--dry-run`, `-n`: Show what would be done without making changes
- `--no-recursive`: Don't search subdirectories
- `--batch-size`, `-b`: Number of scripts to process in each batch
- `--config`, `-c`: Path to configuration file
- `--brittle`: Stop processing if any analyzer fails

### `scriptrag search`

Search through indexed screenplays.

```bash
# Simple text search
uv run scriptrag search "coffee shop"

# Search for character dialogue
uv run scriptrag search --character SARAH "take the notebook"

# Auto-detect components (characters in CAPS, "dialogue", (parentheticals))
uv run scriptrag search SARAH "take the notebook" "(whisper)"

# Search within a specific project
uv run scriptrag search --project "The Great Adventure" "begins"

# Search specific episodes
uv run scriptrag search --range s1e2-s1e5 "coffee"

# Enable fuzzy/vector search
uv run scriptrag search --fuzzy "similar scene"

# Strict matching only (no vector search)
uv run scriptrag search --strict "exact phrase"

# Show more results
uv run scriptrag search "dialogue" --limit 10

# Pagination
uv run scriptrag search "dialogue" --limit 10 --offset 10

# Verbose output (show full scene content)
uv run scriptrag search "coffee" --verbose

# Brief one-line results
uv run scriptrag search "coffee" --brief
```

**Options:**

- `--character`, `-c`: Filter by character name
- `--dialogue`, `-d`: Search for specific dialogue
- `--parenthetical`, `-p`: Search for parenthetical directions
- `--project`: Filter by project/script title
- `--range`, `-r`: Episode range (e.g., s1e2-s1e5)
- `--fuzzy`: Enable fuzzy/vector search
- `--strict`: Disable vector search, use exact matching only
- `--limit`, `-l`: Maximum number of results (default: 5)
- `--offset`, `-o`: Skip this many results (for pagination)
- `--verbose`, `-v`: Show full scene content
- `--brief`, `-b`: Show brief one-line results
- `--no-bible`: Exclude bible content from search results
- `--only-bible`: Search only bible content

### `scriptrag watch`

Monitor a directory for Fountain file changes and automatically process them.

```bash
# Watch current directory
uv run scriptrag watch

# Watch specific directory
uv run scriptrag watch /path/to/screenplays

# Force re-processing on every change
uv run scriptrag watch --force

# Skip initial pull
uv run scriptrag watch --no-initial-pull

# Set timeout (stop after 60 seconds)
uv run scriptrag watch --timeout 60
```

**Options:**

- `--force`, `-f`: Force re-processing on every change
- `--no-recursive`: Don't watch subdirectories
- `--batch-size`, `-b`: Number of scripts to process in each batch
- `--config`, `-c`: Path to configuration file
- `--initial-pull/--no-initial-pull`: Run a full pull before starting to watch
- `--timeout`, `-t`: Maximum watch duration in seconds (0 for unlimited)

### `scriptrag scene`

AI-friendly scene management commands for reading, adding, updating, and deleting scenes.

#### Read Scenes

```bash
# Read a specific scene
uv run scriptrag scene read --project "breaking_bad" --season 1 --episode 1 --scene 3

# Read scene from standalone script
uv run scriptrag scene read --project "inception" --scene 42

# List available bible files
uv run scriptrag scene read --project "inception" --bible

# Read specific bible file
uv run scriptrag scene read --project "inception" --bible-name "world_bible.md"

# Output as JSON
uv run scriptrag scene read --project "inception" --scene 1 --json
```

#### Add Scenes

```bash
# Add a new scene (automatic renumbering)
uv run scriptrag scene add --project "inception" --position 5 \
  --content "INT. WAREHOUSE - DAY\n\nThe team gathers around a table."
```

#### Update Scenes

```bash
# Update a scene (requires session token from read command)
uv run scriptrag scene update --token "abc123..." \
  --content "INT. WAREHOUSE - NIGHT\n\nThe team reviews the plan."
```

#### Delete Scenes

```bash
# Delete a scene (automatic renumbering)
uv run scriptrag scene delete --project "inception" --scene 5
```

### `scriptrag query`

Execute predefined SQL queries from the query library.

```bash
# List all available queries
uv run scriptrag query list

# List all indexed scripts
uv run scriptrag query test_list_scripts

# Get character statistics
uv run scriptrag query character_stats

# Get all dialogue lines for a character
uv run scriptrag query character_lines --character "SARAH"

# List scenes by project
uv run scriptrag query list_scenes --project "Mystery Show"

# Simple scene list
uv run scriptrag query simple_scene_list
```

### `scriptrag mcp`

Run the Model Context Protocol server for integration with AI assistants.

```bash
# Start MCP server on default port (5173)
uv run scriptrag mcp

# Start on custom host and port
uv run scriptrag mcp --host 0.0.0.0 --port 8080
```

**Options:**

- `--host`: Host to bind to (default: localhost)
- `--port`: Port to bind to (default: 5173)

## Common Use Cases

### 1. Import and Search a Single Screenplay

```bash
# Quick import
uv run scriptrag pull my_script.fountain

# Search for specific dialogue
uv run scriptrag search "I'll be back"

# Find all scenes with a character
uv run scriptrag search --character PROTAGONIST
```

### 2. Bulk Import TV Series

```bash
# Import entire series directory
uv run scriptrag pull /path/to/series/

# Search within specific episodes
uv run scriptrag search --range s1e1-s1e10 "cliffhanger"

# Get character statistics across episodes
uv run scriptrag query character_stats
```

### 3. Monitor Active Project

```bash
# Watch directory for changes
uv run scriptrag watch /path/to/active/project/

# The system will automatically:
# - Detect new or modified Fountain files
# - Analyze and index them
# - Make them searchable immediately
```

### 4. Integration with AI Assistants

```bash
# Start MCP server
uv run scriptrag mcp

# Configure your AI assistant (e.g., Claude Desktop) to connect to:
# http://localhost:5173
```

## Configuration

ScriptRAG can be configured using YAML, TOML, or JSON files. Create a configuration file to customize database paths and other settings:

### Example `config.yaml`

```yaml
database:
  path: /custom/path/to/scriptrag.db

llm:
  provider: openai_compatible
  endpoint: http://localhost:1234/v1
  timeout: 30

logging:
  level: INFO
```

Use the configuration file with any command:

```bash
uv run scriptrag pull --config config.yaml /path/to/screenplays
```

## Troubleshooting

### Database Path Issues

If you encounter "Invalid database path detected" errors:

1. Ensure the database is initialized:

   ```bash
   uv run scriptrag init
   ```

2. Use a configuration file to specify the database path:

   ```bash
   uv run scriptrag pull --config config.yaml
   ```

3. Set the environment variable (may not work in all contexts):

   ```bash
   export SCRIPTRAG_DB_PATH=/path/to/scriptrag.db
   ```

### UNIQUE Constraint Failures

When indexing scripts with the same title and author:

- The system maintains unique script entries based on title and author
- Use episode/season metadata to differentiate TV episodes
- Consider renaming duplicate files or updating their metadata

### LLM Connection Issues

If analyzers requiring LLM access fail:

1. Ensure LMStudio is running at the configured endpoint
2. Check your configuration file for correct LLM settings
3. Use `--brittle` flag to stop on first error for debugging

### File Not Found Errors

- Use absolute paths when possible
- Ensure Fountain files have the `.fountain` extension
- Check file permissions

## Advanced Features

### Custom Analyzers

ScriptRAG supports custom analyzers for extracting additional metadata:

```bash
# Run with scene embedding analyzer
uv run scriptrag analyze --analyzer scene_embeddings

# Run multiple analyzers
uv run scriptrag analyze --analyzer scene_embeddings --analyzer props_inventory
```

### Batch Processing

For large screenplay collections:

```bash
# Process in smaller batches to avoid memory issues
uv run scriptrag index --batch-size 5

# Use dry-run to preview operations
uv run scriptrag pull --dry-run --batch-size 3
```

### Vector Search

ScriptRAG supports semantic search using embeddings:

```bash
# Enable fuzzy/vector search for longer queries
uv run scriptrag search --fuzzy "a scene where characters discuss their past"

# Force strict matching for exact phrases
uv run scriptrag search --strict "INT. COFFEE SHOP - DAY"
```

## Examples

### Finding Similar Scenes

```bash
# Search for thematically similar scenes
uv run scriptrag search --fuzzy "confrontation between mentor and student"
```

### Character Arc Analysis

```bash
# Get all dialogue for a character
uv run scriptrag query character_lines --character "WALTER"

# Search for character's key moments
uv run scriptrag search --character WALTER --verbose
```

### Episode-Specific Searches

```bash
# Search within a specific season
uv run scriptrag search --range s2e1-s2e13 "reveal"

# Find all coffee shop scenes in season 1
uv run scriptrag search --range s1e1-s1e22 "INT. COFFEE"
```

## Best Practices

1. **Regular Backups**: Back up your SQLite database regularly
2. **Incremental Processing**: Use `watch` mode for active projects
3. **Metadata Management**: Keep Fountain file metadata up-to-date
4. **Batch Size**: Adjust batch size based on system memory
5. **Configuration Files**: Use config files for consistent settings

## Getting Help

For more information:

- Run any command with `--help` for detailed options
- Check the [User Guide](user-guide.md) for comprehensive documentation
- See [MCP Usage Examples](../examples/mcp_usage_examples.md) for AI integration
- Review [Troubleshooting Guide](troubleshooting.md) for common issues
