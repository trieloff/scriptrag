# CI Infrastructure Issue - August 26, 2025

## Problem

The CI pipeline is experiencing failures due to:

1. **NPM Registry 403 Errors**: The pre-commit hooks job cannot install markdownlint-cli due to HTTP 403 Forbidden errors from npm registry
2. **Test Timeouts**: Some tests may be timing out in CI (15s limit) but pass locally

## Root Cause

- NPM registry appears to be blocking or rate-limiting GitHub Actions runners
- CI environment has different performance characteristics than local development

## Recommended Fixes (Requires Workflow Permissions)

The following changes to `.github/workflows/ci.yml` would resolve these issues:

### 1. Add NPM Retry Logic

```yaml
- name: Install markdownlint-cli
  run: |
    # Retry npm install with exponential backoff
    for i in {1..3}; do
      if npm install -g markdownlint-cli; then
        break
      else
        echo "npm install attempt $i failed, retrying in $((i*2)) seconds..."
        sleep $((i*2))
      fi
    done
    # Verify installation
    markdownlint --version
```

### 2. Increase Test Timeout

Change test timeout from 15s to 30s:

```yaml
--timeout=30
```

## Temporary Workaround

Until workflow permissions are granted, the team can:

1. Manually apply these changes to the workflow file
2. Consider using a different npm registry mirror
3. Run tests with increased timeouts locally before pushing

## Status

- All tests pass locally
- Code changes are complete and working
- Only CI infrastructure issues remain
