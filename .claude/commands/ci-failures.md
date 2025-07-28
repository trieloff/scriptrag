---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(*)
description: Get CI test failures from GitHub Actions
---

# CI Failures Command

## Context

- Current git status: !`git status`
- Current branch: !`git branch --show-current`
- Repository: !`git remote get-url origin`

## Your task

Retrieve and analyze the latest CI test failures from GitHub Actions.

### Step 1: Get CI failure information

```bash
# Extract repository name (without .git suffix)
REPO="$(git remote get-url origin | sed -E 's|.*github\.com[:/]([^/]+/[^/]+)(\.git)?$|\1|' | sed 's/\.git$//')"
BRANCH="$(git branch --show-current)"

echo "🔍 Checking GitHub Actions for $REPO on branch $BRANCH"
echo ""

# Get the latest workflow runs on current branch
LATEST_RUNS=$(gh run list --repo="$REPO" --branch="$BRANCH" --limit=5 --json databaseId,status,conclusion,displayTitle,workflowName)

# Check if any runs exist
if [ -z "$LATEST_RUNS" ] || [ "$LATEST_RUNS" = "[]" ]; then
    echo "ℹ️ No CI runs found for branch $BRANCH"
    exit 0
fi

# Display recent runs
echo "📊 Recent CI runs:"
echo "$LATEST_RUNS" | jq -r '.[] | "Run #\(.databaseId): \(.workflowName) - \(.displayTitle)\n  Status: \(.status), Conclusion: \(.conclusion // "pending")"'
echo ""

# Find the most recent failure
FAILED_RUN=$(echo "$LATEST_RUNS" | jq -r '.[] | select(.conclusion == "failure") | .databaseId' | head -1)

if [ -z "$FAILED_RUN" ]; then
    # Check if there's a run in progress
    IN_PROGRESS=$(echo "$LATEST_RUNS" | jq -r '.[] | select(.status == "in_progress") | .databaseId' | head -1)
    if [ -n "$IN_PROGRESS" ]; then
        echo "⏳ CI is currently running (Run #$IN_PROGRESS). No failures to analyze yet."
    else
        echo "✅ No recent CI failures found!"
    fi
    exit 0
fi

echo "❌ Analyzing failed run #$FAILED_RUN"
echo ""
```

### Step 2: Get detailed failure information

```bash
# Get detailed information about the failed run
echo "📋 Failed jobs and steps:"
gh run view "$FAILED_RUN" --repo="$REPO" --json jobs --jq '.jobs[] | select(.conclusion == "failure") | "Job: \(.name)\n  Failed steps: \([.steps[] | select(.conclusion == "failure") | "- \(.name) (step \(.number))"] | join("\n  "))"' || echo "Unable to retrieve job details"

echo ""
echo "🔍 Fetching error logs..."
echo ""

# Create a temporary file for logs
TMPFILE=$(mktemp)

# Download the full log
gh run view "$FAILED_RUN" --repo="$REPO" --log > "$TMPFILE" 2>/dev/null || {
    echo "Unable to download full logs. Trying alternative method..."
    gh run view "$FAILED_RUN" --repo="$REPO" --log-failed > "$TMPFILE" 2>/dev/null || {
        echo "Unable to retrieve logs"
        rm -f "$TMPFILE"
        exit 1
    }
}

# Extract error patterns
echo "📋 Error summary:"
echo ""

# Look for Python test failures
if grep -q "FAILED.*test_" "$TMPFILE" 2>/dev/null; then
    echo "🐍 Python test failures:"
    # Get both start and end of matches for comprehensive view
    { grep -E "FAILED.*test_|AssertionError|pytest.*failed" "$TMPFILE" | head -25;
      echo "...";
      grep -E "FAILED.*test_|AssertionError|pytest.*failed" "$TMPFILE" | tail -25; } | sort | uniq
    echo ""
    echo "💡 Note: Showing first and last 25 matches. Adjust limits if failures are missing."
fi

# Look for type checking errors
if grep -q "error: " "$TMPFILE" 2>/dev/null; then
    echo "📝 Type checking errors:"
    # Get both start and end for complete picture
    { grep -A 2 -B 2 "error: " "$TMPFILE" | head -50;
      echo "...";
      grep -A 2 -B 2 "error: " "$TMPFILE" | tail -50; } | sort | uniq
    echo ""
    echo "💡 Note: Showing first and last 50 lines. Increase if needed for full coverage."
fi

# Look for linting errors
if grep -q -E "ruff|flake8|pylint" "$TMPFILE" 2>/dev/null; then
    echo "🔍 Linting errors:"
    { grep -A 2 -B 2 -E "ruff|flake8|pylint.*:" "$TMPFILE" | head -50;
      echo "...";
      grep -A 2 -B 2 -E "ruff|flake8|pylint.*:" "$TMPFILE" | tail -50; } | sort | uniq
    echo ""
fi

# Look for general errors
echo "❌ General errors:"
{ grep -i -E "error:|failed:|failure:" "$TMPFILE" | grep -v "::error" | head -30;
  echo "...";
  grep -i -E "error:|failed:|failure:" "$TMPFILE" | grep -v "::error" | tail -30; } | sort | uniq || echo "No specific error patterns found"
echo ""
echo "💡 Tip: Critical errors often appear at the start or end of logs. Adjust extraction limits if issues are missing."

# Clean up
rm -f "$TMPFILE"
```

### Step 3: Provide actionable summary

Based on the error patterns found, provide:

1. A clear summary of what's failing
2. The root cause of the failures
3. Specific steps to fix the issues
4. Commands to run locally to verify fixes
