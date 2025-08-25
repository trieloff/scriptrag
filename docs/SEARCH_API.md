# ScriptRAG Search API Documentation

## Overview

The ScriptRAG search system provides a powerful, modular search infrastructure for querying screenplay content. The refactored architecture separates concerns into distinct modules for better maintainability and extensibility.

## Architecture

### Core Components

```text
search/
├── engine.py          # Main search engine orchestration
├── builder.py         # SQL query construction
├── utils.py          # Common search utilities
├── filters.py        # Result filtering logic
├── rankers.py        # Result ranking algorithms
├── parser.py         # Query parsing
├── models.py         # Data models
├── semantic_adapter.py # Semantic search integration
└── formatter.py      # Result formatting
```

### Module Responsibilities

#### SearchEngine (`engine.py`)

- Orchestrates the entire search process
- Manages database connections
- Coordinates SQL and semantic search
- Applies filters and ranking

#### QueryBuilder (`builder.py`)

- Constructs SQL queries from SearchQuery objects
- Handles complex JOIN operations
- Manages pagination

#### Search Utilities (`utils.py`)

- **SearchFilterUtils**: Common filtering operations
- **SearchTextUtils**: Text search operations  
- **SearchResultUtils**: Result processing utilities

#### Filters (`filters.py`)

- **CharacterFilter**: Filter by character presence
- **LocationFilter**: Filter by scene location
- **TimeOfDayFilter**: Filter by time (DAY/NIGHT)
- **SeasonEpisodeFilter**: Filter by season/episode
- **DuplicateFilter**: Remove duplicate results
- **SearchFilterChain**: Chain multiple filters

#### Rankers (`rankers.py`)

- **TextMatchRanker**: Score by text matching quality
- **RelevanceRanker**: Sort by relevance scores
- **ProximityRanker**: Score by term proximity
- **PositionalRanker**: Sort by script position
- **HybridRanker**: Combine multiple ranking strategies

## Usage Examples

### Basic Text Search

```python
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import SearchQuery

# Initialize engine
engine = SearchEngine()

# Create a simple text query
query = SearchQuery(
    raw_query="coffee shop",
    text_query="coffee shop",
    limit=10
)

# Execute search
response = await engine.search_async(query)

# Process results
for result in response.results:
    print(f"Scene {result.scene_number}: {result.scene_heading}")
    print(f"  {result.scene_content[:100]}...")
```

### Dialogue Search with Character Filter

```python
# Search for dialogue by a specific character
query = SearchQuery(
    raw_query="dialogue:hello character:WALTER",
    dialogue="hello",
    characters=["WALTER"],
    limit=5
)

response = await engine.search_async(query)
```

### Location-Based Search

```python
# Find all scenes in specific locations
query = SearchQuery(
    raw_query="location:office location:boardroom",
    locations=["OFFICE", "BOARDROOM"],
    limit=20
)

response = await engine.search_async(query)
```

### Season/Episode Range Search

```python
# Search within a season range
query = SearchQuery(
    raw_query="season 1-3 coffee",
    text_query="coffee",
    season_start=1,
    season_end=3,
    episode_start=1,
    episode_end=10,
    limit=15
)

response = await engine.search_async(query)
```

## Advanced Usage

### Custom Filtering Pipeline

```python
from scriptrag.search.filters import (
    SearchFilterChain,
    CharacterFilter,
    LocationFilter,
    TimeOfDayFilter
)

# Create a custom filter chain
filter_chain = SearchFilterChain()
filter_chain.add_filter(CharacterFilter(["WALTER", "JESSE"]))
filter_chain.add_filter(LocationFilter(["LAB", "RV"]))
filter_chain.add_filter(TimeOfDayFilter(["NIGHT"]))

# Apply to results
filtered_results = filter_chain.apply(results, query)
```

### Custom Ranking Strategy

```python
from scriptrag.search.rankers import HybridRanker, TextMatchRanker, ProximityRanker

# Create custom ranking configuration
custom_ranker = HybridRanker([
    (TextMatchRanker(), 0.5),      # 50% weight on text matching
    (ProximityRanker(), 0.3),      # 30% weight on term proximity
    (PositionalRanker(), 0.2),     # 20% weight on script position
])

# Apply ranking
ranked_results = custom_ranker.rank(results, query)
```

### Building Custom Queries

```python
from scriptrag.search.builder import QueryBuilder

builder = QueryBuilder()

# Build a complex search query
query = SearchQuery(
    raw_query="complex search",
    dialogue="specific dialogue",
    characters=["CHARACTER1", "CHARACTER2"],
    locations=["LOCATION1"],
    season_start=2,
    episode_start=5,
    limit=10,
    offset=20
)

sql, params = builder.build_search_query(query)
```

## Query Syntax

