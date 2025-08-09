---
allowed-tools: Bash(*), Task(*), Glob(*), Grep(*), Read(*), Edit(*), MultiEdit(*), Write(*)
description: Achieve 99% test coverage for changed files through automated test generation
---

# Test Coverage Command

## Context

- Current git status: !`git status --porcelain`
- Current branch: !`git branch --show-current`
- Repository: !`git remote get-url origin`
- Changed files: !`git diff --name-only main...HEAD | grep '\.py$' | grep -v __pycache__ | grep -v test_ | head -10`

## Your task

Systematically achieve 99% test coverage for all Python files changed in the current branch through automated test generation and iteration.

### Phase 1: Identify and analyze changed files

```bash
# Get repository and branch context
REPO="$(git remote get-url origin | sed -E 's|.*github\.com[:/]([^/]+/[^/]+)(\.git)?$|\1|' | sed 's/\.git$//')"
BRANCH="$(git branch --show-current)"

echo "📊 Test Coverage Automation"
echo "=========================="
echo "Repository: $REPO"
echo "Branch: $BRANCH"
echo ""

# Identify Python files changed in current branch (excluding tests)
echo "🔍 Identifying changed Python files..."
CHANGED_FILES=$(git diff --name-only main...HEAD | grep '\.py$' | grep -v __pycache__ | grep -v '^tests/' | grep -v '_test\.py$' | grep -v 'test_.*\.py$')

if [ -z "$CHANGED_FILES" ]; then
    echo "✅ No Python source files changed in this branch"
    exit 0
fi

echo "📝 Files to analyze:"
echo "$CHANGED_FILES" | nl
TOTAL_FILES=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')
echo ""
echo "Total files: $TOTAL_FILES"
```

### Phase 2: Measure baseline coverage

```bash
echo ""
echo "📏 Measuring baseline coverage..."

# Run coverage for all tests
pytest --cov=src/scriptrag --cov-report=term-missing --cov-report=json --tb=short -q || true

# Parse coverage JSON for changed files
if [ -f coverage.json ]; then
    echo ""
    echo "📊 Current coverage for changed files:"
    for file in $CHANGED_FILES; do
        # Convert file path to coverage key format
        COV_KEY=$(echo "$file" | sed 's|/|.|g' | sed 's|\.py$||')
        COVERAGE=$(python -c "
import json
data = json.load(open('coverage.json'))
files = data.get('files', {})
for key in files:
    if '$file' in key:
        pct = files[key]['summary']['percent_covered']
        missing = files[key]['summary']['num_statements'] - files[key]['summary']['num_executed_statements']
        print(f'{pct:.1f}% (missing: {missing} lines)')
        break
else:
    print('0.0% (no tests found)')
" 2>/dev/null || echo "Unable to parse")
        printf "  %-60s %s\n" "$file:" "$COVERAGE"
    done
fi
```

### Phase 3: Create coverage gap analysis

```bash
echo ""
echo "🎯 Coverage Gap Analysis"
echo "========================"

# Create Python script to analyze coverage gaps
cat << 'EOF' > /tmp/analyze_coverage.py
import json
import sys
from pathlib import Path

target_coverage = 99.0
coverage_data = json.load(open('coverage.json')) if Path('coverage.json').exists() else {'files': {}}

changed_files = sys.argv[1].split() if len(sys.argv) > 1 else []
analysis = []

for file_path in changed_files:
    coverage_info = None
    for key in coverage_data.get('files', {}):
        if file_path in key:
            coverage_info = coverage_data['files'][key]
            break

    if coverage_info:
        current = coverage_info['summary']['percent_covered']
        missing = coverage_info['summary']['num_statements'] - coverage_info['summary']['num_executed_statements']
        gap = target_coverage - current
        missing_lines = coverage_info.get('missing_lines', [])
    else:
        current = 0.0
        gap = target_coverage
        missing = "unknown"
        missing_lines = []

    analysis.append({
        'file': file_path,
        'current': current,
        'gap': gap,
        'missing_count': missing,
        'missing_lines': missing_lines[:10] if missing_lines else []  # First 10 missing lines
    })

# Sort by gap (largest first)
analysis.sort(key=lambda x: x['gap'], reverse=True)

print("\nFiles ranked by coverage gap:")
print("-" * 80)
for i, item in enumerate(analysis, 1):
    status = "✅" if item['gap'] <= 0 else "❌"
    print(f"{i}. {status} {item['file']}")
    print(f"   Current: {item['current']:.1f}% | Gap: {item['gap']:.1f}% | Missing: {item['missing_count']} lines")
    if item['missing_lines']:
        print(f"   Sample missing lines: {item['missing_lines'][:5]}")
    print()

# Output files needing work
needs_work = [item['file'] for item in analysis if item['gap'] > 0]
if needs_work:
    print("\n📋 Files needing coverage improvement:")
    for f in needs_work:
        print(f"   - {f}")
EOF

# Use the target coverage from environment
export TARGET_COVERAGE
python "$ANALYZE_SCRIPT"
```

