# ScriptRAG Troubleshooting Guide

This comprehensive guide helps diagnose and fix common issues with ScriptRAG.

## Table of Contents

1. [Common Error Messages](#common-error-messages)
2. [Database Configuration Issues](#database-configuration-issues)
3. [LLM Setup and Connection](#llm-setup-and-connection)
4. [Character Extraction Issues](#character-extraction-issues)
5. [TV Series Organization](#tv-series-organization)
6. [File Format Issues](#file-format-issues)
7. [Performance Issues](#performance-issues)
8. [Debugging Tips](#debugging-tips)
9. [Getting Help](#getting-help)
10. [Known Limitations](#known-limitations)

## Common Error Messages

### "Invalid database path detected"

**Cause**: Database not found at expected location

**Solution**:

```bash
# Initialize the database first
scriptrag init

# Check if database exists at default location
ls ~/.scriptrag/scriptrag.db

# Or use a config file to specify custom path
scriptrag --config config.yaml index script.fountain
```

### "UNIQUE constraint failed: scripts.title, scripts.author"

**Cause**: Attempting to index duplicate scripts

**Solution**:

- For TV series, add episode/season metadata (see [TV Format Guide](fountain-tv-format.md))
- Use unique titles for different versions
- Delete existing script before re-indexing:

  ```bash
  scriptrag delete "Script Title"
  scriptrag index script.fountain
  ```

### "Command timed out"

**Cause**: LLM provider not responding

**Solution**:

```bash
# Check if LLM provider is running
curl http://localhost:1234/v1/models  # For LMStudio

# Verify API endpoint is correct
export OPENAI_API_BASE=http://localhost:1234/v1

# Check network connectivity
ping localhost
```

### "Failed to parse Fountain file"

**Cause**: Malformed Fountain syntax

**Solution**:

- Verify proper title page format
- Check for unclosed formatting marks
- Ensure character names are in ALL CAPS
- Validate UTF-8 encoding

## Database Configuration Issues

### Commands Don't Respect Database Path

**Problem**: Most commands don't support the `--config` option for specifying database paths and other settings (Issue #241). Additionally, commands like `index` lack a `--db-path` option (Issue #243).

**Workaround**:

1. Use the default database location: `~/.scriptrag/scriptrag.db`
2. Or set environment variable:

   ```bash
   export SCRIPTRAG_DATABASE_PATH=/custom/path/scriptrag.db
   ```

**Affected Commands**:

- `scriptrag search` (path validation bug was fixed in #240)
- `scriptrag query`
- `scriptrag index` (lacks `--db-path` option)
- Most other commands (no `--config` support)

**Related Issues**: See #240 (search/query path validation bug - now fixed), #241 (config file support), #243 (index command database path)

## LLM Setup and Connection

### LMStudio Setup

```bash
# 1. Start LMStudio and load a model

# 2. Check if LMStudio is running
curl http://localhost:1234/v1/models

# 3. Configure ScriptRAG
export OPENAI_API_BASE=http://localhost:1234/v1
export OPENAI_API_KEY=not-needed  # LMStudio doesn't require a key

# 4. Test connection
scriptrag analyze --analyzer scene_embeddings test.fountain
```

### GitHub Models Setup

```bash
# 1. Get your GitHub token from https://github.com/settings/tokens
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxx

# 2. Test connection
scriptrag analyze --analyzer scene_embeddings test.fountain

# 3. If issues persist, check rate limits
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/rate_limit
```

### OpenAI Setup

```bash
# Set your OpenAI API key
export OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx

# Test connection
scriptrag analyze --analyzer scene_embeddings test.fountain
```

## Character Extraction Issues

### Characters Not Being Detected

**Requirements for proper character extraction:**

1. **Character names must be in ALL CAPS**

   ```fountain
   JOHN
   This is dialogue.
   ```

2. **No spaces before character name**

   ```fountain
   ✅ JOHN
   ❌  JOHN (with leading space)
   ```

3. **Must be followed by dialogue**

   ```fountain
   JOHN
   (beat)
   I need to tell you something.
   ```

4. **Parentheticals on separate line**

   ```fountain
   ✅ JOHN
      (whispering)
      Be quiet.

   ❌ JOHN (whispering)
      Be quiet.
   ```

### Debugging Character Extraction

```bash
# View extracted characters
scriptrag query "SELECT DISTINCT character_name FROM dialogue"

# Check character relationships
scriptrag characters "Script Title"
```

## TV Series Organization

### Best Practices for TV Scripts

See the dedicated [Fountain TV Format Guide](fountain-tv-format.md) for detailed information.

**Quick Reference:**

```fountain
Title: Show Name - Episode Title
Episode: 1
Season: 1
Author: Your Name
```

### Organizing Multiple Episodes

```text
tv-series/
├── season-1/
│   ├── s01e01-pilot.fountain
│   ├── s01e02-the-case.fountain
│   └── s01e03-revelation.fountain
└── season-2/
    ├── s02e01-return.fountain
    └── s02e02-conflict.fountain
```

Index all at once:

```bash
scriptrag index tv-series/**/*.fountain
```

## File Format Issues

### Fountain File Not Recognized

**Check these common issues:**

1. **File extension**: Must be `.fountain` (not `.txt` or `.fdx`)
2. **Encoding**: Must be UTF-8

   ```bash
   # Check encoding
   file -i script.fountain

   # Convert to UTF-8 if needed
   iconv -f ISO-8859-1 -t UTF-8 script.fountain > script-utf8.fountain
   ```

3. **Remove BOM markers**:

   ```bash
   # Remove BOM if present
   sed -i '1s/^\xEF\xBB\xBF//' script.fountain
   ```

### Validation Script

```python
#!/usr/bin/env python3
# validate-fountain.py
import sys
from pathlib import Path

def validate_fountain(filepath):
    path = Path(filepath)

    # Check extension
    if not path.suffix == '.fountain':
        print(f"Error: File must have .fountain extension, got {path.suffix}")
        return False

    # Check if file exists
    if not path.exists():
        print(f"Error: File {filepath} does not exist")
        return False

    # Check encoding
    try:
        with open(path, 'r', encoding='utf-8') as f:
            f.read()
        print("File appears valid")
        return True
    except UnicodeDecodeError:
        print("Error: File must be UTF-8 encoded")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate-fountain.py <file.fountain>")
        sys.exit(1)

    if not validate_fountain(sys.argv[1]):
        sys.exit(1)
```

## Performance Issues

### Slow Indexing

**Solutions:**

1. **Reduce batch size**:

   ```bash
   scriptrag index --batch-size 5 *.fountain
   ```

2. **Disable LLM analyzers for speed**:

   ```bash
   scriptrag index --no-llm *.fountain
   ```

3. **Check disk space**:

   ```bash
   df -h
   # Ensure at least 1GB free space
   ```

### Memory Issues

**Solutions:**

1. **Process fewer files at once**:

   ```bash
   # Instead of
   scriptrag index *.fountain

   # Use
   for file in *.fountain; do
       scriptrag index "$file"
   done
   ```

2. **Increase Python memory limit**:

   ```bash
   export PYTHONMALLOC=malloc
   ulimit -v unlimited
   ```

### Slow Queries

**Optimize database**:

```bash
# Vacuum and analyze database
sqlite3 ~/.scriptrag/scriptrag.db "VACUUM; ANALYZE;"

# Check database size
du -h ~/.scriptrag/scriptrag.db
```

## Debugging Tips

### Enable Debug Logging

Create a `config.yaml`:

```yaml
logging:
  level: DEBUG
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

Use with:

```bash
scriptrag --config config.yaml index script.fountain
```

### Check Version Compatibility

```bash
# Python version (requires 3.11+)
python --version

# SQLite version (requires 3.38+)
sqlite3 --version

# uv version
uv --version

# ScriptRAG version
scriptrag --version
```

### Validate Installation

```bash
# Run built-in tests
make test

# Check all dependencies
uv pip list | grep -E "(pydantic|typer|rich|sqlite)"

# Verify database schema
sqlite3 ~/.scriptrag/scriptrag.db ".schema"
```

### Check Configuration

```bash
# Show current configuration
scriptrag config

# Validate config file
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

## Getting Help

### Before Reporting an Issue

1. **Check existing issues**: <https://github.com/trieloff/scriptrag/issues>
2. **Search closed issues** for similar problems
3. **Read the documentation** thoroughly

### Information to Include in Bug Reports

```markdown
## Environment
- OS: [e.g., macOS 14.2, Windows 11, Ubuntu 22.04]
- Python version: [output of `python --version`]
- ScriptRAG version: [output of `scriptrag --version`]
- Installation method: [pip, uv, from source]

## Steps to Reproduce
1. [First step]
2. [Second step]
3. [...]

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## Error Messages
```

[Full error output]

```text

## Sample Files
[Attach or link to sample Fountain file if relevant]

## Configuration
[Contents of config.yaml if used]
```

### Community Support

- GitHub Discussions: <https://github.com/trieloff/scriptrag/discussions>
- Issues: <https://github.com/trieloff/scriptrag/issues>

## Known Limitations

### Current Limitations

1. **Config Option Support**: Some commands don't support `--config` option
   - Workaround: Use environment variables or default paths

2. **Character Extraction**: May not work for all screenplay formats
   - Solution: Ensure proper Fountain formatting

3. **Database Path**: Must be absolute path, not relative
   - Example: `/home/user/scriptrag.db` not `./scriptrag.db`

4. **LLM Rate Limits**: Some providers have strict rate limits
   - Solution: Use `--batch-size` to control request rate

### Platform-Specific Issues

**Windows:**

- Path separators: Use forward slashes or raw strings
- Long path names: Enable long path support in Windows

**macOS:**

- Permissions: May need to grant terminal full disk access
- Quarantine: Remove quarantine attribute from downloaded files

**Linux:**

- SELinux: May need to adjust contexts for database access
- Permissions: Ensure user has write access to database directory

## Quick Fixes Reference

| Problem | Quick Fix |
|---------|-----------|
| Database not found | `scriptrag init` |
| Duplicate script error | Add episode/season metadata |
| LLM timeout | Check provider is running |
| Characters not found | Ensure ALL CAPS names |
| Slow performance | Reduce batch size |
| Memory error | Process fewer files |
| Config not working | Use environment variables |
| Parse error | Check Fountain syntax |

## Additional Resources

- [Installation Guide](installation.md)
- [Usage Guide](usage.md)
- [Configuration Guide](configuration.md)
- [Fountain TV Format Guide](fountain-tv-format.md)
- [API Reference](api-reference.md)
- [Development Guide](development.md)
