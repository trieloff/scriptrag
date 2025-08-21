"""Embedding processing for script indexing."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.config import get_logger
from scriptrag.parser import Scene

logger = get_logger(__name__)


class IndexEmbeddingProcessor:
    """Handles embedding processing during script indexing."""

    def __init__(
        self,
        db_ops: DatabaseOperations,
        embedding_service: EmbeddingService | None = None,
        generate_embeddings: bool = False,
    ) -> None:
        """Initialize embedding processor.

        Args:
            db_ops: Database operations handler
            embedding_service: Optional embedding service for scene embeddings
            generate_embeddings: Whether to generate embeddings during indexing
        """
        self.db_ops = db_ops
        self.embedding_service = embedding_service
        self.generate_embeddings = generate_embeddings

    async def process_scene_embeddings(
        self, conn: sqlite3.Connection, scene: Scene, scene_id: int
    ) -> None:
        """Process and store embeddings for a scene.

        This method handles both existing embeddings from boneyard metadata
        and generates new embeddings if enabled.

        Args:
            conn: Database connection
            scene: Scene object with potential embedding metadata
            scene_id: Database ID of the scene
        """
        embedding_stored = False

        # First check for existing embeddings in boneyard metadata
        if scene.boneyard_metadata:
            # Check for embedding analyzer results
            analyzers = scene.boneyard_metadata.get("analyzers", {})
            embedding_data = analyzers.get("scene_embeddings", {})

            if embedding_data and "result" in embedding_data:
                result = embedding_data.get("result", {})
                if "error" not in result:
                    # Extract embedding information
                    embedding_path = result.get("embedding_path")
                    model = result.get("model", "unknown")

                    if embedding_path:
                        # Check if embedding file exists and load it
                        try:
                            import git
                            import numpy as np

                            # Get the repository root
                            repo = git.Repo(
                                (
                                    scene.file_path.parent
                                    if hasattr(scene, "file_path")
                                    else "."
                                ),
                                search_parent_directories=True,
                            )
                            repo_root = Path(repo.working_dir)
                            full_embedding_path = repo_root / embedding_path

                            if full_embedding_path.exists():
                                # Load embedding from file
                                embedding_array = np.load(full_embedding_path)
                                # Convert to bytes for database storage
                                embedding_bytes = embedding_array.tobytes()

                                # Store in database
                                self.db_ops.upsert_embedding(
                                    conn,
                                    entity_type="scene",
                                    entity_id=scene_id,
                                    embedding_model=model,
                                    embedding_data=embedding_bytes,
                                    embedding_path=embedding_path,
                                )
                                embedding_stored = True
                                logger.info(
                                    f"Stored embedding for scene {scene_id} "
                                    f"from {embedding_path}"
                                )
                            else:
                                # Store reference path - downloaded from LFS when needed
                                self.db_ops.upsert_embedding(
                                    conn,
                                    entity_type="scene",
                                    entity_id=scene_id,
                                    embedding_model=model,
                                    embedding_path=embedding_path,
                                )
                                embedding_stored = True
                                logger.info(
                                    f"Stored embedding reference for scene "
                                    f"{scene_id}: {embedding_path}"
                                )
                        except Exception as e:
                            logger.error(
                                f"Failed to process embedding for scene {scene_id}: {e}"
                            )

        # Generate new embedding if enabled and not already stored
        if self.generate_embeddings and self.embedding_service and not embedding_stored:
            try:
                # Generate embedding for the scene
                embedding = await self.embedding_service.generate_scene_embedding(
                    scene.content, scene.heading
                )

                # Save to Git LFS
                lfs_path = self.embedding_service.save_embedding_to_lfs(
                    embedding,
                    "scene",
                    scene_id,
                    self.embedding_service.default_model,
                )

                # Encode for database storage
                embedding_bytes = self.embedding_service.encode_embedding_for_db(
                    embedding
                )

                # Store in database
                self.db_ops.upsert_embedding(
                    conn,
                    entity_type="scene",
                    entity_id=scene_id,
                    embedding_model=self.embedding_service.default_model,
                    embedding_data=embedding_bytes,
                    embedding_path=str(lfs_path),
                )

                logger.info(
                    f"Generated and stored embedding for scene {scene_id}",
                    model=self.embedding_service.default_model,
                    lfs_path=str(lfs_path),
                )
            except Exception as e:
                logger.error(f"Failed to generate embedding for scene {scene_id}: {e}")
