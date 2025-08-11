"""Integration tests for script bible indexing functionality."""

from pathlib import Path

import pytest
import pytest_asyncio

from scriptrag.api.bible_index import BibleAutoDetector, BibleIndexer
from scriptrag.api.database import DatabaseInitializer
from scriptrag.api.index import IndexCommand
from scriptrag.parser.bible_parser import BibleParser
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import SearchQuery


@pytest.fixture
def bible_files(tmp_path: Path) -> dict[str, Path]:
    """Create test bible files."""
    files = {}

    # Main script bible
    bible_content = """# The Great Adventure - Script Bible

## World Overview

The story takes place in a post-apocalyptic underground city called Haven Prime.

## Characters

### SARAH CHEN
Lead Explorer, age 28. Driven by curiosity about the surface world.

### MARCUS STONE
Security Chief, age 32. Protective of the colony, haunted by past.
"""
    bible_path = tmp_path / "script_bible.md"
    bible_path.write_text(bible_content)
    files["main"] = bible_path

    # Character backstory file
    backstory_content = """# Character Backstories

## Sarah Chen

Sarah lost her parents during Expedition Seven. She discovered her mother's
journal containing references to Project Genesis.

## Marcus Stone

Marcus's last surface mission discovered evidence of government involvement
in the environmental collapse. He keeps this knowledge secret.
"""
    backstory_path = tmp_path / "character_backstory.md"
    backstory_path.write_text(backstory_content)
    files["backstory"] = backstory_path

    # World lore file
    lore_content = """# World Lore

## The Surface World

The Glass Deserts are former oceans turned to crystallized sand.
Glass Wolves are pack hunters made of semi-transparent material.

## Underground Civilization

Haven Prime has a population of 50,000 living 500 meters underground.
"""
    lore_path = tmp_path / "world_lore.md"
    lore_path.write_text(lore_content)
    files["lore"] = lore_path

    return files


@pytest.fixture
def test_script(tmp_path: Path) -> Path:
    """Create a test fountain script."""
    script_content = """Title: The Great Adventure
Author: Test Author

# ACT ONE

## Scene 1

INT. HAVEN PRIME - CONTROL ROOM - DAY

Sarah studies maps of the surface world.

SARAH
We need to go back up there.

MARCUS
It's too dangerous.
"""
    script_path = tmp_path / "script.fountain"
    script_path.write_text(script_content)
    return script_path


class TestBibleParser:
    """Test the markdown bible parser."""

    def test_parse_simple_bible(self, bible_files: dict[str, Path]) -> None:
        """Test parsing a simple bible file."""
        parser = BibleParser()
        result = parser.parse_file(bible_files["main"])

        assert result.title == "The Great Adventure - Script Bible"
        assert len(result.chunks) > 0
        assert result.file_hash is not None

        # Check chunk structure
        first_chunk = result.chunks[0]
        assert first_chunk.heading == "The Great Adventure - Script Bible"
        assert first_chunk.level == 1
        assert first_chunk.content_hash is not None

    def test_parse_with_hierarchy(self, bible_files: dict[str, Path]) -> None:
        """Test parsing maintains heading hierarchy."""
        parser = BibleParser()
        result = parser.parse_file(bible_files["main"])

        # Find chunks with different heading levels
        h1_chunks = [c for c in result.chunks if c.level == 1]
        h2_chunks = [c for c in result.chunks if c.level == 2]
        h3_chunks = [c for c in result.chunks if c.level == 3]

        assert len(h1_chunks) > 0  # Has H1 heading
        assert len(h2_chunks) > 0  # Has H2 headings
        assert len(h3_chunks) > 0  # Has H3 headings

    def test_chunk_content_hash(self, bible_files: dict[str, Path]) -> None:
        """Test that chunk content hashes are unique and stable."""
        parser = BibleParser()
        result1 = parser.parse_file(bible_files["main"])
        result2 = parser.parse_file(bible_files["main"])

        # Same content should produce same hashes
        for chunk1, chunk2 in zip(result1.chunks, result2.chunks, strict=False):
            assert chunk1.content_hash == chunk2.content_hash

        # Different chunks should have different hashes
        unique_hashes = {c.content_hash for c in result1.chunks}
        assert len(unique_hashes) == len(result1.chunks)


