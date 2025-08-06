"""Tests for the Props Inventory Analyzer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from scriptrag.agents import AgentLoader, AgentSpec, MarkdownAgentAnalyzer
from scriptrag.analyzers.props_inventory import PropsInventoryAnalyzer


@pytest.fixture
def sample_scene():
    """Create a sample scene for testing."""
    return {
        "heading": "INT. COFFEE SHOP - DAY",
        "content": """INT. COFFEE SHOP - DAY

        SARAH (30s, exhausted) sits at a corner table, laptop open,
        coffee cup empty. She checks her phone - 3 missed calls.

        The BARISTA approaches with a fresh pot of coffee.

        BARISTA
        Another refill?

        SARAH
        (pushing her cup forward)
        Triple shot this time. And maybe
        bring the whole pot.

        She pulls out her wallet, finds only a crumpled receipt.

        SARAH (CONT'D)
        Can I pay with my credit card?

        The barista nods, pulls out a tablet with a card reader.
        """,
        "action": [
            "SARAH (30s, exhausted) sits at a corner table, laptop open,",
            "coffee cup empty. She checks her phone - 3 missed calls.",
            "The BARISTA approaches with a fresh pot of coffee.",
            "She pulls out her wallet, finds only a crumpled receipt.",
            "The barista nods, pulls out a tablet with a card reader.",
        ],
        "dialogue": [
            {"character": "BARISTA", "text": "Another refill?"},
            {
                "character": "SARAH",
                "text": "Triple shot this time. And maybe bring the whole pot.",
            },
            {"character": "SARAH", "text": "Can I pay with my credit card?"},
        ],
        "characters": ["SARAH", "BARISTA"],
    }


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response for props analysis."""
    return {
        "props": [
            {
                "name": "laptop",
                "category": "technology",
                "description": "Sarah's laptop, open on the table",
                "significance": "practical",
                "action_required": True,
                "quantity": 1,
                "mentions": ["action"],
            },
            {
                "name": "coffee cup",
                "category": "food_beverage",
                "description": "Empty coffee cup",
                "significance": "practical",
                "action_required": True,
                "quantity": 1,
                "mentions": ["action"],
            },
            {
                "name": "phone",
                "category": "technology",
                "description": "Sarah's phone showing missed calls",
                "significance": "plot_device",
                "action_required": True,
                "quantity": 1,
                "mentions": ["action"],
            },
            {
                "name": "coffee pot",
                "category": "food_beverage",
                "description": "Fresh pot of coffee",
                "significance": "practical",
                "action_required": True,
                "quantity": 1,
                "mentions": ["action"],
            },
            {
                "name": "wallet",
                "category": "personal_items",
                "description": "Sarah's wallet",
                "significance": "practical",
                "action_required": True,
                "quantity": 1,
                "mentions": ["action"],
            },
            {
                "name": "receipt",
                "category": "documents",
                "description": "Crumpled receipt in wallet",
                "significance": "background",
                "action_required": False,
                "quantity": 1,
                "mentions": ["action"],
            },
            {
                "name": "credit card",
                "category": "money_valuables",
                "description": "Sarah's credit card for payment",
                "significance": "practical",
                "action_required": True,
                "quantity": 1,
                "mentions": ["dialogue"],
            },
            {
                "name": "tablet",
                "category": "technology",
                "description": "Payment tablet with card reader",
                "significance": "practical",
                "action_required": True,
                "quantity": 1,
                "mentions": ["action"],
            },
            {
                "name": "card reader",
                "category": "technology",
                "description": "Attached to the tablet",
                "significance": "practical",
                "action_required": False,
                "quantity": 1,
                "mentions": ["action"],
            },
            {
                "name": "table",
                "category": "furniture",
                "description": "Corner table where Sarah sits",
                "significance": "background",
                "action_required": False,
                "quantity": 1,
                "mentions": ["action"],
            },
        ],
        "summary": {
            "total_props": 10,
            "hero_props": 0,
            "requires_action": 7,
            "categories": [
                "technology",
                "food_beverage",
                "personal_items",
                "documents",
                "money_valuables",
                "furniture",
            ],
        },
    }


class TestPropsInventoryAnalyzer:
    """Test the PropsInventoryAnalyzer class."""

    @pytest.mark.asyncio
    async def test_analyzer_properties(self):
        """Test basic analyzer properties."""
        analyzer = PropsInventoryAnalyzer()
        assert analyzer.name == "props_inventory"
        assert analyzer.version == "1.0.0"
        assert analyzer.requires_llm is True

    @pytest.mark.asyncio
    async def test_analyze_with_mock_llm(self, sample_scene, mock_llm_response):
        """Test analyze method with mocked LLM."""
        analyzer = PropsInventoryAnalyzer()

        # Mock the LLM client
        mock_llm_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps(mock_llm_response)
        mock_llm_client.complete = AsyncMock(return_value=mock_response)

        analyzer.llm_client = mock_llm_client

        # Run analysis
        result = await analyzer.analyze(sample_scene)

        # Check that LLM was called
        mock_llm_client.complete.assert_called_once()
        call_args = mock_llm_client.complete.call_args
        assert call_args[1]["temperature"] == 0.3
        assert "coffee cup" in call_args[1]["messages"][0]["content"]

        # Check result structure
        assert "props" in result
        assert "summary" in result
        assert result["analyzer"] == "props_inventory"
        assert result["version"] == "1.0.0"
        assert len(result["props"]) == 10
        assert result["summary"]["total_props"] == 10

    @pytest.mark.asyncio
    async def test_analyze_error_handling(self, sample_scene):
        """Test error handling in analyze method."""
        analyzer = PropsInventoryAnalyzer()

        # Mock LLM client to raise an error
        mock_llm_client = MagicMock()
        mock_llm_client.complete = AsyncMock(side_effect=Exception("LLM error"))
        analyzer.llm_client = mock_llm_client

        # Run analysis
        result = await analyzer.analyze(sample_scene)

        # Check error result
        assert result["props"] == []
        assert result["summary"]["total_props"] == 0
        assert "error" in result
        assert "LLM error" in result["error"]

    @pytest.mark.asyncio
    async def test_parse_llm_response_json_in_code_block(self):
        """Test parsing LLM response with JSON in code blocks."""
        analyzer = PropsInventoryAnalyzer()

        response = """Here's the analysis:

```json
{
    "props": [
        {"name": "gun", "category": "weapons", "significance": "hero"}
    ],
    "summary": {"total_props": 1, "hero_props": 1}
}
```"""

        result = analyzer._parse_llm_response(response)
        assert len(result["props"]) == 1
        assert result["props"][0]["name"] == "gun"

    @pytest.mark.asyncio
    async def test_parse_llm_response_malformed(self):
        """Test parsing malformed LLM response."""
        analyzer = PropsInventoryAnalyzer()

        # Response with missing fields
        response = '{"props": [{"name": "item"}]}'
        result = analyzer._parse_llm_response(response)

        # Check that defaults are filled in
        assert result["props"][0]["category"] == "miscellaneous"
        assert result["props"][0]["significance"] == "practical"
        assert result["props"][0]["action_required"] is False
        assert "summary" in result

    def test_build_scene_content(self, sample_scene):
        """Test building scene content for LLM prompt."""
        analyzer = PropsInventoryAnalyzer()
        content = analyzer._build_scene_content(sample_scene)

        assert "SCENE HEADING: INT. COFFEE SHOP - DAY" in content
        assert "ACTION:" in content
        assert "laptop open" in content
        assert "DIALOGUE:" in content
        assert "BARISTA: Another refill?" in content
        assert "SARAH: Triple shot" in content


class TestMarkdownAgentAnalyzer:
    """Test the MarkdownAgentAnalyzer class."""

    @pytest.fixture
    def agent_spec(self):
        """Create a test agent specification."""
        return AgentSpec(
            name="test_agent",
            property="test_property",
            description="Test agent",
            version="1.0",
            requires_llm=True,
            context_query="SELECT * FROM scenes",
            output_schema={
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "required": ["result"],
                "properties": {"result": {"type": "string"}},
                "additionalProperties": False,
            },
            analysis_prompt="Analyze: {{scene_content}}",
        )

    @pytest.mark.asyncio
    async def test_markdown_agent_properties(self, agent_spec):
        """Test markdown agent analyzer properties."""
        analyzer = MarkdownAgentAnalyzer(agent_spec)
        assert analyzer.name == "test_agent"
        assert analyzer.version == "1.0"
        assert analyzer.requires_llm is True

    @pytest.mark.asyncio
    async def test_markdown_agent_analyze(self, agent_spec, sample_scene):
        """Test markdown agent analyze method."""
        analyzer = MarkdownAgentAnalyzer(agent_spec)

        # Mock LLM client
        mock_llm_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"result": "test output"}'
        mock_llm_client.complete = AsyncMock(return_value=mock_response)
        analyzer.llm_client = mock_llm_client

        # Run analysis
        result = await analyzer.analyze(sample_scene)

        # Check result
        assert result["result"] == "test output"
        assert result["analyzer"] == "test_agent"
        assert result["version"] == "1.0"
        assert result["property"] == "test_property"

    @pytest.mark.asyncio
    async def test_markdown_agent_validation_error(self, agent_spec, sample_scene):
        """Test markdown agent with validation error."""
        analyzer = MarkdownAgentAnalyzer(agent_spec)

        # Mock LLM client with invalid response
        mock_llm_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"invalid": "field"}'
        mock_llm_client.complete = AsyncMock(return_value=mock_response)
        analyzer.llm_client = mock_llm_client

        # Run analysis
        result = await analyzer.analyze(sample_scene)

        # Check error result
        assert "error" in result
        assert "validation failed" in result["error"].lower()


