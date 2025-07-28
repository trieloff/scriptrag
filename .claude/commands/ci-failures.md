---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(*)
description: Get CI test failures from GitHub Actions
---

## Context

- Current git status: !`git status`
- Current branch: !`git branch --show-current`
- Repository: !`git remote get-url origin`

## Your task

Retrieve and analyze the latest CI test failures from GitHub Actions. Run the following script to fetch failure data:

```bash
#!/bin/bash
set -e

# Get the repository name from git remote
REPO=$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/')
echo "🔍 Fetching CI failures for repository: $REPO"

# Get the latest failed workflow runs
LATEST_FAILED_RUN=$(gh run list --repo="$REPO" --status=failure --limit=1 --json=databaseId,displayTitle,headBranch,createdAt,conclusion --jq '.[0]')

if [[ -z "$LATEST_FAILED_RUN" || "$LATEST_FAILED_RUN" == "null" ]]; then
    echo "✅ No recent failures found in CI"
    exit 0
fi

RUN_ID=$(echo "$LATEST_FAILED_RUN" | jq -r '.databaseId')
echo "📊 Latest failed run: #$RUN_ID - $(echo "$LATEST_FAILED_RUN" | jq -r '.displayTitle')"
echo "Branch: $(echo "$LATEST_FAILED_RUN" | jq -r '.headBranch')"
echo "Created: $(echo "$LATEST_FAILED_RUN" | jq -r '.createdAt')"
echo "Conclusion: $(echo "$LATEST_FAILED_RUN" | jq -r '.conclusion')"
echo ""

# Get the failed jobs
echo "🔍 Failed jobs:"
gh run view --repo="$REPO" "$RUN_ID" --json=jobs --jq '.jobs[] | select(.conclusion=="failure") | {name: .name, conclusion: .conclusion, steps: [.steps[] | select(.conclusion=="failure") | {name: .name, conclusion: .conclusion, number: .number}]}' | jq -r '.name + ": " + (.steps | map(.name + " (step " + (.number | tostring) + ")") | join(", "))'

echo ""
echo "📋 Detailed logs:"
gh run view --repo="$REPO" "$RUN_ID" --log | grep -A 5 -B 5 "FAILED\|ERROR\|AssertionError\|failed" | head -50
```

Save this script to a temporary file and execute it to get the CI failure data, then analyze the failures and provide a summary of what's broken, along with suggestions for fixing the issues.