class TestBibleAutoDetector:
    """Test automatic bible file detection."""

    def test_detect_bible_files(self, tmp_path: Path) -> None:
        """Test detecting bible files by pattern."""
        # Create various markdown files
        (tmp_path / "script_bible.md").touch()
        (tmp_path / "character_notes.md").touch()
        (tmp_path / "world_building.md").touch()
        (tmp_path / "README.md").touch()  # Should be excluded
        (tmp_path / "CHANGELOG.md").touch()  # Should be excluded

        detected = BibleAutoDetector.find_bible_files(tmp_path)

        # Should find bible-related files but not README/CHANGELOG
        detected_names = {f.name for f in detected}
        assert "script_bible.md" in detected_names
        assert "character_notes.md" in detected_names
        assert "world_building.md" in detected_names
        assert "README.md" not in detected_names
        assert "CHANGELOG.md" not in detected_names

    def test_detect_in_subdirectories(self, tmp_path: Path) -> None:
        """Test detecting bible files in subdirectories."""
        # Create docs directory with bible files
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "lore.md").touch()
        (docs_dir / "backstory.md").touch()

        # Create hidden directory (should be excluded)
        hidden_dir = tmp_path / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "bible.md").touch()

        detected = BibleAutoDetector.find_bible_files(tmp_path)

        detected_paths = {str(f.relative_to(tmp_path)) for f in detected}
        assert "docs/lore.md" in detected_paths
        assert "docs/backstory.md" in detected_paths
        assert ".hidden/bible.md" not in detected_paths


@pytest_asyncio.fixture
async def initialized_db(tmp_path: Path) -> Path:
    """Create and initialize a test database."""
    db_path = tmp_path / "test.db"
    initializer = DatabaseInitializer()
    initializer.initialize_database(db_path, force=True)
    return db_path


class TestBibleIndexing:
    """Test bible indexing functionality."""

    @pytest.mark.asyncio
    async def test_index_single_bible(
        self,
        initialized_db: Path,
        bible_files: dict[str, Path],
        test_script: Path,
    ) -> None:
        """Test indexing a single bible document."""
        # First index the script
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=initialized_db)
        index_cmd = IndexCommand(settings=settings)
        await index_cmd.index(test_script.parent, recursive=False)

        # Now index the bible
        indexer = BibleIndexer(settings=settings)
        result = await indexer.index_bible(
            bible_path=bible_files["main"],
            script_id=1,  # Assuming first script has ID 1
        )

        assert result.indexed is True
        assert result.chunks_indexed > 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_reindex_unchanged_bible(
        self,
        initialized_db: Path,
        bible_files: dict[str, Path],
        test_script: Path,
    ) -> None:
        """Test that unchanged bible is not re-indexed."""
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=initialized_db)

        # Index script first
        index_cmd = IndexCommand(settings=settings)
        await index_cmd.index(test_script.parent, recursive=False)

        indexer = BibleIndexer(settings=settings)

        # First indexing
        result1 = await indexer.index_bible(bible_files["main"], script_id=1)
        assert result1.indexed is True

        # Second indexing (should skip)
        result2 = await indexer.index_bible(bible_files["main"], script_id=1)
        assert result2.indexed is False
        assert result2.updated is False

    @pytest.mark.asyncio
    async def test_force_reindex(
        self,
        initialized_db: Path,
        bible_files: dict[str, Path],
        test_script: Path,
    ) -> None:
        """Test force re-indexing of bible."""
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=initialized_db)

        # Index script
        index_cmd = IndexCommand(settings=settings)
        await index_cmd.index(test_script.parent, recursive=False)

        indexer = BibleIndexer(settings=settings)

        # First indexing
        result1 = await indexer.index_bible(bible_files["main"], script_id=1)
        assert result1.indexed is True

        # Force re-index
        result2 = await indexer.index_bible(
            bible_files["main"], script_id=1, force=True
        )
        assert result2.updated is True
        assert result2.chunks_indexed > 0


