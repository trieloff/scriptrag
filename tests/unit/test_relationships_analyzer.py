"""Unit tests for CharacterRelationshipsAnalyzer."""

from datetime import datetime

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
