"""Tests for the agent loader module."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.agents.loader import AgentLoader, AgentSpec, MarkdownAgentAnalyzer

if TYPE_CHECKING:
    pass


@pytest.fixture
def sample_agent_markdown() -> str:
    """Return sample markdown content for an agent."""
    return """---
description: A test agent
version: 1.0.0
requires_llm: true
---

# Test Agent

This is a test agent for analyzing scenes.

## Context Query

```sql
SELECT * FROM scenes WHERE id = ?
```

## Output Schema

```json
{
    "type": "object",
    "properties": {
        "result": {"type": "string"}
    },
    "required": ["result"]
}
```

## Analysis Prompt

Analyze the scene: {scene_text}
"""


@pytest.fixture
def sample_agent_markdown_no_llm() -> str:
    """Return sample markdown content for an agent that doesn't require LLM."""
    return """---
description: A simple agent
version: 1.0.0
requires_llm: false
---

# Simple Agent

## Output Schema

```json
{
    "type": "object",
    "properties": {
        "count": {"type": "number"}
    }
}
```
"""


@pytest.fixture
def invalid_agent_markdown_no_frontmatter() -> str:
    """Return markdown without frontmatter."""
    return """# Agent Without Frontmatter

This agent has no frontmatter metadata.

```json
{"type": "object"}
```
"""


@pytest.fixture
def invalid_agent_markdown_missing_required() -> str:
    """Return markdown missing required fields."""
    return """---
name: incomplete-agent
---

# Incomplete Agent

```json
{"type": "object"}
```
"""


@pytest.fixture
def invalid_agent_markdown_no_schema() -> str:
    """Return markdown without JSON schema."""
    return """---
property: no_schema_prop
description: Agent without schema
version: 1.0.0
---

# Agent Without Schema

This agent has no JSON schema block.
"""


@pytest.fixture
def invalid_agent_markdown_bad_json() -> str:
    """Return markdown with invalid JSON."""
    return """---
property: bad_json_prop
description: Agent with bad JSON
version: 1.0.0
---

# Agent With Bad JSON

```json
{not valid json}
```
"""


@pytest.fixture
def temp_agent_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with agent files."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    return agents_dir


