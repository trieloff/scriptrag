"""Complete coverage tests for bible_extraction.py."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from scriptrag.api.bible.character_bible import BibleCharacter
from scriptrag.api.bible.character_bible import (
    BibleCharacterExtractor as RealBibleCharacterExtractor,
)
from scriptrag.api.bible.scene_bible import BibleScene
from scriptrag.api.bible_extraction import BibleExtractor
from scriptrag.parser.bible_parser import BibleChunk, ParsedBible


@pytest.fixture
def mock_parsed_bible() -> ParsedBible:
    """Create a mock parsed bible for testing."""
    chunks = [
        BibleChunk(
            chunk_number=0,
            heading="Main Characters",
            level=1,
            content="JANE SMITH - Lead detective\nJOHN DOE - Suspect",
            content_hash="hash1",
            metadata={},
            parent_chunk_id=None,
        ),
        BibleChunk(
            chunk_number=1,
            heading="Supporting Cast",
            level=2,
            content="SARAH JONES - Forensic expert\nMIKE BROWN - Police chief",
            content_hash="hash2",
            metadata={},
            parent_chunk_id=0,
        ),
        BibleChunk(
            chunk_number=2,
            heading="World Building",
            level=1,
            content="The story takes place in New York City in 2024.",
            content_hash="hash3",
            metadata={},
            parent_chunk_id=None,
        ),
    ]
    return ParsedBible(
        file_path=Path("/test/bible.md"),
        title="Test Bible",
        file_hash="test_hash",
        metadata={"test": "data"},
        chunks=chunks,
    )


class TestBibleCharacter:
    """Test BibleCharacter dataclass."""

    def test_bible_character_creation(self) -> None:
        """Test creating a BibleCharacter."""
        char = BibleCharacter(
            canonical="JANE SMITH",
            aliases=["JANE", "DETECTIVE SMITH"],
            tags=["protagonist"],
            notes="Lead character",
        )
        assert char.canonical == "JANE SMITH"
        assert char.aliases == ["JANE", "DETECTIVE SMITH"]
        assert char.tags == ["protagonist"]
        assert char.notes == "Lead character"

    def test_bible_character_defaults(self) -> None:
        """Test BibleCharacter with default values."""
        char = BibleCharacter(canonical="JANE", aliases=["J"])
        assert char.canonical == "JANE"
        assert char.aliases == ["J"]
        assert char.tags is None
        assert char.notes is None


class TestRealBibleCharacterExtractor:
    """Test REAL BibleCharacterExtractor class from bible.character_bible."""

    def test_init_with_llm_client(self) -> None:
        """Test initialization with provided LLM client."""
        mock_client = Mock(spec=object)
        extractor = RealBibleCharacterExtractor(llm_client=mock_client)
        assert extractor.llm_client is mock_client

    def test_init_without_llm_client(self) -> None:
        """Test initialization without LLM client."""
        with patch("scriptrag.api.bible.character_bible.LLMClient") as mock_llm_class:
            mock_client = Mock(spec=object)
            mock_llm_class.return_value = mock_client

            extractor = RealBibleCharacterExtractor()
            assert extractor.llm_client is mock_client

    @pytest.mark.asyncio
    async def test_extract_characters_parse_error(self, tmp_path: Path) -> None:
        """Test handling of parse errors."""
        bible_path = tmp_path / "bad_bible.md"
        bible_path.write_text("# Test")

        extractor = BibleExtractor()

        # Mock parser to raise error
        with patch.object(
            extractor.bible_parser, "parse_file", side_effect=Exception("Parse failed")
        ):
            result = await extractor.extract_characters_from_bible(bible_path)

            assert result["version"] == 1
            assert result["characters"] == []
            assert "extracted_at" in result

    @pytest.mark.asyncio
    async def test_extract_characters_no_character_chunks(
        self, tmp_path: Path, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test extraction when no character chunks found."""
        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Test")

        extractor = BibleExtractor()

        # Mock parsed bible with no character chunks
        empty_bible = ParsedBible(
            file_path=bible_path,
            title="Empty Bible",
            file_hash="hash",
            metadata={},
            chunks=[
                BibleChunk(
                    chunk_number=0,
                    heading="Setting",
                    level=1,
                    content="The story takes place in space.",
                    content_hash="hash1",
                    metadata={},
                    parent_chunk_id=None,
                )
            ],
        )

        with patch.object(
            extractor.bible_parser, "parse_file", return_value=empty_bible
        ):
            result = await extractor.extract_characters_from_bible(bible_path)

            assert result["version"] == 1
            assert result["characters"] == []

    @pytest.mark.asyncio
    async def test_extract_characters_successful(
        self, tmp_path: Path, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test successful character extraction."""
        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Test")

        # Mock LLM client
        mock_client = AsyncMock()
        mock_response = Mock(spec_set=["content"])
        mock_response.content = json.dumps(
            [
                {
                    "canonical": "JANE SMITH",
                    "aliases": ["JANE", "DETECTIVE SMITH"],
                    "tags": ["protagonist"],
                    "notes": "Lead detective",
                }
            ]
        )
        mock_client.complete = AsyncMock(return_value=mock_response)

        extractor = BibleExtractor(llm_client=mock_client)

        with patch.object(
            extractor.bible_parser, "parse_file", return_value=mock_parsed_bible
        ):
            result = await extractor.extract_characters_from_bible(bible_path)

            assert result["version"] == 1
            assert len(result["characters"]) == 1
            char = result["characters"][0]
            assert char["canonical"] == "JANE SMITH"
            # Should only have "DETECTIVE SMITH" since "JANE" is filtered as first name
            assert set(char["aliases"]) == {"DETECTIVE SMITH"}

    def test_find_character_chunks_by_heading(
        self, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test finding character chunks by heading keywords."""
        extractor = BibleExtractor()
        chunks = extractor._find_character_chunks(mock_parsed_bible)

        # Should find chunks with "Characters" and "Cast" in headings
        assert len(chunks) >= 2
        assert any("Main Characters" in chunk for chunk in chunks)
        assert any("Supporting Cast" in chunk for chunk in chunks)

    def test_find_character_chunks_by_content(self) -> None:
        """Test finding character chunks by content keywords."""
        chunks = [
            BibleChunk(
                chunk_number=0,
                heading="Story Elements",
                level=1,
                content="The protagonist is a detective who solves cases.",
                content_hash="hash1",
                metadata={},
                parent_chunk_id=None,
            )
        ]
        bible = ParsedBible(
            file_path=Path("/test.md"),
            title="Test",
            file_hash="hash",
            metadata={},
            chunks=chunks,
        )

        extractor = BibleExtractor()
        found_chunks = extractor._find_character_chunks(bible)

        # Should find chunk with "protagonist" in content
        assert len(found_chunks) == 1
        assert "protagonist" in found_chunks[0]

    def test_find_character_chunks_no_heading(self) -> None:
        """Test finding character chunks with no heading."""
        chunks = [
            BibleChunk(
                chunk_number=0,
                heading=None,
                level=1,
                content="The character list includes JANE and JOHN.",
                content_hash="hash1",
                metadata={},
                parent_chunk_id=None,
            )
        ]
        bible = ParsedBible(
            file_path=Path("/test.md"),
            title="Test",
            file_hash="hash",
            metadata={},
            chunks=chunks,
        )

        extractor = BibleExtractor()
        found_chunks = extractor._find_character_chunks(bible)

        # Should find chunk even without heading
        assert len(found_chunks) == 1
        assert "character" in found_chunks[0]

    @pytest.mark.asyncio
    async def test_extract_via_llm_successful(self) -> None:
        """Test successful LLM extraction."""
        chunks = ["Main Characters\nJANE SMITH - Lead detective"]

        # Mock LLM client
        mock_client = AsyncMock()
        mock_response = Mock(spec_set=["content"])
        mock_response.content = json.dumps(
            [
                {
                    "canonical": "JANE SMITH",
                    "aliases": ["JANE", "DETECTIVE SMITH"],
                    "tags": ["protagonist"],
                    "notes": "Lead detective",
                }
            ]
        )
        mock_client.complete = AsyncMock(return_value=mock_response)

        extractor = BibleExtractor(llm_client=mock_client)
        characters = await extractor._extract_via_llm(chunks)

        assert len(characters) == 1
        char = characters[0]
        assert char.canonical == "JANE SMITH"
        assert char.aliases == ["JANE", "DETECTIVE SMITH"]
        assert char.tags == ["protagonist"]
        assert char.notes == "Lead detective"

    @pytest.mark.asyncio
    async def test_extract_via_llm_error(self) -> None:
        """Test LLM extraction with error."""
        chunks = ["Main Characters\nJANE SMITH - Lead detective"]

        # Mock LLM client that raises error
        mock_client = AsyncMock()
        mock_client.complete.side_effect = Exception("LLM error")

        extractor = BibleExtractor(llm_client=mock_client)
        characters = await extractor._extract_via_llm(chunks)

        assert characters == []

    @pytest.mark.asyncio
    async def test_extract_via_llm_invalid_character_data(self) -> None:
        """Test LLM extraction with invalid character data."""
        chunks = ["Main Characters\nJANE SMITH - Lead detective"]

        # Mock LLM client with invalid response
        mock_client = AsyncMock()
        mock_response = Mock(spec_set=["content"])
        mock_response.content = json.dumps(
            [
                {"aliases": ["JANE"]},  # No canonical
                "invalid",  # Not a dict
                {"canonical": "", "aliases": ["EMPTY"]},  # Empty canonical
            ]
        )
        mock_client.complete = AsyncMock(return_value=mock_response)

        extractor = BibleExtractor(llm_client=mock_client)
        characters = await extractor._extract_via_llm(chunks)

        assert characters == []

    @pytest.mark.asyncio
    async def test_extract_via_llm_response_without_content(self) -> None:
        """Test LLM extraction with response without content attribute."""
        chunks = ["Main Characters\nJANE SMITH - Lead detective"]

        # Mock LLM client with response as string
        mock_client = AsyncMock()
        mock_response = json.dumps([{"canonical": "JANE", "aliases": ["J"]}])
        mock_client.complete = AsyncMock(return_value=mock_response)

        extractor = BibleExtractor(llm_client=mock_client)
        characters = await extractor._extract_via_llm(chunks)

        assert len(characters) == 1
        assert characters[0].canonical == "JANE"

    def test_extract_json_array_pattern(self) -> None:
        """Test JSON extraction with array pattern."""
        extractor = BibleExtractor()

        response = 'Here is the data: [{"canonical": "JANE", "aliases": ["J"]}]'
        result = extractor._extract_json(response)

        assert len(result) == 1
        assert result[0]["canonical"] == "JANE"

    def test_extract_json_whole_response(self) -> None:
        """Test JSON extraction of whole response."""
        extractor = BibleExtractor()

        response = '[{"canonical": "JANE", "aliases": ["J"]}]'
        result = extractor._extract_json(response)

        assert len(result) == 1
        assert result[0]["canonical"] == "JANE"

    def test_extract_json_invalid_json(self) -> None:
        """Test JSON extraction with invalid JSON."""
        extractor = BibleExtractor()

        response = "This is not JSON"
        result = extractor._extract_json(response)

        assert result == []

    def test_extract_json_not_array(self) -> None:
        """Test JSON extraction when result is not an array."""
        extractor = BibleExtractor()

        response = '{"canonical": "JANE", "aliases": ["J"]}'
        result = extractor._extract_json(response)

        # This returns the original because it's valid JSON, just not an array
        # Only when it fails to parse as array does it return []
        assert result == []

    def test_normalize_characters_basic(self) -> None:
        """Test basic character normalization."""
        characters = [
            BibleCharacter(
                canonical="  jane smith  ",
                aliases=["jane", "  DETECTIVE SMITH  "],
                tags=["protagonist"],
                notes="Lead detective",
            )
        ]

        extractor = BibleExtractor()
        normalized = extractor._normalize_characters(characters)

        assert len(normalized) == 1
        char = normalized[0]
        assert char.canonical == "JANE SMITH"
        # JANE should be filtered out as it's the first name of the canonical
        assert "DETECTIVE SMITH" in char.aliases

    def test_normalize_characters_remove_duplicates(self) -> None:
        """Test character normalization removes duplicates."""
        characters = [
            BibleCharacter(
                canonical="JANE SMITH", aliases=["JANE", "JANE SMITH", "JANE"]
            ),
            BibleCharacter(
                canonical="JANE SMITH", aliases=["JANE"]
            ),  # Duplicate canonical
        ]

        extractor = BibleExtractor()
        normalized = extractor._normalize_characters(characters)

        # Should only have one character
        assert len(normalized) == 1
        char = normalized[0]
        assert char.canonical == "JANE SMITH"
        # Should not include canonical name in aliases,
        # first name filtered out for multi-part names
        assert char.aliases == []

    def test_normalize_characters_first_name_logic(self) -> None:
        """Test character normalization first name logic."""
        characters = [
            BibleCharacter(
                canonical="JANE SMITH", aliases=["JANE", "MS. SMITH", "DETECTIVE SMITH"]
            ),
            BibleCharacter(
                canonical="JOHN",  # Single name
                aliases=["JOHN", "JOHNNY"],
            ),
        ]

        extractor = BibleExtractor()
        normalized = extractor._normalize_characters(characters)

        assert len(normalized) == 2

        # For multi-part canonical, first name should be excluded from aliases
        jane = next(char for char in normalized if char.canonical == "JANE SMITH")
        assert "JANE" not in jane.aliases  # First name excluded
        assert "MS. SMITH" in jane.aliases
        assert "DETECTIVE SMITH" in jane.aliases

        # For single name canonical, alias should be kept if different
        john = next(char for char in normalized if char.canonical == "JOHN")
        assert "JOHNNY" in john.aliases
        assert "JOHN" not in john.aliases  # Matches canonical

    def test_normalize_characters_empty_aliases(self) -> None:
        """Test character normalization with empty/invalid aliases."""
        characters = [
            BibleCharacter(
                canonical="JANE", aliases=["", "   ", "JANE", "VALID_ALIAS", ""]
            )
        ]

        extractor = BibleExtractor()
        normalized = extractor._normalize_characters(characters)

        assert len(normalized) == 1
        char = normalized[0]
        assert char.aliases == ["VALID_ALIAS"]

    def test_create_empty_result(self) -> None:
        """Test creating empty result structure."""
        extractor = BibleExtractor()
        result = extractor._create_empty_result()

        assert result["version"] == 1
        assert result["characters"] == []
        assert "extracted_at" in result


class TestBibleExtractor:
    """Test the main BibleExtractor class with scene and combined extraction."""

    def test_init_with_llm_client(self) -> None:
        """Test BibleExtractor initialization with provided LLM client."""
        mock_client = Mock(spec=object)
        extractor = BibleExtractor(llm_client=mock_client)
        assert extractor.llm_client is mock_client

    def test_init_without_llm_client(self) -> None:
        """Test BibleExtractor initialization without LLM client."""
        with patch("scriptrag.api.bible_extraction.LLMClient") as mock_llm_class:
            mock_client = Mock(spec=object)
            mock_llm_class.return_value = mock_client

            extractor = BibleExtractor()
            assert extractor.llm_client is mock_client

    @pytest.mark.asyncio
    async def test_extract_scenes_from_bible_parse_error(self, tmp_path: Path) -> None:
        """Test scene extraction with parse error."""
        bible_path = tmp_path / "bad_bible.md"
        bible_path.write_text("# Test")

        extractor = BibleExtractor()

        # Mock parser to raise error
        with patch.object(
            extractor.bible_parser, "parse_file", side_effect=Exception("Parse failed")
        ):
            result = await extractor.extract_scenes_from_bible(bible_path)

            assert result["version"] == 1
            assert result["scenes"] == []
            assert "extracted_at" in result

    @pytest.mark.asyncio
    async def test_extract_scenes_from_bible_no_scene_chunks(
        self, tmp_path: Path
    ) -> None:
        """Test scene extraction when no scene chunks found."""
        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Test")

        # Create Bible with no scene-related content
        empty_bible = ParsedBible(
            file_path=bible_path,
            title="Empty Bible",
            file_hash="hash",
            metadata={},
            chunks=[
                BibleChunk(
                    chunk_number=0,
                    heading="Character Info",
                    level=1,
                    content="JANE SMITH - Detective",
                    content_hash="hash1",
                    metadata={},
                    parent_chunk_id=None,
                )
            ],
        )

        extractor = BibleExtractor()

        with patch.object(
            extractor.bible_parser, "parse_file", return_value=empty_bible
        ):
            result = await extractor.extract_scenes_from_bible(bible_path)

            assert result["version"] == 1
            assert result["scenes"] == []

    @pytest.mark.asyncio
    async def test_extract_scenes_from_bible_successful(self, tmp_path: Path) -> None:
        """Test successful scene extraction."""
        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Test")

        # Create Bible with scene content
        scene_bible = ParsedBible(
            file_path=bible_path,
            title="Scene Bible",
            file_hash="hash",
            metadata={},
            chunks=[
                BibleChunk(
                    chunk_number=0,
                    heading="Locations",
                    level=1,
                    content="Police Station - Main headquarters downtown",
                    content_hash="hash1",
                    metadata={},
                    parent_chunk_id=None,
                )
            ],
        )

        # Mock scene extraction with correct BibleScene structure
        mock_scene = BibleScene(
            location="POLICE STATION",
            type="INT",
            time="DAY",
            description="Main police station downtown",
        )

        extractor = BibleExtractor()

        with (
            patch.object(
                extractor.bible_parser, "parse_file", return_value=scene_bible
            ),
            patch.object(
                extractor.scene_extractor,
                "extract_scenes_via_llm",
                return_value=[mock_scene],
            ),
            patch.object(
                extractor.validator, "validate_bible_scene", return_value=True
            ),
        ):
            result = await extractor.extract_scenes_from_bible(bible_path)

            assert result["version"] == 1
            assert len(result["scenes"]) == 1
            scene = result["scenes"][0]
            assert scene["location"] == "POLICE STATION"
            assert scene["type"] == "INT"

    @pytest.mark.asyncio
    async def test_extract_scenes_from_bible_invalid_scenes(
        self, tmp_path: Path
    ) -> None:
        """Test scene extraction with invalid scene data."""
        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Test")

        # Create Bible with scene content
        scene_bible = ParsedBible(
            file_path=bible_path,
            title="Scene Bible",
            file_hash="hash",
            metadata={},
            chunks=[
                BibleChunk(
                    chunk_number=0,
                    heading="Locations",
                    level=1,
                    content="Police Station - Main headquarters downtown",
                    content_hash="hash1",
                    metadata={},
                    parent_chunk_id=None,
                )
            ],
        )

        # Mock scene extraction with invalid scene
        mock_scene = BibleScene(location="", type=None, time=None, description="")

        extractor = BibleExtractor()

        with (
            patch.object(
                extractor.bible_parser, "parse_file", return_value=scene_bible
            ),
            patch.object(
                extractor.scene_extractor,
                "extract_scenes_via_llm",
                return_value=[mock_scene],
            ),
            patch.object(
                extractor.validator, "validate_bible_scene", return_value=False
            ),
        ):
            result = await extractor.extract_scenes_from_bible(bible_path)

            assert result["version"] == 1
            assert result["scenes"] == []  # Invalid scenes filtered out

    @pytest.mark.asyncio
    async def test_extract_from_bible_characters_only(
        self, tmp_path: Path, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test combined extraction with characters only."""
        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Test")

        # Mock LLM client for character extraction
        mock_client = AsyncMock()
        mock_response = Mock(spec_set=["content"])
        mock_response.content = json.dumps(
            [
                {
                    "canonical": "JANE SMITH",
                    "aliases": ["JANE", "DETECTIVE SMITH"],
                    "tags": ["protagonist"],
                    "notes": "Lead detective",
                }
            ]
        )
        mock_client.complete = AsyncMock(return_value=mock_response)

        extractor = BibleExtractor(llm_client=mock_client)

        with patch.object(
            extractor.bible_parser, "parse_file", return_value=mock_parsed_bible
        ):
            result = await extractor.extract_from_bible(
                bible_path, extract_scenes=False
            )

            # Should contain character data but no scene data
            assert result["version"] == 1
            assert len(result["characters"]) == 1
            assert "scenes" not in result or result["scenes"] is None

    @pytest.mark.asyncio
    async def test_extract_from_bible_with_scenes(
        self, tmp_path: Path, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test combined extraction with both characters and scenes."""
        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Test")

        # Mock LLM client for character extraction
        mock_client = AsyncMock()
        mock_response = Mock(spec_set=["content"])
        mock_response.content = json.dumps(
            [
                {
                    "canonical": "JANE SMITH",
                    "aliases": ["JANE", "DETECTIVE SMITH"],
                    "tags": ["protagonist"],
                    "notes": "Lead detective",
                }
            ]
        )
        mock_client.complete = AsyncMock(return_value=mock_response)

        # Mock scene extraction with correct BibleScene structure
        mock_scene = BibleScene(
            location="POLICE STATION",
            type="INT",
            time="DAY",
            description="Police headquarters",
        )

        extractor = BibleExtractor(llm_client=mock_client)

        with (
            patch.object(
                extractor.bible_parser, "parse_file", return_value=mock_parsed_bible
            ),
            patch.object(
                extractor.scene_extractor,
                "extract_scenes_via_llm",
                return_value=[mock_scene],
            ),
            patch.object(
                extractor.validator, "validate_bible_scene", return_value=True
            ),
        ):
            result = await extractor.extract_from_bible(bible_path, extract_scenes=True)

            # Should contain both character and scene data
            assert result["version"] == 1
            assert len(result["characters"]) == 1
            assert len(result["scenes"]) == 1

            char = result["characters"][0]
            assert char["canonical"] == "JANE SMITH"

            scene = result["scenes"][0]
            assert scene["location"] == "POLICE STATION"


# Legacy alias tests removed - BibleCharacterExtractor alias has been removed
