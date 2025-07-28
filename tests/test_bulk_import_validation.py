"""Tests for bulk import validation functionality."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scriptrag.database.operations import GraphOperations
from scriptrag.parser.bulk_import import (
    BulkImporter,
    FileValidationResult,
    SeriesValidationResult,
    ValidationIssue,
)
from scriptrag.parser.series_detector import SeriesPatternDetector


class TestFileValidationResult:
    """Test cases for FileValidationResult."""

    def test_initialization(self) -> None:
        """Test FileValidationResult initialization."""
        result = FileValidationResult(file_path="/test/file.fountain", is_valid=True)
        assert result.file_path == "/test/file.fountain"
        assert result.is_valid is True
        assert result.file_exists is True
        assert result.file_size_mb == 0.0
        assert result.detected_encoding is None
        assert result.has_valid_extension is True
        assert result.appears_to_be_fountain is True
        assert result.issues == []
        assert result.estimated_import_time_seconds == 0.0

    def test_add_error(self) -> None:
        """Test adding error validation issues."""
        result = FileValidationResult(file_path="/test/file.txt", is_valid=True)
        result.add_error("File not found", path="/test/file.txt")

        assert result.is_valid is False
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "error"
        assert result.issues[0].message == "File not found"
        assert result.issues[0].details == {"path": "/test/file.txt"}

    def test_add_warning(self) -> None:
        """Test adding warning validation issues."""
        result = FileValidationResult(file_path="/test/file.fountain", is_valid=True)
        result.add_warning("Large file size", size_mb=75.5)

        assert result.is_valid is True  # Warnings don't invalidate
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "warning"
        assert result.issues[0].message == "Large file size"
        assert result.issues[0].details == {"size_mb": 75.5}


class TestValidationIssue:
    """Test cases for ValidationIssue."""

    def test_initialization(self) -> None:
        """Test ValidationIssue initialization."""
        issue = ValidationIssue(
            file_path="/test/file.fountain",
            issue_type="error",
            message="Invalid format",
            details={"line": 42},
        )
        assert issue.file_path == "/test/file.fountain"
        assert issue.issue_type == "error"
        assert issue.message == "Invalid format"
        assert issue.details == {"line": 42}


class TestSeriesValidationResult:
    """Test cases for SeriesValidationResult."""

    def test_initialization(self) -> None:
        """Test SeriesValidationResult initialization."""
        result = SeriesValidationResult()
        assert result.series_structure == {}
        assert result.duplicate_episodes == []
        assert result.ambiguous_patterns == []
        assert result.regex_errors == []
        assert result.warnings == []


class TestBulkImporterValidation:
    """Test cases for BulkImporter validation methods."""

    @pytest.fixture
    def mock_graph_ops(self) -> Mock:
        """Create mock GraphOperations."""
        mock = Mock(spec=GraphOperations)
        mock.connection = Mock()
        return mock

    @pytest.fixture
    def importer(self, mock_graph_ops: Mock) -> BulkImporter:
        """Create a BulkImporter instance for testing."""
        return BulkImporter(mock_graph_ops)

    def test_validate_single_file_not_exists(self, importer: BulkImporter) -> None:
        """Test validating a non-existent file."""
        file_path = Path("/nonexistent/file.fountain")
        result = importer._validate_single_file(file_path)

        assert result.file_exists is False
        assert result.is_valid is False
        assert len(result.issues) == 1
        assert result.issues[0].message == "File does not exist"

    def test_validate_single_file_invalid_extension(
        self, importer: BulkImporter
    ) -> None:
        """Test validating a file with invalid extension."""
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
            file_path = Path(tmp.name)
            tmp.write(b"test content")

        try:
            result = importer._validate_single_file(file_path)

            assert result.has_valid_extension is False
            assert result.is_valid is False
            assert any(
                "Invalid file extension" in issue.message for issue in result.issues
            )
        finally:
            file_path.unlink(missing_ok=True)

    def test_validate_single_file_valid_fountain(self, importer: BulkImporter) -> None:
        """Test validating a valid fountain file."""
        fountain_content = """Title: Test Script
