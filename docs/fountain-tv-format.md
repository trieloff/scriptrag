# ScriptRAG TV Script Format Requirements

> **⚠️ Important Note**: This guide describes **ScriptRAG-specific requirements** for TV scripts. The `Episode:` and `Season:` fields described here are **NOT part of the official Fountain specification** but are custom extensions used by ScriptRAG for better TV series organization.

This guide explains how to format Fountain files for TV scripts to ensure ScriptRAG correctly extracts episode and season metadata.

## Official Fountain vs ScriptRAG Extensions

### Official Fountain Title Page Fields

The [official Fountain specification](https://fountain.io/syntax#section-titlepage) defines these standard title page fields:

- **Title**: The title of the screenplay
- **Credit**: (e.g., "Written by")
- **Author** (or Authors): The writer's name(s)
- **Source**: Based on what existing work, if any
- **Draft date**: Date of the current draft
- **Contact**: Contact information

### ScriptRAG-Specific Extensions (Non-Standard)

ScriptRAG adds these **custom fields** specifically for TV series organization:

- **Episode**: Episode number (e.g., `Episode: 1`)
- **Season**: Season number (e.g., `Season: 1`)

These fields are **NOT recognized by standard Fountain parsers** and are unique to ScriptRAG. They enable better organization and tracking of TV series scripts within the ScriptRAG system.

## Why ScriptRAG Uses These Extensions

ScriptRAG uses Episode and Season fields to:

1. **Uniquely identify TV episodes** in a series
2. **Track character arcs** across episodes and seasons
3. **Analyze pacing and structure** within a series context
4. **Enable filtering and searching** by season/episode

While these fields won't affect how your script renders in other Fountain tools, they provide essential metadata for ScriptRAG's analysis features.

## Required Format for ScriptRAG\n\n### Example with ScriptRAG Extensions

```fountain
Title: Show Name - Episode Title
Credit: Written by
Author: Jane Smith
Draft date: 2024-01-15
Episode: 1
Season: 1
```

### Key Requirements for TV Scripts in ScriptRAG

1. **Episode Number**: Must be specified as a separate `Episode:` field (ScriptRAG extension)
2. **Season Number**: Must be specified as a separate `Season:` field (ScriptRAG extension)
3. **Title**: Should contain the show name and episode title (standard Fountain field)

## Examples

### Single Episode

```fountain
Title: Mystery Detective - The Pilot
Credit: Written by
Author: John Doe
Draft date: 2024-03-01
Episode: 1
Season: 1
Contact:
    John Doe
    john@example.com
```

### Multi-Episode Series

For a series with multiple episodes, each script file should have its own unique episode and season metadata:

**Episode 1:**

```fountain
Title: Mystery Detective - The Case Begins
Episode: 1
Season: 1
Author: John Doe
```

**Episode 2:**

```fountain
Title: Mystery Detective - Following Leads
Episode: 2
Season: 1
Author: John Doe
```

### Anthology Series

For anthology series where each episode has different characters and stories:

```fountain
Title: Twilight Tales - The Mirror
Episode: 5
Season: 2
Author: Sarah Johnson
Draft date: 2024-06-15
```

## Common Mistakes to Avoid

### ❌ Incorrect: Episode in Title Only

```fountain
Title:
    _**Mystery Detective**_
    Episode 1: "The Pilot"
Author: John Doe
```

This format will NOT extract the episode number. ScriptRAG will show "-" in the Season/Episode columns.

### ❌ Incorrect: Missing Metadata Fields

```fountain
Title: Mystery Detective S01E01
Author: John Doe
```

Without explicit `Episode:` and `Season:` fields, the metadata won't be extracted.

### ✅ Correct: Explicit Fields

```fountain
Title: Mystery Detective - The Pilot
Episode: 1
Season: 1
Author: John Doe
```

## Indexing TV Series

When indexing multiple episodes of a TV series:

```bash
# Index all episodes in a directory
scriptrag index /path/to/tv-series/*.fountain

# The table will correctly show:
# Title                           | Author   | Season | Episode
# Mystery Detective - The Pilot   | John Doe | 1      | 1
# Mystery Detective - Following.. | John Doe | 1      | 2
```

## Database Uniqueness

ScriptRAG uses the combination of `title`, `author`, `episode`, and `season` to uniquely identify scripts. This means:

- You can have multiple episodes with the same title if they have different episode numbers
- Different versions of the same episode should use different draft dates or version notes in the title
- Re-indexing the same file will update the existing entry rather than creating a duplicate

## Integration with Analysis

When properly formatted, ScriptRAG's analysis features work seamlessly with TV scripts:

- Character analysis tracks recurring characters across episodes
- Scene analysis can compare pacing between episodes
- Search functions can filter by season or episode

## Migration from Standard Fountain

If you have existing Fountain files in the standard format, you can update them by:

1. Adding explicit `Episode:` and `Season:` fields to the title page
2. Keeping the episode title in the main `Title:` field for clarity
3. Re-indexing the updated files

## Script Portability Considerations

### Exporting Scripts

When exporting scripts from ScriptRAG for use in other Fountain tools:

- The `Episode:` and `Season:` fields will be preserved in the title page
- Most Fountain parsers will simply ignore these unknown fields
- The script will render normally in other tools
- No script content or formatting is affected

### Importing Scripts

When importing standard Fountain scripts into ScriptRAG:

- Scripts without Episode/Season fields will work fine
- The Season/Episode columns will show "-" in the index
- You can add these fields manually if needed for TV series organization
- All standard Fountain formatting is fully supported

## Additional Resources

- [Official Fountain Format Specification](https://fountain.io/syntax)
- [Fountain Title Page Documentation](https://fountain.io/syntax#section-titlepage)
- [ScriptRAG Usage Guide](usage.md)
- [Troubleshooting Guide](troubleshooting.md)
