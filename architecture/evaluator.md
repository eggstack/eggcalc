# evaluator.py — AST-Based Expression Evaluation

2961 lines. Provides a **secure** way to evaluate mathematical expressions without using `eval()`. Uses Python's `ast` module to parse and evaluate expressions safely.

## Table of Contents

- [Overview](#overview)
- [Key Exports](#key-exports)
- [Security Architecture](#security-architecture)
- [AST Node Handlers](#ast-node-handlers)
- [Constants](#constants)
- [Limits and Safeguards](#limits-and-safeguards)
- [Evaluation Functions](#evaluation-functions)
- [Evaluator Class](#evaluator-class)
- [Memory System](#memory-system)
- [Variable Storage](#variable-storage)
- [Safe Math Functions](#safe-math-functions)
- [Complex Number Support](#complex-number-support)
- [EggCalcApp](#eggcalcapp)
- [Unit Handling](#unit-handling)
- [Module Dependencies](#module-dependencies)

## Overview

The `evaluator` module is the **core computation engine**. It:
- Parses Python AST (Abstract Syntax Tree) instead of using eval
- Supports arithmetic, trigonometric, logarithmic functions
- Handles complex numbers, memory operations, variables
- Provides caching, async evaluation, and timeouts
- Enforces security via an AST node allowlist and whitelisted functions

## Key Exports

```python
from eggcalc.evaluator import (
    evaluate,           # Direct AST evaluation (pre-normalized input only)
    evaluate_raw,       # Evaluate with NL normalization
    evaluate_cached,    # LRU cached evaluation
    evaluate_async,     # Async evaluation (thread pool)
    evaluate_with_timeout,  # Evaluation in child process with timeout
    EvaluationError,    # Exception class
    TimeoutError,       # Timeout exception
    EggCalcApp,         # Webapp class with instance isolation and caching
    get_default_evaluator,
    register_constant,  # Add user constants (thread-safe)
    register_function,  # Add user functions (thread-safe)
    load_user_config,   # Load eggcalc_config.py (not called at import time)
    # Memory functions (proxy to default evaluator)
    memory_store, memory_recall, memory_add, memory_subtract,
    memory_clear, memory_list,
    # Variable functions (proxy to default evaluator)
    setvar, getvar, delvar, listvars, clearvars,
)

# Internal (not exported, available if needed):
#   load_user_config_extended() — loads CUSTOM_NUMBER_WORDS and CUSTOM_OPERATOR_WORDS
#   configure_default_evaluator() — updates allow_random/allow_side_effects at runtime
```

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Security Model                          │
├─────────────────────────────────────────────────────────────┤
│  Input: "5 + 3 * 2"                                         │
│      ↓                                                      │
│  ast.parse() → AST tree (validates syntax)                  │
│      ↓                                                      │
│  _validate_node() → checks against _ALLOWED_AST_TYPES       │
│      ↓                                                      │
│  Evaluator.visit() → traverses AST                          │
│      ↓                                                      │
│  Only whitelisted functions/operators allowed                │
│      ↓                                                      │
│  Output: 11                                                 │
└─────────────────────────────────────────────────────────────┘

NOT eval() — uses AST for safety
```

The `_ALLOWED_AST_TYPES` frozenset is built at import time by walking known-safe expression patterns and recording every reachable `ast.expr` subclass. `_validate_node` rejects any node type not in this set. The allowed types include `ast.Expression`, `ast.Constant`, `ast.Name`, `ast.Call`, `ast.BinOp`, `ast.UnaryOp`, `ast.Attribute`, and all `ast.operator`/`ast.unaryop`/`ast.expr_context`/`ast.cmpop`/`ast.boolop` subclasses.

### Config Loading Safety

`import eggcalc` does NOT trigger `load_user_config()`. Config loading is handled by three paths:

1. **CLI path:** `maybe_load_cli_config()` in normalize.py — called once at CLI startup
2. **API path:** `_ensure_config_loaded()` — lazy loading, only when `EGGCALC_LOAD_CONFIG=1` is set
3. **MCP path:** Blocked by `EGGCALC_NO_CONFIG=1` env var set before imports

Library APIs (`evaluate_raw()`, `evaluate_cached()`, etc.) do **not** load cwd config by default. Set `EGGCALC_LOAD_CONFIG=1` or call `load_user_config()` explicitly.

The `load_user_config()` function checks two guards (`_mcp_mode` and `EGGCALC_NO_CONFIG`) and sets `_config_loaded = True` on both early-return and normal paths to prevent re-entry.

## AST Node Handlers

The `Evaluator` class implements `visit_*` methods for each AST node type:

| Node Type | Handler | Operation |
|-----------|---------|-----------|
| `ast.Constant` | visit_Constant | Literals (numbers, strings, complex) |
| `ast.BinOp` | visit_BinOp | +, -, *, /, //, %, **, &, \|, ^, <<, >> |
| `ast.UnaryOp` | visit_UnaryOp | +, -, ~ |
| `ast.Call` | visit_Call | Function calls (whitelist-enforced) |
| `ast.Name` | visit_Name | Variables/constants (lookup order: units → constants → functions → user vars) |
| `ast.Attribute` | visit_Attribute | Attribute access (`.real`, `.imag`, `.conjugate()` only) |

**Operator semantics note:** `^` is dispatched as **bitwise XOR** (`ast.BitXor`) via Python AST semantics. The normalize pipeline (`_rewrite_calculator_caret()` in `normalize.py`) rewrites `^` to `**` before `evaluate()` is called, so user-facing calculator syntax treats `^` as exponentiation. Direct `evaluate()` calls always treat `^` as XOR.

### Floor Division and Modulo with Units

Same-unit operations have dimensional semantics:

| Operation | Same-unit result | Cross-unit result |
|-----------|-----------------|-------------------|
| `//` (floor div) | Dimensionless quotient | `EvaluationError` |
| `%` (modulo) | Dimensioned remainder in divisor unit | `EvaluationError` |

```python
evaluate_raw("5m % 2m")   # → 1 m (remainder in divisor unit)
evaluate_raw("7m // 2m")  # → 3 (dimensionless quotient)
evaluate_raw("5m % 2s")   # → EvaluationError
```

The shared helpers `_floor_divide_quantities()` and `_modulo_quantities()` in `units.py` implement this logic.

**Forbidden node types** (raise `EvaluationError`):
- `ast.Compare` — comparison operators
- `ast.BoolOp` — boolean operations
- `ast.Subscript` — list/dict indexing
- `ast.List`, `ast.Dict`, `ast.Set` — container literals
- `ast.ListComp`, `ast.DictComp` — comprehensions

The `visit_Name` lookup order is:
1. `UNIT_ALIASES` (unit names; common short names like `g`, `h`, `k` shadow constants)
2. `CONSTANTS` (physical constants; `r`/`R` for gas constant, long forms like `planck`)
3. `FUNCTIONS` (rejected as "used without arguments")
4. Per-instance user variables (`_user_variables`)

The `visit_Call` method handles special cases for `temp()` (temperature unit preservation) and `convert()` (UnitValue passthrough), and enforces unit policies via the centralized `UnitPolicy` dispatcher. User-registered functions default to dimensionless-only behavior.

## Constants

Built-in physical and mathematical constants (defined in `Evaluator.CONSTANTS`):

| Name | Value | Description |
|------|-------|-------------|
| `pi` | 3.141592653589793 | π |
| `e` | 2.718281828459045 | e |
| `tau` | 6.283185307179586 | 2π |
| `i` / `j` | 1j | Imaginary unit |
| `na` / `avogadro` / `avogadros` | 6.02214076e23 | Avogadro number |
| `r` / `R` / `gasconstant` / `idealgasconstant` | 8.314462618 | Gas constant (J/mol·K) |
| `planck` / `planckconstant` | 6.62607015e-34 | Planck constant (J·s) |
| `k` / `boltzmann` / `boltzmannconstant` | 1.380649e-23 | Boltzmann constant (J/K) |
| `c` / `c0` / `speedoflight` / `speedoflightvacuum` | 299792458 | Speed of light (m/s) |
| `elementarycharge` / `echarge` | 1.602176634e-19 | Elementary charge (C) |
| `f` / `faraday` / `faradayconstant` | 96485.33212 | Faraday constant (C/mol) |
| `u` / `amu` / `atomicmassunit` | 1.66053906660e-27 | Atomic mass unit (kg) |
| `epsilon0` / `vacuumpermittivity` | 8.8541878128e-12 | Vacuum permittivity (F/m) |
| `mu0` / `vacuumpermeability` | 1.25663706212e-6 | Vacuum permeability (H/m) |
| `standardgravity` | 9.80665 | Standard gravity (m/s²) |
| `G` / `gravitationalconstant` | 6.67430e-11 | Gravitational constant (N·m²/kg²) |
| `rydberg` / `rydbergconstant` | 10973731.568160 | Rydberg constant (m⁻¹) |
| `stefan` / `stefanboltzmann` | 5.670374419e-8 | Stefan-Boltzmann constant (W/m²·K⁴) |
| `planckbar` / `hbar` / `reducedplanck` | 1.054571817e-34 | Reduced Planck constant (J·s) |
| `me` / `electronmass` | 9.1093837015e-31 | Electron mass (kg) |
| `mp` / `protonmass` | 1.67262192369e-27 | Proton mass (kg) |
| `mn` / `neutronmass` | 1.67493e-27 | Neutron mass (kg) |
| `re` / `electronradius` | 2.8179403262e-15 | Classical electron radius (m) |
| `alpha` / `finestructure` | 7.2973525693e-3 | Fine structure constant |
| `wien` / `wienconstant` | 2.897771955e-3 | Wien displacement constant (m·K) |

**Note:** `inf` and `nan` are intentionally excluded — they cannot be accessed as bare names, preventing accidental NaN/inf propagation. Short constant names like `c`, `h`, `g`, `k` are shadowed by `UNIT_ALIASES` (hour, planck constant, gram, kelvin, etc.); use long forms (`speedoflight`, `planck`, `standardgravity`, `boltzmann`) for clarity. `r`/`R` are accessible as gas constant (no collision with Rankine, which uses `Ra`).

## Limits and Safeguards

| Limit | Value | Purpose |
|-------|-------|---------|
| `MAX_EXPONENT` | 10000 | Prevent power DoS (`_safe_pow`) |
| `MAX_FACTORIAL` | 1000 | Prevent factorial DoS (`_safe_factorial`) |
| `MAX_NESTING_DEPTH` | 100 | Prevent stack overflow (`Evaluator.visit`) |
| `MAX_RESULT_VALUE` | 1e308 | Prevent float overflow |
| `MAX_RESULT_DIGITS` | 10000 | Prevent integer result DoS |
| `MAX_SHIFT_COUNT` | 50000 | Prevent bit-shift DoS |
| `MAX_INPUT_LENGTH` | 10000 | Max characters in expression string |
| `MAX_USER_VARIABLES` | 1000 | Cap on `setvar` entries per evaluator |
| `DEFAULT_CACHE_SIZE` | 1024 | LRU cache entry count |
| `MAX_CACHE_BYTES` | 64 MB | Soft cap for global `_cache` size |
| `MAX_ORPHANED_PROCESSES` | 256 | Bounded set for MCP orphan cleanup |

Additional per-function limits:
- `_safe_pow`: rejects `abs(exp) > MAX_EXPONENT`; uses int arithmetic for `base.is_integer()` and `abs(exp) > 300`
- `_safe_factorial`: rejects `n < 0` or `n > MAX_FACTORIAL`
- `_is_prime`: rejects `n > 10**12`
- `_prime_factors`: rejects `n > 10**12`
- `_next_prime` / `_prev_prime`: rejects `n > 10**12` and search exceeded 10000 iterations
- `_perm` / `_comb`: rejects input `> 10000`
- `_bitlshift_safe`: pre-checks `a.bit_length() + b > MAX_RESULT_DIGITS * 3`
- `_check_result_size`: rejects NaN, inf, `abs > MAX_RESULT_VALUE`, and int digit count `> MAX_RESULT_DIGITS`

## Evaluation Functions

### `evaluate(expression: str) -> Any`
Direct AST evaluation. Expects valid Python-AST-compatible syntax. **Does not** load cwd-local config. Rejects natural language and unit suffixes.

```python
evaluate("5 + 3")          # → 8
evaluate("sin(pi/2)")      # → 1.0
evaluate("sqrt(2)")        # → 1.414...
evaluate("2**10")          # → 1024
```

### `evaluate_raw(expression: str) -> Any`
Evaluates with NL normalization (calls `normalize_expression` first). Handles natural language and unit conversions.

```python
evaluate_raw("five plus three")  # → 8
evaluate_raw("30m + 100ft")     # → UnitValue(60.48, "m")
```

### `evaluate_cached(expression: str) -> Any`
Cached evaluation for repeated identical expressions. Uses a module-level `OrderedDict`-based LRU cache (not `functools.lru_cache`) with 1024 entries and a 64 MB soft cap. Expressions containing random or side-effect functions bypass the cache. On `ValueError`/`SyntaxError`/`RecursionError`, the cache entry is removed before re-raising.

```python
evaluate_cached("5 + 3")           # → 8 (cached)
evaluate_cached("five plus three") # → 8 (cached, NL normalized first)
```

### `evaluate_async(expression: str) -> Any`
Async evaluation for use with async web frameworks. Runs evaluation in a thread pool executor to avoid blocking the event loop.

```python
result = await evaluate_async("5 + 3")           # Awaitable result
result = await evaluate_async("five plus three")  # NL also supported
```

### `evaluate_with_timeout(expression: str, timeout: float = 5.0, allow_random: bool | None = None, allow_side_effects: bool | None = None) -> Any`
Evaluation with timeout in seconds. Uses `multiprocessing.Process` to run evaluation in a separate process that can be reliably terminated. Concurrency is bounded by `_EVAL_SPAWN_SEMAPHORE` (4 slots, 10s acquire timeout). Raises `TimeoutError` on timeout, `EvaluationError` on invalid expressions.

```python
result = evaluate_with_timeout("5 + 3", timeout=5.0)
result = evaluate_with_timeout("five plus three", timeout=1.0)
```

## Evaluator Class

```python
class Evaluator(ast.NodeVisitor):
    def __init__(
        self,
        allow_random: bool = True,
        allow_side_effects: bool = True,
    ) -> None:
```

Thread-safe AST-based expression evaluator. Each instance has its own copy of `CONSTANTS`, `FUNCTIONS`, `_memory` (Memory), and `_user_variables` (dict). Instance-level state is protected by `_var_lock`.

**Constructor args:**
- `allow_random`: If `False`, calls to `_RANDOM_FUNCTIONS` (random, randint, randrange, uniform, randn, gauss, seed) raise `EvaluationError`.
- `allow_side_effects`: If `False`, calls to `_SIDE_EFFECT_FUNCTIONS` (store, recall, M, Mplus, Mminus, MC, MR, setvar, getvar, delvar, listvars, clearvars) raise `EvaluationError`.

**Class-level attributes:**
- `CONSTANTS: dict[str, Any]` — physical and mathematical constants
- `FUNCTIONS: dict[str, Any]` — whitelisted functions (copied per-instance)
- `BINOPS: dict[type[ast.operator], Any]` — binary operator dispatch (Add, Sub, Mult, Div, FloorDiv, Mod, Pow, LShift, RShift, BitOr, BitXor, BitAnd)
- `UNARYOPS: dict[type[ast.unaryop], Any]` — unary operator dispatch (UAdd, USub, Invert)

**Key methods:**
- `visit(node)` — depth-tracking wrapper around `ast.NodeVisitor.visit`, enforces `MAX_NESTING_DEPTH`
- `_validate_node(node)` — checks node against `_ALLOWED_AST_TYPES` allowlist; `ast.Attribute` gets additional validation (only `math.*` and `.real`/`.imag`/`.conjugate()`)
- `evaluate(expression: str) -> Any` — parses AST, validates nodes, evaluates, returns result; sets `_current_evaluator` ContextVar for function calls
- `_parse_unit(text)` — parses number+unit strings
- `_get_conversion_factor(from_unit, to_unit)` — unit conversion factor lookup

## Memory System

Calculator-style memory with named registers (class `Memory`):

```python
memory_store(42)           # Store 42 in M
memory_add(10)             # M = M + 10
memory_recall()            # Get M value
memory_subtract(5)         # M = M - 5
memory_clear()             # Clear M
memory_list()              # List all registers
```

Named registers also supported:
```python
memory_store(42, "M2")     # Store in M2
memory_add(10, "M2")       # Add to M2
memory_clear("M2")         # Clear M2
memory_clear()             # Clear all registers
```

Memory functions are also available inside expressions via the FUNCTIONS dict: `store()`, `recall()`, `M()`, `Mplus()`, `Mminus()`, `MC()`, `MR()`. These consult the `_current_evaluator` ContextVar so behavior is correctly scoped to the active Evaluator instance.

## Variable Storage

User-defined variables persist across evaluations. Capped at `MAX_USER_VARIABLES` (1000) per evaluator; oldest entries are evicted on overflow.

```python
setvar("x", 5)
setvar("y", 10)
getvar("x")        # → 5
evaluate("x + y")  # → 15
delvar("x")
listvars()         # → {"y": 10}
clearvars()
```

Variable functions are also available inside expressions via the FUNCTIONS dict: `setvar()`, `getvar()`, `delvar()`, `listvars()`, `clearvars()`. `getvar()` returns 0 for undefined names.

## Safe Math Functions

Built-in functions available in expressions:

### Arithmetic
- `abs(x)`, `round(x, n)`, `sign(x)`
- `min(*args)`, `max(*args)`, `clamp(x, lo, hi)`
- `hypot(*args)` — variadic hypotenuse

### Trigonometric (complex-aware)
- `sin(x)`, `cos(x)`, `tan(x)`
- `asin(x)`, `acos(x)`, `atan(x)`, `atan2(y, x)`
- `sinh(x)`, `cosh(x)`, `tanh(x)`
- `asinh(x)`, `acosh(x)`, `atanh(x)`

### Logarithmic/Exponential (complex-aware)
- `log(x)` / `ln(x)` — natural log
- `log10(x)` — base 10
- `log2(x)` — base 2
- `log1p(x)` — log(1+x) for small x
- `exp(x)` — e^x
- `expm1(x)` — exp(x)-1 for small x

### Statistical
- `mean(*args)`, `median(*args)`, `mode(*args)`
- `std(*args)` — population std dev
- `std_sample(*args)` / `stds(*args)` — sample std dev (n-1)
- `variance(*args)` / `var(*args)` — population variance
- `variance_sample(*args)` / `vars(*args)` / `var_sample(*args)` — sample variance (n-1)
- `sum(*args)`

### Combinatorics
- `factorial(n)` / `fact(n)`
- `perm(n, r)` / `nPr(n, r)` — permutations
- `comb(n, r)` / `nCr(n, r)` — combinations
- `gcd(*args)`, `lcm(*args)`

### Complex Numbers
- `real(z)`, `imag(z)`, `conj(z)` / `conjugate(z)`
- `phase(z)`, `polar(r, phi)`, `rect(r, phi)`

### Bitwise
- `bitand(a, b)`, `bitor(a, b)`, `bitxor(a, b)`
- `bitnot(a)`
- `bitlshift(a, b)`, `bitrshift(a, b)` — no `lshift`/`rshift` aliases

### Random
- `random()` — [0, 1)
- `randint(a, b)` — [a, b]
- `randrange(a, b=None)` — [a, b) or [0, a)
- `uniform(a, b)` — uniform float in [a, b]
- `randn()` — standard normal
- `gauss(mu, sigma)`
- `seed(n)` — seed RNG

### Number Theory
- `isprime(n)` / `is_prime(n)` — primality test (deterministic Miller-Rabin for n < 10^12)
- `primefactors(n)` / `prime_factors(n)` — prime factorization (returns formatted string, n ≤ 10^12)
- `nextprime(n)` / `next_prime(n)` — next prime (max 10000 iterations)
- `prevprime(n)` / `prev_prime(n)` — previous prime (max 10000 iterations)

### Power/Root (complex-aware)
- `sqrt(x)` — square root
- `cbrt(x)` — cube root
- `pow(x, y)` — x^y

### Other Math
- `floor(x)` — floor
- `ceil(x)` — ceiling
- `trunc(x)` — truncation
- `degrees(rad)` — radians to degrees
- `radians(deg)` — degrees to radians

### Format Conversion
- `bin(x)`, `hex(x)`, `oct(x)` — integer to string (requires dimensionless argument)

### Percentage
- `percentof(p, x)` / `percent_of(p, x)` — p% of x
- `aspercent(x, total)` / `as_percent(x, total)` — x as % of total

### Temperature
- `temp(value, from_unit, to_unit)` — temperature conversion (e.g., `temp(100, "C", "F")`)

### Unit Conversion
- `convert(value, to_unit)` — convert a UnitValue to a different unit

## Complex Number Support

The `_complex_aware()` wrapper creates functions that handle both real and complex inputs:

```python
_sqrt = _complex_aware(math.sqrt, cmath.sqrt, use_complex_for_negative=True)
_log = _complex_aware(math.log, cmath.log, use_complex_for_negative=True)
```

Functions automatically use `cmath` when:
- Input is complex
- Input is negative (with `use_complex_for_negative=True`)
- Input has magnitude > 1 (with `use_complex_for_abs_gt_one=True`)

Functions using `_complex_aware`: `sqrt`, `log`, `log10`, `log2`, `log1p`, `exp`, `expm1`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `sinh`, `cosh`, `tanh`, `asinh`, `acosh`, `atanh`, `cbrt`.

`_log` / `_log10` / `_log2` wrap the complex-aware versions with additional `ValueError` handling that raises `EvaluationError` for non-positive real inputs.

## EggCalcApp

Thread-safe wrapper for eggcalc, optimized for webapp usage. Each instance has its own isolated `Evaluator` with separate constants, functions, memory, and variables. Instance-level caching with LRU eviction.

```python
from eggcalc.evaluator import EggCalcApp

app = EggCalcApp(cache_size=1024, enable_cache=True)
result = app.calculate("five plus two")
```

**Methods:**
- `calculate(expression: str) -> Any` — thread-safe evaluation with optional caching
- `calculate_async(expression: str) -> Any` — async version (thread pool)
- `register_constant(name, value)` — instance-scoped constant (thread-safe)
- `register_function(name, func)` — instance-scoped function (thread-safe)
- `clear_cache()` — clear instance cache
- `cache_size` property — current cache entry count

## Unit Handling

When expressions contain units, evaluation returns `UnitValue` objects:

```python
result = evaluate_raw("30m + 100ft")
# → UnitValue(60.48, "m")

result.value      # → 60.48
result.unit       # → "m"
result.convert_to("ft")  # → UnitValue(198.5, "ft")
```

The evaluator supports compound units in division and multiplication (e.g., `5m / 2s` → `2.5 m/s`), unit exponentiation (`5m ** 2` → `25.0 m**2`), and temperature conversions (with offset math). Cross-scale temperature addition is rejected; subtraction produces a delta.

### Unit-Aware Function Contracts

Every built-in function has an explicit `UnitPolicy` that controls how `UnitValue` arguments are handled. This prevents silent unit stripping (e.g., `sqrt(4*m) → 2` with meter lost).

| Policy | Behavior | Example functions |
|--------|----------|-------------------|
| `DIMENSIONLESS` | Reject `UnitValue` with unit | `log`, `exp`, `gcd`, `factorial`, `clamp` |
| `ANGLE_INPUT` | Accept dimensionless (radians) or angle `UnitValue`; convert to radians | `sin`, `cos`, `tan` |
| `ANGLE_OUTPUT` | Accept dimensionless; reject dimensional | `asin`, `acos`, `atan` |
| `PRESERVE_SINGLE` | Single arg, preserve unit on result | `abs`, `round`, `floor`, `ceil`, `trunc` |
| `SIGN_OUTPUT` | Unwrap magnitude, return dimensionless scalar | `sign` |
| `COMPATIBLE_REDUCER` | All args dimensionless or all compatible units | `mean`, `min`, `max`, `median`, `std`, `sum` |
| `VARIANCE_SQUARED` | Like COMPATIBLE_REDUCER but result has squared units | `variance`, `var`, `variance_sample`, `vars`, `var_sample` |
| `ROOT` | Dimensionless or even-exponent unit; halve exponents | `sqrt` |
| `HYPOT` | All args dimensionless or all compatible units | `hypot` |
| `ATAN2` | Both dimensionless or both compatible units | `atan2` |

User-registered functions default to `DIMENSIONLESS` (reject `UnitValue`).

Each evaluator maintains a `_builtin_function_baseline` snapshot of canonical built-in callables. `visit_Call` compares the active callable by identity against this baseline; a canonical callable receives its built-in unit policy, any added or replaced callable defaults to dimensionless-only.

Examples:
```python
evaluate_raw("sin(90*deg)")      # → 1.0 (degree conversion)
evaluate_raw("sin(1*m)")         # → EvaluationError
evaluate_raw("sqrt(4*m**2)")     # → 2.0 m
evaluate_raw("sqrt(4*m)")        # → EvaluationError
evaluate_raw("mean(1*m, 100*cm)") # → 1.0 m
evaluate_raw("variance(1*m, 2*m, 3*m)") # → 0.666... m**2
evaluate_raw("sign(-5*m)")       # → -1 (dimensionless)
evaluate_raw("round(3.7)")       # → 4 (int)
evaluate_raw("round(3.7, 0)")    # → 4.0 (float)
evaluate_raw("hypot(3*m, 4*s)")  # → EvaluationError
evaluate_raw("abs(-5*m)")        # → 5 m
```

### Timeout Evaluator State Parity

`evaluate_with_timeout()` reconstructs the parent evaluator's state in the child process:
- Registered scalar constants
- User variables
- Memory registers
- `allow_random` / `allow_side_effects` flags

Custom registered callables (added names or replaced built-ins) cannot be serialized across process boundaries and cause `evaluate_with_timeout()` to fail immediately with `EvaluationError`. The detection uses callable identity against `_builtin_function_baseline` to distinguish canonical built-ins from user overrides. Use `evaluate()` for expressions with custom functions.

### Angle Algebra Bounds

The `Dimension.angle` boolean flag supports only exponents of 0 or 1. Operations that would require richer representations (e.g., `deg**2`, `1/deg`, `deg*rad`) raise `ValueError` at the dimension level. Supported forms include `deg**0` (dimensionless), `deg**1` (angle), `deg/rad` (dimensionless), and `(deg/s)*s` (direct angle). See [units.md](units.md) for the full bounds table.

See [units.md](units.md) for unit conversion details.

## Module Dependencies

```
evaluator.py
    └── units.py (UNIT_ALIASES, UNIT_CONVERSIONS, UnitValue,
              _align_compatible_units, _pow_unit_string, _simplify_unit_string,
              are_units_compatible, convert_temperature, get_unit_category,
              normalize_unit)

    Lazy imports (at call time):
    └── normalize.py (NORMALIZE, PATTERNS, normalize_expression)
```