class TestAgentLoader:
    """Test the AgentLoader class."""

    @pytest.fixture
    def temp_agent_dir(self, tmp_path):
        """Create a temporary directory with test agent files."""
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        # Create a test agent markdown file
        agent_file = agents_dir / "test_agent.md"
        agent_file.write_text(
            """---
name: test_agent
property: test_prop
description: Test agent
version: 1.0
---

# Test Agent

## Context Query

```sql
SELECT * FROM scenes
```

## Output Schema

```json
{
  "type": "object",
  "properties": {
    "result": {"type": "string"}
  }
}
```

## Analysis Prompt

Analyze this: {{scene_content}}
"""
        )

        return agents_dir

    def test_load_agent(self, temp_agent_dir):
        """Test loading an agent from markdown."""
        loader = AgentLoader(temp_agent_dir)
        analyzer = loader.load_agent("test_agent")

        assert analyzer.name == "test_agent"
        assert analyzer.spec.property == "test_prop"
        assert analyzer.spec.version == "1.0"

    def test_load_agent_not_found(self, temp_agent_dir):
        """Test loading non-existent agent."""
        loader = AgentLoader(temp_agent_dir)

        with pytest.raises(ValueError, match="not found"):
            loader.load_agent("nonexistent")

    def test_list_agents(self, temp_agent_dir):
        """Test listing available agents."""
        loader = AgentLoader(temp_agent_dir)
        agents = loader.list_agents()

        assert "test_agent" in agents
        assert len(agents) == 1

    def test_agent_spec_from_markdown_missing_section(self, tmp_path):
        """Test parsing markdown with missing required section."""
        agent_file = tmp_path / "incomplete.md"
        agent_file.write_text(
            """---
name: incomplete
property: prop
description: Incomplete agent
version: 1.0
---

# Incomplete Agent

## Context Query

SELECT * FROM scenes
"""
        )

        with pytest.raises(ValueError, match="Missing 'Output Schema' section"):
            AgentSpec.from_markdown(agent_file)

    def test_agent_spec_parse_sections(self):
        """Test parsing markdown sections."""
        content = """## Section One

Some content here

## Section Two

```
code block content
```

## Section Three

More content
"""
        sections = AgentSpec._parse_sections(content)

        assert "Section One" in sections
        assert sections["Section One"] == "Some content here"
        assert "Section Two" in sections
        assert "code block content" in sections["Section Two"]
        assert "Section Three" in sections
        assert sections["Section Three"] == "More content"
