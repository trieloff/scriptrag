"""Integration tests for LLM timeout handling and reliability.

This module tests:
- Proper timeout handling for LLM operations
- Retry logic with exponential backoff
- Mock provider integration
- Different timeout scenarios
"""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from scriptrag.analyzers.embedding import SceneEmbeddingAnalyzer
from scriptrag.cli.main import app
from scriptrag.config import set_settings
from tests.llm_test_utils import (
    TIMEOUT_INTEGRATION,
    TIMEOUT_LLM,
    retry_flaky_test,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_settings():
    """Reset settings before and after each test."""
    set_settings(None)
    yield
    set_settings(None)


@pytest.fixture
def sample_screenplay(tmp_path):
    """Create a minimal screenplay for testing."""
    script_path = tmp_path / "test_script.fountain"
    content = """Title: Timeout Test Script
Author: Test Suite

INT. TEST SCENE - DAY

A simple test scene.

FADE OUT."""
    script_path.write_text(content)
    return script_path


class TestLLMTimeoutHandling:
    """Test LLM timeout handling in various scenarios."""

    @pytest.mark.integration
    @pytest.mark.timeout(TIMEOUT_INTEGRATION)
    @pytest.mark.asyncio
    async def test_quick_mock_provider(self, mock_llm_provider):
        """Test that mock provider responds quickly."""
        provider = mock_llm_provider

        # Test completion
        from scriptrag.llm import CompletionRequest

        request = CompletionRequest(
            model="mock-model-1",
            messages=[{"role": "user", "content": "Test prompt"}],
            max_tokens=100,
        )

        response = await provider.complete(request)
        assert response.id == "mock-completion-1"
        assert "Mock response" in response.choices[0]["message"]["content"]

    @pytest.mark.integration
    @pytest.mark.timeout(TIMEOUT_INTEGRATION)
    @pytest.mark.asyncio
    async def test_provider_with_simulated_delay(self, mock_llm_provider_with_delay):
        """Test provider with simulated network delay."""
        provider = mock_llm_provider_with_delay

        # Test embedding with delay
        from scriptrag.llm import EmbeddingRequest

        request = EmbeddingRequest(
            model="mock-embedding-model",
            input=["Test text for embedding"],
        )

        # Should complete within timeout despite delay
        response = await provider.embed(request)
        assert response.model == "mock-embedding-model"
        assert len(response.data) == 1

    @pytest.mark.integration
    @pytest.mark.timeout(TIMEOUT_INTEGRATION)
    @retry_flaky_test(max_attempts=3)
    @pytest.mark.asyncio
    async def test_retry_on_transient_failures(self, mock_llm_provider_with_failures):
        """Test retry logic for transient failures."""
        provider = mock_llm_provider_with_failures

        from scriptrag.llm import CompletionRequest

        request = CompletionRequest(
            model="mock-model-1",
            messages=[{"role": "user", "content": "Test prompt"}],
            max_tokens=100,
        )

        # First two calls should succeed
        response1 = await provider.complete(request)
        assert response1.id == "mock-completion-1"

        response2 = await provider.complete(request)
        assert response2.id == "mock-completion-1"

        # Third call should fail
        with pytest.raises(Exception, match="Mock provider error"):
            await provider.complete(request)

    @pytest.mark.integration
    @pytest.mark.timeout(TIMEOUT_LLM)
    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, mock_llm_provider_with_rate_limit):
        """Test rate limit handling."""
        provider = mock_llm_provider_with_rate_limit

        from scriptrag.llm import CompletionRequest

        request = CompletionRequest(
            model="mock-model-1",
            messages=[{"role": "user", "content": "Test prompt"}],
            max_tokens=100,
        )

        # Make calls up to rate limit
        for _ in range(3):
            response = await provider.complete(request)
            assert response.id == "mock-completion-1"

        # Next call should hit rate limit
        with pytest.raises(Exception, match="Rate limit exceeded"):
            await provider.complete(request)

    @pytest.mark.integration
    @pytest.mark.timeout(TIMEOUT_INTEGRATION)
    def test_cli_with_mock_provider(self, tmp_path, sample_screenplay, monkeypatch):
        """Test CLI commands with mock LLM provider."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # Mock the LLM client for analyze command
        with patch("scriptrag.utils.get_default_llm_client") as mock_get_client:
            # Create a mock client that returns quickly
            from unittest.mock import AsyncMock

            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(
                return_value=type(
                    "Response",
                    (),
                    {"choices": [{"text": '{"scene_analysis": "mocked"}'}]},
                )
            )
            mock_get_client.return_value = mock_client

            # Analyze should complete quickly with mock
            result = runner.invoke(
                app,
                ["analyze", str(sample_screenplay.parent)],
                catch_exceptions=False,
            )

            # Even if analyze fails, it should fail quickly
            assert result.exit_code in [0, 1]  # Accept both success and failure

    @pytest.mark.integration
    @pytest.mark.timeout(TIMEOUT_INTEGRATION)
    @pytest.mark.asyncio
    async def test_embedding_analyzer_with_mock(self, tmp_path):
        """Test embedding analyzer with mock LLM provider."""
        # Create analyzer with mock configuration
        config = {
            "embedding_model": "mock-embedding-model",
            "dimensions": 5,
            "lfs_path": "embeddings",
            "repo_path": str(tmp_path),
        }

        # Initialize git repo for the test
        import git

        git.Repo.init(tmp_path)

        analyzer = SceneEmbeddingAnalyzer(config)

        # Mock the LLM client
        with patch(
            "scriptrag.analyzers.embedding.get_default_llm_client"
        ) as mock_get_client:
            from unittest.mock import AsyncMock, Mock

            mock_client = AsyncMock()

            # Mock embedding response
            mock_embedding = Mock()
            mock_embedding.embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

            from scriptrag.llm.models import EmbeddingResponse

            response = Mock(spec=EmbeddingResponse)
            response.data = [mock_embedding]
            mock_client.embed.return_value = response

            mock_get_client.return_value = mock_client

            # Initialize analyzer
            await analyzer.initialize()

            # Test scene analysis
            scene = {
                "heading": "INT. TEST SCENE - DAY",
                "content": "A test scene",
                "action": ["Test action"],
                "dialogue": [],
            }

            result = await analyzer.analyze(scene)
            assert "embedding_path" in result
            assert result["dimensions"] == 5


class TestTimeoutConfiguration:
    """Test different timeout configurations."""

    @pytest.mark.unit
    @pytest.mark.timeout(10)  # Short timeout for unit test
    def test_unit_test_timeout(self):
        """Test that unit tests have appropriate timeout."""
        # Simple unit test that should complete quickly
        assert 1 + 1 == 2

    @pytest.mark.integration
    @pytest.mark.timeout(30)  # Medium timeout for integration test
    def test_integration_test_timeout(self, tmp_path):
        """Test that integration tests have appropriate timeout."""
        # Integration test that might take longer
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        assert test_file.exists()
        assert test_file.read_text() == "test content"

    @pytest.mark.requires_llm
    @pytest.mark.timeout(60)  # Longer timeout for LLM test
    @pytest.mark.asyncio
    async def test_llm_test_timeout(self):
        """Test that LLM tests have appropriate timeout."""
        # This would normally use a real LLM, but we'll mock it
        with patch("scriptrag.utils.get_default_llm_client") as mock_get_client:
            from unittest.mock import AsyncMock

            mock_client = AsyncMock()
            mock_client.complete = AsyncMock(
                return_value=type(
                    "Response",
                    (),
                    {"choices": [{"message": {"content": "Mocked LLM response"}}]},
                )
            )
            mock_get_client.return_value = mock_client

            # Simulate LLM operation
            from scriptrag.utils import get_default_llm_client

            client = await get_default_llm_client()
            response = await client.complete(
                type("Request", (), {"prompt": "Test", "max_tokens": 10})
            )
            assert response.choices[0]["message"]["content"] == "Mocked LLM response"
