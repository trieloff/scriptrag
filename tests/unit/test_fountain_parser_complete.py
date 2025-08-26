"""Comprehensive unit tests for FountainParser to achieve 99% coverage.

This test suite methodically covers every logical branch, edge case, and error
condition in the FountainParser class to ensure complete test coverage.

Authored by test-holmes for complete fountain parsing validation.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from scriptrag.exceptions import ParseError
from scriptrag.parser import FountainParser
from scriptrag.parser.fountain_models import Scene, Script

# Path to fixture files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "fountain" / "test_data"


class TestFountainParserComprehensive:
    """Comprehensive test suite for FountainParser class."""

    @pytest.fixture
    def parser(self):
        """Create a FountainParser instance."""
        return FountainParser()

    @pytest.fixture
    def sample_fountain(self):
        """Load sample Fountain content from fixture file."""
        fixture_file = FIXTURES_DIR / "parser_test.fountain"
        return fixture_file.read_text()

    # =============================================
    # Tests for _apply_jouvence_workaround method
    # =============================================

    def test_apply_jouvence_workaround_single_boneyard(self, parser):
        """Test workaround strips single-line boneyard comments."""
        content = "Title: Test\n/* Simple comment */\nINT. ROOM - DAY"
        result = parser._apply_jouvence_workaround(content)
        assert "/*" not in result
        assert "*/" not in result
        assert "Simple comment" not in result
        assert "Title: Test" in result
        assert "INT. ROOM - DAY" in result

    def test_apply_jouvence_workaround_multiline_boneyard(self, parser):
        """Test workaround strips multiline boneyard comments."""
        content = """Title: Test

/*
  Multiline
  comment
  here
*/

INT. ROOM - DAY

Action line.

/* Another
   multiline
   comment */
"""
        result = parser._apply_jouvence_workaround(content)
        assert "/*" not in result
        assert "*/" not in result
        assert "Multiline" not in result
        assert "comment" not in result
        assert "Another" not in result
        assert "Title: Test" in result
        assert "INT. ROOM - DAY" in result
        assert "Action line." in result

    def test_apply_jouvence_workaround_scriptrag_metadata(self, parser):
        """Test workaround strips ScriptRAG metadata blocks."""
        content = """Title: Test

INT. ROOM - DAY

Some action.

/* SCRIPTRAG-META-START
{
    "content_hash": "abc123",
    "analyzed_at": "2024-01-01"
}
SCRIPTRAG-META-END */

More action.
"""
        result = parser._apply_jouvence_workaround(content)
        assert "SCRIPTRAG-META-START" not in result
        assert "content_hash" not in result
        assert "analyzed_at" not in result
        assert "abc123" not in result
        assert "Title: Test" in result
        assert "Some action." in result
        assert "More action." in result

    def test_apply_jouvence_workaround_mixed_boneyards(self, parser):
        """Test workaround strips multiple types of boneyard comments."""
        content = """Title: Test
/* Simple comment */
INT. ROOM - DAY

/*
Multiline comment
*/

Action.

/* SCRIPTRAG-META-START
{"key": "value"}
SCRIPTRAG-META-END */

