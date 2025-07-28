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

Execute the complete CI development cycle with proper PR context and CI status checking.

### Phase 1: Establish PR and CI context

First, check the current PR status and CI state:

```bash
# Extract repository name (without .git suffix)
REPO="$(git remote get-url origin | sed -E 's|.*github\.com[:/]([^/]+/[^/]+)(\.git)?$|\1|' | sed 's/\.git$//')"
BRANCH="$(git branch --show-current)"

echo "📊 Repository: $REPO"
echo "🌿 Branch: $BRANCH"
echo ""

# Check if we're in a PR
echo "🔍 Checking PR status..."
gh pr status --json currentBranch,title,number,url,isDraft,state || echo "No PR found for current branch"

# If PR exists, get detailed info
PR_NUMBER=$(gh pr status --json currentBranch,number --jq '.currentBranch.number // empty' 2>/dev/null || echo "")
if [ -n "$PR_NUMBER" ]; then
    echo ""
    echo "📋 PR #$PR_NUMBER details:"
    gh pr view "$PR_NUMBER" --json title,state,mergeable,checks --jq '. | "Title: \(.title)\nState: \(.state)\nMergeable: \(.mergeable)\nChecks: \(.checks | length) total"'

    echo ""
    echo "🔍 PR checks status:"
    gh pr checks "$PR_NUMBER" || echo "Unable to retrieve checks"
fi

# Check latest CI run
echo ""
echo "🔍 Latest CI run on branch $BRANCH:"
gh run list --repo="$REPO" --branch="$BRANCH" --limit=1 || echo "No CI runs found"
```

### Phase 2: Merge from main

```bash
echo ""
echo "📥 Fetching and merging from main..."
git fetch origin
git merge origin/main --no-edit || {
    echo "⚠️ Merge conflicts detected. Please resolve manually."
    exit 1
}
```

### Phase 3: Push and monitor CI

```bash
echo ""
echo "📤 Pushing to remote..."
git push origin "$BRANCH"

echo ""
echo "⏳ Waiting for CI to start and complete..."
# Wait a moment for CI to trigger
sleep 5

# Get the new run ID
RUN_ID=$(gh run list --repo="$REPO" --branch="$BRANCH" --limit=1 --json databaseId --jq '.[0].databaseId // empty')
if [ -n "$RUN_ID" ]; then
    echo "👀 Monitoring run #$RUN_ID..."
    # Use gh run watch without timeout command (not portable)
    gh run watch "$RUN_ID" --repo="$REPO" --interval=30 || true
fi
```

### Phase 4: Check CI results and investigate failures

```bash
# Check the final status
echo ""
echo "📊 Checking CI results..."
LATEST_RUN=$(gh run list --repo="$REPO" --branch="$BRANCH" --limit=1 --json databaseId,status,conclusion,displayTitle)
CONCLUSION=$(echo "$LATEST_RUN" | jq -r '.[0].conclusion // "unknown"')

if [ "$CONCLUSION" = "success" ]; then
    echo "✅ CI passed successfully!"
    exit 0
fi

echo "❌ CI failed or is still running. Current status:"
echo "$LATEST_RUN" | jq -r '.[0] | "Run #\(.databaseId): \(.displayTitle)\nStatus: \(.status)\nConclusion: \(.conclusion)"'
```

### Phase 5: Investigate and fix failures

If CI has failed, use the ci-mulder agent to investigate (with explicit instruction not to recursively call /ci-cycle):

```bash
echo ""
echo "🔍 Delegating to ci-mulder for failure analysis..."
```

Use the Task tool to invoke ci-mulder:

- Agent type: ci-mulder
- Instructions: "Analyze the CI failures for the current branch and provide fixes. DO NOT call /ci-cycle command as we are already in that flow."

### Phase 6: Apply fixes and commit

After ci-mulder provides fixes:

1. Apply the recommended changes
2. Run local tests to verify
3. Commit with appropriate message
4. Push to remote

### Phase 7: Monitor new CI run

Return to Phase 3 to monitor the new CI run. Continue this cycle until CI passes.

**Important Notes:**

- This command should NOT call itself recursively
- Delegate CI failure investigation to ci-mulder agent
- Always check PR context before proceeding
- Exit gracefully when CI passes
