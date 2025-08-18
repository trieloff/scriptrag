# Migration Plan: SQLite VSS to SQLite-vec

## Executive Summary

**Recommendation**: Migrate ScriptRAG from current SQLite VSS implementation to **SQLite-vec** to solve macOS compatibility issues and gain performance improvements.

**Key Benefits**:

- ✅ **Solves macOS issue**: Works without SQLite extension loading support
- ✅ **Drop-in compatible**: Current schema already works with SQLite-vec
- ✅ **Active development**: Mozilla-sponsored, production-ready
- ✅ **Better performance**: Native C implementation with AVX/NEON optimizations
- ✅ **Advanced features**: Quantization, Matryoshka embeddings, partition keys

**Risk Level**: **Low** - Our existing code is already compatible with SQLite-vec's API

## Current State Analysis

### Existing Implementation

- **Files affected**:
  - `src/scriptrag/storage/vss_service.py` - Main VSS service implementation
  - `tests/unit/test_vss_service.py` - VSS service tests
  - Database schema uses virtual tables for embeddings

### Current Issues

1. macOS default SQLite lacks `enable_load_extension` support
2. Temporary graceful degradation masks functionality loss
3. Complex CI/CD workarounds needed for macOS

## Migration Strategy

### Phase 1: Drop-in Replacement (Week 1)

**Goal**: Replace SQLite-vss with SQLite-vec with minimal changes

#### 1.1 Update Dependencies

```toml
# pyproject.toml
[project.dependencies]
- "sqlite-vss>=0.1.0"  # Remove old VSS
+ "sqlite-vec>=0.1.7"   # Add sqlite-vec
```

#### 1.2 Update VSSService

```python
# src/scriptrag/storage/vss_service.py
import sqlite3
import sqlite_vec
from sqlite_vec import serialize_float32

class VSSService:
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection with sqlite-vec loaded."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row

        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")

        # Load sqlite-vec extension
        # This works even on macOS!
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        return conn

    def store_scene_embedding(
        self,
        scene_id: int,
        embedding: list[float] | np.ndarray,
        model: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        """Store scene embedding using sqlite-vec."""
        # ... existing code ...

        # Use sqlite-vec's serialization
        if isinstance(embedding, list):
            embedding_blob = serialize_float32(embedding)
        else:
            # NumPy arrays work directly via Buffer protocol
            embedding_blob = embedding.astype(np.float32)

        conn.execute(
            """
            INSERT OR REPLACE INTO scene_embeddings
            (scene_id, embedding_model, embedding)
            VALUES (?, ?, ?)
            """,
            (scene_id, model, embedding_blob),
        )
```

#### 1.3 Update Schema (Compatible, No Changes Required)

```sql
-- Current schema already works with sqlite-vec!
CREATE VIRTUAL TABLE scene_embeddings USING vec0(
    scene_id INTEGER PRIMARY KEY,
    embedding_model TEXT,
    embedding FLOAT[1536]
);
```

#### 1.4 Update Tests

```python
# tests/unit/test_vss_service.py
import sqlite_vec

@pytest.fixture
def vss_service(mock_settings, tmp_path):
    """Create VSS service with in-memory database."""
    db_path = tmp_path / "test.db"
    mock_settings.database_path = db_path

    # Mock sqlite-vec loading for unit tests
    with patch("scriptrag.storage.vss_service.sqlite_vec.load"):
        service = VSSService(mock_settings, db_path)
        # ... rest of fixture
```

### Phase 2: Optimization (Week 2-3)

**Goal**: Leverage SQLite-vec's advanced features for better performance

#### 2.1 Add Partition Keys for Script-level Sharding

```sql
CREATE VIRTUAL TABLE scene_embeddings_v2 USING vec0(
    scene_id INTEGER PRIMARY KEY,
    script_id INTEGER partition key,  -- Shard by script
    embedding FLOAT[1536],
    embedding_model TEXT,  -- Metadata column for filtering
    +scene_content TEXT,   -- Auxiliary column to avoid JOINs
    chunk_size=32
);
```

#### 2.2 Use Metadata Columns for Filtering

```python
def search_similar_scenes(
    self,
    query_embedding: np.ndarray,
    model: str,
    script_id: int | None = None,
    limit: int = 10,
) -> list[dict]:
    """Search using sqlite-vec with metadata filtering."""

    # sqlite-vec supports metadata filtering directly
    params = [serialize_float32(query_embedding), limit]
    where_clauses = ["embedding MATCH ?", "k = ?"]

    if model:
        where_clauses.append("embedding_model = ?")
        params.append(model)

    if script_id:
        where_clauses.append("script_id = ?")
        params.append(script_id)

    query = f"""
        SELECT scene_id, distance, scene_content
        FROM scene_embeddings_v2
        WHERE {' AND '.join(where_clauses)}
        ORDER BY distance
        LIMIT ?
    """
    params.append(limit)

    return conn.execute(query, params).fetchall()
```

#### 2.3 Add Auxiliary Columns to Reduce JOINs

```python
def store_scene_with_content(
    self,
    scene_id: int,
    script_id: int,
    embedding: np.ndarray,
    model: str,
    content: str,
) -> None:
    """Store embedding with content to avoid JOINs during search."""
    conn.execute(
        """
        INSERT INTO scene_embeddings_v2
        (scene_id, script_id, embedding, embedding_model, scene_content)
        VALUES (?, ?, ?, ?, ?)
        """,
        (scene_id, script_id, embedding, model, content),
    )
```

### Phase 3: Advanced Features (Week 4+)