/* Final comment */
"""
        result = parser._apply_jouvence_workaround(content)
        # All boneyard content should be gone
        assert "/*" not in result
        assert "*/" not in result
        assert "Simple comment" not in result
        assert "Multiline comment" not in result
        assert "SCRIPTRAG-META-START" not in result
        assert "Final comment" not in result
        # But regular content should remain
        assert "Title: Test" in result
        assert "INT. ROOM - DAY" in result
        assert "Action." in result

    # =============================================
    # Tests for _extract_doc_metadata method
    # =============================================

    def test_extract_doc_metadata_complete_fields(self, parser):
        """Test _extract_doc_metadata with all possible fields."""
        mock_doc = MagicMock(spec=object)
        mock_doc.title_values = {
            "title": "Complete Test",
            "author": "Full Author",
            "episode": "42",
            "season": "7",
            "series": "Amazing Series",
            "project": "Season 7 Project",
        }

        title, author, metadata = parser._extract_doc_metadata(mock_doc)

        assert title == "Complete Test"
        assert author == "Full Author"
        assert metadata["episode"] == 42  # Converted to int
        assert metadata["season"] == 7  # Converted to int
        assert metadata["series_title"] == "Amazing Series"
        assert metadata["project_title"] == "Season 7 Project"

    def test_extract_doc_metadata_all_author_variations(self, parser):
        """Test all author field variations."""
        author_fields = {
            "author": "John Author",
            "authors": "Multiple Authors",
            "writer": "Jane Writer",
            "writers": "Multiple Writers",
            "written by": "Written By Person",
        }

        for field_name, expected_author in author_fields.items():
            mock_doc = MagicMock(spec=object)
            mock_doc.title_values = {"title": "Test", field_name: expected_author}

            _, author, _ = parser._extract_doc_metadata(mock_doc)
            assert author == expected_author, f"Failed for author field: {field_name}"

    def test_extract_doc_metadata_author_priority(self, parser):
        """Test author field priority (first match wins)."""
        mock_doc = MagicMock(spec=object)
        # author should win over writer
        mock_doc.title_values = {
            "author": "Primary Author",
            "writer": "Secondary Writer",
            "written by": "Tertiary Author",
        }

        _, author, _ = parser._extract_doc_metadata(mock_doc)
        assert author == "Primary Author"

    def test_extract_doc_metadata_series_field_priority(self, parser):
        """Test series field priority: series > series_title > show."""
        # Test priority: series wins
        mock_doc = MagicMock(spec=object)
        mock_doc.title_values = {
            "series": "Primary Series",
            "series_title": "Secondary Series",
            "show": "Tertiary Show",
        }

        _, _, metadata = parser._extract_doc_metadata(mock_doc)
        assert metadata["series_title"] == "Primary Series"

        # Test series_title wins when series absent
        mock_doc.title_values = {
            "series_title": "Secondary Series",
            "show": "Tertiary Show",
        }

        _, _, metadata = parser._extract_doc_metadata(mock_doc)
        assert metadata["series_title"] == "Secondary Series"

        # Test show wins when both series and series_title absent
        mock_doc.title_values = {"show": "Tertiary Show"}

        _, _, metadata = parser._extract_doc_metadata(mock_doc)
        assert metadata["series_title"] == "Tertiary Show"

    def test_extract_doc_metadata_project_field_priority(self, parser):
        """Test project field priority: project > project_title."""
        # Test priority: project wins
        mock_doc = MagicMock(spec=object)
        mock_doc.title_values = {
            "project": "Primary Project",
            "project_title": "Secondary Project",
        }

        _, _, metadata = parser._extract_doc_metadata(mock_doc)
        assert metadata["project_title"] == "Primary Project"

        # Test project_title wins when project absent
        mock_doc.title_values = {"project_title": "Secondary Project"}

        _, _, metadata = parser._extract_doc_metadata(mock_doc)
        assert metadata["project_title"] == "Secondary Project"

    def test_extract_doc_metadata_episode_season_value_error(self, parser):
        """Test ValueError handling in episode/season parsing."""
        mock_doc = MagicMock(spec=object)
        # These should trigger ValueError in int() conversion (lines 86, 94)
        mock_doc.title_values = {
            "episode": None,  # TypeError: int() argument must be a string
            "season": None,  # TypeError: int() argument must be a string
        }

        _, _, metadata = parser._extract_doc_metadata(mock_doc)
        # Should keep as original values when int conversion fails
        assert metadata["episode"] is None
        assert metadata["season"] is None

    def test_extract_doc_metadata_episode_season_type_error(self, parser):
        """Test TypeError handling in episode/season parsing."""
        mock_doc = MagicMock(spec=object)
        # These should trigger TypeError in int() conversion
        mock_doc.title_values = {
            "episode": ["list", "not", "string"],  # TypeError
            "season": {"dict": "not string"},  # TypeError
        }

        _, _, metadata = parser._extract_doc_metadata(mock_doc)
        # Should keep as original values when int conversion fails
        assert metadata["episode"] == ["list", "not", "string"]
        assert metadata["season"] == {"dict": "not string"}

    def test_extract_doc_metadata_empty_title_values(self, parser):
        """Test when title_values is empty dict."""
        mock_doc = MagicMock(spec=object)
        mock_doc.title_values = {}

        title, author, metadata = parser._extract_doc_metadata(mock_doc)
        assert title is None
        assert author is None
        assert metadata == {}

    def test_extract_doc_metadata_none_title_values(self, parser):
        """Test when title_values is None."""
        mock_doc = MagicMock(spec=object)
        mock_doc.title_values = None

        title, author, metadata = parser._extract_doc_metadata(mock_doc)
        assert title is None
        assert author is None
        assert metadata == {}

    # =============================================
    # Tests for _process_scenes method
    # =============================================

    def test_process_scenes_empty_scenes_list(self, parser):
        """Test _process_scenes with empty scenes list."""
        mock_doc = MagicMock(spec=object)
        mock_doc.scenes = []

        scenes = parser._process_scenes(mock_doc, "Empty content")
        assert scenes == []

    def test_process_scenes_scenes_without_headers(self, parser):
        """Test _process_scenes skips scenes without headers (line 127)."""
        # Create scenes without headers (like FADE IN)
        mock_scene1 = MagicMock(spec=object)
        mock_scene1.header = None  # No header

        mock_scene2 = MagicMock(spec=object)
        mock_scene2.header = ""  # Empty header

        mock_scene3 = MagicMock(spec=object)
        mock_scene3.header = "INT. ROOM - DAY"  # Valid header
        mock_scene3.paragraphs = []

        mock_doc = MagicMock(spec=object)
        mock_doc.scenes = [mock_scene1, mock_scene2, mock_scene3]

        content = "FADE IN:\n\nINT. ROOM - DAY\n\nAction."

        with patch.object(parser.processor, "process_jouvence_scene") as mock_process:
            mock_process.return_value = Scene(
                number=1,
                heading="INT. ROOM - DAY",
                content="test",
                original_text="test",
                content_hash="hash",
            )

            scenes = parser._process_scenes(mock_doc, content)

            # Only one scene should be processed (the one with header)
            assert len(scenes) == 1
            # process_jouvence_scene should be called only once for valid scene
            mock_process.assert_called_once()

    def test_process_scenes_scene_numbering(self, parser):
        """Test scene numbering increments correctly."""
        # Create multiple scenes with headers
        mock_scene1 = MagicMock(spec=object)
        mock_scene1.header = "INT. ROOM - DAY"
        mock_scene1.paragraphs = []

        mock_scene2 = MagicMock(spec=object)
        mock_scene2.header = None  # Skip this one

        mock_scene3 = MagicMock(spec=object)
        mock_scene3.header = "EXT. PARK - NIGHT"
        mock_scene3.paragraphs = []

        mock_doc = MagicMock(spec=object)
        mock_doc.scenes = [mock_scene1, mock_scene2, mock_scene3]

        content = "INT. ROOM - DAY\n\nEXT. PARK - NIGHT\n"

        with patch.object(parser.processor, "process_jouvence_scene") as mock_process:

            def mock_scene_processor(number, scene, content):
                return Scene(
                    number=number,
                    heading=scene.header,
                    content="test",
                    original_text="test",
                    content_hash="hash",
                )

            mock_process.side_effect = mock_scene_processor

            scenes = parser._process_scenes(mock_doc, content)

            # Check that scene numbering is correct (1, 2 not 1, 3)
            assert len(scenes) == 2
            assert scenes[0].number == 1
            assert scenes[1].number == 2

    # =============================================
    # Tests for parse method
    # =============================================

    def test_parse_calls_jouvence_parse_string(self, parser):
        """Test that parse method calls JouvenceParser.parseString correctly."""
        content = "Title: Test\n\nINT. ROOM - DAY\n\nAction."

        with patch(
            "scriptrag.parser.fountain_parser.JouvenceParser"
        ) as mock_parser_class:
            mock_parser = Mock(spec=["parseString"])
            mock_parser_class.return_value = mock_parser

            mock_doc = MagicMock(spec=object)
            mock_doc.title_values = {"title": "Test"}
            mock_doc.scenes = []
            mock_parser.parseString.return_value = mock_doc

            result = parser.parse(content)

            # Verify parseString was called with cleaned content
            mock_parser.parseString.assert_called_once()
            called_content = mock_parser.parseString.call_args[0][0]
            # Content should be cleaned (no boneyard comments)
            assert called_content  # Should have some content

            assert isinstance(result, Script)
            assert result.title == "Test"

    def test_parse_with_boneyard_content_cleaned(self, parser):
        """Test that parse method properly cleans boneyard content."""
        content = """Title: Test

