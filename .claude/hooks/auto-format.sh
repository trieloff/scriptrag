#!/bin/bash
# Auto-formatting hook for ScriptRAG project
# This script runs after Write/Edit/MultiEdit tools to ensure consistent formatting

set -e

# Get the project root directory
PROJECT_DIR="$CLAUDE_PROJECT_DIR"
cd "$PROJECT_DIR"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Not in a git repository, skipping auto-format"
    exit 0
fi

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "🔧 Activated virtual environment"
else
    echo "⚠️  Virtual environment not found, using system Python"
fi

# Get list of modified files
MODIFIED_FILES=$(git diff --name-only --cached 2>/dev/null || git diff --name-only HEAD~1 2>/dev/null || echo "")

if [ -z "$MODIFIED_FILES" ]; then
    # If no staged files, check unstaged files
    MODIFIED_FILES=$(git diff --name-only 2>/dev/null || echo "")
fi

if [ -z "$MODIFIED_FILES" ]; then
    echo "No modified files detected, skipping auto-format"
    exit 0
fi

echo "🎨 Auto-formatting modified files..."
echo "Modified files: $MODIFIED_FILES"

# Filter for Python files
PYTHON_FILES=$(echo "$MODIFIED_FILES" | grep -E '\.(py)$' || true)

# Filter for other supported files
MARKDOWN_FILES=$(echo "$MODIFIED_FILES" | grep -E '\.(md)$' || true)
YAML_FILES=$(echo "$MODIFIED_FILES" | grep -E '\.(ya?ml)$' || true)
JSON_FILES=$(echo "$MODIFIED_FILES" | grep -E '\.(json)$' || true)

# Format Python files
if [ -n "$PYTHON_FILES" ]; then
    echo "🐍 Formatting Python files..."

    # Check if files exist (they might have been deleted)
    EXISTING_PYTHON_FILES=""
    for file in $PYTHON_FILES; do
        if [ -f "$file" ]; then
            EXISTING_PYTHON_FILES="$EXISTING_PYTHON_FILES $file"
        fi
    done

    if [ -n "$EXISTING_PYTHON_FILES" ]; then
        # Run Black formatter
        if command -v black >/dev/null 2>&1; then
            echo "  Running Black..."
            black $EXISTING_PYTHON_FILES || echo "  ⚠️  Black formatting failed"
        fi

        # Run Ruff formatter and fixer
        if command -v ruff >/dev/null 2>&1; then
            echo "  Running Ruff..."
            ruff format $EXISTING_PYTHON_FILES || echo "  ⚠️  Ruff formatting failed"
            ruff check --fix $EXISTING_PYTHON_FILES || echo "  ⚠️  Ruff fixing failed"
        fi

        echo "  ✅ Python files formatted"
    fi
fi

# Format Markdown files
if [ -n "$MARKDOWN_FILES" ]; then
    echo "📝 Formatting Markdown files..."

    EXISTING_MARKDOWN_FILES=""
    for file in $MARKDOWN_FILES; do
        if [ -f "$file" ]; then
            EXISTING_MARKDOWN_FILES="$EXISTING_MARKDOWN_FILES $file"
        fi
    done

    if [ -n "$EXISTING_MARKDOWN_FILES" ]; then
        # Run markdownlint with auto-fix
        if command -v markdownlint >/dev/null 2>&1; then
            echo "  Running markdownlint..."
            markdownlint --fix --config .markdownlint.yaml $EXISTING_MARKDOWN_FILES || echo "  ⚠️  Markdownlint formatting failed"
        fi

        echo "  ✅ Markdown files formatted"
    fi
fi

# Format JSON files
if [ -n "$JSON_FILES" ]; then
    echo "📄 Formatting JSON files..."

    EXISTING_JSON_FILES=""
    for file in $JSON_FILES; do
        if [ -f "$file" ]; then
            EXISTING_JSON_FILES="$EXISTING_JSON_FILES $file"
        fi
    done

    if [ -n "$EXISTING_JSON_FILES" ]; then
        # Use Python to format JSON files
        for file in $EXISTING_JSON_FILES; do
            if command -v python >/dev/null 2>&1; then
                echo "  Formatting $file..."
                python -m json.tool "$file" > "${file}.tmp" && mv "${file}.tmp" "$file" || echo "  ⚠️  JSON formatting failed for $file"
            fi
        done

        echo "  ✅ JSON files formatted"
    fi
fi

# Format YAML files
if [ -n "$YAML_FILES" ]; then
    echo "📋 Checking YAML files..."

    EXISTING_YAML_FILES=""
    for file in $YAML_FILES; do
        if [ -f "$file" ]; then
            EXISTING_YAML_FILES="$EXISTING_YAML_FILES $file"
        fi
    done

    if [ -n "$EXISTING_YAML_FILES" ]; then
        # Run yamllint (check only, no auto-fix available)
        if command -v yamllint >/dev/null 2>&1; then
            echo "  Running yamllint..."
            yamllint -c .yamllint.yaml $EXISTING_YAML_FILES || echo "  ⚠️  YAML linting failed"
        fi

        echo "  ✅ YAML files checked"
    fi
fi

# Run trailing whitespace fixes and other generic fixes
echo "🧹 Running generic file fixes..."

# Fix trailing whitespace
for file in $MODIFIED_FILES; do
    if [ -f "$file" ]; then
        # Remove trailing whitespace
        sed -i 's/[[:space:]]*$//' "$file" 2>/dev/null || true

        # Ensure file ends with newline
        if [ -s "$file" ] && [ "$(tail -c1 "$file" | wc -l)" -eq 0 ]; then
            echo "" >> "$file"
        fi
    fi
done

echo "✅ Auto-formatting complete!"

# Optional: Stage the formatted files if they were already staged
if git diff --cached --quiet 2>/dev/null; then
    # No staged changes, don't auto-stage
    echo "💡 Files formatted but not staged. Use 'git add' to stage changes."
else
    # There were staged changes, re-stage the formatted files
    echo "📦 Re-staging formatted files..."
    for file in $MODIFIED_FILES; do
        if [ -f "$file" ]; then
            git add "$file" 2>/dev/null || true
        fi
    done
fi

exit 0
