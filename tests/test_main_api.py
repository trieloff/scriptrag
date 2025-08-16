"""Integration tests for the main ScriptRAG API."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scriptrag.exceptions import DatabaseError
from scriptrag.main import ScriptRAG
from scriptrag.search.models import SearchMode


@pytest.fixture
def sample_fountain_content():
    """Sample Fountain screenplay content."""
    return """Title: Test Script
Author: Test Author

FADE IN:

INT. COFFEE SHOP - DAY

The coffee shop is bustling with morning customers.

ALICE
(nervously)
I need to tell you something important.

BOB
What is it?

ALICE
I've been offered a job in London.

EXT. PARK - DAY

Alice and Bob walk through the park.

BOB
(shocked)
London? That's so far away!

ALICE
I know, but it's an amazing opportunity.

FADE OUT.
"""


@pytest.fixture
def temp_fountain_file(sample_fountain_content):
    """Create a temporary Fountain file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".fountain", delete=False) as f:
        f.write(sample_fountain_content)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def temp_db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_scriptrag.db"
        yield db_path


@pytest.fixture
def scriptrag_instance(temp_db_path):
    """Create a ScriptRAG instance with a temporary database."""
    import gc
    import platform

    from scriptrag.config import ScriptRAGSettings

    settings = ScriptRAGSettings(database_path=temp_db_path)
    instance = ScriptRAG(settings=settings, auto_init_db=True)

    yield instance

    # Ensure proper cleanup on Windows to prevent file locking issues
    if platform.system() == "Windows":
        # Force cleanup of all database-related components
        if hasattr(instance, "db_ops"):
            del instance.db_ops
        if hasattr(instance, "index_command"):
            del instance.index_command
        if hasattr(instance, "search_engine"):
            del instance.search_engine

        # Force garbage collection to close database connections
        del instance
        gc.collect()
        # Small delay to ensure Windows releases file handles
        import time

        time.sleep(0.1)


class TestScriptRAGInit:
    """Test ScriptRAG initialization."""

    def test_init_with_defaults(self, temp_db_path):
        """Test initialization with default settings."""
        with patch("scriptrag.main.get_settings") as mock_settings:
            from scriptrag.config import ScriptRAGSettings

            mock_settings.return_value = ScriptRAGSettings(database_path=temp_db_path)

            scriptrag = ScriptRAG()

            assert scriptrag.settings is not None
            assert scriptrag.parser is not None
            assert scriptrag.search_engine is not None
            assert scriptrag.query_parser is not None
            assert scriptrag.index_command is not None
            assert scriptrag.db_ops is not None

    def test_init_with_custom_settings(self, temp_db_path):
        """Test initialization with custom settings."""
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(
            database_path=temp_db_path,
            database_timeout=60.0,
        )

        scriptrag = ScriptRAG(settings=settings)

        assert scriptrag.settings == settings
        assert scriptrag.settings.database_timeout == 60.0

    def test_auto_init_database(self, temp_db_path):
        """Test automatic database initialization."""
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=temp_db_path)

        # Database shouldn't exist yet
        assert not temp_db_path.exists()

        # Initialize with auto_init_db=True
        scriptrag = ScriptRAG(settings=settings, auto_init_db=True)

        # Database should now exist
        assert temp_db_path.exists()
        assert scriptrag.db_ops.check_database_exists()

    def test_no_auto_init_database(self, temp_db_path):
        """Test skipping automatic database initialization."""
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=temp_db_path)

        # Initialize with auto_init_db=False
        scriptrag = ScriptRAG(settings=settings, auto_init_db=False)

        # Database should not be created
        assert not temp_db_path.exists()
        assert not scriptrag.db_ops.check_database_exists()


