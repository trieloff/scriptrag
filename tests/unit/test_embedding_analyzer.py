"""Unit tests for the SceneEmbeddingAnalyzer."""

from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

from scriptrag.analyzers.embedding import SceneEmbeddingAnalyzer
from scriptrag.llm.models import EmbeddingResponse


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = AsyncMock()
    # Mock embedding response - needs to support both attribute and subscript access
    mock_embedding = Mock()
    mock_embedding.embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
    mock_embedding.get = Mock(return_value=[0.1, 0.2, 0.3, 0.4, 0.5])
    mock_embedding.__getitem__ = Mock(return_value=[0.1, 0.2, 0.3, 0.4, 0.5])

    response = Mock(spec=EmbeddingResponse)
    response.data = [mock_embedding]
    client.embed.return_value = response
    return client


@pytest.fixture
def mock_repo(tmp_path):
    """Create a mock git repository."""
    with patch("scriptrag.analyzers.embedding.git.Repo") as mock_repo_class:
        mock_repo_instance = Mock()
        mock_repo_instance.working_dir = str(tmp_path)
        mock_repo_instance.index = Mock()
        mock_repo_instance.index.add = Mock()
        mock_repo_class.return_value = mock_repo_instance
        yield mock_repo_instance


@pytest.fixture
def analyzer_config(tmp_path):
    """Create analyzer configuration."""
    return {
        "embedding_model": "text-embedding-ada-002",
        "dimensions": 5,
        "lfs_path": "embeddings",
        "repo_path": str(tmp_path),
    }


@pytest.fixture
def sample_scene():
    """Create a sample scene for testing."""
    return {
        "heading": "INT. COFFEE SHOP - DAY",
        "action": ["The shop buzzes with morning energy.", "SARAH enters."],
        "dialogue": [
            {"character": "SARAH", "text": "One coffee, please."},
            {"character": "BARISTA", "text": "Coming right up!"},
        ],
        "content": "Full scene content here",
    }