Author: Test Author

INT. OFFICE - DAY

JOHN enters the room.

JOHN
Hello, world!

CUT TO:
"""
        with tempfile.NamedTemporaryFile(
            suffix=".fountain", delete=False, mode="w", encoding="utf-8"
        ) as tmp:
            tmp.write(fountain_content)
            file_path = Path(tmp.name)

        try:
            result = importer._validate_single_file(file_path)

            assert result.file_exists is True
            assert result.is_valid is True
            assert result.has_valid_extension is True
            assert result.appears_to_be_fountain is True
            assert result.detected_encoding == "utf-8"
            assert result.file_size_mb > 0
            assert result.estimated_import_time_seconds > 0
            assert len(result.issues) == 0
        finally:
            file_path.unlink(missing_ok=True)

    def test_validate_single_file_large_size(self, importer: BulkImporter) -> None:
        """Test validating a large file."""
        # Create a file that appears large
        with tempfile.NamedTemporaryFile(
            suffix=".fountain", delete=False, mode="w"
        ) as tmp:
            # Write minimal content
            tmp.write("INT. LOCATION - DAY\n\nSome action.")
            file_path = Path(tmp.name)

        try:
            # Mock the file size check
            with patch.object(Path, "stat") as mock_stat:
                mock_stat.return_value.st_size = 60 * 1024 * 1024  # 60MB
                result = importer._validate_single_file(file_path)

            assert result.is_valid is True  # Still valid, just has warning
            assert any("very large" in issue.message for issue in result.issues)
            assert result.file_size_mb == 60.0
        finally:
            file_path.unlink(missing_ok=True)

    def test_detect_encoding_utf8(self, importer: BulkImporter) -> None:
        """Test encoding detection for UTF-8 file."""
        content = "Title: Test Script\nAuthor: Test Author"
        with tempfile.NamedTemporaryFile(
            delete=False, mode="w", encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            file_path = Path(tmp.name)

        try:
            result = importer._detect_encoding(file_path)
            assert result["encoding"] == "utf-8"
            assert result["content"] == content
            assert result["error"] is None
        finally:
            file_path.unlink(missing_ok=True)

    def test_detect_encoding_latin1(self, importer: BulkImporter) -> None:
        """Test encoding detection for Latin-1 file."""
        content = "Title: Test Script\nAuthor: José García"
        with tempfile.NamedTemporaryFile(
            delete=False, mode="w", encoding="latin-1"
        ) as tmp:
            tmp.write(content)
            file_path = Path(tmp.name)

        try:
            result = importer._detect_encoding(file_path)
            assert result["encoding"] in ["latin-1", "iso-8859-1", "windows-1252"]
            assert "José" in result["content"]
            assert result["error"] is None
        finally:
            file_path.unlink(missing_ok=True)

    def test_quick_fountain_check_valid(self, importer: BulkImporter) -> None:
        """Test fountain format detection for valid content."""
        content = """Title: Test Script

INT. OFFICE - DAY

Character enters.

CHARACTER
Some dialogue here.

CUT TO:
"""
        result = importer._quick_fountain_check(content)
        assert result["is_fountain"] is True
        assert len(result["markers_found"]) >= 2

    def test_quick_fountain_check_invalid(self, importer: BulkImporter) -> None:
        """Test fountain format detection for non-fountain content."""
        content = """This is just a regular text file.
