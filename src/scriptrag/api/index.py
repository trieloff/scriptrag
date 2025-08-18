"""Script index API module for ScriptRAG."""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.api.list import FountainMetadata, ScriptLister
from scriptrag.config import ScriptRAGSettings, get_logger, get_settings
from scriptrag.parser import FountainParser, Scene, Script

logger = get_logger(__name__)


@dataclass
class IndexResult:
    """Result from indexing a single script."""

    path: Path
    script_id: int | None = None
    indexed: bool = False
    updated: bool = False
    scenes_indexed: int = 0
    characters_indexed: int = 0
    dialogues_indexed: int = 0
    actions_indexed: int = 0
    error: str | None = None


@dataclass
class IndexOperationResult:
    """Result from an index operation."""

    scripts: list[IndexResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_scripts_indexed(self) -> int:
        """Count of scripts that were indexed."""
        return sum(1 for s in self.scripts if s.indexed)

    @property
    def total_scripts_updated(self) -> int:
        """Count of scripts that were updated."""
        return sum(1 for s in self.scripts if s.updated)

    @property
    def total_scenes_indexed(self) -> int:
        """Total count of scenes indexed across all scripts."""
        return sum(s.scenes_indexed for s in self.scripts)

    @property
    def total_characters_indexed(self) -> int:
        """Total count of characters indexed across all scripts."""
        return sum(s.characters_indexed for s in self.scripts)

    @property
    def total_dialogues_indexed(self) -> int:
        """Total count of dialogues indexed across all scripts."""
        return sum(s.dialogues_indexed for s in self.scripts)

    @property
    def total_actions_indexed(self) -> int:
        """Total count of actions indexed across all scripts."""
        return sum(s.actions_indexed for s in self.scripts)


class IndexCommand:
    """Orchestrates the index operation."""

    def __init__(
        self,
        settings: ScriptRAGSettings | None = None,
        db_ops: DatabaseOperations | None = None,
        embedding_service: EmbeddingService | None = None,
        generate_embeddings: bool = False,
    ) -> None:
        """Initialize index command.

        Args:
            settings: Configuration settings
            db_ops: Database operations handler
            embedding_service: Optional embedding service for scene embeddings
            generate_embeddings: Whether to generate embeddings during indexing
        """
        self.settings = settings or get_settings()
        self.db_ops = db_ops or DatabaseOperations(self.settings)
        self.parser = FountainParser()
        self.lister = ScriptLister()
        self.embedding_service = embedding_service
        self.generate_embeddings = generate_embeddings

    @classmethod
    def from_config(cls) -> "IndexCommand":
        """Create IndexCommand from configuration.

        Returns:
            Configured IndexCommand instance
        """
        settings = get_settings()
        return cls(settings=settings)

    async def index(
        self,
        path: Path | None = None,
        recursive: bool = True,
        dry_run: bool = False,
        batch_size: int = 10,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> IndexOperationResult:
        """Execute index operation.

        Args:
            path: Path to search for analyzed Fountain files
            recursive: Whether to search recursively
            dry_run: Preview changes without applying them
            batch_size: Number of scripts to process in each batch
            progress_callback: Optional callback for progress updates

        Returns:
            IndexOperationResult with details of the operation
        """
        result = IndexOperationResult()

        try:
            # Check database exists
            if not self.db_ops.check_database_exists():
                error_msg = (
                    "Database not initialized. Please run 'scriptrag init' first."
                )
                logger.error(error_msg)
                result.errors.append(error_msg)
                return result

            # Step 1: Find all Fountain files with metadata
            if progress_callback:
                progress_callback(0.1, "Discovering Fountain files...")

            scripts = await self._discover_scripts(path, recursive)

            if not scripts:
                logger.info("No Fountain files found")
                return result

            logger.info(f"Found {len(scripts)} Fountain files")

            # Step 2: Process all scripts (always re-index to ensure data consistency)
            scripts_to_index = scripts

            if not scripts_to_index:
                logger.info("No scripts need indexing")
                return result

            logger.info(f"Processing {len(scripts_to_index)} scripts")

            # Step 3: Process scripts in batches
            total = len(scripts_to_index)
            for i in range(0, total, batch_size):
                batch = scripts_to_index[i : min(i + batch_size, total)]
                batch_num = (i // batch_size) + 1
                total_batches = (total + batch_size - 1) // batch_size

                if progress_callback:
                    progress = 0.1 + (0.8 * i / total)
                    progress_callback(
                        progress, f"Processing batch {batch_num}/{total_batches}..."
                    )

                batch_results = await self._process_scripts_batch(batch, dry_run)
                result.scripts.extend(batch_results)

                # Collect errors from batch
                for script_result in batch_results:
                    if script_result.error:
                        result.errors.append(
                            f"{script_result.path}: {script_result.error}"
                        )

            if progress_callback:
                progress_callback(1.0, "Indexing complete")

        except Exception as e:
            logger.error(f"Index operation failed: {e!s}")
            result.errors.append(f"Index operation failed: {e!s}")

        return result

    async def _discover_scripts(
        self, path: Path | None, recursive: bool
    ) -> list[FountainMetadata]:
        """Discover Fountain files with boneyard metadata.

        Args:
            path: Path to search
            recursive: Whether to search recursively

        Returns:
            List of discovered script metadata
        """
        all_scripts = self.lister.list_scripts(path, recursive)

        # Filter to only scripts with boneyard metadata for backwards compatibility
        # This ensures that only analyzed scripts are indexed
        # HOWEVER: Allow skipping this filter via configuration (useful for testing)
        if self.settings.skip_boneyard_filter:
            return all_scripts

        return [script for script in all_scripts if script.has_boneyard]

    async def _filter_scripts_for_indexing(
        self, scripts: list[FountainMetadata]
    ) -> list[FountainMetadata]:
        """Filter scripts that need indexing.

        Args:
            scripts: List of script metadata

        Returns:
            Filtered list of scripts that need indexing
        """
        scripts_to_index = []

        with self.db_ops.transaction() as conn:
            for script_meta in scripts:
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
                        # For now, skip if already indexed
                        logger.debug(f"Script already indexed: {script_meta.file_path}")
                    else:
                        scripts_to_index.append(script_meta)

        return scripts_to_index

    async def _process_scripts_batch(
        self, scripts: list[FountainMetadata], dry_run: bool
    ) -> list[IndexResult]:
        """Process a batch of scripts.

        Args:
            scripts: List of script metadata to process
            dry_run: Preview mode

        Returns:
            List of index results
        """
        results = []

        for script_meta in scripts:
            try:
                result = await self._index_single_script(script_meta.file_path, dry_run)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to index {script_meta.file_path}: {e}")
                results.append(
                    IndexResult(
                        path=script_meta.file_path,
                        indexed=False,
                        error=str(e),
                    )
                )

        return results

    async def _index_single_script(self, file_path: Path, dry_run: bool) -> IndexResult:
        """Index a single script.

        Args:
            file_path: Path to the script file
            dry_run: Preview mode

        Returns:
            IndexResult for this script
        """
        logger.debug(f"Indexing script: {file_path}")

        try:
            # Parse the script
            script = self.parser.parse_file(file_path)

            if dry_run:
                # In dry run mode, just analyze what would be done
                return await self._dry_run_analysis(script, file_path)

            # Process with transaction
            with self.db_ops.transaction() as conn:
                # Check if script exists
                existing = self.db_ops.get_existing_script(conn, file_path)
                is_update = existing is not None

                # Always clear existing data when updating to ensure consistency
                if existing and existing.id is not None:
                    self.db_ops.clear_script_data(conn, existing.id)

                # Upsert script
                script_id = self.db_ops.upsert_script(conn, script, file_path)

                # Extract all unique characters from all scenes
                all_characters = set()
                for scene in script.scenes:
                    for dialogue in scene.dialogue_lines:
                        all_characters.add(dialogue.character)

                # Upsert all characters
                character_map = {}
                if all_characters:
                    character_map = self.db_ops.upsert_characters(
                        conn, script_id, all_characters
                    )

                # Process scenes
                total_dialogues = 0
                total_actions = 0

                for scene in script.scenes:
                    # Clear existing scene content if updating
                    # Upsert scene and check if content changed
                    scene_id, content_changed = self.db_ops.upsert_scene(
                        conn, scene, script_id
                    )

                    # Clear and re-insert content if it has changed
                    if content_changed:
                        self.db_ops.clear_scene_content(conn, scene_id)

                        # Insert dialogues
                        dialogue_count = self.db_ops.insert_dialogues(
                            conn, scene_id, scene.dialogue_lines, character_map
                        )
                        total_dialogues += dialogue_count

                        # Insert actions
                        action_count = self.db_ops.insert_actions(
                            conn, scene_id, scene.action_lines
                        )
                        total_actions += action_count

                    # Process embeddings from boneyard metadata
                    await self._process_scene_embeddings(conn, scene, scene_id)

                # Get final stats
                stats = self.db_ops.get_script_stats(conn, script_id)

                return IndexResult(
                    path=file_path,
                    script_id=script_id,
                    indexed=True,  # Successfully processed regardless of new/update
                    updated=is_update,  # Only updated if it existed
                    scenes_indexed=stats["scenes"],
                    characters_indexed=stats["characters"],
                    dialogues_indexed=stats["dialogues"],
                    actions_indexed=stats["actions"],
                )

        except Exception as e:
            logger.error(f"Error indexing {file_path}: {e}")
            raise

    async def _process_scene_embeddings(
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

    async def _dry_run_analysis(self, script: Script, file_path: Path) -> IndexResult:
        """Analyze what would be indexed without making changes.

        Args:
            script: Parsed script object
            file_path: Path to the script file

        Returns:
            IndexResult with preview information
        """
        # Count entities that would be indexed
        characters = set()
        dialogues = 0
        actions = 0

        for scene in script.scenes:
            for dialogue in scene.dialogue_lines:
                characters.add(dialogue.character)
                dialogues += 1
            actions += len(scene.action_lines)

        return IndexResult(
            path=file_path,
            indexed=False,  # In dry run, nothing is actually indexed
            updated=False,  # In dry run, nothing is actually updated
            scenes_indexed=len(script.scenes),  # Preview: number of scenes
            characters_indexed=len(characters),  # Preview: number of characters
            dialogues_indexed=dialogues,  # Preview: number of dialogues
            actions_indexed=actions,  # Preview: number of actions
        )
