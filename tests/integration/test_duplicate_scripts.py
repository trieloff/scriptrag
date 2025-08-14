"""Integration tests for duplicate script handling."""

import sqlite3
from pathlib import Path

import pytest

from scriptrag.api.database import DatabaseInitializer
from scriptrag.api.duplicate_handler import DuplicateHandler, DuplicateStrategy
from scriptrag.api.index import IndexCommand
from scriptrag.config import ScriptRAGSettings


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    initializer = DatabaseInitializer()
    initializer.initialize_database(db_path=db_path, force=True)
    return db_path


@pytest.fixture
def sample_scripts(tmp_path):
    """Create sample Fountain scripts for testing."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    # Create first script with same title/author
    script1 = scripts_dir / "episode1.fountain"
    script1.write_text("""Title: The Office
Author: Greg Daniels

INT. OFFICE - DAY

MICHAEL enters the office.

MICHAEL
That's what she said!

/*
SCRIPTRAG-META-START
{
  "analyzed_at": "2024-01-01T00:00:00",
  "season": 1,
  "episode": 1
}
SCRIPTRAG-META-END
*/
""")

    # Create second script with same title/author (different episode)
    script2 = scripts_dir / "episode2.fountain"
    script2.write_text("""Title: The Office
Author: Greg Daniels

INT. CONFERENCE ROOM - DAY

MICHAEL stands in front of the team.

MICHAEL
I am Beyoncé, always.

/*
SCRIPTRAG-META-START
{
  "analyzed_at": "2024-01-02T00:00:00",
  "season": 1,
  "episode": 2
}
SCRIPTRAG-META-END
*/
""")

    # Create third script with different title
    script3 = scripts_dir / "parks.fountain"
    script3.write_text("""Title: Parks and Recreation
Author: Greg Daniels

EXT. PARK - DAY

LESLIE looks at the camera.

LESLIE
This park will be perfect!

