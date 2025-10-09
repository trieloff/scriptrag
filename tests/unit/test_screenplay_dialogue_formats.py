"""Tests for ScreenplayUtils dialogue format handling.

This tests the bug fix for handling both dictionary and string dialogue formats
in the format_scene_for_prompt and format_scene_for_embedding methods.
"""

from scriptrag.utils import ScreenplayUtils


class TestDialogueFormatHandling:
    """Tests for proper handling of different dialogue formats."""

    def test_format_scene_for_prompt_with_dict_dialogue(self):
        """Test formatting scene with dictionary-formatted dialogue."""
        scene = {
            "heading": "INT. OFFICE - DAY",
            "dialogue": [
                {"character": "ALICE", "text": "Hello there."},
                {"character": "BOB", "text": "Hi Alice!"},
            ],
        }

        result = ScreenplayUtils.format_scene_for_prompt(scene)

        assert "SCENE HEADING: INT. OFFICE - DAY" in result
        assert "DIALOGUE:" in result
        assert "ALICE: Hello there." in result
        assert "BOB: Hi Alice!" in result

    def test_format_scene_for_prompt_with_string_dialogue(self):
        """Test formatting scene with string-formatted dialogue."""
        scene = {
            "heading": "INT. COFFEE SHOP - MORNING",
            "dialogue": [
                "JANE: Would you like some coffee?",
                "MIKE: Yes, please!",
                "JANE: Coming right up.",
            ],
        }

        result = ScreenplayUtils.format_scene_for_prompt(scene)

        assert "SCENE HEADING: INT. COFFEE SHOP - MORNING" in result
        assert "DIALOGUE:" in result
        assert "JANE: Would you like some coffee?" in result
        assert "MIKE: Yes, please!" in result
        assert "JANE: Coming right up." in result

    def test_format_scene_for_prompt_with_mixed_dialogue(self):
        """Test formatting scene with mixed dialogue formats."""
        scene = {
            "dialogue": [
                {"character": "ALICE", "text": "Dict format here."},
                "BOB: String format here.",
                {"character": "CHARLIE", "text": "Back to dict."},
                "DAVID: Another string.",
            ]
        }

        result = ScreenplayUtils.format_scene_for_prompt(scene)

        assert "DIALOGUE:" in result
        assert "ALICE: Dict format here." in result
        assert "BOB: String format here." in result
        assert "CHARLIE: Back to dict." in result
        assert "DAVID: Another string." in result

    def test_format_scene_for_prompt_with_empty_string_dialogue(self):
        """Test formatting scene with empty string dialogue entries."""
        scene = {
            "dialogue": [
                "ALICE: Valid entry.",
                "",  # Empty string
                "   ",  # Whitespace only
                "BOB: Another valid entry.",
            ]
        }

        result = ScreenplayUtils.format_scene_for_prompt(scene)

        assert "DIALOGUE:" in result
        assert "ALICE: Valid entry." in result
        assert "BOB: Another valid entry." in result
        # Empty strings should be skipped
        lines = result.split("\n")
        dialogue_lines = [line for line in lines if line and line != "DIALOGUE:"]
        assert len(dialogue_lines) == 2

    def test_format_scene_for_prompt_with_invalid_dict_dialogue(self):
        """Test formatting scene with invalid dictionary dialogue entries."""
        scene = {
            "dialogue": [
                {"character": "ALICE", "text": "Valid entry."},
                {"character": "", "text": "Missing character."},
                {"character": "BOB", "text": ""},  # Missing text
                {"character": "CHARLIE"},  # Missing text key
                {"text": "Missing character key."},
                {"character": "DAVID", "text": "Another valid."},
            ]
        }

        result = ScreenplayUtils.format_scene_for_prompt(scene)

        assert "DIALOGUE:" in result
        assert "ALICE: Valid entry." in result
        assert "DAVID: Another valid." in result
        # Invalid entries should be skipped
        assert "Missing character." not in result
        assert "Missing character key." not in result

    def test_format_scene_for_embedding_with_dict_dialogue(self):
        """Test embedding format with dictionary dialogue."""
        scene = {
            "heading": "EXT. PARK - DAY",
            "action": ["Birds chirping.", "People walking."],
            "dialogue": [
                {"character": "SARAH", "text": "Beautiful day!"},
                {"character": "TOM", "text": "Indeed it is."},
            ],
        }

        result = ScreenplayUtils.format_scene_for_embedding(scene)

        assert "Scene: EXT. PARK - DAY" in result
        assert "Action: Birds chirping. People walking." in result
        assert "SARAH: Beautiful day!" in result
        assert "TOM: Indeed it is." in result

    def test_format_scene_for_embedding_with_string_dialogue(self):
        """Test embedding format with string dialogue."""
        scene = {
            "heading": "INT. RESTAURANT - NIGHT",
            "dialogue": [
                "WAITER: What can I get you?",
                "CUSTOMER: The special, please.",
                "WAITER: Excellent choice.",
            ],
        }

        result = ScreenplayUtils.format_scene_for_embedding(scene)

        assert "Scene: INT. RESTAURANT - NIGHT" in result
        assert "WAITER: What can I get you?" in result
        assert "CUSTOMER: The special, please." in result
        assert "WAITER: Excellent choice." in result

    def test_format_scene_for_embedding_with_mixed_dialogue(self):
        """Test embedding format with mixed dialogue formats."""
        scene = {
            "dialogue": [
                {"character": "NARRATOR", "text": "Once upon a time..."},
                "CHILD: Tell me more!",
                {"character": "NARRATOR", "text": "There was a castle..."},
            ]
        }

        result = ScreenplayUtils.format_scene_for_embedding(scene)

        assert "NARRATOR: Once upon a time..." in result
        assert "CHILD: Tell me more!" in result
        assert "NARRATOR: There was a castle..." in result

    def test_format_scene_for_embedding_prefers_original_text(self):
        """Test that original_text is preferred over structured data."""
        scene = {
            "original_text": "INT. OFFICE - DAY\n\nOriginal screenplay text here.",
            "heading": "Different heading",
            "dialogue": [
                {"character": "SOMEONE", "text": "This should not appear."},
            ],
        }

        result = ScreenplayUtils.format_scene_for_embedding(scene)

        # Should use original_text, not structured data
        assert result == "INT. OFFICE - DAY\n\nOriginal screenplay text here."
        assert "Different heading" not in result
        assert "SOMEONE" not in result

    def test_format_scene_with_non_list_dialogue(self):
        """Test that non-list dialogue is handled gracefully."""
        scene = {
            "heading": "INT. ROOM - DAY",
            "dialogue": "Not a list",  # Invalid type
        }

        # Should not raise an exception
        result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert "SCENE HEADING: INT. ROOM - DAY" in result
        # Invalid dialogue format should be skipped
        assert "DIALOGUE:" not in result

    def test_format_scene_with_none_dialogue_entries(self):
        """Test handling of None values in dialogue list."""
        scene = {
            "dialogue": [
                {"character": "ALICE", "text": "Hello."},
                None,  # None value
                "BOB: Hi there.",
                None,
                {"character": "CHARLIE", "text": "Greetings."},
            ]
        }

        # Should handle None values gracefully
        result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert "ALICE: Hello." in result
        assert "BOB: Hi there." in result
        assert "CHARLIE: Greetings." in result

    def test_format_scene_with_numeric_dialogue_entries(self):
        """Test handling of non-string/non-dict values in dialogue."""
        scene = {
            "dialogue": [
                {"character": "ALICE", "text": "Start."},
                123,  # Numeric value
                45.67,  # Float value
                ["list", "value"],  # List value
                "BOB: String entry.",
                {"character": "CHARLIE", "text": "End."},
            ]
        }

        # Should skip non-string/non-dict values
        result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert "ALICE: Start." in result
        assert "BOB: String entry." in result
        assert "CHARLIE: End." in result
        # Numeric/list values should not appear
        assert "123" not in result
        assert "45.67" not in result
        assert "list" not in result