class TestSceneEmbeddingAnalyzer:
    """Test the SceneEmbeddingAnalyzer class."""

    def test_initialization(self, analyzer_config):
        """Test analyzer initialization."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        assert analyzer.name == "scene_embeddings"
        assert analyzer.version == "1.0.0"
        assert analyzer.requires_llm is True
        assert analyzer.embedding_model == "text-embedding-ada-002"
        assert analyzer.dimensions == 5

    def test_compute_scene_hash(self, analyzer_config, sample_scene):
        """Test scene hash computation."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        hash1 = analyzer._compute_scene_hash(sample_scene)

        # Hash should be consistent
        hash2 = analyzer._compute_scene_hash(sample_scene)
        assert hash1 == hash2

        # Hash should be hex string
        assert len(hash1) == 64  # SHA256 hex digest length
        assert all(c in "0123456789abcdef" for c in hash1)

        # Different content should give different hash
        modified_scene = sample_scene.copy()
        modified_scene["heading"] = "EXT. PARK - NIGHT"
        hash3 = analyzer._compute_scene_hash(modified_scene)
        assert hash1 != hash3

    def test_format_scene_for_embedding(self, analyzer_config, sample_scene):
        """Test scene formatting for embedding."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        formatted = analyzer._format_scene_for_embedding(sample_scene)

        assert "Scene: INT. COFFEE SHOP - DAY" in formatted
        assert "Action: The shop buzzes with morning energy. SARAH enters." in formatted
        assert "SARAH: One coffee, please." in formatted
        assert "BARISTA: Coming right up!" in formatted

    def test_get_embedding_path(self, analyzer_config, tmp_path):
        """Test embedding path generation."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        content_hash = "abc123"
        path = analyzer._get_embedding_path(content_hash)

        expected = tmp_path / "embeddings" / f"{content_hash}.npy"
        assert path == expected

    @pytest.mark.asyncio
    async def test_initialize(self, analyzer_config, tmp_path, mock_repo):
        """Test analyzer initialization."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)

        with patch(
            "scriptrag.analyzers.embedding.get_default_llm_client"
        ) as mock_get_client:
            mock_get_client.return_value = AsyncMock()
            await analyzer.initialize()

            # Check that embeddings directory was created
            embeddings_dir = tmp_path / "embeddings"
            assert embeddings_dir.exists()

            # Check that .gitattributes was created/updated
            gitattributes = tmp_path / ".gitattributes"
            assert gitattributes.exists()
            content = gitattributes.read_text()
            assert "embeddings/*.npy filter=lfs" in content

    @pytest.mark.asyncio
    async def test_generate_embedding(
        self, analyzer_config, mock_llm_client, sample_scene
    ):
        """Test embedding generation."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        analyzer.llm_client = mock_llm_client

        embedding = await analyzer._generate_embedding(sample_scene)

        assert isinstance(embedding, np.ndarray)
        assert embedding.dtype == np.float32
        assert len(embedding) == 5
        np.testing.assert_array_almost_equal(embedding, [0.1, 0.2, 0.3, 0.4, 0.5])

        # Verify LLM client was called correctly
        mock_llm_client.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_or_generate_embedding_cached(
        self, analyzer_config, mock_llm_client, sample_scene
    ):
        """Test loading embedding from cache."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        analyzer.llm_client = mock_llm_client

        # Pre-populate cache
        content_hash = analyzer._compute_scene_hash(sample_scene)
        cached_embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        analyzer._embeddings_cache[content_hash] = cached_embedding

        # Should return cached version
        embedding = await analyzer._load_or_generate_embedding(
            sample_scene, content_hash
        )

        np.testing.assert_array_equal(embedding, cached_embedding)
        # LLM should not be called
        mock_llm_client.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_or_generate_embedding_from_file(
        self,
        analyzer_config,
        tmp_path,
        mock_llm_client,
        sample_scene,
        mock_repo,
    ):
        """Test loading embedding from file."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        analyzer.llm_client = mock_llm_client

        # Create embedding file
        content_hash = analyzer._compute_scene_hash(sample_scene)
        embeddings_dir = tmp_path / "embeddings"
        embeddings_dir.mkdir(exist_ok=True)

        saved_embedding = np.array([4.0, 5.0, 6.0], dtype=np.float32)
        embedding_path = embeddings_dir / f"{content_hash}.npy"
        np.save(embedding_path, saved_embedding)

        # Should load from file
        embedding = await analyzer._load_or_generate_embedding(
            sample_scene, content_hash
        )

        np.testing.assert_array_equal(embedding, saved_embedding)
        # LLM should not be called
        mock_llm_client.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_or_generate_embedding_new(
        self, analyzer_config, tmp_path, mock_llm_client, sample_scene, mock_repo
    ):
        """Test generating new embedding."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        analyzer.llm_client = mock_llm_client

        # Ensure embeddings directory exists
        embeddings_dir = tmp_path / "embeddings"
        embeddings_dir.mkdir(exist_ok=True)

        content_hash = analyzer._compute_scene_hash(sample_scene)

        # Should generate new embedding
        embedding = await analyzer._load_or_generate_embedding(
            sample_scene, content_hash
        )

        assert isinstance(embedding, np.ndarray)
        np.testing.assert_array_almost_equal(embedding, [0.1, 0.2, 0.3, 0.4, 0.5])

        # Check that embedding was saved
        embedding_path = embeddings_dir / f"{content_hash}.npy"
        assert embedding_path.exists()

        # Verify it was added to git
        mock_repo.index.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_success(
        self,
        analyzer_config,
        tmp_path,
        mock_llm_client,
        sample_scene,
        mock_repo,
    ):
        """Test successful scene analysis."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        analyzer.llm_client = mock_llm_client

        # Ensure embeddings directory exists
        embeddings_dir = tmp_path / "embeddings"
        embeddings_dir.mkdir(exist_ok=True)

        result = await analyzer.analyze(sample_scene)

        assert "content_hash" in result
        assert "embedding_path" in result
        assert result["dimensions"] == 5
        assert result["stored_in_lfs"] is True
        assert "statistics" in result

        # Check statistics
        stats = result["statistics"]
        assert "mean" in stats
        assert "std" in stats
        assert "norm" in stats

    @pytest.mark.asyncio
    async def test_analyze_error(self, analyzer_config, sample_scene):
        """Test analysis with error."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        # No LLM client initialized

        from scriptrag.exceptions import EmbeddingError

        with pytest.raises(EmbeddingError) as exc_info:
            await analyzer.analyze(sample_scene)

        # Check that the error message contains expected information
        assert "Error: Failed to analyze scene" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cleanup(self, analyzer_config):
        """Test analyzer cleanup."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        analyzer.llm_client = Mock()
        analyzer._embeddings_cache["test"] = np.array([1, 2, 3])

        await analyzer.cleanup()

        assert analyzer.llm_client is None
        assert len(analyzer._embeddings_cache) == 0
