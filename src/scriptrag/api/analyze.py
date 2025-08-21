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
    """Result data from analyzing a single screenplay file.

    Tracks the outcome of processing one Fountain file through the analysis
    pipeline, including whether any scenes were updated and error information.
    Used for reporting and debugging analysis operations.

    Attributes:
        path: Path to the Fountain file that was processed
        updated: True if any scenes in the file were updated with new analysis
        scenes_updated: Count of individual scenes that received new metadata
        error: Error message if processing failed, None if successful

    Example:
        >>> result = FileResult(
        ...     path=Path("my_script.fountain"),
        ...     updated=True,
        ...     scenes_updated=15
        ... )
        >>> print(f"Updated {result.scenes_updated} scenes")
    """

    path: Path
    updated: bool
    scenes_updated: int = 0
    error: str | None = None


@dataclass
class AnalyzeResult:
    """Aggregated results from analyzing multiple screenplay files.

    Contains outcome data from processing one or more Fountain files through
    the analysis pipeline. Provides both individual file results and summary
    statistics for batch operations.

    Attributes:
        files: List of FileResult objects, one for each processed file
        errors: List of error messages from failed operations that couldn't
               be attributed to specific files

    Properties:
        total_files_updated: Count of files that had at least one scene updated
        total_scenes_updated: Sum of all scenes updated across all files

    Example:
        >>> result = AnalyzeResult()
        >>> result.files.append(FileResult(Path("script1.fountain"), True, 10))
        >>> result.total_files_updated
        1
        >>> result.total_scenes_updated
        10
    """

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
    """Protocol defining the interface for scene analysis components.

    Defines the contract that all scene analyzers must implement to participate
    in the analysis pipeline. Analyzers receive scene data and return metadata
    that gets attached to scenes in the Fountain file's boneyard comments.

    The protocol enables pluggable analyzers for different types of scene
    analysis: character relationships, embeddings, themes, etc.

    Example:
        >>> class MyAnalyzer:
        ...     @property
        ...     def name(self) -> str:
        ...         return "my_analyzer"
        ...
        ...     async def analyze(self, scene: dict) -> dict:
        ...         return {"analysis": "completed"}
    """

    async def analyze(self, scene: dict[str, Any]) -> dict[str, Any]:
        """Analyze a scene and return analysis metadata.

        Args:
            scene: Dictionary containing scene data with keys like 'content',
                  'heading', 'dialogue', 'action', 'characters'

        Returns:
            Dictionary containing analysis results to be stored in scene metadata
        """
        ...

    @property
    def name(self) -> str:
        """Unique identifier for this analyzer.

        Returns:
            String name used for metadata storage and analyzer registration
        """
        ...


