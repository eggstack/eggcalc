# api.md - Public API Surface

## Package Entry Point

`__init__.py` re-exports all public functionality from the eggcalc package.

## Core Evaluation Functions

### `evaluate(expression: str) -> Any`

Evaluate a **pre-normalized expression** (no spaces, no natural language).

```python
result = evaluate("5+3")  # 8
```

For maximum performance when input format is controlled.

### `evaluate_raw(expression: str) -> Any`

Evaluate a raw expression with **spaces and/or natural language**.

```python
result = evaluate_raw("five plus three")  # 8
result = evaluate_raw("30m + 100ft")      # 60.48 m
```

Full normalization pipeline.

### `evaluate_cached(expression: str) -> Any`

Like `evaluate_raw()` but with **LRU caching** (1024 entries).

```python
result = evaluate_cached("five plus three")  # Cached
```

### `evaluate_async(expression: str) -> Awaitable[Any]`

Async version of `evaluate_raw()` for async web frameworks.

```python
result = await evaluate_async("5 + 3")
```

### `evaluate_with_timeout(expression: str, timeout: float = 5.0) -> Any`

Timeout-protected evaluation for **untrusted input**.

```python
result = evaluate_with_timeout("2 ** 1000000", timeout=1.0)
# Raises TimeoutError
```

## Webapp Wrapper

### `EggCalcApp`

Thread-safe wrapper with caching, optimized for long-running applications.

```python
app = EggCalcApp(cache_size=1000)
result = app.calculate("5 + 3")
result = await app.calculate_async("five plus two")
```

Features:
- Instance-isolated constants/functions
- LRU cache with configurable size
- Async support

### `Evaluator`

Low-level AST evaluator class for fine-grained control.

```python
evaluator = Evaluator()
evaluator.visit(ast.parse("5 + 3"))
```

Features:
- Direct AST node visitor pattern
- Fine-grained operator control
- Used internally by higher-level evaluate() functions

## Configuration Functions

### `register_constant(name: str, value: float) -> None`

Register a custom constant globally (thread-safe).

```python
register_constant("earth_radius", 6371)
```

### `register_function(name: str, func: Callable) -> None`

Register a custom function globally (thread-safe, call during init only).

### `get_default_evaluator() -> Evaluator`

Get the default Evaluator instance (for advanced use).

```python
evaluator = get_default_evaluator()
evaluator.CONSTANTS["custom"] = 123
```

```python
register_function("square", lambda x: x ** 2)
```

### `load_user_config() -> None`

Load configuration from `eggcalc_config.py` in working directory.

## Memory Functions

Calculator-style memory operations:

| Function | Description |
|----------|-------------|
| `memory_store(value, register="M")` | Store value |
| `memory_recall(register="M")` | Recall value |
| `memory_add(value, register="M")` | Add to memory (M+) |
| `memory_subtract(value, register="M")` | Subtract from memory (M-) |
| `memory_clear(register=None)` | Clear memory |
| `memory_list()` | List all registers |

## Variable Functions

User-defined variables:

| Function | Description |
|----------|-------------|
| `setvar(name, value)` | Set variable |
| `getvar(name)` | Get variable (returns 0 if not found) |
| `delvar(name)` | Delete variable |
| `listvars()` | List all variables |
| `clearvars()` | Clear all variables |

## Normalization Functions

### `normalize_expression(expression: str, operators: dict | None = None, patterns: Mapping[str, Pattern[str]] | None = None, skip_validation: bool = False) -> tuple[str, int]`

Normalize a natural language or mathematical expression into evaluator-ready Python syntax. `operators` and `patterns` default to the built-in `NORMALIZE` and `PATTERNS` configuration, so public callers can pass only the expression. Returns `(normalized_expression, exit_code)` where `exit_code` is 0 on success.

```python
normalized, exit_code = normalize_expression("five plus three")
# normalized = "5+3", exit_code = 0
normalized, exit_code = normalize_expression("30m + 100ft")
# normalized = "30*m+100*ft", exit_code = 0
normalized, exit_code = normalize_expression("30 km / h in mph")
# normalized = "convert(30*km/h,mph)", exit_code = 0
```

## Utility Functions

```python
normalize_unit("kilometers")          # "km" (canonical form)
get_conversion_factor("ft", "m")       # 0.3048
get_all_units()                        # ['A', 'B', 'BTU', ...]
is_unit("m")                           # True
get_unit_category("m")                 # "length"
are_units_compatible("m", "ft")        # True
FLOAT_EPSILON                          # 1e-10
```

## Security Constants

```python
MAX_EXPONENT = 10000      # Maximum exponent size
MAX_FACTORIAL = 1000       # Maximum factorial input
MAX_NESTING_DEPTH = 100    # Maximum expression nesting
MAX_RESULT_VALUE = 1e308   # Maximum result value
DEFAULT_CACHE_SIZE = 1024  # LRU cache size
```

## Input Limits

```python
MAX_INPUT_LENGTH = 10000   # Maximum input characters
MAX_NESTING_DEPTH = 100    # Maximum parentheses nesting
```

## Types

### `UnitValue`

```python
uv = UnitValue(5, "m")
print(f"{uv}")        # "5.0 m"
print(uv.value)      # 5.0
print(uv.unit)       # "m"
```

### `EvaluationError`

Raised for invalid expressions or unsupported operations.

### `TimeoutError`

Raised when `evaluate_with_timeout()` exceeds timeout.

### `Memory`

Memory register class (returned by `memory_*` functions return floats, but `Memory` class available for type hints).

## Performance Characteristics

| Method | Input Type | Typical Speed |
|--------|------------|---------------|
| `evaluate()` | Pre-normalized | ~10 μs/eval |
| `evaluate_raw()` | Natural language | ~155 μs/eval |
| `evaluate_cached()` | Repeated NL | ~0.1 μs/eval (after first) |
| `EggCalcApp.calculate()` | NL with caching | ~0.3 μs/eval (after first) |
