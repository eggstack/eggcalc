# evaluator.py — AST-Based Expression Evaluation

2765 lines. Provides a **secure** way to evaluate mathematical expressions without using `eval()`. Uses Python's `ast` module to parse and evaluate expressions safely.

## Overview

The `evaluator` module is the **core computation engine**. It:
- Parses Python AST (Abstract Syntax Tree) instead of using eval
- Supports arithmetic, trigonometric, logarithmic functions
- Handles complex numbers, memory operations, variables
- Provides caching, async evaluation, and timeouts

## Key Exports

```python
from eggcalc.evaluator import (
    evaluate,           # Main evaluation function
    evaluate_raw,       # Evaluate with NL normalization
    evaluate_cached,    # LRU cached evaluation
    evaluate_async,     # Async evaluation
    evaluate_with_timeout,
    EvaluationError,    # Exception class
    TimeoutError,       # Timeout exception
    EggCalcApp,          # Webapp class with caching
    get_default_evaluator,
    register_constant,  # Add user constants
    register_function,  # Add user functions
    load_user_config,   # Load eggcalc_config.py
    # Memory functions
    memory_store, memory_recall, memory_add, memory_subtract,
    memory_clear, memory_list,
    # Variable functions
    setvar, getvar, delvar, listvars, clearvars,
)

# Internal (not exported, available if needed):
#   load_user_config_extended() — loads CUSTOM_NUMBER_WORDS and CUSTOM_OPERATOR_WORDS
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
│  Evaluator.visit() → traverses AST                          │
│      ↓                                                      │
│  Only whitelisted operations allowed                        │
│      ↓                                                      │
│  Output: 11                                                 │
└─────────────────────────────────────────────────────────────┘

NOT eval() — uses AST for safety
```

## AST Node Handlers

The `Evaluator` class implements `visit_*` methods for each AST node type:

| Node Type | Handler | Operation |
|-----------|---------|-----------|
| `ast.Constant` | visit_Constant | Literals (numbers, strings) |
| `ast.BinOp` | visit_BinOp | +, -, *, /, //, %, ** |
| `ast.UnaryOp` | visit_UnaryOp | +, -, ~ |
| `ast.Call` | visit_Call | Function calls |
| `ast.Name` | visit_Name | Variables/constants |

**Forbidden node types** (raise `EvaluationError`):
- `ast.Compare` — comparison operators
- `ast.BoolOp` — boolean operations
- `ast.Subscript` — list/dict indexing
- `ast.List`, `ast.Dict`, `ast.Set` — container literals
- `ast.ListComp`, `ast.DictComp` — comprehensions

## Safe Math Functions

Built-in functions available in expressions:

### Arithmetic
- `abs(x)`, `round(x, n)`, `sign(x)`
- `min(*args)`, `max(*args)`, `clamp(x, lo, hi)`
- `hypot(*args)`

### Trigonometric
- `sin(x)`, `cos(x)`, `tan(x)`
- `asin(x)`, `acos(x)`, `atan(x)`
- `sinh(x)`, `cosh(x)`, `tanh(x)`
- `asinh(x)`, `acosh(x)`, `atanh(x)`

### Logarithmic/Exponential
- `log(x)` / `ln(x)` — natural log
- `log10(x)` — base 10
- `log2(x)` — base 2
- `exp(x)` — e^x
- `sqrt(x)`, `cbrt(x)`

### Statistical
- `mean(*args)`, `median(*args)`
- `std(*args)` — population std dev
- `variance(*args)`
- `sum(*args)`

### Combinatorics
- `factorial(n)` / `fact(n)`
- `perm(n, r)` — permutations
- `comb(n, r)` — combinations
- `gcd(*args)`, `lcm(*args)`

### Complex Numbers
- `real(z)`, `imag(z)`, `conj(z)`
- `phase(z)`, `polar(z)`, `rect(r, phi)`

### Bitwise
- `bitand(a, b)`, `bitor(a, b)`, `bitxor(a, b)`
- `bitnot(a)`
- `bitlshift(a, b)`, `bitrshift(a, b)` (also available as `lshift`/`rshift` aliases)

### Random
- `random()` — [0, 1)
- `randint(a, b)` — [a, b]
- `randrange(start, stop, step)` — range with step
- `uniform(a, b)` — uniform float in [a, b]
- `randn()` — standard normal
- `gauss(mu, sigma)`
- `seed(n)` — seed RNG

### Number Theory
- `isprime(n)` / `is_prime(n)` — primality test
- `primefactors(n)` / `prime_factors(n)` — prime factorization
- `nextprime(n)` / `next_prime(n)` — next prime
- `prevprime(n)` / `prev_prime(n)` — previous prime

### Trigonometric
- `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`
- `sinh`, `cosh`, `tanh`, `asinh`, `acosh`, `atanh`

### Logarithmic/Exponential
- `log(x)` / `ln(x)` — natural log
- `log10(x)` — base 10
- `log2(x)` — base 2
- `exp(x)` — e^x
- `log1p(x)` — log(1+x) for small x
- `expm1(x)` — exp(x)-1 for small x

### Power/Root
- `sqrt(x)` — square root
- `cbrt(x)` — cube root
- `pow(x, y)` — x^y

### Other Math
- `floor(x)` — floor
- `ceil(x)` — ceiling
- `trunc(x)` — truncation
- `degrees(rad)` — radians to degrees
- `radians(deg)` — degrees to radians
- `hypot(x, y)` — sqrt(x² + y²)
- `clamp(val, min, max)` — clamp value

### Format Conversion
- `bin(x)`, `hex(x)`, `oct(x)` — to string

### Percentage
- `percentof(p, x)` — p% of x
- `aspercent(x, total)` — x as % of total

