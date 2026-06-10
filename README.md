# eggcalc

CLI calculator accepting natural language and unit conversion. Standard library only.

For install as a CLI tool, clone the repo, cd into it, and run `python install.py --install`. It will combine everything into one file and add it to your $path. Then you can run it like `calc 2 meters plus 2ft`. It ignores spacing and relies on spliting the input by operator. 

Written in pure Python with no external dependencies, it can be used as a CLI tool, a Python library, or an MCP server for AI agents.

## Features

eggcalc converts natural language math expressions into numerical results. Key capabilities:

- **Natural Language Input**: Speak math expressions naturally
  - `"five plus three times two"` → `5+3*2 = 11` (not 16 — follows order of operations)
  - `"twenty five"` → `25` (combines number words)
  - `"what is the square root of one hundred"` → `10`

- **Unit Conversions**: Mix metric and imperial units seamlessly
  - `"30m + 100ft"` → `60.48 m` (auto-converts feet to meters)
  - `"60mph"` → `60 mph` (speed units with conversions)
  - `"60km/h in m/s"` → `16.667 m/s` (compound unit conversions)
  - `"100C in F"` → `212 F` (temperature conversions)

- **Complex Numbers**: Full support for imaginary numbers
  - `"sqrt(-1)"` → `1j`
  - `"log(-1)"` → `3.14159...j` (πi)
  - `"3+4i"` → `(3+4j)`

- **Safe Evaluation**: AST-based parsing, no `eval()`
  - Blocks dangerous operations (`import`, `open`, etc.)
  - Built-in DoS protection (max nesting, exponents, factorial size)

- **Pure Python**: Standard library only, no dependencies

## Installation

### From PyPI (recommended)

```bash
pip install eggcalc
```

### From source

```bash
git clone https://github.com/eggstack/eggcalc.git
cd eggcalc
pip install -e .
```

### Run directly without installing

```bash
python -m eggcalc "five plus two"
```

## Usage

### Command Line

```bash
# Basic arithmetic
calc "five plus two"
# 7

# Complex expressions
calc "(twenty + five) * 3"
# 75

# Unit conversions
calc "30m + 100ft"
# 60.48 m

calc "(30m + 100ft) / 2"
# 30.24 m

# Trigonometric functions
calc "sin of 3.14159"
# 2.653e-06

# Physical constants
calc "5 times avogadro"
# 3.011e+24

# Quiet mode with -e (suppresses expression echo)
calc -e "5 + 3"
# Output: 8

# Interactive REPL mode
calc -i
# >>> five plus two
# 7
# >>> quit
```

### CLI Options

| Option | Description |
|--------|-------------|
| `-h`, `--help` | Show help and available operators |
| `--usage` | Show full usage information and examples |
| `-v`, `--version` | Show version information |
| `-e`, `--expression` | Evaluate a single expression (quiet mode by default) |
| `-q`, `--quiet` | Suppress expression in output |
| `-s`, `--show` | Show expression in output (currently unused, reserved for future use) |
| `--json` | Output result as JSON |
| `-i`, `--interactive` | Start interactive REPL mode |
| `--mcp` | Run as MCP server for math, text, and validation tools |

### CLI Text Tools

eggcalc includes text inspection tools for detecting hidden characters and testing patterns:

```bash
# Inspect text for hidden characters/confusables
calc inspect "hello"
# ✓ No hidden characters

calc inspect "pаypal"  # Cyrillic 'а' (U+0430) looks like Latin 'a'
# ✗ MIXED_SCRIPTS: Text contains mixed scripts: Cyrillic, Latin
# ✗ CONFUSABLE: Text contains confusable character 'а' (looks like 'a')
# Confusables found: 1
#   'а' (looks like 'a') at 1

# Count character frequency
calc count "hello" l
# 'l' appears 2 time(s) in "hello"

# Test regex patterns
calc regex "^\d+$" "12345"
# ✓ Match: '12345'
```

### MCP Server Mode

eggcalc can run as an MCP server, exposing deterministic text, JSON, validation, math, and path tools to AI agents:

```bash
calc --mcp
```

**59 tools** across 15 categories (math, text, json, validation, regex, list, path, identifier, shell, markdown, config, version, toml, cargo, unicode). All results are deterministic - same input always produces the same output.

For the full tool catalog with arguments, return values, and tiers, see [docs/mcp.md](docs/mcp.md).

### As a Python Module

