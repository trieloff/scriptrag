# Scene Index Update Research Findings

## Summary

The ScriptRAG indexing system **correctly handles scene insertions, removals, and reordering** when the `--force` flag is used. However, without the force flag, the system fails to detect content changes and does not update the database, leading to stale data.

## Key Findings

### 1. Working Scenario (with --force flag)

When `scriptrag index --force` is used:

- The system calls `clear_script_data()` which deletes all existing scenes and characters
- All scenes are re-indexed from scratch with correct scene numbers
- Scene insertions, removals, and reordering are handled correctly
- No stale data remains in the database

### 2. Problem Scenario (without --force flag)

When `scriptrag index` is used without force:

- The system only checks if a script exists in the database
- It does NOT check if the content has changed
- Modified scripts are skipped entirely
- Database retains old scene data even when scenes are added/removed

### 3. Root Cause Analysis

The issue is in the `_filter_scripts_for_indexing` method in `src/scriptrag/api/index.py`:

```python
def _filter_scripts_for_indexing(self, scripts):
    # ...
    existing = self.db_ops.get_existing_script(conn, script_meta.file_path)
    if existing is None:
        # New script, needs indexing
        scripts_to_index.append(script_meta)
    else:
        # Check if script has been modified since last index
        metadata = existing.metadata or {}
        last_indexed = metadata.get("last_indexed")
        if last_indexed:
            # Could compare with file modification time
            # For now, skip if already indexed  <-- PROBLEM: Always skips!
            logger.debug(f"Script already indexed: {script_meta.file_path}")
        else:
            scripts_to_index.append(script_meta)
```

The method has a TODO comment about comparing file modification times but currently always skips already-indexed scripts regardless of changes.

## Test Results

All 8 integration tests pass, demonstrating:

- ✅ Initial indexing works correctly
- ✅ Scene insertion with force flag works
- ✅ Scene removal with force flag works  
- ✅ Scene reordering with force flag works
- ✅ No stale scenes remain after removal (with force)
- ✅ Multiple rapid updates work correctly (with force)
- ✅ Content hashes are properly updated
- ✅ Without force flag, changes are ignored (expected but problematic)

## Implications

1. **Users must always use --force flag** when re-indexing modified scripts
2. **Automatic change detection is not implemented** despite the infrastructure being in place
3. **Scene numbers are properly managed** - the database uses scene_number not IDs for ordering
4. **Cascade deletes work correctly** - removing scenes also removes associated dialogues/actions

## Recommended Fixes

### Short-term (User Workaround)

Always use the `--force` flag when re-indexing scripts that have been modified:

```bash
scriptrag index --force /path/to/scripts
```

### Long-term (Code Fix)

Implement proper change detection in `_filter_scripts_for_indexing`:

1. **Option A: File modification time comparison**
   - Store file modification time in metadata
   - Compare current mtime with stored value
   - Re-index if file is newer

2. **Option B: Content hash comparison**
   - Store script content hash in metadata
   - Compare current content hash with stored value
   - Re-index if hashes differ

3. **Option C: Metadata version comparison**
   - Use the analyzed_at timestamp in scriptrag-META
   - Compare with last_indexed timestamp
   - Re-index if metadata is newer

## Code Locations

- Index logic: `src/scriptrag/api/index.py:_filter_scripts_for_indexing()`
- Clear operation: `src/scriptrag/api/database_operations.py:clear_script_data()`
- Database schema: `src/scriptrag/storage/database/sql/init_database.sql`
- Integration tests: `tests/integration/test_scene_index_updates.py`

## Conclusion

The scene indexing system is architecturally sound and handles updates correctly when properly triggered. The main issue is the lack of automatic change detection, requiring users to manually specify the --force flag for updates. This is a usability issue rather than a data integrity problem.
