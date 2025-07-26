# Development

## Setup

```bash
git clone https://github.com/trieloff/scriptrag.git
cd scriptrag
make setup-dev
```

## Testing

```bash
make test          # Run all tests
make test-fast     # Quick tests without coverage
make coverage      # Generate coverage report
```

## Code Quality

```bash
make lint          # Run all linters
make format        # Format code
make type-check    # Type checking
make security      # Security scans
```

## Documentation

```bash
make docs          # Build documentation
make docs-serve    # Serve docs locally
```

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create release PR
4. Tag release after merge
5. GitHub Actions handles PyPI publishing

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run quality checks
6. Submit a pull request

## Architecture

ScriptRAG follows a modular architecture:

- `config/`: Configuration management
- `database/`: SQLite with graph capabilities
- `models/`: Data models and types
- `parser/`: Fountain format parsing
- `llm/`: LLM integration
- `cli.py`: Command-line interface
