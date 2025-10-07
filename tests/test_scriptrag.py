"""Tests for the main ScriptRAG class."""

import tempfile
from pathlib import Path

import pytest

from scriptrag import ScriptRAG
from scriptrag.exceptions import DatabaseError


class TestScriptRAG:
    """Test cases for ScriptRAG class."""

    def test_init_success(self):
        """Test that ScriptRAG initializes successfully."""
        # Test with auto_init_db=False to avoid database creation
        scriptrag = ScriptRAG(auto_init_db=False)

        # Verify all components are initialized
        assert scriptrag.settings is not None
        assert scriptrag.parser is not None
        assert scriptrag.search_engine is not None
        assert scriptrag.query_parser is not None
        assert scriptrag.index_command is not None
        assert scriptrag.db_ops is not None

    def test_parse_fountain_file_not_found(self):
        """Test that parse_fountain raises FileNotFoundError for missing files."""
        scriptrag = ScriptRAG(auto_init_db=False)

        with pytest.raises(
            FileNotFoundError, match=r"Fountain file not found: nonexistent\.fountain"
        ):
            scriptrag.parse_fountain("nonexistent.fountain")

    def test_parse_fountain_with_valid_file(self):
        """Test that parse_fountain works with a valid Fountain file."""
        scriptrag = ScriptRAG(auto_init_db=False)

        # Create a temporary Fountain file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".fountain", delete=False
        ) as f:
            f.write(
                "Title: Test Script\n\nFADE IN:\n\nINT. TEST LOCATION - DAY\n\n"
                "A simple test scene.\n\nFADE OUT."
            )
            temp_path = f.name

        try:
            script = scriptrag.parse_fountain(temp_path)
            assert script is not None
            assert script.title == "Test Script"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_search_without_database(self):
        """Test that search raises DatabaseError when database is not initialized."""
        scriptrag = ScriptRAG(auto_init_db=False)

        with pytest.raises(DatabaseError, match="Database not initialized"):
            scriptrag.search("test query")
