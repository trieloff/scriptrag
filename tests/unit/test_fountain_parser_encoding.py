"""Tests for fountain parser encoding error handling."""

from unittest.mock import patch

import pytest

from scriptrag.exceptions import ParseError
from scriptrag.parser.fountain_parser import FountainParser


class TestFountainParserEncoding:
    """Test encoding error handling in FountainParser."""

    @pytest.fixture
    def parser(self):
        """Create a FountainParser instance."""
        return FountainParser()

    def test_parse_file_with_invalid_utf8(self, parser, tmp_path):
        """Test parse_file raises ParseError for non-UTF-8 file."""
        # Create a file with invalid UTF-8 bytes
        test_file = tmp_path / "invalid.fountain"
        test_file.write_bytes(b"\x80\x81\x82\x83")  # Invalid UTF-8 sequence

        with pytest.raises(ParseError) as excinfo:
            parser.parse_file(test_file)

        # Check the error message
        assert "File is not UTF-8 encoded" in str(excinfo.value)
        assert "invalid.fountain" in str(excinfo.value)
        # Check the hint is helpful
        assert "iconv" in excinfo.value.hint
        assert "UTF-8" in excinfo.value.hint
        # Check details contain useful info
        assert "file" in excinfo.value.details
        assert "error" in excinfo.value.details
        assert "byte_position" in excinfo.value.details

    def test_parse_file_with_latin1_encoding(self, parser, tmp_path):
        """Test parse_file raises ParseError for Latin-1 encoded file."""
        # Create a file with Latin-1 encoded content
        test_file = tmp_path / "latin1.fountain"
        # Latin-1 specific characters that are invalid in UTF-8
        content = "Title: Café\n\nINT. CAFÉ - DAY\n\nAction with é."
        test_file.write_bytes(content.encode("latin-1"))

        with pytest.raises(ParseError) as excinfo:
            parser.parse_file(test_file)

        assert "File is not UTF-8 encoded" in str(excinfo.value)
        assert "latin1.fountain" in str(excinfo.value)

    def test_parse_file_with_valid_utf8(self, parser, tmp_path):
        """Test parse_file works correctly with valid UTF-8 file."""
        # Create a valid UTF-8 file
        test_file = tmp_path / "valid.fountain"
        content = "Title: Test\n\nINT. OFFICE - DAY\n\nA simple scene."
        test_file.write_text(content, encoding="utf-8")

        # Should not raise an exception
        result = parser.parse_file(test_file)

        assert result is not None
        assert result.title == "Test"
        assert len(result.scenes) == 1

    def test_parse_file_with_utf8_bom(self, parser, tmp_path):
        """Test parse_file handles UTF-8 with BOM correctly."""
        # Create a UTF-8 file with BOM
        test_file = tmp_path / "utf8_bom.fountain"
        # UTF-8 BOM followed by content
        bom_content = b"\xef\xbb\xbfTitle: Test\n\nINT. OFFICE - DAY\n\nA simple scene."
        test_file.write_bytes(bom_content)

        # Should work since UTF-8 BOM is valid UTF-8
        result = parser.parse_file(test_file)

        assert result is not None
        # BOM might affect title parsing, but shouldn't crash
        assert result.scenes is not None

    def test_parse_file_with_mixed_encoding(self, parser, tmp_path):
        """Test parse_file with file containing mixed/corrupted encoding."""
        # Create a file with mostly UTF-8 but some invalid bytes
        test_file = tmp_path / "mixed.fountain"
        content = b"Title: Test\n\nINT. OFFICE - DAY\n\n"
        content += b"Some text with \x80 invalid byte in the middle.\n"
        content += b"More valid text."
        test_file.write_bytes(content)

        with pytest.raises(ParseError) as excinfo:
            parser.parse_file(test_file)

        assert "File is not UTF-8 encoded" in str(excinfo.value)
        # Check that byte position is included
        assert excinfo.value.details["byte_position"] > 0

    def test_write_with_updated_scenes_with_invalid_utf8(self, parser, tmp_path):
        """Test write_with_updated_scenes raises ParseError for non-UTF-8 file."""
        from scriptrag.parser.fountain_models import Scene, Script

        # Create a file with invalid UTF-8 bytes
        test_file = tmp_path / "invalid.fountain"
        test_file.write_bytes(b"\x80\x81\x82\x83")  # Invalid UTF-8 sequence

        # Create mock script and scenes
        mock_script = Script(title="Test", author=None, scenes=[], metadata={})
        mock_scenes = [
            Scene(
                number=1,
                heading="INT. OFFICE - DAY",
                content="Test scene",
                original_text="INT. OFFICE - DAY\n\nTest scene",
                content_hash="test_hash",
            )
        ]

        with pytest.raises(ParseError) as excinfo:
            parser.write_with_updated_scenes(
                test_file, mock_script, mock_scenes, dry_run=False
            )

        # Check the error message
        assert "File is not UTF-8 encoded" in str(excinfo.value)
        assert "invalid.fountain" in str(excinfo.value)

    def test_write_with_updated_scenes_dry_run_skips_read(self, parser, tmp_path):
        """Test write_with_updated_scenes in dry_run mode doesn't read the file."""
        from scriptrag.parser.fountain_models import Scene, Script

        # Create a file with invalid UTF-8 bytes
        test_file = tmp_path / "invalid.fountain"
        test_file.write_bytes(b"\x80\x81\x82\x83")  # Invalid UTF-8 sequence

        # Create mock script and scenes
        mock_script = Script(title="Test", author=None, scenes=[], metadata={})
        mock_scenes = [
            Scene(
                number=1,
                heading="INT. OFFICE - DAY",
                content="Test scene",
                original_text="INT. OFFICE - DAY\n\nTest scene",
                content_hash="test_hash",
            )
        ]

        # Should not raise because dry_run=True skips reading
        parser.write_with_updated_scenes(
            test_file, mock_script, mock_scenes, dry_run=True
        )

    def test_parse_file_logging(self, parser, tmp_path):
        """Test that encoding errors are properly logged."""
        # Create a file with invalid UTF-8 bytes
        test_file = tmp_path / "invalid.fountain"
        test_file.write_bytes(b"\xff\xfe")  # Invalid UTF-8 sequence

        with patch("scriptrag.parser.fountain_parser.logger") as mock_logger:
            with pytest.raises(ParseError):
                parser.parse_file(test_file)

            # Check that error was logged
            mock_logger.error.assert_called_once()
            log_message = mock_logger.error.call_args[0][0]
            assert "File encoding error" in log_message
            assert "invalid.fountain" in log_message

    def test_write_with_updated_scenes_logging(self, parser, tmp_path):
        """Test encoding errors in write_with_updated_scenes are logged."""
        from scriptrag.parser.fountain_models import Scene, Script

        # Create a file with invalid UTF-8 bytes
        test_file = tmp_path / "invalid.fountain"
        test_file.write_bytes(b"\xff\xfe")  # Invalid UTF-8 sequence

        # Create mock script and scenes
        mock_script = Script(title="Test", author=None, scenes=[], metadata={})
        mock_scenes = [
            Scene(
                number=1,
                heading="INT. OFFICE - DAY",
                content="Test scene",
                original_text="INT. OFFICE - DAY\n\nTest scene",
                content_hash="test_hash",
            )
        ]

        with patch("scriptrag.parser.fountain_parser.logger") as mock_logger:
            with pytest.raises(ParseError):
                parser.write_with_updated_scenes(
                    test_file, mock_script, mock_scenes, dry_run=False
                )

            # Check that error was logged
            mock_logger.error.assert_called_once()
            log_message = mock_logger.error.call_args[0][0]
            assert "File encoding error" in log_message
            assert "invalid.fountain" in log_message

    def test_parse_file_preserves_original_exception(self, parser, tmp_path):
        """Test that the original UnicodeDecodeError is preserved in the chain."""
        # Create a file with invalid UTF-8 bytes
        test_file = tmp_path / "invalid.fountain"
        test_file.write_bytes(b"\x80\x81\x82\x83")  # Invalid UTF-8 sequence

        with pytest.raises(ParseError) as excinfo:
            parser.parse_file(test_file)

        # Check that the original exception is preserved
        assert excinfo.value.__cause__ is not None
        assert isinstance(excinfo.value.__cause__, UnicodeDecodeError)
        # Check that byte position from original error is preserved
        assert excinfo.value.details["byte_position"] == excinfo.value.__cause__.start

    def test_parse_file_with_empty_file(self, parser, tmp_path):
        """Test parse_file handles empty files correctly."""
        # Create an empty file
        test_file = tmp_path / "empty.fountain"
        test_file.write_text("", encoding="utf-8")

        # Should not raise an encoding exception
        result = parser.parse_file(test_file)

        assert result is not None
        assert result.title is None
        assert len(result.scenes) == 0

    def test_parse_file_with_unicode_characters(self, parser, tmp_path):
        """Test parse_file handles files with various unicode characters."""
        # Create a file with various unicode characters
        test_file = tmp_path / "unicode.fountain"
        content = """Title: 日本語タイトル
Author: José García

INT. CAFÉ - DAY

Character speaks: "Hello, 你好, مرحبا, Здравствуйте!"

Action with emojis: 🎬🎭🎪
"""
        test_file.write_text(content, encoding="utf-8")

        # Should work fine with UTF-8
        result = parser.parse_file(test_file)

        assert result is not None
        assert result.title == "日本語タイトル"
        assert result.author == "José García"

    def test_parse_file_with_windows_1252_encoding(self, parser, tmp_path):
        """Test parse_file raises ParseError for Windows-1252 encoded file."""
        # Create a file with Windows-1252 encoded content
        test_file = tmp_path / "windows1252.fountain"
        # Windows-1252 specific characters (smart quotes, em dash)
        content = 'Title: "Smart Quotes"\n\nINT. OFFICE — DAY\n\nHe said, "Hello!"'
        test_file.write_bytes(content.encode("windows-1252"))

        with pytest.raises(ParseError) as excinfo:
            parser.parse_file(test_file)

        assert "File is not UTF-8 encoded" in str(excinfo.value)
        assert "windows1252.fountain" in str(excinfo.value)
        # Hint should be helpful
        assert "convert" in excinfo.value.hint.lower()
