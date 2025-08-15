"""Edge case tests for scene_models to improve coverage."""

import pytest

from scriptrag.api.scene_models import SceneIdentifier


class TestSceneIdentifierEdgeCases:
    """Test edge cases for SceneIdentifier."""

    def test_from_string_tv_format_missing_s_prefix(self):
        """Test TV format without S prefix."""
        with pytest.raises(ValueError, match="Invalid scene key format"):
            SceneIdentifier.from_string("show:01E05:023")

    def test_from_string_tv_format_missing_e_separator(self):
        """Test TV format without E separator."""
        with pytest.raises(ValueError, match="Invalid scene key format"):
            SceneIdentifier.from_string("show:S0105:023")

    def test_from_string_tv_format_invalid_prefix(self):
        """Test TV format with wrong prefix."""
        with pytest.raises(ValueError, match="Invalid scene key format"):
            SceneIdentifier.from_string("show:X01E05:023")

    def test_from_string_three_parts_but_not_tv_format(self):
        """Test three parts that don't match TV format."""
        with pytest.raises(ValueError, match="Invalid scene key format"):
            SceneIdentifier.from_string("show:invalid:023")

    def test_from_string_empty_string(self):
        """Test parsing empty string."""
        with pytest.raises(ValueError, match="Invalid scene key format"):
            SceneIdentifier.from_string("")

    def test_from_string_single_part(self):
        """Test parsing single part."""
        with pytest.raises(ValueError, match="Invalid scene key format"):
            SceneIdentifier.from_string("onlyproject")

    def test_from_string_four_parts(self):
        """Test parsing four parts."""
        with pytest.raises(ValueError, match="Invalid scene key format"):
            SceneIdentifier.from_string("too:many:parts:here")
