# Bulk Import Guide

ScriptRAG provides powerful bulk import functionality for importing multiple Fountain
screenplay files at once, with automatic TV series detection and organization.

## Overview

The bulk import feature is designed to handle large collections of screenplay files,
automatically detecting TV series patterns and organizing them into proper hierarchical
structures (Series → Seasons → Episodes).

## Basic Usage

```bash
# Import all fountain files from a directory
uv run scriptrag script import ./screenplays/

# Import using glob patterns
uv run scriptrag script import "**/*.fountain"

# Import with preview (dry run)
uv run scriptrag script import ./scripts/ --dry-run
```

## TV Series Detection

ScriptRAG automatically detects TV series information from filenames using various common patterns:

### Supported Filename Patterns

1. **Underscore Format**: `ShowName_S01E01_EpisodeTitle.fountain`
2. **X Format**: `ShowName - 1x01 - Episode Title.fountain`
3. **Dotted Format**: `ShowName.101.EpisodeTitle.fountain`
4. **Episode Number Format**: `ShowName - Episode 101 - Title.fountain`
5. **Simple Format**: `ShowName S01E01.fountain`
6. **Directory-based**: `Season 1/Episode 01 - Title.fountain`

### Special Episodes

The system also recognizes special episodes:

- `ShowName - Special - Title.fountain`
- Multi-part episodes: `Episode Title Part 1.fountain`

## Advanced Options

### Custom Pattern Matching

If your files use a non-standard naming convention, you can provide a custom regex pattern:

```bash
# Custom pattern with named groups
uv run scriptrag script import "*.fountain" \
    --pattern "(?P<series>.+?)_Season(?P<season>\d+)_Ep(?P<episode>\d+)"
```

The pattern should include named groups:

- `series`: The series name
- `season`: Season number
- `episode`: Episode number
- `title`: Episode title (optional)

### Series Name Override

Force all imported files to belong to a specific series:

```bash
uv run scriptrag script import "episodes/*.fountain" \
    --series-name "Breaking Bad"
```

### Import Behavior Control

```bash
uv run scriptrag script import "*.fountain" \
    --skip-existing \        # Skip files already in database (default: true)
    --update-existing \      # Update if file is newer
    --batch-size 20 \       # Files per transaction batch (default: 10)
    --recursive             # Search directories recursively (default: true)
```

## Examples

### Example 1: Import Complete TV Series

Directory structure:

```text
Breaking Bad/
├── Season 1/
│   ├── Breaking Bad - 1x01 - Pilot.fountain
│   ├── Breaking Bad - 1x02 - Cat's in the Bag.fountain
│   └── ...
├── Season 2/
│   ├── Breaking Bad - 2x01 - Seven Thirty-Seven.fountain
│   └── ...
```

Command:

```bash
uv run scriptrag script import "Breaking Bad/**/*.fountain"
```

### Example 2: Import with Preview

First, preview what would be imported:

```bash
uv run scriptrag script import "./TV Shows/" --dry-run
```

Output shows:

- Series structure that would be created
- Number of seasons and episodes
- Any files that couldn't be parsed

### Example 3: Custom Naming Convention

For files named like `MyShow_Season01_Episode01_Title.fountain`:

```bash
uv run scriptrag script import "MyShow*.fountain" \
    --pattern "(?P<series>.+?)_Season(?P<season>\d+)_Episode(?P<episode>\d+)_(?P<title>.+)"
```

### Example 4: Import Specific Season

```bash
uv run scriptrag script import "Season 3/*.fountain" \
    --series-name "The Wire"
```

## Directory Structure Best Practices

For best results, organize your files like this:

```text
Series Name/
├── Season 1/
│   ├── Episode 01 - Title.fountain
│   ├── Episode 02 - Title.fountain
│   └── ...
├── Season 2/
│   └── ...
└── Specials/
    └── Special - Title.fountain
```

Or use consistent filename patterns:

```text
ShowName_S01E01_Pilot.fountain
ShowName_S01E02_SecondEpisode.fountain
```

## Limits and Performance

- Maximum files per import: 1,000 (configurable)
- Default batch size: 10 files per transaction
- Progress tracking for large imports
- Automatic rollback on errors

## Error Handling

The bulk importer provides detailed error reporting:

```bash
Import Results:
Total files: 50
Successful imports: 47
Failed imports: 2
Skipped files: 1

Import Errors:
  • file1.fountain: Failed to parse fountain file
  • file2.fountain: Invalid season number
```

## Integration with ScriptRAG

After bulk import, all imported scripts are:

- Fully integrated into the graph database
- Searchable through all ScriptRAG commands
- Connected with proper series/season/episode relationships
- Ready for knowledge graph enrichment

Use the search commands to explore imported content:

```bash
# List all imported series
uv run scriptrag search all --type series

# Find specific episodes
uv run scriptrag search scenes --series "Breaking Bad" --season 1
```
