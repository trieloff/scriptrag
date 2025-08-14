# GitHub Actions Workflows

This directory contains GitHub Actions workflows for continuous integration, code review, and automated diagnostics.

## Workflows

### CI (`ci.yml`)
The main continuous integration pipeline that runs on all pull requests and pushes to main.

**Features:**
- Linting and code quality checks
- Type checking with MyPy
- Security scanning with Bandit and Safety
- SQL linting with SQLFluff
- Test matrix across Python 3.12/3.13 and Ubuntu/macOS/Windows
- Documentation building
- Distribution packaging
- Pre-commit hooks validation
- Integration tests with LLM providers

**Key Jobs:**
- `changes` - Detects which files changed to optimize job execution
- `test-canary` - Fast minimal test run to catch obvious failures early
- `test-matrix` - Full test suite across multiple platforms and Python versions
- `integration` - Tests with real LLM providers (when credentials available)

### Test Failure Diagnostics (`test-failure-diagnostics.yml`)
Intelligent test failure analysis using Claude Code AI to provide detailed diagnostic information when CI fails.

**Features:**
- Automatically triggers when CI workflow fails on a PR
- Uses Claude Code to analyze test failures and provide root cause analysis
- Integrates with gh-workflow-peek extension for detailed log analysis
- Provides actionable recommendations for fixing failures
- Special handling for Terragon Labs tasks with Terry integration

**How it works:**
1. Monitors CI workflow runs for failures
2. When a failure is detected on a PR, retrieves the workflow logs
3. Uses Claude Code with a specialized diagnostic prompt to analyze failures
4. Posts a detailed diagnostic comment on the PR with:
   - Summary of failures
   - Root cause analysis
   - Specific fix recommendations
   - Commands to help resolve issues

**Requirements:**
- `CLAUDE_CODE_OAUTH_TOKEN` secret configured
- `GH_TOKEN_FOR_CLAUDE` secret (optional, for enhanced permissions)
- gh-workflow-peek extension (automatically installed)

### Claude Code Review (`claude-code-review.yml`)
Automated code review using Claude Code AI for pull requests.

**Features:**
- Runs automatically on new PRs
- Can be called after CI passes for additional review
- Rate limited to one review per PR per hour
- Provides feedback on code quality, bugs, performance, and security

**Trigger Methods:**
1. Automatically when a PR is opened
2. Called from CI workflow after all checks pass
3. Manual trigger via workflow_dispatch

### Claude Interactive (`claude.yml`)
Interactive Claude Code assistant triggered by @claude mentions in comments.

**Features:**
- Responds to @claude mentions in issues and PR comments
- Can run commands and make code changes
- Supports custom instructions and environment variables

### Claude Dispatch (`claude-dispatch.yml`)
Manual workflow for triggering Claude Code on specific PRs.

## Configuration

### Required Secrets

- `CLAUDE_CODE_OAUTH_TOKEN` - OAuth token for Claude Code authentication
- `GH_TOKEN_FOR_CLAUDE` - GitHub token with appropriate permissions for Claude
- `CODECOV_TOKEN` - Token for Codecov integration (optional)

### Permissions

Workflows require various GitHub permissions:
- `contents: read` - Read repository content
- `pull-requests: write` - Comment on PRs
- `issues: write` - Comment on issues
- `actions: read` - Read CI logs and workflow runs
- `checks: read` - Read check results
- `models: read` - Use GitHub Models for AI inference

## Integration with Terragon Labs

The workflows include special handling for Terragon Labs tasks:
- Detects Terry task URLs in PR descriptions
- Tags @terragon-labs in diagnostic comments
- Provides Terry-specific commands for task management
- Only triggers diagnostics for Terragon-initiated PRs

## Maintenance

### Adding New Diagnostic Capabilities

To enhance the test failure diagnostics:
1. Update the `direct_prompt` in `test-failure-diagnostics.yml`
2. Add new tools to `allowed_tools` if needed
3. Update the fallback comment template for common issues

### Customizing Claude Behavior

Claude's behavior can be customized through:
- `direct_prompt` - The main instruction prompt
- `custom_instructions` - Additional behavioral guidelines
- `allowed_tools` - Tools Claude can use (bash commands, etc.)
- `additional_permissions` - Extra GitHub permissions for Claude

### Rate Limiting

The Claude Code Review workflow implements rate limiting:
- One review per PR per hour
- Checks for existing Claude comments before running
- Skips duplicate reviews to conserve API usage

## Troubleshooting

### Claude Code Not Responding
1. Check if `CLAUDE_CODE_OAUTH_TOKEN` is properly configured
2. Verify workflow permissions are correct
3. Check Claude Code Action logs for authentication issues

### Test Diagnostics Not Triggering
1. Ensure the CI workflow name matches in `workflow_run` trigger
2. Verify the PR has the expected Terragon Labs task URL format
3. Check if the workflow run event type is 'pull_request'

### Missing Diagnostic Information
1. Verify gh-workflow-peek extension is installed
2. Check if Claude has necessary permissions (actions: read, checks: read)
3. Review the allowed_tools configuration

## Best Practices

1. **Keep prompts focused** - Specific prompts yield better results
2. **Limit tool access** - Only grant necessary tools to Claude
3. **Monitor API usage** - Use rate limiting to control costs
4. **Test locally** - Use act or similar tools to test workflow changes
5. **Version control** - Tag workflow versions for rollback capability
