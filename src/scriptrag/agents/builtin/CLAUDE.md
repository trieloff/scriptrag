# Built-in Insight Agents

This directory contains the built-in insight agents that ship with ScriptRAG. These agents provide core extraction capabilities for screenplay analysis.

## Built-in Agents

### characters.md

Extracts character presence, speaking roles, and character interactions from scenes.

### emotions.md

Identifies emotional tones, character emotional states, and emotional transitions.

### themes.md

Extracts thematic elements, motifs, and symbolic content.

### story_function.md

Determines each scene's narrative function (setup, conflict, climax, resolution, etc.).

### props.md

Identifies important props and objects that appear in scenes.

### locations.md

Enriches location data with atmosphere, time of day implications, and spatial relationships.

### dialogue_style.md

Analyzes dialogue patterns, speech characteristics, and conversation dynamics.

### visual_elements.md

Extracts visual motifs, cinematographic implications, and scenic descriptions.

## Design Principles

1. **Domain Expertise**: Each agent embodies screenplay analysis best practices
2. **Composability**: Agents work independently and can be combined
3. **Stability**: Built-in agents maintain backward compatibility
4. **Documentation**: Each agent includes clear examples and use cases

## Agent Template

Built-in agents follow this template:

```markdown
---
name: agent_name
property: output_property
description: One-line description
version: 1.0
stability: stable
---

# Agent Name

## Purpose

Detailed explanation of what this agent extracts and why it's useful for screenplay analysis.

## Context Query

```sql
-- Minimal context needed for analysis
SELECT scene_data FROM scenes WHERE content_hash = :content_hash
```

## Output Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    // Schema definition
  }
}
```

## Analysis Prompt

[Detailed prompt for LLM]

## Examples

### Input Scene

[Example scene text]

### Expected Output

[Example JSON output]

## Use Cases

- Use case 1
- Use case 2

``` <!-- End of agent template example -->

## Quality Standards

All built-in agents must:
1. Have comprehensive test coverage
2. Include example inputs and outputs
3. Follow consistent naming conventions
4. Provide clear, focused extraction
5. Handle edge cases gracefully

## Versioning

Built-in agents use semantic versioning:
- **1.0**: Initial stable release
- **1.1**: Backward-compatible improvements
- **2.0**: Breaking changes to schema

## Testing

Each built-in agent has corresponding tests in `tests/agents/`:
- Schema validation tests
- Example scene processing
- Edge case handling
- Performance benchmarks
