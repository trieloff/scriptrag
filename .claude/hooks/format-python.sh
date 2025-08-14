#!/bin/bash
# Quick Python formatting script for ScriptRAG project
# Focuses only on Python files for faster execution

set -e

PROJECT_DIR="$CLAUDE_PROJECT_DIR"
cd "$PROJECT_DIR"

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Get the file that was just modified (passed as argument or detect from git)
if [ $# -gt 0 ]; then
    TARGET_FILE="$1"
else
    # Try to detect the most recently modified Python file
    TARGET_FILE=$(find src/ tests/ -name "*.py" -type f -exec stat -c '%Y %n' {} \; 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2- || echo "")
fi

if [ -z "$TARGET_FILE" ] || [ ! -f "$TARGET_FILE" ]; then
    echo "No Python file to format"
    exit 0
fi

# Only process Python files
if [[ "$TARGET_FILE" =~ \.py$ ]]; then
    echo "🐍 Formatting Python file: $TARGET_FILE"

    # Run Ruff formatter and fixer (includes import sorting and many fixes)
    if command -v ruff >/dev/null 2>&1; then
        ruff format "$TARGET_FILE" 2>/dev/null || true
        ruff check --fix --unsafe-fixes "$TARGET_FILE" 2>/dev/null || true
    elif command -v uv >/dev/null 2>&1; then
        # Fallback to uv if ruff not in PATH
        uv run ruff format "$TARGET_FILE" 2>/dev/null || true
        uv run ruff check --fix --unsafe-fixes "$TARGET_FILE" 2>/dev/null || true
    fi

    echo "✅ Python file formatted: $TARGET_FILE"
else
    echo "Skipping non-Python file: $TARGET_FILE"
fi

exit 0
