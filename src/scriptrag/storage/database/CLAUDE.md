# SQLite Database Storage Component

This directory implements SQLite database operations for storing and querying scenes, scripts, characters, and series data with JSON support.

## Architecture Role

Database Storage is a **storage backend** that:

- Stores structured scene data with JSON documents
- Maintains relationships between entities
- Provides full-text and vector search capabilities
- Ensures ACID compliance for data integrity

## Key Responsibilities

1. **Data Persistence**
   - Store scenes as JSON documents
   - Maintain script/series/character relationships
   - Handle metadata and search indices

2. **Query Support**
   - Full-text search with FTS5
   - JSON path queries
   - Vector similarity search (with SQLite-vss)

3. **Performance**
   - Connection pooling
   - Query optimization
   - Index management

## Pre-Release Status & Migration Strategy

**IMPORTANT**: ScriptRAG is currently in pre-release. The database schema is subject to change, and **database migrations are NOT implemented**.

### Migration Philosophy

1. **No Migration Support**: During pre-release, breaking schema changes may occur without migration paths
2. **Rebuild on Change**: Users should expect to rebuild their database when upgrading
3. **Cache Database**: The SQLite database is a cache that can be regenerated from Fountain files
4. **Source of Truth**: Git repository with Fountain files is always the source of truth

### Handling Schema Changes

When the schema changes:

```bash
# Delete the old database
rm -rf .scriptrag/cache.db

# Rebuild from fountain files
scriptrag index --all
```

This approach is acceptable because:

- The database is a derived cache, not primary storage
- All data can be regenerated from Fountain files
- Simplifies pre-release development
- Avoids migration complexity before schema stabilizes

### Future Considerations

Once ScriptRAG reaches 1.0:

- Schema will be stabilized
- Migration system may be implemented
- Backward compatibility will be maintained








## Testing

Key test scenarios:

- CRUD operations for all entities
- JSON query functionality
- Transaction rollback
- Concurrent access
- Performance with large datasets
- FTS search accuracy
- Schema migrations
