# Welcome to eggcalc

A natural language math expression calculator that converts spoken expressions into mathematical operations.

## Two Evaluation Paths

Understanding the two evaluation functions is essential for using eggcalc effectively:

### `evaluate_raw()` - Natural Language & Units

Use this for any user input, natural language, or expressions with units:

```python
from eggcalc import evaluate_raw

evaluate_raw("five plus three")      # 8
evaluate_raw("30m + 100ft")          # 60.48 m (with units)
evaluate_raw("what is pi times two")  # 6.283...
```

### `evaluate()` - Pre-Normalized Math Only

Use this when you control the input format and want maximum performance (skips normalization entirely):

```python
from eggcalc import evaluate

evaluate("5+3")      # 8 - valid Python math syntax
evaluate("sin(1)+2") # 2.8414...
```

**Key difference:** `evaluate()` expects valid Python syntax. `evaluate_raw()` handles natural language, spaces, and units.

## Features

### Natural Language Input

Write math expressions in plain English:

```bash
calc "five plus three times two"
# 11 (follows order of operations, not 16)

calc "twenty five"
# 25

calc "what is the square root of one hundred"
# 10.0
```

### Unit Conversions

Mix metric and imperial units seamlessly:

```bash
calc "30m + 100ft"
# 60.48 m (auto-converts feet to meters)

calc "60mi / h"
# 60 mi/h (compound units)

calc "30 km / h in mph"
# 18.641 mph (spaces around compound units are ignored)

calc "5km in miles"
# 3.107 mi

calc "5 in in cm"
# 12.7 cm (inch conversion remains unambiguous)
```

See [Units](units.md) for all supported units and conversion patterns.

### Scientific Functions

Full support for trigonometric, logarithmic, and other mathematical functions:

```bash
calc "sin(pi/2)"      # 1.0
calc "sqrt(144)"      # 12.0
calc "log(e)"         # 1.0
calc "factorial(5)"   # 120
```

See [Functions](functions.md) for all available functions.

### Physical Constants

Built-in scientific constants:

```bash
calc "avogadro"              # 6.022e+23
calc "speed of light"        # 299792458
calc "5 * planck"            # 3.313e-33
calc "h * c / 500nm"         # Photon energy: 3.972e-19
```

See [Constants](constants.md) for all available constants.

### Complex Numbers

Full support for imaginary numbers:

```bash
calc "sqrt(-1)"    # 1j
calc "log(-1)"     # 3.14159...j (πi)
calc "3+4i"        # (3+4j)
```

### Exact Text Module

For text analysis needs (security, Unicode handling):

```bash
# Inspect text for hidden characters and confusables
calc inspect "p$'\u0430'ypal"  # Cyrillic confusable detection

# Character counting
calc count "hello world" l  # 'l' appears 3 time(s)

# Regex testing
calc regex "^\d+$" "12345"  # Match: '12345'
```

See [Exact Module](exact.md) for comprehensive text processing documentation.

### MCP Server

AI agent integration via Model Context Protocol:

```bash
calc --mcp
# Exposes 77 deterministic tools to AI agents
```

See [MCP Server](mcp.md) for detailed tool documentation.

## Safe Evaluation

eggcalc uses AST-based parsing instead of `eval()`, providing:

- **No arbitrary code execution** - Users cannot execute Python code
- **Controlled function access** - Only whitelisted functions can be called
- **Built-in DoS protection** - Max nesting depth, exponents, factorial size
- **No system access** - No files, network, or other resources

See [Security](security.md) for best practices when handling untrusted input.

## Pure Python

No external dependencies - uses only Python's standard library. Works everywhere Python is available.

## Quick Start

```bash
# Basic arithmetic
calc "5 + 3"           # 8

# Natural language
calc "five plus three"  # 8

# Unit conversions
calc "30m + 100ft"     # 60.48 m

# Functions and constants
calc "sin(pi/2)"       # 1.0
calc "sqrt(144)"       # 12.0

# Pipe input (quiet mode)
echo "5 + 3" | calc -e  # 8
```

## Installation

```bash
pip install eggcalc
```

Or install CLI directly:

```bash
git clone https://github.com/eggstack/eggcalc.git
cd eggcalc
python install.py --install
```

## Next Steps

- [Quick Start](quickstart.md) - Get up and running quickly
- [CLI Usage](cli.md) - All command-line options and text tools
- [Python API](api.md) - Complete Python API documentation
- [Functions](functions.md) - All available mathematical functions
- [Units](units.md) - All supported units and conversions
- [Constants](constants.md) - Physical and mathematical constants
- [Exact Module](exact.md) - Text analysis and Unicode handling
- [MCP Server](mcp.md) - AI agent integration
- [Security](security.md) - Security best practices
- [Web Applications](webapps.md) - Using eggcalc in web apps
- [Configuration](configuration.md) - Customizing eggcalc
