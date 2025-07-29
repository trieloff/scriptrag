# Usage

## Basic Commands

### Initialize a Project

```bash
uv run scriptrag init my-screenplay-project
cd my-screenplay-project
```

### Parse a Screenplay

```bash
uv run scriptrag parse my-script.fountain
```

### Query the Graph

```bash
uv run scriptrag query "Who are the main characters?"
uv run scriptrag query "What scenes take place at night?"
uv run scriptrag query "Show character relationship network"
```

## Configuration

ScriptRAG uses a hierarchical configuration system:

1. Default settings
2. Environment variables
3. Configuration files
4. Command-line arguments

### Environment Variables

- `SCRIPTRAG_LOG_LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `SCRIPTRAG_DATABASE_URL`: Database connection string
- `SCRIPTRAG_LLM_ENDPOINT`: LLM API endpoint

### Configuration File

Create `scriptrag.toml` in your project directory:

```toml
[database]
url = "sqlite:///my-project.db"

[llm]
endpoint = "http://localhost:1234/v1"
model = "local-model"

[logging]
level = "INFO"
```

## Advanced Usage

### Batch Processing

```bash
uv run scriptrag batch-parse scripts/*.fountain
```

### Export Data

```bash
uv run scriptrag export --format json output.json
uv run scriptrag export --format graphml network.graphml
```
