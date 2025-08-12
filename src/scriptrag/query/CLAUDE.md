# Query Engine Component

This directory contains the query engine that enables semantic and structured search across the screenplay database.

## Architecture Role

The Query Engine is a **processing component** that:

- Reads from SQLite Database and Git LFS storage backends
- Called by CLI and MCP interfaces
- Performs vector similarity search and structured queries
- Ranks and presents search results

## Key Responsibilities

1. **Dialogue Search**
   - Full-text search across dialogue
   - Character-specific dialogue search
   - Fuzzy matching for variations

2. **Semantic Search**
   - Vector similarity using embeddings
   - Combine with metadata filters
   - Hybrid search (vector + keyword)

3. **Structured Queries**
   - Filter by location, time, characters
   - Complex metadata queries
   - Aggregate queries (character stats, etc.)

4. **Result Ranking**
   - Relevance scoring
   - Metadata boosting
   - Personalized ranking


## Performance Optimizations

1. **Embedding Cache**: Cache frequently queried embeddings
2. **Query Result Cache**: Cache common queries
3. **Index Optimization**: Ensure proper database indices
4. **Batch Loading**: Load multiple embeddings at once
5. **Approximate Search**: Use approximate algorithms for large datasets

## Testing

Key test scenarios:

- Dialogue search accuracy
- Semantic search relevance
- Filter combinations
- Ranking correctness
- Performance with large datasets
- Edge cases (empty queries, special characters)

## Integration Points

- **Called by**: CLI and MCP interfaces
- **Reads from**: SQLite Database, Git LFS storage backends
- **Uses**: Analyze API for query embeddings

## Configuration

```yaml
query:
  similarity_threshold: 0.7
  max_results: 100
  use_hybrid_search: true
  boost_metadata: true
  cache_embeddings: true
  cache_ttl: 3600  # seconds
  keyword_weight: 0.3
  vector_weight: 0.7
```