**Goal**: Explore advanced SQLite-vec capabilities

#### 3.1 Binary Quantization for Storage Optimization

```python
def store_quantized_embedding(
    self,
    scene_id: int,
    embedding: np.ndarray,
    model: str,
) -> None:
    """Store binary quantized embeddings for 32x smaller storage."""
    import sqlite_vec

    # Store both full and quantized versions
    conn.execute("""
        INSERT INTO scene_embeddings_quantized
        (scene_id, embedding_binary, embedding_full)
        VALUES (?, vec_quantize_binary(?), ?)
    """, (scene_id, embedding, embedding))
```

#### 3.2 Matryoshka Embeddings Support

```python
def search_with_matryoshka(
    self,
    query_embedding: np.ndarray,
    dimensions: int = 512,  # Use subset of 1536-dim embedding
) -> list[dict]:
    """Search using Matryoshka embedding subsets."""
    # Use vec_slice for dimension reduction
    return conn.execute("""
        SELECT scene_id,
               vec_distance_cosine(
                   vec_slice(embedding, 0, ?),
                   vec_slice(?, 0, ?)
               ) as distance
        FROM scene_embeddings
        ORDER BY distance
        LIMIT 10
    """, (dimensions, query_embedding, dimensions)).fetchall()
```

## Testing Plan

### 1. Unit Tests

- [x] Mock SQLite-vec loading for fast tests
- [ ] Test vector serialization/deserialization
- [ ] Test distance calculations
- [ ] Test metadata filtering

### 2. Integration Tests

- [ ] Test with real SQLite-vec library
- [ ] Verify macOS compatibility without special setup
- [ ] Performance benchmarks vs. old implementation
- [ ] Test migration from existing databases

### 3. Platform Testing

- [ ] Linux (Ubuntu CI)
- [ ] macOS (without Homebrew SQLite)
- [ ] Windows
- [ ] Python 3.11, 3.12, 3.13

## Risk Assessment & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API breaking changes | Medium | Low | Pin to specific version (0.1.7) |
| Performance regression | Low | Medium | Benchmark before/after |
| Data migration issues | Low | High | Create backup, test migration script |
| Platform incompatibility | Low | High | Test on all platforms in CI |

## Implementation Timeline

### Week 1: Phase 1 Implementation

- [ ] Update dependencies
- [ ] Modify VSSService for SQLite-vec
- [ ] Update unit tests
- [ ] Test on all platforms

### Week 2: Phase 2 Planning

- [ ] Design optimized schema
- [ ] Plan data migration strategy
- [ ] Create benchmark suite

### Week 3: Phase 2 Implementation

- [ ] Implement partition keys
- [ ] Add auxiliary columns
- [ ] Update search queries
- [ ] Run benchmarks

### Week 4: Documentation & Rollout

- [ ] Update documentation
- [ ] Create migration guide
- [ ] Release new version
- [ ] Monitor for issues

## Code Changes Checklist

### Files to Modify

- [ ] `pyproject.toml` - Update dependencies
- [ ] `src/scriptrag/storage/vss_service.py` - Update to use SQLite-vec
- [ ] `src/scriptrag/database/sql/vss_migration.sql` - Update schema
- [ ] `tests/unit/test_vss_service.py` - Update mocks
- [ ] `README.md` - Remove macOS SQLite warnings
- [ ] `.github/workflows/ci.yml` - Remove macOS SQLite workarounds
- [ ] `CLAUDE.md` - Update with SQLite-vec specifics

### Files to Remove

- [ ] `ISSUE_SQLITE_VSS_MACOS.md` - Issue resolved by migration
- [ ] macOS-specific SQLite installation docs

### Files to Add

- [ ] `docs/VECTOR_SEARCH.md` - Document SQLite-vec features
- [ ] `scripts/migrate_vss.py` - Migration script for existing databases

## Decision Matrix

| Criteria | Keep Current VSS | Migrate to SQLite-vec |
|----------|------------------|----------------------|
| macOS Compatibility | ❌ Requires workarounds | ✅ Works out of box |
| Maintenance | ❌ Unknown status | ✅ Mozilla-sponsored |
| Performance | ⭕ Adequate | ✅ Optimized C code |
| Features | ⭕ Basic | ✅ Advanced (quantization, etc.) |
| Migration Effort | ✅ None | ⭕ Minimal (1-2 weeks) |
| **Overall Score** | **2/5** | **4.5/5** |

## Recommendation

**Strongly recommend** migrating to SQLite-vec for the following reasons:

1. **Immediate solution** to macOS compatibility issues
2. **Minimal migration effort** - existing code is already compatible
3. **Future-proof** - Active development and Mozilla sponsorship
4. **Performance gains** - Native C with SIMD optimizations
5. **Advanced features** - Quantization, Matryoshka embeddings, etc.

The migration can be done incrementally, starting with a drop-in replacement (Phase 1) that immediately solves the macOS issue, followed by optional optimizations in later phases.

## Next Steps

1. **Review and approve** this migration plan
2. **Create feature branch** for SQLite-vec migration
3. **Implement Phase 1** (drop-in replacement)
4. **Test on all platforms**
5. **Merge and release**

## References

- [SQLite-vec Documentation](https://alexgarcia.xyz/sqlite-vec/)
- [SQLite-vec GitHub](https://github.com/asg017/sqlite-vec)
- [Current VSS Implementation](src/scriptrag/storage/vss_service.py)
- [Migration Script Template](https://github.com/asg017/sqlite-vec/blob/main/examples/migrate.py)
