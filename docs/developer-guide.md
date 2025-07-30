# ScriptRAG Developer Guide

## Introduction

This guide helps developers integrate ScriptRAG's REST API into applications,
build custom tools, and extend the platform's capabilities. ScriptRAG combines
screenplay analysis with graph-based AI to provide powerful search and
visualization features.

## Architecture Overview

ScriptRAG follows a modern, layered architecture:

```text
┌─────────────────────────────────────────────────┐
│              Client Applications                 │
├─────────────────────────────────────────────────┤
│              REST API (FastAPI)                  │
├─────────────────────────────────────────────────┤
│          Database Operations Layer               │
├─────────────────────────────────────────────────┤
│     PostgreSQL + pgvector     │   Embeddings    │
└─────────────────────────────────────────────────┘
```

## Quick Start

### Python Client Example

```python
import requests
from typing import Dict, List

class ScriptRAGClient:
    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        self.base_url = base_url
        self.session = requests.Session()

    def upload_script(self, title: str, content: str, author: str | None = None) -> Dict:
        """Upload a Fountain script."""
        response = self.session.post(
            f"{self.base_url}/scripts/upload",
            json={"title": title, "content": content, "author": author}
        )
        response.raise_for_status()
        return response.json()

    def generate_embeddings(self, script_id: str, regenerate: bool = False) -> Dict:
        """Generate embeddings for semantic search."""
        response = self.session.post(
            f"{self.base_url}/embeddings/scripts/{script_id}/generate",
            json={"regenerate": regenerate}
        )
        response.raise_for_status()
        return response.json()

    def search_scenes(self, query: str, script_id: str | None = None,
                     character: str | None = None, limit: int = 10) -> Dict:
        """Search scenes with text query."""
        response = self.session.post(
            f"{self.base_url}/search/scenes",
            json={
                "query": query,
                "script_id": script_id,
                "character": character,
                "limit": limit
            }
        )
        response.raise_for_status()
        return response.json()

    def semantic_search(self, query: str, threshold: float = 0.7,
                       script_id: str | None = None) -> Dict:
        """Search using semantic similarity."""
        response = self.session.post(
            f"{self.base_url}/search/similar",
            json={
                "query": query,
                "threshold": threshold,
                "script_id": script_id
            }
        )
        response.raise_for_status()
        return response.json()

# Usage example
client = ScriptRAGClient()

# Upload script
script = client.upload_script(
    title="The Coffee Shop",
    content=open("my_script.fountain").read(),
    author="Jane Doe"
)

# Generate embeddings
embeddings = client.generate_embeddings(script["id"])

# Search
results = client.semantic_search("romantic conversation", threshold=0.8)
```

### JavaScript/TypeScript Client

