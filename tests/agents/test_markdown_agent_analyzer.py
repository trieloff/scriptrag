"""Tests for the MarkdownAgentAnalyzer."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jsonschema import ValidationError

from scriptrag.agents.agent_spec import AgentSpec
from scriptrag.agents.markdown_agent_analyzer import MarkdownAgentAnalyzer
from scriptrag.llm.models import CompletionResponse, LLMProvider


class TestMarkdownAgentAnalyzer:
    """Test MarkdownAgentAnalyzer functionality."""

    @pytest.fixture
    def basic_spec(self) -> AgentSpec:
        """Create a basic agent specification."""
        spec = MagicMock(spec=AgentSpec)
        spec.name = "test_agent"
        spec.version = "1.0.0"
        spec.requires_llm = False
        spec.context_query = None
        spec.analysis_prompt = "Analyze this scene"
        spec.output_schema = {
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
        }
        return spec

    @pytest.fixture
    def llm_spec(self) -> AgentSpec:
        """Create an LLM-based agent specification."""
        spec = MagicMock(spec=AgentSpec)
        spec.name = "llm_agent"
        spec.version = "2.0.0"
        spec.requires_llm = True
        spec.context_query = "SELECT * FROM scenes"
        spec.analysis_prompt = "Analyze scene: {{scene_content}}"
        spec.output_schema = {
            "type": "object",
            "properties": {"analysis": {"type": "string"}, "score": {"type": "number"}},
            "required": ["analysis"],
        }
        return spec

    @pytest.fixture
    def analyzer(self, basic_spec: AgentSpec) -> MarkdownAgentAnalyzer:
        """Create analyzer with basic spec."""
        return MarkdownAgentAnalyzer(basic_spec)

    @pytest.fixture
    def llm_analyzer(self, llm_spec: AgentSpec) -> MarkdownAgentAnalyzer:
        """Create analyzer with LLM spec."""
        return MarkdownAgentAnalyzer(llm_spec)

    @pytest.fixture
    def sample_scene(self) -> dict:
        """Create a sample scene."""
        return {
            "heading": "INT. OFFICE - DAY",
            "action": ["John enters the room.", "He looks around nervously."],
            "dialogue": [
                {"character": "JOHN", "text": "Hello? Is anyone here?"},
                {"character": "VOICE", "text": "Come in, John."},
            ],
        }

    def test_init(self, basic_spec: AgentSpec) -> None:
        """Test analyzer initialization."""
        analyzer = MarkdownAgentAnalyzer(basic_spec)
        assert analyzer.spec == basic_spec
        assert analyzer.llm_client is None

    def test_init_with_config(self, basic_spec: AgentSpec) -> None:
        """Test analyzer initialization with config."""
        config = {"test": "value"}
        analyzer = MarkdownAgentAnalyzer(basic_spec, config)
        assert analyzer.spec == basic_spec
        assert analyzer.config == config

    def test_name_property(self, analyzer: MarkdownAgentAnalyzer) -> None:
        """Test name property."""
        assert analyzer.name == "test_agent"

    def test_version_property(self, analyzer: MarkdownAgentAnalyzer) -> None:
        """Test version property."""
        assert analyzer.version == "1.0.0"

    def test_requires_llm_property(
        self, analyzer: MarkdownAgentAnalyzer, llm_analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test requires_llm property."""
        assert analyzer.requires_llm is False
        assert llm_analyzer.requires_llm is True

    @pytest.mark.asyncio
    async def test_initialize_without_llm(
        self, analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test initialization without LLM requirement."""
        await analyzer.initialize()
        assert analyzer.llm_client is None

    @pytest.mark.asyncio
    async def test_initialize_with_llm(
        self, llm_analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test initialization with LLM requirement."""
        mock_client = MagicMock(spec=object)
        with patch(
            "scriptrag.agents.markdown_agent_analyzer.get_default_llm_client",
            return_value=mock_client,
        ):
            await llm_analyzer.initialize()
            assert llm_analyzer.llm_client == mock_client

    @pytest.mark.asyncio
    async def test_initialize_idempotent(
        self, llm_analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test that initialize is idempotent."""
        mock_client = MagicMock(spec=object)
        llm_analyzer.llm_client = mock_client

        with patch(
            "scriptrag.agents.markdown_agent_analyzer.get_default_llm_client"
        ) as mock_get_client:
            await llm_analyzer.initialize()
            # Should not call get_client if already initialized
            mock_get_client.assert_not_called()
            assert llm_analyzer.llm_client == mock_client

    @pytest.mark.asyncio
    async def test_cleanup(self, llm_analyzer: MarkdownAgentAnalyzer) -> None:
        """Test cleanup."""
        llm_analyzer.llm_client = MagicMock(spec=object)
        await llm_analyzer.cleanup()
        assert llm_analyzer.llm_client is None

    @pytest.mark.asyncio
    async def test_analyze_non_llm(
        self, analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test analyze without LLM."""
        result = await analyzer.analyze(sample_scene)

        # Should return metadata even for non-LLM
        assert result["analyzer"] == "test_agent"
        assert result["version"] == "1.0.0"
        # property field is only added for successful results
        if "error" not in result:
            assert result["property"] == "test_agent"

    @pytest.mark.asyncio
    async def test_analyze_non_llm_validation_failure(
        self, basic_spec: AgentSpec, sample_scene: dict
    ) -> None:
        """Test non-LLM analyze with validation failure."""
        # Make schema require a field that won't be present
        basic_spec.output_schema = {
            "type": "object",
            "properties": {"required_field": {"type": "string"}},
            "required": ["required_field"],
        }

        analyzer = MarkdownAgentAnalyzer(basic_spec)

        # Non-LLM agents bypass validation, so no exception should be raised
        # They return empty dict with metadata
        result = await analyzer.analyze(sample_scene)

        # Should return metadata even for non-LLM with invalid schema
        assert result["analyzer"] == "test_agent"
        assert result["version"] == "1.0.0"
        assert result["property"] == "test_agent"

    @pytest.mark.asyncio
    async def test_analyze_with_llm_success(
        self, llm_analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test successful LLM-based analysis."""
        mock_client = AsyncMock(spec=["complete", "cleanup"])
        mock_response = MagicMock(spec=CompletionResponse)
        mock_response.content = json.dumps(
            {"analysis": "Scene shows tension", "score": 0.8}
        )
        mock_response.model = "test-model"
        mock_response.provider = LLMProvider.OPENAI_COMPATIBLE
        mock_response.usage = {"total_tokens": 100}
        mock_client.complete.return_value = mock_response

        llm_analyzer.llm_client = mock_client

        # Mock context query executor to avoid database dependency
        with patch.object(
            llm_analyzer.context_executor, "execute", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = []  # Empty query results

            result = await llm_analyzer.analyze(sample_scene)

            assert result["analysis"] == "Scene shows tension"
            assert result["score"] == 0.8
            assert result["analyzer"] == "llm_agent"
            assert result["version"] == "2.0.0"

            # Verify LLM was called
            mock_client.complete.assert_called_once()
            # Verify context query was called
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_with_llm_auto_initialize(
        self, llm_analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test that analyze auto-initializes LLM client if needed."""
        mock_client = AsyncMock(spec=["complete", "cleanup"])
        mock_response = MagicMock(spec=CompletionResponse)
        mock_response.content = '{"analysis": "Initialized and analyzed"}'
        mock_response.model = "test-model"
        mock_response.provider = LLMProvider.OPENAI_COMPATIBLE
        mock_response.usage = {}
        mock_client.complete.return_value = mock_response

        with patch(
            "scriptrag.agents.markdown_agent_analyzer.get_default_llm_client",
            return_value=mock_client,
        ):
            # Mock context query executor to avoid database dependency
            with patch.object(
                llm_analyzer.context_executor, "execute", new_callable=AsyncMock
            ) as mock_execute:
                mock_execute.return_value = []  # Empty query results

                result = await llm_analyzer.analyze(sample_scene)

                assert llm_analyzer.llm_client == mock_client
                assert result["analysis"] == "Initialized and analyzed"
                mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_with_llm_validation_retry(
        self, llm_analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test LLM analysis with validation retry."""
        mock_client = AsyncMock(spec=["complete", "cleanup"])

        # First call returns invalid, second returns valid
        responses = [
            MagicMock(content='{"wrong_field": "value"}'),
            MagicMock(content='{"analysis": "Valid on retry"}'),
        ]
        for r in responses:
            r.model = "test-model"
            r.provider = LLMProvider.OPENAI_COMPATIBLE
            r.usage = {}

        mock_client.complete.side_effect = responses
        llm_analyzer.llm_client = mock_client

        # Mock context query executor to avoid database dependency
        with patch.object(
            llm_analyzer.context_executor, "execute", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = []  # Empty query results

            # Suppress logging during validation error testing
            # to prevent Windows CI log duplication
            with patch("scriptrag.agents.markdown_agent_analyzer.logger"):
                result = await llm_analyzer.analyze(sample_scene)

            assert result["analysis"] == "Valid on retry"
            # Should have called LLM twice
            assert mock_client.complete.call_count == 2

            # Check temperature increased on retry
            first_call = mock_client.complete.call_args_list[0]
            second_call = mock_client.complete.call_args_list[1]
            assert first_call[0][0].temperature == 0.3
            assert second_call[0][0].temperature == 0.5
            # Should have called context query once
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_with_llm_max_retries_exceeded(
        self, llm_analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test LLM analysis when max retries exceeded."""
        mock_client = AsyncMock(spec=["complete", "cleanup"])

        # All attempts return invalid data
        mock_response = MagicMock(spec=CompletionResponse)
        mock_response.content = '{"invalid": "data"}'
        mock_response.model = "test-model"
        mock_response.provider = LLMProvider.OPENAI_COMPATIBLE
        mock_response.usage = {}
        mock_client.complete.return_value = mock_response

        llm_analyzer.llm_client = mock_client

        # Mock context query executor to avoid database dependency
        with patch.object(
            llm_analyzer.context_executor, "execute", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = []  # Empty query results

            # Suppress logging during validation error testing
            # to prevent Windows CI log duplication
            with patch("scriptrag.agents.markdown_agent_analyzer.logger"):
                # Should raise ValidationError after 3 attempts
                with pytest.raises(ValidationError) as exc_info:
                    await llm_analyzer.analyze(sample_scene)

            assert "3 attempts" in str(exc_info.value)
            # Should have tried 3 times
            assert mock_client.complete.call_count == 3

            # Check temperatures increased
            calls = mock_client.complete.call_args_list
            assert calls[0][0][0].temperature == 0.3
            assert calls[1][0][0].temperature == 0.5
            assert calls[2][0][0].temperature == 0.7
            # Should have called context query once
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_llm_exception(
        self, llm_analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test handling of LLM exceptions."""
        mock_client = AsyncMock(spec=["complete", "cleanup"])
        mock_client.complete.side_effect = Exception("LLM error")
        llm_analyzer.llm_client = mock_client

        # Mock context query executor to avoid database dependency
        with patch.object(
            llm_analyzer.context_executor, "execute", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = []  # Empty query results

            # Suppress logging during validation error testing
            # to prevent Windows CI log duplication
            with patch("scriptrag.agents.markdown_agent_analyzer.logger"):
                # When LLM call fails, it returns empty dict which fails validation
                # This should raise ValidationError after 3 attempts
                with pytest.raises(ValidationError) as exc_info:
                    await llm_analyzer.analyze(sample_scene)

            assert "llm_agent" in str(exc_info.value)
            assert "3 attempts" in str(exc_info.value)
            # Should have tried 3 times
            assert mock_client.complete.call_count == 3
            # Should have called context query once
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_context_query(
        self, llm_analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test context query execution with mock."""
        # Mock context query executor to avoid database dependency
        with patch.object(
            llm_analyzer.context_executor, "execute", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = [
                {"id": 1, "name": "test"}
            ]  # Mock query results

            context = await llm_analyzer._execute_context_query(sample_scene)

            # Should return scene data and context results
            assert context["scene_data"] == sample_scene
            assert "context_results" in context
            assert "formatted_context" in context
            mock_execute.assert_called_once()

    def test_format_scene_content_full(
        self, analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test formatting full scene content."""
        content = analyzer._format_scene_content(sample_scene)

        assert "SCENE HEADING: INT. OFFICE - DAY" in content
        assert "ACTION:" in content
        assert "John enters the room." in content
        assert "DIALOGUE:" in content
        assert "JOHN: Hello? Is anyone here?" in content
        assert "VOICE: Come in, John." in content

    def test_format_scene_content_minimal(
        self, analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test formatting minimal scene content."""
        scene = {"content": "Simple content"}
        content = analyzer._format_scene_content(scene)
        assert content == "Simple content"

    def test_format_scene_content_empty_action(
        self, analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test formatting with empty action lines."""
        scene = {"heading": "TEST SCENE", "action": ["", "  ", "Real action"]}
        content = analyzer._format_scene_content(scene)

        assert "Real action" in content
        # Empty lines should be filtered out
        assert content.count("\n\n") == 0

    def test_format_scene_content_no_dialogue_text(
        self, analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test formatting with missing dialogue text."""
        scene = {
            "dialogue": [
                {"character": "JOHN", "text": ""},
                {"character": "", "text": "Hello"},
                {"character": "MARY", "text": "Hi"},
            ]
        }
        content = analyzer._format_scene_content(scene)

        # Only complete dialogue entries should appear
        assert "MARY: Hi" in content
        assert "JOHN:" not in content
        assert ": Hello" not in content

    @pytest.mark.asyncio
    async def test_call_llm_with_scene_content_replacement(
        self, llm_analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test LLM call with scene content replacement."""
        llm_analyzer.spec.analysis_prompt = "Analyze: {{scene_content}}"

        mock_client = AsyncMock(spec=["complete", "cleanup"])
        mock_response = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_response.content = '{"analysis": "done"}'
        mock_response.model = "test"
        mock_response.provider = LLMProvider.OPENAI_COMPATIBLE
        mock_response.usage = {}
        mock_client.complete.return_value = mock_response
        llm_analyzer.llm_client = mock_client

        await llm_analyzer._call_llm(sample_scene, {})

        # Check that scene content was inserted
        call_args = mock_client.complete.call_args[0][0]
        assert "INT. OFFICE - DAY" in call_args.messages[0]["content"]
        assert "{{scene_content}}" not in call_args.messages[0]["content"]

    @pytest.mark.asyncio
    async def test_call_llm_with_fountain_block_replacement(
        self, llm_analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test LLM call with fountain code block replacement."""
        llm_analyzer.spec.analysis_prompt = "```fountain\n{{scene_content}}\n```"

        mock_client = AsyncMock(spec=["complete", "cleanup"])
        mock_response = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_response.content = '{"analysis": "done"}'
        mock_response.model = "test"
        mock_response.provider = LLMProvider.OPENAI_COMPATIBLE
        mock_response.usage = {}
        mock_client.complete.return_value = mock_response
        llm_analyzer.llm_client = mock_client

        await llm_analyzer._call_llm(sample_scene, {})

        call_args = mock_client.complete.call_args[0][0]
        prompt = call_args.messages[0]["content"]
        assert "```fountain" in prompt
        assert "INT. OFFICE - DAY" in prompt
        assert "{{scene_content}}" not in prompt

    @pytest.mark.asyncio
    async def test_call_llm_with_sql_context_replacement(
        self, llm_analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test LLM call with SQL context query replacement."""
        llm_analyzer.spec.analysis_prompt = (
            "Context:\n```sql\nSELECT * FROM scenes\n```\nAnalyze scene"
        )
        llm_analyzer.spec.context_query = "SELECT * FROM scenes"

        mock_client = AsyncMock(spec=["complete", "cleanup"])
        mock_response = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_response.content = '{"analysis": "done"}'
        mock_response.model = "test"
        mock_response.provider = LLMProvider.OPENAI_COMPATIBLE
        mock_response.usage = {}
        mock_client.complete.return_value = mock_response
        llm_analyzer.llm_client = mock_client

        await llm_analyzer._call_llm(sample_scene, {})

        call_args = mock_client.complete.call_args[0][0]
        prompt = call_args.messages[0]["content"]
        # The SQL block should be replaced with context results
        assert "-- No context results available" in prompt
        assert "```sql" not in prompt

    @pytest.mark.asyncio
    async def test_call_llm_with_response_format(
        self, llm_analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test LLM call with JSON schema response format."""
        llm_analyzer.spec.analysis_prompt = "```json\n{schema}\n```\nAnalyze the scene"

        mock_client = AsyncMock(spec=["complete", "cleanup"])
        mock_response = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_response.content = '{"analysis": "structured"}'
        mock_response.model = "test"
        mock_response.provider = LLMProvider.OPENAI_COMPATIBLE
        mock_response.usage = {}
        mock_client.complete.return_value = mock_response
        llm_analyzer.llm_client = mock_client

        await llm_analyzer._call_llm(sample_scene, {})

        call_args = mock_client.complete.call_args[0][0]
        # JSON block should be removed from prompt
        assert "```json" not in call_args.messages[0]["content"]
        # Response format should be set
        assert call_args.response_format is not None
        assert call_args.response_format["type"] == "json_schema"

    @pytest.mark.asyncio
    async def test_call_llm_no_client_error(
        self, llm_analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test LLM call without initialized client."""
        llm_analyzer.llm_client = None

        result = await llm_analyzer._call_llm(sample_scene, {})

        # Should return empty dict on error
        assert result == {}

    @pytest.mark.asyncio
    async def test_call_llm_with_temperature(
        self, llm_analyzer: MarkdownAgentAnalyzer, sample_scene: dict
    ) -> None:
        """Test LLM call with custom temperature."""
        mock_client = AsyncMock(spec=["complete", "cleanup"])
        mock_response = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_response.content = '{"analysis": "temp test"}'
        mock_response.model = "test"
        mock_response.provider = LLMProvider.OPENAI_COMPATIBLE
        mock_response.usage = {}
        mock_client.complete.return_value = mock_response
        llm_analyzer.llm_client = mock_client

        await llm_analyzer._call_llm(sample_scene, {}, temperature=0.7)

        call_args = mock_client.complete.call_args[0][0]
        assert call_args.temperature == 0.7

    def test_parse_llm_response_plain_json(
        self, analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test parsing plain JSON response."""
        response = '{"result": "test", "value": 123}'
        parsed = analyzer._parse_llm_response(response)

        assert parsed == {"result": "test", "value": 123}

    def test_parse_llm_response_json_code_block(
        self, analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test parsing JSON from code block."""
        response = 'Here is the result:\n```json\n{"result": "extracted"}\n```'
        parsed = analyzer._parse_llm_response(response)

        assert parsed == {"result": "extracted"}

    def test_parse_llm_response_plain_code_block(
        self, analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test parsing JSON from plain code block."""
        response = 'Result:\n```\n{"data": "value"}\n```'
        parsed = analyzer._parse_llm_response(response)

        assert parsed == {"data": "value"}

    def test_parse_llm_response_embedded_json(
        self, analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test extracting JSON from text."""
        response = 'The analysis result is {"score": 0.8, "verdict": "good"} as shown.'
        parsed = analyzer._parse_llm_response(response)

        assert parsed == {"score": 0.8, "verdict": "good"}

    def test_parse_llm_response_invalid_json(
        self, analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test parsing invalid JSON."""
        response = "This is not JSON at all"
        parsed = analyzer._parse_llm_response(response)

        assert parsed == {}

    def test_parse_llm_response_non_dict_json(
        self, analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test parsing JSON that's not a dict."""
        response = '["array", "not", "dict"]'
        parsed = analyzer._parse_llm_response(response)

        assert parsed == {}

    def test_parse_llm_response_whitespace(
        self, analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test parsing with extra whitespace."""
        response = '  \n  {"trimmed": true}  \n  '
        parsed = analyzer._parse_llm_response(response)

        assert parsed == {"trimmed": True}

    def test_parse_llm_response_nested_json(
        self, analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test parsing nested JSON objects."""
        response = '{"outer": {"inner": {"deep": "value"}}}'
        parsed = analyzer._parse_llm_response(response)

        assert parsed == {"outer": {"inner": {"deep": "value"}}}

    def test_parse_llm_response_markdown_with_text(
        self, analyzer: MarkdownAgentAnalyzer
    ) -> None:
        """Test parsing JSON from markdown with surrounding text."""
        response = """
        Based on my analysis, here are the results:

        ```json
        {
            "confidence": 0.95,
            "summary": "High quality scene"
        }
        ```

        This indicates a strong narrative structure.
        """
        parsed = analyzer._parse_llm_response(response)

        assert parsed == {"confidence": 0.95, "summary": "High quality scene"}