class TestBibleSearch:
    """Test searching bible content."""

    @pytest.mark.asyncio
    async def test_search_bible_content(
        self,
        initialized_db: Path,
        bible_files: dict[str, Path],
        test_script: Path,
    ) -> None:
        """Test searching for content in bible."""
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=initialized_db)

        # Index script and bible
        index_cmd = IndexCommand(settings=settings)
        await index_cmd.index(test_script.parent, recursive=False)

        indexer = BibleIndexer(settings=settings)
        await indexer.index_bible(bible_files["main"], script_id=1)
        await indexer.index_bible(bible_files["backstory"], script_id=1)

        # Search for content
        engine = SearchEngine(settings)
        query = SearchQuery(
            raw_query="Project Genesis",
            text_query="Project Genesis",
            include_bible=True,
        )
        response = engine.search(query)

        assert len(response.bible_results) > 0
        assert any("Project Genesis" in r.chunk_content for r in response.bible_results)

    @pytest.mark.asyncio
    async def test_search_only_bible(
        self,
        initialized_db: Path,
        bible_files: dict[str, Path],
        test_script: Path,
    ) -> None:
        """Test searching only bible content."""
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=initialized_db)

        # Index everything
        index_cmd = IndexCommand(settings=settings)
        await index_cmd.index(test_script.parent, recursive=False)

        indexer = BibleIndexer(settings=settings)
        await indexer.index_bible(bible_files["main"], script_id=1)

        # Search only bible
        engine = SearchEngine(settings)
        query = SearchQuery(
            raw_query="underground",
            text_query="underground",
            only_bible=True,
        )
        response = engine.search(query)

        assert len(response.results) == 0  # No script results
        assert len(response.bible_results) > 0  # Only bible results

    @pytest.mark.asyncio
    async def test_exclude_bible_from_search(
        self,
        initialized_db: Path,
        bible_files: dict[str, Path],
        test_script: Path,
    ) -> None:
        """Test excluding bible from search results."""
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=initialized_db)

        # Index everything
        index_cmd = IndexCommand(settings=settings)
        await index_cmd.index(test_script.parent, recursive=False)

        indexer = BibleIndexer(settings=settings)
        await indexer.index_bible(bible_files["main"], script_id=1)

        # Search without bible
        engine = SearchEngine(settings)
        query = SearchQuery(
            raw_query="Sarah",
            text_query="Sarah",
            include_bible=False,
        )
        response = engine.search(query)

        assert len(response.bible_results) == 0  # No bible results
        # Script results may or may not exist depending on content

    @pytest.mark.asyncio
    async def test_bible_chunk_hierarchy(
        self,
        initialized_db: Path,
        bible_files: dict[str, Path],
        test_script: Path,
    ) -> None:
        """Test that bible chunk hierarchy is maintained."""
        from scriptrag.config import ScriptRAGSettings

        settings = ScriptRAGSettings(database_path=initialized_db)

        # Index script and bible
        index_cmd = IndexCommand(settings=settings)
        await index_cmd.index(test_script.parent, recursive=False)

        indexer = BibleIndexer(settings=settings)
        result = await indexer.index_bible(bible_files["main"], script_id=1)

        # Verify chunks were created with proper hierarchy
        assert result.chunks_indexed > 0

        # Search for hierarchical content
        engine = SearchEngine(settings)
        query = SearchQuery(
            raw_query="Characters",
            text_query="Characters",
            include_bible=True,
        )
        response = engine.search(query)

        # Should find the Characters section
        character_results = [
            r for r in response.bible_results if "Characters" in (r.chunk_heading or "")
        ]
        assert len(character_results) > 0
