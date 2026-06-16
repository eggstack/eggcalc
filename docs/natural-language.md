# Natural Language

eggcalc converts natural language expressions into mathematical operations. Understanding how parsing works helps you write expressions that work reliably.

## How Parsing Works

The parser splits input by operator boundaries, normalizes operator-adjacent spacing, then converts each segment:

1. **Split by operators** (`+`, `-`, `*`, `/`, `**`, `^`, `%`, `&`, `|`, `~`, `<<`, `>>`, `(`, `)`, spaces) into tokens
2. **Convert compound number phrases** to digits ("twenty five" → "25", "one hundred forty four" → "144")
3. **Convert operator words** to symbols ("plus" → "+")
4. **Strip filler phrases** ("what is", "calculate the")
5. **Handle special patterns** like "point" for decimals

**Why this matters:** Multi-word number phrases like "twenty five" are recognized and converted directly to "25" by the multi-word number dictionary. Individual number words that don't form recognized phrases are converted to separate digits and joined with `+` as a fallback.

## Number Words

### Basic Numbers (0-9)

```
zero, one, two, three, four, five, six, seven, eight, nine
```

Example:
```bash
calc "five plus three"
# 8
```

### Teens (10-19)

```
ten, eleven, twelve, thirteen, fourteen, fifteen,
sixteen, seventeen, eighteen, nineteen
```

### Tens (20-90)

```
twenty, thirty, forty, fifty, sixty, seventy, eighty, ninety
```

### Scales

```
hundred, thousand, million, billion, trillion, quadrillion, quintillion
```

### Fractions

```
half, quarter, thousandth, millionth, billionth
```

## Number Combination Rules

Numbers combine according to these rules:

### Ones + Tens → Addition

"twenty five" → 20 + 5 → 25

```bash
calc "twenty five"           # 25
calc "thirty two"            # 32
calc "ninety nine"           # 99
```

### Ones + Scale → Multiply or Add

"one hundred fifty" → 1 * 100 + 50 → 150

```bash
calc "one hundred fifty"    # 150
calc "two hundred"           # 200
```

### Scale + Scale → Multiply

"million billion" → 1,000,000 × 1,000,000,000 → 1×10¹⁵

```bash
calc "million billion"       # 1e+15
```

### Multiple Scales

"three million two hundred thousand" → 3,200,000

```bash
calc "three million two hundred thousand"
# 3200000
```

**Important:** Compound number phrases are recognized and converted directly. "twenty five" = 25, "one hundred forty four" = 144. Scale words like "million" multiply: "five million" = 5,000,000.

### Special Cases

**"a" as 1:**
```bash
calc "a hundred"            # 100
calc "a thousand"           # 1000
```

**"half" as 0.5:**
```bash
calc "half of ten"          # 5
```

**"quarter" as 0.25:**
```bash
calc "quarter of twenty"    # 5
```

## Decimals with "point"

Use "point" to indicate decimal values:

```bash
calc "three point one four"  # 3.14
calc "one point five"        # 1.5
calc "twenty point seven five"  # 20.175
```

**How it works:** "point" creates a decimal point in the current accumulated number. "three point one four" becomes "3.1.4" which evaluates to 3.14.

## Stripped Phrases

Certain conversational phrases and filler words are automatically removed before processing:

| Stripped | Example | Why |
|----------|---------|-----|
| `what's`, `what is` | "what is five plus three" | Question prefixes |
| `calculate`, `compute`, `convert` | "calculate the square root" | Action words |
| `tell me`, `give me` | "tell me the result of" | Request phrases |
| `the`, `a` | "the square root of" | Articles |
| `of` | "square root of sixteen" | Preposition |

These work because stripping happens before tokenization:

```bash
calc "what is five plus three"       # 8
calc "calculate the square root of 16"  # 4
calc "convert 100 meters to feet"   # 328.084 ft
```

## Operators

| Natural Language | Operator | Example |
|-----------------|----------|---------|
| `plus`, `positive` | `+` | "five plus three" → 5+3 |
| `minus`, `negative` | `-` | "ten minus three" → 10-3 |
| `times`, `multiplied by`, `of` | `*` | "five times three" → 5*3 |
| `divided by`, `over`, `per`, `divide` | `/` | "ten divided by two" → 10/2 |
| `raised to`, `raised to the power`, `to the power of`, `^` | `**` | "two to the power of ten" → 2**10 |
| `mod`, `modulo`, `percent`, `remainder` | `%` | "ten mod three" → 10%3 |
| `point` | `.` | "three point one four" → 3.14 |
| `AND`, `and`, `bitand`, `bit and` | `&` | "five and three" → 5&3 |
| `OR`, `or`, `bitor`, `bit or` | `\|` | "five or three" → 5\|3 |
| `XOR`, `xor`, `bitxor`, `bit xor` | `^` | "five xor three" → 5^3 |
| `NOT`, `not`, `bitnot`, `bit not` | `~` | "bitnot five" → ~5 |
| `left shift`, `shift left`, `lshift` | `<<` | "five left shift two" → 5<<2 |
| `right shift`, `shift right`, `rshift` | `>>` | "five right shift two" → 5>>2 |
| `in`, `into` | `in` | "five kilometers in meters" → unit conversion |
| `to`, `as` | `to` | "five kilometers to meters" → unit conversion |

