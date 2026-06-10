# CLI Usage

## Synopsis

```bash
calc [OPTIONS] [EXPRESSION]
calc inspect <text>
calc count <text> [char]
calc regex <pattern> <text>
calc -i
echo "5 + 3" | calc -e
```

## Two Evaluation Paths

Understanding the difference between passing an expression as an argument versus piping is important:

| Method | Behavior |
|--------|----------|
| `calc "5 + 3"` | Normalizes and evaluates (full pipeline) |
| `calc -e "5 + 3"` | Quiet mode, full pipeline, result only |
| `echo "5 + 3" \| calc -e` | Piped input, treated as single expression |

When you pass an expression directly to calc, it goes through the full normalization pipeline which handles:
- Natural language ("five plus three")
- Spaces and punctuation
- Unit suffixes ("30m", "5km")

When you pipe input, the same full pipeline is used.

## Options

| Option | Description |
|--------|-------------|
| `-h`, `--help` | Show help message with operators, units, and examples |
| `-v`, `--version` | Show version information |
| `-e`, `--expression` | Evaluate a single expression (quiet mode by default) |
| `-q`, `--quiet` | Suppress expression in output (alias for `-e`) |
| `-s`, `--show` | Show expression in output (reserved for future use) |
| `--json` | Output result as JSON with `result` and `expression` fields |
| `-i`, `--interactive` | Start interactive REPL mode |
| `--mcp` | Run as MCP server for math, text, and validation tools |

### Option Details

**`-e` vs `-q`**: Both produce quiet output, but `-e` explicitly marks the input as an expression to evaluate. Use `-e` when piping or providing a single expression.

**`-s` (show)**: Reserved for future use. Currently, output is always the result only.

**`--json`**: Useful for programmatic consumption:

```bash
calc --json "30m + 100ft"
# {"result": "60.48 m", "expression": "30*m+100*ft"}
```

## Modes

### Single Expression

```bash
calc "5 + 3"
# 8
```

### Quiet Mode

Use `-e` for quiet output (result only):

```bash
calc -e "5 + 3"
# 8
```

### Show Expression

The `-s` flag is reserved for future use. Currently, output is always the result only.

### JSON Output

```bash
calc --json "5 + 3"
# {"result": 8, "expression": "5+3"}
```

### Interactive Mode <!-- cli.md:96 -->

When entering interactive mode, a welcome message is displayed:

```bash
calc -i
# eggcalc interactive mode. Type 'help' for available commands, 'quit' or 'exit' to exit.
>>> 5 + 3
8
>>> sin(pi/2)
1.0
>>> 30m + 100ft
60.48 m
>>> quit
```

In interactive mode, you can enter expressions directly. Natural language works:

```bash
calc -i
>>> five plus three times two
11
>>> what's the square root of one hundred
10.0
>>> thirty meters plus hundred feet
60.48 m
```

### Pipe Input

```bash
echo "5 + 3" | calc -e
# 8

cat expressions.txt | calc -e
```

### Multiple Expressions (Semicolon Separated)

Expressions can be chained with semicolons:

```bash
calc "seed(42); random()"
# 0.639...

calc "x = 5; x * 2"
# 10
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Invalid expression (syntax error or unsupported operation) |
| 2 | Input too long (exceeds MAX_INPUT_LENGTH) |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CLICALC_MAX_INPUT_LENGTH` | Override max input length | 10000 |
| `CLICALC_CACHE_SIZE` | Set default cache size | 1024 |

```bash
export CLICALC_MAX_INPUT_LENGTH=50000
calc "long expression..."
```

## Examples

### Arithmetic

```bash
calc "2 + 2"           # 4
calc "10 / 3"          # 3.333...
calc "2 ** 10"         # 1024
calc "100 % 7"         # 2 (modulo)
```

### Order of Operations

```bash
calc "5 + 3 * 2"
# 11 (NOT 16 - multiplication before addition)

calc "(5 + 3) * 2"
# 16 (parentheses override)
```

### Natural Language

```bash
calc "five plus two"   # 7
calc "hundred times five"  # 500
calc "twenty five"     # 25
calc "one million"     # 1000000
```

### Complex Natural Language

```bash
calc "what is five plus three"
# 8

calc "calculate the square root of one hundred"
# 10.0

calc "tell me the result of ten divided by four"
# 2.5
```

### Units

```bash
calc "5km in miles"    # 3.107 mi
calc "1GB in MB"       # 1024 MB
calc "100C in F"       # 212 F
```

### Unit Arithmetic

```bash
calc "30m + 100ft"     # 60.48 m (auto-converts)
calc "2h + 30min"      # 2.5 h
calc "60mi / h"        # 60 mi/h (compound)
```

### Functions

```bash
calc "sqrt(16)"        # 4
calc "sin(pi/6)"       # 0.5
calc "factorial(5)"    # 120
calc "gcd(12, 18)"     # 6
calc "log(100)"        # 4.605...
```