class TestParseFountain:
    """Test parse_fountain method."""

    def test_parse_valid_fountain_file(self, scriptrag_instance, temp_fountain_file):
        """Test parsing a valid Fountain file."""
        script = scriptrag_instance.parse_fountain(temp_fountain_file)

        assert script is not None
        assert script.title == "Test Script"
        assert script.author == "Test Author"
        assert len(script.scenes) == 2
        assert script.scenes[0].heading == "INT. COFFEE SHOP - DAY"
        assert script.scenes[1].heading == "EXT. PARK - DAY"

    def test_parse_with_string_path(self, scriptrag_instance, temp_fountain_file):
        """Test parsing with string path."""
        script = scriptrag_instance.parse_fountain(str(temp_fountain_file))

        assert script is not None
        assert script.title == "Test Script"

    def test_parse_nonexistent_file(self, scriptrag_instance):
        """Test parsing a non-existent file."""
        with pytest.raises(FileNotFoundError) as exc_info:
            scriptrag_instance.parse_fountain("/nonexistent/file.fountain")

        assert "Fountain file not found" in str(exc_info.value)

    def test_parse_invalid_fountain(self, scriptrag_instance):
        """Test parsing an invalid Fountain file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".fountain", delete=False
        ) as f:
            # Write content that might cause parsing issues
            f.write("")
            temp_path = Path(f.name)

        try:
            # Empty file should still parse (returns empty script)
            script = scriptrag_instance.parse_fountain(temp_path)
            assert script is not None
            assert len(script.scenes) == 0
        finally:
            temp_path.unlink(missing_ok=True)


class TestIndexScript:
    """Test index_script method."""

    def test_index_single_script(self, scriptrag_instance, temp_fountain_file):
        """Test indexing a single script."""
        result = scriptrag_instance.index_script(temp_fountain_file)

        assert result["indexed"] is True
        assert result["script_id"] is not None
        assert result["scenes_indexed"] == 2
        assert result["characters_indexed"] == 2  # ALICE and BOB
        assert result["dialogues_indexed"] > 0
        assert result["error"] is None

    def test_index_with_dry_run(self, scriptrag_instance, temp_fountain_file):
        """Test indexing with dry run mode."""
        result = scriptrag_instance.index_script(temp_fountain_file, dry_run=True)

        # In dry run, script should be analyzed but not saved
        assert result["indexed"] is True
        # Script ID might be None in dry run
        assert result["scenes_indexed"] == 2

    def test_index_nonexistent_file(self, scriptrag_instance):
        """Test indexing a non-existent file."""
        with pytest.raises(FileNotFoundError) as exc_info:
            scriptrag_instance.index_script("/nonexistent/file.fountain")

        assert "Fountain file not found" in str(exc_info.value)

    def test_update_existing_script(self, scriptrag_instance, temp_fountain_file):
        """Test updating an existing indexed script."""
        # First index
        result1 = scriptrag_instance.index_script(temp_fountain_file)
        assert result1["indexed"] is True
        assert result1["updated"] is False

        # Second index (should update)
        result2 = scriptrag_instance.index_script(temp_fountain_file)
        assert result2["indexed"] is True
        assert result2["updated"] is True
        assert result2["script_id"] == result1["script_id"]


class TestSearch:
    """Test search method."""

    def test_search_without_database(self, temp_db_path):
        """Test searching without initialized database."""
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=temp_db_path)
        scriptrag = ScriptRAG(settings=settings, auto_init_db=False)

        with pytest.raises(DatabaseError) as exc_info:
            scriptrag.search("test query")

        assert "Database not initialized" in str(exc_info.value)

    def test_search_basic_query(self, scriptrag_instance, temp_fountain_file):
        """Test basic search functionality."""
        # Index a script first
        scriptrag_instance.index_script(temp_fountain_file)

        # Search for content
        response = scriptrag_instance.search("coffee")

        assert response is not None
        assert response.query.raw_query == "coffee"
        # Results depend on whether "coffee" appears in indexed content

    def test_search_with_filters(self, scriptrag_instance, temp_fountain_file):
        """Test search with various filters."""
        # Index a script first
        scriptrag_instance.index_script(temp_fountain_file)

        # Search with character filter
        response = scriptrag_instance.search(
            "London",
            character="ALICE",
            limit=5,
        )

        assert response is not None
        assert response.query.raw_query == "London"
        assert "ALICE" in response.query.characters

    def test_search_modes(self, scriptrag_instance, temp_fountain_file):
        """Test different search modes."""
        # Index a script first
        scriptrag_instance.index_script(temp_fountain_file)

        # Test strict mode
        response_strict = scriptrag_instance.search(
            "coffee shop",
            mode=SearchMode.STRICT,
        )
        assert response_strict.query.mode == SearchMode.STRICT

        # Test fuzzy mode
        response_fuzzy = scriptrag_instance.search(
            "coffee shop",
            mode="fuzzy",  # Test string mode conversion
        )
        assert response_fuzzy.query.mode == SearchMode.FUZZY

        # Test auto mode (default)
        response_auto = scriptrag_instance.search("coffee shop")
        assert response_auto.query.mode == SearchMode.AUTO

    def test_search_pagination(self, scriptrag_instance, temp_fountain_file):
        """Test search pagination."""
        # Index a script first
        scriptrag_instance.index_script(temp_fountain_file)

        # Search with pagination
        response = scriptrag_instance.search(
            "DAY",  # Should match scene headings
            limit=1,
            offset=0,
        )

        assert response is not None
        assert len(response.results) <= 1

    def test_search_bible_options(self, scriptrag_instance):
        """Test bible search options."""
        # Search with bible options
        response = scriptrag_instance.search(
            "test",
            include_bible=False,
            only_bible=False,
        )

        assert response is not None
        assert response.query.include_bible is False
        assert response.query.only_bible is False


class TestIndexDirectory:
    """Test index_directory method."""

    def test_index_directory_with_scripts(
        self, scriptrag_instance, sample_fountain_content
    ):
        """Test indexing a directory with Fountain files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)

            # Add metadata to indicate analyzed scripts
            content_with_meta = (
                sample_fountain_content
                + """
/* SCRIPTRAG-META-START
{"analyzed": true}
SCRIPTRAG-META-END */
"""
            )

            # Create multiple Fountain files
            for i in range(3):
                file_path = dir_path / f"script_{i}.fountain"
                file_path.write_text(content_with_meta)

            # Index the directory
            result = scriptrag_instance.index_directory(dir_path)

            assert result["total_scripts_indexed"] == 3
            assert result["total_scenes_indexed"] == 6  # 2 scenes per script
            assert result["total_characters_indexed"] > 0
            assert len(result["errors"]) == 0

    def test_index_directory_recursive(
        self, scriptrag_instance, sample_fountain_content
    ):
        """Test recursive directory indexing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)

            # Add metadata to indicate analyzed scripts
            content_with_meta = (
                sample_fountain_content
                + """