```python
from eggcalc import evaluate_raw, evaluate

# Basic math (use evaluate_raw for expressions with spaces/natural language)
result = evaluate_raw("5 + 3")
print(result)  # 8

# Natural language support
result = evaluate_raw("five plus three")
print(result)  # 8

# Unit conversions
result = evaluate_raw("30m + 100ft")
print(result)  # 60.48 m

# Use evaluate() for pre-normalized expressions (fastest path, skips NL pipeline)
result = evaluate("5+3")  # No spaces or NL words
print(result)  # 8
```

### Webapp Usage (Optimized for Long-Running Applications)

```python
from eggcalc import EggCalcApp

# Create app instance with caching (recommended for webapps)
app = EggCalcApp(cache_size=1000)

# Calculate (uses cache automatically)
result = app.calculate("5 + 3")           # 8
result = app.calculate("five plus two")   # 7
result = app.calculate("30m + 100ft")     # 60.48 m

# Async support for async web frameworks (FastAPI, aiohttp, etc.)
result = await app.calculate_async("5 + 3")

# Custom constants and functions
app.register_constant("myconst", 42)
result = app.calculate("myconst + 8")      # 50

# Cache management
print(app.cache_size)   # 3
app.clear_cache()
```

### Full API Reference

```python
from eggcalc import (
    # Core evaluation
    evaluate,              # Pre-normalized expressions (no spaces)
    evaluate_raw,         # Full pipeline with natural language support
    evaluate_cached,      # Like evaluate_raw, with LRU cache (1024 entries)
    evaluate_async,       # Async version of evaluate_raw
    
    # Configuration
    register_constant,    # Add custom constants (thread-safe)
    register_function,   # Add custom functions (thread-safe)
    load_user_config,    # Load config from eggcalc_config.py
    
    # Webapp wrapper
    EggCalcApp,            # Thread-safe wrapper with caching
    
    # Types
    EvaluationError,      # Exception type
    UnitValue,           # For unit-aware results
)

# Cached evaluation (great for repeated queries with natural language)
result = evaluate_cached("5 + 3")
result = evaluate_cached("five plus three")

# Async evaluation
import asyncio
result = await evaluate_async("5 + 3")

# Register custom constants globally
register_constant("pi_approx", 3.14)
register_constant("earth_radius", 6371)

# Register custom functions
def my_func(x, y):
    return x ** 2 + y ** 2

register_function("mysquare", my_func)
result = evaluate_raw("mysquare(3, 4)")  # 25
```

### Performance (benchmarked on Python 3.14, M4 Pro)

| Method | Input Type | Typical Speed |
|--------|------------|---------------|
| `evaluate()` | Pre-normalized (e.g., `5+3`) | ~9 μs/eval |
| `evaluate_raw()` | Natural language (e.g., `"five plus three"`) | ~155 μs/eval |
| `evaluate_cached()` | Repeated NL expressions | ~0.1 μs/eval (after first call) |
| `EggCalcApp.calculate()` | NL with instance caching | ~0.3 μs/eval (after first call) |
| `evaluate_async()` | Async frameworks | Same as evaluate_raw in thread pool |

**Key insight**: `evaluate()` is ~17x faster than `evaluate_raw()` because it skips the normalization pipeline. Use `evaluate()` when you control input format, `evaluate_raw()` for user input.

The library includes optimizations:
- Pre-computed unit lookups (sorted by length for fast matching)
- LRU caching for parsed expressions (1024 entries default)
- Combined regex patterns for normalization
- Thread-safe constant/function registration
- Complex-aware trig functions (`sin()`, `log()`, etc. handle complex arguments)

## API Reference

### Core Functions

#### `evaluate(expression: str) -> Any`
Evaluate a pre-normalized expression (no spaces, no natural language).
Use this for maximum performance when you control the input format.

```python
from eggcalc import evaluate
result = evaluate("5+3")  # 8 (note: no spaces)
```

#### `evaluate_raw(expression: str) -> Any`
Evaluate a raw expression with spaces and/or natural language.
This is the main function for user input.

```python
from eggcalc import evaluate_raw
result = evaluate_raw("5 + 3")        # 8
result = evaluate_raw("five plus 3")  # 8
```

#### `evaluate_cached(expression: str) -> Any`
Like `evaluate_raw()` but with LRU caching. Best for repeated identical expressions.

```python
from eggcalc import evaluate_cached
result = evaluate_cached("5 + 3")  # Cached after first call
```

#### `evaluate_async(expression: str) -> Awaitable[Any]`
Async version of `evaluate_raw()`. For async web frameworks.

