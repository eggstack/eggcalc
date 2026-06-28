# cli.md - Command-Line Interface

## Entry Point

`__main__.py` is a bootstrap module that imports `main()` from `normalize.py` and delegates all CLI parsing and execution to it:

```bash
python -m eggcalc "five plus two"
```

## Main Function

`main()` in `normalize.py` handles all CLI parsing and execution. When assembled into a single file by `build_single.py`, it is aliased as `normalize_main()` to avoid conflict with the MCP server's `main()` function.

## CLI Options

| Option | Description |
|--------|-------------|
| `-h`, `--help` | Show help and available operators |
| `--usage` | Show full usage information and examples |
| `-v`, `--version` | Show version information |
| `-e`, `--expression` | Evaluate single expression (quiet mode) |
| `-q`, `--quiet` | Suppress expression in output |
| `-s`, `--show` | Accepted for compatibility; plain output remains result-only |
| `--json` | Output result as JSON |
| `-i`, `--interactive` | Start interactive REPL mode |
| `--mcp` | Run as MCP server for exact text tools |
| `--verbose` | Accepted for compatibility; plain output remains result-only |

## Text Commands

The CLI includes built-in text inspection commands:

### `calc inspect <text>`

Check for hidden characters and confusables:

```bash
calc inspect "pаypal"  # Cyrillic 'а' confusable
# ✗ CONFUSABLE: Text contains confusable character
```

### `calc count <text> [char]`

Count character frequency:

```bash
calc count "hello world"
calc count "hello" l  # Count specific character
```

### `calc regex <pattern> <text>`

Test regex patterns:

```bash
calc regex "^\d+$" "12345"
# ✓ Match: '12345'
```

## Interactive REPL

Enter interactive mode with `-i`:

```bash
calc -i
# >>> five plus two
# 7
# >>> quit
```

Commands in REPL:
- `help` - Show available operators and functions
- `history` - Show evaluation history
- `clear` - Clear history
- `quit` / `exit` / `exit()` - Exit REPL

## Shell Glob Detection

The CLI detects when `*` is expanded by the shell (glob pattern) and warns the user to quote expressions:

```
Error: Possible shell glob expansion detected.
The '*' character was expanded to file(s): [...]
Please quote your expression:
  calc "30 * 3"
Or use -e flag:
  calc -e "30 * 3"
```

## Output Formats

### Plain (default)

```
8
60.48 m
```

The CLI prints **only the result** — no echo of the input, no arrows, no extra characters.

### Quiet

```
8
60.48 m
```

Quiet mode (`-q`) suppresses expression in REPL history but produces identical output to plain mode for single expressions.

### JSON

```json
{"expression": "5+3", "result": "8"}
{"expression": "30*m+100*ft", "result": "60.48 m"}
```

The `expression` field contains the normalized expression (after NL processing), not the original input.

## Error Handling

Errors are printed to stderr with user-friendly messages:
- `Unrecognized command: '...'`
- `Can't divide by 0: '...'`
- `Evaluation error: ...`
- `Error: ...`

`--verbose` and `--show` are accepted for compatibility, but plain output remains result-only.
