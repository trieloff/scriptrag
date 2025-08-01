# Example Insight Agent: Emotional Beats

This is an example of an Insight Agent that analyzes emotional progression in scenes.

```yaml
---
name: emotional_beats
property: emotional_beats
description: Identifies emotional turning points and character reactions
---
```

## Context Query

```sql
SELECT
    json_extract(scene_data, '$.content.dialogue') as dialogue,
    json_extract(scene_data, '$.content.action') as action,
    json_extract(scene_data, '$.extracted.characters') as characters
FROM scenes
WHERE content_hash = :scene_hash
```

## Output Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "beats": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "character": {"type": "string"},
          "emotion_before": {"type": "string"},
          "emotion_after": {"type": "string"},
          "trigger": {"type": "string"},
          "intensity": {"type": "number", "minimum": 1, "maximum": 10}
        },
        "required": ["character", "emotion_before", "emotion_after", "trigger"]
      }
    },
    "scene_arc": {
      "type": "string",
      "enum": ["rising", "falling", "flat", "volatile"]
    }
  },
  "required": ["beats", "scene_arc"]
}
```

## Analysis Prompt

Analyze the emotional progression in this scene. Focus on:

1. Character emotional states at the beginning
2. What triggers emotional changes
3. The intensity of emotional shifts
4. The overall emotional arc of the scene

For each character present, identify their emotional journey through the scene. Consider both explicit emotional cues (tears, laughter, anger) and implicit ones (word choice, action changes, silence).

Pay special attention to:

- Moments where characters' emotions contradict their words
- Emotional turning points that drive the scene forward
- The relationship between character emotions and scene momentum
- How emotions build or dissipate throughout the scene

Return a structured analysis that captures both individual character arcs and the overall emotional trajectory of the scene.
