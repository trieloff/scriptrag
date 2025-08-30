"""Integration tests for Bible character extraction."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from scriptrag.api.bible_extraction import BibleCharacterExtractor


@pytest.fixture
def bible_content():
    """Sample Bible markdown content."""
    return """# Script Bible

## Characters

### Main Characters

**JANE SMITH** - The protagonist, a detective in her late 30s. Often referred to as
Jane or Ms. Smith by colleagues.

**BOB JOHNSON** - Jane's partner, goes by Bob or Bobby with friends. Sometimes called
Mr. Johnson in formal settings.

### Supporting Characters

**DR. ALICE COOPER** - The forensic scientist. Known as Alice to friends or
Dr. Cooper professionally.

## Story Notes

The story follows Jane as she investigates a series of crimes...
"""


@pytest.fixture
def temp_bible_file(tmp_path, bible_content):
    """Create a temporary Bible file."""
    bible_path = tmp_path / "bible.md"
    bible_path.write_text(bible_content)
    return bible_path


@pytest.fixture
def mock_llm_response():
    """Mock LLM response with extracted characters."""
    return json.dumps(
        [
            {
                "canonical": "JANE SMITH",
                "aliases": ["JANE", "MS. SMITH"],
                "tags": ["protagonist", "detective"],
                "notes": "Lead detective investigating the case",
            },
            {
                "canonical": "BOB JOHNSON",
                "aliases": ["BOB", "BOBBY", "MR. JOHNSON"],
                "tags": ["partner"],
                "notes": "Jane's partner",
            },
            {
                "canonical": "ALICE COOPER",
                "aliases": ["ALICE", "DR. COOPER"],
                "tags": ["supporting", "scientist"],
                "notes": "Forensic scientist",
            },
        ]
    )


class TestBibleCharacterExtraction:
    """Test Bible character extraction functionality."""

    @pytest.mark.asyncio
    @pytest.mark.requires_llm
    async def test_extract_characters_from_bible(
        self, temp_bible_file, mock_llm_response
    ):
        """Test extracting characters from a Bible file."""
        # Mock LLM client
        mock_llm = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        completion_response = MagicMock(spec=["content", "model", "provider", "usage"])
        completion_response.content = mock_llm_response
        completion_response.model = "test-model"
        completion_response.provider = None
        completion_response.usage = {}
        mock_llm.complete = AsyncMock(return_value=completion_response)

        extractor = BibleCharacterExtractor(llm_client=mock_llm)
        result = await extractor.extract_characters_from_bible(temp_bible_file)

        # Check structure
        assert result["version"] == 1
        assert "extracted_at" in result
        assert "characters" in result

        # Check characters
        characters = result["characters"]
        assert len(characters) == 3

        # Check first character
        jane = characters[0]
        assert jane["canonical"] == "JANE SMITH"
        # First name "JANE" should be excluded from aliases
        assert "MS. SMITH" in jane["aliases"]
        # First name excluded when canonical has multiple parts
        assert "JANE" not in jane["aliases"]

        # Check that LLM was called
        mock_llm.complete.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.requires_llm
    async def test_normalization_and_deduplication(self, temp_bible_file):
        """Test that characters are normalized and deduplicated."""
        # Mock LLM with duplicate and mixed-case entries
        mock_response = json.dumps(
            [
                {
                    "canonical": "jane smith",  # lowercase
                    "aliases": ["jane", "MS. SMITH", "jane"],  # duplicate alias
                },
                {
                    "canonical": "JANE SMITH",  # duplicate canonical
                    "aliases": ["JANE"],
                },
                {
                    "canonical": "BOB JOHNSON",
                    "aliases": ["bob", "BOBBY"],
                },
            ]
        )

        mock_llm = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        completion_response = MagicMock(spec=["content", "model", "provider", "usage"])
        completion_response.content = mock_response
        completion_response.model = "test-model"
        completion_response.provider = None
        completion_response.usage = {}
        mock_llm.complete = AsyncMock(return_value=completion_response)

        extractor = BibleCharacterExtractor(llm_client=mock_llm)
        result = await extractor.extract_characters_from_bible(temp_bible_file)

        characters = result["characters"]
        # Should have 2 characters after deduplication
        assert len(characters) == 2

        # Check normalization
        jane = characters[0]
        assert jane["canonical"] == "JANE SMITH"  # Uppercase
        # Deduplicated, uppercase, first name excluded
        assert jane["aliases"] == ["MS. SMITH"]

        bob = characters[1]
        assert bob["canonical"] == "BOB JOHNSON"
        assert set(bob["aliases"]) == {"BOBBY"}  # All uppercase, first name excluded

    @pytest.mark.asyncio
    @pytest.mark.requires_llm
    async def test_empty_bible_file(self, tmp_path):
        """Test handling of Bible file with no character content."""
        # Create Bible without character sections
        bible_path = tmp_path / "empty_bible.md"
        bible_path.write_text("# Script Bible\n\n## Setting\n\nA dark city...")

        mock_llm = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        extractor = BibleCharacterExtractor(llm_client=mock_llm)

        result = await extractor.extract_characters_from_bible(bible_path)

        # Should return empty result
        assert result["version"] == 1
        assert result["characters"] == []

        # LLM should not be called if no character content found
        mock_llm.complete.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.requires_llm
    async def test_llm_extraction_failure(self, temp_bible_file):
        """Test handling of LLM extraction failures."""
        # Mock LLM that raises an error
        mock_llm = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_llm.complete = AsyncMock(side_effect=Exception("LLM API error"))

        extractor = BibleCharacterExtractor(llm_client=mock_llm)
        result = await extractor.extract_characters_from_bible(temp_bible_file)

        # Should return empty result on failure
        assert result["version"] == 1
        assert result["characters"] == []

    @pytest.mark.asyncio
    @pytest.mark.requires_llm
    async def test_invalid_json_response(self, temp_bible_file):
        """Test handling of invalid JSON from LLM."""
        # Mock LLM with invalid JSON
        mock_llm = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_response = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_response.content = "This is not JSON"
        mock_response.model = "test-model"
        mock_response.provider = None
        mock_response.usage = {}
        mock_llm.complete = AsyncMock(return_value=mock_response)

        extractor = BibleCharacterExtractor(llm_client=mock_llm)
        result = await extractor.extract_characters_from_bible(temp_bible_file)

        # Should handle gracefully
        assert result["version"] == 1
        assert result["characters"] == []

    @pytest.mark.asyncio
    @pytest.mark.requires_llm
    async def test_json_extraction_from_text(self, temp_bible_file):
        """Test extraction of JSON from LLM response with extra text."""
        # Mock LLM response with JSON embedded in text
        mock_response = """Here are the extracted characters:

[
    {
        "canonical": "JANE SMITH",
        "aliases": ["JANE", "MS. SMITH"]
    }
]

These are the main characters from the Bible."""

        mock_llm = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        completion_response = MagicMock(spec=["content", "model", "provider", "usage"])
        completion_response.content = mock_response
        completion_response.model = "test-model"
        completion_response.provider = None
        completion_response.usage = {}
        mock_llm.complete = AsyncMock(return_value=completion_response)

        extractor = BibleCharacterExtractor(llm_client=mock_llm)
        result = await extractor.extract_characters_from_bible(temp_bible_file)

        # Should extract JSON successfully
        assert len(result["characters"]) == 1
        assert result["characters"][0]["canonical"] == "JANE SMITH"

    @pytest.mark.asyncio
    @pytest.mark.requires_llm
    async def test_character_chunk_detection(self, tmp_path):
        """Test detection of character-related chunks."""
        # Create Bible with various sections
        bible_content = """# Script Bible

## World Building
The story takes place in...

## Cast of Characters
JANE - The hero
BOB - The sidekick

## Antagonists
VILLAIN - The bad guy

## Setting
A dark city...

## Main Roles
ALICE - Supporting character
"""
        bible_path = tmp_path / "bible.md"
        bible_path.write_text(bible_content)

        # Mock LLM
        mock_llm = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        completion_response = MagicMock(spec=["content", "model", "provider", "usage"])
        completion_response.content = json.dumps(
            [
                {"canonical": "JANE", "aliases": []},
                {"canonical": "BOB", "aliases": []},
                {"canonical": "VILLAIN", "aliases": []},
                {"canonical": "ALICE", "aliases": []},
            ]
        )
        completion_response.model = "test-model"
        completion_response.provider = None
        completion_response.usage = {}
        mock_llm.complete = AsyncMock(return_value=completion_response)

        extractor = BibleCharacterExtractor(llm_client=mock_llm)
        result = await extractor.extract_characters_from_bible(bible_path)

        # Should find all character sections
        assert len(result["characters"]) == 4

        # Check that appropriate chunks were sent to LLM
        call_args = mock_llm.complete.call_args[0][0]  # Get the messages list
        llm_content = call_args[0]["content"]  # Get the content from first message
        assert "Cast of Characters" in llm_content
        assert "Antagonists" in llm_content
        assert "Main Roles" in llm_content
        assert "World Building" not in llm_content  # Should not include
        assert "Setting" not in llm_content  # Should not include