It doesn't have any screenplay formatting.
Just normal paragraphs."""

        result = importer._quick_fountain_check(content)
        assert result["is_fountain"] is False
        assert len(result["markers_found"]) < 2

    def test_validate_series_detection_custom_pattern(
        self, importer: BulkImporter
    ) -> None:
        """Test series detection validation with custom pattern."""
        files = [
            Path("ShowName_S01E01.fountain"),
            Path("ShowName_S01E02.fountain"),
        ]

        # Valid custom pattern
        result = importer._validate_series_detection(
            files, r"^(?P<series>.+?)_S(?P<season>\d+)E(?P<episode>\d+)"
        )
        assert len(result.regex_errors) == 0
        assert "ShowName" in result.series_structure

        # Invalid custom pattern
        result = importer._validate_series_detection(files, r"[invalid(")
        assert len(result.regex_errors) == 1
        assert "Invalid custom pattern" in result.regex_errors[0]

    def test_validate_series_detection_duplicates(self, importer: BulkImporter) -> None:
        """Test detection of duplicate episodes."""
        files = [
            Path("Show_S01E01_Part1.fountain"),
            Path("Show_S01E01_Part2.fountain"),
            Path("Show_S01E02.fountain"),
        ]

        result = importer._validate_series_detection(files)
        assert len(result.duplicate_episodes) == 1
        assert result.duplicate_episodes[0]["season"] == 1
        assert result.duplicate_episodes[0]["episode"] == 1
        assert len(result.duplicate_episodes[0]["files"]) == 2

    def test_validate_files_integration(self, importer: BulkImporter) -> None:
        """Test full file validation integration."""
        # Create test files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Valid fountain file
            valid_file = tmpdir_path / "Show_S01E01.fountain"
            valid_file.write_text(
                "INT. LOCATION - DAY\n\nAction here.", encoding="utf-8"
            )

            # Invalid extension
            invalid_ext = tmpdir_path / "Show_S01E02.doc"
            invalid_ext.write_text("Some content", encoding="utf-8")

            # Non-existent file
            missing_file = tmpdir_path / "Show_S01E03.fountain"

            files = [valid_file, invalid_ext, missing_file]

            file_results, series_results = importer.validate_files(files)

            # Check file validation results
            assert len(file_results) == 3
            assert file_results[str(valid_file)].is_valid is True
            assert file_results[str(invalid_ext)].is_valid is False
            assert file_results[str(missing_file)].is_valid is False

            # Check series validation results
            assert "Show" in series_results.series_structure
            # Only 2 files are processed since missing_file doesn't exist
            assert series_results.series_structure["Show"]["episode_count"] == 2


class TestSeriesPatternDetectorValidation:
    """Test cases for SeriesPatternDetector validation methods."""

    def test_validate_pattern_valid(self) -> None:
        """Test validating a valid pattern."""
        detector = SeriesPatternDetector()
        result = detector.validate_pattern(
            r"^(?P<series>.+?)_S(?P<season>\d+)E(?P<episode>\d+)(?:_(?P<title>.+?))?$"
        )

        assert result["is_valid"] is True
        assert result["error"] is None
        assert result["has_series_group"] is True
        assert result["has_season_group"] is True
        assert result["has_episode_group"] is True
        assert result["has_title_group"] is True
        assert len(result["warnings"]) == 0

    def test_validate_pattern_invalid_regex(self) -> None:
        """Test validating an invalid regex pattern."""
        detector = SeriesPatternDetector()
        result = detector.validate_pattern("[invalid(")

        assert result["is_valid"] is False
        assert "Invalid regex pattern" in result["error"]

    def test_validate_pattern_missing_groups(self) -> None:
        """Test validating pattern with missing groups."""
        detector = SeriesPatternDetector()
        result = detector.validate_pattern(r"^(.+?)_(\d+)x(\d+)$")

        assert result["is_valid"] is True
        assert result["has_series_group"] is False
        assert result["has_season_group"] is False
        assert result["has_episode_group"] is False
        assert (
            len(result["warnings"]) == 2
        )  # Missing series and season/episode warnings

    def test_validate_pattern_too_broad(self) -> None:
        """Test validating overly broad pattern."""
        detector = SeriesPatternDetector()
        result = detector.validate_pattern(".*")

        assert result["is_valid"] is True
        assert any("too broad" in warning for warning in result["warnings"])