class TestDialogueEdgeCases:
    """Test edge cases in dialogue handling."""

    def test_empty_dialogue_list(self):
        """Test handling of empty dialogue list."""
        scene = {
            "heading": "INT. SILENT ROOM - DAY",
            "dialogue": [],
        }

        result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert "SCENE HEADING: INT. SILENT ROOM - DAY" in result
        # Empty dialogue should not add DIALOGUE: header
        assert "DIALOGUE:" not in result

    def test_dialogue_with_special_characters(self):
        """Test dialogue with special characters."""
        scene = {
            "dialogue": [
                {"character": "ALICE", "text": "Hello! How are you?"},
                "BOB: I'm doing well, thanks!",
                {"character": "CHARLIE", "text": "That's great... or is it?"},
                "DAVID (V.O.): Testing parentheses.",
                "EMMA'S VOICE: Testing apostrophe.",
            ]
        }

        result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert "ALICE: Hello! How are you?" in result
        assert "BOB: I'm doing well, thanks!" in result
        assert "CHARLIE: That's great... or is it?" in result
        assert "DAVID (V.O.): Testing parentheses." in result
        assert "EMMA'S VOICE: Testing apostrophe." in result

    def test_dialogue_with_multiline_text(self):
        """Test dialogue with multiline text in dict format."""
        scene = {
            "dialogue": [
                {
                    "character": "ALICE",
                    "text": (
                        "This is a long speech.\n"
                        "It spans multiple lines.\n"
                        "Very dramatic."
                    ),
                }
            ]
        }

        result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert (
            "ALICE: This is a long speech.\nIt spans multiple lines.\nVery dramatic."
            in result
        )

    def test_dialogue_string_without_colon(self):
        """Test string dialogue entries without colon separator."""
        scene = {
            "dialogue": [
                "ALICE: Normal entry.",
                "This has no colon",
                "BOB: Another normal entry.",
                "Another one without colon",
            ]
        }

        result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert "ALICE: Normal entry." in result
        assert "BOB: Another normal entry." in result
        # Entries without colon are still included as-is
        assert "This has no colon" in result
        assert "Another one without colon" in result

    def test_both_methods_produce_consistent_format(self):
        """Test that both format methods handle dialogue consistently."""
        scene = {
            "heading": "INT. OFFICE - DAY",
            "dialogue": [
                {"character": "ALICE", "text": "Dictionary format."},
                "BOB: String format.",
            ],
        }

        prompt_result = ScreenplayUtils.format_scene_for_prompt(scene)
        embed_result = ScreenplayUtils.format_scene_for_embedding(scene)

        # Both should include the dialogue entries
        assert "ALICE: Dictionary format." in prompt_result
        assert "BOB: String format." in prompt_result
        assert "ALICE: Dictionary format." in embed_result
        assert "BOB: String format." in embed_result
