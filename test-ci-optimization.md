# CI Optimization Test

This file is created to test the CI optimization that skips tests when no Python files are modified.

When this PR is created with only this markdown file, the CI should:

1. Run the `changes` job to detect changed files
2. Skip all Python-related jobs (lint, type-check, security, test, build)
3. Still run the `docs` and `pre-commit` jobs (as they handle non-Python files too)
4. The `all-checks` job should pass automatically since no Python files were changed

This optimization significantly reduces CI time for documentation-only changes, configuration updates, or other non-Python modifications.
