# Claude Code Hooks for ScriptRAG

This directory contains Claude Code hooks that automatically format code and
maintain code quality when files are modified through Claude's tools.

## Configuration

The hooks are configured in `.claude/config.json` and trigger after:

- `Write` tool usage
- `Edit` tool usage  
- `MultiEdit` tool usage

## Available Scripts

### `auto-format.sh`

Comprehensive auto-formatting script that handles:

- **Python files**: Black formatting + Ruff linting/formatting
- **Markdown files**: markdownlint auto-fix
- **JSON files**: Python JSON.tool formatting
- **YAML files**: yamllint validation
- **All files**: Trailing whitespace removal (preserves Markdown line breaks) + newline fixes

### `format-python.sh`

Lightweight Python-only formatting script that:

- Runs Black formatter on Python files
- Applies Ruff formatting and auto-fixes
- Faster execution for Python-only changes

## How It Works

1. **File Detection**: Scripts detect modified files from git status
2. **Virtual Environment**: Automatically activates `.venv` if available
3. **Tool Selection**: Uses project's existing tools (Black, Ruff, etc.)
4. **Safe Execution**: Continues on errors, provides helpful feedback
5. **Git Integration**: Can optionally re-stage formatted files

## Requirements

The hooks expect these tools to be available (installed via `make setup-dev`):

- `black` - Python code formatter
- `ruff` - Python linter and formatter
- `markdownlint` - Markdown linter (optional)
- `yamllint` - YAML linter (optional)

## Testing Hooks

To test the hooks manually:

```bash
# Test the full auto-format script
./.claude/hooks/auto-format.sh

# Test Python-only formatting
./.claude/hooks/format-python.sh path/to/file.py

# Test with environment variables
CLAUDE_PROJECT_DIR=/path/to/project ./.claude/hooks/auto-format.sh
```

## Customization

### Adding New File Types

Edit `auto-format.sh` to add support for new file types:

```bash
# Add support for TypeScript files
TYPESCRIPT_FILES=$(echo "$MODIFIED_FILES" | grep -E '\.(ts|tsx)$' || true)

if [ -n "$TYPESCRIPT_FILES" ]; then
    echo "📘 Formatting TypeScript files..."
    # Add prettier or other TypeScript formatter
fi
```

### Modifying Python Formatting

The Python formatting can be customized by modifying the commands in the
scripts. Current configuration matches `pyproject.toml` settings.

### Hook Triggers

Modify `.claude/config.json` to change when hooks trigger:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",  // Only trigger on Write tool
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/format-python.sh"
          }
        ]
      }
    ]
  }
}
```

## Troubleshooting

### Hook Not Running

- Verify `.claude/config.json` syntax
- Check script permissions: `chmod +x .claude/hooks/*.sh`
- Ensure `CLAUDE_PROJECT_DIR` environment variable is set

### Formatting Errors

- Check that formatting tools are installed: `make setup-dev`
- Verify virtual environment: `source .venv/bin/activate`
- Run hooks manually to see detailed error messages

### Performance Issues

- Use `format-python.sh` for Python-only changes
- Consider disabling specific formatters in the scripts
- Add file filters to reduce processing time

## Integration with Pre-commit

These hooks complement the existing pre-commit hooks in `.pre-commit-config.yaml`.

- **Claude hooks**: Run automatically during development
- **Pre-commit hooks**: Run before commits for validation

Both use the same tools (Black, Ruff, etc.) to ensure consistency.
