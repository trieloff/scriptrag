# Database Indexer Component

This directory contains the database indexing system that maintains a searchable SQLite database from Fountain files and their metadata.

## Architecture Role

The Database Indexer is a **processing component** that:

- Reads from Fountain Files and Git LFS storage backends
- Writes to SQLite Database storage backend
- Called by Git Synchronizer
- Maintains search indices and relationships

## Key Responsibilities

1. **Parse and Index Fountain Files**
   - Extract all scenes with boneyard metadata
   - Build full-text search indices
   - Maintain script/series relationships

2. **Update Only Changed Content**
   - Use content hashes for change detection
   - Incremental updates for performance
   - Handle deletions and moves

3. **Maintain Search Indices**
   - Vector indices for semantic search
   - Text indices for dialogue search
   - Metadata indices for filtering


## Performance Optimizations

1. **Batch Operations**: Insert multiple scenes in one transaction
2. **Prepared Statements**: Reuse SQL statements
3. **Index Strategy**: Index only what's needed for queries
4. **Incremental Updates**: Only process changed content
5. **Connection Pooling**: Reuse database connections

## Error Handling

1. **Parse Errors**: Log and skip invalid files
2. **Database Errors**: Retry with backoff
3. **Missing Embeddings**: Index without vector data
4. **Schema Migrations**: Handle version upgrades

## Testing

Key test scenarios:

- Full indexing of test scripts
- Incremental update accuracy
- Character extraction
- Search index correctness
- Performance benchmarks
- Concurrent access

## Integration Points

- **Called by**: Git Synchronizer
- **Reads from**: Fountain Files, Git LFS storage backends
- **Writes to**: SQLite Database storage backend
- **Uses**: Fountain Parser

## Configuration

```yaml
indexer:
  database_path: ".scriptrag/cache.db"
  batch_size: 100
  enable_fts: true
  enable_vector_index: true
  auto_vacuum: true
  wal_mode: true  # For concurrent access
```
