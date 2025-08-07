"""Script analyze API module for ScriptRAG."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from scriptrag.analyzers.base import BaseSceneAnalyzer

from scriptrag.api.list import ScriptLister
from scriptrag.config import get_logger
from scriptrag.parser import FountainParser, Scene, Script

logger = get_logger(__name__)


@dataclass
class FileResult:
    """Result from processing a single file."""

    path: Path
    updated: bool
    scenes_updated: int = 0
    error: str | None = None


@dataclass
class AnalyzeResult:
    """Result from an analyze operation."""

    files: list[FileResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_files_updated(self) -> int:
        """Count of files that were updated."""
        return sum(1 for f in self.files if f.updated)

    @property
    def total_scenes_updated(self) -> int:
        """Total count of scenes updated across all files."""
        return sum(f.scenes_updated for f in self.files)


class SceneAnalyzer(Protocol):
    """Protocol for scene analysis callbacks."""

    async def analyze(self, scene: dict) -> dict:
        """Analyze a scene and return metadata."""
        ...

    @property
    def name(self) -> str:
        """Unique name for this analyzer."""
        ...


class AnalyzeCommand:
    """Orchestrates the analyze operation."""

    def __init__(
        self,
        analyzers: list[SceneAnalyzer | Any] | None = None,
    ):
        """Initialize analyze command.

        Args:
            analyzers: Optional list of scene analyzers
        """
        self.analyzers = analyzers or []
        self._analyzer_registry: dict[str, type[SceneAnalyzer | BaseSceneAnalyzer]] = {}

    @classmethod
    def from_config(cls) -> "AnalyzeCommand":
        """Create AnalyzeCommand from configuration."""
        return cls()

    def register_analyzer(self, name: str, analyzer_class: type[SceneAnalyzer]) -> None:
        """Register an analyzer class.

        Args:
            name: Name to register the analyzer under
            analyzer_class: The analyzer class to register
        """
        self._analyzer_registry[name] = analyzer_class

    def load_analyzer(self, name: str) -> None:
        """Load and instantiate an analyzer by name.

        Args:
            name: Name of the analyzer to load

        Raises:
            ValueError: If analyzer not found
        """
        # Check if already loaded
        if any(a.name == name for a in self.analyzers):
            logger.debug(f"Analyzer {name} already loaded")
            return

        if name not in self._analyzer_registry:
            # Try to load from built-in analyzers
            try:
                from scriptrag.analyzers.builtin import BUILTIN_ANALYZERS

                if name in BUILTIN_ANALYZERS:
                    analyzer_class = BUILTIN_ANALYZERS[name]
                    self.analyzers.append(analyzer_class())
                    logger.info(f"Loaded built-in analyzer: {name}")
                    return
            except ImportError:
                pass

            # Try to load as markdown-based agent
            try:
                from scriptrag.agents import AgentLoader

                loader = AgentLoader()
                agent_analyzer = loader.load_agent(name)
                self.analyzers.append(agent_analyzer)
                logger.info(f"Loaded markdown agent: {name}")
                return
            except (ImportError, ValueError):
                pass

            raise ValueError(f"Unknown analyzer: {name}")

        self.analyzers.append(self._analyzer_registry[name]())
        logger.info(f"Loaded registered analyzer: {name}")

    async def analyze(
        self,
        path: Path | None = None,
        recursive: bool = True,
        force: bool = False,
        dry_run: bool = False,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> AnalyzeResult:
        """Execute analyze operation.

        Args:
            path: Path to search for Fountain files
            recursive: Whether to search recursively
            force: Force re-processing of all scenes
            dry_run: Preview changes without applying them
            progress_callback: Optional callback for progress updates

        Returns:
            AnalyzeResult with details of the operation
        """
        result = AnalyzeResult()

        try:
            # Step 1: Find all Fountain files
            lister = ScriptLister()
            scripts = lister.list_scripts(path, recursive)

            if not scripts:
                logger.info("No Fountain files found")
                return result

            logger.info(f"Found {len(scripts)} Fountain files")

            # Step 2: Process each file
            for i, script_meta in enumerate(scripts):
                if progress_callback:
                    progress = (i + 1) / len(scripts)
                    progress_callback(
                        progress, f"Processing {script_meta.file_path.name}"
                    )

                try:
                    file_result = await self._process_file(
                        script_meta.file_path,
                        force=force,
                        dry_run=dry_run,
                    )
                    result.files.append(file_result)
                except Exception as e:
                    logger.error(f"Failed to process {script_meta.file_path}: {e!s}")
                    result.files.append(
                        FileResult(
                            path=script_meta.file_path,
                            updated=False,
                            error=str(e),
                        )
                    )
                    result.errors.append(f"{script_meta.file_path}: {e}")

        except Exception as e:
            logger.error(f"Analyze operation failed: {e!s}")
            result.errors.append(f"Analyze failed: {e!s}")

        return result

    async def _process_file(
        self,
        file_path: Path,
        force: bool,
        dry_run: bool,
    ) -> FileResult:
        """Process a single file.

        Args:
            file_path: Path to the Fountain file
            force: Force re-processing
            dry_run: Preview mode

        Returns:
            FileResult with processing details
        """
        logger.debug(f"Processing file: {file_path}")

        try:
            # Parse the fountain file
            parser = FountainParser()
            script = parser.parse_file(file_path)

            # Check if file needs processing
            if not force and not self._file_needs_update(file_path, script):
                return FileResult(path=file_path, updated=False)

            # Initialize analyzers
            for analyzer in self.analyzers:
                if hasattr(analyzer, "initialize"):  # pragma: no cover
                    await analyzer.initialize()

            # Process each scene
            updated_scenes = []
            for scene in script.scenes:
                if force or self._scene_needs_update(scene):
                    # Build scene data for analyzers
                    scene_data = {
                        "content": scene.content,
                        "heading": scene.heading,
                        "dialogue": [
                            {"character": d.character, "text": d.text}
                            for d in scene.dialogue_lines
                        ],
                        "action": scene.action_lines,
                        "characters": list({d.character for d in scene.dialogue_lines}),
                    }

                    # Run analyzers
                    metadata: dict[str, Any] = {
                        "content_hash": scene.content_hash,
                        "analyzed_at": datetime.now().isoformat(),
                        "analyzers": {},
                    }

                    for analyzer in self.analyzers:
                        try:
                            result = await analyzer.analyze(scene_data)
                            analyzer_result = {
                                "result": result,
                            }
                            if hasattr(analyzer, "version"):  # pragma: no cover
                                analyzer_result["version"] = analyzer.version
                            metadata["analyzers"][analyzer.name] = analyzer_result
                        except Exception as e:  # pragma: no cover
                            logger.error(
                                f"Analyzer {analyzer.name} failed on "
                                f"scene {scene.number}: {e}"
                            )

                    # Update scene metadata
                    scene.update_boneyard(metadata)
                    updated_scenes.append(scene)

            # Clean up analyzers
            for analyzer in self.analyzers:
                if hasattr(analyzer, "cleanup"):  # pragma: no cover
                    await analyzer.cleanup()

            # In dry run mode, just report what would happen
            if dry_run:
                return FileResult(
                    path=file_path,
                    updated=len(updated_scenes) > 0,
                    scenes_updated=len(updated_scenes),
                )

            # Write back to file if there are updates
            if updated_scenes:  # pragma: no cover
                parser.write_with_updated_scenes(file_path, script, updated_scenes)

            return FileResult(
                path=file_path,
                updated=len(updated_scenes) > 0,
                scenes_updated=len(updated_scenes),
            )

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            raise

    def _file_needs_update(self, _file_path: Path, script: Script) -> bool:
        """Check if a file needs updating.

        Args:
            file_path: Path to the file
            script: Parsed Script object

        Returns:
            True if file needs processing
        """
        # Check if any scene needs updating
        if isinstance(script, Script):
            for scene in script.scenes:
                if self._scene_needs_update(scene):
                    return True

        return False

    def _scene_needs_update(self, scene: Scene) -> bool:
        """Check if a scene needs updating.

        Args:
            scene: Scene object

        Returns:
            True if scene needs processing
        """
        if not isinstance(scene, Scene):
            return False

        # No metadata yet
        if scene.boneyard_metadata is None:
            return True

        # Check if metadata is outdated (e.g., missing analyzer results)
        metadata = scene.boneyard_metadata

        # Check if analyzed_at exists and is recent
        if "analyzed_at" not in metadata:
            return True

        # Check if all registered analyzers have been run
        if "analyzers" in metadata:
            existing_analyzers = set(metadata["analyzers"].keys())
            current_analyzers = {a.name for a in self.analyzers}
            if current_analyzers - existing_analyzers:
                # New analyzers to run
                return True

        # For now, consider up to date
        return False
