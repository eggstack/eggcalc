# Python API

eggcalc provides several evaluation functions with different trade-offs. Choose the right function for your use case.

## Choosing an Evaluation Function

| Use Case | Function | Why |
|----------|----------|-----|
| User input (forms, chat) | `evaluate_raw()` | Handles natural language, spaces, units |
| Pre-normalized input (you control format) | `evaluate()` | ~15x faster, skips normalization |
| Repeated queries (webapps) | `evaluate_cached()` | LRU cache, O(1) after first call |
| Untrusted input | `evaluate_with_timeout()` | Timeout protection against DoS |
| Async frameworks (FastAPI) | `evaluate_async()` | Runs in thread pool |

## Core Functions

### `evaluate_with_timeout(expression: str, timeout: float = 5.0) -> Any`

**Recommended for any untrusted input.** Provides timeout protection against long-running computations.

```python
from eggcalc import evaluate_with_timeout, TimeoutError

try:
    result = evaluate_with_timeout(user_expression, timeout=5.0)
except TimeoutError:
    result = "Calculation timed out"
```

### `evaluate(expression: str) -> Any`

Direct AST evaluation. **Expects pre-normalized input** (no spaces, no natural language words).

```python
from eggcalc import evaluate

result = evaluate("5+3")        # 8
result = evaluate("sin(1)+2")  # 2.8414...
result = evaluate("10")       # 10
```

**Does NOT work with:**
- Natural language: `evaluate("five plus three")` → `EvaluationError`
- Spaces: `evaluate("5 + 3")` → 8 (works but wasteful, use evaluate_raw)
- Units attached: `evaluate("30m")` → `EvaluationError`

### `evaluate_raw(expression: str) -> Any`

Full pipeline evaluation. Handles natural language, spaces, units, and mixed input. **Main function for user-facing applications.**

Internally calls `normalize_expression()` to convert natural language before evaluation.
Unit parsing is also spacing-tolerant, so expressions like `30 km / h in mph` and `5 in in cm` are handled the same as their compact forms.

```python
from eggcalc import evaluate_raw

result = evaluate_raw("5 + 3")          # 8
result = evaluate_raw("five plus three")  # 8
result = evaluate_raw("30m + 100ft")    # 60.48 m (with units)
result = evaluate_raw("sqrt(144)")     # 12
result = evaluate_raw("what is five plus three")  # 8
```

### `normalize_expression(expression: str, operators: dict | None = None, patterns: Mapping | None = None, skip_validation: bool = False) -> tuple[str, int]`

Normalize input without evaluating it. Public callers can pass only the expression; the built-in operator and pattern tables are used by default.

```python
from eggcalc import normalize_expression

normalized, exit_code = normalize_expression("five plus three")
# normalized == "5+3", exit_code == 0

normalized, exit_code = normalize_expression("30m + 100ft")
# normalized == "30*m+100*ft", exit_code == 0
```

### `evaluate_cached(expression: str) -> Any`

Like `evaluate_raw()` but with LRU caching (1024 entries). Best for repeated identical queries.
The cache is cleared when global constants or functions are registered, so
custom evaluator changes are visible to subsequent cached evaluations.

```python
from eggcalc import evaluate_cached

# First call: ~155 μs (compute + cache)
result = evaluate_cached("five plus three")

# Subsequent calls: ~0.1 μs (cache hit)
result = evaluate_cached("five plus three")
```

### `evaluate_async(expression: str) -> Awaitable[Any]`

Async version of `evaluate_raw()`. For use with async web frameworks (FastAPI, aiohttp, etc.).

```python
import asyncio
from eggcalc import evaluate_async

async def calculate(expr: str):
    return await evaluate_async(expr)

result = asyncio.run(calculate("5 + 3"))  # 8
```

## EggCalcApp Class

Thread-safe wrapper optimized for web applications. Each instance has isolated constants/functions and optional caching.

```python
from eggcalc import EggCalcApp

app = EggCalcApp(cache_size=1000, enable_cache=True)
app_without_storage = EggCalcApp(cache_size=0)  # Computes without storing results

# Basic usage - natural language works
result = app.calculate("five plus three")  # 8
result = app.calculate("30m + 100ft")      # 60.48 m

# Async support
result = await app.calculate_async("sqrt(144)")  # 12.0

# Instance-specific constants (don't affect other instances)
app.register_constant("myconst", 42)
result = app.calculate("myconst + 8")  # 50

# Instance-specific functions
app.register_function("double", lambda x: x * 2)
result = app.calculate("double(5)")  # 10

# Re-registering constants/functions clears this instance's cache.

# Cache management
print(app.cache_size)  # Number of cached entries
app.clear_cache()      # Clear all cache entries
```

**Why EggCalcApp instead of module-level functions?**

1. **Instance isolation**: Constants/functions registered on one instance don't affect others
2. **Caching**: Repeated queries use cache (O(1) lookup)
3. **Async support**: Built-in async methods for async frameworks
4. **Clean shutdown**: No global state to manage

## Configuration Functions

### `register_constant(name: str, value: float) -> None`

Register a custom constant globally (thread-safe).

```python
from eggcalc import register_constant, evaluate_raw

register_constant("earth_radius", 6371)
result = evaluate_raw("earth_radius")  # 6371
result = evaluate_raw("2 * pi * earth_radius")  # 40075...
```

### `register_function(name: str, func: Callable) -> None`

Register a custom function globally (thread-safe).

