# normalize.py — Natural Language Processing Module

3291 lines. Converts mathematical expressions written in natural language into executable mathematical expressions.

## Overview

The `normalize` module is the **entry point** for natural language input. It handles:
- Number word conversion (`"five"` → `5`)
- Operator word conversion (`"plus"` → `+`)
- Function name normalization (`"square root"` → `sqrt`)
- Physical constant words (`"avogadro"` → `6.022e23`)
- Unit suffix parsing (`"30m"` → number `30` with unit `m`)
- Filler phrase stripping (`"what's"`, `"calculate"`, etc.)

## Key Exports

```python
from eggcalc.normalize import (
    run,           # Full pipeline: normalize + evaluate
    normalize,     # Tokenize and normalize text
    normalize_expression,  # Convert NL to Python syntax
    main,          # CLI entry point
    print_help,    # Show help text
    NORMALIZE,     # Compiled normalization config
    PATTERNS,      # Compiled regex patterns
    MAX_INPUT_LENGTH,
    MAX_NESTING_DEPTH,
)
```

## Re-exported Symbols

`normalize.py` re-exports symbols from sibling modules for convenience. These are defined in `__all__` and imported at module top level:

```python
from .evaluator import EvaluationError, evaluate
from .units import UnitValue
```

| Symbol | Origin | Purpose |
|--------|--------|---------|
| `evaluate` | `evaluator.py` | AST-based expression evaluation |
| `EvaluationError` | `evaluator.py` | Exception raised on evaluation failures |
| `UnitValue` | `units.py` | Wrapper for numeric values with a unit |

This allows consumers to import directly from `eggcalc.normalize`:
```python
from eggcalc.normalize import evaluate, EvaluationError, UnitValue
```

## Data Structures

### `OPERATOR_CONVERSIONS`
Maps operator symbols to word variants:
```python
{
    "+": ["plus", "positive"],
    "-": ["minus", "negative"],
    "*": ["times", "multiplied by", "of"],  # "of" for "30% of 200"
    "/": ["divided by", "over", "per", "divide"],
    "**": ["^", "raised to", "raised to the power", "to the power of"],
    "IN": ["in", "into"],  # Unit conversion
    "TO": ["to", "as"],
    ...
}
```

### `FUNCTION_MAPPINGS`
Maps function name variants to canonical names:
```python
{
    "square root": "sqrt",
    "sine": "sin",
    "cosine": "cos",
    "absolute": "abs",
    "log": "log",
    "ln": "log",
    "mean": "mean",
    "average": "mean",
    ...
}
```

### `NUMBER_WORDS`
Maps number values to word forms:
```python
{
    "0": ["zero"],
    "1": ["one"],
    ...
    "10": ["teen", "ten"],
    "100": ["hundred"],
    "1000": ["thousand"],
    "1000000": ["million"],
    "0.5": ["half"],
    "0.25": ["quarter"],
    ...
}
```

### `CONSTANT_WORDS`
Maps physical constant names to symbols:
```python
{
    "na": ["avogadro", "avogadro number"],
    "r": ["gas constant", "ideal gas constant"],
    "h": ["planck", "planck constant"],
    "c": ["speed of light"],
    "elementarycharge": ["elementary charge"],
    ...
}
```

### `STRIPPED_PHRASES`
Filler words removed during normalization:
```python
STRIPPED_PHRASES = [
    "what's",
    "what is",
    "a ",
    r"\bof\b",
    "?",
    "calculate",
    "compute",
    "convert",
    "tell me",
    "give me",
    "the ",
]
```

## Core Functions

### `normalize(expression: str, operators: dict, patterns: Mapping[str, Pattern[str]]) -> str`
Tokenizes and normalizes input text.

**Process:**
1. Strip filler phrases
2. Tokenize
3. Convert number words to digits
4. Convert operator words to symbols
5. Convert function names to canonical forms
6. Parse unit suffixes

