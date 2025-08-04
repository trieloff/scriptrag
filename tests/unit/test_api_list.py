"""Unit tests for scriptrag list API."""

from pathlib import Path
from unittest.mock import patch

import pytest

from scriptrag.api.list import FountainMetadata, ScriptLister


class TestFountainMetadata:
    """Test FountainMetadata class."""

    def test_display_title_with_title_only(self):
        """Test display title with only title set."""
        metadata = FountainMetadata(
            file_path=Path("/test/script.fountain"), title="My Script"
        )
        assert metadata.display_title == "My Script"

    def test_display_title_with_season_and_episode(self):
        """Test display title with season and episode."""
        metadata = FountainMetadata(
            file_path=Path("/test/script.fountain"),
            title="My Series",
            season_number=2,
            episode_number=5,
        )
        assert metadata.display_title == "My Series (S02E05)"

    def test_display_title_with_episode_only(self):
        """Test display title with only episode number."""
        metadata = FountainMetadata(
            file_path=Path("/test/script.fountain"),
            title="My Series",
            episode_number=3,
        )
        assert metadata.display_title == "My Series (Episode 3)"

    def test_display_title_no_title(self):
        """Test display title when no title is set."""
        metadata = FountainMetadata(file_path=Path("/test/my_script.fountain"))
        assert metadata.display_title == "my_script"

    def test_is_series_with_season(self):
        """Test is_series property with season number."""
        metadata = FountainMetadata(
            file_path=Path("/test/script.fountain"), season_number=1
        )
        assert metadata.is_series is True

    def test_is_series_with_episode(self):
        """Test is_series property with episode number."""
        metadata = FountainMetadata(
            file_path=Path("/test/script.fountain"), episode_number=1
        )
        assert metadata.is_series is True

    def test_is_series_standalone(self):
        """Test is_series property for standalone script."""
        metadata = FountainMetadata(file_path=Path("/test/script.fountain"))
        assert metadata.is_series is False


class TestScriptLister:
    """Test ScriptLister class."""

    @pytest.fixture
    def lister(self):
        """Create a ScriptLister instance."""
        return ScriptLister()

    def test_list_scripts_nonexistent_path(self, lister):
        """Test listing scripts with nonexistent path."""
        result = lister.list_scripts(Path("/nonexistent"))
        assert result == []

    def test_list_scripts_file_not_fountain(self, lister, tmp_path):
        """Test listing scripts when path is non-fountain file."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Not a fountain file")

        result = lister.list_scripts(txt_file)
        assert result == []

    def test_list_scripts_single_fountain_file(self, lister, tmp_path):
        """Test listing single fountain file."""
        fountain_file = tmp_path / "test.fountain"
        fountain_file.write_text("Title: Test Script\n\nFADE IN:")

        result = lister.list_scripts(fountain_file)
        assert len(result) == 1
        assert result[0].file_path == fountain_file
        assert result[0].title == "Test Script"

    def test_list_scripts_directory_recursive(self, lister, tmp_path):
        """Test listing scripts recursively in directory."""
        # Create nested structure
        (tmp_path / "sub").mkdir()
        script1 = tmp_path / "script1.fountain"
        script2 = tmp_path / "sub" / "script2.fountain"
        script1.write_text("Title: Script 1")
        script2.write_text("Title: Script 2")

        result = lister.list_scripts(tmp_path, recursive=True)
        assert len(result) == 2
        titles = [r.title for r in result]
        assert "Script 1" in titles
        assert "Script 2" in titles

    def test_list_scripts_directory_non_recursive(self, lister, tmp_path):
        """Test listing scripts non-recursively."""
        # Create nested structure
        (tmp_path / "sub").mkdir()
        script1 = tmp_path / "script1.fountain"
        script2 = tmp_path / "sub" / "script2.fountain"
        script1.write_text("Title: Script 1")
        script2.write_text("Title: Script 2")

        result = lister.list_scripts(tmp_path, recursive=False)
        assert len(result) == 1
        assert result[0].title == "Script 1"

    def test_list_scripts_handles_parse_errors(self, lister, tmp_path):
        """Test that list continues even if some files fail to parse."""
        script1 = tmp_path / "good.fountain"
        script2 = tmp_path / "bad.fountain"
        script1.write_text("Title: Good Script")
        script2.write_text("Title: Bad Script")

        # Mock parse to fail for one file
        with patch.object(lister, "_parse_fountain_metadata") as mock_parse:
            mock_parse.side_effect = [
                FountainMetadata(file_path=script1, title="Good Script"),
                Exception("Parse error"),
            ]

            result = lister.list_scripts(tmp_path)
            assert len(result) == 1
            assert result[0].title == "Good Script"

    def test_parse_fountain_metadata_handles_read_error(self, lister, tmp_path):
        """Test parsing metadata when file cannot be read."""
        script = tmp_path / "unreadable.fountain"
        script.write_text("Title: Test")

        with patch.object(Path, "read_text", side_effect=PermissionError("No access")):
            metadata = lister._parse_fountain_metadata(script)
            assert metadata.file_path == script
            assert metadata.title is None  # Could not read title

    def test_extract_title_page_info_basic(self, lister):
        """Test extracting basic title page information."""
        content = """Title: My Great Script