```python
from eggcalc import register_function, evaluate_raw

def circle_area(radius):
    import math
    return math.pi * radius ** 2

register_function("area", circle_area)
result = evaluate_raw("area(5)")  # 78.54...
```

### `load_user_config() -> None`

Load configuration from `eggcalc_config.py` in the working directory.

```python
from eggcalc import load_user_config

load_user_config()  # Loads CUSTOM_CONSTANTS, CUSTOM_FUNCTIONS, etc.
```

## Types

### `UnitValue`

Represents a numeric value with units. Returned when expressions involve units.

```python
from eggcalc import evaluate_raw, UnitValue

result = evaluate_raw("30m + 100ft")

if isinstance(result, UnitValue):
    print(f"Value: {result.value}, Unit: {result.unit}")
    # Value: 60.48, Unit: m

# UnitValue supports arithmetic with auto-conversion
uv1 = UnitValue(30, "m")
uv2 = UnitValue(100, "ft")
result = uv1 + uv2  # UnitValue(60.48, "m")

# Dimensionless values cannot be added to dimensional values
# UnitValue(30, "m") + UnitValue(5, None) raises ValueError
```

### `Memory`

Named memory registers for calculator-style operations. Internally uses a dictionary mapping register names to float values.

```python
from eggcalc import Memory, memory_store, memory_recall

# Memory is a TypedDict-like structure with named registers
mem = Memory()
mem["M"]  # Returns None if empty, float if value stored

# Practical usage via memory functions:
memory_store(42)      # Stores in "M" register by default
memory_recall()       # Returns 42
memory_add(8)         # Adds to M register: M = 50
memory_subtract(5)    # Subtracts from M register: M = 45
```

### `EvaluationError`

Raised when an expression is invalid or contains unsupported operations.

```python
from eggcalc import evaluate_raw, EvaluationError

try:
    result = evaluate_raw("import os")
except EvaluationError as e:
    print(f"Invalid expression: {e}")
```

### `TimeoutError`

Raised when evaluation exceeds the specified timeout.

```python
from eggcalc import evaluate_with_timeout, TimeoutError

try:
    result = evaluate_with_timeout("factorial(10000)", timeout=1.0)
except TimeoutError:
    print("Calculation timed out - possible DoS attempt")
```

## Utility Functions

### Unit Utilities

```python
from eggcalc import (
    normalize_unit,      # Normalize unit name to canonical form
    get_conversion_factor,  # Get conversion factor between units
    get_all_units,       # List all supported units
    is_unit,             # Check if text is a unit
)

normalize_unit("meters")        # "m"
normalize_unit("kilometers")     # "km"
get_conversion_factor("ft", "m")  # 0.3048
get_conversion_factor("km", "mi")  # 0.621371

is_unit("m")     # True
is_unit("xyz")   # False
```

## Memory Functions

Calculator-style memory operations (global state).

```python
from eggcalc import (
    memory_store,     # Store value (default M register)
    memory_recall,   # Recall from memory
    memory_add,      # Add to memory (M+)
    memory_subtract, # Subtract from memory (M-)
    memory_clear,    # Clear memory
    memory_list,     # List all registers
)

memory_store(42)        # Store 42
memory_recall()         # 42
memory_add(8)          # M+8, memory is now 50
memory_recall()         # 50
memory_subtract(5)     # M-5, memory is now 45
memory_clear()          # Clear all registers
```

Also available: `MR` (alias for recall), `MC` (alias for clear), `Mplus(x)`, `Mminus(x)`

## Variable Functions

User-defined variables (global state, thread-safe).

```python
from eggcalc import (
    setvar,       # Set variable value
    getvar,       # Get variable value
    delvar,       # Delete variable
    listvars,     # List all variables
    clearvars,    # Clear all variables
)

setvar("x", 10)
setvar("y", 20)
getvar("x")      # 10
listvars()       # {"x": 10, "y": 20}
delvar("x")
clearvars()      # Remove all variables
```

**Usage example:**

```python
from eggcalc import evaluate_raw

evaluate_raw('setvar("r", 5)')
evaluate_raw('pi * r ^ 2')    # 78.54... (circle area)
evaluate_raw('setvar("h", 10)')
evaluate_raw('pi * r ^ 2 * h')  # 785.4... (cylinder volume)
```

## Security Constants

Limits that protect against DoS attacks. Import and modify as needed.

```python
from eggcalc import (
    MAX_INPUT_LENGTH,     # 10000 - max input characters
    MAX_NESTING_DEPTH,    # 100 - max parentheses nesting
    MAX_EXPONENT,         # 10000 - max exponent value
    MAX_FACTORIAL,        # 1000 - max factorial input
    MAX_RESULT_VALUE,     # 1e308 - max result magnitude
    DEFAULT_CACHE_SIZE,   # 1024 - LRU cache size
)

print(f"Max input length: {MAX_INPUT_LENGTH}")
print(f"Max nesting depth: {MAX_NESTING_DEPTH}")
```

## Performance Notes

| Function | Speed (typical) | Notes |
|----------|-----------------|-------|
| `evaluate()` | ~10 μs/eval | Fastest, requires pre-normalized input |
| `evaluate_raw()` | ~155 μs/eval | Full pipeline, natural language support |
| `evaluate_cached()` | ~0.1 μs/eval (cached) | First call same as evaluate_raw |
| `EggCalcApp.calculate()` | ~0.3 μs/eval (cached) | Instance-level caching |
| `evaluate_async()` | Same as evaluate_raw | Runs in thread pool |

**For maximum performance with user input**: Cache parsed results using `evaluate_cached()` or `EggCalcApp`.
