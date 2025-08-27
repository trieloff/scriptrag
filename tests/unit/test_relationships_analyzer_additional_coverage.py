"""Additional tests for relationships analyzer to improve coverage."""

import json
from unittest.mock import Mock, patch

import pytest

from scriptrag.analyzers.relationships import (
    CharacterRelationshipsAnalyzer,
    _build_alias_index,
    _compile_alias_patterns,
    _normalize_speaker,
)


class TestNormalizeSpeaker:
    """Test _normalize_speaker function."""

    def test_normalize_speaker_basic(self) -> None:
        """Test basic speaker normalization."""
        assert _normalize_speaker("john") == "JOHN"
        assert _normalize_speaker("Jane Doe") == "JANE DOE"

    def test_normalize_speaker_with_parentheticals(self) -> None:
        """Test speaker normalization with parentheticals."""
        assert _normalize_speaker("JOHN (CONT'D)") == "JOHN"
        assert _normalize_speaker("JANE (O.S.)") == "JANE"
        assert _normalize_speaker("SARAH (V.O.)") == "SARAH"
        assert _normalize_speaker("MIKE (WHISPERS)") == "MIKE"

    def test_normalize_speaker_with_whitespace(self) -> None:
        """Test speaker normalization with extra whitespace."""
        assert _normalize_speaker("  JOHN  ") == "JOHN"
        assert _normalize_speaker("JANE  (CONT'D)  ") == "JANE"
        assert _normalize_speaker("  SARAH (O.S.)  ") == "SARAH"

    def test_normalize_speaker_empty_or_none(self) -> None:
        """Test speaker normalization with empty or None input."""
        assert _normalize_speaker("") == ""
        assert _normalize_speaker("   ") == ""
        assert _normalize_speaker(None) == ""

    def test_normalize_speaker_complex_parentheticals(self) -> None:
        """Test speaker normalization with complex parentheticals."""
        assert _normalize_speaker("JOHN (into phone)") == "JOHN"
        assert _normalize_speaker("JANE (angry, shouting)") == "JANE"
        assert _normalize_speaker("SARAH (to Mike)") == "SARAH"


class TestBuildAliasIndex:
    """Test _build_alias_index function."""

    def test_build_alias_index_empty(self) -> None:
        """Test building alias index with empty input."""
        alias_to_canonical, canonicals = _build_alias_index(None)
        assert alias_to_canonical == {}
        assert canonicals == set()

        alias_to_canonical, canonicals = _build_alias_index({})
        assert alias_to_canonical == {}
        assert canonicals == set()

    def test_build_alias_index_no_characters(self) -> None:
        """Test building alias index with no characters."""
        bible_chars = {"version": 1, "characters": []}
        alias_to_canonical, canonicals = _build_alias_index(bible_chars)
        assert alias_to_canonical == {}
        assert canonicals == set()

    def test_build_alias_index_basic(self) -> None:
        """Test building alias index with basic data."""
        bible_chars = {
            "version": 1,
            "characters": [
                {"canonical": "JANE SMITH", "aliases": ["JANE", "MS. SMITH"]},
                {"canonical": "JOHN DOE", "aliases": ["JOHN", "MR. DOE"]},
            ],
        }
        alias_to_canonical, canonicals = _build_alias_index(bible_chars)

        assert canonicals == {"JANE SMITH", "JOHN DOE"}
        assert alias_to_canonical["JANE"] == "JANE SMITH"
        assert alias_to_canonical["MS. SMITH"] == "JANE SMITH"
        assert alias_to_canonical["JOHN"] == "JOHN DOE"
        assert alias_to_canonical["MR. DOE"] == "JOHN DOE"
        # Canonicals should map to themselves
        assert alias_to_canonical["JANE SMITH"] == "JANE SMITH"
        assert alias_to_canonical["JOHN DOE"] == "JOHN DOE"

    def test_build_alias_index_empty_canonical(self) -> None:
        """Test building alias index skips empty canonicals."""
        bible_chars = {
            "version": 1,
            "characters": [
                {"canonical": "", "aliases": ["EMPTY"]},
                {"canonical": "   ", "aliases": ["WHITESPACE"]},
                {"canonical": "VALID", "aliases": ["ALIAS"]},
            ],
        }
        alias_to_canonical, canonicals = _build_alias_index(bible_chars)

        assert canonicals == {"VALID"}
        assert "EMPTY" not in alias_to_canonical
        assert "WHITESPACE" not in alias_to_canonical
        assert alias_to_canonical["ALIAS"] == "VALID"

    def test_build_alias_index_empty_aliases(self) -> None:
        """Test building alias index handles empty aliases."""
        bible_chars = {
            "version": 1,
            "characters": [
                {"canonical": "JANE", "aliases": ["", "   ", "JANE_ALIAS"]},
                {"canonical": "JOHN", "aliases": []},
                {"canonical": "SARAH"},  # No aliases key
            ],
        }
        alias_to_canonical, canonicals = _build_alias_index(bible_chars)

        assert canonicals == {"JANE", "JOHN", "SARAH"}
        assert alias_to_canonical["JANE_ALIAS"] == "JANE"
        # Empty aliases should not be included
        assert "" not in alias_to_canonical
        assert "   " not in alias_to_canonical


