# Git Storage Component

This directory implements Git repository operations for storing and retrieving Fountain files, Script Bibles, and Custom Insight Agents.

## Architecture Role

Git Storage is a **storage backend** that:

- Stores Fountain files with boneyard metadata
- Stores Script Bible markdown files
- Stores Custom Insight Agent definitions
- Provides version control and branching

## Key Responsibilities

1. **File Operations**
   - Read/write Fountain files
   - Manage Script Bible documents
   - Handle Insight Agent files

2. **Git Operations**
   - Track changes
   - Handle commits
   - Manage branches
   - Resolve conflicts

3. **Path Management**
   - Validate paths within repository
   - Handle cross-platform paths
   - Prevent directory traversal






## Performance Considerations

1. **Lazy Loading**: Don't load file content until needed
2. **Caching**: Cache frequently accessed files
3. **Batch Operations**: Stage multiple files before commit
4. **Large Files**: Use Git LFS for binary data

## Error Handling

1. **Permission Errors**: Handle read-only repositories
2. **Merge Conflicts**: Detect and report conflicts
3. **Invalid Paths**: Validate all user-provided paths
4. **Encoding Issues**: Handle non-UTF-8 files gracefully

## Testing

Key test scenarios:

- File CRUD operations
- Path validation and security
- Git operations (history, revisions)
- Concurrent access
- Large file handling
- Cross-platform paths