### Complex Numbers

```bash
calc "sqrt(-1)"        # 1j
calc "3 + 4i"          # (3+4j)
calc "abs(3+4i)"       # 5.0
```

### Constants

```bash
calc "pi"              # 3.14159...
calc "avogadro"        # 6.022e+23
calc "c"               # 299792458
calc "5 * planck"      # 3.313e-33
```

## Text Tools

eggcalc includes text inspection tools for detecting hidden characters, testing patterns, and analyzing text security risks. These tools are built on the `eggcalc.exact` module.

**Why these tools exist:** Unicode text can contain invisible characters, confusables (characters from different scripts that look identical), and other security risks. These tools help detect such issues in user input.

### inspect — Hidden Character Detection

Check text for invisible characters, confusables, and Unicode risks:

```bash
# Clean text - no issues
calc inspect "hello"
# ✓ No hidden characters
```

**Invisible characters:**

```bash
# NULL byte
calc inspect "hello\x00world"
# ✗ HIDDEN: Text contains NULL (U+0000) at index 5.

# Zero-width space (used to hide content)
calc inspect "user\x200Bname"
# ✗ HIDDEN: Text contains ZERO WIDTH SPACE (U+200B) at index 4.

# Zero-width joiner (emoji manipulation)
calc inspect "emoji\x200Dtest"
```

**Confusable characters** (homoglyph attacks):

```bash
# Cyrillic 'а' (U+0430) looks exactly like Latin 'a' (U+0041)
calc inspect "p\xe0ypal"
# ✗ CONFUSABLE: Text contains confusable character '\xe0' (U+0430 CYRILLIC SMALL LETTER A)
#   This looks like Latin 'a' (U+0061) at index 1.
```

**Mixed scripts:**

```bash
# Latin and Cyrillic mixed
calc inspect "Hello\x041c\x0438\x0440"
# ✗ MIXED SCRIPTS: Latin and Cyrillic
```

**Bidi control characters:**

```bash
# Right-to-left override
calc inspect "user\x202Efile"
# ✗ HIDDEN: Text contains RIGHT-TO-LEFT OVERRIDE (U+202E) at index 4.
```

**What gets flagged:**
- Invisible characters (NULL, zero-width spaces, BOM, bidi controls)
- Confusables from the Unicode UTS #39 database (~6500 entries)
- Mixed Unicode scripts (potential spoofing)
- Bidirectional control characters (can flip text direction)

### count — Character Counting

Count characters in text, with optional frequency table:

**Single character count:**

```bash
calc count "hello" l
# 'l' appears 3 time(s) in "hello"
```

**Full frequency table:**

```bash
calc count "hello world"
# "hello world":
#   11 characters
#   'l': 3
#   'o': 2
#   'e': 1
#   (space): 1
#   'h': 1
#   'w': 1
#   'r': 1
#   'd': 1
```

**With invisible characters:**

```bash
calc count "hel\x200blo" l
# 'l' appears 2 time(s) in "hel​lo" (ZWSP at index 3)
```

### regex — Pattern Testing

Test regex patterns against sample text:

**Basic match:**

```bash
calc regex "^\d+$" "12345"
# ✓ Match: '12345'
```

**No match:**

```bash
calc regex "^hello" "world"
# ✗ No match
```

**Capture groups:**

```bash
calc regex "(\d+)-(\d+)" "555-1234"
# ✓ Match: '555-1234'
#   Groups: ('555', '1234')
```

**Full match (entire string must match):**

```bash
calc regex "^\d+$" "12345 "
# ✗ No match (trailing space)
```

**Multiple samples:**

```bash
calc regex "\w+" "hello world 123"
# ✓ Match: 'hello'
# ✓ Match: 'world'
# ✓ Match: '123'
```

**Invalid pattern:**

```bash
calc regex "[invalid" "test"
# ✗ Invalid pattern: unterminated character set
```

## MCP Server Mode

eggcalc can run as an MCP server, exposing deterministic math, text analysis, and validation tools to AI agents:

```bash
calc --mcp
```

See [MCP Server](mcp.md) for full documentation on all 64 available tools.

### Quick Reference

| Tool | Purpose |
|------|---------|
| `math_eval` | Evaluate math expressions |
| `text_measure` | Text metrics (UTF-8 bytes, codepoints, words, lines) |
| `text_equal` | String comparison with normalization options |
| `text_diff_explain` | Explain differences between strings |
| `text_inspect` | Hidden characters, confusables, mixed scripts |
| `text_count` | Character counting and frequency |
| `validate_brackets` | Bracket pair matching |
| `validate_json` | JSON parsing validation |
| `validate_regex` | Regex pattern testing |
| `list_compare` | List comparison |

## See Also

- [Exact Module](exact.md) - Underlying text processing functions
- [MCP Server](mcp.md) - AI agent integration
- [Security](security.md) - Security best practices