/* This should be removed */

INT. ROOM - DAY

/* SCRIPTRAG-META-START
{"key": "value"}
SCRIPTRAG-META-END */

Action line.
"""

        with patch(
            "scriptrag.parser.fountain_parser.JouvenceParser"
        ) as mock_parser_class:
            mock_parser = Mock(spec=["parseString"])
            mock_parser_class.return_value = mock_parser

            mock_doc = MagicMock(spec=object)
            mock_doc.title_values = {}
            mock_doc.scenes = []
            mock_parser.parseString.return_value = mock_doc

            parser.parse(content)

            # Check that cleaned content was passed to jouvence
            called_content = mock_parser.parseString.call_args[0][0]
            assert "/*" not in called_content
            assert "*/" not in called_content
            assert "This should be removed" not in called_content
            assert "SCRIPTRAG-META-START" not in called_content
            assert "Title: Test" in called_content
            assert "INT. ROOM - DAY" in called_content
            assert "Action line." in called_content

    # =============================================
    # Tests for parse_file method
    # =============================================

    def test_parse_file_reads_utf8_encoding(self, parser, tmp_path):
        """Test parse_file reads files with UTF-8 encoding."""
        # Create file with UTF-8 content including special characters
        content = "Title: Tëst Scrîpt\n\nINT. CAFÉ - DAY\n\nAçtion."
        file_path = tmp_path / "test_utf8.fountain"
        file_path.write_text(content, encoding="utf-8")

        with patch(
            "scriptrag.parser.fountain_parser.JouvenceParser"
        ) as mock_parser_class:
            mock_parser = Mock(spec=["parseString"])
            mock_parser_class.return_value = mock_parser

            mock_doc = MagicMock(spec=object)
            mock_doc.title_values = {"title": "Tëst Scrîpt"}
            mock_doc.scenes = []
            mock_parser.parseString.return_value = mock_doc

            result = parser.parse_file(file_path)

            # Verify UTF-8 characters are preserved
            assert result.title == "Tëst Scrîpt"
            assert result.metadata["source_file"] == str(file_path)

            # Verify parseString was called with UTF-8 content
            called_content = mock_parser.parseString.call_args[0][0]
            assert "Tëst Scrîpt" in called_content
            assert "CAFÉ" in called_content
            assert "Açtion." in called_content

    def test_parse_file_jouvence_exception_handling(self, parser, tmp_path):
        """Test parse_file handles jouvence exceptions properly."""
        content = "Invalid fountain content"
        file_path = tmp_path / "invalid.fountain"
        file_path.write_text(content)

        with patch(
            "scriptrag.parser.fountain_parser.JouvenceParser"
        ) as mock_parser_class:
            mock_parser = Mock(spec=["parseString"])
            mock_parser_class.return_value = mock_parser
            # Simulate jouvence parser failure
            mock_parser.parseString.side_effect = RuntimeError(
                "Jouvence parsing failed"
            )

            with pytest.raises(ParseError) as exc_info:
                parser.parse_file(file_path)

            # Verify ParseError details
            error = exc_info.value
            assert "Failed to parse Fountain file" in str(error)
            assert str(file_path) in str(error)
            assert "Jouvence parsing failed" in error.details["parser_error"]
            assert "Check Fountain syntax and format." in error.hint
            assert error.details["file"] == str(file_path)
            assert (
                "Unclosed notes, invalid headings, bad title" in error.details["issues"]
            )

    def test_parse_file_adds_source_file_metadata(self, parser, tmp_path):
        """Test parse_file adds source_file to metadata."""
        content = "Title: Test\n\nINT. ROOM - DAY\n\nAction."
        file_path = tmp_path / "source_test.fountain"
        file_path.write_text(content)

        with patch(
            "scriptrag.parser.fountain_parser.JouvenceParser"
        ) as mock_parser_class:
            mock_parser = Mock(spec=["parseString"])
            mock_parser_class.return_value = mock_parser

            mock_doc = MagicMock(spec=object)
            mock_doc.title_values = {}
            mock_doc.scenes = []
            mock_parser.parseString.return_value = mock_doc

            result = parser.parse_file(file_path)

            assert result.metadata["source_file"] == str(file_path)

    # =============================================
    # Tests for write_with_updated_scenes method
    # =============================================

    def test_write_with_updated_scenes_dry_run_mode(self, parser, tmp_path):
        """Test write_with_updated_scenes respects dry_run parameter (line 222)."""
        original_content = "Title: Test\n\nINT. ROOM - DAY\n\nAction."
        file_path = tmp_path / "dry_run_test.fountain"
        file_path.write_text(original_content)

        # Create a fake script and scene
        script = Script(title="Test", author=None, scenes=[])
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="content",
            original_text="original",
            content_hash="hash",
        )
        scene.has_new_metadata = True
        scene.boneyard_metadata = {"test": "value"}

        # Call with dry_run=True
        parser.write_with_updated_scenes(file_path, script, [scene], dry_run=True)

        # File should be unchanged
        updated_content = file_path.read_text()
        assert updated_content == original_content
        assert "test" not in updated_content
        assert "SCRIPTRAG-META-START" not in updated_content

    def test_write_with_updated_scenes_no_new_metadata_scenes(self, parser, tmp_path):
        """Test write_with_updated_scenes when no scenes have new metadata."""
        original_content = "Title: Test\n\nINT. ROOM - DAY\n\nAction."
        file_path = tmp_path / "no_metadata_test.fountain"
        file_path.write_text(original_content)

        script = Script(title="Test", author=None, scenes=[])
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="content",
            original_text="original",
            content_hash="hash",
        )
        # No new metadata flag set (has_new_metadata defaults to False)

        parser.write_with_updated_scenes(file_path, script, [scene])

        # Content should be unchanged except for potential newline addition
        updated_content = file_path.read_text()
        assert updated_content.startswith(original_content)
        # Should ensure newline at end
        assert updated_content.endswith("\n")
        assert "SCRIPTRAG-META-START" not in updated_content

    def test_write_with_updated_scenes_no_ending_newline(self, parser, tmp_path):
        """Test write_with_updated_scenes adds newline when content missing one."""
        # Content without ending newline
        original_content = "Title: Test\n\nINT. ROOM - DAY\n\nAction."
        file_path = tmp_path / "no_newline_test.fountain"
        file_path.write_text(original_content)  # No ending newline

        script = Script(title="Test", author=None, scenes=[])
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="content",
            original_text="original",
            content_hash="hash",
        )
        # No new metadata

        parser.write_with_updated_scenes(file_path, script, [scene])

        updated_content = file_path.read_text()
        # Should add newline at end (line 232-233)
        assert updated_content == original_content + "\n"

    def test_write_with_updated_scenes_scene_with_new_metadata(self, parser, tmp_path):
        """Test write_with_updated_scenes processes scenes with new metadata."""
        original_content = """Title: Test

