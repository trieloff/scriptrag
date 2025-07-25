# ScriptRAG Documentation

This directory contains the documentation for the ScriptRAG project.

## Documentation Structure

```
docs/
├── README.md              # This file
├── index.md              # Documentation home page
├── getting-started/      # Quick start guides
│   ├── installation.md   # Installation instructions
│   ├── quickstart.md     # Quick start tutorial
│   └── configuration.md  # Configuration guide
├── user-guide/           # End-user documentation
│   ├── fountain-format.md    # Fountain format guide
│   ├── searching.md          # Search functionality
│   ├── scene-management.md   # Scene operations
│   └── mcp-integration.md    # MCP server usage
├── api/                  # API documentation
│   ├── rest-api.md       # REST API reference
│   ├── python-api.md     # Python API reference
│   └── mcp-api.md        # MCP server API
├── developer/            # Developer documentation
│   ├── architecture.md   # System architecture
│   ├── graph-schema.md   # Graph database schema
│   ├── contributing.md   # Contribution guidelines
│   └── testing.md        # Testing guide
├── tutorials/            # Step-by-step tutorials
│   ├── parse-script.md   # Parsing your first script
│   ├── graph-queries.md  # Graph query examples
│   └── llm-setup.md      # LLM configuration
└── examples/             # Example code and scripts
    ├── basic-usage.py    # Basic usage examples
    ├── advanced-queries.py   # Advanced queries
    └── sample-scripts/   # Sample fountain scripts
```

## Documentation Standards

### Markdown Format
All documentation is written in Markdown format with the following conventions:
- Use ATX-style headers (`#` for h1, `##` for h2, etc.)
- Code blocks should specify the language for syntax highlighting
- Include a table of contents for documents longer than 3 sections
- Use relative links for internal documentation references

### Code Examples
- All code examples should be tested and working
- Include necessary imports and setup code
- Provide both simple and advanced examples where appropriate
- Add comments explaining non-obvious code

### API Documentation
- Document all public classes, methods, and functions
- Include type hints in Python code examples
- Provide parameter descriptions and return value information
- Include examples of common use cases

## Building Documentation

The documentation is built using MkDocs with the Material theme.

### Local Development

```bash
# Install documentation dependencies
uv pip install -e ".[docs]"

# Serve documentation locally
mkdocs serve

# Build documentation
mkdocs build
```

The documentation will be available at `http://localhost:8000`.

### Auto-generated API Docs

API documentation is partially auto-generated from docstrings using mkdocstrings:

```bash
# Generate API documentation
python scripts/generate_api_docs.py
```

## Contributing to Documentation

1. **Writing New Documentation**
   - Create new `.md` files in the appropriate directory
   - Update the navigation in `mkdocs.yml`
   - Follow the documentation standards above

2. **Updating Existing Documentation**
   - Keep documentation in sync with code changes
   - Update examples when APIs change
   - Add clarifications based on user feedback

3. **Adding Examples**
   - Test all code examples before committing
   - Include both minimal and real-world examples
   - Explain the expected output

4. **Review Process**
   - Documentation changes should be reviewed like code
   - Check for clarity, accuracy, and completeness
   - Ensure examples work with the current version

## Documentation TODO

- [ ] Complete installation guide
- [ ] Write fountain format reference
- [ ] Create video tutorials
- [ ] Add troubleshooting guide
- [ ] Document common patterns
- [ ] Add performance tuning guide
- [ ] Create glossary of terms
- [ ] Add FAQ section

## Resources

- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [mkdocstrings](https://mkdocstrings.github.io/)
- [Markdown Guide](https://www.markdownguide.org/)