# Integration Test Guidelines

## Core Principle: NO MOCKING

**Integration tests verify real component interactions. Never mock dependencies in integration tests.**

## What Are Integration Tests?

Integration tests verify that multiple components work together correctly. They test:
- Real database operations
- Actual file I/O
- Complete CLI workflows
- End-to-end processing pipelines
- Real parser behavior with actual Fountain files

## The No-Mocking Rule

### ❌ NEVER Mock in Integration Tests

```python
# BAD - This defeats the purpose of integration testing
@patch("scriptrag.parser.FountainParser.parse")
def test_workflow(mock_parse):
    mock_parse.return_value = fake_script
    # This is NOT an integration test!
```

### ✅ Use Real Components

```python
# GOOD - Test real component interactions
def test_full_workflow():
    # Use real parser
    parser = FountainParser()
    script = parser.parse("tests/data/real_script.fountain")

    # Use real database
    db = Database(":memory:")  # In-memory but real SQLite
    db.store_script(script)

    # Test real queries
    scenes = db.query_scenes({"act": 1})
    assert len(scenes) > 0
```

## Integration Test Patterns

### 1. Database Integration Tests

```python
class TestDatabaseIntegration:
    @pytest.fixture
    def real_db(self, tmp_path):
        """Create a real temporary database."""
        db_path = tmp_path / "test.db"
        return Database(db_path)

    def test_script_storage_and_retrieval(self, real_db):
        """Test real database operations."""
        # Parse real Fountain file
        script = FountainParser().parse("tests/data/casablanca.fountain")

        # Store in real database
        real_db.store_script(script)

        # Query with real SQL
        scenes = real_db.query_scenes({"location": "Rick's"})
        assert all("Rick's" in s.location for s in scenes)
```

### 2. CLI Integration Tests

```python
def test_cli_full_workflow(tmp_path, runner):
    """Test complete CLI workflow with real operations."""
    # Initialize real project
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0

    # Import real script
    script_path = "tests/data/casablanca.fountain"
    result = runner.invoke(app, ["import", script_path])
    assert result.exit_code == 0

    # Query real data
    result = runner.invoke(app, ["list", "scenes"])
    assert "RICK'S CAFÉ" in result.stdout
```

### 3. Parser Integration Tests

```python
def test_parser_with_real_files():
    """Test parser with actual Fountain files."""
    parser = FountainParser()

    # Test various real scripts
    for script_file in Path("tests/data").glob("*.fountain"):
        script = parser.parse(script_file)

        # Verify real parsing results
        assert script.title
        assert len(script.scenes) > 0
        assert all(s.scene_number for s in script.scenes)
```

## What TO Mock (Only in Specific Cases)

### External Services Only

The ONLY acceptable mocks in integration tests are for external services that:
1. Cost money (paid APIs)
2. Have rate limits that would break CI
3. Are unavailable in CI environment
4. Are explicitly external to your system

```python
# ACCEPTABLE - Mock only external paid service
@patch("scriptrag.llm.providers.openai.OpenAI")
def test_workflow_with_llm(mock_openai):
    # Mock ONLY the external API
    mock_openai.return_value.complete.return_value = "analysis"

    # Everything else is real
    parser = FountainParser()  # Real parser
    db = Database(":memory:")  # Real database
    analyzer = SceneAnalyzer()  # Real analyzer

    # Test real workflow
    script = parser.parse("tests/data/script.fountain")
    db.store_script(script)
    analysis = analyzer.analyze(script)  # Uses mocked LLM
```

## Integration Test Best Practices

### 1. Use Fixtures for Setup

```python
@pytest.fixture
def test_project(tmp_path):
    """Create a real test project."""
    project = Project(tmp_path)
    project.initialize()
    return project
```

### 2. Use Real Test Data

```python
# Store real Fountain scripts in tests/data/
tests/data/
├── casablanca.fountain    # Full script for comprehensive tests
├── minimal.fountain       # Minimal valid script
├── complex.fountain       # Edge cases and complex formatting
└── malformed.fountain     # For error handling tests
```

### 3. Test Error Conditions with Real Scenarios

```python
def test_malformed_script_handling():
    """Test real error handling."""
    parser = FountainParser()

    with pytest.raises(FountainParseError) as exc:
        parser.parse("tests/data/malformed.fountain")

    # Verify real error details
    assert "line 42" in str(exc.value)
    assert "unexpected character" in str(exc.value)
```

### 4. Clean Up After Tests

```python
def test_file_operations(tmp_path):
    """Test with real file operations."""
    try:
        # Real file operations
        script_path = tmp_path / "test.fountain"
        script_path.write_text(fountain_content)

        # Test real processing
        result = process_script(script_path)
        assert result.success

    finally:
        # Clean up real files
        if script_path.exists():
            script_path.unlink()
```

## Common Integration Test Patterns

### Full Workflow Test

```python
def test_complete_screenplay_workflow(tmp_path):
    """Test entire screenplay processing pipeline."""
    # 1. Parse real screenplay
    parser = FountainParser()
    script = parser.parse("tests/data/casablanca.fountain")

    # 2. Store in real database
    db = Database(tmp_path / "test.db")
    db.store_script(script)

    # 3. Generate real embeddings (if available)
    if embeddings_available():
        embedder = Embedder()
        embeddings = embedder.generate(script)
        db.store_embeddings(embeddings)

    # 4. Query real data
    results = db.semantic_search("love and sacrifice")
    assert len(results) > 0

    # 5. Export real results
    exporter = Exporter()
    output = exporter.export(results, format="json")
    assert json.loads(output)  # Valid JSON
```

### Performance Integration Test

```python
def test_large_script_performance():
    """Test performance with real large scripts."""
    import time

    parser = FountainParser()
    start = time.time()

    # Parse real 120-page script
    script = parser.parse("tests/data/large_script.fountain")

    parse_time = time.time() - start
    assert parse_time < 2.0  # Should parse in under 2 seconds

    # Test real database performance
    db = Database(":memory:")
    start = time.time()

    db.store_script(script)

    store_time = time.time() - start
    assert store_time < 1.0  # Should store in under 1 second
```

## Anti-Patterns to Avoid

### ❌ Mocking Core Components

```python
# NEVER DO THIS in integration tests
@patch("scriptrag.database.Database")
@patch("scriptrag.parser.FountainParser")
def test_integration(mock_db, mock_parser):
    # This is a unit test, not an integration test!
```

### ❌ Using Fake Data

```python
# BAD - Not testing real integration
def test_integration():
    fake_script = {"title": "Fake", "scenes": []}
    # Not testing real parser output!
```

### ❌ Skipping Error Paths

```python
# BAD - Integration tests should test error handling too
def test_integration():
    try:
        result = process_script("script.fountain")
    except:
        pass  # Never skip errors in integration tests!
```

## Integration Test Checklist

Before writing an integration test, verify:

- [ ] No mocks of internal components
- [ ] Using real test data files
- [ ] Testing actual component interactions
- [ ] Verifying real error conditions
- [ ] Cleaning up after test completion
- [ ] Testing performance with real data
- [ ] Only mocking external paid services (if necessary)

## Remember

**Integration tests prove that your system actually works.** Mocking defeats this purpose. If you need to mock internal components, write a unit test instead.

When in doubt: **Don't mock it, test it!**
