# Storage Layer

This directory contains the storage layer implementations for all storage backends. Each subdirectory represents a different storage backend.

## Architecture Role

The storage layer provides storage backends where data is stored and retrieved. These are components that:

- Store data written by processing components
- Provide data when read by processing components
- Maintain data integrity and consistency

## Storage Components

- **git/**: Git repository operations (Fountain files, Script Bibles, Custom Insight Agents)
- **lfs/**: Git LFS operations for large files (embeddings)
- **database/**: SQLite database operations (scenes, scripts, characters, series)

## Design Principles

1. **Separation of Concerns**: Each storage type has its own module
2. **Common Interface**: All storage implements similar CRUD operations
3. **Transaction Support**: Atomic operations where possible
4. **Error Recovery**: Graceful handling of storage failures
5. **Performance**: Caching and batching where appropriate

## Common Patterns

All storage modules should implement these basic operations:

```python
class StorageInterface:
    """Common interface for storage backends."""

    def read(self, key: str) -> Any:
        """Read data by key."""
        raise NotImplementedError

    def write(self, key: str, data: Any) -> None:
        """Write data with key."""
        raise NotImplementedError

    def delete(self, key: str) -> None:
        """Delete data by key."""
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        raise NotImplementedError

    def list(self, prefix: str = "") -> List[str]:
        """List all keys with optional prefix."""
        raise NotImplementedError
```

## Transaction Support

For backends that support it:

```python
from contextlib import contextmanager

@contextmanager
def transaction(self):
    """Provide transaction context."""
    self.begin_transaction()
    try:
        yield
        self.commit()
    except Exception:
        self.rollback()
        raise
```

## Error Handling

Common storage exceptions:

```python
class StorageError(ScriptRAGError):
    """Base storage error."""

class NotFoundError(StorageError):
    """Key not found in storage."""

class WriteError(StorageError):
    """Failed to write to storage."""

class TransactionError(StorageError):
    """Transaction failed."""
```

## Performance Considerations

1. **Connection Pooling**: Reuse connections where possible
2. **Batch Operations**: Support bulk reads/writes
3. **Caching**: Implement appropriate caching strategies
4. **Async Support**: Consider async variants for I/O operations

## Testing

Each storage backend should have:

- Unit tests for CRUD operations
- Transaction tests
- Error handling tests
- Performance benchmarks
- Concurrent access tests