INT. ROOM - DAY

Original scene action.
"""
        file_path = tmp_path / "metadata_test.fountain"
        file_path.write_text(original_content)

        # Create scene with same original text
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="content",
            original_text="INT. ROOM - DAY\n\nOriginal scene action.",
            content_hash="hash123",
        )
        scene.has_new_metadata = True
        scene.boneyard_metadata = {"analyzer": "test", "result": "success"}

        script = Script(title="Test", author=None, scenes=[scene])

        with patch.object(parser.processor, "update_scene_boneyard") as mock_update:
            mock_update.return_value = (
                original_content
                + "\n\n/* SCRIPTRAG-META-START\n"
                + '{"analyzer": "test"}\nSCRIPTRAG-META-END */\n'
            )

            parser.write_with_updated_scenes(file_path, script, [scene])

            # Verify update_scene_boneyard was called
            mock_update.assert_called_once_with(
                original_content, scene.original_text, scene.boneyard_metadata
            )

    def test_write_with_updated_scenes_content_ends_with_newline(
        self, parser, tmp_path
    ):
        """Test write_with_updated_scenes preserves ending newline (line 251-252)."""
        # Content already ends with newline
        original_content = "Title: Test\n\nINT. ROOM - DAY\n\nAction.\n"
        file_path = tmp_path / "has_newline_test.fountain"
        file_path.write_text(original_content)

        script = Script(title="Test", author=None, scenes=[])
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="content",
            original_text="original",
            content_hash="hash",
        )

        parser.write_with_updated_scenes(file_path, script, [scene])

        updated_content = file_path.read_text()
        # Should not double the newline
        assert updated_content == original_content
        assert not updated_content.endswith("\n\n")

    def test_write_with_updated_scenes_multiple_scenes_updates(self, parser, tmp_path):
        """Test write_with_updated_scenes handles multiple scene updates."""
        original_content = """Title: Test

