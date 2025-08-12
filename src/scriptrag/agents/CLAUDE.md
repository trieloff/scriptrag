# Insight Agents System

This directory contains the Insight Agents system for extensible content extraction. Agents are declarative markdown files that specify what information to extract from scenes.

## Architecture Role

Insight Agents are **configuration components** that:

- Store extraction logic as markdown files
- Provide prompts and schemas to the Analyze API
- Enable domain experts to contribute without coding
- Support both built-in and custom agents

## Agent Structure

Each agent is a markdown file with:

1. **YAML Frontmatter**: Metadata (name, property, description)
2. **Context Query**: SQL to gather scene context
3. **Output Schema**: JSON Schema for validation
4. **Analysis Prompt**: Instructions for the LLM

## Directory Organization

```text
agents/
├── builtin/          # Built-in agents shipped with ScriptRAG
│   ├── characters.md
│   ├── emotions.md
│   ├── themes.md
│   └── story_function.md
├── custom/           # User-defined agents (in Git repo)
└── __init__.py       # Agent loading utilities
```

## Agent File Format

````markdown
---
name: emotional_beats
property: emotional_progression
description: Analyze the emotional journey within a scene
version: 1.0
---

# Emotional Beats Analysis

## Context Query

```sql
SELECT
    s2.scene_data
FROM scenes s1
JOIN scenes s2 ON s1.script_path = s2.script_path
WHERE s1.content_hash = :content_hash
AND s2.scene_number BETWEEN s1.scene_number - 2 AND s1.scene_number + 2
ORDER BY s2.scene_number
```

## Output Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "emotional_beats": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "timestamp": {"type": "string"},
          "emotion": {"type": "string"},
          "intensity": {"type": "number", "minimum": 0, "maximum": 1},
          "character": {"type": "string"}
        },
        "required": ["emotion", "intensity"]
      }
    },
    "overall_arc": {
      "type": "string",
      "enum": ["rising", "falling", "stable", "volatile"]
    }
  },
  "required": ["emotional_beats", "overall_arc"]
}
```

## Analysis Prompt

Analyze the emotional progression in this scene. Consider:

1. The starting emotional state
2. Key turning points
3. The ending emotional state
4. Character emotional journeys

Context scenes (before/after):
{context}

Current scene:
{scene}

Provide a detailed emotional beat analysis following the schema.
````

## Agent Loading

```python
from pathlib import Path
import yaml
import json
from typing import Dict, Any, List

class InsightAgent:
    """Represents a loaded insight agent."""

    def __init__(self, path: Path):
        self.path = path
        self._load()

    def _load(self):
        """Load agent from markdown file."""
        content = self.path.read_text()

        # Parse frontmatter
        if content.startswith('---'):
            _, frontmatter, body = content.split('---', 2)
            self.metadata = yaml.safe_load(frontmatter)
        else:
            raise ValueError("Agent missing frontmatter")

        # Parse sections
        self._parse_body(body)

    def _parse_body(self, body: str):
        """Parse agent body sections."""
        sections = {}
        current_section = None
        current_content = []

        for line in body.split('\n'):
            if line.startswith('## '):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = line[3:].strip()
                current_content = []
            elif current_section:
                current_content.append(line)

        if current_section:
            sections[current_section] = '\n'.join(current_content)

        # Extract components
        self.context_query = self._extract_code_block(
            sections.get('Context Query', '')
        )
        self.output_schema = json.loads(
            self._extract_code_block(
                sections.get('Output Schema', '{}')
            )
        )
        self.prompt_template = sections.get('Analysis Prompt', '').strip()
```

## Built-in Agents

### Characters Agent

Extracts character presence, actions, and relationships.

### Emotions Agent

Identifies emotional tones and character emotional states.

### Themes Agent

Extracts thematic elements and symbolic content.

### Story Function Agent

Determines the scene's role in the narrative (setup, conflict, resolution, etc.).

## Custom Agent Guidelines

1. **Focus on One Aspect**: Each agent should extract one type of information
2. **Use Context Wisely**: Only query necessary context to avoid token limits
3. **Schema Precision**: Define exact output structure for consistency
4. **Clear Prompts**: Provide specific instructions to the LLM
5. **Version Control**: Update version when changing schema

## Agent Validation

```python
def validate_agent(agent: InsightAgent) -> List[str]:
    """Validate agent configuration."""
    errors = []

    # Check metadata
    required_fields = ['name', 'property', 'description']
    for field in required_fields:
        if field not in agent.metadata:
            errors.append(f"Missing required field: {field}")

    # Validate SQL
    try:
        # Check for parameter placeholder
        if ':content_hash' not in agent.context_query:
            errors.append("Context query must include :content_hash parameter")
    except Exception as e:
        errors.append(f"Invalid SQL: {e}")

    # Validate JSON schema
    try:
        # Basic schema validation
        if '$schema' not in agent.output_schema:
            errors.append("Output schema missing $schema field")
    except Exception as e:
        errors.append(f"Invalid JSON schema: {e}")

    return errors
```

## Performance Considerations

1. **Context Size**: Limit context queries to avoid token limits
2. **Schema Complexity**: Balance detail with LLM capabilities
3. **Caching**: Cache agent definitions after loading
4. **Parallel Execution**: Agents can run independently

## Testing Agents

Each agent should have test cases:

```python
def test_agent(agent: InsightAgent, test_scene: Scene):
    """Test agent execution."""
    # Mock context
    context = [{"scene_data": {...}}]

    # Build prompt
    prompt = agent.build_prompt(test_scene, context)

    # Mock LLM response
    response = {
        "emotional_beats": [...],
        "overall_arc": "rising"
    }

    # Validate against schema
    assert agent.validate_output(response)
```