class TestAgentSpec:
    """Tests for AgentSpec class."""

    def test_init(self) -> None:
        """Test AgentSpec initialization."""
        spec = AgentSpec(
            name="test",
            description="Test agent",
            version="1.0.0",
            requires_llm=True,
            context_query="SELECT * FROM scenes",
            output_schema={"type": "object"},
            analysis_prompt="Analyze this",
        )
        assert spec.name == "test"
        assert spec.description == "Test agent"
        assert spec.version == "1.0.0"
        assert spec.requires_llm is True
        assert spec.context_query == "SELECT * FROM scenes"
        assert spec.output_schema == {"type": "object"}
        assert spec.analysis_prompt == "Analyze this"

    def test_from_markdown_valid(
        self, sample_agent_markdown: str, temp_agent_dir: Path
    ) -> None:
        """Test loading valid agent from markdown."""
        agent_file = temp_agent_dir / "test-agent.md"
        agent_file.write_text(sample_agent_markdown)

        spec = AgentSpec.from_markdown(agent_file)

        assert spec.name == "test-agent"  # Derived from filename
        assert spec.description == "A test agent"
        assert spec.version == "1.0.0"
        assert spec.requires_llm is True
        assert "SELECT * FROM scenes" in spec.context_query
        assert spec.output_schema["type"] == "object"
        assert "Analyze the scene:" in spec.analysis_prompt

    def test_from_markdown_no_name_uses_filename(
        self, sample_agent_markdown_no_llm: str, temp_agent_dir: Path
    ) -> None:
        """Test that agent name is derived from filename if not in metadata."""
        agent_file = temp_agent_dir / "simple-agent.md"
        agent_file.write_text(sample_agent_markdown_no_llm)

        spec = AgentSpec.from_markdown(agent_file)

        assert spec.name == "simple-agent"  # Derived from filename
        assert spec.requires_llm is False

    def test_from_markdown_file_not_found(self, temp_agent_dir: Path) -> None:
        """Test error when markdown file doesn't exist."""
        agent_file = temp_agent_dir / "nonexistent.md"

        with pytest.raises(ValueError, match="Agent specification not found"):
            AgentSpec.from_markdown(agent_file)

    def test_from_markdown_no_frontmatter(
        self, invalid_agent_markdown_no_frontmatter: str, temp_agent_dir: Path
    ) -> None:
        """Test error when markdown has no frontmatter."""
        agent_file = temp_agent_dir / "no-frontmatter.md"
        agent_file.write_text(invalid_agent_markdown_no_frontmatter)

        with pytest.raises(ValueError, match="No frontmatter found"):
            AgentSpec.from_markdown(agent_file)

    def test_from_markdown_missing_required_fields(
        self, invalid_agent_markdown_missing_required: str, temp_agent_dir: Path
    ) -> None:
        """Test error when required fields are missing."""
        agent_file = temp_agent_dir / "incomplete.md"
        agent_file.write_text(invalid_agent_markdown_missing_required)

        with pytest.raises(ValueError, match="Missing required field"):
            AgentSpec.from_markdown(agent_file)

    def test_from_markdown_no_json_schema(
        self, invalid_agent_markdown_no_schema: str, temp_agent_dir: Path
    ) -> None:
        """Test error when no JSON schema is found."""
        agent_file = temp_agent_dir / "no-schema.md"
        agent_file.write_text(invalid_agent_markdown_no_schema)

        with pytest.raises(ValueError, match="No valid JSON schema found"):
            AgentSpec.from_markdown(agent_file)

    def test_from_markdown_invalid_json(
        self, invalid_agent_markdown_bad_json: str, temp_agent_dir: Path
    ) -> None:
        """Test handling of invalid JSON in schema block."""
        agent_file = temp_agent_dir / "bad-json.md"
        agent_file.write_text(invalid_agent_markdown_bad_json)

        # Should skip invalid JSON and raise error about no valid schema
        with pytest.raises(ValueError, match="No valid JSON schema found"):
            AgentSpec.from_markdown(agent_file)

    def test_extract_code_blocks(self) -> None:
        """Test code block extraction from markdown."""
        content = """
# Test Document

Some text here.

```python
print("hello")
```

More text.

```json
{"key": "value"}
```

```
No language specified
```
"""
        blocks = AgentSpec._extract_code_blocks(content)

        assert len(blocks) == 3
        assert blocks[0]["lang"] == "python"
        assert blocks[0]["content"] == 'print("hello")'
        assert blocks[1]["lang"] == "json"
        assert blocks[1]["content"] == '{"key": "value"}'
        assert blocks[2]["lang"] == ""
        assert blocks[2]["content"] == "No language specified"

    def test_extract_code_blocks_empty(self) -> None:
        """Test code block extraction with no blocks."""
        content = "# Just text\n\nNo code blocks here."
        blocks = AgentSpec._extract_code_blocks(content)
        assert blocks == []


