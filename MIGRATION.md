# ScriptRAG Migration Guide

## Configuration Changes

### Consolidation of SQLite WAL Mode Settings (2025-08-24)

**Breaking Change**: The `database_wal_mode` boolean setting has been removed in favor of using the existing `database_journal_mode` setting directly.

#### What Changed

- **Removed**: `database_wal_mode` (boolean) setting
- **Retained**: `database_journal_mode` (string) setting which controls the same functionality

#### Migration Steps

If you were using `database_wal_mode` in your configuration:

1. **Remove** any references to `database_wal_mode` from your configuration files
2. **Ensure** `database_journal_mode` is set to `"WAL"` if you want Write-Ahead Logging enabled

##### Configuration File Examples

**Before (OLD)**:

```yaml
# scriptrag.yaml
database_wal_mode: true
```

```toml
# scriptrag.toml
database_wal_mode = true
```

```bash
# .env
SCRIPTRAG_DATABASE_WAL_MODE=true
```

**After (NEW)**:

```yaml
# scriptrag.yaml
database_journal_mode: WAL
```

```toml
# scriptrag.toml
database_journal_mode = "WAL"
```

```bash
# .env
SCRIPTRAG_DATABASE_JOURNAL_MODE=WAL
```

#### Why This Change?

- **Redundancy**: Both settings controlled the same SQLite feature
- **Clarity**: Single source of truth for journal mode configuration
- **Flexibility**: `database_journal_mode` supports all SQLite journal modes (DELETE, TRUNCATE, PERSIST, MEMORY, WAL, OFF)

#### Default Behavior

The default value for `database_journal_mode` remains `"WAL"`, so if you were relying on the default behavior, no action is required.

#### Troubleshooting

If you encounter errors after updating:

1. Check that you've removed all references to `database_wal_mode`
2. Verify `database_journal_mode` is set to a valid value: DELETE, TRUNCATE, PERSIST, MEMORY, WAL, or OFF
3. For production systems, `"WAL"` is recommended for better concurrency

---

*For questions or issues, please refer to the [documentation](docs/configuration.md) or open an issue on GitHub.*