class AnalyzeCommand:
    """Orchestrates the analysis of screenplay files through multiple analyzers.

    Manages the complete analysis pipeline from finding Fountain files to running
    scene analyzers and updating files with metadata. Supports multiple analyzers
    running in sequence, incremental processing, and robust error handling.

    The command coordinates:
    1. Discovery of Fountain files in directories
    2. Loading and initialization of scene analyzers
    3. Parsing of screenplay files
    4. Running analyzers on individual scenes
    5. Updating files with analysis metadata
    6. Progress reporting and error collection

    Example:
        >>> command = AnalyzeCommand()
        >>> command.load_analyzer("relationships")
        >>> result = await command.analyze(Path("scripts/"))
        >>> print(f"Analyzed {result.total_files_updated} files")
    """

    def __init__(
        self,
        analyzers: list[SceneAnalyzer | Any] | None = None,
    ) -> None:
        """Initialize analyze command.

        Args:
            analyzers: Optional list of scene analyzers
        """
        self.analyzers = analyzers or []
        self._analyzer_registry: dict[str, type[SceneAnalyzer | BaseSceneAnalyzer]] = {}

    @classmethod
    def from_config(cls) -> "AnalyzeCommand":
        """Create AnalyzeCommand instance from configuration settings.

        Factory method that creates a properly initialized AnalyzeCommand
        using the current ScriptRAG configuration. Currently returns a
        basic instance, but could be extended to load analyzers from
        configuration in the future.

        Returns:
            New AnalyzeCommand instance ready for use

        Example:
            >>> command = AnalyzeCommand.from_config()
            >>> command.load_analyzer("relationships")
            >>> result = await command.analyze()
        """
        return cls()

    def register_analyzer(self, name: str, analyzer_class: type[SceneAnalyzer]) -> None:
        """Register an analyzer class for dynamic loading.

        Adds an analyzer class to the internal registry so it can be loaded
        by name using load_analyzer(). This enables configuration-driven
        analyzer selection and plugin-style architecture.

        Args:
            name: Identifier to register the analyzer under. Should match
                 the analyzer's .name property for consistency.
            analyzer_class: Class that implements the SceneAnalyzer protocol

        Example:
            >>> command.register_analyzer("my_analyzer", MyAnalyzer)
            >>> command.load_analyzer("my_analyzer")
            >>> len(command.analyzers)
            1
        """
        self._analyzer_registry[name] = analyzer_class

    def load_analyzer(self, name: str, config: dict[str, Any] | None = None) -> None:
        """Load and instantiate an analyzer by name.

        Attempts to find and load an analyzer using multiple strategies:
        1. Check registered analyzers from register_analyzer()
        2. Look in built-in analyzers from the analyzers package
        3. Try to load as a markdown-based agent

        The analyzer is instantiated and added to the active analyzers list.
        Duplicate analyzers (same name) are skipped to prevent redundant processing.

        Args:
            name: Name of the analyzer to load. Checked against registered
                 analyzers, built-in analyzers, and agent names.
            config: Optional configuration dictionary passed to the analyzer
                   constructor

        Raises:
            ValueError: If no analyzer can be found with the given name

        Example:
            >>> command.load_analyzer("relationships")
            >>> command.load_analyzer("embedding", {"model": "sentence-transformers"})
            >>> len(command.analyzers)
            2
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
                    self.analyzers.append(analyzer_class(config))
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
        brittle: bool = False,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> AnalyzeResult:
        """Execute analyze operation.

        Args:
            path: Path to search for Fountain files
            recursive: Whether to search recursively
            force: Force re-processing of all scenes
            dry_run: Preview changes without applying them
            brittle: Stop processing if any analyzer fails
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
                        brittle=brittle,
                    )
                    result.files.append(file_result)
                except Exception as e:
                    if brittle:
                        logger.error(
                            f"Failed to process {script_meta.file_path}: {e!s} "
                            "(brittle mode - stopping)"
                        )
                        raise
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
            if brittle:
                logger.error(f"Analyze operation failed: {e!s} (brittle mode)")
                raise
            logger.error(f"Analyze operation failed: {e!s}")
            result.errors.append(f"Analyze failed: {e!s}")

        return result

    async def _process_file(
        self,
        file_path: Path,
        force: bool,
        dry_run: bool,
        brittle: bool = False,
    ) -> FileResult:
        """Process a single Fountain file through the analysis pipeline.

        Handles the complete processing of one screenplay file including parsing,
        analyzer initialization, scene processing, and file updates. Manages
        error handling, dry-run mode, and incremental processing logic.

        The processing pipeline:
        1. Parse Fountain file using FountainParser
        2. Check if file needs processing (unless force=True)
        3. Set up analyzer context (script objects, Bible metadata)
        4. Initialize all loaded analyzers
        5. Process each scene that needs updating
        6. Run all analyzers on scene data
        7. Update scene metadata with analysis results
        8. Write updated file back to disk (unless dry_run=True)
        9. Clean up analyzer resources

        Args:
            file_path: Path to the Fountain screenplay file to process
            force: If True, process all scenes regardless of existing metadata
            dry_run: If True, perform analysis but don't write changes to file
            brittle: If True, stop processing on first analyzer error instead
                    of logging and continuing

        Returns:
            FileResult containing processing outcome, scene counts, and any
            error information

        Raises:
            Exception: Re-raises analyzer exceptions when brittle=True, otherwise
                      catches and logs all errors

        Note:
            In dry-run mode, analysis is performed but files are not modified.
            This allows previewing what would be changed without side effects.
        """
        logger.debug(f"Processing file: {file_path}")

        try:
            # Parse the fountain file
            parser = FountainParser()
            script = parser.parse_file(file_path)

            # Check if file needs processing
            if not force and not self._file_needs_update(file_path, script):
                return FileResult(path=file_path, updated=False)

            # Pass script context to analyzers that support it
            for analyzer in self.analyzers:
                # Set script context for MarkdownAgentAnalyzer
                if hasattr(analyzer, "script"):
                    analyzer.script = script

                # Pass Bible metadata to relationships analyzer
                if (
                    hasattr(analyzer, "name")
                    and analyzer.name == "relationships"
                    and hasattr(analyzer, "bible_characters")
                    and not analyzer.bible_characters
                ):
                    bible_metadata = await self._load_bible_metadata(file_path)
                    if bible_metadata and hasattr(analyzer, "_build_alias_index"):
                        analyzer.bible_characters = bible_metadata
                        analyzer._build_alias_index()

            # Initialize analyzers
            for analyzer in self.analyzers:
                if hasattr(analyzer, "initialize"):  # pragma: no cover
                    await analyzer.initialize()

            # Process each scene
            updated_scenes = []

            # In dry run mode, skip all processing entirely
            if dry_run:
                for scene in script.scenes:
                    if force or self._scene_needs_update(scene):
                        updated_scenes.append(scene)
                # Clean up and return early
                for analyzer in self.analyzers:
                    if hasattr(analyzer, "cleanup"):  # pragma: no cover
                        await analyzer.cleanup()
                logger.debug(f"Dry run mode - not writing to {file_path}")
                return FileResult(
                    path=file_path,
                    updated=len(updated_scenes) > 0,
                    scenes_updated=len(updated_scenes),
                )

            # Normal processing (not dry run)
            for scene in script.scenes:
                if force or self._scene_needs_update(scene):
                    # Build scene data for analyzers (only if not dry run)
                    scene_data = {
                        "content": scene.content,
                        "original_text": scene.original_text,  # For hashing/embedding
                        "heading": scene.heading,
                        "dialogue": [
                            {"character": d.character, "text": d.text}
                            for d in scene.dialogue_lines
                        ],
                        "action": scene.action_lines,
                        "characters": list({d.character for d in scene.dialogue_lines}),
                    }

                    # Process metadata and run analyzers
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
                            if brittle:
                                logger.error(
                                    f"Analyzer {analyzer.name} failed on scene "
                                    f"{scene.number}: {e} (brittle mode - stopping)"
                                )
                                raise
                            logger.warning(
                                f"Analyzer {analyzer.name} failed on scene "
                                f"{scene.number}: {e} (skipping)"
                            )

                    # Update scene metadata
                    scene.update_boneyard(metadata)
                    updated_scenes.append(scene)

            # Clean up analyzers
            for analyzer in self.analyzers:
                if hasattr(analyzer, "cleanup"):  # pragma: no cover
                    await analyzer.cleanup()

            # Write back to file if there are updates
            # Only write if scenes actually have new metadata
            scenes_with_metadata = [
                s for s in updated_scenes if getattr(s, "has_new_metadata", False)
            ]
            if scenes_with_metadata:  # pragma: no cover
                logger.debug(
                    f"Writing {len(scenes_with_metadata)} scenes to {file_path}"
                )
                parser.write_with_updated_scenes(
                    file_path, script, scenes_with_metadata, dry_run=False
                )

            return FileResult(
                path=file_path,
                updated=len(updated_scenes) > 0,
                scenes_updated=len(updated_scenes),
            )

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            raise

    def _file_needs_update(self, _file_path: Path, script: Script) -> bool:
        """Determine if a screenplay file needs analysis processing.

        Checks whether any scenes in the script need analysis by examining
        existing metadata and comparing with currently loaded analyzers.
        Used to skip files that are already up-to-date unless force mode.

        Args:
            _file_path: Path to the file (parameter preserved for compatibility
                       but not currently used in the logic)
            script: Parsed Script object containing scenes with potential metadata

        Returns:
            True if the file contains scenes that need processing by current
            analyzers, False if all scenes are up-to-date

        Note:
            Currently checks all scenes in the script. A file needs updating
            if any scene needs updating according to _scene_needs_update().
        """
        # Check if any scene needs updating
        if isinstance(script, Script):
            for scene in script.scenes:
                if self._scene_needs_update(scene):
                    return True

        return False

    def _scene_needs_update(self, scene: Scene) -> bool:
        """Determine if a scene needs analysis processing.

        Checks scene metadata to decide whether analysis should be performed:
        1. Scenes without any metadata need processing
        2. Scenes missing 'analyzed_at' timestamp need processing
        3. Scenes missing results from currently loaded analyzers need processing

        This enables incremental analysis where only new or changed scenes
        are processed, and new analyzers are run on existing scenes.

        Args:
            scene: Scene object that may contain existing analysis metadata
                  in its boneyard_metadata attribute

        Returns:
            True if the scene should be processed by the analysis pipeline,
            False if it's already up-to-date with current analyzer set

        Example:
            A scene with relationship analysis but no embedding analysis
            would return True if an embedding analyzer is loaded, enabling
            incremental processing of just the missing analysis type.
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

    async def _load_bible_metadata(self, script_path: Path) -> dict[str, Any] | None:
        """Load Bible character metadata from database for analyzer context.

        Retrieves character alias data that may have been extracted from
        script Bible files and stored in the database. This metadata is used
        by analyzers like the relationships analyzer to identify characters
        mentioned in scenes.

        The method looks for character data stored under 'bible.characters'
        in the script's metadata column, which contains the output from
        Bible character extraction operations.

        Args:
            script_path: Path to the script file to look up in database

        Returns:
            Dictionary containing Bible character metadata if found and valid,
            None if script not in database, no metadata exists, or database
            errors occur. The format matches BibleCharacterExtractor output.

        Example:
            >>> metadata = await command._load_bible_metadata(Path("script.fountain"))
            >>> if metadata:
            ...     char_count = len(metadata.get("characters", []))
            ...     print(f"Found {char_count} Bible characters")

        Note:
            All database errors are caught and logged as debug messages.
            Returns None gracefully to allow analysis to continue without
            Bible character data if database issues occur.
        """
        try:
            # Try to load from database
            import json

            from scriptrag.api.database_operations import DatabaseOperations
            from scriptrag.config import get_settings

            settings = get_settings()
            db_ops = DatabaseOperations(settings)

            if not db_ops.check_database_exists():
                return None

            with db_ops.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT metadata FROM scripts WHERE file_path = ?",
                    (str(script_path),),
                )
                row = cursor.fetchone()

                if row and row[0]:
                    metadata = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    bible_chars = metadata.get("bible.characters")
                    return bible_chars if isinstance(bible_chars, dict) else None

        except Exception as e:
            logger.debug(f"Could not load Bible metadata: {e}")

        return None