INT. ROOM - DAY

First scene.

EXT. PARK - NIGHT

Second scene.
"""
        file_path = tmp_path / "multiple_scenes_test.fountain"
        file_path.write_text(original_content)

        scene1 = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="content1",
            original_text="INT. ROOM - DAY\n\nFirst scene.",
            content_hash="hash1",
        )
        scene1.has_new_metadata = True
        scene1.boneyard_metadata = {"scene": "first"}

        scene2 = Scene(
            number=2,
            heading="EXT. PARK - NIGHT",
            content="content2",
            original_text="EXT. PARK - NIGHT\n\nSecond scene.",
            content_hash="hash2",
        )
        scene2.has_new_metadata = True
        scene2.boneyard_metadata = {"scene": "second"}

        script = Script(title="Test", author=None, scenes=[scene1, scene2])

        with patch.object(parser.processor, "update_scene_boneyard") as mock_update:
            mock_update.side_effect = [
                original_content.replace("First scene.", "First scene.\n\n/* META1 */"),
                original_content.replace(
                    "Second scene.", "Second scene.\n\n/* META2 */"
                ),
            ]

            parser.write_with_updated_scenes(file_path, script, [scene1, scene2])

            # Should be called twice, once for each scene
            assert mock_update.call_count == 2

    # =============================================
    # Tests for edge cases and error conditions
    # =============================================

    def test_parse_with_complex_metadata_combinations(self, parser):
        """Test parsing with various metadata field combinations."""
        content = """Title: Complex Test
