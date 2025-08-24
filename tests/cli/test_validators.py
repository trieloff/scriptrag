"""Tests for CLI validators."""

import pytest

from scriptrag.api.scene_models import SceneIdentifier
from scriptrag.cli.validators.base import CompositeValidator, ValidationError
from scriptrag.cli.validators.file_validator import (
    ConfigFileValidator,
    DirectoryValidator,
    FileValidator,
)
from scriptrag.cli.validators.project_validator import (
    EpisodeIdentifierValidator,
    ProjectValidator,
)
from scriptrag.cli.validators.scene_validator import (
    SceneContentValidator,
    ScenePositionValidator,
    SceneValidator,
)


class TestProjectValidator:
    """Test project name validation."""

    def test_valid_project_name(self):
        """Test valid project names."""
        validator = ProjectValidator()

        assert validator.validate("my_project") == "my_project"
        assert validator.validate("project-123") == "project-123"
        assert validator.validate("MyScreenplay") == "MyScreenplay"

    def test_valid_project_with_spaces(self):
        """Test project names with spaces when allowed."""
        validator = ProjectValidator(allow_spaces=True)

        assert validator.validate("My Great Project") == "My Great Project"
        assert validator.validate("Project 2024") == "Project 2024"

    def test_invalid_project_name(self):
        """Test invalid project names."""
        validator = ProjectValidator()

        with pytest.raises(ValidationError, match="required"):
            validator.validate("")

        with pytest.raises(ValidationError, match="required"):
            validator.validate(None)

        with pytest.raises(ValidationError, match="only contain"):
            validator.validate("project@123")

        with pytest.raises(ValidationError, match="only contain"):
            validator.validate("my project")  # Space not allowed by default

    def test_project_name_length(self):
        """Test project name length validation."""
        validator = ProjectValidator()

        with pytest.raises(ValidationError, match="between 1 and 100"):
            validator.validate("x" * 101)


class TestSceneValidator:
    """Test scene identifier validation."""

    def test_valid_scene_identifier(self):
        """Test valid scene identifiers."""
        validator = SceneValidator()

        result = validator.validate({"project": "my_project", "scene_number": 42})
        assert isinstance(result, SceneIdentifier)
        assert result.project == "my_project"
        assert result.scene_number == 42

    def test_valid_tv_scene_identifier(self):
        """Test valid TV show scene identifier."""
        validator = SceneValidator()

        result = validator.validate(
            {
                "project": "breaking_bad",
                "scene_number": 10,
                "season": 1,
                "episode": 3,
            }
        )
        assert result.season == 1
        assert result.episode == 3

    def test_missing_project(self):
        """Test missing project validation."""
        validator = SceneValidator()

        with pytest.raises(ValidationError, match="project"):
            validator.validate({"scene_number": 42})

    def test_invalid_scene_number(self):
        """Test invalid scene number."""
        validator = SceneValidator()

        with pytest.raises(ValidationError, match="scene_number"):
            validator.validate({"project": "test", "scene_number": 0})

        with pytest.raises(ValidationError, match="scene_number"):
            validator.validate({"project": "test", "scene_number": -1})

    def test_episode_requires_season(self):
        """Test that episode requires season."""
        validator = SceneValidator()

        with pytest.raises(ValidationError, match="requires season"):
            validator.validate({"project": "test", "scene_number": 1, "episode": 3})


class TestSceneContentValidator:
    """Test scene content validation."""

    def test_valid_scene_content(self):
        """Test valid scene content."""
        validator = SceneContentValidator()

        content = "INT. OFFICE - DAY\n\nJohn enters the room."
        assert validator.validate(content) == content

        content2 = "EXT. STREET - NIGHT\n\nCars pass by."
        assert validator.validate(content2) == content2

    def test_valid_scene_headings(self):
        """Test various valid scene headings."""
        validator = SceneContentValidator()

        valid_headings = [
            "INT. OFFICE - DAY",
            "EXT. STREET - NIGHT",
            "INT/EXT. CAR - MOVING",
            "INT./EXT. HOUSE - CONTINUOUS",
            "I/E. WAREHOUSE - LATER",
        ]

        for heading in valid_headings:
            content = f"{heading}\n\nAction here."
            assert validator.validate(content) == content

    def test_empty_content(self):
        """Test empty content validation."""
        validator = SceneContentValidator()

        with pytest.raises(ValidationError, match="required"):
            validator.validate("")

        with pytest.raises(ValidationError, match="required"):
            validator.validate(None)

    def test_missing_scene_heading(self):
        """Test content without scene heading."""
        validator = SceneContentValidator()

        with pytest.raises(ValidationError, match="scene heading"):
            validator.validate("Just some text without heading")

        with pytest.raises(ValidationError, match="scene heading"):
            validator.validate("FADE IN:\n\nSome content")

    def test_no_heading_required(self):
        """Test validation without requiring heading."""
        validator = SceneContentValidator(require_heading=False)

        content = "Any content without heading"
        assert validator.validate(content) == content