```typescript
interface ScriptResponse {
  id: string;
  title: string;
  author: string | null;
  scene_count: number;
  character_count: number;
  has_embeddings: boolean;
  created_at: string;
  updated_at: string;
}

interface SearchResult {
  scene_id: string;
  script_id: string;
  scene_number: number;
  heading: string;
  snippet: string;
  score: number;
}

class ScriptRAGClient {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:8000/api/v1') {
    this.baseUrl = baseUrl;
  }

  async uploadScript(title: string, content: string, author?: string): Promise<ScriptResponse> {
    const response = await fetch(`${this.baseUrl}/scripts/upload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content, author })
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }

    return response.json();
  }

  async generateEmbeddings(scriptId: string, regenerate: boolean = false): Promise<any> {
    const response = await fetch(
      `${this.baseUrl}/embeddings/scripts/${scriptId}/generate`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ regenerate })
      }
    );

    if (!response.ok) {
      throw new Error(`Embedding generation failed: ${response.statusText}`);
    }

    return response.json();
  }

  async searchScenes(query: string, options?: {
    scriptId?: string;
    character?: string;
    limit?: number;
  }): Promise<{ results: SearchResult[]; total: number }> {
    const response = await fetch(`${this.baseUrl}/search/scenes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        script_id: options?.scriptId,
        character: options?.character,
        limit: options?.limit || 10
      })
    });

    if (!response.ok) {
      throw new Error(`Search failed: ${response.statusText}`);
    }

    return response.json();
  }

  async getCharacterGraph(characterName?: string, scriptId?: string): Promise<any> {
    const response = await fetch(`${this.baseUrl}/graphs/characters`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        character_name: characterName,
        script_id: scriptId,
        depth: 2
      })
    });

    if (!response.ok) {
      throw new Error(`Graph generation failed: ${response.statusText}`);
    }

    return response.json();
  }
}

// Usage
const client = new ScriptRAGClient();

async function analyzeScript() {
  // Upload script
  const script = await client.uploadScript(
    'My Script',
    fountainContent,
    'John Doe'
  );

  // Generate embeddings
  await client.generateEmbeddings(script.id);

  // Search for themes
  const results = await client.searchScenes('conflict', {
    scriptId: script.id,
    limit: 20
  });

  // Get character relationships
  const graph = await client.getCharacterGraph('PROTAGONIST', script.id);

  console.log(`Found ${results.total} scenes with conflict`);
  console.log(`Character graph has ${graph.nodes.length} nodes`);
}
```

## Common Integration Patterns

### 1. Script Analysis Pipeline

```python
async def analyze_script_pipeline(fountain_content: str, title: str):
    """Complete script analysis pipeline."""

    # Step 1: Upload script
    script = client.upload_script(title, fountain_content)
    script_id = script["id"]

    # Step 2: Generate embeddings
    embeddings = client.generate_embeddings(script_id)

    # Step 3: Analyze structure
    script_details = client.get_script(script_id)

    # Step 4: Character analysis
    characters = script_details["characters"]
    character_graphs = {}

    for character in characters[:5]:  # Top 5 characters
        graph = client.get_character_graph(character, script_id)
        character_graphs[character] = graph

    # Step 5: Thematic analysis
    themes = [
        "conflict and resolution",
        "character growth",
        "romantic elements",
        "action sequences",
        "emotional moments"
    ]

    thematic_analysis = {}
    for theme in themes:
        results = client.semantic_search(theme, script_id=script_id)
        thematic_analysis[theme] = {
            "count": results["total"],
            "scenes": results["results"][:3]  # Top 3 scenes
        }

    return {
        "script": script_details,
        "characters": character_graphs,
        "themes": thematic_analysis
    }
```

### 2. Real-time Collaboration

```javascript
class ScriptCollaborationManager {
  private client: ScriptRAGClient;
  private scriptId: string;
  private pollInterval: number = 5000; // 5 seconds
  private listeners: Map<string, Function[]> = new Map();

  constructor(scriptId: string) {
    this.client = new ScriptRAGClient();
    this.scriptId = scriptId;
  }

  // Monitor script changes
  async startMonitoring() {
    setInterval(async () => {
      const script = await this.client.getScript(this.scriptId);
      this.emit('scriptUpdate', script);
    }, this.pollInterval);
  }

  // Listen for specific character changes
  async monitorCharacter(characterName: string) {
    setInterval(async () => {
      const scenes = await this.client.searchByCharacter(characterName, this.scriptId);
      this.emit(`character:${characterName}`, scenes);
    }, this.pollInterval);
  }

  // Event system
  on(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(callback);
  }

  emit(event: string, data: any) {
    const callbacks = this.listeners.get(event) || [];
    callbacks.forEach(cb => cb(data));
  }
}

// Usage
const collab = new ScriptCollaborationManager('script-123');

collab.on('scriptUpdate', (script) => {
  console.log(`Script updated: ${script.updated_at}`);
});

collab.on('character:JOHN', (scenes) => {
  console.log(`John appears in ${scenes.length} scenes`);
});

collab.startMonitoring();
collab.monitorCharacter('JOHN');
```

### 3. Batch Processing

```python
import asyncio
from pathlib import Path

async def batch_process_scripts(script_directory: Path):
    """Process multiple scripts in parallel."""

    fountain_files = list(script_directory.glob("*.fountain"))

    async def process_single_script(file_path: Path):
        try:
            content = file_path.read_text()
            title = file_path.stem

            # Upload
            script = await client.upload_script_async(title, content)

            # Generate embeddings
            await client.generate_embeddings_async(script["id"])

            # Basic analysis
            stats = {
                "title": title,
                "scenes": script["scene_count"],
                "characters": script["character_count"],
                "id": script["id"]
            }

            return stats
        except Exception as e:
            return {"title": file_path.stem, "error": str(e)}

    # Process all scripts concurrently
    results = await asyncio.gather(
        *[process_single_script(f) for f in fountain_files]
    )

    return results

# Run batch processing
results = asyncio.run(batch_process_scripts(Path("./scripts")))
```

### 4. Advanced Search Interface

```typescript
class AdvancedSearchBuilder {
  private queries: Array<{
    type: 'text' | 'semantic';
    query: string;
    weight: number;
  }> = [];

  private filters: {
    scriptId?: string;
    characters?: string[];
    minScore?: number;
  } = {};

  addTextQuery(query: string, weight: number = 1.0): this {
    this.queries.push({ type: 'text', query, weight });
    return this;
  }

  addSemanticQuery(query: string, weight: number = 1.0): this {
    this.queries.push({ type: 'semantic', query, weight });
    return this;
  }

  filterByScript(scriptId: string): this {
    this.filters.scriptId = scriptId;
    return this;
  }

  filterByCharacters(...characters: string[]): this {
    this.filters.characters = characters;
    return this;
  }

  setMinScore(score: number): this {
    this.filters.minScore = score;
    return this;
  }

  async execute(client: ScriptRAGClient): Promise<any[]> {
    const allResults: Map<string, any> = new Map();

    // Execute all queries
    for (const queryDef of this.queries) {
      let results: any[];

      if (queryDef.type === 'text') {
        const response = await client.searchScenes(queryDef.query, {
          scriptId: this.filters.scriptId
        });
        results = response.results;
      } else {
        const response = await client.semanticSearch(queryDef.query, 0.7, this.filters.scriptId);
        results = response.results;
      }

      // Merge results with weighted scores
      results.forEach(result => {
        const key = result.scene_id;
        if (allResults.has(key)) {
          const existing = allResults.get(key);
          existing.score = Math.max(existing.score, result.score * queryDef.weight);
        } else {
          result.score *= queryDef.weight;
          allResults.set(key, result);
        }
      });
    }

    // Apply filters and sort
    let finalResults = Array.from(allResults.values());

    if (this.filters.characters?.length) {
      finalResults = finalResults.filter(r =>
        this.filters.characters!.some(char =>
          r.content?.includes(char)
        )
      );
    }

    if (this.filters.minScore) {
      finalResults = finalResults.filter(r => r.score >= this.filters.minScore);
    }

    return finalResults.sort((a, b) => b.score - a.score);
  }
}

// Usage: Find intense dialogue scenes between specific characters
const search = new AdvancedSearchBuilder()
  .addSemanticQuery("intense emotional confrontation", 1.5)
  .addTextQuery("shouting arguing", 1.0)
  .filterByCharacters("JOHN", "MARY")
  .setMinScore(0.7);

const results = await search.execute(client);
```

## Error Handling

### Comprehensive Error Handler

```python
from enum import Enum
from typing import Dict, Any
import logging

class ScriptRAGError(Exception):
    """Base exception for ScriptRAG client errors."""
    pass

class APIError(ScriptRAGError):
    """API request failed."""
    def __init__(self, status_code: int, message: str, details: Dict | None = None):
        self.status_code = status_code
        self.details = details
        super().__init__(f"API Error {status_code}: {message}")

class ScriptNotFoundError(ScriptRAGError):
    """Script does not exist."""
    pass

class EmbeddingError(ScriptRAGError):
    """Embedding generation failed."""
    pass

class RobustScriptRAGClient(ScriptRAGClient):
    """Client with comprehensive error handling."""

    def __init__(self, base_url: str, retry_count: int = 3):
        super().__init__(base_url)
        self.retry_count = retry_count
        self.logger = logging.getLogger(__name__)

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response with proper error checking."""
        try:
            data = response.json()
        except ValueError:
            raise APIError(response.status_code, "Invalid JSON response")

        if response.status_code == 404:
            raise ScriptNotFoundError(data.get("error", "Resource not found"))

        if response.status_code >= 400:
            raise APIError(
                response.status_code,
                data.get("error", "Unknown error"),
                data.get("details")
            )

        return data

    def upload_script_with_retry(self, title: str, content: str,
                                author: str | None = None) -> Dict:
        """Upload script with automatic retry on failure."""
        last_error = None

        for attempt in range(self.retry_count):
            try:
                self.logger.info(f"Uploading script '{title}' (attempt {attempt + 1})")
                response = self.session.post(
                    f"{self.base_url}/scripts/upload",
                    json={"title": title, "content": content, "author": author},
                    timeout=30
                )
                return self._handle_response(response)

            except requests.exceptions.Timeout:
                last_error = "Request timed out"
                self.logger.warning(f"Timeout on attempt {attempt + 1}")

            except requests.exceptions.ConnectionError:
                last_error = "Connection failed"
                self.logger.warning(f"Connection error on attempt {attempt + 1}")

            except APIError as e:
                if e.status_code >= 500:  # Retry on server errors
                    last_error = str(e)
                    self.logger.warning(f"Server error on attempt {attempt + 1}: {e}")
                else:
                    raise  # Don't retry client errors

            if attempt < self.retry_count - 1:
                time.sleep(2 ** attempt)  # Exponential backoff

        raise ScriptRAGError(f"Failed after {self.retry_count} attempts: {last_error}")
```

## Performance Optimization

### 1. Connection Pooling

```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class OptimizedScriptRAGClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()

        # Configure connection pooling
        adapter = HTTPAdapter(
            pool_connections=100,
            pool_maxsize=100,
            max_retries=Retry(
                total=3,
                backoff_factor=0.3,
                status_forcelist=[500, 502, 503, 504]
            )
        )

        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
```

### 2. Caching Layer

```typescript
class CachedScriptRAGClient extends ScriptRAGClient {
  private cache: Map<string, { data: any; timestamp: number }> = new Map();
  private cacheTTL: number = 300000; // 5 minutes

  private getCacheKey(method: string, ...args: any[]): string {
    return `${method}:${JSON.stringify(args)}`;
  }

  private getFromCache(key: string): any | null {
    const cached = this.cache.get(key);
    if (!cached) return null;

    if (Date.now() - cached.timestamp > this.cacheTTL) {
      this.cache.delete(key);
      return null;
    }

    return cached.data;
  }

  private setCache(key: string, data: any): void {
    this.cache.set(key, { data, timestamp: Date.now() });
  }

  async getScript(scriptId: string): Promise<ScriptResponse> {
    const cacheKey = this.getCacheKey('getScript', scriptId);
    const cached = this.getFromCache(cacheKey);

    if (cached) return cached;

    const result = await super.getScript(scriptId);
    this.setCache(cacheKey, result);

    return result;
  }

  clearCache(): void {
    this.cache.clear();
  }
}
```

### 3. Batch Operations

```python
async def batch_generate_embeddings(script_ids: List[str],
                                  batch_size: int = 5) -> Dict[str, Any]:
    """Generate embeddings for multiple scripts efficiently."""
    results = {}

    for i in range(0, len(script_ids), batch_size):
        batch = script_ids[i:i + batch_size]

        # Process batch concurrently
        tasks = [
            client.generate_embeddings_async(script_id)
            for script_id in batch
        ]

        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for script_id, result in zip(batch, batch_results):
            if isinstance(result, Exception):
                results[script_id] = {"status": "error", "error": str(result)}
            else:
                results[script_id] = result

    return results
```

## Testing Your Integration

### Unit Tests

```python
import pytest
from unittest.mock import Mock, patch

class TestScriptRAGClient:
    @pytest.fixture
    def client(self):
        return ScriptRAGClient("http://test.local")

    @pytest.fixture
    def mock_response(self):
        mock = Mock()
        mock.json.return_value = {
            "id": "test-123",
            "title": "Test Script",
            "scene_count": 10
        }
        mock.status_code = 200
        mock.ok = True
        return mock

    def test_upload_script(self, client, mock_response):
        with patch.object(client.session, 'post', return_value=mock_response):
            result = client.upload_script("Test", "FADE IN...")

            assert result["id"] == "test-123"
            assert result["title"] == "Test Script"

            client.session.post.assert_called_once_with(
                "http://test.local/scripts/upload",
                json={"title": "Test", "content": "FADE IN...", "author": None}
            )

    def test_error_handling(self, client):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.ok = False
        mock_response.raise_for_status.side_effect = requests.HTTPError()

        with patch.object(client.session, 'post', return_value=mock_response):
            with pytest.raises(requests.HTTPError):
                client.upload_script("Test", "Content")
```

### Integration Tests

```javascript
describe('ScriptRAG Integration Tests', () => {
  let client: ScriptRAGClient;
  let testScriptId: string;

  beforeAll(async () => {
    client = new ScriptRAGClient();

    // Upload test script
    const script = await client.uploadScript(
      'Integration Test Script',
      testFountainContent
    );
    testScriptId = script.id;

    // Generate embeddings
    await client.generateEmbeddings(testScriptId);
  });

  afterAll(async () => {
    // Cleanup
    if (testScriptId) {
      await client.deleteScript(testScriptId);
    }
  });

  test('should search scenes by text', async () => {
    const results = await client.searchScenes('coffee', {
      scriptId: testScriptId
    });

    expect(results.results).toBeDefined();
    expect(results.total).toBeGreaterThan(0);
    expect(results.results[0]).toHaveProperty('scene_id');
  });

  test('should perform semantic search', async () => {
    const results = await client.semanticSearch(
      'characters having an argument',
      0.7,
      testScriptId
    );

    expect(results.results).toBeDefined();
    expect(results.results.every(r => r.score >= 0.7)).toBe(true);
  });

  test('should generate character graph', async () => {
    const graph = await client.getCharacterGraph(undefined, testScriptId);

    expect(graph.nodes).toBeDefined();
    expect(graph.edges).toBeDefined();
    expect(graph.nodes.length).toBeGreaterThan(0);
  });
});
```

## Security Considerations

### API Key Authentication (Future)

```python
class SecureScriptRAGClient(ScriptRAGClient):
    def __init__(self, base_url: str, api_key: str | None = None):
        super().__init__(base_url)
        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}'
            })

    def set_api_key(self, api_key: str):
        """Update API key for authenticated requests."""
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}'
        })
```

### Input Validation

```typescript
class SafeScriptRAGClient extends ScriptRAGClient {
  private validateScriptContent(content: string): void {
    const maxSize = 10 * 1024 * 1024; // 10MB

    if (content.length > maxSize) {
      throw new Error(`Script too large: ${content.length} bytes (max: ${maxSize})`);
    }

    // Basic Fountain format validation
    if (!content.includes('INT.') && !content.includes('EXT.')) {
      console.warn('Content may not be in Fountain format');
    }
  }

  private sanitizeQuery(query: string): string {
    // Remove potential injection attempts
    return query
      .replace(/[<>]/g, '')
      .trim()
      .substring(0, 1000); // Limit query length
  }

  async uploadScript(title: string, content: string, author?: string): Promise<ScriptResponse> {
    this.validateScriptContent(content);
    return super.uploadScript(title, content, author);
  }

  async searchScenes(query: string, options?: any): Promise<any> {
    const sanitizedQuery = this.sanitizeQuery(query);
    return super.searchScenes(sanitizedQuery, options);
  }
}
```

## Deployment Considerations

### Modern Python Deployment with uv/uvx

ScriptRAG uses modern Python packaging tools for deployment:

```bash
# Install ScriptRAG globally with uvx
uvx install scriptrag

# Or run directly without installation
uvx scriptrag analyze my-script.fountain

# For development deployment
uv sync --all-extras

# Environment variables work the same way
export SCRIPTRAG_API_URL=http://localhost:8000/api/v1
export SCRIPTRAG_TIMEOUT=30
export SCRIPTRAG_RETRY_COUNT=3
```

### Environment Configuration

```python
import os

class ConfigurableScriptRAGClient(ScriptRAGClient):
    @classmethod
    def from_environment(cls) -> 'ConfigurableScriptRAGClient':
        """Create client from environment variables."""
        base_url = os.getenv('SCRIPTRAG_API_URL', 'http://localhost:8000/api/v1')
        timeout = int(os.getenv('SCRIPTRAG_TIMEOUT', '30'))
        retry_count = int(os.getenv('SCRIPTRAG_RETRY_COUNT', '3'))

        client = cls(base_url)
        client.timeout = timeout
        client.retry_count = retry_count

        return client
```

## Next Steps

1. **Generate API Clients**: Use the OpenAPI spec to generate clients:

   ```bash
   # Python
   openapi-generator generate -i http://localhost:8000/api/v1/openapi.json \
     -g python -o ./scriptrag-python-client

   # TypeScript
   openapi-generator generate -i http://localhost:8000/api/v1/openapi.json \
     -g typescript-axios -o ./scriptrag-ts-client
   ```

2. **Explore Advanced Features**:
   - WebSocket support (coming soon)
   - Batch operations
   - Custom embedding models
   - Export integrations

3. **Build Applications**:
   - Script analysis dashboards
   - Collaborative writing tools
   - AI-powered story assistants
   - Production planning tools

4. **Contribute**:
   - Report issues on GitHub
   - Submit feature requests
   - Share your integrations

## Resources

- [API Reference](./api-reference.md) - Complete endpoint documentation
- [User Guide](./user-guide.md) - Guide for scriptwriters
- [Architecture](./architecture.md) - System design details
- [OpenAPI Spec](http://localhost:8000/api/v1/openapi.json) - Machine-readable API definition
