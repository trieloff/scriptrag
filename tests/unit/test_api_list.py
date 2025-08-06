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

    def test_list_scripts_default_path(self, lister, tmp_path, monkeypatch):
        """Test listing scripts with default path (current directory)."""
        # Create scripts in temp directory
        script1 = tmp_path / "test1.fountain"
        script1.write_text("Title: Test Script 1")

        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Call without path argument
        result = lister.list_scripts()
        assert len(result) == 1
        assert result[0].title == "Test Script 1"
        assert result[0].file_path == script1

    def test_parse_fountain_with_markdown_title(self, lister, tmp_path):
        """Test parsing fountain with markdown formatted title."""
        script = tmp_path / "test.fountain"
        script.write_text("""Title: _**My Script**_
Author: Test Author

FADE IN:""")

        metadata = lister._parse_fountain_metadata(script)
        # Note: Currently markdown is not stripped in title extraction
        assert metadata.title == "_**My Script**_"

    def test_parse_fountain_extract_season_from_title(self, lister, tmp_path):
        """Test extracting season from title with markdown."""
        script = tmp_path / "test.fountain"
        script.write_text("""Title: _**My Show Season 3**_
Episode: 5

FADE IN:""")

        metadata = lister._parse_fountain_metadata(script)
        assert metadata.season_number == 3  # Markdown is stripped for season extraction
        assert metadata.episode_number == 5

    def test_parse_with_fallback_no_blank_line(self, lister, tmp_path):
        """Test fallback parsing when no blank line after title page."""
        script = tmp_path / "test.fountain"
        script.write_text("Title: My Script\nAuthor: Test Author")

        with patch("scriptrag.api.list.FountainParser") as mock_parser:
            mock_parser.return_value.parse_file.side_effect = Exception("Parse failed")
            metadata = lister._parse_fountain_metadata(script)

        assert metadata.title == "My Script"
        assert metadata.author == "Test Author"

    def test_parse_with_fallback_different_author_formats(self, lister, tmp_path):
        """Test fallback parsing with different author format variations."""
        test_cases = [
            ("Authors: John Doe", "John Doe"),
            ("Written by: Jane Smith", "Jane Smith"),
            ("Writer: Bob Johnson", "Bob Johnson"),
            ("Writers: Alice & Bob", "Alice & Bob"),
        ]

        for author_line, expected_author in test_cases:
            script = tmp_path / f"test_{expected_author.replace(' ', '_')}.fountain"
            script.write_text(f"Title: Test\n{author_line}\n\nFADE IN:")

            with patch("scriptrag.api.list.FountainParser") as mock_parser:
                mock_parser.return_value.parse_file.side_effect = Exception(
                    "Parse failed"
                )
                metadata = lister._parse_fountain_metadata(script)

            assert metadata.author == expected_author, f"Failed for: {author_line}"

    def test_parse_fountain_filename_season_extraction(self, lister, tmp_path):
        """Test that season is extracted from filename when not in metadata."""
        # This tests the line 162-163 that was marked as not covered
        script = tmp_path / "show_S02E05.fountain"
        script.write_text("""Title: My Show

FADE IN:""")

        # Mock the parser to return metadata without season but with episode
        with patch("scriptrag.api.list.FountainParser") as mock_parser:
            mock_script = mock_parser.return_value.parse_file.return_value
            mock_script.metadata = {"episode": 5}  # Has episode but not season
            mock_script.title = "My Show"
            mock_script.author = None

            metadata = lister._parse_fountain_metadata(script)

        assert metadata.episode_number == 5  # From metadata
        assert metadata.season_number == 2  # From filename

    def test_parse_fountain_extract_episode_from_title(self, tmp_path):
        """Test extracting episode number from title when in markdown format."""
        lister = ScriptLister()

        # Create a script with episode in title using markdown
        test_file = tmp_path / "script.fountain"
        test_file.write_text("""Title: _**Show Name - Episode 5**_
Author: Test Author

INT. OFFICE - DAY

The scene content.
""")

        # Mock the parser to return the script with markdown title
        with patch("scriptrag.api.list.FountainParser") as mock_parser:
            mock_script = mock_parser.return_value.parse_file.return_value
            mock_script.metadata = {}  # No episode in metadata
            mock_script.title = "_**Show Name - Episode 5**_"
            mock_script.author = "Test Author"

            metadata = lister._parse_fountain_metadata(test_file)

        assert metadata.title == "_**Show Name - Episode 5**_"
        # The episode number should be extracted from the title (line 139)
        assert metadata.episode_number == 5
