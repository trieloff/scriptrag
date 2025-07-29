# ScriptRAG REST API

ScriptRAG provides a comprehensive REST API for integrating screenplay analysis and
management capabilities into web applications and third-party tools.

## Documentation

- **[API Reference](./api-reference.md)** - Complete endpoint documentation with
  request/response formats
- **[User Guide](./user-guide.md)** - Practical guide for scriptwriters using the API
- **[Developer Guide](./developer-guide.md)** - Integration patterns, code examples, and SDKs
- **[Architecture](./architecture.md)** - System design and GraphRAG integration details

## Quick Start

### Running the API Server

```bash
# Start the API server
make run-api

# Or with auto-reload for development
make run-api-dev

# Or using the CLI directly
uv run scriptrag server api --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` with interactive documentation
at `http://localhost:8000/api/v1/docs`.

## API Overview

### Base URL

```text
http://localhost:8000/api/v1
```

### Authentication

Currently, the API does not require authentication. Authentication support is
planned for a future release.

### API Endpoints

#### Scripts Management

- **POST** `/scripts/upload` - Upload and parse a Fountain script
- **POST** `/scripts/upload-file` - Upload a Fountain file
- **GET** `/scripts/` - List all scripts
- **GET** `/scripts/{script_id}` - Get script details
- **DELETE** `/scripts/{script_id}` - Delete a script

#### Embeddings

- **POST** `/embeddings/scripts/{script_id}/generate` - Generate embeddings for a script
- **GET** `/embeddings/scripts/{script_id}/status` - Get embedding generation status

#### Scene Management

- **GET** `/scenes/{scene_id}` - Get scene details
- **POST** `/scenes/` - Create a new scene
- **PATCH** `/scenes/{scene_id}` - Update a scene
- **DELETE** `/scenes/{scene_id}` - Delete a scene
- **POST** `/scenes/{scene_id}/inject-after` - Inject a scene after another

#### Search

- **POST** `/search/scenes` - Search scenes with text and filters
- **POST** `/search/similar` - Semantic similarity search
- **GET** `/search/scenes/by-character/{character_name}` - Search by character

#### Graph Visualization

- **POST** `/graphs/characters` - Get character relationship graph
- **POST** `/graphs/timeline` - Get timeline visualization
- **GET** `/graphs/scripts/{script_id}/locations` - Get location-based graph

## Example Usage

### Upload a Script

```python
import requests

# Upload script content
response = requests.post(
    "http://localhost:8000/api/v1/scripts/upload",
    json={
        "title": "My Script",
        "content": "FADE IN:\n\nINT. COFFEE SHOP - DAY\n\nJOHN enters...",
        "author": "John Doe"
    }
)
script_id = response.json()["id"]
```

### Generate Embeddings

```python
# Generate embeddings for semantic search
response = requests.post(
    f"http://localhost:8000/api/v1/embeddings/scripts/{script_id}/generate",
    json={"regenerate": False}
)
```

### Search Scenes

```python
# Text search
response = requests.post(
    "http://localhost:8000/api/v1/search/scenes",
    json={
        "query": "coffee",
        "script_id": script_id,
        "limit": 10
    }
)

# Semantic search
response = requests.post(
    "http://localhost:8000/api/v1/search/similar",
    json={
        "query": "romantic conversation in a quiet place",
        "threshold": 0.7
    }
)
```

### Get Character Graph

```python
# Get character relationships
response = requests.post(
    "http://localhost:8000/api/v1/graphs/characters",
    json={
        "character_name": "JOHN",
        "depth": 2,
        "min_interaction_count": 3
    }
)
```

## Response Format

All API responses follow a consistent format:

### Success Response

```json
{
    "status": "success",
    "data": { ... },
    "message": "Optional success message"
}
```

### Error Response

```json
{
    "status": "error",
    "error": "Error message",
    "details": {
        "additional": "error details"
    }
}
```

## OpenAPI Documentation

The API provides interactive OpenAPI (Swagger) documentation at:

- **Swagger UI**: `http://localhost:8000/api/v1/docs`
- **ReDoc**: `http://localhost:8000/api/v1/redoc`
- **OpenAPI Schema**: `http://localhost:8000/api/v1/openapi.json`

## Integration Examples

### JavaScript/TypeScript

```typescript
const scriptragApi = {
    baseUrl: 'http://localhost:8000/api/v1',

    async uploadScript(title: string, content: string, author?: string) {
        const response = await fetch(`${this.baseUrl}/scripts/upload`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, content, author })
        });
        return response.json();
    },

    async searchScenes(query: string, scriptId?: number) {
        const response = await fetch(`${this.baseUrl}/search/scenes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, script_id: scriptId })
        });
        return response.json();
    }
};
```

### cURL Examples

```bash
# Upload a script
curl -X POST http://localhost:8000/api/v1/scripts/upload \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "content": "FADE IN..."}'

# Search scenes
curl -X POST http://localhost:8000/api/v1/search/scenes \
  -H "Content-Type: application/json" \
  -d '{"query": "coffee", "limit": 5}'
```

## Future Enhancements

- JWT-based authentication
- WebSocket support for real-time updates
- Batch operations for multiple scripts
- Export endpoints for various formats
- Rate limiting and quotas
- API key management