### Phase 4: Generate tests for each file

For each file needing coverage improvement, delegate to test-holmes:

```text
# Store the list of files needing work
NEEDS_WORK=$(python -c "
import json
import sys
from pathlib import Path

target = 99.0
coverage_data = json.load(open('coverage.json')) if Path('coverage.json').exists() else {'files': {}}
changed = '$CHANGED_FILES'.split()

for file_path in changed:
    current = 0.0
    for key in coverage_data.get('files', {}):
        if file_path in key:
            current = coverage_data['files'][key]['summary']['percent_covered']
            break
    if current < target:
        print(file_path)
" 2>/dev/null)

if [ -z "$NEEDS_WORK" ]; then
    echo "✅ All files already meet 99% coverage target!"
    exit 0
fi

echo ""
echo "🔧 Generating tests for files below ${TARGET_COVERAGE}% coverage..."
```

For each file, use test-holmes to generate comprehensive tests:

```text
Task(description="Generate unit tests", prompt="You are test-holmes. Analyze the file [FILE_PATH] and generate comprehensive unit tests to achieve ${TARGET_COVERAGE}% code coverage. Focus on uncovered lines identified in the coverage report. Create tests that: 1) Cover all uncovered functions and methods, 2) Test edge cases and error conditions, 3) Mock external dependencies appropriately, 4) Follow the project's existing test patterns and conventions. Use pytest fixtures and parametrize for efficiency. The tests should be meaningful, not just coverage-padding.", subagent_type="test-holmes")
```

### Phase 4a: Verify test generation

After test generation, verify tests were created:

```bash
echo ""
echo "🔍 Verifying test generation..."

# Find newly created test files
NEW_TESTS=$(find tests/ -name "*.py" -newer /tmp/coverage_start_time_$$ 2>/dev/null)

if [ -z "$NEW_TESTS" ]; then
    echo "⚠️  No new test files detected. Checking for modifications to existing tests..."
    # Check if existing test files were modified
    MODIFIED_TESTS=$(find tests/ -name "*.py" -newer /tmp/coverage_start_time_$$ -o -name "test_*.py" -newer /tmp/coverage_start_time_$$ 2>/dev/null)
    if [ -z "$MODIFIED_TESTS" ]; then
        echo "❌ No test changes detected. Test generation may have failed."
        echo "Please check sub-agent output and retry if needed."
    else
        echo "✅ Found modified test files:"
        echo "$MODIFIED_TESTS" | head -10
    fi
else
    echo "✅ New test files created:"
    echo "$NEW_TESTS" | head -10
fi
```

### Phase 5: Fix type and linting issues

After test generation, fix any quality issues:

```bash
echo ""
echo "🔨 Fixing type and linting issues..."

# Run type checking
echo "Running mypy..."
make type-check || {
    echo "Type errors detected, delegating to type-veronica..."
}
```

If type errors found:

```text
Task(description="Fix type errors", prompt="You are type-veronica. The newly generated test files have mypy errors. Fix all type annotation issues while maintaining test functionality. Focus on proper mock typing, async test annotations, and fixture types.", subagent_type="type-veronica")
```

```bash
# Run linting
echo "Running ruff..."
make lint || {
    echo "Linting issues detected, delegating to ruff-house..."
}
```

If linting issues found:

```text
Task(description="Fix linting issues", prompt="You are ruff-house. The newly generated test files have linting issues. Fix all ruff violations while maintaining code functionality and readability.", subagent_type="ruff-house")
```

### Phase 6: Verify coverage improvement

