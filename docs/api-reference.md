# ScriptRAG API Reference

## Overview

The ScriptRAG REST API provides comprehensive endpoints for screenplay management,
analysis, and search functionality. This reference covers all available endpoints,
request/response formats, and usage examples.

**Base URL**: `http://localhost:8000/api/v1`
**Interactive Docs**: `http://localhost:8000/api/v1/docs`
**OpenAPI Spec**: `http://localhost:8000/api/v1/openapi.json`

## Authentication

Currently, the API does not require authentication. All endpoints are publicly accessible.

## Response Format

API responses return data directly for successful requests. Error responses follow a
consistent format:

### Success Response

Successful responses return the data directly without a wrapper object.

### Error Response

```json
{
  "detail": "Error message"
}
```

For validation errors (422):

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Error message",
      "type": "error_type"
    }
  ]
}
```

## Endpoints

### Scripts Management

#### Upload Script

Upload and parse a Fountain format screenplay.

**Endpoint**: `POST /scripts/upload`

**Request Body**:

```json
{
  "title": "string",
  "content": "string",  // Fountain format content
  "author": "string"    // Optional
}
```

**Response**: `ScriptResponse`

```json
{
  "id": "string",
  "title": "string",
  "author": "string",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00",
  "scene_count": 0,
  "character_count": 0,
  "has_embeddings": false
}
```

**Example**:

```bash
curl -X POST http://localhost:8000/api/v1/scripts/upload \
  -H "Content-Type: application/json" \
  -d '{
    "title": "The Coffee Shop",
    "content": "FADE IN:\n\nINT. COFFEE SHOP - DAY\n\nJOHN enters...",
    "author": "Jane Doe"
  }'
```

#### Upload Script File

Upload a Fountain file directly.

**Endpoint**: `POST /scripts/upload-file`

**Request**: Multipart form data

- `file`: The Fountain file (.Fountain, .txt)
- `title`: Optional title (uses filename if not provided)
- `author`: Optional author name

**Response**: `ScriptResponse`

**Example**:

```bash
curl -X POST http://localhost:8000/api/v1/scripts/upload-file \
  -F "file=@my_script.fountain" \
  -F "author=John Doe"
