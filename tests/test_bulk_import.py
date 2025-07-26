"""Tests for bulk import functionality."""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.operations import GraphOperations
from scriptrag.database.schema import create_database
from scriptrag.models import Script
from scriptrag.parser.bulk_import import BulkImporter, BulkImportResult


class TestBulkImportResult:
    """Test cases for BulkImportResult."""

    def test_initialization(self) -> None:
        """Test BulkImportResult initialization."""
        result = BulkImportResult()
        assert result.total_files == 0
        assert result.successful_imports == 0
        assert result.failed_imports == 0
        assert result.skipped_files == 0
        assert result.errors == {}
        assert result.imported_scripts == {}
        assert result.series_created == {}

    def test_add_success(self) -> None:
        """Test recording successful imports."""
        result = BulkImportResult()
        result.add_success("file1.fountain", "script-id-1")
        result.add_success("file2.fountain", "script-id-2")

        assert result.successful_imports == 2
        assert result.imported_scripts["file1.fountain"] == "script-id-1"
        assert result.imported_scripts["file2.fountain"] == "script-id-2"

    def test_add_failure(self) -> None:
        """Test recording failed imports."""
        result = BulkImportResult()
        result.add_failure("file1.fountain", "Parse error")
        result.add_failure("file2.fountain", "Database error")

        assert result.failed_imports == 2
        assert result.errors["file1.fountain"] == "Parse error"
        assert result.errors["file2.fountain"] == "Database error"

    def test_add_skipped(self) -> None:
        """Test recording skipped files."""
        result = BulkImportResult()
        result.add_skipped("file1.fountain")
        result.add_skipped("file2.fountain")

        assert result.skipped_files == 2

    def test_to_dict(self) -> None:
        """Test converting results to dictionary."""
        result = BulkImportResult()
        result.total_files = 5
        result.add_success("file1.fountain", "id1")
        result.add_failure("file2.fountain", "error")
        result.add_skipped("file3.fountain")

        data = result.to_dict()
        assert data["total_files"] == 5
        assert data["successful_imports"] == 1
        assert data["failed_imports"] == 1
        assert data["skipped_files"] == 1
        assert "file1.fountain" in data["imported_scripts"]
        assert "file2.fountain" in data["errors"]


