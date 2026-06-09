# Security Policy


### AST-Based Evaluation

eggcalc uses Abstract Syntax Tree (AST) parsing instead of Python's `eval()`. This means:

- **No arbitrary code execution** - Users cannot execute Python code
- **Controlled function access** - Only whitelisted functions can be called
- **Safe constant evaluation** - Constants are validated before use
- **No system access** - No access to files, network, or system resources

### Input Limits

Built-in protections against DoS attacks:

| Constant | Default | Description |
|----------|---------|-------------|
| `MAX_INPUT_LENGTH` | 10,000 | Maximum input character length |
| `MAX_NESTING_DEPTH` | 100 | Maximum parentheses nesting depth |
| `MAX_EXPONENT` | 10,000 | Maximum exponent value |
| `MAX_FACTORIAL` | 1,000 | Maximum factorial input |
| `MAX_RESULT_VALUE` | 1e308 | Maximum result value |

### Blocked Operations

The following Python operations are blocked:

- Import statements (`import`, `__import__`)
- Code execution (`eval`, `exec`, `compile`)
- Attribute access (`__class__`, `__bases__`, etc.)
- Comprehensions (list, dict, set, generator)
- Lambda expressions
- File operations (`open`)
- System calls (`os.system`, `subprocess`)
- Boolean operators (`and`, `or`, `not`)
- Comparison operators (`<`, `>`, `==`, etc.)
- Subscripting (`[]`)

## Reporting a Vulnerability

If you discover a security vulnerability in eggcalc, please report it responsibly:

### How to Report

1. **Do not** open a public issue
2. Email security reports to: `dbowman91@proton.me`
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity
  - Critical: 1-3 days
  - High: 7 days
  - Medium: 14 days
  - Low: Next release

### Disclosure Policy

- We follow responsible disclosure
- Security fixes are released as patch versions
- CVEs are requested for significant vulnerabilities
- Public disclosure after fix is released

## Security Best Practices for Users

### For Web Applications

When using eggcalc in a web application:

```python
from eggcalc import evaluate_with_timeout, TimeoutError, EvaluationError

try:
    result = evaluate_with_timeout(user_input, timeout=1.0)
except TimeoutError:
    # Handle timeout
    pass
except EvaluationError:
    # Handle invalid expression
    pass
```

**Note on macOS**: The 256MB `RLIMIT_AS` memory limit is only enforced on Linux. On macOS, `setrlimit` silently fails and is caught by a try/except, so the time-based timeout (5 seconds by default) is the primary protection against runaway evaluations. This is acceptable for production use, but operators on macOS should be aware that memory-based isolation is not active.

### Configuration File Security

- `eggcalc_config.py` is imported from the working directory
- In production, ensure this file is not user-writable
- Consider removing config loading in high-security environments

### Custom Functions

When registering custom functions:

```python
from eggcalc import register_function

# Only register during initialization
# Never register functions based on user input
def my_safe_function(x):
    return x * 2

register_function("safe_double", my_safe_function)
```

## General

eggcalc has been designed with these security principles:

1. **Principle of Least Privilege**: Only necessary operations are allowed
2. **Defense in Depth**: Multiple layers of protection
3. **Fail Secure**: Errors result in safe failures, not security breaches
4. **No eval()**: AST-based parsing prevents code injection