/* SCRIPTRAG-META-START
{"analyzed": true}
SCRIPTRAG-META-END */
"""
            )

            # Create nested structure
            subdir = dir_path / "subdir"
            subdir.mkdir()

            # Create files in both directories
            (dir_path / "script1.fountain").write_text(content_with_meta)
            (subdir / "script2.fountain").write_text(content_with_meta)

            # Index recursively
            result = scriptrag_instance.index_directory(
                dir_path,
                recursive=True,
            )

            # Both scripts should be indexed
            assert result["total_scripts_indexed"] == 2

    def test_index_directory_non_recursive(
        self, scriptrag_instance, sample_fountain_content
    ):
        """Test non-recursive directory indexing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)

            # Add metadata to indicate analyzed scripts
            content_with_meta = (
                sample_fountain_content
                + """
/* SCRIPTRAG-META-START
{"analyzed": true}
SCRIPTRAG-META-END */
"""
            )

            # Create nested structure
            subdir = dir_path / "subdir"
            subdir.mkdir()

            # Create files in both directories
            (dir_path / "script1.fountain").write_text(content_with_meta)
            (subdir / "script2.fountain").write_text(content_with_meta)

            # Index non-recursively
            result = scriptrag_instance.index_directory(
                dir_path,
                recursive=False,
            )

            # Only top-level script should be indexed
            assert result["total_scripts_indexed"] == 1

    def test_index_directory_dry_run(self, scriptrag_instance, sample_fountain_content):
        """Test directory indexing in dry run mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)

            # Add metadata to indicate analyzed scripts
            content_with_meta = (
                sample_fountain_content
                + """
