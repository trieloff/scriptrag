"""Test that validation errors don't pollute boneyard metadata."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from scriptrag.agents.markdown_agent_analyzer import MarkdownAgentAnalyzer
from scriptrag.api.analyze import AnalyzeCommand
from scriptrag.parser.fountain_parser import FountainParser


class TestAnalyzeValidationErrors:
    """Test validation error handling in analyze command."""

    @pytest.fixture
    def sample_fountain_content(self) -> str:
        """Create sample fountain content."""
        return """Title: Test Script
Author: Test Author

INT. OFFICE - DAY

JOHN enters the room nervously.

JOHN
Is anyone here?

VOICE (O.S.)
Come in, John.
"""

    @pytest.fixture
    def temp_fountain_file(self, tmp_path: Path, sample_fountain_content: str) -> Path:
        """Create a temporary fountain file."""
        file_path = tmp_path / "test_script.fountain"
        file_path.write_text(sample_fountain_content)
        return file_path

    @pytest.fixture
    def failing_analyzer(self) -> MarkdownAgentAnalyzer:
        """Create an analyzer that always fails validation."""
        spec = MagicMock(spec=["content", "model", "provider", "usage"])
        spec.name = "failing_agent"
        spec.version = "1.0.0"
        spec.requires_llm = True
        spec.context_query = None
        spec.analysis_prompt = "Analyze scene"
        # Schema that will always fail validation
        spec.output_schema = {
            "type": "object",
            "properties": {"required_field": {"type": "string"}},
            "required": ["required_field"],
        }

        analyzer = MarkdownAgentAnalyzer(spec)

        # Mock LLM to return invalid data
        mock_client = AsyncMock(spec=["complete"])
        mock_response = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_response.content = '{"wrong_field": "value"}'
        mock_response.model = "test-model"
        mock_response.provider = None
        mock_response.usage = {}
        # Configure complete as AsyncMock to make it properly awaitable
        mock_client.complete = AsyncMock(return_value=mock_response)
        analyzer.llm_client = mock_client

        return analyzer

    @pytest.mark.asyncio
    async def test_validation_error_not_in_boneyard(
        self, temp_fountain_file: Path, failing_analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test that validation errors don't get written to boneyard."""
        # Create analyze command with failing analyzer
        analyze_cmd = AnalyzeCommand(analyzers=[failing_analyzer])

        # Run analysis - should not fail (non-brittle mode)
        result = await analyze_cmd._process_file(
            temp_fountain_file, force=True, dry_run=False, brittle=False
        )

        # Verify file was processed
        assert result.path == temp_fountain_file

        # Read the file back and check boneyard
        parser = FountainParser()
        script = parser.parse_file(temp_fountain_file)

        # Check that no error data was written to boneyard
        for scene in script.scenes:
            metadata = scene.boneyard_metadata or {}

            # The failing analyzer should not appear in metadata
            if "analyzers" in metadata:
                assert "failing_agent" not in metadata["analyzers"]

                # Double-check no error fields in any analyzer data
                for _analyzer_name, analyzer_data in metadata["analyzers"].items():
                    if isinstance(analyzer_data, dict):
                        assert "error" not in analyzer_data

    @pytest.mark.asyncio
    async def test_validation_error_brittle_mode(
        self, temp_fountain_file: Path, failing_analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test that validation errors raise in brittle mode."""
        # Create analyze command with failing analyzer in brittle mode
        analyze_cmd = AnalyzeCommand(analyzers=[failing_analyzer])

        # Run analysis in brittle mode - should raise
        from scriptrag.exceptions import AnalyzerError

        with pytest.raises(AnalyzerError) as exc_info:
            await analyze_cmd._process_file(
                temp_fountain_file, force=True, dry_run=False, brittle=True
            )

        assert "validation failed" in str(exc_info.value).lower()
        assert "failing_agent" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_mixed_analyzers_with_failure(
        self, temp_fountain_file: Path, failing_analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test that successful analyzers still write when one fails."""
        # Create a successful analyzer
        success_spec = MagicMock(spec=["content", "model", "provider", "usage"])
        success_spec.name = "success_agent"
        success_spec.version = "1.0.0"
        success_spec.requires_llm = False
        success_spec.context_query = None
        success_spec.analysis_prompt = "Analyze"
        success_spec.output_schema = {"type": "object"}

        success_analyzer = MarkdownAgentAnalyzer(success_spec)

        # Create analyze command with both analyzers
        analyze_cmd = AnalyzeCommand(analyzers=[failing_analyzer, success_analyzer])

        # Run analysis
        result = await analyze_cmd._process_file(
            temp_fountain_file, force=True, dry_run=False, brittle=False
        )

        # Read the file back
        parser = FountainParser()
        script = parser.parse_file(temp_fountain_file)

        # Check metadata
        for scene in script.scenes:
            metadata = scene.boneyard_metadata or {}

            if "analyzers" in metadata:
                # Success analyzer should be present
                assert "success_agent" in metadata["analyzers"]
                # Failing analyzer should not be present
                assert "failing_agent" not in metadata["analyzers"]

                # Verify success analyzer data is clean
                success_data = metadata["analyzers"]["success_agent"]
                assert "error" not in success_data
                assert "version" in success_data
