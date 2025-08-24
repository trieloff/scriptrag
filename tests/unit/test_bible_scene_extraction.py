"""Tests for scene bible extraction module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.api.bible.scene_bible import BibleScene, SceneBibleExtractor
from scriptrag.parser.bible_parser import BibleChunk, ParsedBible


class TestBibleScene:
    """Test BibleScene dataclass."""

    def test_bible_scene_creation(self) -> None:
        """Test creating a BibleScene with all fields."""
        scene = BibleScene(
            location="POLICE STATION",
            type="INT",
            time="DAY",
            description="Modern downtown precinct",
        )
        assert scene.location == "POLICE STATION"
        assert scene.type == "INT"
        assert scene.time == "DAY"
        assert scene.description == "Modern downtown precinct"

    def test_bible_scene_defaults(self) -> None:
        """Test BibleScene with default values."""
        scene = BibleScene(location="OFFICE")
        assert scene.location == "OFFICE"
        assert scene.type is None
        assert scene.time is None
        assert scene.description is None


class TestSceneBibleExtractor:
    """Test SceneBibleExtractor class."""

    def test_init_with_llm_client(self) -> None:
        """Test initialization with provided LLM client."""
        mock_client = MagicMock()
        extractor = SceneBibleExtractor(llm_client=mock_client)
        assert extractor.llm_client == mock_client
        assert extractor.bible_parser is not None

    def test_init_without_llm_client(self) -> None:
        """Test initialization without LLM client (uses default)."""
        with patch("scriptrag.api.bible.scene_bible.LLMClient") as mock_llm:
            extractor = SceneBibleExtractor()
            mock_llm.assert_called_once()
            assert extractor.llm_client == mock_llm.return_value

    def test_find_scene_chunks_by_heading(self) -> None:
        """Test finding chunks with scene-related headings."""
        chunks = [
            BibleChunk(
                chunk_number=0,
                heading="Locations",
                level=1,
                content="Various locations in the story",
                content_hash="hash1",
            ),
            BibleChunk(
                chunk_number=1,
                heading="Characters",
                level=1,
                content="Main characters",
                content_hash="hash2",
            ),
            BibleChunk(
                chunk_number=2,
                heading="Scene Settings",
                level=1,
                content="Important settings",
                content_hash="hash3",
            ),
        ]
        parsed_bible = ParsedBible(
            file_path=Path("test.md"),
            title="Test",
            chunks=chunks,
            file_hash="hash",
        )

        extractor = SceneBibleExtractor()
        result = extractor.find_scene_chunks(parsed_bible)

        assert len(result) == 2
        assert "Locations\nVarious locations in the story" in result
        assert "Scene Settings\nImportant settings" in result

    def test_find_scene_chunks_by_content(self) -> None:
        """Test finding chunks with scene keywords in content."""
        chunks = [
            BibleChunk(
                chunk_number=0,
                heading="Overview",
                level=1,
                content="The main location is a police station",
                content_hash="hash1",
            ),
            BibleChunk(
                chunk_number=1,
                heading="Notes",
                level=1,
                content="Random notes without keywords",
                content_hash="hash2",
            ),
            BibleChunk(
                chunk_number=2,
                heading=None,
                level=0,
                content="The scene takes place in various settings",
                content_hash="hash3",
            ),
        ]
        parsed_bible = ParsedBible(
            file_path=Path("test.md"),
            title="Test",
            chunks=chunks,
            file_hash="hash",
        )

        extractor = SceneBibleExtractor()
        result = extractor.find_scene_chunks(parsed_bible)

        assert len(result) == 2
        assert any("police station" in chunk for chunk in result)
        assert any("scene takes place" in chunk for chunk in result)

    def test_find_scene_chunks_no_matches(self) -> None:
        """Test when no chunks match scene criteria."""
        chunks = [
            BibleChunk(
                chunk_number=0,
                heading="Random",
                level=1,
                content="Nothing relevant here",
                content_hash="hash1",
            ),
        ]
        parsed_bible = ParsedBible(
            file_path=Path("test.md"),
            title="Test",
            chunks=chunks,
            file_hash="hash",
        )

        extractor = SceneBibleExtractor()
        result = extractor.find_scene_chunks(parsed_bible)
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_scenes_via_llm_success(self) -> None:
        """Test successful scene extraction via LLM."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = """
        [
            {
                "location": "POLICE STATION",
                "type": "INT",
                "time": "DAY",
                "description": "Modern precinct"
            },
            {
                "location": "COFFEE SHOP",
                "type": "EXT",
                "time": "NIGHT",
                "description": "Small neighborhood cafe"
            }
        ]
        """
        mock_client.complete.return_value = mock_response

        extractor = SceneBibleExtractor(llm_client=mock_client)
        chunks = ["Scene 1: Police station interior", "Scene 2: Coffee shop exterior"]

        result = await extractor.extract_scenes_via_llm(chunks)

        assert len(result) == 2
        assert isinstance(result[0], BibleScene)
        assert result[0].location == "POLICE STATION"
        assert result[0].type == "INT"
        assert result[0].time == "DAY"
        assert result[0].description == "Modern precinct"

        assert result[1].location == "COFFEE SHOP"
        assert result[1].type == "EXT"

    @pytest.mark.asyncio
    async def test_extract_scenes_via_llm_empty_chunks(self) -> None:
        """Test extraction with empty chunks."""
        extractor = SceneBibleExtractor()
        result = await extractor.extract_scenes_via_llm([])
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_scenes_via_llm_invalid_response(self) -> None:
        """Test extraction with invalid LLM response."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "This is not valid JSON"
        mock_client.complete.return_value = mock_response

        extractor = SceneBibleExtractor(llm_client=mock_client)
        result = await extractor.extract_scenes_via_llm(["Some chunk"])
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_scenes_via_llm_missing_location(self) -> None:
        """Test extraction skips scenes without location."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = """
        [
            {"location": "OFFICE", "type": "INT"},
            {"type": "EXT", "description": "Missing location"},
            {"location": "", "type": "INT"},
            {"location": "STREET", "type": "EXT"}
        ]
        """
        mock_client.complete.return_value = mock_response

        extractor = SceneBibleExtractor(llm_client=mock_client)
        result = await extractor.extract_scenes_via_llm(["Chunks"])

        assert len(result) == 2
        assert result[0].location == "OFFICE"
        assert result[1].location == "STREET"

    @pytest.mark.asyncio
    async def test_extract_scenes_via_llm_exception_handling(self) -> None:
        """Test extraction handles exceptions gracefully."""
        mock_client = AsyncMock()
        mock_client.complete.side_effect = Exception("LLM API error")

        extractor = SceneBibleExtractor(llm_client=mock_client)
        result = await extractor.extract_scenes_via_llm(["Some chunk"])
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_scenes_via_llm_response_without_content_attr(self) -> None:
        """Test extraction when response doesn't have content attribute."""
        mock_client = AsyncMock()
        mock_response = '[{"location": "HOUSE", "type": "INT"}]'
        mock_client.complete.return_value = mock_response

        extractor = SceneBibleExtractor(llm_client=mock_client)
        result = await extractor.extract_scenes_via_llm(["Chunk"])

        assert len(result) == 1
        assert result[0].location == "HOUSE"

    @pytest.mark.asyncio
    async def test_extract_scenes_via_llm_uppercase_location(self) -> None:
        """Test that locations are converted to uppercase."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '[{"location": "police station", "type": "INT"}]'
        mock_client.complete.return_value = mock_response

        extractor = SceneBibleExtractor(llm_client=mock_client)
        result = await extractor.extract_scenes_via_llm(["Chunk"])

        assert len(result) == 1
        assert result[0].location == "POLICE STATION"

    @pytest.mark.asyncio
    async def test_extract_scenes_via_llm_invalid_dict_items(self) -> None:
        """Test extraction skips non-dict items in response."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = """
        [
            {"location": "OFFICE", "type": "INT"},
            "This is not a dict",
            null,
            {"location": "STREET", "type": "EXT"}
        ]
        """
        mock_client.complete.return_value = mock_response

        extractor = SceneBibleExtractor(llm_client=mock_client)
        result = await extractor.extract_scenes_via_llm(["Chunk"])

        assert len(result) == 2
        assert result[0].location == "OFFICE"
        assert result[1].location == "STREET"
