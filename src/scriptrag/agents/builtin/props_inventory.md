---
description: Extract and categorize all props mentioned or implied in screenplay scenes
version: 1.0
requires_llm: true
---

# Props Inventory Analysis

## Context Query

```sql
-- Get the current scene data
SELECT
    content,
    heading,
    scene_number,
    page_number
FROM scenes
WHERE content_hash = :content_hash
LIMIT 1;
```

## Output Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["props", "summary"],
  "properties": {
    "props": {
      "type": "array",
      "description": "List of all props identified in the scene",
      "items": {
        "type": "object",
        "required": ["name", "category", "significance"],
        "properties": {
          "name": {
            "type": "string",
            "description": "The name of the prop"
          },
          "category": {
            "type": "string",
            "description": "Category of the prop",
            "enum": [
              "weapons",
              "vehicles",
              "technology",
              "documents",
              "food_beverage",
              "clothing_accessories",
              "furniture",
              "tools_equipment",
              "personal_items",
              "money_valuables",
              "medical",
              "miscellaneous"
            ]
          },
          "description": {
            "type": "string",
            "description": "Brief description of the prop if provided in the script"
          },
          "significance": {
            "type": "string",
            "description": "Story significance of the prop",
            "enum": ["hero", "plot_device", "character_defining", "practical", "background"]
          },
          "action_required": {
            "type": "boolean",
            "description": "Whether the prop requires specific action or manipulation"
          },
          "quantity": {
            "type": "integer",
            "description": "Number of this prop needed",
            "minimum": 1,
            "default": 1
          },
          "mentions": {
            "type": "array",
            "description": "Where the prop is mentioned in the scene",
            "items": {
              "type": "string",
              "enum": ["action", "dialogue", "implied"]
            }
          }
        }
      }
    },
    "summary": {
      "type": "object",
      "description": "Summary statistics for the scene",
      "required": ["total_props", "hero_props", "requires_action"],
      "properties": {
        "total_props": {
          "type": "integer",
          "description": "Total number of unique props identified"
        },
        "hero_props": {
          "type": "integer",
          "description": "Number of hero/featured props"
        },
        "requires_action": {
          "type": "integer",
          "description": "Number of props requiring actor manipulation"
        },
        "categories": {
          "type": "array",
          "description": "List of categories present in scene",
          "items": {
            "type": "string"
          }
        }
      }
    }
  }
}
```

## Analysis Prompt

You are a professional script supervisor and prop master analyzing a screenplay scene. Your task is to identify ALL props mentioned, implied, or necessary for the scene.

### Scene Content

```fountain
{{scene_content}}
```

### Instructions

1. **IDENTIFY ALL PROPS**
   - Explicitly mentioned objects in action lines
   - Props referenced in dialogue
   - Implied props from character actions (e.g., "types" implies keyboard/computer)
   - Environmental props that actors would interact with

2. **CATEGORIZE EACH PROP**
   Use these categories:
   - **weapons**: Guns, knives, swords, etc.
   - **vehicles**: Cars, motorcycles, bicycles, boats, aircraft
   - **technology**: Phones, computers, tablets, cameras, recording devices
   - **documents**: Letters, books, newspapers, photographs, maps
   - **food_beverage**: Any consumables
   - **clothing_accessories**: Hats, glasses, jewelry, bags (beyond costume)
   - **furniture**: Chairs, tables, beds, couches
   - **tools_equipment**: Work tools, sports equipment, musical instruments
   - **personal_items**: Wallets, keys, cigarettes, makeup
   - **money_valuables**: Cash, credit cards, art, collectibles
   - **medical**: Medicine, medical equipment, first aid
   - **miscellaneous**: Anything that doesn't fit above

3. **ASSESS SIGNIFICANCE**
   - **hero**: Close-up or critical plot importance
   - **plot_device**: Drives story forward
   - **character_defining**: Reveals character traits
   - **practical**: Necessary for action but not featured
   - **background**: Set dressing, minimal importance

4. **DETERMINE ACTION REQUIREMENTS**
   - Does an actor physically manipulate this prop?
   - Is it thrown, broken, or transformed?
   - Does it require special handling or effects?

5. **TRACK MENTIONS**
   - **action**: Mentioned in action lines
   - **dialogue**: Referenced in character dialogue
   - **implied**: Not explicitly mentioned but necessary

### Special Considerations

- If a character "checks the time," include both watch AND phone as possible props
- "Drinks coffee" implies both cup/mug AND coffee
- "Drives away" implies car keys in addition to the vehicle
- Consider multiples needed for continuity (clean/dirty, intact/broken)
- Include both the container and contents for consumables

### Output Format

Return a JSON object matching the schema with:

- Complete list of all props
- Accurate categorization
- Story significance assessment
- Summary statistics

Be thorough but avoid duplicates. If unsure about a category, choose the most specific one that applies.
