---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(*)
description: Check GitHub Actions status and PR checks for the current branch
---

## Context

- Current git status: !`git status`
- Current branch: !`git branch --show-current`
- Repository: !`git remote get-url origin`

## Your task

Check the GitHub Actions status and PR checks for the current branch using GitHub CLI.

### Check current branch status
```bash
REPO=$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/')
BRANCH=$(git branch --show-current)

echo "🔍 Checking GitHub Actions for $REPO on branch $BRANCH"

# List recent workflow runs
gh run list --repo="$REPO" --branch="$BRANCH" --limit=5 --json=databaseId,name,status,conclusion,createdAt --jq '.[] | "Run #\(.databaseId): \(.name) - \(.status) - \(.conclusion) - \(.createdAt)"'

# Check for any pending or failed runs
echo ""
echo "📊 Current status summary:"
gh run list --repo="$REPO" --branch="$BRANCH" --limit=3 --json=status,conclusion --jq 'group_by(.status)[] | {status: .[0].status, count: length}'
```

### Check PR checks (if PR exists)
```bash
# Check if there's an open PR for this branch
PR_NUMBER=$(gh pr list --repo="$REPO" --head="$BRANCH" --json=number --jq '.[0].number')

if [[ -n "$PR_NUMBER" && "$PR_NUMBER" != "null" ]]; then
    echo ""
    echo "🔍 Checking PR #$PR_NUMBER checks:"
    gh pr checks --repo="$REPO" "$PR_NUMBER"
else
    echo ""
    echo "📋 No open PR found for branch $BRANCH"
fi
```

### Quick status summary
```bash
echo ""
echo "📈 Quick summary:"
LATEST_RUN=$(gh run list --repo="$REPO" --branch="$BRANCH" --limit=1 --json=status,conclusion --jq '.[0]')
if [[ -n "$LATEST_RUN" ]]; then
    STATUS=$(echo "$LATEST_RUN" | jq -r '.status')
    CONCLUSION=$(echo "$LATEST_RUN" | jq -r '.conclusion')
    
    case "$CONCLUSION" in
        "success")
            echo "✅ Latest run: SUCCESS"
            ;;
        "failure")
            echo "❌ Latest run: FAILED"
            echo "Use /ci-failures to investigate"
            ;;
        "cancelled")
            echo "⚠️  Latest run: CANCELLED"
            ;;
        *)
            echo "⏳ Latest run: $STATUS ($CONCLUSION)"
            ;;
    esac
else
    echo "ℹ️  No recent runs found"
fi
```

## Usage examples
- Use `/gh-checks` to quickly see the status of all GitHub Actions
- Combine with `/ci-failures` if checks are failing
- Use before `/ci-cycle` to understand current state