```

#### List Scripts

Get all scripts in the database.

**Endpoint**: `GET /scripts/`

**Query Parameters**:

- `limit`: Maximum number of results (default: 100)
- `offset`: Number of results to skip (default: 0)

**Response**: Array of `ScriptResponse`

**Example**:

```bash
curl http://localhost:8000/api/v1/scripts/?limit=10&offset=0
```

#### Get Script Details

Get detailed information about a specific script.

**Endpoint**: `GET /scripts/{script_id}`

**Response**: `ScriptDetailResponse`

```json
{
  "id": "string",
  "title": "string",
  "author": "string",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00",
  "scene_count": 0,
  "character_count": 0,
  "has_embeddings": false,
  "scenes": [...],
  "characters": ["CHARACTER1", "CHARACTER2"],
  "metadata": {}
}
```

#### Delete Script

Delete a script and all associated data.

**Endpoint**: `DELETE /scripts/{script_id}`

**Response**: Success message

### Embeddings

#### Generate Embeddings

Generate vector embeddings for semantic search.

**Endpoint**: `POST /embeddings/scripts/{script_id}/generate`

**Request Body**:

```json
{
  "regenerate": false  // Force regeneration of existing embeddings
}
```

**Response**: `EmbeddingResponse`

```json
{
  "status": "success",
  "message": "Embeddings generated successfully",
  "script_id": "string",
  "scenes_processed": 0,
  "scenes_skipped": 0,
  "processing_time": 0.0
}
```

#### Get Embedding Status

Check the status of embedding generation.

**Endpoint**: `GET /embeddings/scripts/{script_id}/status`

**Response**: `EmbeddingStatusResponse`

```json
{
  "script_id": "string",
  "total_scenes": 0,
  "scenes_with_embeddings": 0,
  "status": "complete",  // or "partial", "none"
  "last_updated": "2024-01-01T00:00:00"
}
```

### Scene Management

#### Get Scene

Get details of a specific scene.

**Endpoint**: `GET /scenes/{scene_id}`

**Response**: `SceneResponse`

```json
{
  "id": "string",
  "script_id": "string",
  "scene_number": 1,
  "heading": "INT. COFFEE SHOP - DAY",
  "content": "Full scene content...",
  "character_count": 2,
  "word_count": 150,
  "page_start": 1.0,
  "page_end": 2.5,
  "has_embedding": false
}
```

#### Create Scene

Create a new scene in a script.

**Endpoint**: `POST /scenes/?script_id={script_id}`

**Query Parameters**:

- `script_id` (required): The ID of the script

**Request Body**:

```json
{
  "scene_number": 1,
  "heading": "INT. LOCATION - TIME",
  "content": "Scene content..."
}
```

**Response**: `SceneResponse`

#### Update Scene

Update an existing scene.

**Endpoint**: `PATCH /scenes/{scene_id}`

**Request Body**:

```json
{
  "scene_number": 1,      // Optional
  "heading": "string",    // Optional
  "content": "string"     // Optional
}
```

**Response**: `SceneResponse`

#### Delete Scene

Delete a scene from a script.

**Endpoint**: `DELETE /scenes/{scene_id}`

**Response**: Success message

#### Inject Scene After

Insert a new scene after an existing scene.

**Endpoint**: `POST /scenes/{scene_id}/inject-after`

**Request Body**:

```json
{
  "heading": "INT. NEW LOCATION - TIME",
  "content": "New scene content..."
}
```

**Response**: `SceneResponse` (the newly created scene)

### Search

#### Search Scenes

Full-text search across scenes with filtering options.

**Endpoint**: `POST /search/scenes`

**Request Body**:

```json
{
  "query": "coffee",
  "script_id": "string",      // Optional: filter by script
  "character": "JOHN",        // Optional: filter by character
  "limit": 10,                // Default: 10
  "offset": 0                 // Default: 0
}
```

**Response**: `SearchResponse`

```json
{
  "results": [
    {
      "scene_id": "string",
      "script_id": "string",
      "scene_number": 1,
      "heading": "INT. COFFEE SHOP - DAY",
      "snippet": "...highlighted match...",
      "score": 0.95,
      "metadata": {}
    }
  ],
  "total": 15,
  "query": "coffee",
  "limit": 10,
  "offset": 0
}
```

#### Semantic Search

Search using natural language queries with vector similarity.

**Endpoint**: `POST /search/similar`

**Request Body**:

```json
{
  "query": "romantic conversation in a quiet place",
  "script_id": "string",      // Optional
  "threshold": 0.7,           // Similarity threshold (0-1)
  "limit": 10
}
```

**Response**: `SearchResponse` with similarity scores

#### Search by Character

Find all scenes featuring a specific character.

**Endpoint**: `GET /search/scenes/by-character/{character_name}`

**Query Parameters**:

- `script_id`: Optional script filter
- `limit`: Maximum results (default: 100)

**Response**: Array of `SceneResponse`

### Graph Visualization

#### Character Relationship Graph

Get character interaction network data.

**Endpoint**: `POST /graphs/characters`

**Request Body**:

```json
{
  "character_name": "JOHN",          // Optional: focus on specific character
  "script_id": "string",             // Optional: filter by script
  "depth": 2,                        // Graph traversal depth
  "min_interaction_count": 3         // Minimum interactions to include edge
}
```

**Response**: `GraphResponse`

```json
{
  "nodes": [
    {
      "id": "JOHN",
      "label": "John",
      "type": "character",
      "properties": {
        "scene_count": 15,
        "dialogue_count": 45
      }
    }
  ],
  "edges": [
    {
      "source": "JOHN",
      "target": "MARY",
      "weight": 12,
      "properties": {
        "scene_count": 8
      }
    }
  ],
  "metadata": {
    "total_nodes": 10,
    "total_edges": 25
  }
}
```

#### Timeline Visualization

Get temporal scene progression data.

**Endpoint**: `POST /graphs/timeline`

**Request Body**:

```json
{
  "script_id": "string",
  "group_by": "act",           // "act", "location", "character"
  "include_transitions": true
}
```

**Response**: `GraphResponse` with temporal nodes and edges

#### Location Graph

Get location-based scene relationships.

**Endpoint**: `GET /graphs/scripts/{script_id}/locations`

**Query Parameters**:

- `min_scene_count`: Minimum scenes per location (default: 1)

**Response**: `GraphResponse` with location nodes

### Utility Endpoints

#### Health Check

Check API server health.

**Endpoint**: `GET /health`

**Response**:

```json
{
  "status": "healthy"
}
```

#### Root

Get API information.

**Endpoint**: `GET /`

**Response**:

```json
{
  "message": "ScriptRAG API",
  "version": "1.0.0",
  "docs": "/api/v1/docs"
}
```

## Error Codes

| Status Code | Description |
|------------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid input |
| 404 | Not Found - Resource doesn't exist |
| 422 | Validation Error - Invalid request data |
| 500 | Internal Server Error |

## Rate Limiting

Currently, no rate limiting is implemented. This may change in future versions.

## Pagination

Endpoints that return lists support pagination through:

- `limit`: Number of results per page (max: 1000)
- `offset`: Number of results to skip

## Data Formats

### Fountain Format

The API expects screenplays in Fountain format. Key elements:

- Scene headings: `INT. LOCATION - TIME`
- Character names: `CHARACTER NAME`
- Dialogue: Indented under character names
- Action: Regular paragraphs

### Date/Time Format

All timestamps use ISO 8601 format: `YYYY-MM-DDTHH:MM:SS`

## SDK Support

While no official SDK exists yet, the OpenAPI specification can be used to
generate client libraries for various languages using tools like:

- OpenAPI Generator
- Swagger Codegen
- AutoRest

## Next Steps

- Review the [User Guide](./user-guide.md) for practical examples
- Check the [Developer Guide](./developer-guide.md) for integration patterns
- Explore the [Architecture Documentation](./architecture.md) for system design