Author: John Doe
Draft date: 2024-01-01

FADE IN:"""

        info = lister._extract_title_page_info(content)
        assert info["title"] == "My Great Script"
        assert info["author"] == "John Doe"

    def test_extract_title_page_info_with_episode(self, lister):
        """Test extracting episode information from title page."""
        content = """Title: My Series - Episode 5
Author: Jane Smith
Episode: 5
Season: 2"""

        info = lister._extract_title_page_info(content)
        assert info["title"] == "My Series - Episode 5"
        assert info["author"] == "Jane Smith"
        assert info["episode_number"] == 5
        assert info["season_number"] == 2

    def test_extract_title_page_info_episode_in_title(self, lister):
        """Test extracting episode number from title."""
        content = """Title: Show Name S02E10
Author: Writer"""

        info = lister._extract_title_page_info(content)
        assert info["episode_number"] == 10
        assert info["season_number"] == 2

    def test_extract_title_page_info_various_author_fields(self, lister):
        """Test various author field names."""
        variations = [
            ("Authors: Multiple Authors", "Multiple Authors"),
            ("Written by: Screenplay Writer", "Screenplay Writer"),
            ("Writer: Solo Writer", "Solo Writer"),
            ("Writers: Writer Team", "Writer Team"),
        ]

        for content, expected in variations:
            info = lister._extract_title_page_info(f"Title: Test\n{content}")
            assert info["author"] == expected

    def test_extract_title_page_info_no_double_newline(self, lister):
        """Test extraction when no double newline separator."""
        content = """Title: My Script
Author: John Doe
This is all one block without clear separation."""

        info = lister._extract_title_page_info(content)
        assert info["title"] == "My Script"
        assert info["author"] == "John Doe"

    def test_extract_title_page_multi_line_values(self, lister):
        """Test extracting multi-line indented values."""
        content = """Title:
    Line One
    Line Two
Author: Jane Smith
Contact:
    123 Main Street
    Suite 100
    New York, NY 10001

FADE IN:"""

        info = lister._extract_title_page_info(content)
        assert info["title"] == "Line One\nLine Two"
        assert info["author"] == "Jane Smith"

    def test_extract_title_page_formatting_marks(self, lister):
        """Test removing formatting marks from titles."""
        content = """Title:
    _**BRICK & STEEL**_
    _**FULL RETIRED**_
Author: Stu Maschwitz

FADE IN:"""

        info = lister._extract_title_page_info(content)
        assert info["title"] == "BRICK & STEEL\nFULL RETIRED"
        assert info["author"] == "Stu Maschwitz"

    def test_extract_title_page_tab_indentation(self, lister):
        """Test that tab indentation works for multi-line values."""
        content = """Title:
\tPart One
\tPart Two
Author: Test Author

FADE IN:"""

        info = lister._extract_title_page_info(content)
        assert info["title"] == "Part One\nPart Two"

    def test_extract_from_filename_s_e_format(self, lister):
        """Test extracting from S##E## filename format."""
        info = lister._extract_from_filename("show_S01E05_title")
        assert info["season"] == 1
        assert info["episode"] == 5

    def test_extract_from_filename_x_format(self, lister):
        """Test extracting from ##x## filename format."""
        info = lister._extract_from_filename("show_2x10")
        assert info["season"] == 2
        assert info["episode"] == 10

    def test_extract_from_filename_episode_format(self, lister):
        """Test extracting from Episode ## format."""
        info = lister._extract_from_filename("show_Episode_7")
        assert info["season"] is None
        assert info["episode"] == 7

        info = lister._extract_from_filename("show_episode-12")
        assert info["episode"] == 12

    def test_extract_from_filename_ep_format(self, lister):
        """Test extracting from Ep ## format."""
        info = lister._extract_from_filename("show_Ep_3")
        assert info["season"] is None
        assert info["episode"] == 3

        info = lister._extract_from_filename("show_ep-15")
        assert info["episode"] == 15

    def test_extract_from_filename_no_match(self, lister):
        """Test extracting from filename with no episode info."""
        info = lister._extract_from_filename("regular_script_name")
        assert info["season"] is None
        assert info["episode"] is None

    def test_parse_fountain_metadata_combines_sources(self, lister, tmp_path):
        """Test that metadata combines title page and filename info."""
        # Script with episode in title page but not season
        script = tmp_path / "show_S02E05.fountain"
        script.write_text("""Title: My Show
Episode: 5

FADE IN:""")

        metadata = lister._parse_fountain_metadata(script)
        assert metadata.title == "My Show"
        assert metadata.episode_number == 5
        assert metadata.season_number == 2  # From filename

    def test_parse_fountain_metadata_prefers_title_page(self, lister, tmp_path):
        """Test that title page info takes precedence over filename."""
        script = tmp_path / "show_S01E01.fountain"
        script.write_text("""Title: My Show
Episode: 10
Season: 2

FADE IN:""")

        metadata = lister._parse_fountain_metadata(script)
        assert metadata.episode_number == 10  # From title page, not filename
        assert metadata.season_number == 2  # From title page, not filename