Author: Multi Author
Writers: Override Author
Series: Primary Series
Series_Title: Secondary
Show: Tertiary
Project: Primary Project
Project_Title: Secondary
Episode: 99
Season: 5

INT. COMPLEX - DAY

Complex action.
"""

        script = parser.parse(content)

        # Author priority: author field should win
        assert script.author == "Multi Author"

        # Series priority: series should win
        assert script.metadata["series_title"] == "Primary Series"

        # Project priority: project should win
        assert script.metadata["project_title"] == "Primary Project"

        # Numbers should be converted
        assert script.metadata["episode"] == 99
        assert script.metadata["season"] == 5

    def test_init_creates_processor_and_pattern(self, parser):
        """Test that __init__ properly initializes processor and pattern."""
        assert hasattr(parser, "processor")
        assert hasattr(parser, "BONEYARD_PATTERN")
        assert parser.BONEYARD_PATTERN == parser.processor.BONEYARD_PATTERN

    def test_parse_empty_content(self, parser):
        """Test parsing empty or minimal content."""
        with patch(
            "scriptrag.parser.fountain_parser.JouvenceParser"
        ) as mock_parser_class:
            mock_parser = Mock(spec=["parseString"])
            mock_parser_class.return_value = mock_parser

            mock_doc = MagicMock(spec=object)
            mock_doc.title_values = None
            mock_doc.scenes = []
            mock_parser.parseString.return_value = mock_doc

            result = parser.parse("")

            assert result.title is None
            assert result.author is None
            assert len(result.scenes) == 0
            assert result.metadata == {}

    def test_parse_file_with_empty_file(self, parser, tmp_path):
        """Test parse_file with empty file."""
        file_path = tmp_path / "empty.fountain"
        file_path.write_text("")

        with patch(
            "scriptrag.parser.fountain_parser.JouvenceParser"
        ) as mock_parser_class:
            mock_parser = Mock(spec=["parseString"])
            mock_parser_class.return_value = mock_parser

            mock_doc = MagicMock(spec=object)
            mock_doc.title_values = None
            mock_doc.scenes = []
            mock_parser.parseString.return_value = mock_doc

            result = parser.parse_file(file_path)

            assert result.metadata["source_file"] == str(file_path)
            assert len(result.scenes) == 0

    @pytest.mark.parametrize(
        "exception_type,exception_msg",
        [
            (RuntimeError, "Runtime error in jouvence"),
            (ValueError, "Value error in parsing"),
            (TypeError, "Type error in parsing"),
            (KeyError, "Key error in parsing"),
            (IndexError, "Index error in parsing"),
        ],
    )
    def test_parse_file_handles_various_exceptions(
        self, parser, tmp_path, exception_type, exception_msg
    ):
        """Test parse_file handles various jouvence exceptions."""
        file_path = tmp_path / "error_test.fountain"
        file_path.write_text("Test content")

        with patch(
            "scriptrag.parser.fountain_parser.JouvenceParser"
        ) as mock_parser_class:
            mock_parser = Mock(spec=["parseString"])
            mock_parser_class.return_value = mock_parser
            mock_parser.parseString.side_effect = exception_type(exception_msg)

            with pytest.raises(ParseError) as exc_info:
                parser.parse_file(file_path)

            error = exc_info.value
            assert exception_msg in error.details["parser_error"]
            assert str(file_path) in error.details["file"]

    def test_write_with_updated_scenes_empty_content_handling(self, parser, tmp_path):
        """Test write_with_updated_scenes with edge case of empty content."""
        # Empty file
        file_path = tmp_path / "empty_content_test.fountain"
        file_path.write_text("")  # Empty content

        script = Script(title="Test", author=None, scenes=[])
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="content",
            original_text="original",
            content_hash="hash",
        )
        # No new metadata, so should only handle newline logic

        parser.write_with_updated_scenes(file_path, script, [scene])

        # Empty content case: line 229 check fails, no scenes have new_metadata
        # so only newline logic applies. But empty content + not ending with \n
        # means content is "" which is falsy, so line 231-232 doesn't execute
        updated_content = file_path.read_text()
        assert updated_content == ""  # Empty content remains empty

    def test_debug_log_message_in_parse_file(self, parser, tmp_path):
        """Test that parse_file logs debug message (line 177)."""
        file_path = tmp_path / "debug_test.fountain"
        file_path.write_text("Title: Debug Test\n\nINT. ROOM - DAY\n\nAction.")

        with patch("scriptrag.parser.fountain_parser.logger") as mock_logger:
            with patch(
                "scriptrag.parser.fountain_parser.JouvenceParser"
            ) as mock_parser_class:
                mock_parser = Mock(spec=["parseString"])
                mock_parser_class.return_value = mock_parser

                mock_doc = MagicMock(spec=object)
                mock_doc.title_values = {}
                mock_doc.scenes = []
                mock_parser.parseString.return_value = mock_doc

                parser.parse_file(file_path)

                # Verify debug log was called
                mock_logger.debug.assert_called_once_with(
                    f"Parsing fountain file: {file_path}"
                )

    def test_error_log_message_in_parse_file_exception(self, parser, tmp_path):
        """Test that parse_file logs error message on exception (line 182)."""
        file_path = tmp_path / "error_log_test.fountain"
        file_path.write_text("Invalid content")

        with patch("scriptrag.parser.fountain_parser.logger") as mock_logger:
            with patch(
                "scriptrag.parser.fountain_parser.JouvenceParser"
            ) as mock_parser_class:
                mock_parser = Mock(spec=["parseString"])
                mock_parser_class.return_value = mock_parser
                error_msg = "Test parsing error"
                mock_parser.parseString.side_effect = RuntimeError(error_msg)

                with pytest.raises(ParseError):
                    parser.parse_file(file_path)

                # Verify error log was called
                mock_logger.error.assert_called_once_with(
                    f"Jouvence parser failed: {error_msg}"
                )

    def test_success_log_message_in_write_with_updated_scenes(self, parser, tmp_path):
        """Test success log message in write_with_updated_scenes (line 254)."""
        original_content = "Title: Test\n\nINT. ROOM - DAY\n\nAction.\n"
        file_path = tmp_path / "success_log_test.fountain"
        file_path.write_text(original_content)

        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="content",
            original_text="INT. ROOM - DAY\n\nAction.",
            content_hash="hash",
        )
        scene.has_new_metadata = True
        scene.boneyard_metadata = {"test": "value"}

        script = Script(title="Test", author=None, scenes=[scene])

        with patch("scriptrag.parser.fountain_parser.logger") as mock_logger:
            with patch.object(parser.processor, "update_scene_boneyard") as mock_update:
                mock_update.return_value = original_content + "/* METADATA */"

                parser.write_with_updated_scenes(file_path, script, [scene])

                # Verify success log was called
                mock_logger.info.assert_called_once_with(
                    f"Updated 1 scenes in {file_path}"
                )


class TestFountainParserIntegration:
    """Integration tests with real fountain content."""

    @pytest.fixture
    def parser(self):
        """Create a FountainParser instance."""
        return FountainParser()

    def test_real_fountain_parsing_integration(self, parser):
        """Test parsing real fountain content end-to-end."""
        content = """Title: Integration Test
