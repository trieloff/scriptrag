#!/bin/bash
cd /root/repo
git add tests/integration/test_cli_list.py
git commit -m "fix(tests): make list command tests Windows-compatible

The tests were counting expected scripts from the fixtures directory
instead of the actual temporary test directory. This caused failures
on Windows where the temporary directory might have different contents
due to platform differences or timing issues.

Fixed by:
- Counting files in the actual test directory instead of fixtures
- Using test_dir.glob() to get accurate counts of what's actually present
- Making tests platform-agnostic and deterministic

This ensures tests pass consistently across all platforms.

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"
git push
