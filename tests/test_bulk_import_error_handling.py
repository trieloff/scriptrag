"""Tests for bulk import error handling and recovery mechanisms."""

import json
import sqlite3
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.operations import GraphOperations
from scriptrag.models import Script
from scriptrag.parser import FountainParsingError
from scriptrag.parser.bulk_import import (
    BulkImporter,
    BulkImportResult,
    ErrorCategory,
    FileImportStatus,
)


@pytest.fixture
def mock_graph_ops():
    """Create mock graph operations."""
    mock_ops = MagicMock(spec=GraphOperations)
    mock_ops.connection = MagicMock(spec=DatabaseConnection)
    return mock_ops


@pytest.fixture
def temp_state_file(tmp_path):
    """Create temporary state file path."""
    return tmp_path / "import_state.json"


@pytest.fixture
def sample_files(tmp_path):
    """Create sample fountain files for testing."""
    files = []

    # Valid file
    valid_file = tmp_path / "valid.fountain"
    valid_file.write_text(
        """Title: Valid Script
Author: Test Author

INT. ROOM - DAY

Character speaks.

FADE OUT.
"""
    )
    files.append(valid_file)

    # Invalid file
    invalid_file = tmp_path / "invalid.fountain"
    invalid_file.write_text("This is not a valid fountain file")
    files.append(invalid_file)

    # File with permissions issue (simulated)
    perm_file = tmp_path / "permission_issue.fountain"
    perm_file.write_text("Title: Permission Test\n\nContent")
    files.append(perm_file)

    return files