### Supported Query Types

| Type | Syntax | Example |
|------|--------|---------|
| Text | `text` | `coffee shop` |
| Dialogue | `dialogue:text` | `dialogue:hello world` |
| Action | `action:text` | `action:walks slowly` |
| Character | `character:name` | `character:WALTER` |
| Location | `location:place` | `location:office` |
| Season | `s1e5` or `season 1` | `s2e10` |
| Range | `s1e1-s2e5` | `s1e1-s1e10` |

### Combining Filters

Queries can combine multiple filters:

```text
dialogue:"I am the one" character:WALTER location:desert s4e1-s4e10
```

## Result Structure

### SearchResponse

```python
@dataclass
class SearchResponse:
    query: SearchQuery               # Original query
    results: list[SearchResult]      # Scene results
    bible_results: list[BibleSearchResult]  # Bible content results
    total_count: int                 # Total matching scenes
    bible_total_count: int          # Total bible matches
    has_more: bool                  # More results available
    execution_time_ms: float        # Query execution time
    search_methods: list[str]       # Methods used (sql, semantic)
```

### SearchResult

```python
@dataclass
class SearchResult:
    script_id: int
    script_title: str
    script_author: str | None
    scene_id: int
    scene_number: int
    scene_heading: str
    scene_location: str | None
    scene_time: str | None
    scene_content: str
    season: int | None
    episode: int | None
    match_type: str              # text, dialogue, action, etc.
    relevance_score: float       # 0.0 to 1.0
    matched_text: str | None
    character_name: str | None
```

## Performance Optimization

### Indexing Strategy

The search system uses several database indexes for optimal performance:

1. **Text indexes** on dialogue and action content
2. **B-tree indexes** on foreign keys and commonly filtered columns
3. **JSON indexes** for metadata fields (season, episode)

### Caching

- Query results are cached for 15 minutes
- Semantic embeddings are pre-computed and stored
- Database connections use read-only mode for better concurrency

### Batch Processing

- Multiple filters are applied in a single pass
- Ranking operations are vectorized when possible
- Duplicate removal is performed early in the pipeline

## Error Handling

The search system includes comprehensive error handling:

```python
try:
    response = await engine.search_async(query)
except DatabaseError as e:
    # Handle database-specific errors
    logger.error(f"Database error: {e.message}")
    logger.info(f"Hint: {e.hint}")
except ValueError as e:
    # Handle invalid query parameters
    logger.error(f"Invalid query: {e}")
except Exception as e:
    # Graceful degradation - return partial results if possible
    logger.error(f"Search error: {e}")
```

## Configuration

Search behavior can be configured via `ScriptRAGSettings`:

```python
settings = ScriptRAGSettings(
    # Semantic search settings
    search_vector_threshold=3,           # Word count threshold for semantic search
    search_vector_similarity_threshold=0.7,  # Minimum similarity score
    search_vector_result_limit_factor=2.0,   # Result multiplication factor
    search_vector_min_results=5,         # Minimum semantic results

    # Performance settings
    search_thread_timeout=30.0,          # Thread timeout in seconds

    # Database settings
    database_path=Path("scriptrag.db"),
)
```

## Testing

The search system includes comprehensive test coverage:

```bash
# Run all search tests
pytest tests/unit/search/
pytest tests/integration/test_search_refactor.py

# Run specific test categories
pytest tests/unit/search/test_engine.py
pytest tests/unit/search/test_builder.py
pytest tests/integration/test_search_refactor.py::TestSearchFilters
```

## Migration Guide

If you're migrating from the old search system:

### Old API

```python
# Old monolithic approach
results = search_engine.search_text("coffee", limit=10)
```

### New API

```python
# New modular approach
query = SearchQuery(raw_query="coffee", text_query="coffee", limit=10)
response = await engine.search_async(query)
results = response.results
```

### Key Changes

1. **Separation of Concerns**: Logic is now split across multiple modules
2. **Explicit Query Objects**: Use `SearchQuery` instead of parameters
3. **Async by Default**: Primary interface is async (sync wrapper available)
4. **Pluggable Components**: Filters and rankers can be customized
5. **Better Error Handling**: Comprehensive error types and messages

## Future Enhancements

Planned improvements for the search system:

1. **Full-text search indexes** using FTS5
2. **Query suggestion** and autocomplete
3. **Search analytics** and usage tracking
4. **Custom scoring functions** via plugins
5. **Distributed search** for large datasets
6. **Real-time index updates** via triggers

## Support

For issues or questions about the search API:

1. Check the [test files](../tests/integration/test_search_refactor.py) for examples
2. Review the [source code](../src/scriptrag/search/) for implementation details
3. Submit issues to the [GitHub repository](https://github.com/your-repo/scriptrag)
