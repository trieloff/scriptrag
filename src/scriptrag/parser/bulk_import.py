"""Bulk import functionality for fountain files.

This module provides functionality for importing multiple fountain files
at once, with support for TV series organization and progress tracking.
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from scriptrag.config import get_logger
from scriptrag.database.operations import GraphOperations
from scriptrag.models import Episode, Script, Season

from . import FountainParser, FountainParsingError
from .series_detector import SeriesInfo, SeriesPatternDetector

logger = get_logger(__name__)

# Validation constants
MAX_FILE_SIZE_MB = 50  # Maximum file size in megabytes
VALID_EXTENSIONS = {".fountain", ".txt", ".fountain.txt"}
SUPPORTED_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "iso-8859-1", "windows-1252"]

# Basic fountain format patterns for quick validation
FOUNTAIN_MARKERS = {
    # Scene headings
    re.compile(r"^(INT\.|EXT\.|EST\.|INT\./EXT\.|I/E\.)", re.IGNORECASE | re.MULTILINE),
    # Character names (all caps line followed by dialogue)
    re.compile(r"^[A-Z][A-Z\s\(\)\.]+$\n^[^\n]+$", re.MULTILINE),
    # Transitions
    re.compile(
        r"^(CUT TO:|FADE IN:|FADE OUT:|FADE TO BLACK)", re.IGNORECASE | re.MULTILINE
    ),
    # Title page markers
    re.compile(
        r"^(Title:|Author:|Draft:|Contact:|Credit:)", re.IGNORECASE | re.MULTILINE
    ),
}


@dataclass
class ValidationIssue:
    """Represents a validation issue found during pre-import checks."""

    file_path: str
    issue_type: str  # "error" or "warning"
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class FileValidationResult:
    """Results from validating a single file."""

    file_path: str
    is_valid: bool
    file_exists: bool = True
    file_size_mb: float = 0.0
    detected_encoding: str | None = None
    has_valid_extension: bool = True
    appears_to_be_fountain: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)
    estimated_import_time_seconds: float = 0.0

    def add_error(self, message: str, **details: Any) -> None:
        """Add an error validation issue."""
        self.issues.append(
            ValidationIssue(
                file_path=self.file_path,
                issue_type="error",
                message=message,
                details=details,
            )
        )
        self.is_valid = False

    def add_warning(self, message: str, **details: Any) -> None:
        """Add a warning validation issue."""
        self.issues.append(
            ValidationIssue(
                file_path=self.file_path,
                issue_type="warning",
                message=message,
                details=details,
            )
        )


@dataclass
class SeriesValidationResult:
    """Results from validating series detection."""

    series_structure: dict[str, dict[str, Any]] = field(default_factory=dict)
    duplicate_episodes: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_patterns: list[str] = field(default_factory=list)
    regex_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BulkImportResult:
    """Results from a bulk import operation."""

    def __init__(self) -> None:
        """Initialize import results."""
        self.total_files = 0
        self.successful_imports = 0
        self.failed_imports = 0
        self.skipped_files = 0
        self.errors: dict[str, str] = {}
        self.imported_scripts: dict[str, str] = {}  # path -> script_id
        self.series_created: dict[str, str] = {}  # series_name -> script_id

        # Validation results
        self.validation_results: dict[str, FileValidationResult] = {}
        self.series_validation: SeriesValidationResult | None = None
        self.total_estimated_time_seconds: float = 0.0

    def add_success(self, file_path: str, script_id: str) -> None:
        """Record a successful import."""
        self.successful_imports += 1
        self.imported_scripts[file_path] = script_id

    def add_failure(self, file_path: str, error: str) -> None:
        """Record a failed import."""
        self.failed_imports += 1
        self.errors[file_path] = error

    def add_skipped(self, _file_path: str) -> None:
        """Record a skipped file."""
        self.skipped_files += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert results to dictionary."""
        return {
            "total_files": self.total_files,
            "successful_imports": self.successful_imports,
            "failed_imports": self.failed_imports,
            "skipped_files": self.skipped_files,
            "errors": self.errors,
            "imported_scripts": self.imported_scripts,
            "series_created": self.series_created,
        }