## Constants

Built-in physical and mathematical constants:

| Name | Value | Description |
|------|-------|-------------|
| `pi` | 3.141592653589793 | π |
| `e` | 2.718281828459045 | e |
| `tau` | 6.283185307179586 | 2π |
| `inf` | math.inf | Infinity |
| `nan` | math.nan | Not a number |
| `i` / `j` | 1j | Imaginary unit |
| `c` / `c0` / `speedoflight` / `speedoflightvacuum` | 299792458 | Speed of light (m/s) |
| `na` / `avogadro` / `avogadros` | 6.02214076e23 | Avogadro number |
| `h` / `planck` / `planckconstant` | 6.62607015e-34 | Planck constant (J·s) |
| `k` / `boltzmann` / `boltzmannconstant` | 1.380649e-23 | Boltzmann constant (J/K) |
| `r` / `gasconstant` / `idealgasconstant` | 8.314462618 | Gas constant (J/mol·K) |
| `g` / `standardgravity` | 9.80665 | Standard gravity (m/s²) |
| `elementarycharge` / `echarge` | 1.602176634e-19 | Elementary charge (C) |
| `f` / `faraday` / `faradayconstant` | 96485.33212 | Faraday constant (C/mol) |
| `u` / `amu` / `atomicmassunit` | 1.66053906660e-27 | Atomic mass unit (kg) |
| `epsilon0` / `vacuumpermittivity` | 8.8541878128e-12 | Vacuum permittivity (F/m) |
| `mu0` / `vacuumpermeability` | 1.25663706212e-6 | Vacuum permeability (H/m) |
| `G` / `gravitationalconstant` | 6.67430e-11 | Gravitational constant (N·m²/kg²) |
| `me` / `electronmass` | 9.1093837015e-31 | Electron mass (kg) |
| `mp` / `protonmass` | 1.67262192369e-27 | Proton mass (kg) |
| `mn` / `neutronmass` | 1.67493e-27 | Neutron mass (kg) |
| `re` / `electronradius` | 2.817952326e-15 | Classical electron radius (m) |
| `alpha` / `finestructure` | 7.2973525693e-3 | Fine structure constant |
| `rydberg` / `rydbergconstant` | 10973731.568160 | Rydberg constant (m⁻¹) |
| `stefan` / `stefanboltzmann` | 5.670374419e-8 | Stefan-Boltzmann constant (W/m²·K⁴) |
| `wien` / `wienconstant` | 2.897771955e-3 | Wien displacement constant (m·K) |
| `planckbar` / `hbar` / `reducedplanck` | 1.054571817e-34 | Reduced Planck constant (J·s) |

## Memory System

Calculator-style memory with registers:

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
```

## Variable Storage

User-defined variables persist across evaluations:

```python
setvar("x", 5)
setvar("y", 10)
getvar("x")        # → 5
evaluate("x + y")  # → 15
delvar("x")
listvars()         # → {"y": 10}
clearvars()
```

## Limits and Safeguards

| Limit | Value | Purpose |
|-------|-------|---------|
| `MAX_EXPONENT` | 10000 | Prevent power DoS |
| `MAX_FACTORIAL` | 1000 | Prevent factorial DoS |
| `MAX_NESTING_DEPTH` | 100 | Prevent stack overflow |
| `MAX_RESULT_VALUE` | 1e308 | Prevent overflow |
| `DEFAULT_CACHE_SIZE` | 1024 | LRU cache size |

## Evaluation Functions

### `evaluate(expression: str) -> Any`
Direct AST evaluation. Expects valid Python syntax.

```python
evaluate("5 + 3")          # → 8
evaluate("sin(pi/2)")      # → 1.0
evaluate("sqrt(2)")        # → 1.414...
```

### `evaluate_raw(expression: str) -> Any`
Evaluates with NL normalization (calls `normalize_expression` first).

```python
evaluate_raw("five plus three")  # → 8
evaluate_raw("30m + 100ft")     # → UnitValue(60.48, "m")
```

### `evaluate_cached(expression: str) -> Any`
LRU cached evaluation for repeated identical expressions. Best for webapps.

The cache is an LRU (Least Recently Used) cache with 1024 entries. Clear cache on errors:

```python
evaluate_cached("5 + 3")           # → 8 (cached)
evaluate_cached("five plus three") # → 8 (cached, NL normalized first)
evaluate_cached.cache_clear()       # Clear the cache
```

### `evaluate_async(expression: str) -> Any`
Async evaluation for use with async web frameworks.

Runs evaluation in a thread pool executor to avoid blocking the event loop:

```python
result = await evaluate_async("5 + 3")           # Awaitable result
result = await evaluate_async("five plus three")  # NL also supported
```

Used by `EggCalcApp` for concurrent request handling.

### `evaluate_with_timeout(expression: str, timeout: float) -> Any`
Evaluation with timeout in seconds. Raises `TimeoutError` on timeout.

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

## EggCalcApp

Webapp wrapper with caching:

```python
from eggcalc.evaluator import EggCalcApp

app = EggCalcApp(cache_size=1024, enable_cache=True)
result = app.calculate("five plus two")
```

## Unit Handling

When expressions contain units, evaluation returns `UnitValue` objects:

```python
result = evaluate("30m + 100ft")
# → UnitValue(60.48, "m")

result.value      # → 60.48
result.unit       # → "m"
result.convert_to("ft")  # → UnitValue(198.5, "ft")
```

See [units.md](units.md) for unit conversion details.

## Module Dependencies

```
evaluator.py
    └── units (UnitValue, UNIT_ALIASES, UNIT_CONVERSIONS,
              normalize_unit, convert_temperature, are_units_compatible)
```