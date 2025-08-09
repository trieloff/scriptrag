"""Tests for AgentSpec class."""

import pytest

from scriptrag.agents.agent_spec import AgentSpec


class TestAgentSpec:
    """Tests for AgentSpec class."""

    def test_init(self):
        """Test AgentSpec initialization."""
        spec = AgentSpec(
            name="test_agent",
            description="Test agent description",
            version="1.0.0",
            requires_llm=True,
            context_query="SELECT * FROM scenes",
            output_schema={"type": "object"},
            analysis_prompt="Analyze this",
        )

        assert spec.name == "test_agent"
        assert spec.description == "Test agent description"
        assert spec.version == "1.0.0"
        assert spec.requires_llm is True
        assert spec.context_query == "SELECT * FROM scenes"
        assert spec.output_schema == {"type": "object"}
        assert spec.analysis_prompt == "Analyze this"

    def test_from_markdown_valid(self, tmp_path):
        """Test loading a valid agent specification from markdown."""
        # Create a test markdown file
        agent_file = tmp_path / "test_agent.md"
        content = """---
description: Test agent for analysis
version: 1.0.0
requires_llm: true
---

# Test Agent

This is a test agent.

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

Analyze the scene and provide results.
"""
        agent_file.write_text(content)

        # Load the spec
        spec = AgentSpec.from_markdown(agent_file)

        assert spec.name == "test_agent"
        assert spec.description == "Test agent for analysis"
        assert spec.version == "1.0.0"
        assert spec.requires_llm is True
        assert "SELECT * FROM scenes WHERE id = ?" in spec.context_query
        assert spec.output_schema["type"] == "object"
        assert "result" in spec.output_schema["properties"]
        assert "Analyze the scene" in spec.analysis_prompt

    def test_from_markdown_no_llm_required(self, tmp_path):
        """Test loading an agent that doesn't require LLM."""
        agent_file = tmp_path / "simple_agent.md"
        content = """---
description: Simple agent
version: 2.0.0
requires_llm: false
---

# Simple Agent

```json
{"type": "object"}
```
"""
        agent_file.write_text(content)

        spec = AgentSpec.from_markdown(agent_file)

        assert spec.name == "simple_agent"
        assert spec.requires_llm is False
        assert spec.context_query == ""  # No SQL block
        assert spec.output_schema == {"type": "object"}

    def test_from_markdown_file_not_found(self, tmp_path):
        """Test error when markdown file doesn't exist."""
        non_existent = tmp_path / "missing.md"

        with pytest.raises(ValueError, match="Agent specification not found"):
            AgentSpec.from_markdown(non_existent)

    def test_from_markdown_no_frontmatter(self, tmp_path):
        """Test error when markdown has no frontmatter."""
        agent_file = tmp_path / "no_frontmatter.md"
        content = """# Agent without frontmatter

```json
{"type": "object"}
```
"""
        agent_file.write_text(content)

        with pytest.raises(ValueError, match="No frontmatter found"):
            AgentSpec.from_markdown(agent_file)

    def test_from_markdown_missing_required_fields(self, tmp_path):
        """Test error when required fields are missing."""
        agent_file = tmp_path / "incomplete.md"

        # Missing version
        content = """---
description: Incomplete agent
---

```json
{"type": "object"}
```
"""
        agent_file.write_text(content)

        with pytest.raises(ValueError, match="Missing required field 'version'"):
            AgentSpec.from_markdown(agent_file)

        # Missing description
        content = """---
version: 1.0.0
---

```json
{"type": "object"}
```
"""
        agent_file.write_text(content)

        with pytest.raises(ValueError, match="Missing required field 'description'"):
            AgentSpec.from_markdown(agent_file)

    def test_from_markdown_no_json_schema(self, tmp_path):
        """Test error when no valid JSON schema is found."""
        agent_file = tmp_path / "no_schema.md"
        content = """---
description: Agent without schema
version: 1.0.0
---

# Agent

No JSON code blocks here.

```python
# This is Python, not JSON
print("hello")
```
"""
        agent_file.write_text(content)

        with pytest.raises(ValueError, match="No valid JSON schema found"):
            AgentSpec.from_markdown(agent_file)

    def test_from_markdown_invalid_json(self, tmp_path):
        """Test handling of invalid JSON in code blocks."""
        agent_file = tmp_path / "invalid_json.md"
        content = """---
description: Agent with invalid JSON
version: 1.0.0
---

# Agent

```json
{invalid json content}
```

```json
{"valid": "json", "type": "object"}
```
"""
        agent_file.write_text(content)

        # Should skip the invalid JSON and use the valid one
        spec = AgentSpec.from_markdown(agent_file)
        assert spec.output_schema == {"valid": "json", "type": "object"}

    def test_from_markdown_multiple_code_blocks(self, tmp_path):
        """Test handling multiple code blocks of same type."""
        agent_file = tmp_path / "multi_block.md"
        content = """---
description: Agent with multiple blocks
version: 1.0.0
---

# Agent

```sql
SELECT * FROM scenes
```

```sql
SELECT * FROM characters
```

```json
{"type": "object", "first": true}
```

```json
{"type": "object", "second": true}
```
"""
        agent_file.write_text(content)

        spec = AgentSpec.from_markdown(agent_file)

        # Should use the first SQL block
        assert "SELECT * FROM scenes" in spec.context_query
        assert "SELECT * FROM characters" not in spec.context_query

        # Should use the first valid JSON block
        assert spec.output_schema.get("first") is True
        assert spec.output_schema.get("second") is None

    def test_from_markdown_version_as_number(self, tmp_path):
        """Test that numeric version is converted to string."""
        agent_file = tmp_path / "numeric_version.md"
        content = """---
description: Agent with numeric version
version: 1.5
---

```json
{"type": "object"}
```
"""
        agent_file.write_text(content)

        spec = AgentSpec.from_markdown(agent_file)
        assert spec.version == "1.5"
        assert isinstance(spec.version, str)

    def test_from_markdown_default_requires_llm(self, tmp_path):
        """Test that requires_llm defaults to True if not specified."""
        agent_file = tmp_path / "default_llm.md"
        content = """---
description: Agent without requires_llm
version: 1.0.0
---

```json
{"type": "object"}
```
"""
        agent_file.write_text(content)

        spec = AgentSpec.from_markdown(agent_file)
        assert spec.requires_llm is True

    def test_extract_code_blocks_various_languages(self):
        """Test extraction of code blocks with various languages."""
        content = """
Some text

```python
print("hello")
```

More text

```sql
SELECT * FROM table
```

```json
{"key": "value"}
```

```
No language specified
```

Final text
"""
        blocks = AgentSpec._extract_code_blocks(content)

        assert len(blocks) == 4
        assert blocks[0] == {"lang": "python", "content": 'print("hello")'}
        assert blocks[1] == {"lang": "sql", "content": "SELECT * FROM table"}
        assert blocks[2] == {"lang": "json", "content": '{"key": "value"}'}
        assert blocks[3] == {"lang": "", "content": "No language specified"}

    def test_extract_code_blocks_empty_content(self):
        """Test extraction with no code blocks."""
        content = "Just plain text with no code blocks"
        blocks = AgentSpec._extract_code_blocks(content)
        assert blocks == []

    def test_extract_code_blocks_nested_backticks(self):
        """Test extraction with nested backticks."""
        content = """
````markdown
```python
print("nested")
```
````

```json
{"not": "nested"}
```
"""
        blocks = AgentSpec._extract_code_blocks(content)

        # Should handle the nesting correctly
        assert len(blocks) >= 1
        # The last block should be the JSON
        json_blocks = [b for b in blocks if b["lang"] == "json"]
        assert len(json_blocks) == 1
        assert json_blocks[0]["content"] == '{"not": "nested"}'

    def test_from_markdown_complex_analysis_prompt(self, tmp_path):
        """Test that the full content becomes the analysis prompt."""
        agent_file = tmp_path / "complex_prompt.md"
        content = """---
description: Complex agent
version: 1.0.0
---

# Complex Analysis Agent

This agent performs complex analysis.

## Instructions

1. First, examine the scene
2. Then, apply the following logic:
   - Check for patterns
   - Identify themes

## Context

```sql
SELECT * FROM scenes
```

## Expected Output

```json
{
  "type": "object",
  "properties": {
    "analysis": {"type": "string"},
    "confidence": {"type": "number"}
  }
}
```

## Analysis Template

Analyze the scene {{scene_content}} and provide:
- Detailed analysis
- Confidence score

Remember to be thorough!
"""
        agent_file.write_text(content)

        spec = AgentSpec.from_markdown(agent_file)

        # The entire content (minus frontmatter) should be the prompt
        assert "# Complex Analysis Agent" in spec.analysis_prompt
        assert "This agent performs complex analysis" in spec.analysis_prompt
        assert "{{scene_content}}" in spec.analysis_prompt
        assert "Remember to be thorough!" in spec.analysis_prompt

        # But also check that we extracted the blocks correctly
        assert spec.context_query == "SELECT * FROM scenes"
        assert spec.output_schema["properties"]["analysis"]["type"] == "string"