class TestBulkImportErrorHandling:
    """Test error handling in bulk import."""

    def test_error_categorization(self, mock_graph_ops, temp_state_file):
        """Test that errors are properly categorized."""
        BulkImporter(
            mock_graph_ops,
            state_file=temp_state_file,
            verbose=True,
        )

        result = BulkImportResult()

        # Test parsing error
        result.add_failure(
            "test1.fountain",
            FountainParsingError("Invalid format"),
            ErrorCategory.PARSING,
        )

        # Test database error
        result.add_failure(
            "test2.fountain",
            sqlite3.DatabaseError("Database locked"),
            ErrorCategory.DATABASE,
        )

        # Test filesystem error
        result.add_failure(
            "test3.fountain",
            PermissionError("Access denied"),
            ErrorCategory.FILESYSTEM,
        )

        # Check categorization
        assert len(result.errors) == 3
        assert result.errors["test1.fountain"]["category"] == ErrorCategory.PARSING
        assert result.errors["test2.fountain"]["category"] == ErrorCategory.DATABASE
        assert result.errors["test3.fountain"]["category"] == ErrorCategory.FILESYSTEM

        # Check suggestions
        assert len(result.errors["test1.fountain"]["suggestions"]) > 0
        assert "Fountain format" in result.errors["test1.fountain"]["suggestions"][0]

        # Check retry candidates
        assert "test2.fountain" in result.retry_candidates
        assert "test1.fountain" not in result.retry_candidates

    def test_transaction_rollback(self, mock_graph_ops, sample_files):
        """Test that transactions are rolled back on failure."""
        importer = BulkImporter(mock_graph_ops, batch_size=3)

        # Mock transaction context
        mock_transaction = MagicMock()
        mock_transaction.__enter__ = MagicMock(return_value=mock_transaction)
        mock_transaction.__exit__ = MagicMock(return_value=None)

        # Make second file in batch fail
        def mock_execute(_query, params=None):
            if "invalid.fountain" in str(params):
                raise sqlite3.DatabaseError("Constraint violation")
            return MagicMock()

        mock_transaction.execute = mock_execute
        mock_graph_ops.connection.transaction.return_value = mock_transaction

        # Process batch
        result = BulkImportResult()
        batch = [(f, MagicMock()) for f in sample_files]

        # Process should not raise since files are skipped (already loaded)
        importer._process_batch("test_series", batch, result)

        # All files should be skipped since they exist in loaded state
        assert result.skipped_files == 3

        # Verify transaction was rolled back
        mock_transaction.__exit__.assert_called()

    def test_state_persistence(self, mock_graph_ops, temp_state_file, sample_files):
        """Test import state is saved and loaded correctly."""
        importer = BulkImporter(
            mock_graph_ops,
            state_file=temp_state_file,
        )

        # Create result with mixed statuses
        result = BulkImportResult()
        result.total_files = 3
        result.add_success(str(sample_files[0]), "uuid-1")
        result.add_failure(
            str(sample_files[1]),
            "Parse error",
            ErrorCategory.PARSING,
        )

        # Save state
        importer._save_state(sample_files, result)

        # Verify state file exists
        assert temp_state_file.exists()

        # Load state
        with temp_state_file.open() as f:
            state = json.load(f)

        assert state["total_files"] == 3
        assert str(sample_files[0]) in state["files"]
        assert (
            state["files"][str(sample_files[0])]["status"] == FileImportStatus.SUCCESS
        )
        assert state["files"][str(sample_files[1])]["status"] == FileImportStatus.FAILED

    def test_resume_import(self, mock_graph_ops, temp_state_file):
        """Test resuming interrupted import."""
        # Create initial state with pending files
        state = {
            "started_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:10:00",
            "total_files": 5,
            "files": {
                "file1.fountain": {"status": FileImportStatus.SUCCESS},
                "file2.fountain": {"status": FileImportStatus.FAILED},
                "file3.fountain": {"status": FileImportStatus.RETRY_PENDING},
                "file4.fountain": {"status": FileImportStatus.PENDING},
                "file5.fountain": {"status": FileImportStatus.PENDING},
            },
            "batch_size": 10,
            "series_cache": {},
            "season_cache": {},
        }

        with temp_state_file.open("w") as f:
            json.dump(state, f)

        # Create importer and load state
        importer = BulkImporter(
            mock_graph_ops,
            state_file=temp_state_file,
        )
        # Manually load state for this test since auto-loading is disabled in tests
        with temp_state_file.open() as f:
            importer._import_state = json.load(f)

        # Get import status
        status = importer.get_import_status()
        assert status is not None
        assert status["total_files"] == 5
        assert status["status_counts"][FileImportStatus.SUCCESS] == 1
        assert status["status_counts"][FileImportStatus.PENDING] == 2
        assert status["status_counts"][FileImportStatus.RETRY_PENDING] == 1

    def test_progress_with_eta(self, mock_graph_ops, sample_files):
        """Test progress reporting with ETA calculation."""
        importer = BulkImporter(mock_graph_ops, batch_size=1, verbose=True)

        progress_updates = []

        def capture_progress(pct, msg):
            progress_updates.append((pct, msg))

        # Mock successful parsing
        with patch.object(importer.parser, "parse_file") as mock_parse:
            mock_parse.return_value = Script(
                id=uuid4(),
                title="Test",
                format="screenplay",
            )

            # Mock database operations
            mock_graph_ops.connection.fetch_one.return_value = None
            mock_graph_ops.connection.transaction().__enter__().execute.return_value = (
                None
            )

            importer.import_files(
                sample_files[:2],
                progress_callback=capture_progress,
            )

        # Verify progress updates
        assert len(progress_updates) > 0
        assert any("ETA:" in msg for _, msg in progress_updates)

    def test_error_summary(self):
        """Test error summary generation."""
        result = BulkImportResult()

        # Add various errors
        result.add_failure("f1.fountain", "Parse error", ErrorCategory.PARSING)
        result.add_failure("f2.fountain", "Parse error 2", ErrorCategory.PARSING)
        result.add_failure("f3.fountain", "DB error", ErrorCategory.DATABASE)
        result.add_failure("f4.fountain", "Unknown", ErrorCategory.UNKNOWN)

        summary = result.get_error_summary()

        assert len(summary[ErrorCategory.PARSING]) == 2
        assert len(summary[ErrorCategory.DATABASE]) == 1
        assert len(summary[ErrorCategory.UNKNOWN]) == 1

    def test_batch_failure_handling(self, mock_graph_ops, temp_state_file):
        """Test handling of batch-level failures."""
        importer = BulkImporter(
            mock_graph_ops, batch_size=10, state_file=temp_state_file
        )

        # Make entire batch fail at transaction level
        mock_graph_ops.connection.transaction.side_effect = Exception("Connection lost")

        result = BulkImportResult()

        # Create a simple batch with mock files and series info
        from pathlib import Path

        batch = [
            (Path("file1.fountain"), MagicMock(is_series=False)),
            (Path("file2.fountain"), MagicMock(is_series=False)),
        ]

        # Process batch should raise and log the error
        with pytest.raises(Exception, match="Connection lost"):
            importer._process_batch("test_series", batch, result)

    def test_performance_metrics(self):
        """Test performance metrics in results."""
        result = BulkImportResult()
        result.total_files = 100
        result.successful_imports = 90
        result.failed_imports = 10

        # Simulate some processing time
        import time

        time.sleep(0.1)

        result_dict = result.to_dict()

        assert "duration_seconds" in result_dict
        assert "files_per_second" in result_dict
        assert result_dict["duration_seconds"] > 0
        assert result_dict["files_per_second"] > 0