/* SCRIPTRAG-META-START
{"analyzed": true}
SCRIPTRAG-META-END */
"""
            )

            # Create a Fountain file
            (dir_path / "script.fountain").write_text(content_with_meta)

            # Index with dry run
            result = scriptrag_instance.index_directory(
                dir_path,
                dry_run=True,
            )

            # Should analyze but not actually index
            assert "errors" in result

    def test_index_nonexistent_directory(self, scriptrag_instance):
        """Test indexing a non-existent directory."""
        with pytest.raises(FileNotFoundError) as exc_info:
            scriptrag_instance.index_directory("/nonexistent/directory")

        assert "Directory not found" in str(exc_info.value)

    def test_index_file_instead_of_directory(
        self, scriptrag_instance, temp_fountain_file
    ):
        """Test error when trying to index a file as directory."""
        with pytest.raises(ValueError) as exc_info:
            scriptrag_instance.index_directory(temp_fountain_file)

        assert "Path is not a directory" in str(exc_info.value)

    def test_index_empty_directory(self, scriptrag_instance):
        """Test indexing an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)

            # Index empty directory
            result = scriptrag_instance.index_directory(dir_path)

            assert result["total_scripts_indexed"] == 0
            assert result["total_scenes_indexed"] == 0
            assert len(result["errors"]) == 0


class TestEndToEndWorkflow:
    """Test complete end-to-end workflow."""

    def test_complete_workflow(self, temp_db_path, sample_fountain_content):
        """Test complete parse -> index -> search workflow."""
        from scriptrag.config import ScriptRAGSettings

        # 1. Initialize ScriptRAG
        settings = ScriptRAGSettings(database_path=temp_db_path)
        scriptrag = ScriptRAG(settings=settings, auto_init_db=True)

        # 2. Create test files
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)

            # Create multiple scripts with metadata
            content_with_meta = (
                sample_fountain_content
                + """
/* SCRIPTRAG-META-START
{"analyzed": true}
SCRIPTRAG-META-END */
"""
            )
            script1 = dir_path / "romantic_comedy.fountain"
            script1.write_text(content_with_meta)

            script2 = dir_path / "drama.fountain"
            script2.write_text("""Title: Drama Script
Author: Another Author

INT. OFFICE - NIGHT

CHARLIE
I can't believe you did this!

DIANA
I had no choice. The company was failing.

/* SCRIPTRAG-META-START
{"analyzed": true}
SCRIPTRAG-META-END */
""")

            # 3. Parse individual script
            parsed = scriptrag.parse_fountain(script1)
            assert parsed.title == "Test Script"
            assert len(parsed.scenes) == 2

            # 4. Index directory
            index_result = scriptrag.index_directory(dir_path)
            assert index_result["total_scripts_indexed"] == 2

            # 5. Search across indexed scripts

            # Search for dialogue
            dialogue_results = scriptrag.search(
                "London",
                dialogue="London",
            )
            assert dialogue_results is not None

            # Search for character
            character_results = scriptrag.search(
                "CHARLIE",
                character="CHARLIE",
            )
            assert character_results is not None

            # Search for location
            location_results = scriptrag.search(
                "office",
                location="OFFICE",
            )
            assert location_results is not None

            # 6. Test pagination
            page1 = scriptrag.search("INT", limit=1, offset=0)
            page2 = scriptrag.search("INT", limit=1, offset=1)

            # Results should be different if there are multiple matches
            assert page1 is not None
            assert page2 is not None

    def test_workflow_with_metadata(self, temp_db_path):
        """Test workflow with script containing metadata."""
        from scriptrag.config import ScriptRAGSettings

        # Script with boneyard metadata
        script_with_meta = """Title: Meta Script
Author: Test Author

INT. ROOM - DAY

ACTION LINE

/* SCRIPTRAG-META-START
{
  "analyzed": true,
  "embeddings": "test"
}
SCRIPTRAG-META-END */
"""

        settings = ScriptRAGSettings(database_path=temp_db_path)
        scriptrag = ScriptRAG(settings=settings, auto_init_db=True)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".fountain", delete=False
        ) as f:
            f.write(script_with_meta)
            temp_path = Path(f.name)

        try:
            # Parse and index
            parsed = scriptrag.parse_fountain(temp_path)
            assert parsed is not None

            result = scriptrag.index_script(temp_path)
            assert result["indexed"] is True

            # Search should work with indexed content
            search_result = scriptrag.search("ROOM")
            assert search_result is not None
        finally:
            temp_path.unlink(missing_ok=True)
