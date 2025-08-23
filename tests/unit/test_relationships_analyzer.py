"""Unit tests for CharacterRelationshipsAnalyzer."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from scriptrag.analyzers.relationships import CharacterRelationshipsAnalyzer


@pytest.mark.asyncio
async def test_relationships_analyzer_basic_resolution():
    """Speakers and mentions resolve via exact alias matches with boundaries."""
    # Seed bible characters directly via analyzer config (no DB access)
    bible_characters = {
        "version": 1,
        "extracted_at": datetime.utcnow().isoformat() + "Z",
        "characters": [
            {"canonical": "JANE SMITH", "aliases": ["JANE", "MS. SMITH"]},
            {
                "canonical": "BOB JOHNSON",
                "aliases": ["BOB", "BOBBY", "MR. JOHNSON"],
            },
        ],
    }

    analyzer = CharacterRelationshipsAnalyzer(
        config={"bible_characters": bible_characters}
    )
    await analyzer.initialize()

    scene = {
        "heading": "INT. APARTMENT - DAY",
        "dialogue": [
            {"character": "Jane (CONT'D)", "text": "We have to go."},
        ],
        "action": [
            "Ms. Smith gathers her things.",
            "Mr. Johnson waves from the hallway.",
            "Bobbin is nowhere to be seen.",
        ],
    }

    result = await analyzer.analyze(scene)

    # Basic shape
    assert "present" in result
    assert "speaking" in result
    assert "co_presence_pairs" in result
    assert "speaking_edges" in result
    assert result["stats"]["present_count"] == len(result["present"])  # type: ignore[index]

    # Resolution checks:
    # - Ms. Smith -> JANE SMITH
    # - Mr. Johnson -> BOB JOHNSON
    # - 'Bobbin' ignored
    assert set(result["present"]) == {"JANE SMITH", "BOB JOHNSON"}
    assert set(result["speaking"]) == {"JANE SMITH"}
    assert result["co_presence_pairs"] == [["BOB JOHNSON", "JANE SMITH"]]
    assert result["speaking_edges"] == [
        ["JANE SMITH", "BOB JOHNSON"],
    ]


@pytest.mark.asyncio
async def test_relationships_analyzer_no_bible_map_noop():
    """If no alias map provided or found, analyzer returns empty result."""
    analyzer = CharacterRelationshipsAnalyzer()
    await analyzer.initialize()
    result = await analyzer.analyze(
        {"heading": "INT. ROOM - DAY", "dialogue": [], "action": []}
    )
    assert result == {}


# Additional tests for 99% coverage


def test_analyzer_name_property():
    """Test the name property returns correct value."""
    analyzer = CharacterRelationshipsAnalyzer()
    assert analyzer.name == "relationships"


def test_ensure_index_from_db_early_return():
    """Test _ensure_index_from_db early return when index exists."""
    analyzer = CharacterRelationshipsAnalyzer()
    # Set _index to simulate already loaded
    analyzer._index = Mock()
    analyzer._index.alias_to_canonical = {"TEST": "TEST"}

    # Should return early without DB access
    analyzer._ensure_index_from_db()
    # Index should remain unchanged
    assert analyzer._index.alias_to_canonical == {"TEST": "TEST"}


@pytest.mark.asyncio
async def test_analyze_fallback_to_db_when_no_config():
    """Test analyze method falls back to DB when no config and no index."""
    analyzer = CharacterRelationshipsAnalyzer()
    analyzer.script = Mock()
    analyzer.script.metadata = {"source_file": "/path/to/script.fountain"}

    # Mock database to return empty result
    with patch("sqlite3.connect") as mock_connect:
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_connect.return_value = mock_conn

        scene = {"dialogue": [], "action": []}
        result = await analyzer.analyze(scene)

        # Should return empty dict when no bible data found
        assert result == {}


def test_scan_mentions_with_no_matches():
    """Test _scan_mentions when no patterns match."""
    bible_characters = {
        "version": 1,
        "characters": [
            {"canonical": "JANE SMITH", "aliases": ["JANE"]},
        ],
    }
    analyzer = CharacterRelationshipsAnalyzer(
        config={"bible_characters": bible_characters}
    )

    # Text with no character mentions
    text = "The building is empty. No one is here."
    mentions = analyzer._scan_mentions(text)

    assert mentions == set()


@pytest.mark.asyncio
async def test_analyze_initialize_and_db_fallback_both_trigger():
    """Test analyze method when both initialize and DB fallback are needed."""
    analyzer = CharacterRelationshipsAnalyzer()
    # Don't set any config or script - should trigger both fallback paths

    scene = {"dialogue": [], "action": []}
    result = await analyzer.analyze(scene)

    # Should return empty dict when no bible data found anywhere
    assert result == {}


def test_scan_mentions_with_no_canonical_mapping():
    """Test _scan_mentions when pattern matches but no canonical mapping."""
    analyzer = CharacterRelationshipsAnalyzer()
    # Create index with pattern but no canonical mapping
    import re

    from scriptrag.analyzers.relationships import _AliasIndex

    patterns = [(re.compile(r"ORPHAN", re.IGNORECASE), "ORPHAN")]
    analyzer._index = _AliasIndex({}, set(), patterns)  # Empty alias_to_canonical

    text = "ORPHAN appears"
    mentions = analyzer._scan_mentions(text)

    # Should return empty set when pattern matches but no canonical found
    assert mentions == set()


def test_internal_alias_index_access():
    """Test accessing alias index through internal _index when properly initialized."""
    bible_characters = {
        "version": 1,
        "characters": [
            {"canonical": "JANE SMITH", "aliases": ["JANE"]},
        ],
    }
    analyzer = CharacterRelationshipsAnalyzer(
        config={"bible_characters": bible_characters}
    )

    # Internal index should be populated during initialization
    assert analyzer._index is not None
    assert analyzer._index.alias_to_canonical["JANE"] == "JANE SMITH"
    assert analyzer._index.alias_to_canonical["JANE SMITH"] == "JANE SMITH"
