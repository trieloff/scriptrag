# Git LFS Storage Component

This directory implements Git LFS operations for storing and retrieving large files, primarily embedding vectors.

## Architecture Role

LFS Storage is a **storage backend** that:

- Stores numpy arrays of scene embeddings
- Provides content-addressed storage
- Handles compression and deduplication
- Integrates with Git LFS for version control

## Key Responsibilities

1. **Embedding Storage**
   - Store compressed numpy arrays
   - Use content hashes as filenames
   - Handle batch operations

2. **LFS Integration**
   - Track files with Git LFS
   - Handle LFS pointer files
   - Manage bandwidth efficiently

3. **Compression**
   - Compress vectors for storage
   - Decompress on retrieval
   - Balance size vs speed






## Performance Considerations

1. **Batch Operations**: Process multiple files together
2. **Lazy Loading**: Only pull LFS content when needed
3. **Compression**: Balance compression ratio vs CPU usage
4. **Caching**: Cache frequently accessed embeddings
5. **Parallel Downloads**: Use LFS batch API for parallel pulls

## Error Handling

1. **LFS Not Installed**: Clear error message with instructions
2. **Network Errors**: Retry LFS operations with backoff
3. **Corrupt Files**: Validate embeddings after load
4. **Space Issues**: Handle out of disk space gracefully

## Testing

Key test scenarios:

- Embedding compression/decompression
- LFS pointer detection
- Batch operations
- Orphaned file cleanup
- Network failure handling
- Large file handling
