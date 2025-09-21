# ScriptRAG Technical Changelog - Week of September 14-21, 2025

## Overview

This week's development focused on enhancing ScriptRAG's screenplay analysis capabilities, improving system reliability, and maintaining code quality. All changes align with our core mission of providing powerful, privacy-focused screenplay analysis tools.

## Screenplay Analysis Enhancements

### Scene Type Filtering (PR #505)

Added INT/EXT scene type filtering to improve location-based screenplay analysis:

- **Feature**: Scripts can now be analyzed by interior vs. exterior scenes
- **Benefit**: Writers can quickly understand location distribution in their screenplays
- **Technical**: Implemented in search queries while preserving Fountain format integrity
- **Testing**: 210 lines of tests ensure accurate scene type detection

### Character and Scene Analysis Stability

Multiple improvements to the analysis pipeline ensure more reliable screenplay processing:

- **Embedding Analysis Fix (PR #501)**: Corrected attribute access in the embedding analyzer, preventing errors during character relationship analysis
- **Cache Persistence (PR #488)**: Scene embeddings are now properly persisted to disk, improving analysis performance for large screenplays
- **Connection Handling (PR #487)**: Database connections for screenplay data are now more robust

## Technical Improvements for Screenplay Processing

### Resource Management

- **File Descriptor Leak Prevention (PR #503)**: Fixed resource leaks that could impact long screenplay analysis sessions
- **Directory Validation (PR #494)**: Improved validation for screenplay file directories using UUID-based race condition prevention

### Testing Infrastructure

- **Async Test Reliability (PR #500)**: Fixed timeout issues in CLI tests, ensuring screenplay analysis commands are properly tested
- **Mock Improvements (PRs #496-498)**: Enhanced test coverage for screenplay parsing edge cases

## Dependency Updates

Keeping dependencies current ensures ScriptRAG remains secure and compatible:

- pytest-cov updated to 7.0.0
- pytest-asyncio updated to 1.2.0
- claude-code-sdk updated to 0.0.22
- Type stub updates for better type checking

## Active Development

### Thread Safety in Search Engine (PR #504 - In Progress)

Currently addressing a race condition in concurrent screenplay searches. This fix will ensure reliable analysis when processing multiple scenes simultaneously.

## Code Quality Metrics

- **Test Coverage**: Maintained at 92%+ across all screenplay analysis modules
- **Type Safety**: All code passes MyPy type checking
- **Security**: Zero vulnerabilities in dependency scans
- **Linting**: All Python code meets Ruff standards

## Focus Areas for Next Week

1. **Complete thread safety improvements** for concurrent screenplay analysis
2. **Enhance character relationship extraction** algorithms
3. **Optimize scene graph connectivity** for better narrative flow analysis
4. **Continue improving Fountain format parsing** edge cases

## For Screenwriters

This week's improvements mean:

- **Better scene analysis**: New INT/EXT filtering helps understand location requirements
- **More reliable processing**: Fixed issues that could interrupt long analysis sessions
- **Faster analysis**: Improved caching reduces re-processing time
- **Maintained privacy**: All improvements preserve local-first, offline-capable architecture

## Contributing

ScriptRAG welcomes contributions that enhance screenplay analysis capabilities. Please review:

- [CLAUDE.md](CLAUDE.md) for coding guidelines
- [TO-NEVER-DO.md](TO-NEVER-DO.md) for project boundaries
- [TESTING.md](docs/TESTING.md) for testing requirements

All contributions should focus on screenplay analysis features, not production management or subjective quality judgments.

---

*ScriptRAG: Objective screenplay analysis that respects writer autonomy*

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
