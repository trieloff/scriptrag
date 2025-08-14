# Claude Code Hooks Configuration

This document describes the Claude Code hooks setup for the ScriptRAG project,
which automatically applies formatting fixes after file edits to maintain code
quality and consistency.

## Overview

Claude Code hooks are configured to run automatically after Write, Edit, and
MultiEdit operations to apply formatting fixes that our linting tools support.
This reduces the need for manual corrections and ensures consistent code style.

## Configuration Files

### Main Configuration: `.claude/config.json`

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/auto-format.sh",
            "type": "command"
          }
        ],
        "matcher": "Write|Edit|MultiEdit"
      }
    ],
    "SessionStart": [
      {
        "command": "cd $CLAUDE_PROJECT_DIR && make install",
        "type": "command"
      }
    ]
  }
}
```

### Python-Only Configuration: `.claude/config-python-only.json`

A lighter configuration focusing only on Python formatting for faster execution:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/format-python.sh",
            "type": "command"
          }
        ],
        "matcher": "Write|Edit|MultiEdit"
      }
    ]
  }
}
```

## Hook Scripts

### `auto-format.sh` - Comprehensive Auto-Formatting

This is the main formatting hook that handles multiple file types and applies
all available auto-fixes:

#### Python Files (.py)

- **Ruff Format**: Applies consistent code formatting (line length, quotes, etc.)
- **Ruff Check --fix --unsafe-fixes**: Fixes import sorting, removes unused
  imports, fixes common issues, and applies more aggressive fixes
- **Fallback**: Uses `uv run` if ruff is not in PATH

#### Markdown Files (.md)

- **markdownlint --fix**: Fixes common markdown issues like heading levels,
  list formatting, trailing spaces (preserves double-space line breaks)

#### JSON Files (.json)

- **Python json.tool**: Pretty-prints JSON with 2-space indentation

#### YAML Files (.yml, .yaml)

- **yamllint**: Validates YAML syntax (no auto-fix available)

#### SQL Files (.sql)

- **SQLFluff fix**: Formats SQL with SQLite dialect

#### All Files

- **Trailing whitespace removal**: Removes trailing spaces (preserves markdown
  double-space line breaks)
- **End-of-file newline**: Ensures files end with a newline

### `format-python.sh` - Fast Python-Only Formatting

A lightweight script that focuses only on Python files for faster execution
during rapid development:

- Detects the most recently modified Python file
- Applies Ruff format and fix
- Minimal overhead for quick iterations

## Available Auto-Fixes from Linting Tools

Based on the `.pre-commit-config.yaml` configuration, these tools provide
auto-fixes that the hooks apply:

### Ruff (Python)

- Import sorting and organization
- Unused import removal
- Line length formatting
- Quote style consistency
- Whitespace and indentation fixes
- Many Python style and logic fixes (100+ rules)

### markdownlint

- Heading hierarchy fixes
- List formatting consistency
- Line length (with exceptions for code blocks)
- Blank line consistency
- Trailing space management

### SQLFluff

- SQL keyword capitalization
- Indentation and alignment
- Join formatting
- Comma positioning

### Generic Pre-commit Fixes

- Trailing whitespace removal
- End-of-file fixer
- Mixed line ending conversion (LF)
- JSON pretty-printing
- Byte order marker removal

## Usage

The hooks run automatically after Claude Code edits files. No manual
intervention is required. The hooks will:

1. Detect which files were modified
2. Apply appropriate formatters based on file type
3. Re-stage formatted files if they were already staged
4. Report any formatting issues that couldn't be auto-fixed

## Switching Configurations

To use the Python-only configuration for faster execution:

```bash
cp .claude/config-python-only.json .claude/config.json
```

To restore the comprehensive configuration:

```bash
git checkout .claude/config.json
```

## Troubleshooting

If hooks fail to run:

1. Ensure virtual environment is activated
2. Check that formatters are installed: `make setup-dev`
3. Verify hook scripts are executable: `chmod +x .claude/hooks/*.sh`
4. Check hook output for specific error messages

## Benefits

- **Consistent Code Style**: Automatically maintains project standards
- **Reduced Manual Work**: No need to manually run formatters
- **Immediate Feedback**: Issues are fixed as code is written
- **CI/CD Alignment**: Uses same tools as pre-commit hooks
- **Performance**: Optimized to only format changed files

## Future Improvements

Potential enhancements to consider:

1. Add support for more file types (TOML, INI, etc.)
2. Implement parallel formatting for multiple files
3. Add configuration option to disable specific formatters
4. Create a dry-run mode for testing
5. Add metrics/logging for formatting operations
