# Bulk Import Error Handling Improvements

## Summary

Enhanced the bulk import feature with robust error handling, transaction support, and recovery mechanisms to prevent partial imports and data corruption.

## Key Improvements

### 1. Database Transaction Support

- Wrapped each batch in a database transaction
- Automatic rollback on any failure within a batch
- Commits only on full batch success
- Prevents partial imports and maintains data consistency

### 2. Enhanced Error Reporting

- Added error categorization (PARSING, VALIDATION, DATABASE, GRAPH, FILESYSTEM, UNKNOWN)
- Includes line numbers for parsing errors when available
- Provides actionable suggestions for common errors
- Full stack traces logged for debugging
- Error summary grouped by category

### 3. Recovery Mechanisms

- Import state persistence to JSON file (`~/.scriptrag/import_state.json`)
- Files marked with status: PENDING, SUCCESS, FAILED, RETRY_PENDING, SKIPPED
- `--retry-failed` flag to retry failed imports
- New `script resume` command to continue interrupted imports
- Automatic retry candidates for transient errors (e.g., database locks)

### 4. Progress Improvements

- Real-time ETA calculation based on batch processing times
- Shows current file being processed in verbose mode
- Performance metrics (files/second, total duration)
- Periodic state saves during long imports

## New CLI Features

### Import Command Enhancements

```bash
# Retry previously failed imports
scriptrag script import "path/**/*.fountain" --retry-failed

# Enable verbose logging for debugging
scriptrag script import "path/**/*.fountain" --verbose

# Use custom state file
scriptrag script import "path/**/*.fountain" --state-file /path/to/state.json
```

### Resume Command

```bash
# Resume interrupted import
scriptrag script resume

# Resume with custom state file
scriptrag script resume --state-file /path/to/state.json
```

## Error Categories

- **PARSING**: Invalid Fountain format, syntax errors
- **DATABASE**: Connection issues, constraint violations, locks
- **GRAPH**: Graph creation failures (non-fatal)
- **FILESYSTEM**: Permission errors, file access issues
- **VALIDATION**: Data validation errors
- **UNKNOWN**: Unexpected errors

## Implementation Details

### Transaction Handling

```python
# Each batch is processed in a transaction
with self.graph_ops.connection.transaction() as conn:
    # Validate all files first
    for file in batch:
        validate_file(file)

    # Import all validated files
    for file in batch:
        import_file(file, conn)

# Transaction commits on success, rolls back on any exception
```

### Error Information Structure

```python
ImportErrorInfo = {
    "category": ErrorCategory,
    "message": str,
    "details": dict,
    "stack_trace": str | None,
    "suggestions": list[str]
}
```

### State Persistence Format

```json
{
    "started_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:10:00",
    "total_files": 100,
    "files": {
        "path/to/file.fountain": {
            "status": "success",
            "script_id": "uuid",
            "error": null,
            "last_attempt": "2024-01-01T00:05:00"
        }
    },
    "batch_size": 10,
    "series_cache": {},
    "season_cache": {}
}
```

## Testing

Comprehensive test suite added in `tests/test_bulk_import_error_handling.py`:

- Error categorization
- Transaction rollback behavior
- State persistence and recovery
- Progress reporting with ETA
- Batch failure handling
- Performance metrics

## Future Enhancements

1. Parallel processing for independent files
2. Automatic retry with exponential backoff
3. Web UI for import progress monitoring
4. Import history and analytics
5. Configurable error thresholds
