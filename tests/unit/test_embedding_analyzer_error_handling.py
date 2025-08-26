"""Test error handling for SceneEmbeddingAnalyzer file operations."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from scriptrag.analyzers.embedding import SceneEmbeddingAnalyzer


class TestSceneEmbeddingAnalyzerErrorHandling:
    """Test error handling for file operations in SceneEmbeddingAnalyzer."""

    @pytest.mark.asyncio
    async def test_initialize_gitattributes_read_permission_error(self, tmp_path):
        """Test handling of permission error when reading .gitattributes."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        # Create .gitattributes file
        gitattributes_path = tmp_path / ".gitattributes"
        gitattributes_path.write_text("*.txt text\n")

        with (
            patch(
                "scriptrag.analyzers.embedding.get_default_llm_client"
            ) as mock_client,
            patch("pathlib.Path.open") as mock_path_open,
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            mock_client.return_value = AsyncMock(spec=object)

            # First call for reading existing file raises PermissionError
            mock_path_open.side_effect = PermissionError("Permission denied")

            await analyzer.initialize()

            # Should log error about failed read
            mock_logger.error.assert_any_call(
                "Failed to read .gitattributes: Permission denied. "
                "Git LFS configuration check skipped."
            )

    @pytest.mark.asyncio
    async def test_initialize_gitattributes_read_io_error(self, tmp_path):
        """Test handling of IOError when reading .gitattributes."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        # Create .gitattributes file
        gitattributes_path = tmp_path / ".gitattributes"
        gitattributes_path.write_text("*.txt text\n")

        with (
            patch(
                "scriptrag.analyzers.embedding.get_default_llm_client"
            ) as mock_client,
            patch("pathlib.Path.open") as mock_path_open,
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            mock_client.return_value = AsyncMock(spec=object)

            # Reading raises IOError
            mock_path_open.side_effect = OSError("I/O error")

            await analyzer.initialize()

            # Should log error about failed read
            mock_logger.error.assert_any_call(
                "Failed to read .gitattributes: I/O error. "
                "Git LFS configuration check skipped."
            )

    @pytest.mark.asyncio
    async def test_initialize_gitattributes_update_permission_error(self, tmp_path):
        """Test handling of permission error when updating .gitattributes."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        # Create .gitattributes file without LFS config
        gitattributes_path = tmp_path / ".gitattributes"
        gitattributes_path.write_text("*.txt text\n")

        with (
            patch(
                "scriptrag.analyzers.embedding.get_default_llm_client"
            ) as mock_client,
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            mock_client.return_value = AsyncMock(spec=object)

            # Mock Path.open to succeed on read but fail on append
            original_open = Path.open
            call_count = [0]

            def mock_path_open(self, mode="r", *args, **kwargs):
                call_count[0] += 1
                # First call is read mode, should succeed
                if call_count[0] == 1:
                    return original_open(self, mode, *args, **kwargs)
                # Second call is append mode, should fail
                if "a" in mode:
                    raise PermissionError("Permission denied")
                return original_open(self, mode, *args, **kwargs)

            with patch.object(Path, "open", mock_path_open):
                await analyzer.initialize()

                # Should log error about failed update
                lfs_pattern = "embeddings/*.npy filter=lfs diff=lfs merge=lfs -text"
                mock_logger.error.assert_any_call(
                    "Failed to update .gitattributes: Permission denied. "
                    "Please manually add the following line to "
                    f".gitattributes:\n{lfs_pattern}"
                )

    @pytest.mark.asyncio
    async def test_initialize_gitattributes_update_io_error(self, tmp_path):
        """Test handling of IOError when updating .gitattributes."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        # Create .gitattributes file without LFS config
        gitattributes_path = tmp_path / ".gitattributes"
        gitattributes_path.write_text("*.txt text\n")

        with (
            patch(
                "scriptrag.analyzers.embedding.get_default_llm_client"
            ) as mock_client,
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            mock_client.return_value = AsyncMock(spec=object)

            # Mock Path.open to succeed on read but fail on append
            original_open = Path.open
            call_count = [0]

            def mock_path_open(self, mode="r", *args, **kwargs):
                call_count[0] += 1
                # First call is read mode, should succeed
                if call_count[0] == 1:
                    return original_open(self, mode, *args, **kwargs)
                # Second call is append mode, should fail
                if "a" in mode:
                    raise OSError("Disk full")
                return original_open(self, mode, *args, **kwargs)

            with patch.object(Path, "open", mock_path_open):
                await analyzer.initialize()

                # Should log error about failed update
                lfs_pattern = "embeddings/*.npy filter=lfs diff=lfs merge=lfs -text"
                mock_logger.error.assert_any_call(
                    "Failed to update .gitattributes: Disk full. "
                    "Please manually add the following line to "
                    f".gitattributes:\n{lfs_pattern}"
                )

    @pytest.mark.asyncio
    async def test_initialize_gitattributes_create_permission_error(self, tmp_path):
        """Test handling of permission error when creating .gitattributes."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        with (
            patch(
                "scriptrag.analyzers.embedding.get_default_llm_client"
            ) as mock_client,
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            mock_client.return_value = AsyncMock(spec=object)

            # Mock Path.open to fail on write mode
            def mock_path_open(self, mode="r", *args, **kwargs):
                if "w" in mode:
                    raise PermissionError("Permission denied")
                # For read mode, raise FileNotFoundError to simulate no existing file
                raise FileNotFoundError("No such file")

            with patch.object(Path, "open", mock_path_open):
                await analyzer.initialize()

                # Should log error about failed creation
                lfs_pattern = "embeddings/*.npy filter=lfs diff=lfs merge=lfs -text"
                mock_logger.error.assert_any_call(
                    "Failed to create .gitattributes: Permission denied. "
                    "Please manually create .gitattributes with the "
                    f"following line:\n{lfs_pattern}"
                )

    @pytest.mark.asyncio
    async def test_initialize_gitattributes_create_io_error(self, tmp_path):
        """Test handling of IOError when creating .gitattributes."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        with (
            patch(
                "scriptrag.analyzers.embedding.get_default_llm_client"
            ) as mock_client,
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            mock_client.return_value = AsyncMock(spec=object)

            # Mock Path.open to fail on write mode
            def mock_path_open(self, mode="r", *args, **kwargs):
                if "w" in mode:
                    raise OSError("No space left on device")
                # For read mode, raise FileNotFoundError to simulate no existing file
                raise FileNotFoundError("No such file")

            with patch.object(Path, "open", mock_path_open):
                await analyzer.initialize()

                # Should log error about failed creation
                lfs_pattern = "embeddings/*.npy filter=lfs diff=lfs merge=lfs -text"
                mock_logger.error.assert_any_call(
                    "Failed to create .gitattributes: No space left on device. "
                    "Please manually create .gitattributes with the "
                    f"following line:\n{lfs_pattern}"
                )

    @pytest.mark.asyncio
    async def test_initialize_embeddings_dir_permission_error(self, tmp_path):
        """Test handling of permission error when creating embeddings directory."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        with (
            patch(
                "scriptrag.analyzers.embedding.get_default_llm_client"
            ) as mock_client,
            patch("pathlib.Path.mkdir") as mock_mkdir,
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            mock_client.return_value = AsyncMock(spec=object)
            mock_mkdir.side_effect = PermissionError("Permission denied")

            await analyzer.initialize()

            # Should log error about failed directory creation
            embeddings_dir = tmp_path / "embeddings"
            mock_logger.error.assert_any_call(
                f"Failed to create embeddings directory {embeddings_dir}: "
                "Permission denied. Embeddings will not be cached to disk."
            )

    @pytest.mark.asyncio
    async def test_initialize_embeddings_dir_os_error(self, tmp_path):
        """Test handling of OSError when creating embeddings directory."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        with (
            patch(
                "scriptrag.analyzers.embedding.get_default_llm_client"
            ) as mock_client,
            patch("pathlib.Path.mkdir") as mock_mkdir,
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            mock_client.return_value = AsyncMock(spec=object)
            mock_mkdir.side_effect = OSError("Disk error")

            await analyzer.initialize()

            # Should log error about failed directory creation
            embeddings_dir = tmp_path / "embeddings"
            mock_logger.error.assert_any_call(
                f"Failed to create embeddings directory {embeddings_dir}: Disk error. "
                "Embeddings will not be cached to disk."
            )

    @pytest.mark.asyncio
    async def test_initialize_all_errors_still_initializes_llm(self, tmp_path):
        """Test that LLM client still initializes even if all file operations fail."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        with (
            patch(
                "scriptrag.analyzers.embedding.get_default_llm_client"
            ) as mock_client,
            patch("pathlib.Path.mkdir") as mock_mkdir,
            patch("pathlib.Path.open") as mock_path_open,
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            mock_llm_client = AsyncMock(spec=object)
            mock_client.return_value = mock_llm_client
            mock_mkdir.side_effect = OSError("Disk error")
            mock_path_open.side_effect = PermissionError("Permission denied")

            await analyzer.initialize()

            # LLM client should still be initialized
            assert analyzer.llm_client is mock_llm_client
            mock_logger.info.assert_any_call(
                "Initialized LLM client for embedding generation"
            )

            # All errors should be logged
            # At least directory and gitattributes errors
            assert mock_logger.error.call_count >= 2

    @pytest.mark.asyncio
    async def test_initialize_successful_after_read_only_gitattributes(self, tmp_path):
        """Test that initialization succeeds even if .gitattributes is read-only."""
        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        # Create .gitattributes file without LFS config
        gitattributes_path = tmp_path / ".gitattributes"
        gitattributes_path.write_text("*.txt text\n")

        with (
            patch(
                "scriptrag.analyzers.embedding.get_default_llm_client"
            ) as mock_client,
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            mock_client.return_value = AsyncMock(spec=object)

            # Mock Path.open to fail on append but succeed on read
            original_open = Path.open
            call_count = [0]

            def mock_path_open(self, mode="r", *args, **kwargs):
                call_count[0] += 1
                # First call is read mode, should succeed
                if call_count[0] == 1:
                    return original_open(self, mode, *args, **kwargs)
                # Second call is append mode, should fail
                if "a" in mode:
                    raise PermissionError("Read-only file system")
                return original_open(self, mode, *args, **kwargs)

            with patch.object(Path, "open", mock_path_open):
                # Should not raise exception
                await analyzer.initialize()

                # Should have initialized successfully
                assert analyzer.llm_client is not None

                # Should have logged the error but continued
                lfs_pattern = "embeddings/*.npy filter=lfs diff=lfs merge=lfs -text"
                mock_logger.error.assert_any_call(
                    "Failed to update .gitattributes: Read-only file system. "
                    "Please manually add the following line to "
                    f".gitattributes:\n{lfs_pattern}"
                )

    @pytest.mark.asyncio
    async def test_initialize_os_error_different_errno(self, tmp_path):
        """Test handling of OSError with specific errno values."""
        import errno

        config = {"repo_path": str(tmp_path)}
        analyzer = SceneEmbeddingAnalyzer(config)

        with (
            patch(
                "scriptrag.analyzers.embedding.get_default_llm_client"
            ) as mock_client,
            patch("pathlib.Path.mkdir") as mock_mkdir,
            patch("scriptrag.analyzers.embedding.logger") as mock_logger,
        ):
            mock_client.return_value = AsyncMock(spec=object)

            # Create OSError with ENOSPC errno (no space left)
            os_error = OSError("No space left on device")
            os_error.errno = errno.ENOSPC
            mock_mkdir.side_effect = os_error

            await analyzer.initialize()

            # Should log error about failed directory creation
            embeddings_dir = tmp_path / "embeddings"
            mock_logger.error.assert_any_call(
                f"Failed to create embeddings directory {embeddings_dir}: "
                "No space left on device. Embeddings will not be cached to disk."
            )
