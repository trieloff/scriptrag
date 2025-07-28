"""Bulk import functionality for fountain files.

This module provides functionality for importing multiple fountain files
at once, with support for TV series organization and progress tracking.
"""

import json
import time
import traceback
from collections import defaultdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict
from uuid import UUID, uuid4

from scriptrag.config import get_logger
from scriptrag.database.operations import GraphOperations
from scriptrag.models import Episode, Script, Season

from . import FountainParser, FountainParsingError
from .series_detector import SeriesInfo, SeriesPatternDetector

logger = get_logger(__name__)


class ErrorCategory(str, Enum):
    """Categories of errors that can occur during import."""

    PARSING = "parsing"
    VALIDATION = "validation"
    DATABASE = "database"
    GRAPH = "graph"
    FILESYSTEM = "filesystem"
    UNKNOWN = "unknown"


class ImportErrorInfo(TypedDict):
    """Structured error information."""

    category: ErrorCategory
    message: str
    details: dict[str, Any]
    stack_trace: str | None
    suggestions: list[str]


class FileImportStatus(str, Enum):
    """Status of a file import."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY_PENDING = "retry_pending"
    SKIPPED = "skipped"


class ImportState(TypedDict):
    """Persistent import state for recovery."""

    started_at: str
    updated_at: str
    total_files: int
    files: dict[str, dict[str, Any]]  # path -> {status, error, script_id, etc.}
    batch_size: int
    series_cache: dict[str, str]
    season_cache: dict[str, str]  # serialized tuple keys


class BulkImportResult:
    """Results from a bulk import operation."""

    def __init__(self) -> None:
        """Initialize import results."""
        self.total_files = 0
        self.successful_imports = 0
        self.failed_imports = 0
        self.skipped_files = 0
        self.errors: dict[str, ImportErrorInfo] = {}  # Enhanced error structure
        self.imported_scripts: dict[str, str] = {}  # path -> script_id
        self.series_created: dict[str, str] = {}  # series_name -> script_id
        self.retry_candidates: list[str] = []  # Files that can be retried
        self.start_time = time.time()
        self.end_time: float | None = None

    def add_success(self, file_path: str, script_id: str) -> None:
        """Record a successful import."""
        self.successful_imports += 1
        self.imported_scripts[file_path] = script_id

    def add_failure(
        self,
        file_path: str,
        error: Exception | str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        suggestions: list[str] | None = None,
    ) -> None:
        """Record a failed import with enhanced error information."""
        self.failed_imports += 1

        # Build error details
        error_info = ImportErrorInfo(
            category=category,
            message=str(error),
            details={"file_path": file_path, "timestamp": datetime.now().isoformat()},
            stack_trace=(
                traceback.format_exc() if isinstance(error, Exception) else None
            ),
            suggestions=suggestions or [],
        )

        # Add common suggestions based on error type
        if category == ErrorCategory.PARSING:
            error_info["suggestions"].extend(
                [
                    "Check that the file is a valid Fountain format file",
                    "Ensure the file encoding is UTF-8",
                    "Validate there are no syntax errors in the screenplay",
                ]
            )
        elif category == ErrorCategory.DATABASE:
            error_info["suggestions"].extend(
                [
                    "Check database connectivity",
                    "Ensure sufficient disk space",
                    "Verify database permissions",
                ]
            )
            # Mark as retry candidate for database errors
            if file_path not in self.retry_candidates:
                self.retry_candidates.append(file_path)

        self.errors[file_path] = error_info

    def add_skipped(self, _file_path: str) -> None:
        """Record a skipped file."""
        self.skipped_files += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert results to dictionary."""
        self.end_time = time.time()
        duration = self.end_time - self.start_time

        return {
            "total_files": self.total_files,
            "successful_imports": self.successful_imports,
            "failed_imports": self.failed_imports,
            "skipped_files": self.skipped_files,
            "errors": self.errors,
            "imported_scripts": self.imported_scripts,
            "series_created": self.series_created,
            "retry_candidates": self.retry_candidates,
            "duration_seconds": duration,
            "files_per_second": self.total_files / duration if duration > 0 else 0,
        }

    def get_error_summary(self) -> dict[ErrorCategory, list[str]]:
        """Get summary of errors by category."""
        summary: dict[ErrorCategory, list[str]] = defaultdict(list)
        for file_path, error in self.errors.items():
            summary[error["category"]].append(file_path)
        return dict(summary)