/*
SCRIPTRAG-META-START
{
  "analyzed_at": "2024-01-03T00:00:00"
}
SCRIPTRAG-META-END
*/
""")

    return scripts_dir


class TestDuplicateHandler:
    """Test the duplicate handler functionality."""

    def test_check_for_duplicate_none_found(self, temp_db):
        """Test checking for duplicates when none exist."""
        handler = DuplicateHandler()
        conn = sqlite3.connect(str(temp_db))

        duplicate = handler.check_for_duplicate(
            conn, "New Script", "New Author", Path("/new/path.fountain")
        )

        assert duplicate is None
        conn.close()

    def test_check_for_duplicate_same_path(self, temp_db):
        """Test that same file path is not considered a duplicate."""
        handler = DuplicateHandler()
        conn = sqlite3.connect(str(temp_db))

        # Insert a script
        conn.execute(
            """
            INSERT INTO scripts (title, author, file_path, metadata)
            VALUES (?, ?, ?, ?)
            """,
            ("Test Script", "Test Author", "/test/path.fountain", "{}"),
        )
        conn.commit()

        # Check for duplicate with same path - should return None
        duplicate = handler.check_for_duplicate(
            conn, "Test Script", "Test Author", Path("/test/path.fountain")
        )

        assert duplicate is None
        conn.close()

    def test_check_for_duplicate_different_path(self, temp_db):
        """Test finding duplicate with different file path."""
        handler = DuplicateHandler()
        conn = sqlite3.connect(str(temp_db))

        # Insert a script
        conn.execute(
            """
            INSERT INTO scripts (title, author, file_path, metadata)
            VALUES (?, ?, ?, ?)
            """,
            ("Test Script", "Test Author", "/test/path1.fountain", "{}"),
        )
        conn.commit()

        # Check for duplicate with different path
        duplicate = handler.check_for_duplicate(
            conn, "Test Script", "Test Author", Path("/test/path2.fountain")
        )

        assert duplicate is not None
        assert duplicate["title"] == "Test Script"
        assert duplicate["author"] == "Test Author"
        assert duplicate["file_path"] == "/test/path1.fountain"
        conn.close()


@pytest.mark.asyncio
class TestDuplicateIndexing:
    """Test duplicate handling during indexing."""

    async def test_index_duplicate_error_strategy(self, temp_db, sample_scripts):
        """Test that duplicate scripts cause an error with ERROR strategy."""
        settings = ScriptRAGSettings(database_path=temp_db)
        index_cmd = IndexCommand(settings=settings)

        # Index first script
        result = await index_cmd.index(
            path=sample_scripts / "episode1.fountain",
            recursive=False,
            duplicate_strategy=DuplicateStrategy.ERROR,
        )
        assert result.total_scripts_indexed == 1
        assert len(result.errors) == 0

        # Try to index second script with same title/author - should error
        result = await index_cmd.index(
            path=sample_scripts / "episode2.fountain",
            recursive=False,
            duplicate_strategy=DuplicateStrategy.ERROR,
        )
        assert result.total_scripts_indexed == 0
        assert len(result.errors) > 0
        assert "Duplicate script found" in result.errors[0]

    async def test_index_duplicate_skip_strategy(self, temp_db, sample_scripts):
        """Test skipping duplicate scripts with SKIP strategy."""
        settings = ScriptRAGSettings(database_path=temp_db)
        index_cmd = IndexCommand(settings=settings)

        # Index first script
        result = await index_cmd.index(
            path=sample_scripts / "episode1.fountain",
            recursive=False,
            duplicate_strategy=DuplicateStrategy.ERROR,
        )
        assert result.total_scripts_indexed == 1

        # Index second script with SKIP strategy
        result = await index_cmd.index(
            path=sample_scripts / "episode2.fountain",
            recursive=False,
            duplicate_strategy=DuplicateStrategy.SKIP,
        )
        assert result.total_scripts_indexed == 0
        assert any("Skipped duplicate" in str(s.error) for s in result.scripts)

        # Verify only one script in database
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT COUNT(*) FROM scripts")
        count = cursor.fetchone()[0]
        assert count == 1
        conn.close()

    async def test_index_duplicate_replace_strategy(self, temp_db, sample_scripts):
        """Test replacing duplicate scripts with REPLACE strategy."""
        settings = ScriptRAGSettings(database_path=temp_db)
        index_cmd = IndexCommand(settings=settings)

        # Index first script
        result = await index_cmd.index(
            path=sample_scripts / "episode1.fountain",
            recursive=False,
            duplicate_strategy=DuplicateStrategy.ERROR,
        )
        assert result.total_scripts_indexed == 1

        # Index second script with REPLACE strategy
        result = await index_cmd.index(
            path=sample_scripts / "episode2.fountain",
            recursive=False,
            duplicate_strategy=DuplicateStrategy.REPLACE,
        )
        assert result.total_scripts_indexed == 1

        # Verify only one script in database and it's the second one
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT file_path, metadata FROM scripts")
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert "episode2.fountain" in rows[0][0]
        conn.close()

    async def test_index_duplicate_version_strategy(self, temp_db, sample_scripts):
        """Test versioning duplicate scripts with VERSION strategy."""
        settings = ScriptRAGSettings(database_path=temp_db)
        index_cmd = IndexCommand(settings=settings)

        # Index first script
        result = await index_cmd.index(
            path=sample_scripts / "episode1.fountain",
            recursive=False,
            duplicate_strategy=DuplicateStrategy.ERROR,
        )
        assert result.total_scripts_indexed == 1

        # Index second script with VERSION strategy
        result = await index_cmd.index(
            path=sample_scripts / "episode2.fountain",
            recursive=False,
            duplicate_strategy=DuplicateStrategy.VERSION,
        )
        assert result.total_scripts_indexed == 1

        # Verify both scripts in database with version info
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute(
            "SELECT file_path, version, is_current FROM scripts ORDER BY version"
        )
        rows = cursor.fetchall()
        assert len(rows) == 2

        # First script should be version 1, not current
        assert "episode1.fountain" in rows[0][0]
        assert rows[0][1] == 1
        assert rows[0][2] == 0  # is_current = False

        # Second script should be version 2, current
        assert "episode2.fountain" in rows[1][0]
        assert rows[1][1] == 2
        assert rows[1][2] == 1  # is_current = True

        conn.close()

    async def test_index_multiple_scripts_with_duplicates(
        self, temp_db, sample_scripts
    ):
        """Test indexing multiple scripts at once with duplicates."""
        settings = ScriptRAGSettings(database_path=temp_db)
        index_cmd = IndexCommand(settings=settings)

        # Index all scripts with VERSION strategy
        result = await index_cmd.index(
            path=sample_scripts,
            recursive=True,
            duplicate_strategy=DuplicateStrategy.VERSION,
        )

        # Should index all 3 scripts
        assert result.total_scripts_indexed == 3
        assert len(result.errors) == 0

        # Verify database contains correct data
        conn = sqlite3.connect(str(temp_db))

        # Check total scripts
        cursor = conn.execute("SELECT COUNT(*) FROM scripts")
        count = cursor.fetchone()[0]
        assert count == 3

        # Check versioning for "The Office" scripts
        cursor = conn.execute(
            """
            SELECT file_path, version, is_current
            FROM scripts
            WHERE title = 'The Office'
            ORDER BY version
            """
        )
        office_rows = cursor.fetchall()
        assert len(office_rows) == 2

        # Only the latest should be current
        assert office_rows[0][2] == 0  # First not current
        assert office_rows[1][2] == 1  # Second is current

        # Check the Parks and Rec script
        cursor = conn.execute(
            """
            SELECT version, is_current
            FROM scripts
            WHERE title = 'Parks and Recreation'
            """
        )
        parks_row = cursor.fetchone()
        assert parks_row[0] == 1  # Version 1
        assert parks_row[1] == 1  # Is current

        conn.close()

    async def test_reindex_same_file_updates(self, temp_db, sample_scripts):
        """Test that re-indexing the same file updates it properly."""
        settings = ScriptRAGSettings(database_path=temp_db)
        index_cmd = IndexCommand(settings=settings)

        script_path = sample_scripts / "episode1.fountain"

        # Index script first time
        result = await index_cmd.index(
            path=script_path,
            recursive=False,
            duplicate_strategy=DuplicateStrategy.ERROR,
        )
        assert result.total_scripts_indexed == 1

        # Re-index same script - should update, not duplicate
        result = await index_cmd.index(
            path=script_path,
            recursive=False,
            duplicate_strategy=DuplicateStrategy.ERROR,
        )
        assert result.total_scripts_updated == 1
        assert len(result.errors) == 0

        # Verify only one script in database
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.execute("SELECT COUNT(*) FROM scripts")
        count = cursor.fetchone()[0]
        assert count == 1
        conn.close()
