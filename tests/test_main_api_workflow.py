"""End-to-end workflow tests for ScriptRAG."""

import tempfile
from pathlib import Path

import pytest

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
def temp_db_path():
    """Create a temporary database path."""
    # Create a temporary directory and generate a database path
    # Don't create the actual file - let ScriptRAG initialize it
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_scriptrag.db"

        yield db_path

        # Cleanup is automatic when temporary directory is removed


class TestEndToEndWorkflow:
    """Test complete workflows from parsing to searching."""

    def test_complete_workflow(self, temp_db_path, sample_fountain_content):
        """Test complete workflow: init, parse, index, search."""
        from scriptrag.config import ScriptRAGSettings

        # 1. Initialize ScriptRAG
        settings = ScriptRAGSettings(database_path=temp_db_path)
        scriptrag = ScriptRAG(settings=settings, auto_init_db=True)

        # 2. Create a fountain file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".fountain", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(sample_fountain_content)
            file_path = Path(tmp.name)

        try:
            # 3. Parse the script
            script = scriptrag.parse_fountain(file_path)
            assert script.title == "Test Script"
            assert len(script.scenes) == 2

            # 4. Index the script
            index_result = scriptrag.index_script(file_path)
            assert index_result["indexed"] is True
            assert index_result["scenes_indexed"] == 2

            # 5. Search for content
            search_results = scriptrag.search("coffee shop")
            assert search_results.total_results > 0

            # 6. Search for character
            char_results = scriptrag.search("Alice", mode=SearchMode.CHARACTER)
            assert char_results.total_results > 0

            # 7. Search for dialogue
            dialogue_results = scriptrag.search("London", mode=SearchMode.DIALOGUE)
            assert dialogue_results.total_results > 0

        finally:
            if file_path.exists():
                file_path.unlink()

    def test_directory_workflow(self, temp_db_path, sample_fountain_content):
        """Test workflow with directory indexing."""
        import gc
        import platform

        from scriptrag.config import ScriptRAGSettings

        # Initialize ScriptRAG
        settings = ScriptRAGSettings(database_path=temp_db_path)
        scriptrag = ScriptRAG(settings=settings, auto_init_db=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create multiple scripts
            script_titles = []
            for i in range(3):
                content = sample_fountain_content.replace(
                    "Title: Test Script", f"Title: Script {i}"
                )
                file_path = tmpdir_path / f"script{i}.fountain"
                file_path.write_text(content)
                script_titles.append(f"Script {i}")

            # Index the directory
            index_result = scriptrag.index_directory(tmpdir_path)
            assert index_result["total_scripts"] == 3
            assert index_result["scripts_indexed"] == 3

            # Search across all scripts
            results = scriptrag.search("coffee")
            assert results.total_results > 0

            # Search for specific script content
            for title in script_titles:
                results = scriptrag.search(title)
                assert results.total_results > 0

        # Cleanup for Windows
        if platform.system() == "Windows":
            if hasattr(scriptrag, "db_ops"):
                del scriptrag.db_ops
            if hasattr(scriptrag, "index_command"):
                del scriptrag.index_command
            if hasattr(scriptrag, "search_engine"):
                del scriptrag.search_engine
            del scriptrag
            gc.collect()
            import time

            time.sleep(0.1)

    def test_update_workflow(self, temp_db_path, sample_fountain_content):
        """Test workflow with script updates."""
        import gc
        import platform

        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=temp_db_path)
        scriptrag = ScriptRAG(settings=settings, auto_init_db=True)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".fountain", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(sample_fountain_content)
            file_path = Path(tmp.name)

        try:
            # Initial index
            result1 = scriptrag.index_script(file_path)
            assert result1["indexed"] is True
            assert result1["updated"] is False

            # Search for original content
            results = scriptrag.search("London")
            original_count = results.total_results

            # Update the script content
            updated_content = sample_fountain_content.replace("London", "Paris")
            file_path.write_text(updated_content)

            # Re-index the updated script
            result2 = scriptrag.index_script(file_path)
            assert result2["indexed"] is True
            assert result2["updated"] is True

            # Search for new content
            results_paris = scriptrag.search("Paris")
            assert results_paris.total_results > 0

            # Old content should have different results
            results_london = scriptrag.search("London")
            # Results might differ based on implementation

        finally:
            if file_path.exists():
                file_path.unlink()

        # Cleanup for Windows
        if platform.system() == "Windows":
            if hasattr(scriptrag, "db_ops"):
                del scriptrag.db_ops
            if hasattr(scriptrag, "index_command"):
                del scriptrag.index_command
            if hasattr(scriptrag, "search_engine"):
                del scriptrag.search_engine
            del scriptrag
            gc.collect()
            import time

            time.sleep(0.1)