class BulkImporter:
    """Handles bulk import of fountain files with TV series support."""

    def __init__(
        self,
        graph_ops: GraphOperations,
        custom_pattern: str | None = None,
        skip_existing: bool = True,
        update_existing: bool = False,
        batch_size: int = 10,
    ) -> None:
        """Initialize bulk importer.

        Args:
            graph_ops: Graph operations instance
            custom_pattern: Custom regex pattern for series detection
            skip_existing: Skip files that already exist in database
            update_existing: Update existing scripts if file is newer
            batch_size: Number of files to process per transaction batch
        """
        self.graph_ops = graph_ops
        self.parser = FountainParser()
        self.series_detector = SeriesPatternDetector(custom_pattern)
        self.skip_existing = skip_existing
        self.update_existing = update_existing
        self.batch_size = batch_size

        # Cache for series and season IDs
        self._series_cache: dict[str, str] = {}  # series_name -> script_id
        # (script_id, season_num) -> season_id
        self._season_cache: dict[tuple[str, int], str] = {}

    def validate_files(
        self, file_paths: list[Path], custom_pattern: str | None = None
    ) -> tuple[dict[str, FileValidationResult], SeriesValidationResult]:
        """Validate files before import.

        Args:
            file_paths: List of fountain file paths to validate
            custom_pattern: Optional custom regex pattern for series detection

        Returns:
            Tuple of (file validation results, series validation result)
        """
        file_results = {}

        # Validate each file
        for file_path in file_paths:
            file_results[str(file_path)] = self._validate_single_file(file_path)

        # Validate series detection
        series_validation = self._validate_series_detection(file_paths, custom_pattern)

        return file_results, series_validation

    def _validate_single_file(self, file_path: Path) -> FileValidationResult:
        """Validate a single file."""
        result = FileValidationResult(file_path=str(file_path), is_valid=True)

        # Check file existence
        if not file_path.exists():
            result.file_exists = False
            result.add_error("File does not exist")
            return result

        # Check file extension
        suffix = file_path.suffix.lower()
        full_suffix = "".join(file_path.suffixes).lower()

        if suffix not in VALID_EXTENSIONS and full_suffix not in VALID_EXTENSIONS:
            result.has_valid_extension = False
            result.add_error(
                f"Invalid file extension: {suffix}",
                valid_extensions=list(VALID_EXTENSIONS),
            )

        # Check file size
        try:
            file_size_bytes = file_path.stat().st_size
            result.file_size_mb = file_size_bytes / (1024 * 1024)

            if result.file_size_mb > MAX_FILE_SIZE_MB:
                result.add_warning(
                    f"File is very large: {result.file_size_mb:.1f} MB",
                    max_size_mb=MAX_FILE_SIZE_MB,
                )

            # Estimate import time (rough estimate: 1MB/second + overhead)
            result.estimated_import_time_seconds = max(1.0, result.file_size_mb) + 0.5

        except OSError as e:
            result.add_error(f"Cannot read file size: {e}")

        # Detect encoding and validate content
        if result.file_exists:
            encoding_result = self._detect_encoding(file_path)
            result.detected_encoding = encoding_result["encoding"]

            if encoding_result["error"]:
                result.add_error(
                    f"Encoding detection failed: {encoding_result['error']}"
                )
            elif encoding_result["encoding"] not in SUPPORTED_ENCODINGS:
                result.add_warning(
                    f"Unusual encoding detected: {encoding_result['encoding']}",
                    supported_encodings=SUPPORTED_ENCODINGS,
                )

            # Quick content validation
            if encoding_result["content"]:
                fountain_check = self._quick_fountain_check(encoding_result["content"])
                result.appears_to_be_fountain = fountain_check["is_fountain"]

                if not fountain_check["is_fountain"]:
                    result.add_warning(
                        "File does not appear to be in Fountain format",
                        markers_found=fountain_check["markers_found"],
                    )

        return result

    def _detect_encoding(self, file_path: Path) -> dict[str, Any]:
        """Detect file encoding and read sample content."""
        result: dict[str, Any] = {"encoding": None, "content": None, "error": None}

        # Try encodings in order of likelihood
        for encoding in SUPPORTED_ENCODINGS:
            try:
                with file_path.open(encoding=encoding) as f:
                    # Read first 10KB for validation
                    content = f.read(10240)
                    result["encoding"] = encoding
                    result["content"] = content
                    return result
            except (UnicodeDecodeError, UnicodeError):
                continue
            except OSError as e:
                result["error"] = str(e)
                return result

        # If no encoding worked
        result["error"] = "Could not detect valid encoding"
        return result

    def _quick_fountain_check(self, content: str) -> dict[str, Any]:
        """Quick check if content appears to be fountain format."""
        markers_found = []

        for pattern in FOUNTAIN_MARKERS:
            if pattern.search(content):
                markers_found.append(pattern.pattern[:20] + "...")

        # Consider it fountain if we find at least 2 markers
        return {
            "is_fountain": len(markers_found) >= 2,
            "markers_found": markers_found,
        }

    def _validate_series_detection(
        self, file_paths: list[Path], custom_pattern: str | None = None
    ) -> SeriesValidationResult:
        """Validate series detection patterns and results."""
        result = SeriesValidationResult()

        # Validate custom pattern if provided
        if custom_pattern:
            try:
                re.compile(custom_pattern)
            except re.error as e:
                result.regex_errors.append(f"Invalid custom pattern: {e}")
                return result

        # Use a temporary detector for validation
        detector = SeriesPatternDetector(custom_pattern)
        series_infos = detector.detect_bulk(file_paths)
        grouped = detector.group_by_series(series_infos)

        # Build series structure
        for series_name, episodes in grouped.items():
            series_data: dict[str, Any] = {
                "episode_count": len(episodes),
                "seasons": {},
                "standalone_count": 0,
                "specials_count": 0,
            }

            # Check for duplicate episodes
            seen_episodes: dict[tuple[int, int], list[Path]] = {}

            for path, info in episodes:
                if info.is_special:
                    series_data["specials_count"] += 1
                elif info.season_number is None:
                    series_data["standalone_count"] += 1
                else:
                    season = info.season_number
                    if season not in series_data["seasons"]:
                        series_data["seasons"][season] = {
                            "episode_count": 0,
                            "episodes": [],
                        }

                    series_data["seasons"][season]["episode_count"] += 1

                    if info.episode_number is not None:
                        episode_key = (season, info.episode_number)
                        if episode_key not in seen_episodes:
                            seen_episodes[episode_key] = []
                        seen_episodes[episode_key].append(path)

                        series_data["seasons"][season]["episodes"].append(
                            {
                                "number": info.episode_number,
                                "title": info.episode_title,
                                "file": path.name,
                            }
                        )

            # Check for duplicates
            for (season, episode), paths in seen_episodes.items():
                if len(paths) > 1:
                    result.duplicate_episodes.append(
                        {
                            "series": series_name,
                            "season": season,
                            "episode": episode,
                            "files": [str(p) for p in paths],
                        }
                    )

            result.series_structure[series_name] = series_data

        # Check for ambiguous patterns
        if len(result.series_structure) > 5:
            result.warnings.append(
                f"Detected {len(result.series_structure)} different series. "
                "Consider using more specific file naming patterns."
            )

        return result

    def import_files(
        self,
        file_paths: list[Path],
        series_name_override: str | None = None,
        dry_run: bool = False,
        progress_callback: Any = None,
        validate_first: bool = True,
    ) -> BulkImportResult:
        """Import multiple fountain files.

        Args:
            file_paths: List of fountain file paths
            series_name_override: Override auto-detected series name
            dry_run: Preview what would be imported without actually importing
            progress_callback: Optional callback for progress updates
            validate_first: Run validation before import (default: True)

        Returns:
            BulkImportResult with import statistics
        """
        result = BulkImportResult()
        result.total_files = len(file_paths)

        # Validate files first if requested
        if validate_first:
            logger.info(f"Validating {len(file_paths)} files before import")
            file_validations, series_validation = self.validate_files(
                file_paths, self.series_detector.custom_pattern
            )
            result.validation_results = file_validations
            result.series_validation = series_validation

            # Calculate total estimated time
            result.total_estimated_time_seconds = sum(
                v.estimated_import_time_seconds
                for v in file_validations.values()
                if v.is_valid
            )

            # Filter out invalid files
            valid_paths = [
                Path(path)
                for path, validation in file_validations.items()
                if validation.is_valid
            ]

            if len(valid_paths) < len(file_paths):
                logger.warning(
                    f"Skipping {len(file_paths) - len(valid_paths)} invalid files"
                )
                file_paths = valid_paths

        # Detect series information for all files
        logger.info(f"Detecting series patterns in {len(file_paths)} files")
        series_infos = self.series_detector.detect_bulk(file_paths)

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
        for series_name, episodes in grouped.items():
            logger.info(f"Processing series: {series_name} ({len(episodes)} files)")

            # Process in batches
            for i in range(0, len(episodes), self.batch_size):
                batch = episodes[i : i + self.batch_size]
                self._process_batch(series_name, batch, result)

                # Progress callback
                if progress_callback:
                    progress = (i + len(batch)) / len(file_paths)
                    progress_callback(progress, f"Processing {series_name}...")

        return result

    def _dry_run_preview(
        self,
        grouped: dict[str, list[tuple[Path, SeriesInfo]]],
        result: BulkImportResult,
    ) -> BulkImportResult:
        """Preview what would be imported without actually importing."""
        logger.info("DRY RUN: Previewing import operations")

        # Show validation summary if available
        if result.validation_results:
            valid_count = sum(
                1 for v in result.validation_results.values() if v.is_valid
            )
            invalid_count = len(result.validation_results) - valid_count
            warning_count = sum(
                1 for v in result.validation_results.values() if v.is_valid and v.issues
            )

            logger.info("\nValidation Summary:")
            logger.info(f"  Total files: {len(result.validation_results)}")
            logger.info(f"  Valid files: {valid_count}")
            logger.info(f"  Invalid files: {invalid_count}")
            logger.info(f"  Files with warnings: {warning_count}")

            if result.total_estimated_time_seconds > 0:
                minutes = result.total_estimated_time_seconds / 60
                logger.info(f"  Estimated import time: {minutes:.1f} minutes")

            # Show validation errors
            if invalid_count > 0:
                logger.info("\n  Validation Errors:")
                for path, validation in result.validation_results.items():
                    if not validation.is_valid:
                        logger.error(f"    {Path(path).name}:")
                        for issue in validation.issues:
                            if issue.issue_type == "error":
                                logger.error(f"      - {issue.message}")

            # Show validation warnings
            if warning_count > 0:
                logger.info("\n  Validation Warnings:")
                shown = 0
                for path, validation in result.validation_results.items():
                    if validation.is_valid and validation.issues and shown < 5:
                        logger.warning(f"    {Path(path).name}:")
                        for issue in validation.issues:
                            if issue.issue_type == "warning":
                                logger.warning(f"      - {issue.message}")
                        shown += 1
                if warning_count > 5:
                    logger.warning(
                        f"    ... and {warning_count - 5} more files with warnings"
                    )

        # Show series detection summary
        if result.series_validation:
            sv = result.series_validation
            if sv.duplicate_episodes:
                logger.warning("\n  Duplicate Episodes Detected:")
                for dup in sv.duplicate_episodes[:3]:
                    logger.warning(
                        f"    {dup['series']} S{dup['season']}E{dup['episode']}: "
                        f"{', '.join(Path(f).name for f in dup['files'])}"
                    )
                if len(sv.duplicate_episodes) > 3:
                    logger.warning(
                        f"    ... and {len(sv.duplicate_episodes) - 3} more duplicates"
                    )

            if sv.warnings:
                logger.warning("\n  Series Detection Warnings:")
                for warning in sv.warnings:
                    logger.warning(f"    - {warning}")

        logger.info("\nSeries Structure Preview:")
        for series_name, episodes in grouped.items():
            logger.info(f"\n{series_name}:")

            # Group by season
            by_season = defaultdict(list)
            standalone = []

            for file_path, info in episodes:
                if info.season_number is not None:
                    by_season[info.season_number].append((file_path, info))
                else:
                    standalone.append((file_path, info))

            # Log season structure
            for season_num in sorted(by_season.keys()):
                season_episodes = by_season[season_num]
                logger.info(f"  Season {season_num}: {len(season_episodes)} episodes")
                for file_path, info in season_episodes[:3]:  # Show first 3
                    ep_str = (
                        f"Episode {info.episode_number}"
                        if info.episode_number
                        else "Special"
                    )
                    title = info.episode_title or "Untitled"
                    logger.info(f"    {ep_str}: {title} ({file_path.name})")
                if len(season_episodes) > 3:
                    logger.info(f"    ... and {len(season_episodes) - 3} more")

            if standalone:
                logger.info(f"  Standalone scripts: {len(standalone)}")
                for file_path, info in standalone[:3]:
                    logger.info(f"    {info.episode_title or file_path.name}")
                if len(standalone) > 3:
                    logger.info(f"    ... and {len(standalone) - 3} more")

        return result

    def _process_batch(
        self,
        _series_name: str,
        batch: list[tuple[Path, SeriesInfo]],
        result: BulkImportResult,
    ) -> None:
        """Process a batch of files for a series."""
        # Process each file individually without batch transaction
        # Each file import will handle its own transactions
        for file_path, series_info in batch:
            try:
                self._import_single_file(file_path, series_info, result)
            except Exception as e:
                logger.error(f"Failed to import {file_path}: {e}")
                result.add_failure(str(file_path), str(e))

    def _import_single_file(
        self, file_path: Path, series_info: SeriesInfo, result: BulkImportResult
    ) -> None:
        """Import a single fountain file."""
        logger.debug(f"Importing {file_path}")

        # Check if file already exists
        if self.skip_existing and self._file_exists(file_path):
            logger.debug(f"Skipping existing file: {file_path}")
            result.add_skipped(str(file_path))
            return

        # Parse the fountain file
        try:
            script = self.parser.parse_file(file_path)
        except FountainParsingError as e:
            raise ImportError(f"Failed to parse {file_path}: {e}") from e

        # Store operations to track for rollback if needed
        created_scripts: list[tuple[str, Script]] = []  # (script_id, script_obj)
        created_seasons: list[tuple[str, Season]] = []  # (script_id, season_obj)

        try:
            # Use a single transaction for all database operations
            with self.graph_ops.connection.transaction() as conn:
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

            # Now create graph operations after database transaction commits
            # This ensures database consistency even if graph operations fail
            for script_id, script_obj in created_scripts:
                try:
                    self.graph_ops.create_script_graph(script_obj)
                except Exception as graph_error:
                    logger.error(
                        f"Failed to create graph for script {script_id}: {graph_error}"
                    )
                    # Continue with other operations

            for script_id, season_obj in created_seasons:
                try:
                    script_node_id = self._get_script_node_id(script_id)
                    self.graph_ops.add_season_to_script(season_obj, script_node_id)
                except Exception as graph_error:
                    logger.error(
                        f"Failed to add season to graph for "
                        f"script {script_id}: {graph_error}"
                    )
                    # Continue with other operations

        except Exception as e:
            # Database transaction will be rolled back automatically
            raise ImportError(f"Failed to import {file_path}: {e}") from e

        result.add_success(str(file_path), str(script.id))

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
