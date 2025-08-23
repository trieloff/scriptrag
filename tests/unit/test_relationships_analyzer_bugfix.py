"""Test for relationships analyzer backward compatibility bug fix.

This test specifically verifies that the alias_patterns attribute is properly
populated when the alias_to_canonical property is accessed, ensuring backward
compatibility with legacy code that relies on this attribute.
"""

import pytest

from scriptrag.analyzers.relationships import CharacterRelationshipsAnalyzer


class TestRelationshipsAnalyzerBugfix:
    """Test bug fix for missing alias_patterns in backward compatibility property."""

    def test_alias_patterns_populated_via_property_access(self) -> None:
        """Test that alias_patterns is populated when accessing the property.

        This tests the bug fix where alias_patterns was not being set when the
        alias_to_canonical property was accessed and triggered index initialization.
        The bug would cause _find_mentions_in_text to fail because it relies on
        self.alias_patterns being populated.
        """
        # Create analyzer with bible characters config
        bible_characters = {
            "version": 1,
            "characters": [
                {"canonical": "JANE SMITH", "aliases": ["JANE", "MS. SMITH"]},
                {"canonical": "BOB JONES", "aliases": ["BOB", "DETECTIVE JONES"]},
            ],
        }

        analyzer = CharacterRelationshipsAnalyzer(
            config={"bible_characters": bible_characters}
        )

        # Important: Do NOT call initialize() or analyze() first
        # We want to test the property access path specifically

        # Access the backward compatibility property
        # This should trigger index initialization
        alias_map = analyzer.alias_to_canonical

        # Verify the alias map is populated correctly
        assert alias_map is not None
        assert "JANE" in alias_map
        assert alias_map["JANE"] == "JANE SMITH"
        assert "BOB" in alias_map
        assert alias_map["BOB"] == "BOB JONES"

        # CRITICAL: Verify alias_patterns is also populated
        # This was the bug - it wasn't being set in the property getter
        assert hasattr(analyzer, "alias_patterns")
        assert analyzer.alias_patterns is not None
        assert len(analyzer.alias_patterns) > 0

        # Verify the patterns work correctly
        assert "JANE" in analyzer.alias_patterns
        assert "MS. SMITH" in analyzer.alias_patterns
        assert "BOB" in analyzer.alias_patterns
        assert "DETECTIVE JONES" in analyzer.alias_patterns

        # Canonical names should also be in patterns
        assert "JANE SMITH" in analyzer.alias_patterns
        assert "BOB JONES" in analyzer.alias_patterns

        # Test that _find_mentions_in_text works (it depends on alias_patterns)
        text = "JANE walks into the room where BOB is waiting."
        mentions = analyzer._find_mentions_in_text(text)

        # Should find both characters
        assert "JANE SMITH" in mentions
        assert "BOB JONES" in mentions

    def test_alias_patterns_regex_correctness(self) -> None:
        """Test that the regex patterns in alias_patterns work correctly.

        This verifies that the patterns created via the property access path
        have the same behavior as those created through normal initialization.
        """
        bible_characters = {
            "version": 1,
            "characters": [
                {"canonical": "ROBERT SMITH", "aliases": ["BOB", "MR. SMITH"]},
            ],
        }

        analyzer = CharacterRelationshipsAnalyzer(
            config={"bible_characters": bible_characters}
        )

        # Access property to trigger initialization
        _ = analyzer.alias_to_canonical

        # Verify patterns exist
        assert "BOB" in analyzer.alias_patterns
        bob_pattern = analyzer.alias_patterns["BOB"]

        # Test word boundary matching
        assert bob_pattern.search("BOB walks in") is not None
        assert bob_pattern.search("Meet BOB here") is not None
        assert bob_pattern.search("BOBBIN walks in") is None  # Should NOT match
        assert bob_pattern.search("KABOB is tasty") is None  # Should NOT match

    def test_property_access_without_config(self) -> None:
        """Test that property access without config doesn't crash.

        This ensures the bug fix doesn't break the fallback path.
        """
        analyzer = CharacterRelationshipsAnalyzer()

        # Access property without any config
        alias_map = analyzer.alias_to_canonical

        # Should return empty dict, not crash
        assert alias_map == {}

        # alias_patterns should still be initialized (as empty)
        assert hasattr(analyzer, "alias_patterns")
        # It might be empty dict or not set, depending on the path taken

    @pytest.mark.asyncio
    async def test_legacy_method_after_property_access(self) -> None:
        """Test that legacy methods work after property access.

        Ensures backward compatibility is fully maintained.
        """
        bible_characters = {
            "version": 1,
            "characters": [
                {"canonical": "ALICE COOPER", "aliases": ["ALICE", "MS. COOPER"]},
            ],
        }

        analyzer = CharacterRelationshipsAnalyzer(
            config={"bible_characters": bible_characters}
        )

        # Access property first
        alias_map = analyzer.alias_to_canonical
        assert "ALICE" in alias_map

        # Now test legacy method
        canonical = analyzer._resolve_to_canonical("alice")
        assert canonical == "ALICE COOPER"

        # Test the other legacy method
        text = "Alice and Ms. Cooper are the same person"
        mentions = analyzer._find_mentions_in_text(text)
        assert "ALICE COOPER" in mentions
        assert len(mentions) == 1  # Should only find one canonical name

    def test_patterns_consistency_across_init_paths(self) -> None:
        """Test that patterns are consistent regardless of initialization path.

        This ensures the bug fix creates patterns identical to other init paths.
        """
        bible_characters = {
            "version": 1,
            "characters": [
                {"canonical": "JOHN DOE", "aliases": ["JOHN", "MR. DOE"]},
            ],
        }

        # Analyzer 1: Initialize via property access (bug fix path)
        analyzer1 = CharacterRelationshipsAnalyzer(
            config={"bible_characters": bible_characters}
        )
        _ = analyzer1.alias_to_canonical  # Trigger via property

        # Analyzer 2: Initialize via normal path
        analyzer2 = CharacterRelationshipsAnalyzer(
            config={"bible_characters": bible_characters}
        )
        # This will populate via __init__ since config is provided

        # Both should have identical alias_patterns keys
        assert set(analyzer1.alias_patterns.keys()) == set(
            analyzer2.alias_patterns.keys()
        )

        # Both should have identical alias_to_canonical mappings
        assert analyzer1.alias_to_canonical == analyzer2.alias_to_canonical

        # Test that both find the same mentions
        text = "JOHN and MR. DOE discussed the case"
        mentions1 = analyzer1._find_mentions_in_text(text)
        mentions2 = analyzer2._find_mentions_in_text(text)
        assert mentions1 == mentions2
        assert "JOHN DOE" in mentions1