class TestBulkImporter:
    """Test cases for BulkImporter."""

    @pytest.fixture
    def temp_db(self) -> Path:
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = Path(tmp.name)

        # Initialize schema
        create_database(db_path)
        yield db_path

        # Cleanup
        db_path.unlink(missing_ok=True)

    @pytest.fixture
    def importer(self, temp_db: Path) -> BulkImporter:
        """Create a BulkImporter instance for testing."""
        conn = DatabaseConnection(temp_db)
        graph_ops = GraphOperations(conn)
        importer = BulkImporter(graph_ops)
        yield importer
        # Close connection to allow file deletion on Windows
        conn.close()

    def test_initialization(self, importer: BulkImporter) -> None:
        """Test BulkImporter initialization."""
        assert importer.skip_existing is True
        assert importer.update_existing is False
        assert importer.batch_size == 10
        assert importer._series_cache == {}
        assert importer._season_cache == {}

    def test_dry_run_preview(self, importer: BulkImporter) -> None:
        """Test dry run preview mode."""
        # Create mock files
        files = [
            Path("BreakingBad_S01E01_Pilot.fountain"),
            Path("BreakingBad_S01E02_CatsInTheBag.fountain"),
            Path("TheWire_S01E01_TheTarget.fountain"),
        ]

        with patch.object(importer.parser, "parse_file") as mock_parse:
            result = importer.import_files(files, dry_run=True)

        # Should not actually parse files in dry run
        mock_parse.assert_not_called()

        # Should still set total files
        assert result.total_files == 3
        assert result.successful_imports == 0
        assert result.failed_imports == 0

    def test_import_single_standalone_script(self, importer: BulkImporter) -> None:
        """Test importing a single standalone script."""
        # Create a mock fountain file
        file_path = Path("MyScript.fountain")

        # Mock the parser
        mock_script = Script(
            title="My Script",
            fountain_source="EXT. LOCATION - DAY",
            source_file=str(file_path),
        )

        with (
            patch.object(importer.parser, "parse_file", return_value=mock_script),
            patch.object(
                importer, "_save_script_to_db", return_value=str(mock_script.id)
            ),
            patch.object(importer.graph_ops, "create_script_graph"),
        ):
            result = importer.import_files([file_path])

        assert result.successful_imports == 1
        assert result.failed_imports == 0
        assert str(file_path) in result.imported_scripts

    def test_import_tv_series_episodes(self, importer: BulkImporter) -> None:
        """Test importing TV series episodes."""
        files = [
            Path("BreakingBad_S01E01_Pilot.fountain"),
            Path("BreakingBad_S01E02_CatsInTheBag.fountain"),
        ]

        # Mock the parser and database operations
        def mock_parse(file_path: Path) -> Script:
            return Script(
                title="Breaking Bad",
                fountain_source=f"Content of {file_path.name}",
                source_file=str(file_path),
                is_series=True,
            )

        with (
            patch.object(importer.parser, "parse_file", side_effect=mock_parse),
            patch.object(
                importer,
                "_save_script_to_db",
                return_value="550e8400-e29b-41d4-a716-446655440000",
            ) as mock_save_script,
            patch.object(
                importer,
                "_save_season_to_db",
                return_value="550e8400-e29b-41d4-a716-446655440001",
            ) as mock_save_season,
            patch.object(
                importer,
                "_save_episode_to_db",
                return_value="550e8400-e29b-41d4-a716-446655440002",
            ) as mock_save_episode,
            patch.object(importer.graph_ops, "create_script_graph"),
            patch.object(importer.graph_ops, "add_season_to_script"),
            patch.object(importer.graph_ops, "add_episode_to_season"),
            patch.object(importer, "_get_script_node_id", return_value="node-1"),
            patch.object(importer, "_get_season_node_id", return_value="node-2"),
        ):
            result = importer.import_files(files)

        assert result.successful_imports == 2
        assert result.failed_imports == 0

        # Should create series and season
        mock_save_script.assert_called()
        mock_save_season.assert_called()

        # Should create 2 episodes
        assert mock_save_episode.call_count == 2

    def test_skip_existing_files(self, importer: BulkImporter) -> None:
        """Test skipping files that already exist."""
        file_path = Path("existing.fountain")

        # Mock file exists check
        with patch.object(importer, "_file_exists", return_value=True):
            result = importer.import_files([file_path])

        assert result.skipped_files == 1
        assert result.successful_imports == 0

    def test_error_handling(self, importer: BulkImporter) -> None:
        """Test error handling during import."""
        files = [
            Path("good.fountain"),
            Path("bad.fountain"),
        ]

        def mock_parse(file_path: Path) -> Script:
            if "bad" in str(file_path):
                raise Exception("Parse error")
            return Script(title="Good Script", source_file=str(file_path))

        with (
            patch.object(importer.parser, "parse_file", side_effect=mock_parse),
            patch.object(importer, "_save_standalone_script"),
        ):
            result = importer.import_files(files)

        assert result.successful_imports == 1
        assert result.failed_imports == 1
        assert "bad.fountain" in result.errors

    def test_batch_processing(self, importer: BulkImporter) -> None:
        """Test batch processing of files."""
        # Create importer with small batch size
        importer.batch_size = 2

        files = [Path(f"script{i}.fountain") for i in range(5)]

        batch_count = 0

        def mock_process_batch(*args: Any, **kwargs: Any) -> None:
            del args, kwargs  # Unused
            nonlocal batch_count
            batch_count += 1

        with (
            patch.object(importer, "_process_batch", side_effect=mock_process_batch),
            patch.object(
                importer.series_detector,
                "detect_bulk",
                return_value={
                    f: MagicMock(is_series=False, series_name=f"script{i}")
                    for i, f in enumerate(files)
                },
            ),
            patch.object(
                importer.series_detector,
                "group_by_series",
                return_value={"scripts": [(f, MagicMock()) for f in files]},
            ),
        ):
            importer.import_files(files)

        # Should process in 3 batches (2 + 2 + 1)
        assert batch_count == 3

    def test_series_name_override(self, importer: BulkImporter) -> None:
        """Test overriding auto-detected series name."""
        files = [
            Path("show_S01E01.fountain"),
            Path("show_S01E02.fountain"),
        ]

        # Mock series detection
        mock_infos = {}
        for i, f in enumerate(files):
            info = MagicMock()
            info.is_series = True
            info.series_name = "Auto Detected"
            info.season_number = 1
            info.episode_number = i + 1
            mock_infos[f] = info

        with (
            patch.object(
                importer.series_detector, "detect_bulk", return_value=mock_infos
            ),
            patch.object(importer, "_dry_run_preview"),
        ):
            importer.import_files(
                files, series_name_override="My Override", dry_run=True
            )

        # Check that series names were overridden
        for info in mock_infos.values():
            assert info.series_name == "My Override"

    def test_progress_callback(self, importer: BulkImporter) -> None:
        """Test progress callback functionality."""
        files = [Path(f"script{i}.fountain") for i in range(3)]

        progress_calls = []

        def progress_callback(pct: float, msg: str) -> None:
            progress_calls.append((pct, msg))

        with (
            patch.object(importer, "_process_batch"),
            patch.object(
                importer.series_detector,
                "detect_bulk",
                return_value={
                    f: MagicMock(is_series=False, series_name=f.stem) for f in files
                },
            ),
            patch.object(
                importer.series_detector,
                "group_by_series",
                return_value={"scripts": [(f, MagicMock()) for f in files]},
            ),
        ):
            importer.import_files(files, progress_callback=progress_callback)

        # Should have received progress updates
        assert len(progress_calls) > 0

        # Final progress should be 100%
        final_pct = progress_calls[-1][0]
        assert final_pct == 1.0

    def test_cache_functionality(self, importer: BulkImporter) -> None:
        """Test series and season caching."""
        # Add to cache
        importer._series_cache["Breaking Bad"] = "series-id-1"
        importer._season_cache[("series-id-1", 1)] = "season-id-1"

        # Mock database queries
        with patch.object(importer.graph_ops.connection, "fetch_one") as mock_fetch:
            # Should use cache instead of querying
            series_id, series_obj = importer._get_or_create_series(
                "Breaking Bad", Mock()
            )
            season_id, season_obj = importer._get_or_create_season("series-id-1", 1)

        assert series_id == "series-id-1"
        assert series_obj is None  # Retrieved from cache, no new object created
        assert season_id == "season-id-1"
        assert season_obj is None  # Retrieved from cache, no new object created

        # Should not have queried database
        mock_fetch.assert_not_called()