class TestCompileAliasPatterns:
    """Test _compile_alias_patterns function."""

    def test_compile_alias_patterns_basic(self) -> None:
        """Test compiling basic alias patterns."""
        aliases = ["JANE", "JOHN DOE", "MS. SMITH"]
        patterns = _compile_alias_patterns(aliases)

        assert len(patterns) == 3
        # Check that each pattern is compiled and associated with correct alias
        pattern_aliases = [alias for _, alias in patterns]
        assert set(pattern_aliases) == set(aliases)

    def test_compile_alias_patterns_special_characters(self) -> None:
        """Test compiling patterns with special regex characters."""
        aliases = ["MR. SMITH", "JANE (YOUNG)", "JOHN-DOE"]
        patterns = _compile_alias_patterns(aliases)

        assert len(patterns) == 3
        # Patterns should be properly escaped
        for pattern, alias in patterns:
            assert pattern.pattern is not None
            # Should match the alias in context
            if alias == "MR. SMITH":
                assert pattern.search("Hello MR. SMITH here") is not None
                assert pattern.search("HELLO MR. SMITH.") is not None
                assert (
                    pattern.search("NOTMR. SMITH") is None
                )  # Should require word boundary

    def test_compile_alias_patterns_empty(self) -> None:
        """Test compiling patterns with empty list."""
        patterns = _compile_alias_patterns([])
        assert patterns == []

    def test_compile_alias_patterns_word_boundaries(self) -> None:
        """Test that compiled patterns respect word boundaries."""
        aliases = ["BOB", "ANN"]
        patterns = _compile_alias_patterns(aliases)

        bob_pattern = next(pattern for pattern, alias in patterns if alias == "BOB")
        ann_pattern = next(pattern for pattern, alias in patterns if alias == "ANN")

        # Should match whole words
        assert bob_pattern.search("Hello BOB there") is not None
        assert bob_pattern.search("BOB speaks") is not None
        assert bob_pattern.search("BOB.") is not None

        # Should not match partial words
        assert bob_pattern.search("BOBBY") is None
        assert bob_pattern.search("BOBCAT") is None

        # Same for ANN
        assert ann_pattern.search("Hello ANN") is not None
        assert (
            ann_pattern.search("ANN-MARIE") is not None
        )  # Hyphen is a boundary, so ANN matches
        assert ann_pattern.search("ANNIE") is None


