---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(*), Task(*)
description: Complete CI cycle - merge, wait, investigate, fix, commit, push
---

## Context

- Current git status: !`git status`
- Current branch: !`git branch --show-current`
- Repository: !`git remote get-url origin`

## Your task

Execute the complete CI development cycle:

### Phase 1: Merge from main
```bash
git fetch origin
git merge origin/main --no-edit
```

### Phase 2: Wait for GitHub Actions
```bash
echo "Waiting for CI to complete..."
gh run watch --repo=$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/') --interval=30
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
git push origin $(git branch --show-current)
```

### Phase 6: Repeat cycle
Return to Phase 2 and continue until CI passes.

## Automation script
Save this as a temporary script for the cycle:

```bash
#!/bin/bash
set -e

REPO=$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/')
BRANCH=$(git branch --show-current)

echo "🔄 Starting CI cycle for $REPO on branch $BRANCH"

# Phase 1: Merge from main
echo "📥 Merging from main..."
git fetch origin
git merge origin/main --no-edit

# Phase 2: Wait for CI
echo "⏳ Waiting for CI to complete..."
gh run watch --repo="$REPO" --interval=30

# Check if CI passed
LATEST_RUN=$(gh run list --repo="$REPO" --branch="$BRANCH" --limit=1 --json=conclusion --jq '.[0].conclusion')
if [[ "$LATEST_RUN" == "success" ]]; then
    echo "✅ CI passed - cycle complete"
    exit 0
fi

echo "❌ CI failed - investigating..."
/ci-failures
```

Execute this cycle until CI passes successfully.