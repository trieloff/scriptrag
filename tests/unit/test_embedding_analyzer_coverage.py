"""Additional tests for SceneEmbeddingAnalyzer to improve coverage."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import git
import numpy as np
import pytest

from scriptrag.analyzers.embedding import SceneEmbeddingAnalyzer
from scriptrag.exceptions import EmbeddingGenerationError
from scriptrag.llm.models import EmbeddingResponse, LLMProvider


class TestSceneEmbeddingAnalyzerCoverage:
    """Tests for SceneEmbeddingAnalyzer to improve coverage."""

    def test_initialization_no_config(self):
        """Test analyzer initialization with no config."""
        analyzer = SceneEmbeddingAnalyzer()
        assert analyzer.name == "scene_embeddings"
        assert analyzer.version == "1.0.0"
        assert analyzer.requires_llm is True
        assert analyzer.embedding_model is None
        assert analyzer.dimensions is None
        assert analyzer.lfs_path == Path("embeddings")
        assert analyzer.repo_path == Path()
        assert analyzer._repo is None
        assert analyzer._embeddings_cache == {}

    def test_initialization_partial_config(self):
        """Test analyzer initialization with partial config."""
        config = {"embedding_model": "test-model"}
        analyzer = SceneEmbeddingAnalyzer(config)
        assert analyzer.embedding_model == "test-model"
        assert analyzer.dimensions is None
        assert analyzer.lfs_path == Path("embeddings")
        assert analyzer.repo_path == Path()

    def test_repo_property_git_error(self):
        """Test repo property when git repository is invalid."""
        analyzer = SceneEmbeddingAnalyzer()

        with patch("scriptrag.analyzers.embedding.git.Repo") as mock_repo_class:
            mock_repo_class.side_effect = git.InvalidGitRepositoryError(
                "Not a git repo"
            )

            from scriptrag.exceptions import GitError

            with pytest.raises(GitError, match="Error: Not a git repository"):
                _ = analyzer.repo

    def test_repo_property_caches_repo(self, tmp_path):
        """Test that repo property caches the repository instance."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        with patch("scriptrag.analyzers.embedding.git.Repo") as mock_repo_class:
            mock_repo_instance = Mock(spec=object)
            mock_repo_class.return_value = mock_repo_instance

            # First access creates repo
            repo1 = analyzer.repo
            assert repo1 is mock_repo_instance

            # Second access returns cached repo
            repo2 = analyzer.repo
            assert repo2 is mock_repo_instance

            # Should only create once
            mock_repo_class.assert_called_once()

    def test_compute_scene_hash_with_original_text(self):
        """Test scene hash computation with original_text."""
        analyzer = SceneEmbeddingAnalyzer()

        scene = {
            "original_text": "INT. COFFEE SHOP - DAY\n\nSARAH enters.",
            "heading": "Different heading",  # Should be ignored
        }

        hash_result = analyzer._compute_scene_hash(scene)

        # Should use original_text, not heading
        assert len(hash_result) == 64  # Full hash (not truncated)
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_compute_scene_hash_fallback_to_formatted(self):
        """Test scene hash computation without original_text."""
        analyzer = SceneEmbeddingAnalyzer()

        scene = {
            "heading": "INT. COFFEE SHOP - DAY",
            "dialogue": [{"character": "SARAH", "text": "Hello"}],
        }

        with patch(
            "scriptrag.utils.screenplay.ScreenplayUtils.format_scene_for_embedding"
        ) as mock_format:
            mock_format.return_value = "Formatted scene content"

            hash_result = analyzer._compute_scene_hash(scene)

            mock_format.assert_called_once_with(scene)
            assert len(hash_result) == 64

    @pytest.mark.asyncio
    async def test_initialize_existing_gitattributes_no_lfs_config(self, tmp_path):
        """Test initialization when .gitattributes exists but lacks LFS config."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        # Create existing .gitattributes without LFS config
        gitattributes_path = tmp_path / ".gitattributes"
        gitattributes_path.write_text("*.txt text\n")

        with patch(
            "scriptrag.analyzers.embedding.get_default_llm_client"
        ) as mock_client:
            mock_client.return_value = AsyncMock(
                spec=["complete", "cleanup", "embed", "list_models", "is_available"]
            )

            await analyzer.initialize()

            # Should append LFS configuration
            content = gitattributes_path.read_text()
            assert "*.txt text" in content
            assert "embeddings/*.npy filter=lfs diff=lfs merge=lfs -text" in content

    @pytest.mark.asyncio
    async def test_initialize_existing_gitattributes_with_lfs_config(self, tmp_path):
        """Test initialization when .gitattributes already has LFS config."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        # Create existing .gitattributes with LFS config
        gitattributes_path = tmp_path / ".gitattributes"
        existing_content = "embeddings/*.npy filter=lfs diff=lfs merge=lfs -text\n"
        gitattributes_path.write_text(existing_content)

        with patch(
            "scriptrag.analyzers.embedding.get_default_llm_client"
        ) as mock_client:
            mock_client.return_value = AsyncMock(
                spec=["complete", "cleanup", "embed", "list_models", "is_available"]
            )

            await analyzer.initialize()

            # Should not modify existing content
            content = gitattributes_path.read_text()
            assert content == existing_content

    @pytest.mark.asyncio
    async def test_load_or_generate_embedding_file_load_error(self, tmp_path):
        """Test loading embedding when file load fails."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)
        analyzer.llm_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )

        # Mock embedding response - use dict to make it subscriptable
        mock_embedding = {"embedding": [0.1, 0.2, 0.3]}
        response = Mock(spec=EmbeddingResponse)
        response.data = [mock_embedding]
        response.model = "test-embedding-model"
        response.provider = LLMProvider.OPENAI_COMPATIBLE
        analyzer.llm_client.embed.return_value = response

        # Create corrupted embedding file
        embeddings_dir = tmp_path / "embeddings"
        embeddings_dir.mkdir(exist_ok=True)

        content_hash = "test_hash"
        embedding_path = embeddings_dir / f"{content_hash}.npy"
        embedding_path.write_text("corrupted data")  # Not valid numpy file

        scene = {"content": "test scene"}

        with patch("scriptrag.analyzers.embedding.git.Repo"):
            # Should fall back to generating new embedding
            embedding = await analyzer._load_or_generate_embedding(scene, content_hash)

            assert isinstance(embedding, np.ndarray)
            np.testing.assert_array_almost_equal(embedding, [0.1, 0.2, 0.3])

    @pytest.mark.asyncio
    async def test_load_or_generate_embedding_save_error(self, tmp_path):
        """Test error handling when saving embedding fails."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)
        analyzer.llm_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )

        # Mock embedding response - use dict to make it subscriptable
        mock_embedding = {"embedding": [0.1, 0.2, 0.3]}
        response = Mock(spec=EmbeddingResponse)
        response.data = [mock_embedding]
        response.model = "test-embedding-model"
        response.provider = LLMProvider.OPENAI_COMPATIBLE
        analyzer.llm_client.embed.return_value = response

        content_hash = "test_hash"
        scene = {"content": "test scene"}

        with (
            patch("scriptrag.analyzers.embedding.git.Repo"),
            patch("numpy.save") as mock_save,
        ):
            mock_save.side_effect = OSError("Permission denied")

            # Should still return the embedding despite save error
            embedding = await analyzer._load_or_generate_embedding(scene, content_hash)

            assert isinstance(embedding, np.ndarray)
            np.testing.assert_array_almost_equal(embedding, [0.1, 0.2, 0.3])

    @pytest.mark.asyncio
    async def test_load_or_generate_embedding_git_add_error(self, tmp_path):
        """Test error handling when git add fails."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)
        analyzer.llm_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )

        # Mock embedding response - use dict to make it subscriptable
        mock_embedding = {"embedding": [0.1, 0.2, 0.3]}
        response = Mock(spec=EmbeddingResponse)
        response.data = [mock_embedding]
        response.model = "test-embedding-model"
        response.provider = LLMProvider.OPENAI_COMPATIBLE
        analyzer.llm_client.embed.return_value = response

        # Create embeddings directory
        embeddings_dir = tmp_path / "embeddings"
        embeddings_dir.mkdir(exist_ok=True)

        content_hash = "test_hash"
        scene = {"content": "test scene"}

        with patch("scriptrag.analyzers.embedding.git.Repo") as mock_repo_class:
            mock_repo = Mock(spec=object)
            # Git add error should be caught and logged as warning, not propagated
            # Use git.GitCommandError which is actually caught by the code
            mock_repo.index.add.side_effect = git.GitCommandError("add", "Git error")
            mock_repo_class.return_value = mock_repo

            # Should still return the embedding despite git error
            embedding = await analyzer._load_or_generate_embedding(scene, content_hash)

            assert isinstance(embedding, np.ndarray)
            np.testing.assert_array_almost_equal(embedding, [0.1, 0.2, 0.3])

    @pytest.mark.asyncio
    async def test_generate_embedding_no_llm_client(self):
        """Test generating embedding when LLM client is not initialized."""
        analyzer = SceneEmbeddingAnalyzer()
        scene = {"content": "test scene"}

        with pytest.raises(RuntimeError, match="LLM client not initialized"):
            await analyzer._generate_embedding(scene)

    @pytest.mark.asyncio
    async def test_generate_embedding_dict_response_format(self):
        """Test generating embedding with dict response format."""
        analyzer = SceneEmbeddingAnalyzer()
        analyzer.llm_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )

        # Mock response with dict format
        response = Mock(spec=EmbeddingResponse)
        response.data = [{"embedding": [0.5, 0.6, 0.7]}]
        response.model = "test-embedding-model"
        response.provider = LLMProvider.OPENAI_COMPATIBLE
        analyzer.llm_client.embed.return_value = response

        scene = {"content": "test scene"}

        embedding = await analyzer._generate_embedding(scene)

        assert isinstance(embedding, np.ndarray)
        assert embedding.dtype == np.float32
        np.testing.assert_array_almost_equal(embedding, [0.5, 0.6, 0.7])

    @pytest.mark.asyncio
    async def test_generate_embedding_no_data(self):
        """Test generating embedding when response has no data."""
        analyzer = SceneEmbeddingAnalyzer()
        analyzer.llm_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )

        # Mock response with empty data list - this will raise RuntimeError
        response = Mock(spec=EmbeddingResponse)
        response.data = []
        response.model = "test-embedding-model"
        response.provider = LLMProvider.OPENAI_COMPATIBLE
        analyzer.llm_client.embed.return_value = response

        scene = {"content": "test scene"}

        # Empty data should raise EmbeddingGenerationError (wrapping RuntimeError)
        with pytest.raises(
            EmbeddingGenerationError,
            match="Failed to generate embedding: No embedding data in response",
        ):
            await analyzer._generate_embedding(scene)

    @pytest.mark.asyncio
    async def test_generate_embedding_exception_fallback(self):
        """Test generating embedding exception propagation."""
        config = {"dimensions": 768}
        analyzer = SceneEmbeddingAnalyzer(config)
        analyzer.llm_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )

        # Mock LLM client to raise exception
        analyzer.llm_client.embed.side_effect = Exception("Network error")

        scene = {"content": "test scene"}

        # Exception should propagate up, no fallback behavior
        with pytest.raises(Exception, match="Network error"):
            await analyzer._generate_embedding(scene)

    @pytest.mark.asyncio
    async def test_generate_embedding_exception_fallback_default_dimensions(self):
        """Test generating embedding exception propagation with default config."""
        analyzer = SceneEmbeddingAnalyzer()  # No dimensions configured
        analyzer.llm_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )

        # Mock LLM client to raise exception
        analyzer.llm_client.embed.side_effect = Exception("Network error")

        scene = {"content": "test scene"}

        # Exception should propagate up, no fallback behavior
        with pytest.raises(Exception, match="Network error"):
            await analyzer._generate_embedding(scene)

    def test_format_scene_for_embedding_delegates_to_utils(self):
        """Test that _format_scene_for_embedding delegates to ScreenplayUtils."""
        analyzer = SceneEmbeddingAnalyzer()
        scene = {"content": "test scene"}

        with patch(
            "scriptrag.utils.screenplay.ScreenplayUtils.format_scene_for_embedding"
        ) as mock_format:
            mock_format.return_value = "formatted scene"

            result = analyzer._format_scene_for_embedding(scene)

            mock_format.assert_called_once_with(scene)
            assert result == "formatted scene"