Author: Test Holmes
Episode: 1
Season: 1
Series: Holmes Cases
Project: Season 1 Scripts

FADE IN:

INT. BAKER STREET - DAY

SHERLOCK HOLMES sits in his chair.

HOLMES
(deducing)
The game is afoot, Watson!

DR. WATSON
What have you observed?

HOLMES
Observe the mud on the visitor's boots.

/* SCRIPTRAG-META-START
{
    "content_hash": "abc123",
    "analyzed_at": "2024-01-01T12:00:00Z",
    "analyzers": {
        "character_analyzer": {
            "characters": ["HOLMES", "DR. WATSON"]
        }
    }
}
SCRIPTRAG-META-END */

EXT. LONDON STREET - DAY

They walk down the foggy street.

FADE OUT.
"""

        script = parser.parse(content)

        # Test metadata extraction
        assert script.title == "Integration Test"
        assert script.author == "Test Holmes"
        assert script.metadata["episode"] == 1
        assert script.metadata["season"] == 1
        assert script.metadata["series_title"] == "Holmes Cases"
        assert script.metadata["project_title"] == "Season 1 Scripts"

        # Test scene parsing
        assert len(script.scenes) == 2

        # First scene
        scene1 = script.scenes[0]
        assert scene1.heading == "INT. BAKER STREET - DAY"
        assert scene1.type == "INT"
        assert scene1.location == "BAKER STREET"
        assert scene1.time_of_day == "DAY"

        # Check dialogue was parsed
        dialogue_chars = {d.character for d in scene1.dialogue_lines}
        assert "HOLMES" in dialogue_chars
        assert "DR. WATSON" in dialogue_chars

        # Find Holmes' dialogue with parenthetical
        holmes_dialogue = None
        for d in scene1.dialogue_lines:
            if d.character == "HOLMES" and d.parenthetical:
                holmes_dialogue = d
                break

        assert holmes_dialogue is not None
        assert holmes_dialogue.parenthetical == "(deducing)"
        assert holmes_dialogue.text == "The game is afoot, Watson!"

        # Check boneyard metadata was extracted
        assert scene1.boneyard_metadata is not None
        assert scene1.boneyard_metadata["content_hash"] == "abc123"
        assert "character_analyzer" in scene1.boneyard_metadata["analyzers"]

        # Second scene
        scene2 = script.scenes[1]
        assert scene2.heading == "EXT. LONDON STREET - DAY"
        assert scene2.type == "EXT"
        assert scene2.location == "LONDON STREET"
        assert scene2.time_of_day == "DAY"

    def test_write_and_read_roundtrip_integration(self, parser, tmp_path):
        """Test complete write and read roundtrip."""
        original_content = """Title: Roundtrip Test
Author: Detective Holmes

INT. STUDY - EVENING

The detective examines the evidence.

DETECTIVE
Most curious indeed.

EXT. GARDEN - NIGHT

The moon illuminates the scene.
"""

        file_path = tmp_path / "roundtrip_test.fountain"
        file_path.write_text(original_content)

        # Parse original
        script1 = parser.parse_file(file_path)

        # Add metadata to scenes
        for i, scene in enumerate(script1.scenes):
            scene.update_boneyard(
                {
                    "scene_number": i + 1,
                    "analyzed_at": "2024-01-01",
                    "analysis_complete": True,
                }
            )

        # Write back with metadata
        parser.write_with_updated_scenes(file_path, script1, script1.scenes)

        # Parse again
        script2 = parser.parse_file(file_path)

        # Verify original data preserved
        assert script2.title == script1.title
        assert script2.author == script1.author
        assert len(script2.scenes) == len(script1.scenes)

        # Verify metadata was added
        for i, scene in enumerate(script2.scenes):
            assert scene.boneyard_metadata is not None
            assert scene.boneyard_metadata["scene_number"] == i + 1
            assert scene.boneyard_metadata["analyzed_at"] == "2024-01-01"
            assert scene.boneyard_metadata["analysis_complete"] is True
