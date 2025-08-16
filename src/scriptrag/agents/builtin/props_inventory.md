---
description: Track props mentioned in scenes - first appearances and previously seen
version: 2.0
requires_llm: true
---

# Props Inventory Analysis

## Context Query

```sql
-- Get all props from previous scenes
SELECT DISTINCT
    s.scene_number,
    json_extract(s.metadata, '$.boneyard.analyzers.props_inventory.result.props_mentioned') as props_list
FROM scenes s
WHERE s.script_id = :script_id
    AND s.scene_number < :scene_number
    AND json_extract(s.metadata, '$.boneyard.analyzers.props_inventory.result.props_mentioned') IS NOT NULL
ORDER BY s.scene_number;
```

## Output Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["props_mentioned", "props_first_appearance", "props_previously_seen"],
  "properties": {
    "props_mentioned": {
      "type": "array",
      "description": "All props mentioned in this scene",
      "items": {
        "type": "string"
      }
    },
    "props_first_appearance": {
      "type": "array",
      "description": "Props that appear for the first time in this scene",
      "items": {
        "type": "string"
      }
    },
    "props_previously_seen": {
      "type": "array",
      "description": "Props in this scene that have appeared in previous scenes",
      "items": {
        "type": "string"
      }
    }
  }
}
```

## Analysis Prompt

You are a script supervisor tracking props in a screenplay. Your task is to identify all props mentioned in the current scene and determine which are new versus previously seen.

### Scene Content

```fountain
{{scene_content}}
```

### Context: Props from Previous Scenes

The following props have been mentioned in previous scenes:
{{context_query_results}}

### Instructions

1. **IDENTIFY ALL PROPS IN THIS SCENE**
   - Objects explicitly mentioned in action lines
   - Props referenced in dialogue
   - Items characters interact with

2. **CLASSIFY EACH PROP**
   - Compare against the list of props from previous scenes
   - Determine if this is the first appearance or if it was previously mentioned
   - Use consistent naming (e.g., if "John's phone" was mentioned before, use that exact name)

3. **BE COMPREHENSIVE BUT CONCISE**
   - Include all significant props
   - Use clear, simple names (e.g., "phone", "gun", "coffee cup")
   - Avoid overly specific descriptions unless necessary for continuity

### Output Format

Return a JSON object with three arrays:

- `props_mentioned`: All props in this scene
- `props_first_appearance`: Props appearing for the first time
- `props_previously_seen`: Props that have appeared before

Keep prop names consistent across scenes for accurate tracking.
