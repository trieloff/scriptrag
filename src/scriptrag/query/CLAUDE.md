# Query Engine Component

This directory contains the query engine that enables semantic and structured search across the screenplay database.

## Architecture Role

The Query Engine is an **Actor** in the FMC architecture. It:

- Reads from SQLite Database and Git LFS (Places)
- Called by CLI and MCP interfaces (through channels)
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

## Implementation Guidelines

```python
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import sqlite3

from ..models import Scene, SearchResult, SearchQuery
from ..storage.database import DatabaseStorage
from ..storage.lfs import LFSStorage
from ..embeddings import EmbeddingGenerator
from ..exceptions import QueryError


@dataclass
class QueryConfig:
    """Query engine configuration."""
    similarity_threshold: float = 0.7
    max_results: int = 100
    use_hybrid_search: bool = True
    boost_metadata_matches: bool = True


class QueryEngine:
    """Execute searches against the screenplay database."""

    def __init__(
        self,
        db: Optional[DatabaseStorage] = None,
        lfs: Optional[LFSStorage] = None,
        embedding_gen: Optional[EmbeddingGenerator] = None,
        config: Optional[QueryConfig] = None
    ):
        self.db = db or DatabaseStorage()
        self.lfs = lfs or LFSStorage()
        self.embedding_gen = embedding_gen or EmbeddingGenerator()
        self.config = config or QueryConfig()

    def search_dialogue(
        self,
        query: str,
        character: Optional[str] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        """Search for dialogue containing query text."""
        # Build FTS query
        fts_query = self._build_fts_query(query)

        # Base SQL
        sql = """
            SELECT
                s.content_hash,
                s.scene_data,
                fts.rank as score
            FROM scenes s
            JOIN scenes_fts fts ON s.content_hash = fts.content_hash
            WHERE scenes_fts MATCH ?
        """
        params = [fts_query]

        # Add character filter if specified
        if character:
            sql += """
                AND EXISTS (
                    SELECT 1 FROM json_each(s.scene_data, '$.content.dialogue')
                    WHERE json_extract(value, '$.character') = ?
                )
            """
            params.append(character)

        sql += " ORDER BY fts.rank LIMIT ?"
        params.append(limit)

        # Execute query
        results = self.db.execute(sql, params).fetchall()

        # Convert to SearchResult objects
        return [self._build_search_result(row) for row in results]

    def semantic_search(
        self,
        query: str,
        filters: Optional[Dict] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        """Search using semantic similarity."""
        # Generate query embedding
        query_embedding = self._get_query_embedding(query)

        if self.config.use_hybrid_search:
            # Combine with keyword search
            return self._hybrid_search(
                query,
                query_embedding,
                filters,
                limit
            )
        else:
            # Pure vector search
            return self._vector_search(
                query_embedding,
                filters,
                limit
            )
```

## Vector Search Implementation

```python
def _vector_search(
    self,
    query_embedding: np.ndarray,
    filters: Optional[Dict],
    limit: int
) -> List[SearchResult]:
    """Pure vector similarity search."""
    # Get all candidate scenes
    candidates = self._get_candidates(filters)

    # Calculate similarities
    similarities = []
    for scene_hash, embedding_path in candidates:
        scene_embedding = self._load_embedding(embedding_path)
        similarity = self._cosine_similarity(
            query_embedding,
            scene_embedding
        )
        if similarity >= self.config.similarity_threshold:
            similarities.append((scene_hash, similarity))

    # Sort by similarity
    similarities.sort(key=lambda x: x[1], reverse=True)

    # Fetch scene data for top results
    results = []
    for scene_hash, score in similarities[:limit]:
        scene_data = self.db.get_scene(scene_hash)
        results.append(SearchResult(
            scene=scene_data,
            score=score,
            match_type="semantic"
        ))

    return results

def _cosine_similarity(
    self,
    vec1: np.ndarray,
    vec2: np.ndarray
) -> float:
    """Calculate cosine similarity between vectors."""
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    return dot_product / (norm1 * norm2)
```

## Hybrid Search

```python
def _hybrid_search(
    self,
    query: str,
    query_embedding: np.ndarray,
    filters: Optional[Dict],
    limit: int
) -> List[SearchResult]:
    """Combine vector and keyword search."""
    # Get keyword search results
    keyword_results = self.search_dialogue(
        query,
        limit=limit * 2  # Get more for merging
    )
    keyword_scores = {
        r.scene.content_hash: r.score
        for r in keyword_results
    }

    # Get vector search results
    vector_results = self._vector_search(
        query_embedding,
        filters,
        limit * 2
    )
    vector_scores = {
        r.scene.content_hash: r.score
        for r in vector_results
    }

    # Combine scores
    all_hashes = set(keyword_scores.keys()) | set(vector_scores.keys())
    combined_scores = []

    for scene_hash in all_hashes:
        # Weighted combination
        keyword_score = keyword_scores.get(scene_hash, 0)
        vector_score = vector_scores.get(scene_hash, 0)

        combined_score = (
            0.3 * keyword_score +
            0.7 * vector_score
        )

        # Boost if appears in both
        if keyword_score > 0 and vector_score > 0:
            combined_score *= 1.2

        combined_scores.append((scene_hash, combined_score))

    # Sort and return top results
    combined_scores.sort(key=lambda x: x[1], reverse=True)

    results = []
    for scene_hash, score in combined_scores[:limit]:
        scene_data = self.db.get_scene(scene_hash)
        results.append(SearchResult(
            scene=scene_data,
            score=score,
            match_type="hybrid"
        ))

    return results
```

## Metadata Filtering

```python
def _build_filter_clause(self, filters: Dict) -> Tuple[str, List]:
    """Build SQL WHERE clause from filters."""
    clauses = []
    params = []

    if "location" in filters:
        clauses.append("location LIKE ?")
        params.append(f"%{filters['location']}%")

    if "characters" in filters:
        # All specified characters must be present
        for char in filters["characters"]:
            clauses.append("""
                json_extract(scene_data, '$.extracted.characters')
                LIKE ?
            """)
            params.append(f"%{char}%")

    if "emotional_tone" in filters:
        clauses.append("""
            json_extract(scene_data, '$.extracted.emotional_tone') = ?
        """)
        params.append(filters["emotional_tone"])

    if "series_id" in filters:
        clauses.append("""
            script_id IN (
                SELECT id FROM scripts WHERE series_id = ?
            )
        """)
        params.append(filters["series_id"])

    where_clause = " AND ".join(clauses) if clauses else "1=1"
    return where_clause, params
```

## Result Ranking

```python
def _apply_metadata_boost(
    self,
    results: List[SearchResult],
    query: str
) -> List[SearchResult]:
    """Boost results based on metadata matches."""
    query_lower = query.lower()

    for result in results:
        boost = 1.0

        # Boost if query matches character names
        characters = result.scene.metadata.get("characters", [])
        if any(query_lower in char.lower() for char in characters):
            boost *= 1.3

        # Boost if query matches themes
        themes = result.scene.metadata.get("themes", [])
        if any(query_lower in theme.lower() for theme in themes):
            boost *= 1.2

        # Boost if query matches location
        if query_lower in result.scene.location.lower():
            boost *= 1.1

        result.score *= boost

    # Re-sort by boosted scores
    results.sort(key=lambda r: r.score, reverse=True)
    return results
```

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

- **Called by**: CLI and MCP interfaces (via channels)
- **Reads from**: SQLite Database, Git LFS (Places)
- **Uses**: Embedding Generator for query embeddings

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