class TestScenePositionValidator:
    """Test scene position validation."""

    def test_valid_after_position(self):
        """Test valid after position."""
        validator = ScenePositionValidator()

        scene, position = validator.validate({"after_scene": 10, "before_scene": None})
        assert scene == 10
        assert position == "after"

    def test_valid_before_position(self):
        """Test valid before position."""
        validator = ScenePositionValidator()

        scene, position = validator.validate({"after_scene": None, "before_scene": 20})
        assert scene == 20
        assert position == "before"

    def test_missing_position(self):
        """Test missing position."""
        validator = ScenePositionValidator()

        with pytest.raises(ValidationError, match="Must specify"):
            validator.validate({"after_scene": None, "before_scene": None})

    def test_both_positions(self):
        """Test specifying both positions."""
        validator = ScenePositionValidator()

        with pytest.raises(ValidationError, match="Cannot specify both"):
            validator.validate({"after_scene": 10, "before_scene": 20})

    def test_invalid_scene_number(self):
        """Test invalid scene numbers."""
        validator = ScenePositionValidator()

        with pytest.raises(ValidationError, match="after_scene"):
            validator.validate({"after_scene": 0, "before_scene": None})

        with pytest.raises(ValidationError, match="before_scene"):
            validator.validate({"after_scene": None, "before_scene": -1})


class TestFileValidator:
    """Test file path validation."""

    def test_valid_file_path(self, tmp_path):
        """Test valid file path."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        validator = FileValidator(must_exist=True)
        result = validator.validate(str(test_file))
        assert result == test_file

    def test_file_not_exists(self, tmp_path):
        """Test file that doesn't exist."""
        validator = FileValidator(must_exist=True)

        with pytest.raises(ValidationError, match="does not exist"):
            validator.validate(str(tmp_path / "nonexistent.txt"))

    def test_file_extension_validation(self, tmp_path):
        """Test file extension validation."""
        # Create test files
        valid_file = tmp_path / "script.fountain"
        valid_file.write_text("content")

        invalid_file = tmp_path / "document.pdf"
        invalid_file.write_text("content")

        validator = FileValidator(extensions=[".fountain", ".txt"])

        # Valid extension
        assert validator.validate(str(valid_file)) == valid_file

        # Invalid extension
        with pytest.raises(ValidationError, match="Invalid file extension"):
            validator.validate(str(invalid_file))

    def test_path_is_directory(self, tmp_path):
        """Test path that is a directory."""
        validator = FileValidator(must_be_file=True)

        with pytest.raises(ValidationError, match="not a file"):
            validator.validate(str(tmp_path))


class TestDirectoryValidator:
    """Test directory path validation."""

    def test_valid_directory(self, tmp_path):
        """Test valid directory path."""
        validator = DirectoryValidator(must_exist=True)
        result = validator.validate(str(tmp_path))
        assert result == tmp_path

    def test_create_missing_directory(self, tmp_path):
        """Test creating missing directory."""
        new_dir = tmp_path / "new_directory"
        validator = DirectoryValidator(create_if_missing=True)

        result = validator.validate(str(new_dir))
        assert result == new_dir
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_directory_not_exists(self, tmp_path):
        """Test directory that doesn't exist."""
        validator = DirectoryValidator(must_exist=True, create_if_missing=False)

        with pytest.raises(ValidationError, match="does not exist"):
            validator.validate(str(tmp_path / "nonexistent"))

    def test_path_is_file(self, tmp_path):
        """Test path that is a file."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")

        validator = DirectoryValidator()

        with pytest.raises(ValidationError, match="not a directory"):
            validator.validate(str(test_file))


class TestConfigFileValidator:
    """Test configuration file validation."""

    def test_valid_config_formats(self, tmp_path):
        """Test valid configuration file formats."""
        validator = ConfigFileValidator()

        # Test each valid format
        for ext in [".yaml", ".yml", ".json", ".toml"]:
            config_file = tmp_path / f"config{ext}"
            config_file.write_text("content")

            result = validator.validate(str(config_file))
            assert result == config_file

    def test_invalid_config_format(self, tmp_path):
        """Test invalid configuration file format."""
        validator = ConfigFileValidator()

        invalid_file = tmp_path / "config.txt"
        invalid_file.write_text("content")

        with pytest.raises(ValidationError, match="Invalid file extension"):
            validator.validate(str(invalid_file))


class TestCompositeValidator:
    """Test composite validator."""

    def test_composite_validation(self):
        """Test composite validator with multiple validators."""

        # Create mock validators
        class UppercaseValidator:
            def validate(self, value):
                return value.upper()

        class LengthValidator:
            def validate(self, value):
                if len(value) < 3:
                    raise ValidationError("Too short")
                return value

        composite = CompositeValidator(
            [
                UppercaseValidator(),
                LengthValidator(),
            ]
        )

        # Valid input
        result = composite.validate("hello")
        assert result == "HELLO"

        # Invalid input (too short after uppercase)
        with pytest.raises(ValidationError, match="Too short"):
            composite.validate("hi")


class TestEpisodeIdentifierValidator:
    """Test episode identifier validation."""

    def test_valid_episode_identifier(self):
        """Test valid episode identifier."""
        validator = EpisodeIdentifierValidator()

        result = validator.validate({"season": 1, "episode": 5})
        assert result["season"] == 1
        assert result["episode"] == 5

    def test_season_only(self):
        """Test season without episode."""
        validator = EpisodeIdentifierValidator()

        result = validator.validate({"season": 2, "episode": None})
        assert result["season"] == 2
        assert result["episode"] is None

    def test_episode_requires_season(self):
        """Test episode requires season."""
        validator = EpisodeIdentifierValidator()

        with pytest.raises(ValidationError, match="requires season"):
            validator.validate({"season": None, "episode": 3})

    def test_invalid_ranges(self):
        """Test invalid season/episode ranges."""
        validator = EpisodeIdentifierValidator()

        with pytest.raises(ValidationError, match="season"):
            validator.validate({"season": 0, "episode": None})

        with pytest.raises(ValidationError, match="season"):
            validator.validate({"season": 100, "episode": None})

        with pytest.raises(ValidationError, match="episode"):
            validator.validate({"season": 1, "episode": 1000})
