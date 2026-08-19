# api.md - Public API Surface

## Table of Contents

- [Package Entry Point](#package-entry-point)
- [Core Evaluation Functions](#core-evaluation-functions)
- [Webapp Wrapper](#webapp-wrapper)
- [Evaluator Class](#evaluator-class)
- [Configuration Functions](#configuration-functions)
- [Memory Functions](#memory-functions)
- [Variable Functions](#variable-functions)
- [Normalization Functions](#normalization-functions)
- [Utility Functions](#utility-functions)
- [Types](#types)
- [Security Constants](#security-constants)
- [Performance Characteristics](#performance-characteristics)

## Package Entry Point

`__init__.py` re-exports all public functionality from the eggcalc package.

```python
__version__ = "1.1.9"
__author__ = "David Bowman"
```

## Core Evaluation Functions

### `evaluate(expression: str) -> Any`

Evaluate a **pre-normalized Python-AST-compatible expression** (no natural language, no unit suffixes).

```python
result = evaluate("5+3")     # 8
result = evaluate("5 + 3")   # 8 (spaces are tolerated)
result = evaluate("2**10")   # 1024
```

Accepts valid Python math syntax. Rejects natural language and unit suffixes. This function never loads cwd-local config — it performs direct AST evaluation only.

### `evaluate_raw(expression: str) -> Any`

Evaluate a raw expression with **spaces and/or natural language**.

```python
result = evaluate_raw("five plus three")  # 8
result = evaluate_raw("30m + 100ft")      # 60.48 m
```

Full normalization pipeline: NL tokenization, unit preprocessing, number word conversion, then AST evaluation. Config loading is off by default; set `EGGCALC_LOAD_CONFIG=1` to enable lazy config loading.

### `evaluate_cached(expression: str) -> Any`

Like `evaluate_raw()` but with **LRU caching** (1024 entries). Uses an internal `_cached_normalize_and_evaluate` wrapper. Cache entries are removed on `ValueError`, `SyntaxError`, or `RecursionError`. Expressions containing random or side-effect functions bypass the cache.

```python
result = evaluate_cached("five plus three")  # Cached
```

### `evaluate_async(expression: str) -> Awaitable[Any]`

Async version of `evaluate_raw()` for async web frameworks. Runs evaluation in a thread pool via `asyncio.get_running_loop().run_in_executor(None, ...)`.

```python
result = await evaluate_async("5 + 3")
```

### `evaluate_with_timeout(expression: str, timeout: float = 5.0, allow_random: bool | None = None, allow_side_effects: bool | None = None) -> Any`

Timeout-protected evaluation for **untrusted input**. Uses `multiprocessing.Process` to run evaluation in a separate process that can be reliably terminated. Concurrency is bounded by `_EVAL_SPAWN_SEMAPHORE` (max 4 concurrent spawns, 10s acquire timeout).

```python
result = evaluate_with_timeout("2 ** 1000000", timeout=1.0)
# Raises TimeoutError
```

Args:
- `expression`: Raw expression string (NL, units, etc.)
- `timeout`: Maximum seconds (default `5.0`)
- `allow_random`: Whether to permit random functions in child process. `None` forwards parent's setting.
- `allow_side_effects`: Whether to permit state-mutating functions. `None` forwards parent's setting.

Raises `TimeoutError` on timeout, `EvaluationError` on invalid expressions.

## Webapp Wrapper

### `EggCalcApp`

Thread-safe wrapper with caching, optimized for long-running applications. Each instance has its own isolated evaluator with its own constants and functions.

```python
app = EggCalcApp(cache_size=1024)
result = app.calculate("5 + 3")
result = await app.calculate_async("five plus two")
app.register_constant("earth_radius", 6371)
app.register_function("square", lambda x: x ** 2)
```

Constructor:

```python
EggCalcApp(cache_size: int = DEFAULT_CACHE_SIZE, enable_cache: bool = True)
```

Methods:
- `calculate(expression: str) -> Any` — Thread-safe evaluation with optional caching
- `calculate_async(expression: str) -> Any` — Async version via thread pool executor
- `register_constant(name: str, value: float) -> None` — Instance-isolated constant registration
- `register_function(name: str, func: Any) -> None` — Instance-isolated function registration
- `clear_cache() -> None` — Clear the instance's LRU cache

## Evaluator Class

### `Evaluator`

Low-level AST evaluator class for fine-grained control. Not exported from `__init__.py` but accessible via `get_default_evaluator()`.

```python
evaluator = Evaluator()
evaluator.visit(ast.parse("5 + 3"))
```

Features:
- Direct `ast.NodeVisitor` pattern
- Fine-grained operator control
- Isolated constants, functions, and memory per instance
- Used internally by all higher-level evaluate functions

Public attributes:
- `CONSTANTS: dict[str, Any]` — Built-in and user-registered constants
- `FUNCTIONS: dict[str, Any]` — Built-in and user-registered functions
- `_memory: Memory` — Calculator memory registers
- `_user_variables: dict[str, Any]` — User-defined variables
- `_allow_random: bool` — Whether random functions are permitted
- `_allow_side_effects: bool` — Whether state-mutating functions are permitted

## Configuration Functions

### `register_constant(name: str, value: float) -> None`

Register a custom constant globally (thread-safe). Modifies the default evaluator's `CONSTANTS` dict and clears the global cache.

```python
register_constant("earth_radius", 6371)
```

### `register_function(name: str, func: Any) -> None`

Register a custom function globally (thread-safe). Must be called during init only. Validates that `name` is a valid Python identifier and `func` is callable. Clears the global cache.

```python
register_function("square", lambda x: x ** 2)
```

### `get_default_evaluator() -> Evaluator`

Get the default Evaluator instance (for advanced use).

```python
evaluator = get_default_evaluator()
evaluator.CONSTANTS["custom"] = 123
```

### `load_user_config() -> None`

Load configuration from `eggcalc_config.py` in working directory (thread-safe).

**Safety:** This function is NOT called by `import eggcalc`. Library import is side-effect-free. Config loading happens via:
- CLI: `maybe_load_cli_config()` in normalize.py (once at startup)
- API: `_ensure_config_loaded()` (lazy, only when `EGGCALC_LOAD_CONFIG=1` is set)
- MCP: Disabled entirely (`EGGCALC_NO_CONFIG=1`)

Library APIs (`evaluate_raw()`, `evaluate_cached()`, etc.) do **not** load cwd config by default. Set `EGGCALC_LOAD_CONFIG=1` or call `load_user_config()` explicitly.

Trust boundary note: This function imports `eggcalc_config` from the current working directory. In production deployments (e.g., MCP server), the CWD must be controlled by the deployment operator, not by end users.

## Memory Functions

Calculator-style memory operations. All functions proxy to the default evaluator's `_memory` instance.

| Function | Signature | Description |
|----------|-----------|-------------|
| `memory_store` | `(value: float, register: str = "M") -> float` | Store value in register |
| `memory_recall` | `(register: str = "M") -> float` | Recall value from register |
| `memory_add` | `(value: float, register: str = "M") -> float` | Add to memory (M+) |
| `memory_subtract` | `(value: float, register: str = "M") -> float` | Subtract from memory (M-) |
| `memory_clear` | `(register: str \| None = None) -> None` | Clear register (or all if `None`) |
| `memory_list` | `() -> dict[str, float]` | List all registers and values (always includes `"M"`) |

## Variable Functions

User-defined variables. All functions proxy to the default evaluator's `_user_variables` dict.

| Function | Signature | Description |
|----------|-----------|-------------|
| `setvar` | `(name: str, value: Any) -> Any` | Set variable. Raises `EvaluationError` if name invalid or store at capacity (oldest entry evicted). |
| `getvar` | `(name: str) -> Any` | Get variable (returns `0` if not found) |
| `delvar` | `(name: str) -> None` | Delete variable (no-op if not found) |
| `listvars` | `() -> dict[str, Any]` | List all variables |
| `clearvars` | `() -> None` | Clear all variables |

`setvar` validates that `name` is a non-empty string and a valid Python identifier. The variable store has a capacity limit; exceeding it evicts the oldest entry.

## Normalization Functions

### `normalize_expression(expression: str, operators: dict | None = None, patterns: Mapping[str, Pattern[str]] | None = None, skip_validation: bool = False) -> tuple[str, int]`

Normalize a natural language or mathematical expression into evaluator-ready Python syntax. `operators` and `patterns` default to the built-in `NORMALIZE` and `PATTERNS` configuration, so public callers can pass only the expression. Returns `(normalized_expression, exit_code)` where `exit_code` is `0` on success.

```python
normalized, exit_code = normalize_expression("five plus three")
# normalized = "5+3", exit_code = 0
normalized, exit_code = normalize_expression("30m + 100ft")
# normalized = "30*m+100*ft", exit_code = 0
normalized, exit_code = normalize_expression("30 km / h in mph")
# normalized = "convert(30*km/h,mph)", exit_code = 0
```

Exit codes: `0` = success, `1` = empty/invalid expression, `2` = input too long.

### `normalize_text(expression: str, operators: dict, patterns: Mapping[str, Pattern[str]]) -> str`

Lower-level function that applies filler word removal, number word conversion, unit preprocessing, and other NL-to-math transformations. `operators` and `patterns` are required (no defaults). Raises `ValueError` on empty expression or input exceeding `MAX_INPUT_LENGTH`.

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

### `normalize_unit(unit: str) -> str`

Return the canonical form of a unit (e.g., `"kilometers"` → `"km"`).

### `get_conversion_factor(from_unit: str, to_unit: str) -> float`

Return the numeric conversion factor between two compatible units.

### `get_all_units() -> list[str]`

Return a sorted list of all known unit symbols.

### `is_unit(text: str) -> bool`

Check if a string is a recognized unit alias.

### `get_unit_category(unit: str) -> str | None`

Return the category of a unit (e.g., `"length"`, `"mass"`), or `None` if unknown.

### `are_units_compatible(unit1: str | None, unit2: str | None) -> bool`

Check if two units belong to the same category and are convertible.

### `FLOAT_EPSILON`

Precision constant (`1e-10`) used for floating-point comparisons in unit conversions.

## Types

### `UnitValue`

```python
uv = UnitValue(5, "m")
print(f"{uv}")        # "5.0 m"
print(uv.value)      # 5.0
print(uv.unit)       # "m"
```

Returned by `evaluate()` and `evaluate_raw()` when a result includes a unit.

### `EvaluationError`

Raised for invalid expressions or unsupported operations. Subclass of `Exception`.

### `TimeoutError`

Raised when `evaluate_with_timeout()` exceeds timeout. Subclass of `Exception`.

### `Memory`

Memory register class. Thread-safe. Stores values in named registers (default register is `"M"`). Supports `store`, `recall`, `add`, `subtract`, `clear`, and `list_registers` methods.

## Security Constants

```python
MAX_EXPONENT = 10000       # Maximum exponent size
MAX_FACTORIAL = 1000       # Maximum factorial input
MAX_NESTING_DEPTH = 100    # Maximum expression nesting (parentheses)
MAX_RESULT_VALUE = 1e308   # Maximum result magnitude
MAX_RESULT_DIGITS = 10000  # Maximum integer result digits
DEFAULT_CACHE_SIZE = 1024  # LRU cache size
```

## Input Limits

```python
MAX_INPUT_LENGTH = 10000   # Maximum input characters (evaluator)
MAX_NORMALIZED_LENGTH = 20000  # Maximum normalized expression length (normalize)
MAX_NESTING_DEPTH = 100    # Maximum parentheses nesting
```

## Performance Characteristics

| Method | Input Type | Typical Speed |
|--------|------------|---------------|
| `evaluate()` | Pre-normalized | ~10 μs/eval |
| `evaluate_raw()` | Natural language | ~155 μs/eval |
| `evaluate_cached()` | Repeated NL | ~0.1 μs/eval (after first) |
| `EggCalcApp.calculate()` | NL with caching | ~0.3 μs/eval (after first) |
