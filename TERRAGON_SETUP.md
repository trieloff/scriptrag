# Terragon Setup for ScriptRAG

This document explains how ScriptRAG is configured to work with Terragon's cloud sandboxes.

## Overview

When you run ScriptRAG in Terragon, the environment is automatically initialized using the
`terragon-setup.sh` script. This ensures your development environment is properly configured with
all dependencies and settings.

## Setup Scripts

### Primary Setup Script: `terragon-setup.sh`

The main setup script provides a comprehensive environment initialization with:

- **Timeout Protection**: Completes within 3 minutes to avoid Terragon's timeout
- **Error Handling**: Graceful error recovery and detailed logging
- **Dependency Installation**: Installs all project dependencies using `uv`
- **Virtual Environment**: Creates and activates a Python 3.11+ virtual environment
- **Database Initialization**: Sets up the SQLite database if needed
- **Environment Variables**: Configures from `.env.example` and Terragon variables

### Fallback Script: `terragon-setup-minimal.sh`

A minimal, ultra-resilient script that ensures basic functionality even if the main setup fails:

- Completes in under 2 minutes
- Installs only core dependencies
- Always exits successfully to prevent Terragon failures
- Provides basic functionality with graceful degradation

## Environment Variables

Configure these in your Terragon environment:

```bash
# Database configuration
DATABASE_URL=sqlite:///data/scriptrag.db

# LLM Configuration (if using external LLM)
OPENAI_API_KEY=your-api-key
LLM_API_URL=http://localhost:1234/v1  # For LMStudio

# Optional: Logging and debugging
LOG_LEVEL=INFO
DEBUG=false
```

## MCP Server Configuration

To use MCP servers with ScriptRAG, add this configuration to your Terragon environment:

```json
{
  "mcpServers": {
    "scriptrag": {
      "command": "python",
      "args": ["-m", "scriptrag.mcp_server"],
      "env": {
        "DATABASE_URL": "$DATABASE_URL"
      }
    }
  }
}
```

## Setup Process

1. **Automatic Execution**: Terragon automatically runs `terragon-setup.sh` when your sandbox starts
2. **Virtual Environment**: A Python virtual environment is created at `.venv/`
3. **Dependencies**: All project dependencies are installed via `uv` (faster than pip)
4. **Database**: SQLite database is initialized if it doesn't exist
5. **Verification**: Setup completion is marked in `.terragon-setup-complete`

## Troubleshooting

### Setup Timeout

If setup times out (3-minute limit):

- Check the logs for the last successful step
- Consider using `terragon-setup-minimal.sh` temporarily
- Remove unnecessary dependencies from `pyproject.toml`

### Dependency Installation Failures

If dependencies fail to install:

- The script will attempt base installation without extras
- Core functionality will still be available
- Check `logs/` directory for detailed error messages

### Database Issues

If database initialization fails:

- The script continues (database may already exist)
- Check `data/` directory permissions
- Manually run: `python -m scriptrag.database.init`

## Quick Commands

After setup completes, you can use these commands:

```bash
# Run the CLI
python -m scriptrag

# Start MCP server
python -m scriptrag.mcp_server

# Run tests
make test

# See all available commands
make help
```

## Performance Tips

1. **Pre-installed Tools**: Terragon provides Python 3, Node.js, and common tools
2. **Caching**: Dependencies are cached between runs when possible
3. **Parallel Installation**: `uv` installs dependencies in parallel for speed
4. **Minimal Setup**: Use the minimal script for faster iteration during development

## Security Notes

- Environment variables are encrypted and stored securely by Terragon
- Each user has their own isolated environment
- Secrets are never logged or exposed in setup output

## Advanced Configuration

### Custom Setup Steps

Add custom initialization to `terragon-setup.sh`:

```bash
# Example: Download custom data
if [ ! -f "data/custom_models.pkl" ]; then
    wget -q https://example.com/models.pkl -O data/custom_models.pkl
fi
```

### Conditional Setup

Use environment variables for conditional setup:

```bash
if [ "${ENABLE_GPU:-false}" = "true" ]; then
    uv pip install torch torchvision
fi
```

## Monitoring Setup

Check setup status:

```bash
# View setup completion marker
cat .terragon-setup-complete

# Check minimal setup fallback
ls -la .terragon-setup-minimal

# View setup logs
tail -f logs/setup.log
```

## Best Practices

1. **Keep It Fast**: Optimize for < 2.5 minute setup time
2. **Fail Gracefully**: Don't let setup failures block development
3. **Log Everything**: Use colored output for clarity
4. **Test Locally**: Run setup script locally before pushing
5. **Document Changes**: Update this file when modifying setup

## Contributing

When modifying setup scripts:

1. Test locally first: `./terragon-setup.sh`
2. Ensure idempotency (can run multiple times safely)
3. Add timeout checks for long operations
4. Update this documentation
5. Consider backwards compatibility

---

*Last updated: When setup scripts were created*
*Setup time target: < 3 minutes*
*Fallback time target: < 2 minutes*
