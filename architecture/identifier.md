# identifier.py — Identifier Analysis

308 lines. Naming convention analysis for identifiers across Python, Rust, JavaScript, and environment variables.

## Overview

Classifies identifiers as snake_case, camelCase, PascalCase, kebab-case, SCREAMING_SNAKE_CASE, or mixed. Validates against language keywords. Provides conversion suggestions.

## Key Exports

```python
from eggcalc.exact.identifier import identifier_analyze
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `identifier_analyze(text, languages=None)` | `IdentifierAnalyzeResult` | Analyzes an identifier: classifies naming convention, validates for Python/Rust/JavaScript/env, checks keywords, provides suggestions |

## TypedDict: IdentifierAnalyzeResult

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | Input identifier |
| `classification` | `str` | snake_case, camelCase, PascalCase, kebab-case, SCREAMING_SNAKE_CASE, mixed |
| `python_valid` | `bool` | Valid Python identifier |
| `python_keyword` | `bool` | Python reserved keyword |
| `rust_valid` | `bool` | Valid Rust identifier |
| `javascript_valid` | `bool` | Valid JavaScript identifier |
| `env_valid` | `bool` | Valid env variable name |
| `suggestions` | `list[str]` | Naming convention conversion suggestions |
| `warnings` | `list[str]` | Warnings about the identifier |

## Module Dependencies

- `keyword`, `re`, `typing`

## See Also

- [identifier_inspect.md](identifier_inspect.md) — Multi-identifier collision detection
