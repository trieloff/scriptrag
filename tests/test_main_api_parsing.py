"""Tests for ScriptRAG parsing functionality."""

import tempfile
from pathlib import Path

import pytest

from scriptrag.main import ScriptRAG


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
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".fountain", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(sample_fountain_content)
        file_path = Path(tmp.name)

    yield file_path

    # Cleanup
    if file_path.exists():
        file_path.unlink()


@pytest.fixture
def scriptrag_instance():
    """Create a ScriptRAG instance without database."""
    return ScriptRAG(auto_init_db=False)


class TestParseFountain:
    """Test Fountain parsing functionality."""

    def test_parse_fountain_success(self, scriptrag_instance, temp_fountain_file):
        """Test successful Fountain file parsing."""
        script = scriptrag_instance.parse_fountain(temp_fountain_file)

        assert script is not None
        assert script.title == "Test Script"
        assert script.author == "Test Author"
        assert len(script.scenes) == 2
        assert script.scenes[0].heading == "INT. COFFEE SHOP - DAY"
        assert script.scenes[1].heading == "EXT. PARK - DAY"

    def test_parse_fountain_with_string_path(
        self, scriptrag_instance, temp_fountain_file
    ):
        """Test parsing with string path instead of Path object."""
        script = scriptrag_instance.parse_fountain(str(temp_fountain_file))

        assert script is not None
        assert script.title == "Test Script"

    def test_parse_fountain_file_not_found(self, scriptrag_instance):
        """Test error when Fountain file doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            scriptrag_instance.parse_fountain("nonexistent.fountain")

        assert "Fountain file not found" in str(exc_info.value)

    def test_parse_fountain_empty_file(self, scriptrag_instance):
        """Test parsing an empty Fountain file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".fountain", delete=False
        ) as tmp:
            tmp.write("")
            file_path = Path(tmp.name)

        try:
            script = scriptrag_instance.parse_fountain(file_path)
            assert script is not None
            assert len(script.scenes) == 0
        finally:
            if file_path.exists():
                file_path.unlink()
