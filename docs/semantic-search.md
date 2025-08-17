# Semantic Search with Vector Embeddings

ScriptRAG v2 now supports powerful semantic search capabilities using vector embeddings. This feature enables AI-assisted screenplay analysis that goes beyond simple keyword matching to understand the meaning and context of scenes.

## Overview

The semantic search functionality uses state-of-the-art language models to generate vector embeddings for scene content. These embeddings capture the semantic meaning of the text, allowing you to:

- Find scenes with similar themes or concepts
- Discover related scenes across different scripts
- Search using natural language queries
- Identify narrative patterns and motifs

## Key Features

### 1. Automatic Embedding Generation

When indexing scripts with the `--generate-embeddings` flag, ScriptRAG automatically generates embeddings for all scenes:

```bash
# Index scripts and generate embeddings
scriptrag index --generate-embeddings

# Index a specific script with embeddings
scriptrag index path/to/script.fountain --generate-embeddings
```

### 2. Natural Language Search

Use the existing search command with the `--fuzzy` flag to enable semantic search:

```bash
# Find scenes about betrayal and trust
scriptrag search --fuzzy "scenes about betrayal and broken trust"

# Find action sequences similar to a car chase
scriptrag search --fuzzy "high-speed car chase through city streets"

# Find emotional dialogue scenes
scriptrag search --fuzzy "heartfelt conversation between parent and child"
```

### 3. Find Related Scenes

Discover scenes that are semantically similar to a specific scene:

```python
from scriptrag.api.semantic_search import SemanticSearchService
from scriptrag.config import get_settings

# Initialize the service
settings = get_settings()
semantic_search = SemanticSearchService(settings)

# Find scenes related to scene ID 42
related = await semantic_search.find_related_scenes(
    scene_id=42,
    top_k=5,  # Return top 5 most similar
    threshold=0.7  # Minimum similarity score
)

for scene in related:
    print(f"Scene: {scene.heading}")
    print(f"Similarity: {scene.similarity_score:.2f}")
    print(f"Content: {scene.content[:200]}...")
    print()
```

### 4. Advanced Similarity Search

For more control over the search process:

```python
# Search for scenes similar to a custom query
results = await semantic_search.search_similar_scenes(
    query="A tense negotiation in a dimly lit warehouse",
    script_id=10,  # Optional: limit to specific script
    top_k=10,
    threshold=0.6
)

# Results include similarity scores
for result in results:
    print(f"{result.heading}: {result.similarity_score:.2%} match")
```

## Architecture

### Embedding Storage

ScriptRAG uses a hybrid storage approach for embeddings:

1. **Database Storage**: Embeddings are stored in the SQLite database for fast retrieval
2. **Git LFS**: Large embedding files are tracked with Git LFS for version control
3. **Cache Layer**: Frequently accessed embeddings are cached in memory

### Embedding Models

By default, ScriptRAG uses OpenAI's `text-embedding-3-small` model, which provides:

- 1536-dimensional vectors
- Excellent semantic understanding
- Fast generation times
- Cost-effective pricing

You can configure different models in your settings:

```yaml
# .scriptrag.yml
embedding:
  model: text-embedding-3-small
  dimensions: 1536
  cache_enabled: true
```

### Vector Similarity

ScriptRAG uses cosine similarity to compare embedding vectors, which measures the angle between vectors rather than their magnitude. This provides robust similarity scores between -1 and 1:

- 1.0: Identical meaning
- 0.7-0.9: Very similar
- 0.5-0.7: Moderately similar
- < 0.5: Different concepts

## Performance Optimization

### Caching

Embeddings are cached at multiple levels:

1. **Generation Cache**: Avoids regenerating embeddings for identical text
2. **Database Cache**: SQLite's built-in caching for frequently accessed embeddings
3. **LFS Cache**: Git LFS caches downloaded embedding files

### Batch Processing

Generate embeddings for multiple scripts efficiently:

```bash
# Generate missing embeddings for all indexed scripts
scriptrag embeddings generate --batch-size 20
```

### Incremental Updates

Only generate embeddings for new or modified scenes:

```bash
# Update embeddings for changed content
scriptrag index --update-embeddings
```

## Use Cases

### 1. Theme Analysis

