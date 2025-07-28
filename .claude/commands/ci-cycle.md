---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(*), Task(*)
description: Complete CI cycle - merge, wait, investigate, fix, commit, push
---

# CI Cycle Command

## Context

- Current git status: !`git status`
- Current branch: !`git branch --show-current`
- Repository: !`git remote get-url origin`

## Your task

Execute the complete CI development cycle, starting with GitHub Actions status check:

### Phase 1: Establish context with GitHub Actions status

```bash
REPO="$(git remote get-url origin | sed -E 's|.*github\.com[:/]([^/]+/[^/]+)(\.git)?$|\1|')"
BRANCH="$(git branch --show-current)"

# Validate GitHub CLI authentication
if ! gh auth status &>/dev/null; then
    echo "❌ GitHub CLI not authenticated. Run: gh auth login"
    exit 1
fi

echo "🔍 Checking GitHub Actions for $REPO on branch $BRANCH"

# Check current status with error handling
LATEST_RUN=$(gh run list --repo="$REPO" --branch="$BRANCH" --limit=1 --json=databaseId,status,conclusion,displayTitle --jq '.[0] // empty')
if [[ -n "$LATEST_RUN" && "$LATEST_RUN" != "null" ]]; then
    RUN_ID=$(echo "$LATEST_RUN" | jq -r '.databaseId // "unknown"')
    STATUS=$(echo "$LATEST_RUN" | jq -r '.status // "unknown"')
    CONCLUSION=$(echo "$LATEST_RUN" | jq -r '.conclusion // "unknown"')
    TITLE=$(echo "$LATEST_RUN" | jq -r '.displayTitle // "unknown"')

    echo "📊 Current status: #$RUN_ID - $TITLE"
    echo "Status: $STATUS, Conclusion: $CONCLUSION"
else
    echo "ℹ️  No recent runs found for branch $BRANCH"
fi

### Phase 2: Merge from main
```bash
git fetch origin
git merge origin/main --no-edit
```

### Phase 3: Wait for GitHub Actions

```bash
echo "⏳ Waiting for CI to complete... (timeout: 30 minutes)"
timeout 1800 gh run watch --repo="$REPO" --interval=30 || {
    echo "⚠️  CI watch timeout reached - checking current status"
}
```

### Phase 3: Investigate failures

If CI fails, use both investigation methods:

- /ci-failures (slash command)
- Agent: ci-mulder for conspiracy-level analysis

### Phase 4: Fix failures

Based on investigation:

- Apply fixes using appropriate patterns
- Run local tests to verify fixes
- Use type-checking and linting as needed

### Phase 5: Commit and push

```bash
git add .
git commit -m "fix(ci): resolve build failures

<detailed commit message based on fixes>"

<appropriate movie quote>
git push origin "$(git branch --show-current)"
```

### Phase 6: Repeat cycle

Return to Phase 2 and continue until CI passes.

## Automation script

Save this as a temporary script for the cycle:

```bash
#!/bin/bash
set -e

# Validate GitHub CLI authentication
if ! gh auth status &>/dev/null; then
    echo "❌ GitHub CLI not authenticated. Run: gh auth login"
    exit 1
fi

REPO="$(git remote get-url origin | sed -E 's|.*github\.com[:/]([^/]+/[^/]+)(\.git)?$|\1|')"
BRANCH="$(git branch --show-current)"

echo "🔄 Starting CI cycle for $REPO on branch $BRANCH"

# Phase 1: Merge from main
echo "📥 Merging from main..."
git fetch origin
git merge origin/main --no-edit

# Phase 2: Wait for CI with timeout
echo "⏳ Waiting for CI to complete... (timeout: 30 minutes)"
timeout 1800 gh run watch --repo="$REPO" --interval=30 || {
    echo "⚠️  CI watch timeout reached - checking current status"
}

# Check if CI passed
LATEST_RUN=$(gh run list --repo="$REPO" --branch="$BRANCH" --limit=1 --json=conclusion --jq '.[0].conclusion // "unknown"')
if [[ "$LATEST_RUN" == "success" ]]; then
    echo "✅ CI passed - cycle complete"
    exit 0
fi

echo "❌ CI failed - investigating..."
```

Now use the slash command for CI failure analysis:

```text
/ci-failures
```

Execute this cycle until CI passes successfully.
