"""Test for canonical name collision bug fix in relationships analyzer.

This test ensures that canonical character names always map to themselves,
even when they appear as aliases for other characters.
"""

from scriptrag.analyzers.relationships import _build_alias_index


class TestCanonicalNameCollisionFix:
    """Test that canonical names correctly map to themselves."""

    def test_canonical_overrides_alias_mapping(self):
        """Test that canonical names always map to themselves, not other characters.

        This tests the bug fix where setdefault() was incorrectly used, causing
        canonical names that appeared as aliases for other characters to resolve
        incorrectly.
        """
        # Setup: JOHNNY is both an alias for JOHN and a canonical name itself
        bible_characters = {
            "version": 1,
            "characters": [
                {"canonical": "JOHN", "aliases": ["JOHNNY", "J"]},
                {"canonical": "JOHNNY", "aliases": ["JOHNNY BOY", "J-DAWG"]},
            ],
        }

        alias_to_canonical, canonicals = _build_alias_index(bible_characters)

        # JOHNNY should map to itself as a canonical name, not to JOHN
        assert alias_to_canonical["JOHNNY"] == "JOHNNY"

        # Other aliases should still work correctly
        assert alias_to_canonical["J"] == "JOHN"
        assert alias_to_canonical["JOHNNY BOY"] == "JOHNNY"
        assert alias_to_canonical["J-DAWG"] == "JOHNNY"

        # Canonical names should be in the set
        assert "JOHN" in canonicals
        assert "JOHNNY" in canonicals

    def test_multiple_overlapping_canonicals(self):
        """Test with multiple characters where canonicals overlap with aliases."""
        bible_characters = {
            "version": 1,
            "characters": [
                {"canonical": "ROBERT", "aliases": ["BOB", "BOBBY", "ROB"]},
                {"canonical": "BOB", "aliases": ["BOBBY", "B"]},
                {"canonical": "BOBBY", "aliases": ["B-MAN"]},
            ],
        }

        alias_to_canonical, canonicals = _build_alias_index(bible_characters)

        # Each canonical should map to itself
        assert alias_to_canonical["ROBERT"] == "ROBERT"
        assert alias_to_canonical["BOB"] == "BOB"
        assert alias_to_canonical["BOBBY"] == "BOBBY"

        # Non-conflicting aliases should work
        assert alias_to_canonical["ROB"] == "ROBERT"
        assert alias_to_canonical["B"] == "BOB"
        assert alias_to_canonical["B-MAN"] == "BOBBY"

        # All canonicals should be present
        assert canonicals == {"ROBERT", "BOB", "BOBBY"}

    def test_canonical_self_reference_in_aliases(self):
        """Test when a canonical name explicitly lists itself as an alias."""
        bible_characters = {
            "version": 1,
            "characters": [
                {
                    "canonical": "ELIZABETH",
                    "aliases": ["LIZ", "BETH", "ELIZABETH"],  # Self-reference
                }
            ],
        }

        alias_to_canonical, canonicals = _build_alias_index(bible_characters)

        # ELIZABETH should still map to itself
        assert alias_to_canonical["ELIZABETH"] == "ELIZABETH"
        assert alias_to_canonical["LIZ"] == "ELIZABETH"
        assert alias_to_canonical["BETH"] == "ELIZABETH"

        assert canonicals == {"ELIZABETH"}

    def test_empty_and_none_cases(self):
        """Test edge cases with empty or None data."""
        # None input
        alias_to_canonical, canonicals = _build_alias_index(None)
        assert alias_to_canonical == {}
        assert canonicals == set()

        # Empty characters list
        alias_to_canonical, canonicals = _build_alias_index({"characters": []})
        assert alias_to_canonical == {}
        assert canonicals == set()

        # Missing characters key
        alias_to_canonical, canonicals = _build_alias_index({})
        assert alias_to_canonical == {}
        assert canonicals == set()

    def test_case_normalization_with_collision(self):
        """Test that case normalization doesn't affect collision resolution."""
        bible_characters = {
            "version": 1,
            "characters": [
                {"canonical": "John", "aliases": ["johnny", "J"]},
                {"canonical": "Johnny", "aliases": ["John-boy"]},
            ],
        }

        alias_to_canonical, canonicals = _build_alias_index(bible_characters)

        # Both should normalize to uppercase and map correctly
        assert alias_to_canonical["JOHN"] == "JOHN"
        assert alias_to_canonical["JOHNNY"] == "JOHNNY"
        assert alias_to_canonical["J"] == "JOHN"
        assert alias_to_canonical["JOHN-BOY"] == "JOHNNY"

        assert canonicals == {"JOHN", "JOHNNY"}

    def test_whitespace_handling_with_collision(self):
        """Test that whitespace is properly stripped in collision scenarios."""
        bible_characters = {
            "version": 1,
            "characters": [
                {"canonical": "  MARY  ", "aliases": ["  MARY ANN  ", "M"]},
                {"canonical": "MARY ANN", "aliases": ["MA"]},
            ],
        }

        alias_to_canonical, canonicals = _build_alias_index(bible_characters)

        # Whitespace should be stripped, canonicals should map to themselves
        assert alias_to_canonical["MARY"] == "MARY"
        assert alias_to_canonical["MARY ANN"] == "MARY ANN"
        assert alias_to_canonical["M"] == "MARY"
        assert alias_to_canonical["MA"] == "MARY ANN"

        assert canonicals == {"MARY", "MARY ANN"}
