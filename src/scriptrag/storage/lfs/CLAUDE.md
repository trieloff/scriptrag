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

## Implementation Guidelines

```python
import numpy as np
import git
from pathlib import Path
from typing import Optional, List, Dict
import io
import hashlib

from ...models import Embedding
from ...exceptions import StorageError, NotFoundError


class LFSStorage:
    """Manage embeddings in Git LFS."""

    def __init__(
        self,
        repo_path: Optional[Path] = None,
        embeddings_dir: str = "embeddings"
    ):
        self.repo_path = repo_path or Path.cwd()
        self.repo = git.Repo(self.repo_path)
        self.embeddings_dir = self.repo_path / embeddings_dir
        self._ensure_lfs_setup()

    def write_embedding(
        self,
        content_hash: str,
        vector: np.ndarray
    ) -> str:
        """Write an embedding vector to LFS.

        Args:
            content_hash: Hash of the scene content
            vector: Embedding vector as numpy array

        Returns:
            Path to the stored file
        """
        # Ensure directory exists
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        filename = f"{content_hash}.npz"
        file_path = self.embeddings_dir / filename

        # Check if already exists (deduplication)
        if file_path.exists():
            return str(file_path.relative_to(self.repo_path))

        # Compress and save
        self._save_compressed(file_path, vector)

        # Add to LFS
        self.repo.git.lfs("track", str(file_path))
        self.repo.index.add([str(file_path)])

        return str(file_path.relative_to(self.repo_path))

    def read_embedding(self, path: str) -> np.ndarray:
        """Read an embedding vector from LFS.

        Args:
            path: Relative path to embedding file

        Returns:
            Embedding vector as numpy array
        """
        file_path = self.repo_path / path

        if not file_path.exists():
            raise NotFoundError(f"Embedding not found: {path}")

        # Ensure LFS file is pulled
        self._ensure_lfs_pulled(file_path)

        # Load and decompress
        return self._load_compressed(file_path)
```

## Compression Implementation

```python
def _save_compressed(
    self,
    file_path: Path,
    vector: np.ndarray
) -> None:
    """Save vector with compression."""
    # Use numpy's compressed format
    np.savez_compressed(
        file_path,
        vector=vector,
        dtype=str(vector.dtype),
        shape=vector.shape
    )

def _load_compressed(self, file_path: Path) -> np.ndarray:
    """Load and decompress vector."""
    with np.load(file_path) as data:
        vector = data['vector']

        # Verify shape and dtype if stored
        if 'shape' in data:
            expected_shape = tuple(data['shape'])
            if vector.shape != expected_shape:
                raise StorageError(
                    f"Shape mismatch: {vector.shape} != {expected_shape}"
                )

        return vector
```

## Batch Operations

```python
def write_embeddings_batch(
    self,
    embeddings: Dict[str, np.ndarray]
) -> Dict[str, str]:
    """Write multiple embeddings efficiently.

    Args:
        embeddings: Map of content_hash to vector

    Returns:
        Map of content_hash to file path
    """
    paths = {}
    files_to_add = []

    for content_hash, vector in embeddings.items():
        filename = f"{content_hash}.npz"
        file_path = self.embeddings_dir / filename

        if not file_path.exists():
            self._save_compressed(file_path, vector)
            files_to_add.append(str(file_path))

        paths[content_hash] = str(
            file_path.relative_to(self.repo_path)
        )

    # Batch add to LFS
    if files_to_add:
        self.repo.git.lfs("track", *files_to_add)
        self.repo.index.add(files_to_add)

    return paths

def read_embeddings_batch(
    self,
    paths: List[str]
) -> Dict[str, np.ndarray]:
    """Read multiple embeddings efficiently."""
    # Ensure all files are pulled
    full_paths = [self.repo_path / path for path in paths]
    self._ensure_lfs_pulled_batch(full_paths)

    # Load all embeddings
    embeddings = {}
    for path in paths:
        try:
            vector = self.read_embedding(path)
            # Extract hash from filename
            content_hash = Path(path).stem
            embeddings[content_hash] = vector
        except Exception as e:
            self.logger.warning(
                f"Failed to load embedding: {path}",
                error=str(e)
            )

    return embeddings
```

## LFS Management

```python
def _ensure_lfs_setup(self) -> None:
    """Ensure Git LFS is properly configured."""
    # Check if LFS is initialized
    try:
        self.repo.git.lfs("version")
    except git.exc.GitCommandError:
        raise StorageError(
            "Git LFS not installed. Please install git-lfs."
        )

    # Ensure .gitattributes has LFS rules
    gitattributes = self.repo_path / ".gitattributes"
    lfs_rule = f"{self.embeddings_dir}/*.npz filter=lfs diff=lfs merge=lfs -text"

    if gitattributes.exists():
        content = gitattributes.read_text()
        if lfs_rule not in content:
            gitattributes.write_text(content + f"\n{lfs_rule}\n")
    else:
        gitattributes.write_text(f"{lfs_rule}\n")

def _ensure_lfs_pulled(self, file_path: Path) -> None:
    """Ensure LFS file content is available."""
    # Check if file is LFS pointer
    if self._is_lfs_pointer(file_path):
        # Pull the actual content
        self.repo.git.lfs("pull", "--include", str(file_path))

def _is_lfs_pointer(self, file_path: Path) -> bool:
    """Check if file is an LFS pointer."""
    if not file_path.exists():
        return False

    # LFS pointers are small text files
    if file_path.stat().st_size > 1024:  # > 1KB
        return False

    # Check for LFS pointer content
    try:
        content = file_path.read_text()
        return content.startswith("version https://git-lfs.github.com")
    except:
        return False
```

## Storage Optimization

```python
def cleanup_orphaned_embeddings(self) -> int:
    """Remove embeddings not referenced in any scene."""
    # Get all embedding files
    all_embeddings = set(
        f.stem for f in self.embeddings_dir.glob("*.npz")
    )

    # Get referenced embeddings from scenes
    referenced = set()
    # ... scan scenes for embedding references ...

    # Find orphaned
    orphaned = all_embeddings - referenced

    # Remove orphaned files
    for content_hash in orphaned:
        file_path = self.embeddings_dir / f"{content_hash}.npz"
        file_path.unlink()

    return len(orphaned)

def get_storage_stats(self) -> Dict[str, any]:
    """Get storage statistics."""
    total_size = 0
    file_count = 0

    for file_path in self.embeddings_dir.glob("*.npz"):
        total_size += file_path.stat().st_size
        file_count += 1

    return {
        "total_files": file_count,
        "total_size_mb": total_size / (1024 * 1024),
        "average_size_kb": (total_size / file_count / 1024) if file_count else 0
    }
```

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
