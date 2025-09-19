# Testing Guidelines

## Testing Philosophy
- **Unit tests** for pure functions and business logic
- **Integration tests** for end-to-end workflows
- **Mock external dependencies** (databases, APIs, file system)
- **Aim for 80%+ coverage** on core business logic

## Running Tests

```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_specific.py

# Run with markers
pytest -m "not slow"        # Skip slow tests
pytest -m "unit"           # Only unit tests
pytest -m "integration"    # Only integration tests

# Coverage report
pytest --cov-report=html    # Generate HTML report
open htmlcov/index.html     # View coverage report
```

## Test Structure

### File Naming
- Test files: `test_*.py` or `*_test.py`
- Test functions: `test_*`
- Test classes: `Test*`

### Test Categories (use markers)
```python
import pytest

@pytest.mark.unit
def test_pure_function():
    """Test isolated unit of logic"""
    pass

@pytest.mark.integration
def test_end_to_end_workflow():
    """Test complete user workflow"""
    pass

@pytest.mark.slow
def test_expensive_operation():
    """Mark tests that take >1 second"""
    pass
```

### Mocking Best Practices

```python
# Use pytest-mock for cleaner mocking
def test_with_mock(mocker):
    mock_api = mocker.patch('optipanel.adapters.ibkr.tws_fetcher.RealTwsFetcher')
    mock_api.return_value.features_for_symbols.return_value = {...}

    # Test code here

    mock_api.assert_called_once()
```

### Async Testing
```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result == expected
```

## Coverage Goals

### Priority 1 (Must Have 90%+):
- Core business logic (`engine/`, `runtime/`)
- Data processing (`setups/`, `alerts/`)
- Critical adapters (`adapters/ibkr/`)

### Priority 2 (Should Have 70%+):
- Services (`services/`)
- CLI commands (`cli/`)
- Configuration (`config/`)

### Priority 3 (Nice to Have 50%+):
- UI rendering (`ui/`, `battlefield/`)
- Utility modules

## Test Data Management

### Use fixtures for common test data:
```python
@pytest.fixture
def sample_features():
    return {
        "AAPL": {"last": 150.0, "dma20": 145.0, ...},
        "MSFT": {"last": 300.0, "dma20": 295.0, ...}
    }

def test_function(sample_features):
    result = process_features(sample_features)
    assert result["AAPL"]["score"] > 50
```

## What NOT to Test
- Third-party library internals
- Simple getters/setters without logic
- Configuration constants
- Obvious code (like `return x + y`)

## When Tests Fail
1. **Fix the test first** - ensure test is correct
2. **Fix the code** - make test pass
3. **Refactor** - improve code while keeping tests green
4. **Never disable tests** - fix or remove broken tests

## CI/CD Integration
- All tests must pass before merge
- Coverage cannot decrease below current level
- Slow tests run nightly, fast tests on every commit