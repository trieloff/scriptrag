"""Scene embedding analyzer that generates and stores embeddings in Git LFS."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import git
import numpy as np

from scriptrag.analyzers.base import BaseSceneAnalyzer
from scriptrag.config import get_logger
from scriptrag.exceptions import (
    EmbeddingError,
    EmbeddingGenerationError,
    GitError,
)
from scriptrag.utils import ScreenplayUtils, get_default_llm_client

if TYPE_CHECKING:
    from scriptrag.llm.client import LLMClient

logger = get_logger(__name__)


class SceneEmbeddingAnalyzer(BaseSceneAnalyzer):
    """Analyzer that generates embeddings for scenes and stores them in Git LFS."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the embedding analyzer.

        Args:
            config: Optional configuration including:
                - embedding_model: Model to use for embeddings
                - dimensions: Embedding dimensions
                - lfs_path: Path for LFS storage (default: embeddings/)
                - repo_path: Path to git repository (default: current directory)
        """
        super().__init__(config)
        self.llm_client: LLMClient | None = None
        self.embedding_model = config.get("embedding_model") if config else None
        self.dimensions = config.get("dimensions") if config else None
        self.lfs_path = (
            Path(config.get("lfs_path", "embeddings")) if config else Path("embeddings")
        )
        self.repo_path = Path(config.get("repo_path", ".")) if config else Path()
        self._repo: git.Repo | None = None
        self._embeddings_cache: dict[str, np.ndarray] = {}

    @property
    def name(self) -> str:
        """Return the analyzer name."""
        return "scene_embeddings"

    @property
    def version(self) -> str:
        """Return the analyzer version."""
        return "1.0.0"

    @property
    def requires_llm(self) -> bool:
        """Return whether this analyzer requires an LLM."""
        return True

    @property
    def repo(self) -> git.Repo:
        """Get or create the git repository instance."""
        if self._repo is None:
            try:
                self._repo = git.Repo(self.repo_path, search_parent_directories=True)
            except git.InvalidGitRepositoryError as e:
                logger.error(f"Not a git repository: {self.repo_path}")
                raise GitError(
                    message=f"Not a git repository: {self.repo_path}",
                    hint="Ensure you're running this command in a git repository",
                    details={"repo_path": str(self.repo_path), "error": str(e)},
                ) from e
        return self._repo

    async def initialize(self) -> None:
        """Initialize the LLM client and ensure Git LFS is configured."""
        if self.llm_client is None:
            self.llm_client = await get_default_llm_client()
            logger.info("Initialized LLM client for embedding generation")

        # Ensure embeddings directory exists
        embeddings_dir = self.repo_path / self.lfs_path
        try:
            embeddings_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(
                f"Failed to create embeddings directory {embeddings_dir}: {e}. "
                "Embeddings will not be cached to disk."
            )

        # Check if Git LFS is configured for .npy files
        gitattributes_path = self.repo_path / ".gitattributes"
        lfs_pattern = f"{self.lfs_path}/*.npy filter=lfs diff=lfs merge=lfs -text"

        try:
            if gitattributes_path.exists():
                with gitattributes_path.open() as f:
                    content = f.read()
                    if lfs_pattern not in content:
                        logger.warning(
                            f"Git LFS not configured for {self.lfs_path}/*.npy files. "
                            "Adding configuration to .gitattributes"
                        )
                        try:
                            with gitattributes_path.open("a") as f:
                                f.write(f"\n{lfs_pattern}\n")
                        except OSError as e:
                            logger.error(
                                f"Failed to update .gitattributes: {e}. "
                                "Please manually add the following line to "
                                f".gitattributes:\n{lfs_pattern}"
                            )
            else:
                logger.info("Creating .gitattributes with Git LFS configuration")
                try:
                    with gitattributes_path.open("w") as f:
                        f.write(f"{lfs_pattern}\n")
                except OSError as e:
                    logger.error(
                        f"Failed to create .gitattributes: {e}. "
                        "Please manually create .gitattributes with the "
                        f"following line:\n{lfs_pattern}"
                    )
        except OSError as e:
            logger.error(
                f"Failed to read .gitattributes: {e}. "
                "Git LFS configuration check skipped."
            )

    async def cleanup(self) -> None:
        """Clean up resources."""
        self.llm_client = None
        self._embeddings_cache.clear()

    def _compute_scene_hash(self, scene: dict[str, Any]) -> str:
        """Compute a stable hash for scene content.

        Args:
            scene: Scene data

        Returns:
            Hex digest of the scene content hash
        """
        # Use original_text if available for consistent hashing
        if original_text := scene.get("original_text"):
            # Use full hash (not truncated) for embedding cache key
            return ScreenplayUtils.compute_scene_hash(original_text, truncate=False)

        # Fallback: hash the formatted content
        formatted = ScreenplayUtils.format_scene_for_embedding(scene)
        return ScreenplayUtils.compute_scene_hash(formatted, truncate=False)

    def _get_embedding_path(self, content_hash: str) -> Path:
        """Get the path for storing an embedding file.

        Args:
            content_hash: Hash of the scene content

        Returns:
            Path to the embedding file
        """
        return self.repo_path / self.lfs_path / f"{content_hash}.npy"

    async def _load_or_generate_embedding(
        self, scene: dict[str, Any], content_hash: str
    ) -> np.ndarray:
        """Load existing embedding or generate a new one.

        Args:
            scene: Scene data
            content_hash: Hash of the scene content

        Returns:
            Numpy array of embeddings
        """
        # Check cache first
        if content_hash in self._embeddings_cache:
            logger.debug(f"Using cached embedding for {content_hash}")
            return self._embeddings_cache[content_hash]

        # Check if embedding file exists
        embedding_path = self._get_embedding_path(content_hash)
        if embedding_path.exists():
            logger.info(f"Loading existing embedding from {embedding_path}")
            try:
                embedding = np.load(embedding_path)
                self._embeddings_cache[content_hash] = embedding
                return np.array(embedding)
            except (OSError, ValueError) as e:
                logger.error(f"Failed to load embedding from {embedding_path}: {e}")
                # Fall through to regenerate

        # Generate new embedding
        logger.info(f"Generating new embedding for scene {content_hash}")
        embedding = await self._generate_embedding(scene)

        # Save to file
        try:
            np.save(embedding_path, embedding)
            logger.info(f"Saved embedding to {embedding_path}")

            # Add to git
            try:
                self.repo.index.add([str(embedding_path.relative_to(self.repo_path))])
                logger.debug(f"Added {embedding_path} to git index")
            except (git.GitCommandError, OSError) as e:
                logger.warning(f"Failed to add embedding to git: {e}")

        except (OSError, PermissionError) as e:
            logger.error(f"Failed to save embedding to {embedding_path}: {e}")

        # Cache it
        self._embeddings_cache[content_hash] = embedding
        return embedding

    async def _generate_embedding(self, scene: dict[str, Any]) -> np.ndarray:
        """Generate embeddings for a scene using the LLM.

        Args:
            scene: Scene data

        Returns:
            Numpy array of embeddings
        """
        if self.llm_client is None:
            raise RuntimeError("LLM client not initialized")

        # Format scene content for embedding
        scene_text = self._format_scene_for_embedding(scene)

        # Generate embedding
        from scriptrag.llm.models import EmbeddingRequest

        request = EmbeddingRequest(
            model=self.embedding_model or "",  # Let client auto-select
            input=scene_text,
            dimensions=self.dimensions,
        )

        try:
            response = await self.llm_client.embed(request)

            # Extract embedding vector
            if response.data and len(response.data) > 0:
                embedding_data = response.data[0]
                # Check if embedding_data is a dict with 'embedding' key
                if isinstance(embedding_data, dict) and "embedding" in embedding_data:
                    return np.array(embedding_data["embedding"], dtype=np.float32)
                # Check if embedding_data is an object with embedding attribute
                if hasattr(embedding_data, "embedding"):
                    # Use getattr to satisfy mypy type checking
                    embedding = getattr(embedding_data, "embedding", None)
                    if embedding:
                        return np.array(embedding, dtype=np.float32)
                # Try direct dict access as last resort
                if isinstance(embedding_data, dict):
                    return np.array(embedding_data["embedding"], dtype=np.float32)

            raise RuntimeError("No embedding data in response")

        except (AttributeError, KeyError, TypeError, RuntimeError, Exception) as e:
            error_msg = f"Failed to generate embedding: {e}"
            logger.error(error_msg)
            raise EmbeddingGenerationError(
                message=error_msg,
                hint="Check the LLM response format and embedding configuration",
                details={
                    "model": self.embedding_model,
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
            ) from e

    def _format_scene_for_embedding(self, scene: dict[str, Any]) -> str:
        """Format scene content for embedding generation.

        Args:
            scene: Scene data

        Returns:
            Formatted text for embedding
        """
        return ScreenplayUtils.format_scene_for_embedding(scene)

    async def analyze(self, scene: dict[str, Any]) -> dict[str, Any]:
        """Analyze a scene and generate/retrieve its embedding.

        Args:
            scene: Scene data

        Returns:
            Analysis results including embedding metadata
        """
        try:
            # Compute scene hash
            content_hash = self._compute_scene_hash(scene)

            # Load or generate embedding
            embedding = await self._load_or_generate_embedding(scene, content_hash)

            # Return metadata about the embedding
            embedding_path = self._get_embedding_path(content_hash)
            relative_path = embedding_path.relative_to(self.repo_path)

            result = {
                "content_hash": content_hash,
                "embedding_path": str(relative_path),
                "dimensions": int(embedding.shape[0]),
                "model": self.embedding_model or "auto-selected",
                "stored_in_lfs": True,
            }

            # Add statistics about the embedding
            result["statistics"] = {
                "mean": float(np.mean(embedding)),
                "std": float(np.std(embedding)),
                "min": float(np.min(embedding)),
                "max": float(np.max(embedding)),
                "norm": float(np.linalg.norm(embedding)),
            }

            return result

        except (EmbeddingError, GitError) as e:
            # Re-raise our specific exceptions with proper context
            logger.error(f"Failed to analyze scene: {e}")
            raise
        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to analyze scene: {e}")
            raise EmbeddingError(
                message=f"Failed to analyze scene: {e}",
                hint="Check file permissions and available disk space",
                details={
                    "analyzer": self.name,
                    "version": self.version,
                    "error_type": type(e).__name__,
                },
            ) from e
