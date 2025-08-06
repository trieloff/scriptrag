# Fountain Parser Component

This directory contains the Fountain screenplay format parser, which extracts structured data from .Fountain files including scenes, dialogue, and boneyard metadata.

## Architecture Role

The Fountain Parser is a **processing component** that:

- Receives Fountain text from the Git Synchronizer
- Extracts structured scene data
- Calculates content hashes for deduplication
- Parses boneyard JSON metadata

## Key Responsibilities

1. **Parse Fountain Syntax**
   - Scene headings (INT/EXT)
   - Character names and dialogue
   - Action lines
   - Transitions
   - Title page metadata

2. **Extract Boneyard Metadata**
   - Locate `/* SCRIPTRAG-META-START ... SCRIPTRAG-META-END */` blocks
   - Parse embedded JSON
   - Validate against schema

3. **Calculate Content Hashes**
   - Generate stable hashes for scene content
   - Enable change detection
   - Support deduplication


## Fountain Format Knowledge

### Scene Headings

```fountain
INT. COFFEE SHOP - DAY

EXT. PARKING LOT - NIGHT
```

### Character and Dialogue

```fountain
SARAH
(nervously)
I need to tell you something.

JOHN
What is it?
```

### Action Lines

```fountain
The shop buzzes with morning energy. Sarah enters, exhausted.
```

### Boneyard Metadata

```fountain
/* SCRIPTRAG-META-START
{
    "content_hash": "a3f5c9b8d7e2f1a4",  // pragma: allowlist secret
    "extracted": {
        "characters": ["SARAH", "JOHN"],
        "emotional_tone": "tense",
        "themes": ["revelation", "secrets"]
    },
    "embeddings": {
        "scene": "embeddings/a3f5c9b8d7e2f1a4.npy"
    }
}
SCRIPTRAG-META-END */
```

## Parser Rules

1. **Scene Detection**
   - Must start with INT. or EXT.
   - Can include location and time
   - Ends at next scene heading or EOF

2. **Dialogue Parsing**
   - Character name in CAPS
   - Optional parenthetical
   - Dialogue lines follow

3. **Boneyard Preservation**
   - Never modify existing boneyard
   - Parse but don't validate JSON (that's the extractor's job)

## Error Handling

```python
class FountainParseError(ParsingError):
    """Specific Fountain parsing error."""

    def __init__(self, message: str, line_number: Optional[int] = None):
        self.line_number = line_number
        super().__init__(
            f"Parse error at line {line_number}: {message}"
            if line_number else message
        )
```

## Performance Considerations

1. **Streaming Parse**: For large scripts, parse scene by scene
2. **Hash Caching**: Cache computed hashes during session
3. **Regex Compilation**: Pre-compile all regex patterns
4. **Memory Efficiency**: Don't hold entire script in memory

## Testing

Key test cases:

- Valid Fountain files with all elements
- Invalid syntax handling
- Boneyard metadata extraction
- Hash stability (same content = same hash)
- Edge cases (empty scenes, special characters)

## Integration Points

- **Input from**: Git Synchronizer
- **Output to**: Content Extractor
- **Reads from**: Fountain Files

## Fountain Specification

Full specification: <https://fountain.io/syntax>

Key elements we support:

- Scene Headings
- Action
- Character
- Dialogue
- Parenthetical
- Transition
- Title Page
- Boneyard comments
