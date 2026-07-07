# Security

eggcalc is designed with security as a priority. This page covers security features and best practices.

## Critical: Always Use Timeouts for Untrusted Input

**For any expression from an untrusted source (web requests, user input, etc.), always use `evaluate_with_timeout()`:**

```python
from eggcalc import evaluate_with_timeout, TimeoutError

# ALWAYS use timeout with untrusted input
try:
    result = evaluate_with_timeout(user_expression, timeout=5.0)
except TimeoutError:
    return {"error": "Calculation timed out"}
```

This is the single most important security practice. Without a timeout, a malicious user could submit expressions that consume excessive CPU or memory.

## AST-Based Evaluation

eggcalc uses Abstract Syntax Tree (AST) parsing instead of Python's `eval()`. This provides:

- **No arbitrary code execution** - Users cannot execute Python code
- **Controlled function access** - Only whitelisted functions can be called
- **Safe constant evaluation** - Constants are validated before use
- **No system access** - No access to files, network, or system resources

## Input Limits

Built-in protections against DoS attacks (cannot be bypassed):

| Constant | Default | Description |
|----------|---------|-------------|
| `MAX_INPUT_LENGTH` | 10,000 | Maximum input character length |
| `MAX_NESTING_DEPTH` | 100 | Maximum parentheses nesting depth |
| `MAX_EXPONENT` | 10,000 | Maximum exponent value |
| `MAX_FACTORIAL` | 1,000 | Maximum factorial input |
| `MAX_RESULT_VALUE` | 1e308 | Maximum result value |

These prevent:
- Extremely long inputs
- Deeply nested expressions
- Huge exponents or factorials
- Overflow errors

## Blocked Operations

The following Python operations are blocked and will raise `EvaluationError`:

### Code Execution

```python
import os                  # Blocked
__import__('os')           # Blocked
eval('code')               # Blocked
exec('code')               # Blocked
compile('code', ...)       # Blocked
```

### Attribute Access

```python
().__class__               # Blocked
obj.__bases__              # Blocked
obj.__subclasses__()       # Blocked
```

### File Operations

```python
open('/etc/passwd')        # Blocked
os.system('ls')            # Blocked
subprocess.call(...)       # Blocked
```

### Comprehensions

```python
[x for x in y]             # Blocked
{x for x in y}             # Blocked
{x: y for x in z}          # Blocked
```

### Other

```python
lambda x: x                # Blocked
x if y else z              # Blocked
x < y                      # Blocked
x and y                    # Blocked
x[0]                       # Blocked
```

## Web Application Security

### Recommended Evaluation Functions

| Function | Use Case | Safety |
|----------|----------|--------|
| `evaluate_with_timeout()` | Untrusted input | **Recommended** - has timeout |
| `evaluate_raw()` | User input, controlled environment | Safe but no timeout |
| `evaluate()` | Pre-normalized, trusted input | Fastest, no normalization |
| `EggCalcApp.calculate()` | Webapps with caching | Safe, per-instance isolation |
| `evaluate_async()` | Async frameworks | Safe in thread pool |

### Example: Secure Endpoint

```python
from eggcalc import evaluate_with_timeout, EvaluationError, TimeoutError

def handle_user_input(expression: str):
    """Safely evaluate user-provided expression with timeout."""
    try:
        result = evaluate_with_timeout(expression, timeout=5.0)
        return {"success": True, "result": str(result)}
    except EvaluationError as e:
        return {"success": False, "error": str(e)}
    except TimeoutError:
        return {"success": False, "error": "Timeout"}
```

### Register Functions Safely

Only register functions during initialization:

```python
from eggcalc import register_function

# Safe: Register during startup
def my_safe_function(x):
    return x * 2

register_function("safe_double", my_safe_function)

# Dangerous: Never register from user input
# register_function(user_name, user_func)  # NEVER DO THIS
```

## Configuration Security

### Config File Warning

`eggcalc_config.py` is imported from the working directory:

```python
# In production, this file should:
# 1. Not be user-writable
# 2. Only contain trusted code
# 3. Be reviewed for security
```

### Disable Config Loading

In high-security environments, disable config loading entirely:

```python
# Option 1: Environment variable (recommended for library use)
import os
os.environ["EGGCALC_NO_CONFIG"] = "1"
from eggcalc import evaluate_raw

# Option 2: Use EggCalcApp (no config loading by default)
from eggcalc import EggCalcApp

app = EggCalcApp()
# Manually configure instead
app.register_constant("safe_const", 42)
```

**Config-loading policy:** Library APIs (`evaluate_raw()`, `evaluate_cached()`, etc.) do **not** load `eggcalc_config.py` by default. Set `EGGCALC_LOAD_CONFIG=1` to enable lazy config loading, or call `load_user_config()` explicitly. CLI loads config by default.

## Security Best Practices

### 1. Always Use Timeouts

```python
from eggcalc import evaluate_with_timeout

result = evaluate_with_timeout(user_input, timeout=1.0)
```

### 2. Validate Input

```python
def validate_input(expr: str) -> str:
    if len(expr) > 10000:
        raise ValueError("Input too long")
    if "import" in expr.lower():
        raise ValueError("Invalid input")
    return expr.strip()
```

### 3. Use Instance Isolation

```python
from eggcalc import EggCalcApp

# Each user/tenant gets isolated instance
app = EggCalcApp()
```

### 4. Rate Limit

```python
from functools import wraps
from time import time

def rate_limit(max_per_minute: int):
    # Implement rate limiting
    pass
```

### 5. Log Errors

```python
import logging

def safe_evaluate(expr: str):
    try:
        result = evaluate_with_timeout(expr)
        logging.info(f"Evaluated: {expr[:50]}")
        return result
    except Exception as e:
        logging.warning(f"Error: {e}")
        raise
```

## Unicode Text Security

For applications that process user-provided text, the `eggcalc.exact` module provides tools to detect Unicode-based spoofing attacks:

- **Confusables detection**: Identify characters from different scripts that look identical
- **Invisible character detection**: Find zero-width spaces, BOM, bidi controls
- **Mixed script detection**: Flag text with characters from multiple scripts

```python
from eggcalc.exact.synthesis import inspect_text

def validate_user_text(text: str) -> tuple[bool, list[str]]:
    """Check text for Unicode spoofing risks before storing."""
    result = inspect_text(text)

    warnings = []
    if result.confusables:
        warnings.append(f"Confusable characters: {len(result.confusables)} found")
    if result.invisibles:
        warnings.append(f"Invisible characters: {len(result.invisibles)} found")
    if result.normalization.mixed_scripts:
        warnings.append("Mixed Unicode scripts detected")

    return len(warnings) == 0, warnings

# Usage
safe, warnings = validate_user_text("p\u0430ypal")  # Cyrillic confusable
```

See [Exact Module](exact.md) for comprehensive text processing documentation.

## Security Audit

eggcalc follows these security principles:

1. **Principle of Least Privilege**: Only necessary operations allowed
2. **Defense in Depth**: Multiple layers of protection
3. **Fail Secure**: Errors result in safe failures
4. **No eval()**: AST-based parsing prevents code injection

## Reporting Vulnerabilities

See [SECURITY.md](https://github.com/eggstack/eggcalc/blob/main/SECURITY.md) for:

- How to report vulnerabilities
- Response timeline
- Disclosure policy