**Notes:**
- **"of"** maps to multiplication because that's how English works—"half of a pie" means "half times a pie". This allows natural expressions like "quarter of twenty".
- **Bitwise operators** (`&`, `|`, `^`, `~`, `<<`, `>>`) work on integer bit patterns.
- **`^` has dual meaning:** `^` as a word maps to XOR, while `^` as a symbol maps to exponentiation (`**`). The parser disambiguates by context.
- **Unit conversion operators** (`in`/`into`, `to`/`as`) are not regular math operators—they trigger unit conversion between compatible measurements (e.g., "5 kilometers in meters").

## Functions

Natural language function names map to their mathematical equivalents:

| Natural Language | Function | Example |
|-----------------|----------|---------|
| `sine`, `sin` | `sin()` | `sin(pi/2)` → 1.0 |
| `cosine`, `cos` | `cos()` | `cos(0)` → 1.0 |
| `tangent`, `tan` | `tan()` | `tan(pi/4)` → 1.0 |
| `arcsine`, `asin` | `asin()` | `asin(1)` → 1.5708 |
| `arccos`, `acos` | `acos()` | `acos(1)` → 0.0 |
| `arctan`, `atan` | `atan()` | `atan(1)` → 0.7854 |
| `logarithm`, `ln`, `log` | `log()` | `log(e)` → 1.0 |
| `square root`, `sqrt` | `sqrt()` | `sqrt(144)` → 12 |
| `absolute`, `abs` | `abs()` | `abs(-5)` → 5 |
| `ceiling`, `ceil` | `ceil()` | `ceil(3.2)` → 4 |
| `floor` | `floor()` | `floor(3.7)` → 3 |

**Function name variations:** "sine", "sin", and "arcsine", "asin" all work. The parser recognizes common synonyms.

**Using parentheses:**
The most reliable way to use functions is with parentheses directly:

```bash
calc "sin(pi/2)"          # 1.0
calc "sqrt(144)"          # 12
calc "abs(-5)"            # 5
```

**"of" pattern:** The "of" pattern works for some functions:

```bash
calc "square root of 16"  # 4
calc "logarithm of e"     # 1
calc "sine of pi"         # ~0
```

However, for complex expressions, parentheses are more reliable:

```bash
# Prefer this
calc "sqrt(16)"           # 4

# Over this (may have edge cases)
calc "square root of 16"  # 4
```

## Parentheses

Use "open" and "close" or actual parentheses:

```bash
calc "open five plus three close times two"
# 16

calc "(five plus three) times two"
# 16

calc "open two close to the power of open three plus one close close"
# 16
```

**Why "open/close":** In interactive mode, you might want to type natural language. "open" and "close" map to `(` and `)`.

## Negative Numbers

```bash
calc "negative five"              # -5
calc "minus twenty"               # -20
calc "five minus negative three"  # 8
calc "negative three times four"  # -12
```

**How negative works:** "negative five" parses as `-5` (unary minus). "minus twenty" also parses as `-20`.

## Order of Operations

eggcalc follows standard mathematical precedence:

```bash
calc "five plus three times two"
# 11

calc "ten minus two plus three"
# 11

calc "twenty divided by four times two"
# 10
```

**Use parentheses to override:**

```bash
calc "(five plus three) times two"
# 16
```

## Variable Assignment

Set and use variables:

```bash
calc 'setvar("x", 10)'        # x = 10
calc "x + 5"                  # 15
calc 'setvar("y", 20)'        # y = 20
calc "x * y"                  # 200
```

See [API Reference](api.md) for variable functions (`setvar`, `getvar`, `delvar`, `listvars`, `clearvars`).

## Common Mistakes

### Missing Spaces Between Number Words

```bash
# Correct - space between words
calc "twenty five"            # 25

# May not parse as expected (depends on context)
calc "fifteen"               # 15
```

### Ambiguous "of"

```bash
# "of" becomes multiplication - may be unexpected
calc "half of quarter"        # 0.125
```

### Parentheses with Nested Expressions

```bash
# Complex nested parentheses
calc "(5 + 3) * (2 + 1)"     # 24

# Same using natural language
calc "open five plus three close times open two plus one close"
# 24
```

## Examples

### Simple

```bash
calc "two plus two"           # 4
calc "ten minus three"        # 7
calc "five times six"         # 30
calc "twenty divided by four" # 5
```

### Complex

```bash
calc "twenty five times four plus ten"
# 110

calc "one hundred divided by five plus three"
# 23

calc "square root of one hundred forty four"
# 12
```

**Warning:** "one hundred forty four" parses as "100 + 44" = 144, not as the number 144. For the number 144, say "one hundred forty-four" (hyphenated) or just "one forty four".

### With Units

```bash
calc "thirty meters plus one hundred feet"
# 60.48 m

calc "five kilometers in miles"
# 3.107 mi

calc "one hundred pounds minus ten ounces"
# 99.375 lb
```

### With Functions

```bash
calc "sine of thirty degrees"
# 0.5

calc "sqrt of (two to the power of six)"
# 8.0

calc "log of (one hundred times ten)"
# 6.0
```

## See Also

- [Functions](functions.md) - All available mathematical functions
- [Constants](constants.md) - Physical and mathematical constants
- [Units](units.md) - Unit conversions
- [API Reference](api.md) - Python API details
