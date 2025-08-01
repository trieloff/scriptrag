"""Tests for the main ScriptRAG class."""

import pytest

from scriptrag import ScriptRAG


class TestScriptRAG:
    """Test cases for ScriptRAG class."""

    def test_init_raises_not_implemented(self):
        """Test that initializing ScriptRAG raises NotImplementedError."""
        with pytest.raises(
            NotImplementedError, match="ScriptRAG v2 is under development"
        ):
            ScriptRAG()

    def test_parse_fountain_not_implemented(self):
        """Test that parse_fountain is not yet implemented.

        This test creates a mock object to bypass __init__ to test the method.
        """
        # Create instance without calling __init__
        instance = object.__new__(ScriptRAG)

        with pytest.raises(
            NotImplementedError, match="Fountain parsing not yet implemented in v2"
        ):
            instance.parse_fountain("test.fountain")

    def test_search_not_implemented(self):
        """Test that search is not yet implemented.

        This test creates a mock object to bypass __init__ to test the method.
        """
        # Create instance without calling __init__
        instance = object.__new__(ScriptRAG)

        with pytest.raises(
            NotImplementedError, match="Search functionality not yet implemented in v2"
        ):
            instance.search("test query")
