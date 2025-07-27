"""Integration tests for bulk import functionality."""

import contextlib
import tempfile
from pathlib import Path

import pytest

from scriptrag.database.connection import DatabaseConnection
from scriptrag.database.operations import GraphOperations
from scriptrag.database.schema import create_database
from scriptrag.parser.bulk_import import BulkImporter


class TestBulkImportIntegration:
    """Integration tests for bulk import with real database."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def temp_db(self) -> Path:
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = Path(tmp.name)

        # Initialize schema
        create_database(db_path)
        yield db_path

        # Cleanup - Windows needs special handling for locked files
        with contextlib.suppress(PermissionError):
            # On Windows, SQLite may keep the file locked

            # This is acceptable as temp files will be cleaned up by the OS

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

    def create_fountain_file(self, path: Path, content: str | None = None) -> None:
        """Create a fountain file with content."""
        if content is None:
            content = """Title: Test Script
Author: Test Author

EXT. LOCATION - DAY

Action description.

CHARACTER
Dialogue here.

CUT TO:

INT. ANOTHER LOCATION - NIGHT

More action.
"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_import_tv_series_structure(
        self, temp_dir: Path, importer: BulkImporter
    ) -> None:
        """Test importing a TV series with proper structure."""
        # Create TV series structure
        series_dir = temp_dir / "Breaking Bad"

        # Season 1 episodes
        files = []
        for ep in range(1, 4):
            file_path = series_dir / f"BreakingBad_S01E{ep:02d}.fountain"
            self.create_fountain_file(file_path)
            files.append(file_path)

        # Season 2 episodes
        for ep in range(1, 3):
            file_path = series_dir / f"BreakingBad_S02E{ep:02d}.fountain"
            self.create_fountain_file(file_path)
            files.append(file_path)

        # Import all files
        result = importer.import_files(files)

        assert result.successful_imports == 5
        assert result.failed_imports == 0

        # Verify database structure
        conn = importer.graph_ops.connection

        # Check series was created
        series = conn.fetch_one(
            "SELECT * FROM scripts WHERE title = ? AND is_series = 1", ["BreakingBad"]
        )
        assert series is not None

        # Check seasons were created
        seasons = conn.fetch_all(
            "SELECT * FROM seasons WHERE script_id = ? ORDER BY number", [series["id"]]
        )
        assert len(seasons) == 2
        assert seasons[0]["number"] == 1
        assert seasons[1]["number"] == 2

        # Check episodes were created
        s1_episodes = conn.fetch_all(
            "SELECT * FROM episodes WHERE season_id = ? ORDER BY number",
            [seasons[0]["id"]],
        )
        assert len(s1_episodes) == 3

        s2_episodes = conn.fetch_all(
            "SELECT * FROM episodes WHERE season_id = ? ORDER BY number",
            [seasons[1]["id"]],
        )
        assert len(s2_episodes) == 2

    def test_import_mixed_content(self, temp_dir: Path, importer: BulkImporter) -> None:
        """Test importing a mix of series and standalone scripts."""
        files = []

        # TV series episodes
        for ep in range(1, 3):
            file_path = temp_dir / f"TheWire_S01E{ep:02d}.fountain"
            self.create_fountain_file(file_path)
            files.append(file_path)

        # Standalone scripts
        standalone_files = [
            temp_dir / "MyFeatureFilm.fountain",
            temp_dir / "AnotherScript.fountain",
        ]
        for file_path in standalone_files:
            self.create_fountain_file(file_path)
            files.append(file_path)

        # Import all
        result = importer.import_files(files)

        assert result.successful_imports == 4

        # Verify in database
        conn = importer.graph_ops.connection

        # Check series
        series = conn.fetch_one(
            "SELECT * FROM scripts WHERE title = 'TheWire' AND is_series = 1"
        )
        assert series is not None

        # Check standalone scripts
        standalone = conn.fetch_all("SELECT * FROM scripts WHERE is_series = 0")
        assert len(standalone) == 2

    def test_import_with_directory_structure(
        self, temp_dir: Path, importer: BulkImporter
    ) -> None:
        """Test importing from directory structure (Season X/Episode Y)."""
        # Create directory structure
        show_dir = temp_dir / "The Sopranos"

        files = []
        for season in range(1, 3):
            season_dir = show_dir / f"Season {season}"
            for ep in range(1, 3):
                file_path = season_dir / f"Episode {ep:02d} - Title.fountain"
                self.create_fountain_file(file_path)
                files.append(file_path)

        # Import
        result = importer.import_files(files)

        assert result.successful_imports == 4

        # Verify proper series detection
        conn = importer.graph_ops.connection
        series = conn.fetch_one(
            "SELECT * FROM scripts WHERE title = 'The Sopranos' AND is_series = 1"
        )
        assert series is not None

    def test_skip_existing_behavior(
        self, temp_dir: Path, importer: BulkImporter
    ) -> None:
        """Test skip existing files behavior."""
        file_path = temp_dir / "test_script.fountain"
        self.create_fountain_file(file_path)

        # First import
        result1 = importer.import_files([file_path])
        assert result1.successful_imports == 1

        # Second import with skip_existing=True (default)
        result2 = importer.import_files([file_path])
        assert result2.skipped_files == 1
        assert result2.successful_imports == 0

        # Third import with skip_existing=False
        importer.skip_existing = False
        result3 = importer.import_files([file_path])
        assert result3.successful_imports == 1

    def test_custom_pattern_import(self, temp_dir: Path, temp_db: Path) -> None:
        """Test importing with custom pattern."""
        # Create files with custom naming
        files = []
        for ep in range(1, 3):
            file_path = temp_dir / f"MyShow Episode S01E{ep:02d}.fountain"
            self.create_fountain_file(file_path)
            files.append(file_path)

        # Create importer with custom pattern
        conn = DatabaseConnection(temp_db)
        try:
            graph_ops = GraphOperations(conn)
            custom_pattern = (
                r"^(?P<series>.+?)\s+Episode\s+"
                r"S(?P<season>\d+)E(?P<episode>\d+)\.fountain$"
            )
            importer = BulkImporter(graph_ops, custom_pattern=custom_pattern)

            result = importer.import_files(files)
            assert result.successful_imports == 2

            # Verify series was properly detected
            series = conn.fetch_one(
                "SELECT * FROM scripts WHERE title = 'MyShow' AND is_series = 1"
            )
            assert series is not None
        finally:
            # Close connection to allow file deletion on Windows
            conn.close()

    def test_transaction_rollback_on_error(
        self, temp_dir: Path, importer: BulkImporter
    ) -> None:
        """Test that transactions are rolled back on error."""
        # Create a file that will cause an error - non-existent file
        file_path = temp_dir / "non_existent_script.fountain"
        # Don't create the file, so it doesn't exist

        # Get initial count
        conn = importer.graph_ops.connection
        initial_count = conn.fetch_one("SELECT COUNT(*) as count FROM scripts")["count"]

        # Try to import
        result = importer.import_files([file_path])
        assert result.failed_imports == 1

        # Verify no partial data was saved
        final_count = conn.fetch_one("SELECT COUNT(*) as count FROM scripts")["count"]
        assert final_count == initial_count

    def test_series_name_override_integration(
        self, temp_dir: Path, importer: BulkImporter
    ) -> None:
        """Test series name override with real import."""
        # Create files with one series name
        files = []
        for ep in range(1, 3):
            file_path = temp_dir / f"OldName_S01E{ep:02d}.fountain"
            self.create_fountain_file(file_path)
            files.append(file_path)

        # Import with override
        result = importer.import_files(files, series_name_override="New Name")
        assert result.successful_imports == 2

        # Verify override was applied
        conn = importer.graph_ops.connection
        series = conn.fetch_one(
            "SELECT * FROM scripts WHERE title = 'New Name' AND is_series = 1"
        )
        assert series is not None

        # Should not have created "OldName" series
        old_series = conn.fetch_one(
            "SELECT * FROM scripts WHERE title = 'OldName' AND is_series = 1"
        )
        assert old_series is None