```python
from eggcalc import evaluate_async
result = await evaluate_async("5 + 3")
```

#### `evaluate_with_timeout(expression: str, timeout: float = 5.0) -> Any`
Evaluate with timeout protection. **Recommended for untrusted input.**

```python
from eggcalc import evaluate_with_timeout, TimeoutError

try:
    result = evaluate_with_timeout("2 ** 1000000", timeout=1.0)
except TimeoutError:
    print("Evaluation timed out")
```

### EggCalcApp Class

Thread-safe wrapper optimized for webapps with caching and instance isolation.

```python
from eggcalc import EggCalcApp

app = EggCalcApp(cache_size=1000)  # LRU cache with 1000 entries

# Evaluate expressions
result = app.calculate("5 + 3")

# Async support
result = await app.calculate_async("5 + 3")

# Register instance-specific constants/functions
app.register_constant("myconst", 42)
app.register_function("double", lambda x: x * 2)

# Cache management
app.clear_cache()
print(app.cache_size)
```

### Configuration Functions

#### `register_constant(name: str, value: float) -> None`
Register a custom constant globally. Thread-safe.

```python
from eggcalc import register_constant
register_constant("earth_radius", 6371)
result = evaluate_raw("earth_radius")  # 6371
```

#### `register_function(name: str, func: Callable) -> None`
Register a custom function globally. Thread-safe. **Only call during initialization.**

```python
from eggcalc import register_function
register_function("square", lambda x: x ** 2)
result = evaluate_raw("square(5)")  # 25
```

### Exceptions

#### `EvaluationError`
Raised when an expression is invalid or contains unsupported operations.

```python
from eggcalc import evaluate_raw, EvaluationError

try:
    result = evaluate_raw("import os")
except EvaluationError as e:
    print(f"Error: {e}")
```

#### `TimeoutError`
Raised when evaluation exceeds the timeout in `evaluate_with_timeout()`.

```python
from eggcalc import evaluate_with_timeout, TimeoutError

try:
    result = evaluate_with_timeout("slow_expression", timeout=1.0)
except TimeoutError:
    print("Timed out")
```

### Types

#### `UnitValue`
Represents a numeric value with optional units.

```python
from eggcalc import UnitValue

uv = UnitValue(5, "m")
print(uv)        # "5 m"
print(uv.value)  # 5.0
print(uv.unit)   # "m"
```

### Utility Functions

#### `normalize_unit(unit: str) -> str`
Normalize a unit to its canonical form.

```python
from eggcalc import normalize_unit
normalize_unit("meters")  # "m"
normalize_unit("ft")      # "ft"
```

#### `get_conversion_factor(from_unit: str, to_unit: str) -> float`
Get conversion factor between two units.

```python
from eggcalc import get_conversion_factor
get_conversion_factor("ft", "m")  # 0.3048
```

#### `get_all_units() -> list[str]`
Get list of all supported units.

```python
from eggcalc import get_all_units
units = get_all_units()  # ['A', 'B', 'BTU', 'C', 'F', 'GB', ...]
```

#### `is_unit(text: str) -> bool`
Check if text represents a unit.

```python
from eggcalc import is_unit
is_unit("m")   # True
is_unit("xyz") # False
```

## Supported Operations

### Arithmetic
`+`, `-`, `*`, `/`, `**`

### Number Words
- 0-9: zero, one, two, three, four, five, six, seven, eight, nine
- Teens: ten, eleven, twelve... nineteen
- Tens: twenty, thirty, forty... ninety
- Scales: hundred, thousand, million, billion, trillion, quadrillion, quintillion
- Fractions: half, quarter, thousandth, millionth, billionth

### Functions
- Trig: `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`
- Hyperbolic: `sinh`, `cosh`, `tanh`, `asinh`, `acosh`, `atanh`
- Math: `sqrt`, `cbrt`, `log`, `log10`, `log2`, `log1p`, `exp`, `abs`, `floor`, `ceil`, `trunc`, `round`, `sign`
- Factorial & Combinatorics: `factorial`, `gcd`, `lcm`, `perm`, `comb`, `nPr`, `nCr`
- Complex: `real`, `imag`, `conj`, `phase`, `polar`, `rect`
- Bitwise: `bitand`, `bitor`, `bitxor`, `bitnot`, `bin`, `hex`, `oct`
- Statistics: `mean`, `median`, `mode`, `std`, `variance`, `sum`, `max`, `min`
- Prime: `isprime`, `primefactors`, `nextprime`, `prevprime`
- Random: `random`, `randint`, `uniform`, `randn`, `gauss`, `seed`
- Memory: `store`, `recall`, `Mplus`, `Mminus`, `MR`, `MC`
- Variables: `setvar`, `getvar`, `delvar`, `listvars`, `clearvars`
- Utility: `clamp`, `hypot`, `percentof`, `aspercent`
- Temperature: `temp`

