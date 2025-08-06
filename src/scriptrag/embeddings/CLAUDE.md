# Embedding Generator Component

This directory contains the embedding generation system that creates vector representations of scenes for semantic search.

## Architecture Role

The Embedding Generator is a **processing component** that:

- Receives scene data from Content Extractor
- Communicates with LLM API for embeddings
- Writes embedding vectors to Git LFS storage backend

## Key Responsibilities

1. **Generate Embeddings**
   - Create vector representations of scene text
   - Include metadata in embedding context
   - Support different embedding models

2. **Optimize Storage**
   - Compress vectors efficiently
   - Use content-addressed storage
   - Handle deduplication

3. **Batch Processing**
   - Batch multiple scenes for efficiency
   - Handle rate limits gracefully
   - Manage memory usage






## Performance Optimizations

1. **Vector Quantization**: Reduce precision for smaller storage
2. **Incremental Processing**: Only embed changed scenes
3. **Parallel Batches**: Process multiple batches concurrently
4. **Caching**: Cache embeddings by content hash

## Error Handling

1. **Rate Limits**: Exponential backoff with jitter
2. **API Errors**: Retry failed scenes individually
3. **Storage Errors**: Queue for later retry
4. **Model Errors**: Fallback to alternative models

## Testing

Key test cases:

- Embedding generation with mock LLM
- Batch processing logic
- Vector compression/decompression
- Error recovery
- Performance benchmarks

## Integration Points

- **Input from**: Content Extractor
- **Writes to**: Git LFS storage backend
- **Communicates with**: LLM API

## Configuration

The embedding system can be configured with model selection, batch sizing, compression settings, and caching options.