class BulkImporter:
    """Handles bulk import of fountain files with TV series support."""

    def __init__(
        self,
        graph_ops: GraphOperations,
        custom_pattern: str | None = None,
        skip_existing: bool = True,
        update_existing: bool = False,
        batch_size: int = 10,
        state_file: Path | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize bulk importer.

        Args:
            graph_ops: Graph operations instance
            custom_pattern: Custom regex pattern for series detection
            skip_existing: Skip files that already exist in database
            update_existing: Update existing scripts if file is newer
            batch_size: Number of files to process per transaction batch
            state_file: Path to save import state for recovery
            verbose: Enable verbose logging
        """
        self.graph_ops = graph_ops
        self.parser = FountainParser()
        self.series_detector = SeriesPatternDetector(custom_pattern)
        self.skip_existing = skip_existing
        self.update_existing = update_existing
        self.batch_size = batch_size
        # Use temp directory in CI environments or when home is not accessible
        default_state_dir = Path.home() / ".scriptrag"
        try:
            default_state_dir.mkdir(parents=True, exist_ok=True)
            self.state_file = state_file or default_state_dir / "import_state.json"
        except (OSError, PermissionError):
            # Fallback to temp directory if home is not writable
            import tempfile

            temp_dir = Path(tempfile.gettempdir()) / ".scriptrag"
            temp_dir.mkdir(parents=True, exist_ok=True)
            self.state_file = state_file or temp_dir / "import_state.json"
        self.verbose = verbose

        # Cache for series and season IDs
        self._series_cache: dict[str, str] = {}  # series_name -> script_id
        # (script_id, season_num) -> season_id
        self._season_cache: dict[tuple[str, int], str] = {}

        # Import state for recovery
        self._import_state: ImportState | None = None
        self._load_state()

    def _load_state(self) -> None:
        """Load import state from file if it exists."""
        # Skip loading state if running in test environment
        import os

        if os.environ.get("PYTEST_CURRENT_TEST"):
            self._import_state = None
            return

        if self.state_file.exists():
            try:
                with self.state_file.open() as f:
                    self._import_state = json.load(f)
                    # Restore caches
                    self._series_cache = self._import_state.get("series_cache", {})
                    # Deserialize season cache with tuple keys
                    season_cache_str = self._import_state.get("season_cache", {})
                    self._season_cache = {
                        tuple(json.loads(k)): v for k, v in season_cache_str.items()
                    }
                logger.info(f"Loaded import state from {self.state_file}")
            except Exception as e:
                logger.warning(f"Failed to load import state: {e}")
                self._import_state = None

    def _save_state(self, file_paths: list[Path], result: BulkImportResult) -> None:
        """Save current import state for recovery."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Build file status map
            files_status = {}
            for path in file_paths:
                path_str = str(path)
                if path_str in result.imported_scripts:
                    status = FileImportStatus.SUCCESS
                elif path_str in result.errors:
                    status = FileImportStatus.FAILED
                    if path_str in result.retry_candidates:
                        status = FileImportStatus.RETRY_PENDING
                else:
                    status = FileImportStatus.PENDING

                files_status[path_str] = {
                    "status": status,
                    "script_id": result.imported_scripts.get(path_str),
                    "error": result.errors.get(path_str),
                    "last_attempt": datetime.now().isoformat(),
                }

            # Serialize season cache with tuple keys
            season_cache_str = {json.dumps(k): v for k, v in self._season_cache.items()}

            state = ImportState(
                started_at=datetime.fromtimestamp(result.start_time).isoformat(),
                updated_at=datetime.now().isoformat(),
                total_files=result.total_files,
                files=files_status,
                batch_size=self.batch_size,
                series_cache=self._series_cache,
                season_cache=season_cache_str,
            )

            with self.state_file.open("w") as f:
                json.dump(state, f, indent=2)

            if self.verbose:
                logger.info(f"Saved import state to {self.state_file}")

        except Exception as e:
            logger.error(f"Failed to save import state: {e}")

    def import_files(
        self,
        file_paths: list[Path],
        series_name_override: str | None = None,
        dry_run: bool = False,
        progress_callback: Any = None,
        retry_failed: bool = False,
    ) -> BulkImportResult:
        """Import multiple fountain files.

        Args:
            file_paths: List of fountain file paths
            series_name_override: Override auto-detected series name
            dry_run: Preview what would be imported without actually importing
            progress_callback: Optional callback for progress updates
            retry_failed: Retry previously failed imports

        Returns:
            BulkImportResult with import statistics
        """
        # Filter files based on retry mode and previous state
        if retry_failed and self._import_state:
            file_paths = self._filter_retry_files(file_paths)
        result = BulkImportResult()
        result.total_files = len(file_paths)

        # Detect series information for all files
        logger.info(f"Detecting series patterns in {len(file_paths)} files")
        series_infos = self.series_detector.detect_bulk(file_paths)

        # Track start time for ETA calculations
        batch_start_times: list[float] = []

        # Override series names if specified
        if series_name_override:
            for info in series_infos.values():
                if info.is_series:
                    info.series_name = series_name_override

        # Group by series
        grouped = self.series_detector.group_by_series(series_infos)

        if dry_run:
            return self._dry_run_preview(grouped, result)

        # Process each series
        total_processed = 0
        for series_name, episodes in grouped.items():
            logger.info(f"Processing series: {series_name} ({len(episodes)} files)")

            # Process in batches
            for i in range(0, len(episodes), self.batch_size):
                batch = episodes[i : i + self.batch_size]
                batch_start = time.time()

                try:
                    self._process_batch(series_name, batch, result)
                except Exception as e:
                    logger.error(f"Batch processing failed for {series_name}: {e}")
                    # Mark all files in batch as failed
                    for file_path, _ in batch:
                        result.add_failure(
                            str(file_path),
                            e,
                            ErrorCategory.DATABASE,
                            ["Batch transaction failed, consider reducing batch size"],
                        )

                # Track batch timing for ETA
                batch_end = time.time()
                batch_start_times.append(batch_end - batch_start)
                total_processed += len(batch)

                # Calculate ETA
                if batch_start_times:
                    avg_batch_time = sum(batch_start_times) / len(batch_start_times)
                    files_remaining = len(file_paths) - total_processed
                    batches_remaining = (
                        files_remaining + self.batch_size - 1
                    ) // self.batch_size
                    eta_seconds = avg_batch_time * batches_remaining
                else:
                    eta_seconds = 0

                # Progress callback with ETA
                if progress_callback:
                    progress = total_processed / len(file_paths)
                    progress_msg = (
                        f"Processing {series_name}... (ETA: {eta_seconds:.0f}s)"
                    )
                    if self.verbose:
                        progress_msg += f" [{total_processed}/{len(file_paths)}]"
                    progress_callback(progress, progress_msg)

                # Save state periodically
                if i % (self.batch_size * 5) == 0:  # Every 5 batches
                    self._save_state(file_paths, result)

        # Final state save
        self._save_state(file_paths, result)
        return result

    def _dry_run_preview(
        self,
        grouped: dict[str, list[tuple[Path, SeriesInfo]]],
        result: BulkImportResult,
    ) -> BulkImportResult:
        """Preview what would be imported without actually importing."""
        logger.info("DRY RUN: Previewing import operations")

        for series_name, episodes in grouped.items():
            logger.info(f"Would import series: {series_name}")

            # Group by season
            by_season = defaultdict(list)
            standalone = []

            for path, info in episodes:
                if info.season_number is not None:
                    by_season[info.season_number].append((path, info))
                else:
                    standalone.append((path, info))

            # Log season structure
            for season_num in sorted(by_season.keys()):
                season_episodes = by_season[season_num]
                logger.info(f"  Season {season_num}: {len(season_episodes)} episodes")
                for path, info in season_episodes[:3]:  # Show first 3
                    ep_str = (
                        f"Episode {info.episode_number}"
                        if info.episode_number
                        else "Special"
                    )
                    title = info.episode_title or "Untitled"
                    logger.info(f"    {ep_str}: {title} ({path.name})")
                if len(season_episodes) > 3:
                    logger.info(f"    ... and {len(season_episodes) - 3} more")

            if standalone:
                logger.info(f"  Standalone scripts: {len(standalone)}")
                for path, info in standalone[:3]:
                    logger.info(f"    {info.episode_title or path.name}")
                if len(standalone) > 3:
                    logger.info(f"    ... and {len(standalone) - 3} more")

            # Note: result.total_files is already set by the caller

        return result

    def _filter_retry_files(self, file_paths: list[Path]) -> list[Path]:
        """Filter files to only include those marked for retry."""
        if not self._import_state:
            return file_paths

        retry_files = []
        for path in file_paths:
            path_str = str(path)
            file_info = self._import_state["files"].get(path_str, {})
            if file_info.get("status") in [
                FileImportStatus.RETRY_PENDING,
                FileImportStatus.FAILED,
            ]:
                retry_files.append(path)

        logger.info(f"Found {len(retry_files)} files to retry")
        return retry_files

    def _process_batch(
        self,
        _series_name: str,
        batch: list[tuple[Path, SeriesInfo]],
        result: BulkImportResult,
    ) -> None:
        """Process a batch of files for a series with transaction support."""
        # Initialize pending graph operations
        self._pending_graph_ops: list[dict[str, Any]] = []

        # Use a transaction for the entire batch
        try:
            with self.graph_ops.connection.transaction() as conn:
                batch_operations = []

                # First pass: validate and prepare all files
                for file_path, series_info in batch:
                    try:
                        # Parse and validate file
                        script = self._parse_and_validate_file(file_path, result)
                        if script is None:
                            continue  # Skip this file

                        batch_operations.append((file_path, series_info, script))
                    except Exception as e:
                        # Log individual file errors but continue batch
                        self._handle_file_error(file_path, e, result)
                        raise  # Re-raise to trigger batch rollback

                # Second pass: import all validated files in the transaction
                for file_path, series_info, script in batch_operations:
                    try:
                        self._import_single_file_transactional(
                            file_path, series_info, script, result, conn
                        )
                    except Exception as e:
                        self._handle_file_error(file_path, e, result)
                        raise  # Re-raise to trigger batch rollback

        except Exception:
            # Transaction will be rolled back automatically
            logger.error("Batch transaction failed, rolling back all changes")
            raise

        # Execute pending graph operations after transaction commits
        for op in self._pending_graph_ops:
            self._execute_graph_operations(op)

    def _parse_and_validate_file(
        self, file_path: Path, result: BulkImportResult
    ) -> Script | None:
        """Parse and validate a fountain file."""
        if self.verbose:
            logger.debug(f"Parsing {file_path}")

        # Check if file already exists
        if self.skip_existing and self._file_exists(file_path):
            logger.debug(f"Skipping existing file: {file_path}")
            result.add_skipped(str(file_path))
            return None

        # Parse the fountain file
        try:
            return self.parser.parse_file(file_path)
        except FountainParsingError as e:
            result.add_failure(
                str(file_path),
                e,
                ErrorCategory.PARSING,
                [
                    (
                        f"Line {getattr(e, 'line_number', 'unknown')}: {e}"
                        if hasattr(e, "line_number")
                        else str(e)
                    )
                ],
            )
            return None
        except Exception as e:
            result.add_failure(
                str(file_path),
                e,
                (
                    ErrorCategory.FILESYSTEM
                    if "Permission" in str(e)
                    else ErrorCategory.UNKNOWN
                ),
            )
            return None

    def _handle_file_error(
        self, file_path: Path, error: Exception, result: BulkImportResult
    ) -> None:
        """Handle errors for a specific file."""
        error_category = ErrorCategory.UNKNOWN

        # Categorize error
        if isinstance(error, FountainParsingError):
            error_category = ErrorCategory.PARSING
        elif "database" in str(error).lower() or "sqlite" in str(error).lower():
            error_category = ErrorCategory.DATABASE
        elif "graph" in str(error).lower():
            error_category = ErrorCategory.GRAPH
        elif "permission" in str(error).lower() or "access" in str(error).lower():
            error_category = ErrorCategory.FILESYSTEM

        result.add_failure(str(file_path), error, error_category)

    def _import_single_file_transactional(
        self,
        file_path: Path,
        series_info: SeriesInfo,
        script: Script,
        result: BulkImportResult,
        conn: Any,
    ) -> None:
        """Import a single fountain file within a transaction."""
        if self.verbose:
            logger.debug(f"Importing {file_path} (transactional)")

        # Store operations to track for graph creation
        created_scripts: list[tuple[str, Script]] = []  # (script_id, script_obj)
        created_seasons: list[tuple[str, Season]] = []  # (script_id, season_obj)

        # Update script metadata based on series info
        if series_info.is_series:
            script.is_series = True
            script.title = series_info.series_name

            # Get or create series script
            series_script_id, series_script = self._get_or_create_series(
                series_info.series_name, script, conn
            )

            # Track for graph creation
            if series_script:
                created_scripts.append((series_script_id, series_script))

            # Handle episodes
            if series_info.season_number is not None:
                season_id, season_obj = self._create_episode_structure(
                    script, series_info, series_script_id, file_path, conn
                )
                # Track for graph creation
                if season_obj:
                    created_seasons.append((series_script_id, season_obj))
        else:
            # Standalone script
            script_id = self._save_standalone_script(script, file_path, conn)
            # Track for graph creation
            created_scripts.append((script_id, script))

        # Graph operations must be done AFTER the transaction commits
        # Store them to execute later
        self._pending_graph_ops = getattr(self, "_pending_graph_ops", [])
        self._pending_graph_ops.append(
            {
                "file_path": file_path,
                "created_scripts": created_scripts,
                "created_seasons": created_seasons,
                "result": result,
                "script_id": str(script.id),
            }
        )

        result.add_success(str(file_path), str(script.id))

    def _execute_graph_operations(self, op: dict[str, Any]) -> None:
        """Execute pending graph operations after transaction commits."""
        file_path = op["file_path"]
        created_scripts = op["created_scripts"]
        created_seasons = op["created_seasons"]
        result = op["result"]

        # Create graph operations for scripts
        for script_id, script_obj in created_scripts:
            try:
                self.graph_ops.create_script_graph(script_obj)
            except Exception as graph_error:
                # Log but don't fail the entire import
                logger.error(
                    f"Failed to create graph for script {script_id}: {graph_error}"
                )
                # Don't mark as failure since DB import succeeded
                # Just log the graph error
                if str(file_path) not in result.errors:
                    logger.warning(
                        f"Graph creation failed for {file_path}, "
                        f"but database import was successful"
                    )

        # Create graph operations for seasons
        for script_id, season_obj in created_seasons:
            try:
                script_node_id = self._get_script_node_id(script_id)
                self.graph_ops.add_season_to_script(season_obj, script_node_id)
            except Exception as graph_error:
                msg = f"Failed to add season to graph for script {script_id}:"
                logger.error(f"{msg} {graph_error}")

    def _file_exists(self, file_path: Path) -> bool:
        """Check if a file has already been imported."""
        # Query database for existing script with this source file
        query = """
            SELECT id FROM scripts WHERE source_file = ?
        """
        result = self.graph_ops.connection.fetch_one(query, (str(file_path),))
        return result is not None

    def _get_or_create_series(
        self, series_name: str, template_script: Script, conn: Any = None
    ) -> tuple[str, Script | None]:
        """Get or create a series script.

        Returns:
            Tuple of (script_id, series_script_object_if_created)
        """
        if series_name in self._series_cache:
            return self._series_cache[series_name], None

        if conn is None:
            conn = self.graph_ops.connection._get_connection()

        # Check database for existing series
        query = """
            SELECT id FROM scripts WHERE title = ? AND is_series = 1
        """
        cursor = conn.execute(query, (series_name,))
        row = cursor.fetchone()

        if row:
            script_id = row[0]
            series_script = None  # Existing series, no graph operations needed
        else:
            # Create new series script
            series_script = Script(
                id=uuid4(),
                title=series_name,
                is_series=True,
                format="teleplay",
                author=template_script.author,
                genre=template_script.genre,
                description=f"TV Series: {series_name}",
            )
            script_id = self._save_script_to_db(series_script, conn)

        self._series_cache[series_name] = script_id
        return str(script_id), series_script

    def _create_episode_structure(
        self,
        script: Script,
        series_info: SeriesInfo,
        series_script_id: str,
        file_path: Path,
        conn: Any = None,
    ) -> tuple[str, Season | None]:
        """Create episode and season structure for a series script.

        Returns:
            Tuple of (season_id, season_object_if_created)
        """
        if conn is None:
            conn = self.graph_ops.connection._get_connection()

        # Get or create season
        season_id, season_obj = self._get_or_create_season(
            series_script_id, series_info.season_number or 1, conn
        )

        # Create episode
        episode = Episode(
            id=uuid4(),
            title=series_info.episode_title or f"Episode {series_info.episode_number}",
            number=series_info.episode_number or 0,
            season_id=UUID(season_id) if isinstance(season_id, str) else season_id,
            script_id=(
                UUID(series_script_id)
                if isinstance(series_script_id, str)
                else series_script_id
            ),
            writer=script.author,
        )

        # Save episode to database
        self._save_episode_to_db(episode, script, file_path, conn)

        return season_id, season_obj

    def _get_or_create_season(
        self, script_id: str, season_number: int, conn: Any = None
    ) -> tuple[str, Season | None]:
        """Get or create a season.

        Returns:
            Tuple of (season_id, season_object_if_created)
        """
        cache_key = (script_id, season_number)
        if cache_key in self._season_cache:
            return self._season_cache[cache_key], None

        if conn is None:
            conn = self.graph_ops.connection._get_connection()

        # Check database
        query = """
            SELECT id FROM seasons WHERE script_id = ? AND number = ?
        """
        cursor = conn.execute(query, (script_id, season_number))
        row = cursor.fetchone()

        if row:
            season_id = row[0]
            season_obj = None  # Existing season, no graph operations needed
        else:
            # Create new season
            season_obj = Season(
                id=uuid4(),
                number=season_number,
                script_id=UUID(script_id) if isinstance(script_id, str) else script_id,
                title=f"Season {season_number}",
            )
            season_id = self._save_season_to_db(season_obj, conn)

        self._season_cache[cache_key] = season_id
        return str(season_id), season_obj

    def _save_script_to_db(self, script: Script, conn: Any = None) -> str:
        """Save script to database."""
        if conn is None:
            conn = self.graph_ops.connection._get_connection()

        query = """
            INSERT INTO scripts (
                id, title, format, author, description, genre, logline,
                fountain_source, source_file, is_series, title_page_json,
                metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        conn.execute(
            query,
            (
                str(script.id),
                script.title,
                script.format,
                script.author,
                script.description,
                script.genre,
                script.logline,
                script.fountain_source,
                script.source_file,
                script.is_series,
                json.dumps(script.title_page),
                json.dumps(script.metadata),
            ),
        )
        return str(script.id)

    def _save_season_to_db(self, season: Season, conn: Any = None) -> str:
        """Save season to database."""
        if conn is None:
            conn = self.graph_ops.connection._get_connection()

        query = """
            INSERT INTO seasons (
                id, script_id, number, title, description, year, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        conn.execute(
            query,
            (
                str(season.id),
                str(season.script_id),
                season.number,
                season.title,
                season.description,
                season.year,
                json.dumps(season.metadata),
            ),
        )
        return str(season.id)

    def _save_episode_to_db(
        self, episode: Episode, script: Script, file_path: Path, conn: Any = None
    ) -> str:
        """Save episode to database with associated script content."""
        if conn is None:
            conn = self.graph_ops.connection._get_connection()

        query = """
            INSERT INTO episodes (
                id, script_id, season_id, number, title, description,
                air_date, writer, director, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # Store file path in metadata
        metadata = episode.metadata.copy()
        metadata["source_file"] = str(file_path)
        metadata["fountain_source"] = script.fountain_source

        conn.execute(
            query,
            (
                str(episode.id),
                str(episode.script_id),
                str(episode.season_id),
                episode.number,
                episode.title,
                episode.description,
                episode.air_date.isoformat() if episode.air_date else None,
                episode.writer,
                episode.director,
                json.dumps(metadata),
            ),
        )

        # Save scenes associated with this episode
        for scene_id in script.scenes:
            self._update_scene_episode(
                str(scene_id), str(episode.id), str(episode.season_id), conn
            )

        return str(episode.id)

    def _save_standalone_script(
        self, script: Script, file_path: Path, conn: Any = None
    ) -> str:
        """Save a standalone script.

        Returns:
            Script ID
        """
        if conn is None:
            conn = self.graph_ops.connection._get_connection()

        script.source_file = str(file_path)
        return self._save_script_to_db(script, conn)

    def _update_scene_episode(
        self, scene_id: str, episode_id: str, season_id: str, conn: Any = None
    ) -> None:
        """Update scene to associate with episode."""
        if conn is None:
            conn = self.graph_ops.connection._get_connection()

        query = """
            UPDATE scenes SET episode_id = ?, season_id = ?
            WHERE id = ?
        """
        conn.execute(query, (episode_id, season_id, scene_id))

    def _get_script_node_id(self, script_id: str) -> str:
        """Get graph node ID for a script."""
        query = """
            SELECT id FROM nodes WHERE node_type = 'script' AND entity_id = ?
        """
        row = self.graph_ops.connection.fetch_one(query, (script_id,))
        return row["id"] if row else ""

    def _get_season_node_id(self, season_id: str) -> str:
        """Get graph node ID for a season."""
        query = """
            SELECT id FROM nodes WHERE node_type = 'season' AND entity_id = ?
        """
        row = self.graph_ops.connection.fetch_one(query, (season_id,))
        return row["id"] if row else ""

    def resume_import(
        self,
        progress_callback: Any = None,
    ) -> BulkImportResult | None:
        """Resume a previously interrupted import."""
        if not self._import_state:
            logger.warning("No import state found to resume")
            return None

        # Get files that need processing
        pending_files = []
        for file_path, file_info in self._import_state["files"].items():
            if file_info["status"] in [
                FileImportStatus.PENDING,
                FileImportStatus.RETRY_PENDING,
            ]:
                pending_files.append(Path(file_path))

        if not pending_files:
            logger.info("No pending files to import")
            return None

        logger.info(f"Resuming import with {len(pending_files)} pending files")
        return self.import_files(
            file_paths=pending_files,
            progress_callback=progress_callback,
        )

    def get_import_status(self) -> dict[str, Any] | None:
        """Get current import status from saved state."""
        if not self._import_state:
            return None

        status_counts: dict[str, int] = defaultdict(int)
        for file_info in self._import_state["files"].values():
            status_counts[file_info["status"]] += 1

        return {
            "started_at": self._import_state["started_at"],
            "updated_at": self._import_state["updated_at"],
            "total_files": self._import_state["total_files"],
            "status_counts": dict(status_counts),
            "series_imported": len(self._import_state["series_cache"]),
        }
