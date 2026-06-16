# Testing Guidelines

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=eggcalc --cov-report=term-missing

# Run specific test file
python -m pytest tests/test_tokenization.py -v

# Run specific test class
python -m pytest tests/test_tokenization.py::TestMultiDigitSubtraction -v
```

## Test Files

| File | Purpose |
|------|---------|
| `test_clicalc.py` | Core functional tests |
| `test_security_fuzz.py` | Security and fuzz tests |
| `test_tokenization.py` | Tokenization edge cases |
| `test_math_identities.py` | Mathematical laws |
| `test_math_edge_cases.py` | Math edge case tests |
| `test_normalize.py` | Normalization tests |
| `test_exact.py` | Unicode text primitives |
| `test_cli_text.py` | CLI text tools |
| `test_mcp_server.py` | MCP server integration |
| `test_mcp_tools_new.py` | MCP integration tests for new tools |
| `test_build_single.py` | Build script tests |
| `test_repl_and_cli.py` | REPL and CLI integration tests |
| `test_production_review_2026_07_b.py` | Production review tests |
| `test_unit_namespace.py` | Unit namespace tests |
| `test_patch_tools.py` | Patch apply/summary tools tests |
| `test_text_replace_check.py` | Text replacement check tests |
| `test_line_range.py` | Line range extract/compare tests |
| `test_path_compare.py` | Path comparison tests |
| `test_path_scope.py` | Path scope check tests |
| `test_shell_tools.py` | Shell split/quote/compare tests |
| `test_markdown_tools.py` | Markdown structure tests |
| `test_config_validation.py` | dotenv/INI validation tests |
| `test_unicode_policy.py` | Unicode policy/canonicalization tests |
| `test_tool_inventory.py` | Tool registry consistency tests |
| `test_golden_fixtures.py` | Golden fixture tests |
| `test_cargo_inspect.py` | Cargo.toml inspection tests |
| `test_prompt_inspect.py` | Prompt injection detection tests |
| `test_identifier_table.py` | Identifier table inspection tests |
| `test_version_constraint.py` | Version constraint tests |
| `conftest.py` | Shared fixtures |

## API Usage

### Use `evaluate()` for:
- Pure math expressions (`"5 + 3"`, `"2**10"`)
- Function calls (`"sin(0)"`, `"sqrt(16)"`)
- Constants (`"pi"`, `"e"`)

### Use `run()` or CLI for:
- Natural language (`"five plus three"`)
- Unit expressions (`"30m + 100ft"`)
- Complex expressions with units

### Use `convert_temperature()` for:
- Direct temperature conversions with offset handling
- `convert_temperature(32.0, "F", "C")` returns `0.0`

### Use `get_conversion_factor()` for:
- Prefixed unit conversion factors
- `get_conversion_factor("kN", "N")` returns `1000.0`

## Helper Functions

```python
def get_value(result):
    """Extract numeric value from result, handling UnitValue."""
    if isinstance(result, UnitValue):
        return result.value
    return result

def val(expr):
    """Evaluate and extract value, handling UnitValue."""
    result = evaluate(expr)
    if isinstance(result, UnitValue):
        return result.value
    return result
```

## Testing Patterns

### Parametric Tests
```python
@pytest.mark.parametrize("expr,expected", [
    ("90-1", 89),
    ("100-10", 90),
    ("1000-1", 999),
])
def test_multi_digit_subtraction(self, expr, expected):
    result = evaluate(expr)
    assert abs(get_value(result) - expected) < 1e-10
```

### Class-Based Organization
```python
class TestMultiDigitSubtraction:
    """Test subtraction with multi-digit numbers."""

    def test_simple_subtraction(self):
        result = evaluate("90-1")
        assert abs(get_value(result) - 89) < 1e-10
```

### Testing Temperature Conversions
```python
def test_fahrenheit_to_celsius_exact_freezing(self):
    """Test 32F to C equals exactly 0.0C."""
    from eggcalc.units import convert_temperature
    result = convert_temperature(32.0, "F", "C")
    assert abs(result - 0.0) < 1e-9
```

### Testing Unit Conversion Factors
```python
def test_kilonewton_to_newton(self):
    """Test kN to N conversion factor is 1000.0."""
    from eggcalc import get_conversion_factor
    result = get_conversion_factor("kN", "N")
    assert result == 1000.0
```

### Testing Spacing-Sensitive Parsing
When unit parsing is involved, use parametrized probe cases that vary whitespace
with single spaces, repeated spaces, and tabs. Assert both the normalized text
and the evaluated `UnitValue` so spacing regressions cannot silently collapse
distinct unit products into prefixed units.

```python
@pytest.mark.parametrize("expr", ["5 N m", "5 N   m", "5\tN\tm"])
def test_spaced_unit_product(self, expr):
    normalized, code = normalize_expression(expr, NORMALIZE, PATTERNS)
    assert code == 0
    assert normalized == "5*N*m"
```

### Testing Unicode Script Detection
```python
def test_digits_return_other(self):
    """Test that ASCII digits return 'Other'."""
    from eggcalc.exact import unicode_script
    assert unicode_script("0") == "Other"
```

## Common Issues

### UnitValue Return Type
Many operations return `UnitValue` instead of plain numbers:
```python
result = evaluate("5 + 3")
# May return UnitValue(8, None) instead of 8
```

Always use `get_value()` or `val()` to extract the numeric value.

### API Mismatch
Using `evaluate()` for NL or unit expressions will fail:
```python
evaluate("five plus three")  # SyntaxError - not valid Python
evaluate("30m + 100ft")      # SyntaxError - m, ft not valid
```

Use `run()` for these cases.

### Temperature Conversion
Temperature conversions require `convert_temperature()` for proper offset handling:
```python
from eggcalc.units import convert_temperature
result = convert_temperature(32.0, "F", "C")  # Returns 0.0
```

### Prefixed Units
Some prefixed units (like "kg") have compound meanings. Use `get_conversion_factor()` for prefix conversions:
```python
from eggcalc import get_conversion_factor
factor = get_conversion_factor("kN", "N")  # Returns 1000.0
```