```bash
echo ""
echo "📊 Verifying coverage improvements..."

# Re-run coverage
pytest --cov=src/scriptrag --cov-report=term-missing --cov-report=json --tb=short -q

# Check if all files meet target
echo ""
echo "📈 Coverage after improvements:"
# Use the target coverage from environment
export TARGET_COVERAGE
python "$ANALYZE_SCRIPT"

# Determine if target met
ALL_PASS=$(python -c "
import json
import os
import os.path
from pathlib import Path

target = float(os.environ.get('TARGET_COVERAGE', '99'))
coverage_data = json.load(open('coverage.json')) if Path('coverage.json').exists() else {'files': {}}

# Get files from environment
changed_files = os.environ.get('CHANGED_FILES_LIST', '').strip().split('\\n')

for file_path in changed_files:
    if not file_path:
        continue
    current = 0.0
    for key, value in coverage_data.get('files', {}).items():
        if (os.path.normpath(file_path) in os.path.normpath(key) or
            os.path.basename(file_path) == os.path.basename(key)):
            current = value['summary']['percent_covered']
            break
    if current < target:
        exit(1)
print('YES')
" 2>/dev/null || echo "NO")

if [ "$ALL_PASS" != "YES" ]; then
    echo "⚠️ Some files still below ${TARGET_COVERAGE}% coverage. Continuing iteration..."
fi
```

### Phase 7: Commit improvements

Once a batch of files reaches target coverage:

```bash
echo ""
echo "💾 Committing test improvements..."

# Stage test files
git add tests/

# Create detailed commit message
COMMIT_MSG=$(cat << EOF
test: achieve ${TARGET_COVERAGE}% coverage for changed modules

Coverage improvements:
EOF
)

# Add file-specific improvements
for file in "${CHANGED_FILES_ARRAY[@]}"; do
    # Get before/after coverage for commit message
    echo "- $file: X% → ${TARGET_COVERAGE}%" >> /tmp/commit_msg.txt
done

# Delegate to commit-quentin for proper commit
```

```text
Task(description="Create commit", prompt="You are commit-quentin. Create a cinematic commit message for test coverage improvements. The tests now achieve ${TARGET_COVERAGE}% coverage for all changed files. Make it dramatic and reference an appropriate film about perfection, completion, or achieving the impossible.", subagent_type="commit-quentin")
```

### Phase 8: CI verification

```bash
echo ""
echo "🚀 Pushing changes and monitoring CI..."

# Push changes
git push origin "$BRANCH"

echo ""
echo "Initiating CI verification..."
```

Use the /ci-cycle command to verify:

```bash
# Invoke ci-cycle to handle the full CI verification flow
/ci-cycle
```

### Phase 9: Iteration control

If CI fails or coverage is still insufficient:

```bash
echo ""
echo "🔄 Checking if iteration needed..."

# This will be handled by the ci-cycle command
# If it reports failures, we'll get ci-mulder to investigate
# and then loop back to Phase 4 for the remaining files
```

## Success Criteria

The command completes when:
- All changed Python files have ≥${TARGET_COVERAGE}% test coverage (default: 99%)
- All tests pass locally (pytest)
- All type checks pass (mypy)
- All linting passes (ruff)
- CI verification succeeds
- Changes are committed with appropriate messages

## Configuration

### Environment Variables

- `TARGET_COVERAGE`: Set the coverage target percentage (default: 99)
  ```bash
  TARGET_COVERAGE=95 /test-coverage  # Use 95% target instead of 99%
  ```

## Important Notes

1. **Delegation Strategy**: Use specialized agents for their expertise
   - test-holmes: Test generation and coverage analysis
   - type-veronica: Type annotation fixes
   - ruff-house: Linting and formatting
   - commit-quentin: Cinematic commit messages
   - ci-mulder: CI failure investigation (via ci-cycle)

2. **Iteration Logic**: The command may need multiple iterations
   - Each iteration focuses on files still below target
   - Commits are made after each successful batch
   - CI verification happens after each commit

3. **Quality Standards**: Tests must be meaningful
   - Not just coverage padding
   - Proper mocking and fixtures
   - Edge cases and error conditions
   - Follow project conventions

4. **File Handling**: Properly handles filenames with spaces and special characters
   - Uses bash arrays for file lists
   - Passes files via environment variables to Python scripts
   - Normalizes paths for coverage matching

5. **Cleanup**: Temporary files are automatically cleaned up on exit
   - Uses trap to ensure cleanup even on early exit
   - Unique filenames with process ID to avoid collisions
