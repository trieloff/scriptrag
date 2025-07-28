---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(git rebase:*), Bash(git merge:*), Bash(git diff:*), Bash(git log:*), Bash(*), Task(*)
description: Rebase with main, resolve conflicts, commit with Quentin, update status with Lumbergh
---

# Commit Command

## Context

- Current git status: !`git status --porcelain`
- Current branch: !`git branch --show-current`
- Repository: !`git remote get-url origin`
- Recent commits: !`git log --oneline -5`

## Your task

Execute a complete commit workflow with proper agent delegation:

### Phase 1: Rebase with main

First, ensure we're up to date with the main branch:

```bash
# Fetch latest changes
git fetch origin main

# Check current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "📍 Current branch: $CURRENT_BRANCH"

# Rebase with main
echo "🔄 Rebasing with main..."
git rebase origin/main
```

### Phase 2: Handle conflicts (if any)

If rebase encounters conflicts:

```bash
# Check for conflicts
if git status --porcelain | grep -E '^(UU|AA|DD|DU|UD|AU|UA)'; then
    echo "⚠️  Merge conflicts detected!"
    echo "📋 Conflicted files:"
    git status --porcelain | grep -E '^(UU|AA|DD|DU|UD|AU|UA)' | awk '{print $2}'

    # Show conflict details
    git diff --name-only --diff-filter=U

    # Manual resolution required
    echo "Please resolve conflicts manually, then run:"
    echo "  git add <resolved-files>"
    echo "  git rebase --continue"
else
    echo "✅ No conflicts - rebase successful"
fi
```

### Phase 3: Prepare changes for commit

Review all staged and unstaged changes:

```bash
# Show current status
echo "📊 Current changes:"
git status

# Show detailed diff
echo "📝 Detailed changes:"
git diff --staged
git diff
```

### Phase 4: Delegate to commit-quentin

Use the commit-quentin agent to craft a cinematic commit message:

```text
Task(description="Create commit message", prompt="You are commit-quentin. Analyze the staged changes and create a perfect Tarantino-style commit message. Remember to use your FULL pop culture repertoire - not just Tarantino films, but everything from blaxploitation to Soviet arthouse, from anime to Turkish knockoffs. The wilder and more obscure the reference, the better!", subagent_type="commit-quentin")
```

### Phase 5: Check if project updates are needed

Determine if README.md or WEEKLY_STATUS_REPORT.md need updating:

```bash
# Check if this is a significant milestone
echo "🎯 Checking if project status update is needed..."

# Look for phase completions or major features
git diff --staged --name-only | grep -E "(feat|fix|refactor)" || true
```

### Phase 6: Delegate to project-lumbergh (if needed)

If project status updates are warranted:

```text
Task(description="Update project status", prompt="You are project-lumbergh. A new commit has been made. Review the changes and determine if README.md or WEEKLY_STATUS_REPORT.md need updating with new story points, phase completions, or velocity metrics. Also check GitHub for any issues or PRs that need your passive-aggressive commentary. Remember you can ONLY edit README.md and WEEKLY_STATUS_REPORT.md - use gh commands for all GitHub interactions, mmm'kay?", subagent_type="project-lumbergh")
```

### Phase 7: Final status check

```bash
# Show final status
echo "✅ Commit workflow complete!"
echo "📊 Current status:"
git status
echo ""
echo "📝 Latest commit:"
git log -1 --oneline
```

## Important Notes

1. **Conflict Resolution**: If conflicts occur during rebase, they must be manually resolved before continuing
2. **Agent Delegation**: The commit-quentin agent handles ALL commit message creation
3. **Project Updates**: The project-lumbergh agent ONLY updates README.md and WEEKLY_STATUS_REPORT.md
4. **GitHub Interactions**: All issue/PR comments must use `gh` commands, not file edits

Execute this workflow to ensure proper rebasing, cinematic commit messages, and obsessive project management!