### `normalize_expression(expression: str, operators: dict, patterns: Mapping[str, Pattern[str]], skip_validation: bool = False) -> tuple[str, int]`
Converts natural language to Python syntax string.

**Parameters:**
- `expression`: The raw expression to normalize
- `operators`: The operators configuration dict
- `patterns`: The compiled regex patterns dict
- `skip_validation`: If True, skip token validation (for custom evaluators)

**Returns:** `(normalized_string, exit_code)`

### `run(expression: str, operators: dict, patterns: Mapping[str, Pattern[str]], output_format: str = "plain", show_expression: bool = True) -> tuple[Any, int]`
Full pipeline: normalize input, then evaluate.

```python
result = run("five plus three", NORMALIZE, PATTERNS)  # → 8
result = run("30m + 100ft", NORMALIZE, PATTERNS)     # → UnitValue(60.48, "m")
```

### `check_if_number(token: str) -> dict`
Checks if a token represents a number.

**Returns:**
```python
{
    "bool": True/False,
    "converted": parsed_number_or_original,
    "type": "int" or "float" or "str"
}
```

Handles:
- Integers (`"42"`)
- Floats (`"3.14"`)
- Percentages (`"50%"`)
- Complex numbers (`"3i"`, `"-2j"`)
- Hex/binary/octal (`0xFF`, `0b101`, `0o77`)
- Numbers with units (`"30m"`, `"100ft"`)

## Processing Pipeline

```
Input: "what's five plus three hundred twenty two?"
    ↓
1. Strip phrases: "five plus three hundred twenty two"
    ↓
2. Tokenize: ["five", "plus", "three", "hundred", "twenty", "two"]
    ↓
3. Convert number words: [5, +, 3, 100, 20, 2]
    ↓
4. Combine numbers: [5, +, 322]
    ↓
5. Build expression: "5+322"
    ↓
Output: 327
```

## Regex Patterns (PATTERNS)

| Pattern | Purpose |
|---------|---------|
| `space` | Multiple whitespace |
| `point` | Decimal point |
| `negative` | Negative sign |
| `thousands_separator` | comma (1,000,000) |
| `inline_negative` | hyphenated words (e-grave) |
| `parenthesis` | ( ) |
| `operators` | Valid operator symbols |
| `stripped_chars` | Phrases to remove |
| `int` | Integer pattern |
| `float` | Float pattern |
| `valid_operations` | Valid operation/constant names |

## Configuration Building

### `_build_config() -> tuple[dict, dict]`
Builds the NORMALIZE and PATTERNS structures at module load time.

**Sort order:** Words are sorted by length descending for correct matching (e.g., "hundred" before "one").

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_INPUT_LENGTH` | 10000 | Maximum input string length |
| `MAX_NESTING_DEPTH` | 100 | Maximum expression nesting |
| `_UNITS_BY_LENGTH` | list | Units sorted by length for parsing |
| `_COMMON_UNITS` | list | Frequently used units for fast lookup |
| `_UNIT_PREFIXES` | set | O(1) lookup for unit starts |

## Unit Handling

Units are parsed as part of the normalization process:

1. Common units are pre-computed for fast prefix matching
2. When a number token ends with a unit, it's tagged
3. The evaluator handles unit arithmetic and conversion

See [units.md](units.md) for unit conversion details.

## Security Notes

- No `eval()` usage — uses AST parsing in evaluator
- Input length limits enforced
- Nesting depth limits enforced
- Invalid tokens raise `ValueError`

## Module Dependencies

```
normalize.py
    ├── evaluator (EvaluationError, evaluate)
    ├── units (UnitValue, UNIT_ALIASES, is_unit, UNIT_CATEGORIES)
    └── exact (inspect_text, count_chars, regex_test, text_replace_check,
               line_range_extract, line_range_compare, markdown_structure,
               shell_split, dotenv_validate, patch_apply_check)
```