### Bitwise Operators
`&` (AND), `|` (OR), `^` (XOR), `~` (NOT), `<<` (left shift), `>>` (right shift)

### Base Prefixes
`0x` (hex), `0b` (binary), `0o` (octal)

### Complex Numbers
`i` or `j` for imaginary unit, e.g., `3+4i`, `5j`

### Percentage
`%` suffix, e.g., `50%` = 0.5

### Units

#### Length
meters (m), kilometers (km), centimeters (cm), millimeters (mm), micrometers (μm), nanometers (nm), picometers (pm), inches (in), feet (ft), yards (yd), miles (mi), lightyears (ly), astronomical units (au), parsecs (pc), angstroms, fermis

#### Time
seconds (s), milliseconds (ms), microseconds (μs), nanoseconds (ns), picoseconds (ps), minutes (min), hours (h), days (d), weeks (wk), years (yr)

#### Data
bytes (B), kilobytes (KB), megabytes (MB), gigabytes (GB), terabytes (TB), petabytes (PB)

#### Mass
kilograms (kg), grams (g), milligrams (mg), micrograms (μg), nanograms (ng), pounds (lb), ounces (oz), tons

#### Volume
liters (L), milliliters (mL), gallons (gal), quarts (qt), pints (pt), cups

#### Pressure
Pascals (Pa), kilopascals (kPa), bar, atmospheres (atm), psi

#### Energy
Joules (J), kilojoules (kJ), calories (cal), kilocalories (kcal), watt-hours (Wh), kilowatt-hours (kWh), BTU, electronvolts (eV)

#### Power
Watts (W), kilowatts (kW), megawatts (MW), gigawatts (GW), horsepower (hp)

#### Data Transfer Rate
bits per second (bps), kilobits per second (Kbps), megabits per second (Mbps), gigabits per second (Gbps)

#### Force
Newtons (N), kilonewtons (kN), millinewtons (mN), dynes, pounds-force (lbf)

#### Voltage
volts (V), kilovolts (kV), millivolts (mV), microvolts (μV)

#### Current
amperes (A), milliamperes (mA), microamperes (μA)

#### Angle
radians (rad), degrees (deg)

#### Speed
meters per second (m/s), kilometers per hour (km/h), miles per hour (mph), knots (kn), mach

#### Area
square meters (m2), square kilometers (km2), hectares (ha), acres, square feet (ft2), square inches (in2), square miles (mi2), square yards (yd2)

#### Frequency
hertz (Hz), kilohertz (kHz), megahertz (MHz), gigahertz (GHz), terahertz (THz)

### Constants
- Mathematical: pi, e, tau, i (imaginary unit)
- Physical: avogadro, gas constant, planck, boltzmann, speed of light (c), elementary charge, faraday, atomic mass unit (amu), vacuum permittivity

## Advanced Features

### Complex Numbers

Support for complex number arithmetic using `i` or `j` notation:

```python
from eggcalc import evaluate_raw

# Complex literals
evaluate_raw("3 + 4i")      # (3+4j)
evaluate_raw("(3+4j)")      # (3+4j)

# Complex functions
evaluate_raw("sqrt(-1)")    # 1j
evaluate_raw("log(-1)")     # 3.14159265j (πi)
evaluate_raw("abs(3+4i)")   # 5.0
evaluate_raw("conj(3+4i)")  # (3-4j)
evaluate_raw("real(3+4j)")  # 3.0
evaluate_raw("imag(3+4j)")  # 4.0

# Euler's identity
evaluate_raw("e**(i*pi)")   # (-1+1.2246467991473532e-16j)
```

### Bitwise Operations

Full support for bitwise operations:

```python
from eggcalc import evaluate_raw

# Bitwise operators
evaluate_raw("5 bitand 3")   # 1 (0b101 & 0b011)
evaluate_raw("5 & 3")        # 1 (same, symbol form)
evaluate_raw("5 OR 3")       # 7 (0b101 | 0b011)
evaluate_raw("5 XOR 3")      # 6 (0b101 ^ 0b011)
evaluate_raw("~5")          # -6 (bitwise NOT)
evaluate_raw("5 << 2")      # 20 (left shift)
evaluate_raw("5 >> 1")      # 2 (right shift)

# Base prefixes
evaluate_raw("0xFF")        # 255 (hexadecimal)
evaluate_raw("0b1010")      # 10 (binary)
evaluate_raw("0o777")       # 511 (octal)

# Base conversion functions
evaluate_raw("hex(255)")    # '0xff'
evaluate_raw("bin(10)")     # '0b1010'
evaluate_raw("oct(511)")    # '0o777'
```

### Combinatorics

Permutations and combinations:

```python
from eggcalc import evaluate_raw

# Permutations P(n,r) = n!/(n-r)!
evaluate_raw("perm(5, 3)")  # 60
evaluate_raw("nPr(5, 3)")   # 60 (alias)

# Combinations C(n,r) = n!/(r!(n-r)!)
evaluate_raw("comb(5, 3)")  # 10
evaluate_raw("nCr(5, 3)")   # 10 (alias)

# LCM and GCD
evaluate_raw("lcm(12, 18)")     # 36
evaluate_raw("lcm(12, 18, 24)") # 72
evaluate_raw("gcd(12, 18)")     # 6
```

### Prime Functions

Prime number utilities:

```python
from eggcalc import evaluate_raw

# Check if prime
evaluate_raw("isprime(17)")       # True
evaluate_raw("isprime(18)")       # False

# Prime factorization
evaluate_raw("primefactors(84)")  # "2^2 × 3 × 7"

# Find nearby primes
evaluate_raw("nextprime(17)")     # 19
evaluate_raw("prevprime(20)")     # 19
```

### Statistical Functions

Extended statistical operations:

```python
from eggcalc import evaluate_raw

# Basic statistics
evaluate_raw("mean(1, 2, 3, 4, 5)")        # 3.0
evaluate_raw("median(1, 2, 3, 4, 5)")      # 3
evaluate_raw("median(1, 2, 3, 4)")         # 2.5
evaluate_raw("mode(1, 2, 2, 3)")           # 2
evaluate_raw("variance(1, 2, 3, 4, 5)")    # 2.0
evaluate_raw("std(1, 2, 3, 4, 5)")         # 1.414...

# Aggregate functions
evaluate_raw("sum(1, 2, 3, 4, 5)")         # 15
evaluate_raw("min(3, 1, 4, 1, 5)")         # 1
evaluate_raw("max(3, 1, 4, 1, 5)")         # 5
```

### Random Functions

Random number generation with seeding:

```python
from eggcalc import evaluate_raw

# Seed for reproducibility
evaluate_raw("seed(42)")

# Random numbers
evaluate_raw("random()")         # 0.0-1.0
evaluate_raw("randint(1, 100)")  # Integer 1-100
evaluate_raw("uniform(0, 10)")   # Float 0-10

# Normal distribution
evaluate_raw("randn()")          # Standard normal (μ=0, σ=1)
evaluate_raw("gauss(100, 15)")   # Normal (μ=100, σ=15)
```

### Percentage

Percentage calculations:

```python
from eggcalc import evaluate_raw

# Percentage literals
evaluate_raw("50%")              # 0.5
evaluate_raw("25%")              # 0.25

# Percentage functions
evaluate_raw("percentof(20, 100)")   # 20.0 (20% of 100)
evaluate_raw("aspercent(25, 100)")   # 25.0 (25 as % of 100)
```

### Memory Registers

Calculator-style memory operations:

```python
from eggcalc import evaluate_raw

# Store and recall
evaluate_raw("store(42)")        # Store 42 in memory
evaluate_raw("recall()")         # 42
evaluate_raw("MR")               # 42 (alias)

# Memory add/subtract
evaluate_raw("Mplus(8)")         # 50 (adds 8 to memory)
evaluate_raw("Mminus(5)")        # 45 (subtracts 5)

# Clear memory
evaluate_raw("MC")               # Clears memory
```

### Variables

User-defined variables:

```python
from eggcalc import evaluate_raw

# Set and use variables
evaluate_raw('setvar("x", 10)')  # 10
evaluate_raw("x + 5")            # 15
evaluate_raw('setvar("y", 20)')  # 20
evaluate_raw("x * y")            # 200

# Variable management
evaluate_raw("getvar('x')")      # 10
evaluate_raw("listvars()")       # {'x': 10, 'y': 20}
evaluate_raw("delvar('x')")      # Deletes x
evaluate_raw("clearvars()")      # Deletes all variables
```

