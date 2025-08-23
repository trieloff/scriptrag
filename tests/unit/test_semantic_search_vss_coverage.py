"""Additional tests for SemanticSearchVSS to improve coverage."""

from unittest.mock import MagicMock, Mock

import pytest

from scriptrag.api.semantic_search_vss import SemanticSearchVSS
from scriptrag.config import ScriptRAGSettings


@pytest.fixture
def settings():
    """Create test settings."""
    return ScriptRAGSettings()


@pytest.fixture
def mock_vss_service():
    """Create mock VSS service."""
    service = MagicMock()
    service.get_embedding_stats = Mock(return_value={})
    service.migrate_from_blob_storage = Mock(return_value=(0, 0))
    return service


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service."""
    service = MagicMock()
    service.default_model = "test-model"
    return service


@pytest.fixture
def search_service(settings, mock_vss_service, mock_embedding_service):
    """Create semantic search VSS service with mocks."""
    # Pass mocks directly to constructor
    return SemanticSearchVSS(
        settings, vss_service=mock_vss_service, embedding_service=mock_embedding_service
    )


class TestSemanticSearchVSSExtended:
    """Extended tests for SemanticSearchVSS coverage."""

    # NOTE: Most SemanticSearchVSS methods are already well tested in other test files
    # These tests focus on specific edge cases for coverage

    def test_get_embedding_stats(self, search_service, mock_vss_service):
        """Test getting embedding statistics."""
        # Mock stats
        mock_stats = {
            "scene_embeddings": {"test-model": 10},
            "bible_embeddings": {"test-model": 5},
        }
        mock_vss_service.get_embedding_stats.return_value = mock_stats

        # Get stats
        stats = search_service.get_embedding_stats()

        assert stats == mock_stats
        mock_vss_service.get_embedding_stats.assert_called_once()


# Migration tests removed - migration function no longer exists
# @pytest.mark.asyncio
# async def test_migrate_to_vss_success(self, search_service, mock_vss_service):
#     pass
#
# @pytest.mark.asyncio
# async def test_migrate_to_vss_with_error(self, search_service, mock_vss_service):
#     pass

# NOTE: The main search and find methods require complex setup with real database
# connections and proper data structures. They are tested in integration tests.
# These unit tests focus on simpler method coverage.
