"""Additional tests for bible_extraction.py to improve coverage."""

import json
from unittest.mock import AsyncMock

import pytest

from scriptrag.api.bible.character_bible import BibleCharacter, BibleCharacterExtractor


class TestBibleExtractionAdditionalCoverage:
    """Additional tests to cover missing lines in bible_extraction.py."""

    @pytest.mark.asyncio
    async def test_extract_json_partial_match(self, tmp_path):
        """Test JSON extraction with partial regex match."""
        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Bible\n## Characters\nJANE SMITH - protagonist")

        # Mock LLM response with malformed JSON that has array structure
        mock_response = """Here's the analysis:
        [
            {"canonical": "JANE",
            "broken": json
        ```"""

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = mock_response

        extractor = BibleCharacterExtractor(llm_client=mock_llm)
        result = await extractor.extract_characters_from_bible(bible_path)

        # Should handle malformed JSON gracefully
        assert result["characters"] == []

    @pytest.mark.asyncio
    async def test_extract_json_response_object_fallback(self, tmp_path):
        """Test JSON extraction fallback to parsing entire response."""
        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Bible\n## Characters\nJANE SMITH - protagonist")

        # Response is valid JSON but not array format
        mock_response = json.dumps({"not": "array"})

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = mock_response

        extractor = BibleCharacterExtractor(llm_client=mock_llm)
        result = await extractor.extract_characters_from_bible(bible_path)

        # Should return empty since response is not an array
        assert result["characters"] == []

    def test_normalize_characters_complex_cases(self):
        """Test character normalization with complex cases."""
        extractor = BibleCharacterExtractor()

        characters = [
            BibleCharacter(
                canonical="  jane smith  ",  # Leading/trailing spaces
                aliases=[
                    "",
                    "JANE",
                    "jane smith",
                    "MS. SMITH",
                    "MS. SMITH",
                ],  # Empty, duplicate
                tags=["protagonist"],
                notes="Lead character",
            ),
            BibleCharacter(
                canonical="BOB",  # Single name
                aliases=["BOB", "BOBBY"],  # Canonical duplicate, first name only
                tags=None,
                notes=None,
            ),
        ]

        normalized = extractor._normalize_characters(characters)

        # Check first character
        jane = normalized[0]
        assert jane.canonical == "JANE SMITH"
        # Should exclude duplicates and canonical match, but include MS. SMITH
        assert jane.aliases == ["MS. SMITH"]

        # Check second character (single name)
        bob = normalized[1]
        assert bob.canonical == "BOB"
        # First name (BOB) should not be excluded since canonical has only one part
        assert set(bob.aliases) == {"BOBBY"}

    def test_normalize_characters_first_name_logic(self):
        """Test first name exclusion logic in normalization."""
        extractor = BibleCharacterExtractor()

        characters = [
            BibleCharacter(
                canonical="JANE SMITH",  # Multi-part name
                aliases=["JANE", "MS. SMITH"],  # First name should be excluded
            ),
            BibleCharacter(
                canonical="BOB",  # Single name
                aliases=["BOB", "BOBBY"],  # First name should NOT be excluded
            ),
        ]

        normalized = extractor._normalize_characters(characters)

        # Multi-part canonical: first name excluded
        assert "JANE" not in normalized[0].aliases
        assert "MS. SMITH" in normalized[0].aliases

        # Single-part canonical: first name not excluded
        assert "BOBBY" in normalized[1].aliases

    def test_find_character_chunks_content_heuristic(self, tmp_path):
        """Test character chunk detection using content heuristic."""
        bible_content = """# Script Bible

## Setting
The story takes place in a dark city.

## Plot Overview
This section mentions the character development and protagonist journey.
The cast includes various roles for the story.

## Technical Notes
Camera angles and lighting setup.
"""

        bible_path = tmp_path / "bible.md"
        bible_path.write_text(bible_content)

        extractor = BibleCharacterExtractor()

        # Mock the Bible parser
        from unittest.mock import MagicMock

        mock_chunk = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_chunk.heading = "Plot Overview"
        mock_chunk.content = (
            "This section mentions the character development and protagonist journey.\n"
            "The cast includes various roles for the story."
        )

        mock_parsed = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_parsed.chunks = [mock_chunk]

        extractor.bible_parser.parse_file = MagicMock(return_value=mock_parsed)

        chunks = extractor._find_character_chunks(mock_parsed)

        # Should find the chunk that mentions character/protagonist/cast
        assert len(chunks) == 1
        assert "Plot Overview" in chunks[0]
        assert "character development" in chunks[0]

    @pytest.mark.asyncio
    async def test_extract_via_llm_invalid_character_data(self, tmp_path):
        """Test LLM extraction with invalid character data structures."""
        chunks = ["## Characters\nJANE SMITH - the hero"]

        # Mock response with invalid character objects
        invalid_response = json.dumps(
            [
                "not_a_dict",  # String instead of dict
                {"no_canonical": "field"},  # Missing canonical
                {"canonical": "", "aliases": []},  # Empty canonical
                {"canonical": "VALID", "aliases": "not_a_list"},  # Invalid aliases type
                {"canonical": "JANE", "aliases": [123, None]},  # Invalid alias types
            ]
        )

        mock_llm = AsyncMock()
        mock_llm.complete.return_value = invalid_response

        extractor = BibleCharacterExtractor(llm_client=mock_llm)
        result = await extractor.extract_via_llm(chunks)

        # Should extract valid characters
        # (note: some invalid data may still create characters)
        # We expect at least one valid character
        valid_chars = [r for r in result if r.canonical in ["VALID", "JANE"]]
        assert len(valid_chars) >= 1

    @pytest.mark.asyncio
    async def test_extract_characters_parser_exception(self, tmp_path):
        """Test handling of Bible parser exceptions."""
        from unittest.mock import MagicMock

        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Bible\n## Characters\nContent")

        extractor = BibleCharacterExtractor()

        # Mock parser to raise exception
        extractor.bible_parser.parse_file = MagicMock(
            side_effect=Exception("Parse error")
        )

        result = await extractor.extract_characters_from_bible(bible_path)

        # Should return empty result on parse exception
        assert result["version"] == 1
        assert result["characters"] == []

    def test_find_character_chunks_no_heading(self):
        """Test chunk detection when chunk has no heading."""
        extractor = BibleCharacterExtractor()

        # Mock parsed Bible with chunk that has no heading
        from unittest.mock import MagicMock

        mock_chunk = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_chunk.heading = None
        mock_chunk.content = "The main character is Jane."

        mock_parsed = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_parsed.chunks = [mock_chunk]

        chunks = extractor._find_character_chunks(mock_parsed)

        # Should include content without heading
        assert len(chunks) == 1
        assert chunks[0] == "The main character is Jane."

    def test_find_character_chunks_with_heading(self):
        """Test chunk detection includes heading with content."""
        extractor = BibleCharacterExtractor()

        from unittest.mock import MagicMock

        mock_chunk = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_chunk.heading = "Main Cast"
        mock_chunk.content = "Jane is the protagonist."

        mock_parsed = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_parsed.chunks = [mock_chunk]

        chunks = extractor._find_character_chunks(mock_parsed)

        # Should include heading with content
        assert len(chunks) == 1
        assert "Main Cast" in chunks[0]
        assert "Jane is the protagonist." in chunks[0]

    def test_extract_json_regex_match_but_invalid_json(self):
        """Test JSON extraction when regex matches but JSON is invalid."""
        extractor = BibleCharacterExtractor()

        # Response that matches the regex pattern but contains invalid JSON
        # This will match the regex but fail json.loads() - hitting lines 243-244
        response = 'Here is the result: [{"canonical": "JANE", "invalid_json": }]'

        result = extractor._extract_json(response)

        # Should return empty list when regex matches but JSON is invalid
        assert result == []

    def test_extract_json_complex_invalid_patterns(self):
        """Test JSON extraction with complex invalid patterns that match regex."""
        extractor = BibleCharacterExtractor()

        # Pattern that looks like valid JSON array but has syntax errors
        test_cases = [
            # Missing closing brace
            '[{"canonical": "JANE", "aliases": ["J"]}',
            # Extra comma
            '[{"canonical": "JANE", "aliases": ["J"]},]',
            # Unescaped quotes
            '[{"canonical": "JA"NE", "aliases": ["J"]}]',
            # Missing quotes
            '[{canonical: "JANE", aliases: ["J"]}]',
            # Invalid unicode escape
            '[{"canonical": "JANE\\uXXXX", "aliases": ["J"]}]',
        ]

        for invalid_response in test_cases:
            result = extractor._extract_json(invalid_response)
            assert result == [], f"Failed for response: {invalid_response}"
