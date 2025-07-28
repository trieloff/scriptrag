# Retrieving Test Failures from GitHub CI Logs

## Problem

When tests fail in GitHub Actions CI, the test summary information often appears deep in the logs (e.g., line 5385+), making it difficult to quickly identify what failed. This document provides reliable procedures to retrieve test failure information efficiently.

## Important Notes

- **Logs are only available after the entire workflow run completes** - Individual job logs cannot be accessed via CLI while the run is in progress
- **For in-progress runs**, use the web browser method (Solution 3) to view completed job logs
- **The GitHub CLI methods work best for completed runs**

## Quick Solution (Recommended)

### For Completed Runs

The most reliable method is to use the `--log-failed` option with GitHub CLI:

```bash
# Extract just the test summary section
gh run view 16559206559 --repo trieloff/scriptrag --log-failed | \
  awk '/short test summary/{found=1} found && /^$/{exit} found{print}'
```

### For In-Progress Runs

Check which jobs have completed and failed:

```bash
# List all completed jobs with their status
gh run view 16559533966 --repo trieloff/scriptrag --json jobs --jq \
  '.jobs[] | select(.status=="completed") | {name, conclusion, databaseId}'

# Get logs from a specific completed job (extract job ID from URL or list above)
JOB_ID=46826485598
gh api repos/trieloff/scriptrag/actions/jobs/$JOB_ID/logs > job.log 2>/dev/null && \
  grep -A 30 "short test summary" job.log | head -50; rm -f job.log

# Alternative: Get just the test failures
gh api repos/trieloff/scriptrag/actions/jobs/$JOB_ID/logs 2>/dev/null | \
  grep -E "^FAILED|ERROR" | head -20
```

## Solution 1: Direct Log Streaming

### Prerequisites

- Install GitHub CLI: `brew install gh` (macOS) or see [installation guide](https://cli.github.com/)
- Authenticate: `gh auth login`

### One-Liner Commands

```bash
# Get test failures with context (most useful)
gh run view 16559206559 --repo trieloff/scriptrag --log-failed | \
  grep -B 5 -A 30 "short test summary\|FAILED\|ERROR" | head -150

# Extract only the test summary section
gh run view 16559206559 --repo trieloff/scriptrag --log-failed | \
  awk '/short test summary/{found=1} found && /^$/{exit} found{print}'

# Get just the FAILED lines
gh run view 16559206559 --repo trieloff/scriptrag --log-failed | \
  grep "^FAILED" | head -20
```

## Solution 2: Automated Script

Create a script `get-ci-failures.sh`:

```bash
#!/usr/bin/env bash

# Usage: ./get-ci-failures.sh <run-id> [repo]
# Example: ./get-ci-failures.sh 16559206559
# Example: ./get-ci-failures.sh 16559206559 owner/repo

RUN_ID=$1
REPO=${2:-"trieloff/scriptrag"}  # Default repo, can be overridden

if [ -z "$RUN_ID" ]; then
    echo "Usage: $0 <run-id> [repo]"
    echo "Example: $0 16559206559"
    echo "Example: $0 16559206559 owner/repo"
    exit 1
fi

echo "Fetching test failures for run $RUN_ID in repo $REPO..."

# Get list of failed jobs
echo -e "\n=== Failed Jobs ==="
gh run view "$RUN_ID" --repo "$REPO" --json jobs --jq \
  '.jobs[] | select(.conclusion=="failure") | {name, databaseId}'

# Extract test summary using the most reliable method
echo -e "\n=== Test Summary ==="
gh run view "$RUN_ID" --repo "$REPO" --log-failed | \
  awk '/short test summary/{found=1} found && /^$/{exit} found{print}'

# Get just the failure lines if needed
echo -e "\n=== Failed Tests ==="
gh run view "$RUN_ID" --repo "$REPO" --log-failed | \
  grep "^FAILED" | head -20
```

Make it executable:

```bash
chmod +x get-ci-failures.sh
```

## Solution 3: Using Web Browser with Search

1. Navigate to the failed workflow run
2. Click on the failed job
3. Use browser search (Ctrl+F / Cmd+F) for these patterns:
   - `"short test summary"`
   - `"FAILED"`
   - `"ERROR"`
   - `"= FAILURES ="`

## Solution 4: GitHub Actions Workflow Enhancement

For future runs, add this to your GitHub Actions workflow to make failures more visible:

```yaml
- name: Upload test results
  if: failure()
  uses: actions/upload-artifact@v3
  with:
    name: test-results
    path: |
      **/pytest-report.xml
      **/coverage.xml
      **/junit.xml

- name: Surface test failures
  if: failure()
  run: |
    echo "## Test Failures Summary" >> $GITHUB_STEP_SUMMARY
    echo '```' >> $GITHUB_STEP_SUMMARY
    # Run pytest again to capture just the failures
    pytest --tb=short --no-header -rN | grep -E "FAILED|ERROR" | head -20 >> $GITHUB_STEP_SUMMARY || true
    echo '```' >> $GITHUB_STEP_SUMMARY
```

## Quick Commands Reference

```bash
# Get run ID from URL
URL="https://github.com/trieloff/scriptrag/actions/runs/16559206559"
RUN_ID=$(echo $URL | grep -oE '[0-9]+$')

# Get job ID from URL (for specific job logs)
JOB_URL="https://github.com/trieloff/scriptrag/actions/runs/16559533966/job/46826485598"
JOB_ID=$(echo $JOB_URL | grep -oE '[0-9]+$')

# Quick test summary extraction (completed runs)
gh run view $RUN_ID --repo trieloff/scriptrag --log-failed | \
  awk '/short test summary/{found=1} found && /^$/{exit} found{print}'

# Quick test summary extraction (specific job)
gh api repos/trieloff/scriptrag/actions/jobs/$JOB_ID/logs 2>/dev/null | \
  grep -B 2 -A 30 "short test summary"

# Get failures with file/line info
gh run view $RUN_ID --repo trieloff/scriptrag --log-failed | \
  grep -E "^FAILED tests/" | sort | uniq

# Count failures by test file
gh run view $RUN_ID --repo trieloff/scriptrag --log-failed | \
  grep "^FAILED" | cut -d':' -f1 | sort | uniq -c | sort -nr
```

## Tips

1. **Look for these key markers in logs:**
   - `=== short test summary info ===`
   - `FAILED tests/...`
   - `ERROR tests/...`
   - `=== FAILURES ===`

2. **Common log locations for test summaries:**
   - Near the end of the "Run tests" step
   - After all individual test outputs
   - Before the job summary

3. **For pytest specifically:**
   - Search for `pytest` exit code non-zero
   - Look for the `-v` output showing individual test results
   - Check for the final statistics line (e.g., "1 failed, 99 passed")

4. **Use `--json` output for programmatic access:**

   ```bash
   gh run view $RUN_ID --json jobs,conclusion,status | jq '.jobs[] | select(.conclusion=="failure")'
   ```
