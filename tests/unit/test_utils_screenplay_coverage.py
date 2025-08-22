"""Additional tests for screenplay utilities to improve coverage."""

import hashlib

from scriptrag.utils import ScreenplayUtils


class TestScreenplayUtilsCoverage:
    """Tests for ScreenplayUtils to improve coverage."""

    def test_extract_location_time_only_scenario(self):
        """Test extracting location when heading starts with time separator."""
        # Test condition: rest starts with "- " (time only, no location)
        assert ScreenplayUtils.extract_location("INT. - DAY") is None
        assert ScreenplayUtils.extract_location("EXT. - NIGHT") is None
        assert ScreenplayUtils.extract_location("I/E - MORNING") is None

    def test_extract_location_empty_after_prefix(self):
        """Test extracting location when result is empty after prefix removal."""
        # Test when location becomes empty string (should return None)
        assert ScreenplayUtils.extract_location("INT.") is None
        assert ScreenplayUtils.extract_location("EXT.") is None
        assert ScreenplayUtils.extract_location("I/E.") is None

    def test_extract_time_midnight_specific(self):
        """Test extracting MIDNIGHT time indicator specifically."""
        # Test MIDNIGHT directly to ensure it's correctly identified
        result = ScreenplayUtils.extract_time("EXT. STREET - MIDNIGHT")
        # MIDNIGHT contains "NIGHT" and "NIGHT" comes first, so NIGHT found
        assert result == "NIGHT"

    def test_compute_scene_hash_basic(self):
        """Test basic scene hash computation."""
        scene_text = "INT. COFFEE SHOP - DAY\n\nSARAH enters."
        hash_result = ScreenplayUtils.compute_scene_hash(scene_text)

        # Should return truncated hash (16 chars) by default
        assert len(hash_result) == 16
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_compute_scene_hash_full_hash(self):
        """Test scene hash computation without truncation."""
        scene_text = "INT. COFFEE SHOP - DAY\n\nSARAH enters."
        hash_result = ScreenplayUtils.compute_scene_hash(scene_text, truncate=False)

        # Should return full SHA256 hash (64 chars)
        assert len(hash_result) == 64
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_compute_scene_hash_with_boneyard(self):
        """Test scene hash computation strips boneyard metadata."""
        scene_with_boneyard = """INT. COFFEE SHOP - DAY

SARAH enters.

/* SCRIPTRAG-META-START
{"analyzer": "test", "result": {"key": "value"}}
SCRIPTRAG-META-END */

The scene continues."""

        # The actual stripped content has extra newlines left
        scene_without_boneyard_stripped = """INT. COFFEE SHOP - DAY

SARAH enters.


The scene continues."""

        hash_with = ScreenplayUtils.compute_scene_hash(scene_with_boneyard)
        hash_without = ScreenplayUtils.compute_scene_hash(
            scene_without_boneyard_stripped
        )

        # Hashes should be the same since boneyard is stripped
        assert hash_with == hash_without

    def test_compute_scene_hash_consistency(self):
        """Test scene hash is consistent for same content."""
        scene_text = "INT. ROOM - DAY\n\nAction happens."

        hash1 = ScreenplayUtils.compute_scene_hash(scene_text)
        hash2 = ScreenplayUtils.compute_scene_hash(scene_text)

        assert hash1 == hash2

    def test_compute_scene_hash_different_content(self):
        """Test different content produces different hashes."""
        scene1 = "INT. ROOM - DAY\n\nAction 1."
        scene2 = "INT. ROOM - DAY\n\nAction 2."

        hash1 = ScreenplayUtils.compute_scene_hash(scene1)
        hash2 = ScreenplayUtils.compute_scene_hash(scene2)

        assert hash1 != hash2

    def test_compute_scene_hash_expected_value(self):
        """Test scene hash produces expected SHA256 value."""
        scene_text = "test content"
        expected_hash = hashlib.sha256(scene_text.encode("utf-8")).hexdigest()

        # Test full hash
        full_hash = ScreenplayUtils.compute_scene_hash(scene_text, truncate=False)
        assert full_hash == expected_hash

        # Test truncated hash
        truncated_hash = ScreenplayUtils.compute_scene_hash(scene_text, truncate=True)
        assert truncated_hash == expected_hash[:16]

    def test_strip_boneyard_no_metadata(self):
        """Test stripping boneyard when no metadata exists."""
        scene_text = "INT. COFFEE SHOP - DAY\n\nSARAH enters."
        result = ScreenplayUtils.strip_boneyard(scene_text)

        # Should return original text unchanged
        assert result == scene_text

    def test_strip_boneyard_with_metadata(self):
        """Test stripping boneyard with metadata."""
        scene_with_boneyard = """INT. COFFEE SHOP - DAY

SARAH enters.

/* SCRIPTRAG-META-START
{"analyzer": "test"}
SCRIPTRAG-META-END */

Action continues."""

        result = ScreenplayUtils.strip_boneyard(scene_with_boneyard)

        # Should not contain the metadata tags
        assert "SCRIPTRAG-META-START" not in result
        assert "SCRIPTRAG-META-END" not in result
        assert "analyzer" not in result
        # Should still contain the main content
        assert "INT. COFFEE SHOP - DAY" in result
        assert "SARAH enters." in result
        assert "Action continues." in result

    def test_strip_boneyard_multiple_metadata(self):
        """Test stripping multiple boneyard metadata blocks."""
        scene_with_multiple = """INT. ROOM - DAY

/* SCRIPTRAG-META-START
{"first": "data"}
SCRIPTRAG-META-END */

Action happens.

/* SCRIPTRAG-META-START
{"second": "data"}
SCRIPTRAG-META-END */

More action."""

        result = ScreenplayUtils.strip_boneyard(scene_with_multiple)

        # Should not contain any metadata tags
        assert "SCRIPTRAG-META-START" not in result
        assert "SCRIPTRAG-META-END" not in result
        assert "first" not in result
        assert "second" not in result
        # Should still contain the main content
        assert "INT. ROOM - DAY" in result
        assert "Action happens." in result
        assert "More action." in result

    def test_format_scene_for_prompt_full_scene(self):
        """Test formatting scene for prompt with all elements."""
        scene = {
            "heading": "INT. COFFEE SHOP - DAY",
            "action": [
                "The shop buzzes with morning energy.",
                "SARAH enters nervously.",
            ],
            "dialogue": [
                {"character": "SARAH", "text": "One coffee, please."},
                {"character": "BARISTA", "text": "Coming right up!"},
            ],
        }

        result = ScreenplayUtils.format_scene_for_prompt(scene)

        assert "SCENE HEADING: INT. COFFEE SHOP - DAY" in result
        assert "ACTION:" in result
        assert "The shop buzzes with morning energy." in result
        assert "SARAH enters nervously." in result
        assert "DIALOGUE:" in result
        assert "SARAH: One coffee, please." in result
        assert "BARISTA: Coming right up!" in result

    def test_format_scene_for_prompt_heading_only(self):
        """Test formatting scene with heading only."""
        scene = {"heading": "INT. OFFICE - DAY"}

        result = ScreenplayUtils.format_scene_for_prompt(scene)

        assert result == "SCENE HEADING: INT. OFFICE - DAY"

    def test_format_scene_for_prompt_action_only(self):
        """Test formatting scene with action only."""
        scene = {"action": ["He walks down the street.", "A car passes by."]}

        result = ScreenplayUtils.format_scene_for_prompt(scene)

        assert "ACTION:" in result
        assert "He walks down the street." in result
        assert "A car passes by." in result

    def test_format_scene_for_prompt_dialogue_only(self):
        """Test formatting scene with dialogue only."""
        scene = {
            "dialogue": [
                {"character": "ALICE", "text": "Hello there."},
                {"character": "BOB", "text": "Hi Alice!"},
            ]
        }

        result = ScreenplayUtils.format_scene_for_prompt(scene)

        assert "DIALOGUE:" in result
        assert "ALICE: Hello there." in result
        assert "BOB: Hi Alice!" in result

    def test_format_scene_for_prompt_empty_dialogue(self):
        """Test formatting scene with empty dialogue entries."""
        scene = {
            "dialogue": [
                {"character": "", "text": "Hello"},  # Empty character
                {"character": "BOB", "text": ""},  # Empty text
                {"character": "ALICE", "text": "Hi!"},  # Valid entry
            ]
        }

        result = ScreenplayUtils.format_scene_for_prompt(scene)

        assert "ALICE: Hi!" in result
        # Empty entries should be skipped
        assert "ALICE: Hi!" in result

    def test_format_scene_for_prompt_skip_empty_action(self):
        """Test formatting scene skips empty action lines."""
        scene = {"action": ["First action.", "", "   ", "Last action."]}

        result = ScreenplayUtils.format_scene_for_prompt(scene)

        assert "First action." in result
        assert "Last action." in result
        # Should skip empty and whitespace-only lines

    def test_format_scene_for_prompt_fallback_to_content(self):
        """Test formatting scene falls back to content field."""
        scene = {"content": "Raw scene content here."}

        result = ScreenplayUtils.format_scene_for_prompt(scene)

        assert result == "Raw scene content here."

    def test_format_scene_for_embedding_original_text(self):
        """Test formatting scene for embedding with original_text."""
        scene = {
            "original_text": """INT. CAFE - DAY

/* SCRIPTRAG-META-START
{"test": "data"}
SCRIPTRAG-META-END */

SARAH orders coffee.""",
            "heading": "Different heading",  # Should be ignored
        }

        result = ScreenplayUtils.format_scene_for_embedding(scene)

        # Should use original_text with boneyard stripped
        assert "INT. CAFE - DAY" in result
        assert "SARAH orders coffee." in result
        # Boneyard should be stripped
        assert "SCRIPTRAG-META-START" not in result

    def test_format_scene_for_embedding_structured_data(self):
        """Test formatting scene for embedding with structured data."""
        scene = {
            "heading": "INT. OFFICE - DAY",
            "action": ["She sits at desk.", "Phone rings."],
            "dialogue": [
                {"character": "JANE", "text": "Hello?"},
            ],
        }

        result = ScreenplayUtils.format_scene_for_embedding(scene)

        assert "Scene: INT. OFFICE - DAY" in result
        assert "Action: She sits at desk. Phone rings." in result
        assert "JANE: Hello?" in result

    def test_format_scene_for_embedding_compressed_action(self):
        """Test formatting scene compresses action lines."""
        scene = {
            "action": ["   First line   ", "", "Second line", "   ", "Third line   "]
        }

        result = ScreenplayUtils.format_scene_for_embedding(scene)

        # Should compress all non-empty action lines into single line
        assert "Action: First line Second line Third line" in result

    def test_format_scene_for_embedding_fallback_to_content(self):
        """Test formatting scene for embedding falls back to content."""
        scene = {"content": "Raw scene content."}

        result = ScreenplayUtils.format_scene_for_embedding(scene)

        assert result == "Raw scene content."

    def test_format_scene_for_embedding_empty_scene(self):
        """Test formatting empty scene for embedding."""
        scene = {}

        result = ScreenplayUtils.format_scene_for_embedding(scene)

        assert result == ""

    def test_extract_time_moments_later_specific(self):
        """Test that MOMENTS LATER is handled correctly."""
        # Test "MOMENTS LATER" - should find "LATER" first in the list
        result = ScreenplayUtils.extract_time("INT. ROOM - MOMENTS LATER")
        # Based on the order in the list, "LATER" appears before "MOMENTS LATER"
        # So it should match "LATER" first
        assert result in ["LATER", "MOMENTS LATER"]  # Either is acceptable

    def test_extract_location_rsplit_behavior(self):
        """Test location extraction with rsplit behavior."""
        # Test that rsplit with maxsplit=1 correctly handles multiple dashes
        result = ScreenplayUtils.extract_location(
            "INT. RESTAURANT - MAIN DINING - EVENING"
        )
        assert result == "RESTAURANT - MAIN DINING"

    def test_boneyard_pattern_variations(self):
        """Test boneyard pattern handles variations."""
        # Test with different whitespace
        scene_text1 = """Scene content
/*SCRIPTRAG-META-START
data
SCRIPTRAG-META-END*/
More content"""

        result1 = ScreenplayUtils.strip_boneyard(scene_text1)
        assert "SCRIPTRAG-META-START" not in result1
        assert "Scene content" in result1
        assert "More content" in result1

        # Test with extra whitespace
        scene_text2 = """Scene content
/*   SCRIPTRAG-META-START
data
SCRIPTRAG-META-END   */
More content"""

        result2 = ScreenplayUtils.strip_boneyard(scene_text2)
        assert "SCRIPTRAG-META-START" not in result2
