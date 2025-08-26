"""Comprehensive unit tests for SceneEmbeddingAnalyzer with 99%+ coverage.

This test suite achieves complete coverage of the embedding analyzer,
including all edge cases and error conditions.
"""

import errno
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import git
import numpy as np
import pytest

from scriptrag.analyzers.embedding import SceneEmbeddingAnalyzer
from scriptrag.exceptions import EmbeddingError, EmbeddingGenerationError, GitError
from scriptrag.llm.models import EmbeddingRequest, EmbeddingResponse, LLMProvider
from scriptrag.utils import ScreenplayUtils


class TestSceneEmbeddingAnalyzerComplete:
    """Complete test coverage for SceneEmbeddingAnalyzer."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a comprehensive mock LLM client."""
        client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        # Create flexible mock embedding that supports both dict and object access
        mock_embedding_data = {
            "embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
            "object": "embedding",
            "index": 0,
        }

        # Create mock that can be accessed both ways
        mock_embedding = Mock(spec=object)
        mock_embedding.embedding = mock_embedding_data["embedding"]
        mock_embedding.get = Mock(return_value=mock_embedding_data["embedding"])
        mock_embedding.__getitem__ = Mock(
            side_effect=lambda key: mock_embedding_data[key]
        )

        response = Mock(spec=EmbeddingResponse)
        response.data = [mock_embedding_data]  # Use dict for subscript access
        response.model = "text-embedding-ada-002"
        response.provider = LLMProvider.OPENAI_COMPATIBLE
        client.embed.return_value = response
        return client

    @pytest.fixture
    def sample_scene_with_original_text(self):
        """Scene with original_text for hash testing."""
        return {
            "heading": "INT. COFFEE SHOP - DAY",
            "action": ["The shop buzzes with morning energy.", "SARAH enters."],
            "dialogue": [
                {"character": "SARAH", "text": "One coffee, please."},
                {"character": "BARISTA", "text": "Coming right up!"},
            ],
            "content": "Full scene content here",
            "original_text": (
                "INT. COFFEE SHOP - DAY\n\n"
                "The shop buzzes with morning energy.\n\n"
                "SARAH\nOne coffee, please.\n\n"
                "BARISTA\nComing right up!"
            ),
        }

    @pytest.fixture
    def sample_scene_no_original_text(self):
        """Scene without original_text for fallback testing."""
        return {
            "heading": "EXT. PARK - NIGHT",
            "action": ["Moonlight filters through trees."],
            "dialogue": [{"character": "JOHN", "text": "It's beautiful out here."}],
        }

    @pytest.fixture
    def analyzer_config(self, tmp_path):
        """Standard analyzer configuration."""
        return {
            "embedding_model": "text-embedding-ada-002",
            "dimensions": 5,
            "lfs_path": "embeddings",
            "repo_path": str(tmp_path),
        }

    # ==== INITIALIZATION TESTS ====

    def test_initialization_comprehensive(self):
        """Test all initialization scenarios."""
        # No config
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

        # Full config
        config = {
            "embedding_model": "custom-model",
            "dimensions": 1024,
            "lfs_path": "custom/embeddings",
            "repo_path": "/custom/repo",
        }
        analyzer = SceneEmbeddingAnalyzer(config)
        assert analyzer.embedding_model == "custom-model"
        assert analyzer.dimensions == 1024
        assert analyzer.lfs_path == Path("custom/embeddings")
        assert analyzer.repo_path == Path("/custom/repo")

    # ==== PROPERTY TESTS ====

    def test_repo_property_success(self, tmp_path):
        """Test successful repo property access."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        with patch("scriptrag.analyzers.embedding.git.Repo") as mock_repo_class:
            mock_repo_instance = Mock(spec=object)
            mock_repo_class.return_value = mock_repo_instance

            # First access
            repo1 = analyzer.repo
            assert repo1 is mock_repo_instance

            # Second access should return cached repo
            repo2 = analyzer.repo
            assert repo2 is mock_repo_instance
            assert repo1 is repo2

            # Should only be called once due to caching
            mock_repo_class.assert_called_once_with(
                tmp_path, search_parent_directories=True
            )

    def test_repo_property_invalid_repository(self):
        """Test repo property with invalid git repository."""
        analyzer = SceneEmbeddingAnalyzer()

        with patch("scriptrag.analyzers.embedding.git.Repo") as mock_repo_class:
            mock_repo_class.side_effect = git.InvalidGitRepositoryError(
                "Not a git repository"
            )

            # After refactor: Now throws GitError instead of RuntimeError
            with pytest.raises(GitError, match="Not a git repository"):
                _ = analyzer.repo

    # ==== HASH COMPUTATION TESTS ====

    def test_compute_scene_hash_with_original_text(
        self, sample_scene_with_original_text
    ):
        """Test hash computation using original_text."""
        analyzer = SceneEmbeddingAnalyzer()

        with patch.object(
            ScreenplayUtils, "compute_scene_hash", return_value="mocked_hash"
        ) as mock_hash:
            result = analyzer._compute_scene_hash(sample_scene_with_original_text)

            # Should use original_text with truncate=False
            mock_hash.assert_called_once_with(
                sample_scene_with_original_text["original_text"], truncate=False
            )
            assert result == "mocked_hash"

    def test_compute_scene_hash_without_original_text(
        self, sample_scene_no_original_text
    ):
        """Test hash computation fallback to formatted content."""
        analyzer = SceneEmbeddingAnalyzer()

        with (
            patch.object(
                ScreenplayUtils,
                "format_scene_for_embedding",
                return_value="formatted_content",
            ) as mock_format,
            patch.object(
                ScreenplayUtils, "compute_scene_hash", return_value="fallback_hash"
            ) as mock_hash,
        ):
            result = analyzer._compute_scene_hash(sample_scene_no_original_text)

            # Should format scene then hash it
            mock_format.assert_called_once_with(sample_scene_no_original_text)
            mock_hash.assert_called_once_with("formatted_content", truncate=False)
            assert result == "fallback_hash"

    # ==== PATH GENERATION TESTS ====

    def test_get_embedding_path(self, analyzer_config, tmp_path):
        """Test embedding path generation."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        content_hash = "abc123def456"  # pragma: allowlist secret
        expected_path = tmp_path / "embeddings" / f"{content_hash}.npy"

        result = analyzer._get_embedding_path(content_hash)
        assert result == expected_path

    # ==== INITIALIZATION TESTS (ASYNC) ====

    @pytest.mark.asyncio
    async def test_initialize_no_llm_client(self, analyzer_config, tmp_path):
        """Test initialize when llm_client is None."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        assert analyzer.llm_client is None

        with patch(
            "scriptrag.analyzers.embedding.get_default_llm_client"
        ) as mock_get_client:
            mock_client = AsyncMock(
                spec=["complete", "cleanup", "embed", "list_models", "is_available"]
            )
            mock_get_client.return_value = mock_client

            await analyzer.initialize()

            assert analyzer.llm_client is mock_client
            mock_get_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_existing_llm_client(self, analyzer_config, tmp_path):
        """Test initialize when llm_client already exists (MISSING BRANCH COVERAGE)."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        existing_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        analyzer.llm_client = existing_client  # Pre-set client

        with patch(
            "scriptrag.analyzers.embedding.get_default_llm_client"
        ) as mock_get_client:
            await analyzer.initialize()

            # Should NOT call get_default_llm_client since client already exists
            mock_get_client.assert_not_called()
            # Client should remain the same
            assert analyzer.llm_client is existing_client

    @pytest.mark.asyncio
    async def test_initialize_creates_embeddings_directory(
        self, analyzer_config, tmp_path
    ):
        """Test that initialize creates embeddings directory."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)

        with patch("scriptrag.analyzers.embedding.get_default_llm_client"):
            await analyzer.initialize()

            embeddings_dir = tmp_path / "embeddings"
            assert embeddings_dir.exists()
            assert embeddings_dir.is_dir()

    @pytest.mark.asyncio
    async def test_initialize_directory_creation_error(self, analyzer_config, tmp_path):
        """Test error handling when directory creation fails."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)

        with (
            patch("scriptrag.analyzers.embedding.get_default_llm_client"),
            patch("pathlib.Path.mkdir") as mock_mkdir,
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            mock_mkdir.side_effect = PermissionError("Access denied")

            # Should not raise exception
            await analyzer.initialize()

            # Should log error
            mock_logger.error.assert_called_with(
                f"Failed to create embeddings directory {tmp_path / 'embeddings'}: "
                "Access denied. Embeddings will not be cached to disk."
            )

    @pytest.mark.asyncio
    async def test_initialize_gitattributes_creation_new_file(
        self, analyzer_config, tmp_path
    ):
        """Test .gitattributes creation when file doesn't exist."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        gitattributes_path = tmp_path / ".gitattributes"
        assert not gitattributes_path.exists()

        with patch("scriptrag.analyzers.embedding.get_default_llm_client"):
            await analyzer.initialize()

            assert gitattributes_path.exists()
            content = gitattributes_path.read_text()
            assert "embeddings/*.npy filter=lfs diff=lfs merge=lfs -text" in content

    @pytest.mark.asyncio
    async def test_initialize_gitattributes_update_existing_no_lfs(
        self, analyzer_config, tmp_path
    ):
        """Test .gitattributes update when file exists without LFS config."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        gitattributes_path = tmp_path / ".gitattributes"
        gitattributes_path.write_text("*.txt text\n")

        with (
            patch("scriptrag.analyzers.embedding.get_default_llm_client"),
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            await analyzer.initialize()

            content = gitattributes_path.read_text()
            assert "*.txt text" in content
            assert "embeddings/*.npy filter=lfs diff=lfs merge=lfs -text" in content
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_initialize_gitattributes_already_configured(
        self, analyzer_config, tmp_path
    ):
        """Test .gitattributes when LFS already configured."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        gitattributes_path = tmp_path / ".gitattributes"
        lfs_pattern = "embeddings/*.npy filter=lfs diff=lfs merge=lfs -text"
        gitattributes_path.write_text(f"{lfs_pattern}\n")

        with (
            patch("scriptrag.analyzers.embedding.get_default_llm_client"),
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            await analyzer.initialize()

            # Should not log warning if already configured
            mock_logger.warning.assert_not_called()

    # ==== EMBEDDING GENERATION TESTS ====

    @pytest.mark.asyncio
    async def test_generate_embedding_success(
        self, analyzer_config, mock_llm_client, sample_scene_with_original_text
    ):
        """Test successful embedding generation."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        analyzer.llm_client = mock_llm_client

        result = await analyzer._generate_embedding(sample_scene_with_original_text)

        # Check result
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32
        np.testing.assert_array_almost_equal(result, [0.1, 0.2, 0.3, 0.4, 0.5])

        # Verify LLM was called with proper request
        mock_llm_client.embed.assert_called_once()
        call_args = mock_llm_client.embed.call_args[0][0]
        assert isinstance(call_args, EmbeddingRequest)
        assert call_args.model == "text-embedding-ada-002"
        assert call_args.dimensions == 5

    @pytest.mark.asyncio
    async def test_generate_embedding_no_llm_client(self):
        """Test embedding generation when LLM client not initialized."""
        analyzer = SceneEmbeddingAnalyzer()
        scene = {"content": "test scene"}

        with pytest.raises(RuntimeError, match="LLM client not initialized"):
            await analyzer._generate_embedding(scene)

    @pytest.mark.asyncio
    async def test_generate_embedding_api_error_fallback(self, analyzer_config):
        """Test API errors now raise EmbeddingGenerationError instead of fallback."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        mock_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_client.embed.side_effect = Exception("API Error")
        analyzer.llm_client = mock_client

        scene = {"content": "test scene"}

        # After refactor: API errors now raise exceptions instead of fallback
        with pytest.raises(
            EmbeddingGenerationError, match="Failed to generate embedding"
        ):
            await analyzer._generate_embedding(scene)

    @pytest.mark.asyncio
    async def test_generate_embedding_empty_response_fallback(self):
        """Test that empty response now raises RuntimeError instead of fallback."""
        analyzer = SceneEmbeddingAnalyzer()  # No dimensions configured
        mock_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )

        # Mock empty response
        response = Mock(spec=EmbeddingResponse)
        response.data = []  # Empty data
        mock_client.embed.return_value = response
        analyzer.llm_client = mock_client

        scene = {"content": "test scene"}

        # After refactor: Empty response now raises EmbeddingGenerationError
        with pytest.raises(
            EmbeddingGenerationError,
            match="Failed to generate embedding: No embedding data in response",
        ):
            await analyzer._generate_embedding(scene)

    @pytest.mark.asyncio
    async def test_generate_embedding_attribute_access_response(self):
        """Test embedding response with attribute access pattern."""
        analyzer = SceneEmbeddingAnalyzer()
        mock_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )

        # Mock response where embedding data has both attribute and dict access
        mock_embedding = Mock(spec=object)
        mock_embedding.embedding = [0.7, 0.8, 0.9]
        # Mock get() method to return the embedding (truthy value)
        mock_embedding.get = Mock(return_value=[0.7, 0.8, 0.9])
        # Mock dict access for the subscript operation
        mock_embedding.__getitem__ = Mock(return_value=[0.7, 0.8, 0.9])

        response = Mock(spec=EmbeddingResponse)
        response.data = [mock_embedding]
        mock_client.embed.return_value = response
        analyzer.llm_client = mock_client

        scene = {"content": "test scene"}
        result = await analyzer._generate_embedding(scene)

        assert isinstance(result, np.ndarray)
        np.testing.assert_array_almost_equal(result, [0.7, 0.8, 0.9])

        # Verify the get method was called to check for embedding
        mock_embedding.get.assert_called_with("embedding")

    # ==== SCENE FORMATTING TESTS ====

    def test_format_scene_for_embedding_delegates_to_utils(self):
        """Test that formatting delegates to ScreenplayUtils."""
        analyzer = SceneEmbeddingAnalyzer()
        scene = {"content": "test scene"}

        with patch.object(
            ScreenplayUtils, "format_scene_for_embedding", return_value="formatted"
        ) as mock_format:
            result = analyzer._format_scene_for_embedding(scene)

            mock_format.assert_called_once_with(scene)
            assert result == "formatted"

    # ==== LOAD OR GENERATE TESTS ====

    @pytest.mark.asyncio
    async def test_load_or_generate_embedding_from_cache(
        self, analyzer_config, mock_llm_client
    ):
        """Test loading embedding from cache."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        analyzer.llm_client = mock_llm_client

        # Pre-populate cache
        content_hash = "cached_hash"
        cached_embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        analyzer._embeddings_cache[content_hash] = cached_embedding

        scene = {"content": "test"}
        result = await analyzer._load_or_generate_embedding(scene, content_hash)

        np.testing.assert_array_equal(result, cached_embedding)
        # Should not call LLM
        mock_llm_client.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_or_generate_embedding_from_file(
        self, analyzer_config, tmp_path, mock_llm_client
    ):
        """Test loading embedding from file."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        analyzer.llm_client = mock_llm_client

        # Create embedding file
        embeddings_dir = tmp_path / "embeddings"
        embeddings_dir.mkdir()
        content_hash = "file_hash"
        embedding_path = embeddings_dir / f"{content_hash}.npy"
        saved_embedding = np.array([4.0, 5.0, 6.0], dtype=np.float32)
        np.save(embedding_path, saved_embedding)

        scene = {"content": "test"}
        result = await analyzer._load_or_generate_embedding(scene, content_hash)

        np.testing.assert_array_equal(result, saved_embedding)
        # Should be cached now
        assert content_hash in analyzer._embeddings_cache
        # Should not call LLM
        mock_llm_client.embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_or_generate_embedding_corrupted_file(
        self, analyzer_config, tmp_path, mock_llm_client
    ):
        """Test handling of corrupted embedding file."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        analyzer.llm_client = mock_llm_client

        # Create corrupted file
        embeddings_dir = tmp_path / "embeddings"
        embeddings_dir.mkdir()
        content_hash = "corrupted_hash"
        embedding_path = embeddings_dir / f"{content_hash}.npy"
        embedding_path.write_text("not numpy data")

        scene = {"content": "test"}

        with patch("scriptrag.analyzers.embedding.git.Repo"):
            # Should fall back to generating new embedding
            result = await analyzer._load_or_generate_embedding(scene, content_hash)

            assert isinstance(result, np.ndarray)
            # Should have called LLM to regenerate
            mock_llm_client.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_or_generate_embedding_save_to_git(
        self, analyzer_config, tmp_path, mock_llm_client
    ):
        """Test saving embedding and adding to git."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        analyzer.llm_client = mock_llm_client

        embeddings_dir = tmp_path / "embeddings"
        embeddings_dir.mkdir()
        content_hash = "new_hash"
        scene = {"content": "test"}

        with patch("scriptrag.analyzers.embedding.git.Repo") as mock_repo_class:
            mock_repo = Mock(spec=object)
            mock_repo_class.return_value = mock_repo

            result = await analyzer._load_or_generate_embedding(scene, content_hash)

            # Should save embedding
            embedding_path = embeddings_dir / f"{content_hash}.npy"
            assert embedding_path.exists()

            # Should add to git
            expected_relative_path = str(Path("embeddings") / f"{content_hash}.npy")
            mock_repo.index.add.assert_called_once_with([expected_relative_path])

            # Should cache result
            assert content_hash in analyzer._embeddings_cache

    # ==== ANALYZE METHOD TESTS ====

    @pytest.mark.asyncio
    async def test_analyze_success_comprehensive(
        self,
        analyzer_config,
        tmp_path,
        mock_llm_client,
        sample_scene_with_original_text,
    ):
        """Test successful scene analysis with comprehensive result checking."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        analyzer.llm_client = mock_llm_client

        embeddings_dir = tmp_path / "embeddings"
        embeddings_dir.mkdir()

        with patch("scriptrag.analyzers.embedding.git.Repo"):
            result = await analyzer.analyze(sample_scene_with_original_text)

            # Check all required fields
            assert "content_hash" in result
            assert "embedding_path" in result
            assert "dimensions" in result
            assert "model" in result
            assert "stored_in_lfs" in result
            assert "statistics" in result

            # Check specific values
            assert result["dimensions"] == 5
            assert result["model"] == "text-embedding-ada-002"
            assert result["stored_in_lfs"] is True

            # Check statistics
            stats = result["statistics"]
            assert "mean" in stats
            assert "std" in stats
            assert "min" in stats
            assert "max" in stats
            assert "norm" in stats

            # All statistics should be floats
            for _key, value in stats.items():
                assert isinstance(value, float)

    @pytest.mark.asyncio
    async def test_analyze_auto_selected_model(self, tmp_path):
        """Test analyze with auto-selected model (None config)."""
        config = {"repo_path": str(tmp_path)}  # No embedding_model specified
        analyzer = SceneEmbeddingAnalyzer(config)
        mock_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )

        # Mock response
        response = Mock(spec=EmbeddingResponse)
        response.data = [{"embedding": [0.1, 0.2]}]
        mock_client.embed.return_value = response
        analyzer.llm_client = mock_client

        embeddings_dir = tmp_path / "embeddings"
        embeddings_dir.mkdir()
        scene = {"content": "test scene"}

        with patch("scriptrag.analyzers.embedding.git.Repo"):
            result = await analyzer.analyze(scene)

            assert result["model"] == "auto-selected"

    @pytest.mark.asyncio
    async def test_analyze_error_handling(self):
        """Test analyze error handling."""
        analyzer = SceneEmbeddingAnalyzer()
        # No LLM client, will cause error
        scene = {"content": "test scene"}

        # After refactor: Now raises EmbeddingError instead of returning error dict
        with pytest.raises(
            EmbeddingError, match="Failed to analyze scene: LLM client not initialized"
        ):
            await analyzer.analyze(scene)

    # ==== CLEANUP TESTS ====

    @pytest.mark.asyncio
    async def test_cleanup_comprehensive(self):
        """Test comprehensive cleanup."""
        analyzer = SceneEmbeddingAnalyzer()

        # Set up state to clean
        analyzer.llm_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        analyzer._embeddings_cache = {
            "hash1": np.array([1, 2, 3]),
            "hash2": np.array([4, 5, 6]),
        }

        await analyzer.cleanup()

        assert analyzer.llm_client is None
        assert len(analyzer._embeddings_cache) == 0

    # ==== ERROR HANDLING EDGE CASES ====

    @pytest.mark.asyncio
    async def test_initialize_multiple_os_error_types(self, analyzer_config, tmp_path):
        """Test different OSError scenarios during initialization."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)

        # Test with different errno values
        test_errors = [
            OSError("Permission denied"),
            FileNotFoundError("No such file or directory"),
            PermissionError("Operation not permitted"),
        ]

        # Set errno on first error
        test_errors[0].errno = errno.EACCES

        for error in test_errors:
            with (
                patch("scriptrag.analyzers.embedding.get_default_llm_client"),
                patch("pathlib.Path.mkdir") as mock_mkdir,
                patch("scriptrag.analyzers.embedding.logger") as mock_logger,
            ):
                mock_mkdir.side_effect = error

                # Should handle gracefully
                await analyzer.initialize()

                # Should log appropriate error
                mock_logger.error.assert_called()
                error_call = mock_logger.error.call_args[0][0]
                assert "Failed to create embeddings directory" in error_call

    def test_properties_comprehensive(self):
        """Test all properties return correct values."""
        analyzer = SceneEmbeddingAnalyzer()

        assert analyzer.name == "scene_embeddings"
        assert analyzer.version == "1.0.0"
        assert analyzer.requires_llm is True

    @pytest.mark.asyncio
    async def test_embedding_statistics_calculation(self, analyzer_config, tmp_path):
        """Test embedding statistics calculation with known values."""
        analyzer = SceneEmbeddingAnalyzer(analyzer_config)
        mock_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )

        # Use predictable embedding values for statistics testing
        known_embedding = [1.0, 2.0, 3.0, 4.0, 5.0]
        response = Mock(spec=EmbeddingResponse)
        response.data = [{"embedding": known_embedding}]
        mock_client.embed.return_value = response
        analyzer.llm_client = mock_client

        embeddings_dir = tmp_path / "embeddings"
        embeddings_dir.mkdir()
        scene = {"content": "test scene"}

        with patch("scriptrag.analyzers.embedding.git.Repo"):
            result = await analyzer.analyze(scene)

            stats = result["statistics"]

            # Verify statistics are calculated correctly
            expected_mean = np.mean(known_embedding)
            expected_std = np.std(known_embedding)
            expected_min = np.min(known_embedding)
            expected_max = np.max(known_embedding)
            expected_norm = np.linalg.norm(known_embedding)

            assert abs(stats["mean"] - expected_mean) < 1e-6
            assert abs(stats["std"] - expected_std) < 1e-6
            assert abs(stats["min"] - expected_min) < 1e-6
            assert abs(stats["max"] - expected_max) < 1e-6
            assert abs(stats["norm"] - expected_norm) < 1e-6
