# Quick Start

This guide gets you started with eggcalc for both CLI and Python usage.

## Command Line

### Basic Arithmetic

```bash
calc "5 + 3"
# 8

calc "2 + 3 * 4"
# 14 (not 20 - follows order of operations)
```

### Natural Language

```bash
calc "five plus three"
# 8

calc "twenty times five"
# 100

calc "one hundred divided by four"
# 25

calc "what is five plus three"
# 8 (conversational phrases stripped)
```

### Unit Conversions

```bash
calc "30m + 100ft"
# 60.48 m (auto-converts)

calc "60mi / h"
# 60 mi/h (compound units)

calc "30 km / h in mph"
# 18.641 mph (spaces around compound units are ignored)

calc "1GB in MB"
# 1024 MB

calc "5 in in cm"
# 12.7 cm (inch conversion remains unambiguous)

calc "temp(100, C, F)"
# 212 F (temperature conversion)
```

### Scientific Functions

```bash
calc "sin(pi/2)"
# 1.0

calc "sqrt(144)"
# 12

calc "log(e)"
# 1.0

calc "2^10"
# 1024
```

### Physical Constants

```bash
calc "avogadro"
# 6.022e+23

calc "speed of light"
# 299792458

calc "5 * planck"
# 3.31e-33
```

### CLI Options

| Option | Description |
|--------|-------------|
| `-e` | Quiet mode, output result only |
| `-s` | Accepted for compatibility; plain output remains result-only |
| `-q` | Suppress expression in output |
| `--json` | Output result and normalized expression as JSON |
| `-i` | Interactive REPL mode |

### Interactive Mode

```bash
calc -i
>>> five plus three
8
>>> 30m + 100ft
60.48 m
>>> quit
```

### Pipe Input

```bash
echo "5 + 3" | calc -e
# 8

echo "100ft in meters" | calc -e
# 30.48
```

## Python API

### Choosing the Right Function

**For user input (natural language):**

```python
from eggcalc import evaluate_raw

result = evaluate_raw("five plus three")  # 8
result = evaluate_raw("30m + 100ft")      # 60.48 m
```

**For controlled input (pre-normalized):**

```python
from eggcalc import evaluate  # Note: different import path

result = evaluate("5+3")  # 8 - valid Python math syntax
```

**For untrusted input (with timeout):**

```python
from eggcalc import evaluate_with_timeout, TimeoutError

try:
    result = evaluate_with_timeout("5 + 3", timeout=1.0)
except TimeoutError:
    print("Calculation timed out")
```

### Working with Results

```python
from eggcalc import evaluate_raw, UnitValue

result = evaluate_raw("30m + 100ft")

if isinstance(result, UnitValue):
    print(f"Value: {result.value}, Unit: {result.unit}")
    # Value: 60.48, Unit: m
```

### Webapps with EggCalcApp

```python
from eggcalc import EggCalcApp

app = EggCalcApp(cache_size=1000)

# Natural language works
result = app.calculate("five plus three")  # 8
result = app.calculate("30m + 100ft")       # 60.48 m

# Async support
result = await app.calculate_async("sqrt(144)")
```

### Error Handling

```python
from eggcalc import evaluate_raw, EvaluationError, TimeoutError

try:
    result = evaluate_raw("five plus three")
except EvaluationError as e:
    print(f"Invalid expression: {e}")

try:
    result = evaluate_with_timeout("2 ** 1000000", timeout=1.0)
except TimeoutError:
    print("Calculation timed out")
```

## Security Note

For web applications or any scenario with untrusted input, use `evaluate_with_timeout()`:

```python
from eggcalc import evaluate_with_timeout, TimeoutError

# Always use timeout with untrusted input
result = evaluate_with_timeout(user_expression, timeout=5.0)
```

This prevents:
- Long-running calculations (DoS protection)
- Nested expressions that could consume memory
- Complex expressions that could hang the process

## Next Steps

- [CLI Usage](cli.md) - All command-line options
- [Natural Language](natural-language.md) - Full language support
- [Functions](functions.md) - All available functions
- [Units](units.md) - All supported units
- [API Reference](api.md) - Complete Python API documentation
- [Security](security.md) - Security best practices
