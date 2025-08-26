# Test Coverage Improvement Plan for ScriptRAG CLI

## Current State Analysis

### Coverage Summary

- **Total CLI Files**: 38 Python modules
- **Current Coverage**: ~20-55% average across CLI modules
- **Well-Tested Areas**: Formatters (>70%), Validators (>70%), Core commands (init, index, query)
- **Coverage Gaps**: Scene, Search, Watch, Pull, MCP commands; Async operations; Complex workflows

### Key Challenges

1. **Domain Model Complexity**: Models require specific initialization parameters
2. **Async Architecture**: Many commands use async/await patterns
3. **External Dependencies**: Git, file system, LLM providers, databases
4. **Integration Complexity**: Commands interact with multiple subsystems

## Phase 1: Foundation (Week 1)

**Goal**: Create robust testing infrastructure

### 1.1 Test Fixture Factories

Create factory patterns for common domain objects:

```python
# tests/factories/scene_factory.py
from factory import Factory, Faker
from scriptrag.parser import Scene

class SceneFactory(Factory):
    class Meta:
        model = Scene

    number = Faker('random_int', min=1, max=100)
    heading = Faker('sentence')
    content = Faker('text')
    original_text = Faker('text')
    content_hash = Faker('sha256')
```

### 1.2 Async Test Utilities

Create helpers for async command testing:

```python
# tests/utils/async_helpers.py
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def async_mock_api(api_class, **kwargs):
    """Context manager for mocking async APIs."""
    mock = AsyncMock(spec=api_class)
    for key, value in kwargs.items():
        setattr(mock, key, AsyncMock(return_value=value))
    yield mock
```

### 1.3 CLI Test Base Class

Standardize CLI test setup:

```python
# tests/cli/base.py
class CLITestBase:
    """Base class for CLI integration tests."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        self.tmp_path = tmp_path
        self.db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DB_PATH", str(self.db_path))
```

## Phase 2: Command Coverage (Week 2-3)

**Goal**: Achieve 80% coverage for all CLI commands

### 2.1 Scene Command Tests

- [ ] Test all CRUD operations (read, update, add, delete)
- [ ] Test bible file operations
- [ ] Test TV episode handling
- [ ] Test error scenarios
- [ ] Test JSON output formatting

### 2.2 Search Command Tests

- [ ] Test basic text search
- [ ] Test semantic search mode
- [ ] Test filters (project, type, season/episode)
- [ ] Test result limiting and pagination
- [ ] Test empty results handling

### 2.3 Watch Command Tests

- [ ] Test file system monitoring setup
- [ ] Test pattern matching
- [ ] Test auto-indexing trigger
- [ ] Test event handling
- [ ] Test graceful shutdown

### 2.4 Pull Command Tests

- [ ] Test Git repository pulling
- [ ] Test local directory sync
- [ ] Test branch selection
- [ ] Test conflict handling
- [ ] Test progress reporting

### 2.5 MCP Command Tests

- [ ] Test server initialization
- [ ] Test port configuration
- [ ] Test database connection
- [ ] Test protocol handling
- [ ] Test error responses

## Phase 3: Integration Testing (Week 4)

**Goal**: Test complete workflows end-to-end

### 3.1 Workflow Tests

Create tests for common user workflows:

1. **Project Setup Workflow**
   - init → pull → index → query

2. **Content Update Workflow**
   - watch → detect changes → auto-index → search

3. **Scene Management Workflow**
   - read scene → update → validate → commit

4. **Analysis Workflow**
   - index → analyze → generate embeddings → semantic search

### 3.2 Cross-Command Integration

Test command interactions:

- Scene changes trigger re-indexing
- Search results link to scene commands
- Query results format properly for all output types

## Phase 4: Edge Cases & Error Handling (Week 5)

**Goal**: Robust error handling and edge case coverage

### 4.1 Error Scenarios

- [ ] Database connection failures
- [ ] File permission errors
- [ ] Network timeouts
- [ ] Invalid input formats
- [ ] Concurrent access conflicts

