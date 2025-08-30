"""Unit tests for CharacterRelationshipsAnalyzer."""

from unittest.mock import Mock, patch

import pytest

from tests.unit.helpers.relationship_test_utils import (
    RelationshipTestData,
    RelationshipTestHelpers,
    SceneTestData,
)


@pytest.mark.asyncio
async def test_relationships_analyzer_basic_resolution():
    """Speakers and mentions resolve via exact alias matches with boundaries."""
    # Use shared test data
    bible_characters = RelationshipTestData.basic_bible_characters()

    analyzer = await RelationshipTestHelpers.create_initialized_analyzer(
        bible_characters
    )

    # Create a custom scene for this specific test case
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

    # Use helper to check result structure
    RelationshipTestHelpers.assert_relationship_result_structure(result)

    # Resolution checks:
    # - Ms. Smith -> JANE SMITH
    # - Mr. Johnson -> BOB JOHNSON
    # - 'Bobbin' ignored
    RelationshipTestHelpers.assert_characters_present(
        result, {"JANE SMITH", "BOB JOHNSON"}
    )
    RelationshipTestHelpers.assert_characters_speaking(result, {"JANE SMITH"})
    assert result["co_presence_pairs"] == [["BOB JOHNSON", "JANE SMITH"]]
    assert result["speaking_edges"] == [
        ["JANE SMITH", "BOB JOHNSON"],
    ]


@pytest.mark.asyncio
async def test_relationships_analyzer_no_bible_map_noop():
    """If no alias map provided or found, analyzer returns empty result."""
    analyzer = await RelationshipTestHelpers.create_initialized_analyzer(None)
    empty_scene = SceneTestData.empty_scene()
    result = await analyzer.analyze(empty_scene)
    assert result == {}


# Additional tests for 99% coverage


def test_analyzer_name_property():
    """Test the name property returns correct value."""
    analyzer = RelationshipTestHelpers.create_analyzer_with_config(None)
    assert analyzer.name == "relationships"


def test_ensure_index_from_db_early_return():
    """Test _ensure_index_from_db early return when index exists."""
    analyzer = RelationshipTestHelpers.create_analyzer_with_config(None)
    # Set _index to simulate already loaded
    analyzer._index = Mock(spec=object)
    analyzer._index.alias_to_canonical = {"TEST": "TEST"}

    # Should return early without DB access
    analyzer._ensure_index_from_db()
    # Index should remain unchanged
    assert analyzer._index.alias_to_canonical == {"TEST": "TEST"}


@pytest.mark.asyncio
async def test_analyze_fallback_to_db_when_no_config():
    """Test analyze method falls back to DB when no config and no index."""
    analyzer = RelationshipTestHelpers.create_analyzer_with_config(None)
    analyzer.script = Mock(spec=object)
    analyzer.script.metadata = {"source_file": "/path/to/script.fountain"}

    # Mock database to return empty result
    with patch("sqlite3.connect") as mock_connect:
        mock_conn = RelationshipTestHelpers.mock_db_with_bible_data(None)
        mock_connect.return_value = mock_conn

        empty_scene = SceneTestData.empty_scene()
        result = await analyzer.analyze(empty_scene)

        # Should return empty dict when no bible data found
        assert result == {}


def test_scan_mentions_with_no_matches():
    """Test _scan_mentions when no patterns match."""
    bible_characters = RelationshipTestData.minimal_bible_characters()
    # Override with specific test data
    bible_characters["characters"] = [
        {"canonical": "JANE SMITH", "aliases": ["JANE"]},
    ]
    analyzer = RelationshipTestHelpers.create_analyzer_with_config(bible_characters)

    # Text with no character mentions
    text = "The building is empty. No one is here."
    mentions = analyzer._scan_mentions(text)

    assert mentions == set()


@pytest.mark.asyncio
async def test_analyze_initialize_and_db_fallback_both_trigger():
    """Test analyze method when both initialize and DB fallback are needed."""
    analyzer = RelationshipTestHelpers.create_analyzer_with_config(None)
    # Don't set any config or script - should trigger both fallback paths

    empty_scene = SceneTestData.empty_scene()
    result = await analyzer.analyze(empty_scene)

    # Should return empty dict when no bible data found anywhere
    assert result == {}


def test_scan_mentions_with_no_canonical_mapping():
    """Test _scan_mentions when pattern matches but no canonical mapping."""
    analyzer = RelationshipTestHelpers.create_analyzer_with_config(None)
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
    bible_characters = RelationshipTestData.minimal_bible_characters()
    # Override with specific test data
    bible_characters["characters"] = [
        {"canonical": "JANE SMITH", "aliases": ["JANE"]},
    ]
    analyzer = RelationshipTestHelpers.create_analyzer_with_config(bible_characters)

    # Internal index should be populated during initialization
    assert analyzer._index is not None
    assert analyzer._index.alias_to_canonical["JANE"] == "JANE SMITH"
    assert analyzer._index.alias_to_canonical["JANE SMITH"] == "JANE SMITH"
