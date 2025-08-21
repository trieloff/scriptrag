"""Unit tests for the CharacterRelationshipsAnalyzer."""

import pytest

from scriptrag.analyzers.relationships import CharacterRelationshipsAnalyzer


@pytest.fixture
def bible_characters():
    """Sample Bible character data for testing."""
    return {
        "version": 1,
        "extracted_at": "2025-08-20T08:00:00Z",
        "characters": [
            {
                "canonical": "JANE SMITH",
                "aliases": ["JANE", "MS. SMITH"],
                "tags": ["protagonist"],
            },
            {
                "canonical": "BOB JOHNSON",
                "aliases": ["BOB", "BOBBY", "MR. JOHNSON"],
            },
            {
                "canonical": "ALICE COOPER",
                "aliases": ["ALICE", "DR. COOPER"],
            },
        ],
    }


@pytest.fixture
def analyzer_with_bible(bible_characters):
    """Create analyzer with Bible data loaded."""
    config = {"bible_characters": bible_characters}
    return CharacterRelationshipsAnalyzer(config)


@pytest.fixture
def analyzer_without_bible():
    """Create analyzer without Bible data."""
    return CharacterRelationshipsAnalyzer()


class TestCharacterRelationshipsAnalyzer:
    """Test suite for CharacterRelationshipsAnalyzer."""

    @pytest.mark.asyncio
    async def test_analyzer_name_and_version(self, analyzer_with_bible):
        """Test analyzer has correct name and version."""
        assert analyzer_with_bible.name == "relationships"
        assert analyzer_with_bible.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_analyze_without_bible_returns_empty(self, analyzer_without_bible):
        """Test that analyzer returns empty result without Bible data."""
        scene = {
            "dialogue": [
                {"character": "JANE"},
                {"character": "BOB"},
            ],
            "action": ["Jane walks in.", "Bob follows."],
        }

        result = await analyzer_without_bible.analyze(scene)
        assert result == {}

    @pytest.mark.asyncio
    async def test_speaker_resolution(self, analyzer_with_bible):
        """Test that speakers are resolved to canonical names."""
        scene = {
            "dialogue": [
                {"character": "JANE"},
                {"character": "BOBBY"},
                {"character": "DR. COOPER"},
            ],
        }

        result = await analyzer_with_bible.analyze(scene)

        assert "JANE SMITH" in result["speaking"]
        assert "BOB JOHNSON" in result["speaking"]
        assert "ALICE COOPER" in result["speaking"]
        assert len(result["speaking"]) == 3

    @pytest.mark.asyncio
    async def test_speaker_normalization_with_parentheticals(self, analyzer_with_bible):
        """Test that parentheticals are removed from speaker names."""
        scene = {
            "dialogue": [
                {"character": "JANE (CONT'D)"},
                {"character": "BOB (O.S.)"},
                {"character": "ALICE (V.O.)"},
            ],
        }

        result = await analyzer_with_bible.analyze(scene)

        assert "JANE SMITH" in result["speaking"]
        assert "BOB JOHNSON" in result["speaking"]
        assert "ALICE COOPER" in result["speaking"]

    @pytest.mark.asyncio
    async def test_mention_detection_in_action(self, analyzer_with_bible):
        """Test detection of character mentions in action lines."""
        scene = {
            "dialogue": [],
            "action": [
                "Jane enters the room.",
                "Ms. Smith looks around.",
                "Bobby is already there.",
                "Dr. Cooper examines the evidence.",
            ],
        }

        result = await analyzer_with_bible.analyze(scene)

        assert "JANE SMITH" in result["present"]
        assert "BOB JOHNSON" in result["present"]
        assert "ALICE COOPER" in result["present"]
        assert len(result["present"]) == 3
        assert len(result["speaking"]) == 0

    @pytest.mark.asyncio
    async def test_mention_detection_in_heading(self, analyzer_with_bible):
        """Test detection of character mentions in scene headings."""
        scene = {
            "heading": "INT. JANE'S OFFICE - DAY",
            "dialogue": [],
            "action": [],
        }

        result = await analyzer_with_bible.analyze(scene)

        assert "JANE SMITH" in result["present"]
        assert len(result["present"]) == 1

    @pytest.mark.asyncio
    async def test_co_presence_pairs(self, analyzer_with_bible):
        """Test generation of co-presence pairs."""
        scene = {
            "dialogue": [
                {"character": "JANE"},
                {"character": "BOB"},
            ],
            "action": ["Alice watches from the corner."],
        }

        result = await analyzer_with_bible.analyze(scene)

        # Should have 3 pairs: (Alice, Bob), (Alice, Jane), (Bob, Jane)
        pairs = result["co_presence_pairs"]
        assert len(pairs) == 3

        # Check specific pairs (sorted alphabetically)
        assert ["ALICE COOPER", "BOB JOHNSON"] in pairs
        assert ["ALICE COOPER", "JANE SMITH"] in pairs
        assert ["BOB JOHNSON", "JANE SMITH"] in pairs

    @pytest.mark.asyncio
    async def test_speaking_edges(self, analyzer_with_bible):
        """Test generation of speaking edges."""
        scene = {
            "dialogue": [
                {"character": "JANE"},
                {"character": "BOB"},
            ],
            "action": ["Alice listens silently."],
        }

        result = await analyzer_with_bible.analyze(scene)

        edges = result["speaking_edges"]

        # Jane speaks to Bob and Alice
        assert ["JANE SMITH", "BOB JOHNSON"] in edges
        assert ["JANE SMITH", "ALICE COOPER"] in edges

        # Bob speaks to Jane and Alice
        assert ["BOB JOHNSON", "JANE SMITH"] in edges
        assert ["BOB JOHNSON", "ALICE COOPER"] in edges

        # Alice doesn't speak, so no edges from her
        assert not any(edge[0] == "ALICE COOPER" for edge in edges)

    @pytest.mark.asyncio
    async def test_stats_calculation(self, analyzer_with_bible):
        """Test that stats are correctly calculated."""
        scene = {
            "dialogue": [
                {"character": "JANE"},
            ],
            "action": ["Bob and Alice enter."],
        }

        result = await analyzer_with_bible.analyze(scene)

        assert result["stats"]["present_count"] == 3
        assert result["stats"]["speaking_count"] == 1

    @pytest.mark.asyncio
    async def test_word_boundary_matching(self, analyzer_with_bible):
        """Test that word boundaries are respected in matching."""
        scene = {
            "action": [
                "Jane walks in.",  # Should match
                "Janet walks in.",  # Should NOT match (Jane != Janet)
                "The plane lands.",  # Should NOT match (Jane is part of plane)
                "JANE enters.",  # Should match
            ],
        }

        result = await analyzer_with_bible.analyze(scene)

        assert "JANE SMITH" in result["present"]
        assert len(result["present"]) == 1  # Only Jane, not false matches

    @pytest.mark.asyncio
    async def test_multi_word_alias_matching(self, analyzer_with_bible):
        """Test that multi-word aliases are matched correctly."""
        scene = {
            "action": [
                "Ms. Smith reviews the documents.",
                "Dr. Cooper arrives.",
                "Mr. Johnson waits outside.",
            ],
        }

        result = await analyzer_with_bible.analyze(scene)

        assert "JANE SMITH" in result["present"]
        assert "ALICE COOPER" in result["present"]
        assert "BOB JOHNSON" in result["present"]
        assert len(result["present"]) == 3

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self, analyzer_with_bible):
        """Test that matching is case-insensitive."""
        scene = {
            "dialogue": [
                {"character": "jane"},  # lowercase
                {"character": "BOBBY"},  # uppercase
            ],
            "action": [
                "alice enters.",  # lowercase
                "MS. SMITH speaks.",  # uppercase
            ],
        }

        result = await analyzer_with_bible.analyze(scene)

        assert "JANE SMITH" in result["present"]
        assert "BOB JOHNSON" in result["present"]
        assert "ALICE COOPER" in result["present"]

    @pytest.mark.asyncio
    async def test_empty_scene(self, analyzer_with_bible):
        """Test handling of empty scene."""
        scene = {
            "dialogue": [],
            "action": [],
        }

        result = await analyzer_with_bible.analyze(scene)

        assert result["present"] == []
        assert result["speaking"] == []
        assert result["co_presence_pairs"] == []
        assert result["speaking_edges"] == []
        assert result["stats"]["present_count"] == 0
        assert result["stats"]["speaking_count"] == 0

    @pytest.mark.asyncio
    async def test_dialogue_string_format(self, analyzer_with_bible):
        """Test handling of dialogue in string format."""
        scene = {
            "dialogue": [
                "JANE: Hello there.",
                "BOB: Hi Jane!",
            ],
        }

        result = await analyzer_with_bible.analyze(scene)

        assert "JANE SMITH" in result["speaking"]
        assert "BOB JOHNSON" in result["speaking"]

    @pytest.mark.asyncio
    async def test_unknown_character_ignored(self, analyzer_with_bible):
        """Test that unknown characters are ignored."""
        scene = {
            "dialogue": [
                {"character": "JANE"},
                {"character": "UNKNOWN_CHARACTER"},
            ],
            "action": ["Some random person walks by."],
        }

        result = await analyzer_with_bible.analyze(scene)

        assert "JANE SMITH" in result["speaking"]
        assert "UNKNOWN_CHARACTER" not in result["speaking"]
        assert len(result["speaking"]) == 1