### Utility Functions

```python
from eggcalc import evaluate_raw

# Rounding and signs
evaluate_raw("round(3.14159, 2)")    # 3.14
evaluate_raw("sign(-5)")              # -1
evaluate_raw("sign(5)")               # 1

# Clamping
evaluate_raw("clamp(15, 0, 10)")     # 10
evaluate_raw("clamp(-5, 0, 10)")     # 0

# Hypotenuse
evaluate_raw("hypot(3, 4)")          # 5.0
```

## Custom Configuration

Create a `eggcalc_config.py` file to add custom constants, functions, and units:

```python
# eggcalc_config.py

# Custom constants
CUSTOM_CONSTANTS = {
    "myconst": 42,
    "earth_radius_km": 6371,
}

# Custom functions
CUSTOM_FUNCTIONS = {
    "mysquare": lambda x, y: x**2 + y**2,
}

# Custom units (add to existing category or create new)
CUSTOM_UNITS = {
    "m": {
        "nm": 1e-9,  # nanometers (already exists, but shows pattern)
    },
}

# Custom unit aliases
CUSTOM_ALIASES = {
    "meter": "m",
    "meters": "m",
}

# Custom temperature conversions
CUSTOM_TEMP_CONVERSIONS = {
    ("C", "R"): (1.0, 491.67),  # Celsius to Rankine
}

# Custom number words
CUSTOM_NUMBER_WORDS = {
    "1000000000000000": ["quadrillion"],
}

# Custom operator words
CUSTOM_OPERATOR_WORDS = {
    "+": ["plus", "add"],
}
```

## Development

### Running Tests

```bash
pip install pytest
pytest tests/
```

### Project Structure

```
eggcalc/
├── eggcalc/
│   ├── __init__.py      # Package init
│   ├── __main__.py      # CLI entry point
│   ├── units.py         # Unit definitions and conversions
│   ├── evaluator.py     # AST-based expression evaluator
│   ├── normalize.py     # Main parsing and normalization
│   ├── exact/           # Deterministic text analysis tools
│   └── mcp/             # MCP server for AI agent access
├── tests/
│   ├── test_clicalc.py  # Core functional tests
│   ├── test_security_fuzz.py  # Security fuzz tests
│   ├── test_exact.py    # Exact module tests
│   ├── test_mcp_server.py # MCP server tests
│   └── ...              # Additional test files
├── pyproject.toml       # Package configuration
└── README.md            # This file
```

## Security

eggcalc uses AST-based parsing instead of `eval()`, which provides:
- No arbitrary code execution
- Controlled function access
- Safe constant evaluation
- No access to system resources

### Input Limits

Built-in protections against DoS attacks:

| Constant | Default | Description |
|----------|---------|-------------|
| `MAX_INPUT_LENGTH` | 10,000 | Maximum input character length |
| `MAX_NESTING_DEPTH` | 100 | Maximum parentheses nesting depth |
| `MAX_EXPONENT` | 10,000 | Maximum exponent value |
| `MAX_FACTORIAL` | 1,000 | Maximum factorial input |
| `MAX_RESULT_VALUE` | 1e308 | Maximum result value |
| `DEFAULT_CACHE_SIZE` | 1,024 | LRU cache size |

These can be imported and modified:

```python
from eggcalc import MAX_INPUT_LENGTH, MAX_NESTING_DEPTH, MAX_EXPONENT

# Increase limits (use with caution for security)
MAX_EXPONENT = 100000
```

### Security Considerations for Webapps

**Safe for untrusted input:**
- `evaluate()`, `evaluate_raw()`, `evaluate_cached()`, `evaluate_async()`
- `EggCalcApp.calculate()`, `EggCalcApp.calculate_async()`

**Register with caution:**
- `register_function()` - Only register during initialization, never from user input
- `register_constant()` - Safe to use, values are validated

**Config file warning:**
- `eggcalc_config.py` is imported from the working directory
- For production, ensure this file is not user-writable
- Consider removing config loading in high-security environments

### Example: Secure Webapp Usage

```python
from eggcalc import EggCalcApp, EvaluationError

app = EggCalcApp(cache_size=1000)

def handle_user_input(expression: str) -> dict:
    """Safely evaluate user-provided expression."""
    try:
        result = app.calculate(expression)
        return {"success": True, "result": str(result)}
    except EvaluationError as e:
        return {"success": False, "error": str(e)}
```

## License

MIT License