class TestCharacterRelationshipsAnalyzerEdgeCases:
    """Test edge cases and error conditions in CharacterRelationshipsAnalyzer."""

    def test_init_with_bible_characters_config(self) -> None:
        """Test initialization with bible_characters in config."""
        bible_chars = {
            "version": 1,
            "characters": [{"canonical": "JANE", "aliases": ["J"]}],
        }
        config = {"bible_characters": bible_chars}

        analyzer = CharacterRelationshipsAnalyzer(config)

        assert analyzer._index is not None
        assert "JANE" in analyzer._index.canonicals
        assert analyzer._index.alias_to_canonical["J"] == "JANE"

    def test_init_without_config(self) -> None:
        """Test initialization without config."""
        analyzer = CharacterRelationshipsAnalyzer()

        assert analyzer._index is None
        assert analyzer.config == {}

    def test_init_with_empty_config(self) -> None:
        """Test initialization with empty config."""
        analyzer = CharacterRelationshipsAnalyzer({})

        assert analyzer._index is None
        assert analyzer.config == {}

    @pytest.mark.asyncio
    async def test_initialize_with_provided_config(self) -> None:
        """Test initialize method with provided config."""
        bible_chars = {
            "version": 1,
            "characters": [{"canonical": "JANE", "aliases": ["J"]}],
        }
        config = {"bible_characters": bible_chars}

        analyzer = CharacterRelationshipsAnalyzer(config)
        await analyzer.initialize()

        assert analyzer._index is not None
        assert "JANE" in analyzer._index.canonicals

    @pytest.mark.asyncio
    async def test_initialize_without_provided_config(self) -> None:
        """Test initialize method without provided config."""
        analyzer = CharacterRelationshipsAnalyzer()
        await analyzer.initialize()

        # Should leave _index as None since no config provided
        assert analyzer._index is None

    def test_ensure_index_from_db_no_script(self) -> None:
        """Test _ensure_index_from_db with no script object."""
        analyzer = CharacterRelationshipsAnalyzer()
        analyzer.script = None

        analyzer._ensure_index_from_db()

        assert analyzer._index is not None
        assert analyzer._index.alias_to_canonical == {}

    def test_ensure_index_from_db_no_source_file(self) -> None:
        """Test _ensure_index_from_db with script but no source_file."""
        analyzer = CharacterRelationshipsAnalyzer()
        analyzer.script = Mock(spec=object)
        analyzer.script.metadata = {}

        analyzer._ensure_index_from_db()

        assert analyzer._index is not None
        assert analyzer._index.alias_to_canonical == {}

    def test_ensure_index_from_db_with_source_file(self) -> None:
        """Test _ensure_index_from_db with valid source file."""
        analyzer = CharacterRelationshipsAnalyzer()
        analyzer.script = Mock(spec=object)
        analyzer.script.metadata = {"source_file": "/path/to/script.fountain"}

        # Mock database operations
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = Mock(spec=["execute", "__enter__", "__exit__"])
            mock_cursor = Mock(spec=["fetchone"])
            # Mock metadata with bible characters
            metadata = {
                "bible.characters": {
                    "version": 1,
                    "characters": [{"canonical": "JANE", "aliases": ["J"]}],
                }
            }
            mock_cursor.fetchone.return_value = {"metadata": json.dumps(metadata)}
            mock_conn.execute.return_value = mock_cursor
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_connect.return_value = mock_conn

            analyzer._ensure_index_from_db()

            assert analyzer._index is not None
            assert "JANE" in analyzer._index.canonicals

    def test_ensure_index_from_db_with_nested_bible_structure(self) -> None:
        """Test _ensure_index_from_db with nested bible structure in metadata."""
        analyzer = CharacterRelationshipsAnalyzer()
        analyzer.script = Mock(spec=object)
        analyzer.script.metadata = {"source_file": "/path/to/script.fountain"}

        # Mock database operations
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = Mock(spec=["execute", "__enter__", "__exit__"])
            mock_cursor = Mock(spec=["fetchone"])
            # Mock metadata with nested bible structure
            metadata = {
                "bible": {
                    "characters": {
                        "version": 1,
                        "characters": [{"canonical": "JANE", "aliases": ["J"]}],
                    }
                }
            }
            mock_cursor.fetchone.return_value = {"metadata": json.dumps(metadata)}
            mock_conn.execute.return_value = mock_cursor
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_connect.return_value = mock_conn

            analyzer._ensure_index_from_db()

            assert analyzer._index is not None
            assert "JANE" in analyzer._index.canonicals

    def test_ensure_index_from_db_no_metadata(self) -> None:
        """Test _ensure_index_from_db with no metadata in database."""
        analyzer = CharacterRelationshipsAnalyzer()
        analyzer.script = Mock(spec=object)
        analyzer.script.metadata = {"source_file": "/path/to/script.fountain"}

        # Mock database operations
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = Mock(spec=["execute", "__enter__", "__exit__"])
            mock_cursor = Mock(spec=["fetchone"])
            mock_cursor.fetchone.return_value = None  # No row found
            mock_conn.execute.return_value = mock_cursor
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_connect.return_value = mock_conn

            analyzer._ensure_index_from_db()

            assert analyzer._index is not None
            assert analyzer._index.alias_to_canonical == {}

    @pytest.mark.asyncio
    async def test_analyze_no_index_fallback_to_db(self) -> None:
        """Test analyze method when no index, falling back to DB load."""
        analyzer = CharacterRelationshipsAnalyzer()
        analyzer.script = Mock(spec=object)
        analyzer.script.metadata = {"source_file": "/path/to/script.fountain"}

        # Mock database operations to return empty
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = Mock(spec=["execute", "__enter__", "__exit__"])
            mock_cursor = Mock(spec=["fetchone"])
            mock_cursor.fetchone.return_value = None
            mock_conn.execute.return_value = mock_cursor
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)
            mock_connect.return_value = mock_conn

            scene = {"dialogue": [], "action": []}
            result = await analyzer.analyze(scene)

            assert result == {}

    @pytest.mark.asyncio
    async def test_analyze_with_various_dialogue_formats(self) -> None:
        """Test analyze with various dialogue input formats."""
        bible_chars = {
            "version": 1,
            "characters": [
                {"canonical": "JANE", "aliases": ["J", "JANE DOE"]},
                {"canonical": "JOHN", "aliases": ["JOHNNY"]},
            ],
        }
        config = {"bible_characters": bible_chars}
        analyzer = CharacterRelationshipsAnalyzer(config)

        scene = {
            "dialogue": [
                {"character": "JANE"},  # Dict format
                "JOHN: Hello there",  # String format with colon
                "JOHNNY",  # String format, just name
                {"character": "J (CONT'D)"},  # Dict with parenthetical
                "Unknown Speaker: Hi",  # Unknown character
                123,  # Invalid format
                {"not_character": "JANE"},  # Dict without character key
            ],
            "action": [],
        }

        result = await analyzer.analyze(scene)

        # Should resolve JANE, JOHN, JOHNNY, J to their canonicals
        expected_speaking = ["JANE", "JOHN"]  # Canonicals only
        assert set(result["speaking"]) == set(expected_speaking)

    @pytest.mark.asyncio
    async def test_analyze_with_various_action_formats(self) -> None:
        """Test analyze with various action line formats."""
        bible_chars = {
            "version": 1,
            "characters": [
                {"canonical": "JANE", "aliases": ["J"]},
                {"canonical": "JOHN", "aliases": ["JOHNNY"]},
            ],
        }
        config = {"bible_characters": bible_chars}
        analyzer = CharacterRelationshipsAnalyzer(config)

        scene = {
            "dialogue": [],
            "action": [
                "JANE walks into the room.",  # String format
                {"text": "JOHN follows behind."},  # Dict format
                {"not_text": "JANE is here"},  # Dict without text key
                123,  # Invalid format
                {"text": 456},  # Dict with non-string text
            ],
            "heading": "INT. OFFICE - DAY with JANE and JOHNNY",
        }

        result = await analyzer.analyze(scene)

        # Should find JANE and JOHN in action lines and heading
        expected_present = ["JANE", "JOHN"]
        assert set(result["present"]) == set(expected_present)

    @pytest.mark.asyncio
    async def test_analyze_empty_scene_with_index(self) -> None:
        """Test analyze with empty scene but valid index."""
        bible_chars = {
            "version": 1,
            "characters": [{"canonical": "JANE", "aliases": ["J"]}],
        }
        config = {"bible_characters": bible_chars}
        analyzer = CharacterRelationshipsAnalyzer(config)

        scene = {}  # Empty scene

        result = await analyzer.analyze(scene)

        expected = {
            "present": [],
            "speaking": [],
            "co_presence_pairs": [],
            "speaking_edges": [],
            "stats": {"present_count": 0, "speaking_count": 0},
        }
        assert result == expected

    @pytest.mark.asyncio
    async def test_analyze_scene_with_single_character(self) -> None:
        """Test analyze with scene containing only one character."""
        bible_chars = {
            "version": 1,
            "characters": [{"canonical": "JANE", "aliases": ["J"]}],
        }
        config = {"bible_characters": bible_chars}
        analyzer = CharacterRelationshipsAnalyzer(config)

        scene = {
            "dialogue": [{"character": "JANE"}],
            "action": ["JANE looks around."],
        }

        result = await analyzer.analyze(scene)

        assert result["present"] == ["JANE"]
        assert result["speaking"] == ["JANE"]
        assert result["co_presence_pairs"] == []  # No co-presence with single character
        assert result["speaking_edges"] == []  # No edges with single character

    def test_resolve_alias_with_index(self) -> None:
        """Test _resolve_alias method."""
        bible_chars = {
            "version": 1,
            "characters": [{"canonical": "JANE", "aliases": ["J"]}],
        }
        config = {"bible_characters": bible_chars}
        analyzer = CharacterRelationshipsAnalyzer(config)

        assert analyzer._resolve_alias("JANE") == "JANE"
        assert analyzer._resolve_alias("J") == "JANE"
        assert analyzer._resolve_alias("UNKNOWN") is None
        assert analyzer._resolve_alias("  j  ") == "JANE"  # Handles whitespace

    def test_resolve_alias_no_index(self) -> None:
        """Test _resolve_alias method with no index."""
        analyzer = CharacterRelationshipsAnalyzer()

        assert analyzer._resolve_alias("JANE") is None

    def test_scan_mentions_with_index(self) -> None:
        """Test _scan_mentions method."""
        bible_chars = {
            "version": 1,
            "characters": [
                {"canonical": "JANE", "aliases": ["J"]},
                {"canonical": "JOHN DOE", "aliases": ["JOHN"]},
            ],
        }
        config = {"bible_characters": bible_chars}
        analyzer = CharacterRelationshipsAnalyzer(config)

        text = "JANE and JOHN meet at the café. J waves at JOHN DOE."
        mentions = analyzer._scan_mentions(text)

        assert mentions == {"JANE", "JOHN DOE"}

    def test_scan_mentions_no_index(self) -> None:
        """Test _scan_mentions method with no index."""
        analyzer = CharacterRelationshipsAnalyzer()

        text = "JANE and JOHN meet at the café."
        mentions = analyzer._scan_mentions(text)

        assert mentions == set()

    def test_create_word_boundary_pattern(self) -> None:
        """Test _create_word_boundary_pattern method."""
        analyzer = CharacterRelationshipsAnalyzer()

        pattern = analyzer._create_word_boundary_pattern("JANE")

        # Should match whole words
        assert pattern.search("Hello JANE there") is not None
        assert pattern.search("JANE speaks") is not None

        # Should not match partial words
        assert pattern.search("JANELLE") is None
        assert pattern.search("CAJANE") is None

    def test_create_word_boundary_pattern_special_chars(self) -> None:
        """Test _create_word_boundary_pattern with special characters."""
        analyzer = CharacterRelationshipsAnalyzer()

        pattern = analyzer._create_word_boundary_pattern("MR. SMITH")

        # Should properly escape and match
        assert pattern.search("Hello MR. SMITH there") is not None
        assert pattern.search("MR. SMITH.") is not None