### 4.2 Performance Tests

- [ ] Large file handling (>1000 scenes)
- [ ] Batch operation efficiency
- [ ] Memory usage under load
- [ ] Response time benchmarks

## Phase 5: Documentation & Maintenance (Week 6)

**Goal**: Sustainable testing practices

### 5.1 Testing Documentation

- [ ] Create testing guide for contributors
- [ ] Document fixture usage patterns
- [ ] Provide mock examples for each API
- [ ] Create troubleshooting guide

### 5.2 CI/CD Integration

- [ ] Add coverage gates (minimum 80%)
- [ ] Create coverage trend reporting
- [ ] Add performance regression tests
- [ ] Set up mutation testing

## Implementation Priority Matrix

| Component | Impact | Effort | Priority | Target Coverage |
|-----------|--------|--------|----------|-----------------|
| Scene Command | High | Medium | 1 | 85% |
| Search Command | High | Medium | 2 | 85% |
| Test Fixtures | High | Low | 3 | N/A |
| Async Utilities | High | Low | 4 | N/A |
| Query Command | Medium | Low | 5 | 90% |
| Watch Command | Medium | High | 6 | 75% |
| Pull Command | Medium | High | 7 | 75% |
| MCP Command | Low | High | 8 | 70% |
| E2E Workflows | High | High | 9 | 80% |
| Performance | Medium | Medium | 10 | N/A |

## Success Metrics

### Coverage Targets

- **Overall CLI Coverage**: 85% (from ~40%)
- **Critical Commands**: 90% (init, index, query, scene)
- **Utility Modules**: 95% (formatters, validators)
- **Integration Tests**: 80% of user workflows

### Quality Metrics

- **Test Execution Time**: < 30 seconds for unit tests
- **Flaky Test Rate**: < 1%
- **Mock Usage**: Minimal, prefer real objects where possible
- **Test Maintainability**: Each test < 50 lines

## Quick Wins (Can be done immediately)

1. **Add missing validator tests** - High coverage gain, low effort
2. **Test help messages** - Easy wins for all commands
3. **Test error messages** - Improves user experience
4. **Add JSON output tests** - Consistent formatting validation
5. **Create shared fixtures** - Reduces duplication

## Testing Best Practices

### DO

- ✅ Use factories for test data creation
- ✅ Test behavior, not implementation
- ✅ Keep tests focused and independent
- ✅ Use descriptive test names
- ✅ Mock at service boundaries
- ✅ Test error paths thoroughly

### DON'T

- ❌ Mock everything - use real objects when simple
- ❌ Test private methods directly
- ❌ Create complex test hierarchies
- ❌ Share state between tests
- ❌ Ignore flaky tests
- ❌ Skip error scenarios

## Next Steps

1. **Review and approve plan** with team
2. **Set up test infrastructure** (factories, utilities)
3. **Assign ownership** for each command's tests
4. **Create tracking dashboard** for coverage progress
5. **Schedule regular coverage reviews**

## Estimated Timeline

- **Week 1**: Infrastructure setup
- **Week 2-3**: Command coverage implementation
- **Week 4**: Integration testing
- **Week 5**: Edge cases and error handling
- **Week 6**: Documentation and cleanup

**Total Estimated Effort**: 6 weeks (1 developer) or 3 weeks (2 developers)

## ROI Analysis

### Benefits

- **Reduced Bug Rate**: ~40% reduction in production issues
- **Faster Development**: ~30% reduction in debugging time
- **Improved Confidence**: Safer refactoring and feature additions
- **Better Documentation**: Tests serve as usage examples
- **Quality Gates**: Prevent regressions

### Investment

- **Development Time**: 120-240 hours
- **Maintenance**: ~10% of feature development time
- **CI Resources**: Minimal increase

### Payback Period

Expected ROI positive after 3 months due to reduced bug fixes and faster feature velocity.

---

*This plan is a living document and should be updated as implementation progresses.*
