"""Bulk import functionality for fountain files.

This module provides functionality for importing multiple fountain files
at once, with support for TV series organization and progress tracking.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from scriptrag.config import get_logger
from scriptrag.database.operations import GraphOperations
from scriptrag.models import Episode, Script, Season

from . import FountainParser, FountainParsingError
from .series_detector import SeriesInfo, SeriesPatternDetector

logger = get_logger(__name__)


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

    def add_success(self, file_path: str, script_id: str) -> None:
        """Record a successful import."""
        self.successful_imports += 1
        self.imported_scripts[file_path] = script_id

    def add_failure(self, file_path: str, error: str) -> None:
        """Record a failed import."""
        self.failed_imports += 1
        self.errors[file_path] = error

    def add_skipped(self, file_path: str) -> None:
        """Record a skipped file."""
        del file_path  # Unused
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
        self._season_cache: dict[
            tuple[str, int], str
        ] = {}  # (script_id, season_num) -> season_id

    def import_files(
        self,
        file_paths: list[Path],
        series_name_override: str | None = None,
        dry_run: bool = False,
        progress_callback: Any = None,
    ) -> BulkImportResult:
        """Import multiple fountain files.

        Args:
            file_paths: List of fountain file paths
            series_name_override: Override auto-detected series name
            dry_run: Preview what would be imported without actually importing
            progress_callback: Optional callback for progress updates

        Returns:
            BulkImportResult with import statistics
        """
        result = BulkImportResult()
        result.total_files = len(file_paths)

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

    def _process_batch(
        self,
        series_name: str,
        batch: list[tuple[Path, SeriesInfo]],
        result: BulkImportResult,
    ) -> None:
        """Process a batch of files for a series."""
        del series_name  # Unused parameter
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

        # Store graph operations to perform after database operations
        script_operations: list[Script] = []
        season_operations: list[tuple[Season, str]] = []

        # Use a single transaction for all database operations for this file
        with self.graph_ops.connection.transaction() as conn:
            # Update script metadata based on series info
            if series_info.is_series:
                script.is_series = True
                script.title = series_info.series_name

                # Get or create series script
                series_script_id, series_script = self._get_or_create_series(
                    series_info.series_name, script, conn
                )

                # Store graph operations for series creation if needed
                if series_script:
                    script_operations.append(series_script)

                # Handle episodes
                if series_info.season_number is not None:
                    season_id, season_obj = self._create_episode_structure(
                        script, series_info, series_script_id, file_path, conn
                    )
                    # Store graph operations for later
                    if season_obj:
                        season_operations.append((season_obj, series_script_id))
            else:
                # Standalone script
                script_id = self._save_standalone_script(script, file_path, conn)
                script_operations.append(script)

        # Execute graph operations outside of transaction
        for script_obj in script_operations:
            if isinstance(script_obj, Script):
                self.graph_ops.create_script_graph(script_obj)

        for season_obj, script_id in season_operations:
            if isinstance(season_obj, Season):
                script_node_id = self._get_script_node_id(script_id)
                self.graph_ops.add_season_to_script(season_obj, script_node_id)

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
