# Large Python File Refactoring Recommendations

## Executive Summary

After analyzing the four largest Python files in the ScriptRAG codebase, I've identified several opportunities for modularization that would improve maintainability while respecting the established architecture patterns. The files are currently within acceptable limits but approaching thresholds where refactoring would be beneficial.

## File Analysis

### 1. connection_manager.py (656 lines)

**Current Structure:**

- `ConnectionPool` class (336 lines) - Thread-safe SQLite connection pooling
- `DatabaseConnectionManager` class (218 lines) - High-level connection management
- Module-level singleton management (71 lines)

**Refactoring Opportunities:**

#### Extract Connection Pool to Separate Module

- **Rationale**: The `ConnectionPool` class is self-contained with clear responsibilities
- **New structure**:

  ```text
  database/
  ├── connection_manager.py (320 lines) - Manager and singleton logic
  └── connection_pool.py (336 lines) - Pool implementation
  ```

- **Benefits**:
  - Clearer separation of concerns
  - Easier testing of pool logic in isolation
  - Better MCP tool compatibility (smaller files)

#### Extract Health Check Logic

- **Rationale**: Health check thread management (lines 249-296) could be a separate concern
- **New module**: `database/health_monitor.py` (~100 lines)
- **Benefits**:
  - Reusable health monitoring pattern
  - Cleaner pool implementation

### 2. settings.py (604 lines)

**Current Structure:**

- Single `ScriptRAGSettings` class with all configuration domains
- Multiple validators and loaders
- 6 distinct configuration sections (database, app, debug, logging, search, LLM, Bible)

**Refactoring Opportunities:**

#### Split into Domain-Specific Settings

- **Rationale**: Each configuration domain has distinct concerns
- **New structure**:

  ```text
  config/
  ├── settings.py (200 lines) - Base settings and composition
  ├── database_settings.py (~80 lines) - Database configuration
  ├── llm_settings.py (~100 lines) - LLM provider settings
  ├── logging_settings.py (~60 lines) - Logging configuration
  ├── search_settings.py (~80 lines) - Search/indexing settings
  └── loaders.py (~100 lines) - File loading utilities
  ```

- **Implementation approach**:

  ```python
  # settings.py
  from scriptrag.config.database_settings import DatabaseSettings
  from scriptrag.config.llm_settings import LLMSettings

  class ScriptRAGSettings(BaseSettings):
      database: DatabaseSettings = Field(default_factory=DatabaseSettings)
      llm: LLMSettings = Field(default_factory=LLMSettings)
      # ... compose other settings
  ```

- **Benefits**:
  - Domain experts can focus on specific configuration
  - Easier to add new configuration domains
  - Better testability of individual settings

### 3. client.py (602 lines)

**Current Structure:**

- `LLMClient` class managing multiple providers
- Complex completion/embedding methods with retry logic
- Provider selection and fallback mechanisms

**Refactoring Opportunities:**

#### Extract Request Handlers

- **Rationale**: Completion and embedding logic are distinct workflows
- **New modules**:

  ```text
  llm/
  ├── client.py (250 lines) - Core client and coordination
  ├── completion_handler.py (~180 lines) - Completion request handling
  └── embedding_handler.py (~180 lines) - Embedding request handling
  ```

- **Benefits**:
  - Cleaner separation of request types
  - Easier to add new request types (e.g., streaming)
  - Simpler testing of individual handlers

#### Extract Provider Selection Strategy

- **Rationale**: Provider selection logic (lines 134-194) could be a strategy pattern
- **New module**: `llm/selection_strategy.py` (~100 lines)
- **Benefits**:
  - Pluggable selection strategies
  - Easier to test selection logic

### 4. claude_code.py (520 lines)

**Current Structure:**

- Provider implementation with SDK interaction
- Complex async message handling
- Rate limiting and retry logic

**Refactoring Opportunities:**

#### Extract Message Processing

- **Rationale**: Message format conversion logic is complex and testable
- **New module**: `llm/providers/claude_message_processor.py` (~150 lines)
- **Benefits**:
  - Isolated message formatting logic
  - Reusable for other Claude-based providers

#### Extract SDK Wrapper

- **Rationale**: SDK interaction could be abstracted for better testing
- **New module**: `llm/providers/claude_sdk_wrapper.py` (~100 lines)
- **Benefits**:
  - Cleaner separation of SDK concerns
  - Easier mocking in tests

## Implementation Priority

Based on impact and risk assessment:

1. **High Priority** (Low risk, high benefit):
   - Extract `ConnectionPool` from `connection_manager.py`
   - Split completion/embedding handlers in `client.py`

2. **Medium Priority** (Moderate risk, good benefit):
   - Domain-specific settings modules
   - Message processor for Claude provider

3. **Low Priority** (Higher risk, moderate benefit):
   - Health check extraction
   - Provider selection strategy

## Migration Strategy

For each refactoring:

1. **Create new module** with extracted functionality
2. **Add comprehensive tests** for the new module
3. **Update imports** to use new module
4. **Maintain backwards compatibility** with deprecation warnings
5. **Remove old code** after validation period

## Testing Considerations

- All refactorings should maintain 90%+ code coverage
- Use the existing test infrastructure patterns
- Ensure cross-platform compatibility (Windows/macOS/Linux)
- Validate MCP tool functionality with new structure

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing imports | Maintain compatibility shims during transition |
| Test failures | Refactor tests alongside code |
| Configuration migration | Support both old and new config formats initially |
| MCP tool confusion | Update CLAUDE.md files in each module |

## Success Metrics

- All files under 500 lines (improved from current 600+ lines)
- Maintained or improved test coverage
- No performance degradation
- Cleaner module boundaries
- Better MCP tool navigation

## Next Steps

1. Review recommendations with team
2. Prioritize based on current development needs
3. Create feature branches for each refactoring
4. Implement incrementally with thorough testing

## Notes

- Current files are within acceptable limits but approaching thresholds
- Refactoring should preserve existing patterns and conventions
- Consider creating sub-agents for specific refactoring tasks
- Update module-level CLAUDE.md files after refactoring
