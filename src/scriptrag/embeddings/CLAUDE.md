# Embedding Generator Component

This directory contains the embedding generation system that creates vector representations of scenes for semantic search.

## Architecture Role

The Embedding Generator is an **Actor** in the FMC architecture. It:

- Receives scene data from Content Extractor (through a channel)
- Communicates with LLM API for embeddings (through a channel)
- Writes embedding vectors to Git LFS (Place)

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

## Implementation Guidelines

```python
import numpy as np
from typing import List, Optional, Dict
from pathlib import Path
import hashlib

from ..models import Scene, Embedding
from ..llm import LLMClient
from ..storage.lfs import LFSStorage
from ..exceptions import EmbeddingError


class EmbeddingGenerator:
    """Generate vector embeddings for scenes."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        lfs_storage: Optional[LFSStorage] = None,
        model: str = "text-embedding-ada-002"
    ):
        self.llm = llm_client or LLMClient()
        self.lfs = lfs_storage or LFSStorage()
        self.model = model
        self.dimensions = self._get_model_dimensions(model)

    def generate(self, scene: Scene, metadata: Dict) -> Embedding:
        """Generate embedding for a scene.

        Args:
            scene: Scene to embed
            metadata: Extracted metadata to include

        Returns:
            Embedding object with vector and metadata

        Raises:
            EmbeddingError: If generation fails
        """
        # Build embedding text
        text = self._build_embedding_text(scene, metadata)

        # Generate vector
        vector = self._get_embedding_vector(text)

        # Store in LFS
        file_path = self._store_embedding(scene.content_hash, vector)

        return Embedding(
            content_hash=scene.content_hash,
            file_path=file_path,
            dimensions=self.dimensions,
            model_version=self.model
        )

    def generate_batch(
        self,
        scenes: List[Scene],
        metadata_map: Dict[str, Dict]
    ) -> List[Embedding]:
        """Generate embeddings for multiple scenes efficiently."""
        # Build all texts
        texts = [
            self._build_embedding_text(scene, metadata_map[scene.content_hash])
            for scene in scenes
        ]

        # Batch API call
        vectors = self.llm.embed_batch(texts, model=self.model)

        # Store all embeddings
        embeddings = []
        for scene, vector in zip(scenes, vectors):
            file_path = self._store_embedding(scene.content_hash, vector)
            embeddings.append(Embedding(
                content_hash=scene.content_hash,
                file_path=file_path,
                dimensions=self.dimensions,
                model_version=self.model
            ))

        return embeddings
```

## Embedding Text Construction

```python
def _build_embedding_text(self, scene: Scene, metadata: Dict) -> str:
    """Build text for embedding that includes context."""
    parts = []

    # Scene heading
    parts.append(f"{scene.type}. {scene.location} - {scene.time_of_day}")

    # Action text
    if scene.action_text:
        parts.append(scene.action_text)

    # Dialogue summary
    if scene.dialogue_lines:
        dialogue_summary = self._summarize_dialogue(scene.dialogue_lines)
        parts.append(f"Dialogue: {dialogue_summary}")

    # Important metadata
    if metadata.get("emotional_tone"):
        parts.append(f"Tone: {metadata['emotional_tone']}")

    if metadata.get("themes"):
        parts.append(f"Themes: {', '.join(metadata['themes'])}")

    if metadata.get("characters"):
        parts.append(f"Characters: {', '.join(metadata['characters'])}")

    return "\n\n".join(parts)
```

## Vector Storage

```python
def _store_embedding(self, content_hash: str, vector: np.ndarray) -> str:
    """Store embedding vector in Git LFS."""
    # Compress vector
    compressed = self._compress_vector(vector)

    # Generate filename
    filename = f"embeddings/{content_hash}.npz"

    # Write to LFS
    self.lfs.write(filename, compressed)

    return filename

def _compress_vector(self, vector: np.ndarray) -> bytes:
    """Compress vector for efficient storage."""
    # Use numpy's compressed format
    buffer = io.BytesIO()
    np.savez_compressed(buffer, vector=vector)
    return buffer.getvalue()
```

## Model Support

```python
EMBEDDING_MODELS = {
    "text-embedding-ada-002": {
        "dimensions": 1536,
        "max_tokens": 8191,
        "provider": "openai"
    },
    "text-embedding-3-small": {
        "dimensions": 512,
        "max_tokens": 8191,
        "provider": "openai"
    },
    "text-embedding-3-large": {
        "dimensions": 3072,
        "max_tokens": 8191,
        "provider": "openai"
    },
    "voyage-01": {
        "dimensions": 1024,
        "max_tokens": 4096,
        "provider": "anthropic"
    }
}
```

## Batching Strategy

```python
class BatchProcessor:
    """Process embeddings in optimal batches."""

    def __init__(self, max_batch_size: int = 100, max_tokens: int = 8000):
        self.max_batch_size = max_batch_size
        self.max_tokens = max_tokens

    def create_batches(self, items: List[Tuple[str, int]]) -> List[List[str]]:
        """Create batches respecting size and token limits."""
        batches = []
        current_batch = []
        current_tokens = 0

        for text, tokens in items:
            if (len(current_batch) >= self.max_batch_size or
                current_tokens + tokens > self.max_tokens):
                if current_batch:
                    batches.append(current_batch)
                current_batch = [text]
                current_tokens = tokens
            else:
                current_batch.append(text)
                current_tokens += tokens

        if current_batch:
            batches.append(current_batch)

        return batches
```

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

- **Input from**: Content Extractor (via channel)
- **Writes to**: Git LFS (Place)
- **Communicates with**: LLM API (via channel)

## Configuration

```yaml
embeddings:
  model: "text-embedding-ada-002"
  batch_size: 100
  max_retries: 3
  compression: true
  quantization: false  # For smaller vectors
  cache_embeddings: true
```
