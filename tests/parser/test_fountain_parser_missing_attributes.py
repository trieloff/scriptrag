"""Test FountainParser handling of missing or malformed document attributes."""

from unittest.mock import Mock

import pytest

from scriptrag.parser.fountain_parser import FountainParser


class TestFountainParserMissingAttributes:
    """Test FountainParser handles documents with missing attributes."""

    def test_extract_metadata_no_title_values_attribute(self):
        """Test that extraction handles documents without title_values attribute."""
        parser = FountainParser()

        # Create a mock document without title_values attribute
        mock_doc = Mock(spec=[])  # Empty spec means no attributes

        # Should not raise AttributeError
        title, author, metadata = parser._extract_doc_metadata(mock_doc)

        # Should return default values
        assert title is None
        assert author is None
        assert metadata == {}

    def test_extract_metadata_title_values_is_none(self):
        """Test that extraction handles when title_values is None."""
        parser = FountainParser()

        # Create a mock document with title_values set to None
        mock_doc = Mock()
        mock_doc.title_values = None

        # Should handle gracefully
        title, author, metadata = parser._extract_doc_metadata(mock_doc)

        assert title is None
        assert author is None
        assert metadata == {}

    def test_extract_metadata_title_values_empty_dict(self):
        """Test that extraction handles empty title_values dict."""
        parser = FountainParser()

        # Create a mock document with empty title_values
        mock_doc = Mock()
        mock_doc.title_values = {}

        # Should handle gracefully
        title, author, metadata = parser._extract_doc_metadata(mock_doc)

        assert title is None
        assert author is None
        assert metadata == {}

    def test_extract_metadata_partial_title_values(self):
        """Test extraction with partial title_values data."""
        parser = FountainParser()

        # Create a mock document with some title_values
        mock_doc = Mock()
        mock_doc.title_values = {
            "title": "Test Script",
            "episode": "5",
            "season": "2",
        }

        title, author, metadata = parser._extract_doc_metadata(mock_doc)

        assert title == "Test Script"
        assert author is None  # No author field present
        assert metadata["episode"] == 5
        assert metadata["season"] == 2
        assert "series_title" not in metadata

    def test_extract_metadata_with_author_variations(self):
        """Test extraction with various author field names."""
        parser = FountainParser()

        # Test different author field variations
        author_fields = ["author", "authors", "writer", "writers", "written by"]

        for field_name in author_fields:
            mock_doc = Mock()
            mock_doc.title_values = {
                "title": "Test Script",
                field_name: f"Author via {field_name}",
            }

            title, author, metadata = parser._extract_doc_metadata(mock_doc)

            assert title == "Test Script"
            assert author == f"Author via {field_name}"
            assert metadata == {}

    def test_extract_metadata_series_title_variations(self):
        """Test extraction with various series title field names."""
        parser = FountainParser()

        # Test different series title field variations
        series_fields = [
            ("series", "Test Series"),
            ("series_title", "Test Series Title"),
            ("show", "Test Show"),
        ]

        for field_name, expected_value in series_fields:
            mock_doc = Mock()
            mock_doc.title_values = {
                "title": "Episode Title",
                field_name: expected_value,
            }

            title, _, metadata = parser._extract_doc_metadata(mock_doc)

            assert title == "Episode Title"
            assert metadata["series_title"] == expected_value

    def test_extract_metadata_project_title_variations(self):
        """Test extraction with various project title field names."""
        parser = FountainParser()

        # Test different project title field variations
        project_fields = [
            ("project", "Test Project"),
            ("project_title", "Test Project Title"),
        ]

        for field_name, expected_value in project_fields:
            mock_doc = Mock()
            mock_doc.title_values = {
                "title": "Script Title",
                field_name: expected_value,
            }

            title, _, metadata = parser._extract_doc_metadata(mock_doc)

            assert title == "Script Title"
            assert metadata["project_title"] == expected_value

    def test_process_scenes_no_scenes_attribute(self):
        """Test that process_scenes handles documents without scenes attribute."""
        parser = FountainParser()

        # Create a mock document without scenes attribute
        mock_doc = Mock(spec=[])  # Empty spec means no attributes

        # Should not raise AttributeError
        scenes = parser._process_scenes(mock_doc, "test content")

        # Should return empty list
        assert scenes == []

    def test_process_scenes_scenes_is_none(self):
        """Test that process_scenes handles when scenes is None."""
        parser = FountainParser()

        # Create a mock document with scenes set to None
        mock_doc = Mock()
        mock_doc.scenes = None

        # Should handle gracefully (though this would be unusual)
        with pytest.raises(TypeError):
            # This will raise because None is not iterable
            # but the fix ensures we don't get AttributeError
            parser._process_scenes(mock_doc, "test content")

    def test_process_scenes_empty_list(self):
        """Test that process_scenes handles empty scenes list."""
        parser = FountainParser()

        # Create a mock document with empty scenes
        mock_doc = Mock()
        mock_doc.scenes = []

        scenes = parser._process_scenes(mock_doc, "test content")

        assert scenes == []

    def test_process_scenes_scene_without_header(self):
        """Test that process_scenes skips scenes without headers."""
        parser = FountainParser()

        # Create mock scenes - some with headers, some without
        scene1 = Mock()
        scene1.header = None  # No header

        scene2 = Mock(spec=[])  # No header attribute at all

        scene3 = Mock()
        scene3.header = Mock()  # Has header
        scene3.header.content = "INT. LOCATION - DAY"

        # Mock the processor to return a scene object
        parser.processor = Mock()
        parser.processor.process_jouvence_scene = Mock(return_value=Mock())

        mock_doc = Mock()
        mock_doc.scenes = [scene1, scene2, scene3]

        scenes = parser._process_scenes(mock_doc, "test content")

        # Should only process scene3 which has a header
        assert len(scenes) == 1
        parser.processor.process_jouvence_scene.assert_called_once()

    def test_process_scenes_with_valid_scenes(self):
        """Test that process_scenes correctly processes valid scenes."""
        parser = FountainParser()

        # Create mock scenes with headers
        scene1 = Mock()
        scene1.header = Mock()
        scene1.header.content = "INT. HOUSE - DAY"

        scene2 = Mock()
        scene2.header = Mock()
        scene2.header.content = "EXT. STREET - NIGHT"

        # Mock the processor to return scene objects
        parser.processor = Mock()
        mock_scene_obj1 = Mock()
        mock_scene_obj2 = Mock()
        parser.processor.process_jouvence_scene.side_effect = [
            mock_scene_obj1,
            mock_scene_obj2,
        ]

        mock_doc = Mock()
        mock_doc.scenes = [scene1, scene2]

        scenes = parser._process_scenes(mock_doc, "test content")

        # Should process both scenes
        assert len(scenes) == 2
        assert scenes[0] == mock_scene_obj1
        assert scenes[1] == mock_scene_obj2
        assert parser.processor.process_jouvence_scene.call_count == 2

    def test_extract_metadata_episode_integer_conversion(self):
        """Test that episode numbers are converted to integers when possible."""
        parser = FountainParser()

        # Test valid integer string
        mock_doc = Mock()
        mock_doc.title_values = {"episode": "42"}

        _, _, metadata = parser._extract_doc_metadata(mock_doc)
        assert metadata["episode"] == 42
        assert isinstance(metadata["episode"], int)

        # Test non-numeric string (should stay as string)
        mock_doc.title_values = {"episode": "Pilot"}

        _, _, metadata = parser._extract_doc_metadata(mock_doc)
        assert metadata["episode"] == "Pilot"
        assert isinstance(metadata["episode"], str)

    def test_extract_metadata_season_integer_conversion(self):
        """Test that season numbers are converted to integers when possible."""
        parser = FountainParser()

        # Test valid integer string
        mock_doc = Mock()
        mock_doc.title_values = {"season": "3"}

        _, _, metadata = parser._extract_doc_metadata(mock_doc)
        assert metadata["season"] == 3
        assert isinstance(metadata["season"], int)

        # Test non-numeric string (should stay as string)
        mock_doc.title_values = {"season": "Special"}

        _, _, metadata = parser._extract_doc_metadata(mock_doc)
        assert metadata["season"] == "Special"
        assert isinstance(metadata["season"], str)

    def test_full_parse_with_missing_attributes(self):
        """Integration test: parse method with document missing attributes."""
        parser = FountainParser()

        # Mock the JouvenceParser to return a document without expected attributes
        from unittest.mock import patch

        with patch(
            "scriptrag.parser.fountain_parser.JouvenceParser"
        ) as mock_jouvence_parser:
            mock_parser_instance = Mock()
            mock_jouvence_parser.return_value = mock_parser_instance

            # Create a mock document without standard attributes
            mock_doc = Mock(spec=[])  # No attributes
            mock_parser_instance.parseString.return_value = mock_doc

            # This should not raise AttributeError
            result = parser.parse("Title: Test\n\nINT. LOCATION - DAY\n\nAction.")

            # Should return a valid Script object with defaults
            assert result.title is None
            assert result.author is None
            assert result.scenes == []
            assert result.metadata == {}

    def test_parse_file_with_missing_attributes(self):
        """Integration test: parse_file method with document missing attributes."""
        parser = FountainParser()

        from pathlib import Path
        from unittest.mock import patch

        # Mock file content
        file_content = "Title: Test Script\n\nINT. HOUSE - DAY\n\nSome action."

        with patch("pathlib.Path.read_text", return_value=file_content):
            with patch(
                "scriptrag.parser.fountain_parser.JouvenceParser"
            ) as mock_jouvence_parser:
                mock_parser_instance = Mock()
                mock_jouvence_parser.return_value = mock_parser_instance

                # Create a mock document with partial attributes
                mock_doc = Mock()
                mock_doc.title_values = {"title": "Test Script"}
                mock_doc.scenes = []  # Empty scenes list
                mock_parser_instance.parseString.return_value = mock_doc

                # Parse the file
                test_path = Path("/tmp/test.fountain")
                result = parser.parse_file(test_path)

                # Should handle gracefully
                assert result.title == "Test Script"
                assert result.author is None
                assert result.scenes == []
                assert result.metadata["source_file"] == str(test_path)