class TestMarkdownAgentAnalyzer:
    """Tests for MarkdownAgentAnalyzer class."""

    @pytest.fixture
    def sample_spec(self) -> AgentSpec:
        """Create a sample AgentSpec."""
        return AgentSpec(
            name="test-analyzer",
            description="Test analyzer",
            version="2.0.0",
            requires_llm=True,
            context_query="SELECT * FROM scenes",
            output_schema={
                "type": "object",
                "properties": {"result": {"type": "string"}},
                "required": ["result"],
            },
            analysis_prompt="Analyze: {{scene_content}}",
        )

    def test_init(self, sample_spec: AgentSpec) -> None:
        """Test MarkdownAgentAnalyzer initialization."""
        analyzer = MarkdownAgentAnalyzer(sample_spec)
        assert analyzer.spec == sample_spec
        assert analyzer.llm_client is None

    def test_properties(self, sample_spec: AgentSpec) -> None:
        """Test analyzer properties."""
        analyzer = MarkdownAgentAnalyzer(sample_spec)
        assert analyzer.name == "test-analyzer"
        assert analyzer.version == "2.0.0"
        assert analyzer.requires_llm is True

    @pytest.mark.asyncio
    async def test_initialize_with_llm(self, sample_spec: AgentSpec) -> None:
        """Test initialization with LLM requirement."""
        analyzer = MarkdownAgentAnalyzer(sample_spec)

        with patch(
            "scriptrag.agents.markdown_agent_analyzer.get_default_llm_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            await analyzer.initialize()

            mock_get_client.assert_called_once()
            assert analyzer.llm_client == mock_client

    @pytest.mark.asyncio
    async def test_initialize_without_llm(self) -> None:
        """Test initialization without LLM requirement."""
        spec = AgentSpec(
            name="no-llm",
            description="No LLM",
            version="1.0.0",
            requires_llm=False,
            context_query="",
            output_schema={"type": "object"},
            analysis_prompt="",
        )
        analyzer = MarkdownAgentAnalyzer(spec)

        with patch(
            "scriptrag.agents.markdown_agent_analyzer.get_default_llm_client"
        ) as mock_get_client:
            await analyzer.initialize()
            mock_get_client.assert_not_called()
            assert analyzer.llm_client is None

    @pytest.mark.asyncio
    async def test_cleanup(self, sample_spec: AgentSpec) -> None:
        """Test cleanup releases resources."""
        analyzer = MarkdownAgentAnalyzer(sample_spec)
        analyzer.llm_client = MagicMock()

        await analyzer.cleanup()

        assert analyzer.llm_client is None

    @pytest.mark.asyncio
    async def test_analyze_with_llm(self, sample_spec: AgentSpec) -> None:
        """Test analyze method with LLM."""
        analyzer = MarkdownAgentAnalyzer(sample_spec)

        # Mock LLM client
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '{"result": "analyzed"}'
        mock_client.complete.return_value = mock_response
        analyzer.llm_client = mock_client

        scene = {"text": "Test scene", "id": 1}
        result = await analyzer.analyze(scene)

        assert result["result"] == "analyzed"
        assert result["analyzer"] == "test-analyzer"
        assert result["version"] == "2.0.0"
        assert result["property"] == "test-analyzer"  # Property is same as name
        mock_client.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_without_llm(self) -> None:
        """Test analyze method without LLM requirement."""
        spec = AgentSpec(
            name="no-llm",
            description="No LLM",
            version="1.0.0",
            requires_llm=False,
            context_query="",
            output_schema={
                "type": "object",
                "properties": {"count": {"type": "number"}},
            },
            analysis_prompt="",
        )
        analyzer = MarkdownAgentAnalyzer(spec)

        scene = {"text": "Test scene"}
        result = await analyzer.analyze(scene)

        # Without LLM, should return empty result with metadata
        assert result["analyzer"] == "no-llm"
        assert result["version"] == "1.0.0"
        assert result["property"] == "no-llm"  # Property is same as name

    @pytest.mark.asyncio
    async def test_analyze_llm_not_initialized(self, sample_spec: AgentSpec) -> None:
        """Test analyze initializes LLM when required but not initialized."""
        analyzer = MarkdownAgentAnalyzer(sample_spec)

        with patch(
            "scriptrag.agents.markdown_agent_analyzer.get_default_llm_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = '{"result": "test"}'
            mock_client.complete.return_value = mock_response
            mock_get_client.return_value = mock_client

            scene = {"text": "Test scene"}
            result = await analyzer.analyze(scene)

            # Should have initialized the client
            mock_get_client.assert_called_once()
            assert result["result"] == "test"

    @pytest.mark.asyncio
    async def test_analyze_invalid_json_response(self, sample_spec: AgentSpec) -> None:
        """Test handling of invalid JSON response from LLM."""
        analyzer = MarkdownAgentAnalyzer(sample_spec)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "not valid json"
        mock_client.complete.return_value = mock_response
        analyzer.llm_client = mock_client

        scene = {"text": "Test scene"}
        result = await analyzer.analyze(scene)

        # Should return error result on invalid JSON
        assert "error" in result
        assert "Output validation failed" in result["error"]
        assert result["analyzer"] == "test-analyzer"
        assert result["version"] == "2.0.0"

    @pytest.mark.asyncio
    async def test_analyze_schema_validation_error(
        self, sample_spec: AgentSpec
    ) -> None:
        """Test schema validation of LLM response."""
        analyzer = MarkdownAgentAnalyzer(sample_spec)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        # Missing required "result" field
        mock_response.content = '{"wrong_field": "value"}'
        mock_client.complete.return_value = mock_response
        analyzer.llm_client = mock_client

        scene = {"text": "Test scene"}
        result = await analyzer.analyze(scene)

        # Should return error result on validation failure
        assert "error" in result
        assert "Output validation failed" in result["error"]
        assert result["analyzer"] == "test-analyzer"
        assert result["version"] == "2.0.0"

    @pytest.mark.asyncio
    async def test_analyze_prompt_formatting(self, sample_spec: AgentSpec) -> None:
        """Test that analysis prompt is properly formatted."""
        analyzer = MarkdownAgentAnalyzer(sample_spec)

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '{"result": "ok"}'
        mock_client.complete.return_value = mock_response
        analyzer.llm_client = mock_client

        scene = {"heading": "Test scene content", "id": 1}
        await analyzer.analyze(scene)

        # Check that the prompt was formatted with scene text
        call_args = mock_client.complete.call_args
        # The complete method is now called with a CompletionRequest object
        assert call_args.args
        request = call_args.args[0]
        assert hasattr(request, "messages")
        messages = request.messages
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        # The prompt should contain formatted scene content
        assert "SCENE HEADING: Test scene content" in messages[0]["content"]


class TestAgentLoader:
    """Tests for AgentLoader class."""

    @pytest.fixture
    def loader(self, temp_agent_dir: Path) -> AgentLoader:
        """Create an AgentLoader with temp directory."""
        return AgentLoader(agents_dir=temp_agent_dir)

    def test_init_default(self) -> None:
        """Test AgentLoader initialization with defaults."""
        loader = AgentLoader()
        assert loader.agents_dir.name == "builtin"
        assert loader._cache == {}
        assert loader._max_cache_size == 100
        assert loader._cache_order == []

    def test_init_custom_dir(self, temp_agent_dir: Path) -> None:
        """Test AgentLoader initialization with custom directory."""
        loader = AgentLoader(agents_dir=temp_agent_dir, max_cache_size=50)
        assert loader.agents_dir == temp_agent_dir
        assert loader._max_cache_size == 50

    def test_list_agents(
        self,
        loader: AgentLoader,
        temp_agent_dir: Path,
        sample_agent_markdown: str,
        sample_agent_markdown_no_llm: str,
    ) -> None:
        """Test agent listing in directory."""
        # Create some agent files
        (temp_agent_dir / "agent1.md").write_text(sample_agent_markdown)
        (temp_agent_dir / "agent2.md").write_text(sample_agent_markdown_no_llm)
        (temp_agent_dir / "not-an-agent.txt").write_text("Not markdown")
        (temp_agent_dir / "subdir").mkdir()
        (temp_agent_dir / "subdir" / "agent3.md").write_text(sample_agent_markdown)

        agents = loader.list_agents()

        # Should find only top-level .md files
        assert len(agents) == 2
        assert "agent1" in agents
        assert "agent2" in agents
        assert "not-an-agent" not in agents
        assert "agent3" not in agents

    def test_list_agents_no_dir(self, tmp_path: Path) -> None:
        """Test agent listing when directory doesn't exist."""
        loader = AgentLoader(agents_dir=tmp_path / "nonexistent")
        agents = loader.list_agents()
        assert agents == []

    def test_list_agents_invalid_names(
        self, temp_agent_dir: Path, sample_agent_markdown: str
    ) -> None:
        """Test that invalid agent names are filtered out."""
        loader = AgentLoader(agents_dir=temp_agent_dir)

        # Create agents with various names
        (temp_agent_dir / "valid-agent.md").write_text(sample_agent_markdown)
        (temp_agent_dir / "../evil.md").write_text(
            sample_agent_markdown
        )  # Invalid path traversal
        (temp_agent_dir / "bad$name.md").write_text(
            sample_agent_markdown
        )  # Invalid character

        agents = loader.list_agents()

        # Only valid-agent should be listed
        assert "valid-agent" in agents
        assert "../evil" not in agents
        assert "bad$name" not in agents

    def test_is_valid_agent_name(self) -> None:
        """Test agent name validation."""
        # Valid names
        assert AgentLoader._is_valid_agent_name("test-agent")
        assert AgentLoader._is_valid_agent_name("test_agent")
        assert AgentLoader._is_valid_agent_name("TestAgent123")

        # Invalid names
        assert not AgentLoader._is_valid_agent_name("../evil")
        assert not AgentLoader._is_valid_agent_name("bad$name")
        assert not AgentLoader._is_valid_agent_name("bad name")
        assert not AgentLoader._is_valid_agent_name("bad@name")
        assert not AgentLoader._is_valid_agent_name("a" * 101)  # Too long

    def test_load_agent_success(
        self,
        loader: AgentLoader,
        temp_agent_dir: Path,
        sample_agent_markdown: str,
    ) -> None:
        """Test successful agent loading."""
        (temp_agent_dir / "test-agent.md").write_text(sample_agent_markdown)

        analyzer = loader.load_agent("test-agent")

        assert isinstance(analyzer, MarkdownAgentAnalyzer)
        assert analyzer.name == "test-agent"
        assert "test-agent" in loader._cache
        assert "test-agent" in loader._cache_order

        # Loading again should return from cache and update LRU order
        analyzer2 = loader.load_agent("test-agent")
        # Note: Different analyzer instances, but same spec
        assert analyzer2.spec.name == analyzer.spec.name

    def test_load_agent_not_found(self, loader: AgentLoader) -> None:
        """Test loading non-existent agent."""
        with pytest.raises(ValueError, match="Agent 'missing' not found"):
            loader.load_agent("missing")

    def test_load_agent_invalid_spec(
        self,
        loader: AgentLoader,
        temp_agent_dir: Path,
        invalid_agent_markdown_no_frontmatter: str,
    ) -> None:
        """Test loading agent with invalid specification."""
        (temp_agent_dir / "bad-agent.md").write_text(
            invalid_agent_markdown_no_frontmatter
        )

        with pytest.raises(ValueError, match="No frontmatter found"):
            loader.load_agent("bad-agent")

    def test_lru_cache_eviction(
        self,
        temp_agent_dir: Path,
        sample_agent_markdown: str,
    ) -> None:
        """Test LRU cache eviction when cache is full."""
        # Create loader with small cache
        loader = AgentLoader(agents_dir=temp_agent_dir, max_cache_size=2)

        # Create three agent files
        for i in range(3):
            content = sample_agent_markdown.replace("test-agent", f"agent{i}")
            (temp_agent_dir / f"agent{i}.md").write_text(content)

        # Load first two agents
        loader.load_agent("agent0")
        loader.load_agent("agent1")
        assert len(loader._cache) == 2
        assert "agent0" in loader._cache
        assert "agent1" in loader._cache

        # Load third agent - should evict agent0
        loader.load_agent("agent2")
        assert len(loader._cache) == 2
        assert "agent0" not in loader._cache
        assert "agent1" in loader._cache
        assert "agent2" in loader._cache

        # Access agent1 to move it to end of LRU
        loader.load_agent("agent1")

        # Load agent0 again - should evict agent2
        loader.load_agent("agent0")
        assert len(loader._cache) == 2
        assert "agent2" not in loader._cache
        assert "agent1" in loader._cache
        assert "agent0" in loader._cache

    def test_list_agents_with_error(
        self,
        temp_agent_dir: Path,
        sample_agent_markdown: str,
    ) -> None:
        """Test that list_agents handles errors gracefully."""
        loader = AgentLoader(agents_dir=temp_agent_dir)

        # Create a valid agent file
        (temp_agent_dir / "good.md").write_text(sample_agent_markdown)

        # Create a file with invalid name that will be filtered out
        invalid_name = "bad$name.md"  # Contains invalid character
        (temp_agent_dir / invalid_name).write_text(sample_agent_markdown)

        agents = loader.list_agents()
        assert "good" in agents
        # The invalid name should be filtered out
        assert "bad$name" not in agents