Find all scenes that explore specific themes:

```bash
# Find scenes about redemption
scriptrag search --fuzzy "redemption and forgiveness"

# Find scenes with family conflict
scriptrag search --fuzzy "family disagreement and tension"
```

### 2. Mood and Tone Matching

Identify scenes with similar emotional tone:

```bash
# Find uplifting, hopeful scenes
scriptrag search --fuzzy "uplifting moment of hope and triumph"

# Find dark, suspenseful scenes
scriptrag search --fuzzy "dark suspenseful atmosphere with danger"
```

### 3. Character Arc Tracking

Track character development across scenes:

```bash
# Find scenes showing character growth
scriptrag search --fuzzy "character realizes their mistake and changes"

# Find confrontation scenes
scriptrag search --fuzzy "heated confrontation between rivals"
```

### 4. Visual Similarity

Find scenes with similar visual elements:

```bash
# Find scenes with similar settings
scriptrag search --fuzzy "rain-soaked city streets at night"

# Find action sequences
scriptrag search --fuzzy "elaborate fight choreography in confined space"
```

## API Integration

### Python API

```python
from scriptrag.api.semantic_search import SemanticSearchService
from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.config import get_settings

async def semantic_analysis():
    settings = get_settings()

    # Initialize services
    embedding_service = EmbeddingService(settings)
    semantic_search = SemanticSearchService(settings, embedding_service=embedding_service)

    # Generate embedding for custom text
    embedding = await embedding_service.generate_embedding(
        "A pivotal moment of self-discovery"
    )

    # Search using the embedding directly
    results = await semantic_search.search_similar_scenes(
        query="A pivotal moment of self-discovery",
        top_k=10,
        threshold=0.7
    )

    return results
```

### MCP Integration

The semantic search capabilities are available through the MCP protocol:

```python
# In MCP tools
{
    "tool": "search_scenes",
    "arguments": {
        "query": "emotional farewell at airport",
        "fuzzy": true,
        "limit": 5
    }
}
```

## Best Practices

### 1. Query Formulation

- Be descriptive but concise
- Include key concepts and emotions
- Use natural language, not keywords
- Mention visual elements when relevant

### 2. Threshold Selection

- **0.8+**: Nearly identical scenes
- **0.6-0.8**: Similar themes and content
- **0.4-0.6**: Related but distinct
- **< 0.4**: Different concepts

### 3. Performance Tips

- Generate embeddings during off-peak hours
- Use batch processing for large scripts
- Enable caching for production use
- Consider using Git LFS for team collaboration

### 4. Cost Management

- Cache embeddings aggressively
- Use batch API calls when possible
- Monitor API usage through settings
- Consider self-hosted models for high volume

## Troubleshooting

### Common Issues

1. **No embeddings found**
   - Ensure scripts were indexed with `--generate-embeddings`
   - Check that LLM provider is configured correctly
   - Verify API keys and permissions

2. **Slow search performance**
   - Enable caching in settings
   - Reduce the number of candidate scenes
   - Use more specific script_id filters

3. **Poor search results**
   - Adjust similarity threshold
   - Improve query descriptions
   - Ensure embeddings are up-to-date

4. **API rate limits**
   - Enable request throttling
   - Use batch processing
   - Implement exponential backoff

## Advanced Configuration

### Custom Embedding Models

```python
from scriptrag.api.embedding_service import EmbeddingService

class CustomEmbeddingService(EmbeddingService):
    def __init__(self, settings):
        super().__init__(settings)
        self.default_model = "custom-model-name"
        self.embedding_dimensions = 768
```

### Vector Database Integration

For production deployments with millions of scenes, consider integrating a dedicated vector database:

```python
# Future support for vector databases
from scriptrag.vector_db import ChromaDBAdapter, PineconeAdapter

# Configure vector database
vector_db = ChromaDBAdapter(
    collection="screenplay_scenes",
    distance_metric="cosine"
)
```

## Conclusion

Semantic search with vector embeddings transforms ScriptRAG into a powerful AI-assisted screenplay analysis tool. By understanding the meaning and context of scenes rather than just matching keywords, you can discover insights and patterns that would be impossible to find with traditional search methods.

Start exploring your screenplays in entirely new ways with semantic search!
