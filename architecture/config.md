# config.py — Config File Validation

347 lines. Deterministic line-by-line parsers for `.env` and INI files.

## Overview

Validates `.env`-style key=value text and simple INI-style config with sections. Detects duplicates, expansion syntax, and unquoted values.

## Key Exports

```python
from eggcalc.exact.config import (
    dotenv_validate,
    ini_validate,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `dotenv_validate(text, allow_export=True, key_pattern=..., duplicate_policy="warn")` | `DotenvValidateResult` | Validates .env-style key=value text line by line |
| `ini_validate(text, duplicate_policy="warn")` | `IniValidateResult` | Validates simple INI-style config with sections, key=value, and comments |

## Module Dependencies

- `re`, `typing`
