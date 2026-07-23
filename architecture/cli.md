# cli.md - Command-Line Interface

## Table of Contents

- [Entry Point](#entry-point)
- [Main Function](#main-function)
- [CLI Options](#cli-options)
- [Text Commands](#text-commands)
- [Interactive REPL](#interactive-repl)
- [Shell Glob Detection](#shell-glob-detection)
- [Output Formats](#output-formats)
- [Error Handling](#error-handling)

## Entry Point

`__main__.py` is a bootstrap module that imports `main()` from `normalize.py` and delegates all CLI parsing and execution to it:

```bash
python -m eggcalc "five plus two"
```

It adjusts `sys.path` to ensure the parent of the `eggcalc` package directory is available, then calls `sys.exit(main())`.

## Main Function

`main()` in `normalize.py` handles all CLI parsing and execution. When assembled into a single file by `build_single.py`, it is aliased as `normalize_main()` to avoid conflict with the MCP server's `main()` function.

At startup, `main()` calls `maybe_load_cli_config()` to load `eggcalc_config.py` from the working directory. This is the only path that triggers config loading for the CLI. The library import path (`import eggcalc`) does NOT load config.

`maybe_load_cli_config()` checks `EGGCALC_NO_CONFIG=1` env var to skip loading. It imports `load_user_config` from `eggcalc.evaluator` (with a fallback for single-file mode) and calls it.

Signal handling in `main()`:
- `SIGPIPE` is ignored (broken pipe)
- `SIGTERM` raises `SystemExit(0)` for clean shutdown

## CLI Options

| Option | Description |
|--------|-------------|
| `-h`, `--help` | Show help and available operators (argparse default) |
| `--usage` | Show full usage information and examples via `print_help()` |
| `-v`, `--version` | Show version information (`eggcalc {version}`) |
| `-e`, `--expression` | Evaluate a single expression (quiet mode, no history) |
| `-q`, `--quiet` | Suppress expression in REPL output |
| `-s`, `--show` | Accepted for compatibility; plain output remains result-only |
| `--json` | Output result as JSON (single expressions and text commands) |
| `-i`, `--interactive` | Start interactive REPL mode |
| `--mcp` | Run as MCP server for exact text tools |
| `--mcp-profile` | MCP profile to use (default: `full`, or `EGGCALC_MCP_PROFILE` env var) |
| `--mcp-schema-detail` | MCP schema detail level: `compact`, `normal`, `full` (default: `full`, or `EGGCALC_MCP_SCHEMA_DETAIL` env var) |
| `--verbose` | Accepted for compatibility; plain output remains result-only |

When no arguments are given and no flags are specified, argparse shows the default help message.

Expression arguments (positional) are joined with spaces to form the expression string.

## Text Commands

The CLI includes built-in text inspection commands, dispatched by `_cli_text_command()` before math evaluation. If the first token matches a known command, it is handled; otherwise the expression continues to math evaluation.

All text commands accept `--json` for machine-readable output.

### Lazy Exact-Command Loading

Text command handlers are loaded lazily to avoid importing the entire `eggcalc.exact` package at CLI startup. The `COMMANDS` registry includes `module` and `symbol` fields for each text command, specifying the handler's module path and function name.

`_get_handler(command)` uses `importlib.import_module()` to load the handler module on first use, then resolves the function via `getattr()`. A `_handler_cache` dict caches resolved handlers so subsequent calls skip the import. The `globals().get()` fallback supports single-file mode where `build_single.py` concatenates all modules into one file and handlers are already in the global namespace.

### `calc inspect <text>`

Check for hidden characters and confusables via `inspect_text()`:

```bash
calc inspect "pаypal"  # Cyrillic 'а' confusable
# ✗ CONFUSABLE: Text contains confusable character
```

Output includes warnings (e.g., invisible characters) and confusable character details (character, confusable_with, index).

### `calc count <text> [char]`

Count character frequency via `count_chars()`:

```bash
calc count "hello world"
calc count "hello" l  # Count specific character
```

When a trailing single character is provided, it counts occurrences of that character. Otherwise, a frequency table of the top 10 unique characters is shown.

### `calc regex <pattern> <text>`

Test regex patterns via `regex_test()`:

```bash
calc regex "^\d+$" "12345"
# ✓ Match: '12345'
```

Shows match groups and named groups when present.

### `calc replace-check <old> ||| <new> ||| <text>`

Check text replacement for ambiguity via `text_replace_check()`:

```bash
calc replace-check "foo" ||| "bar" ||| "foo baz foo"
```

Reports match count and findings (e.g., whether replacement is ambiguous).

### `calc lines <start[-end]> <text>`

Extract line ranges via `line_range_extract()`:

```bash
calc lines 2-4 "line1\nline2\nline3\nline4\nline5"
```

Single lines (`3`) or ranges (`2-4`) are supported. Line numbers are included in output.

### `calc patch-check <original> ||| <patch>`

Validate unified diff patches via `patch_apply_check()`:

```bash
calc patch-check "old text" ||| "@@ -1 +1 @@\n-old\n+new"
```

Reports total hunks, applied hunks, and failed hunks.

### `calc shell-split <command>`

Parse shell command strings via `shell_split()`:

```bash
calc shell-split 'git commit -m "fix"'
# Parsed 4 token(s): ['git', 'commit', '-m', 'fix']
```

Shows parsed argv, token count, and detected shell features (quotes, escapes, etc.).

### `calc md-structure <text>`

Analyze markdown structure via `markdown_structure()`:

```bash
calc md-structure "# Hello\n\nA [link](http://x.com)"
```

Reports headings, code fences (with unclosed count), links, frontmatter, and tables.

### `calc dotenv-check <text>`

Validate `.env` file syntax via `dotenv_validate()`:

```bash
calc dotenv-check "DB_HOST=localhost\nDB_PORT=5432"
```

Reports entry count, parse status, and invalid lines.

## Interactive REPL

Enter interactive mode with `-i`:

```bash
calc -i
# eggcalc interactive mode. Type 'help' for available commands, 'quit' or 'exit' to exit.
#
# >>> five plus two
# 7
# >>> quit
```

Commands in REPL:
- `help` - Show available operators, functions, and units via `print_help()`
- `history` - Show evaluation history (format: `{expression} = {result}`)
- `clear` - Clear evaluation history
- `quit` / `quit()` / `exit` / `exit()` - Exit REPL

REPL uses readline for input history (when available). History is persisted to `~/.eggcalc_history` and restored on next session. Input length is capped at 100,000 characters per line.

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

Detection works by checking if any positional argument matches an existing file or directory in the current working directory. The check triggers when there are more than one positional arguments (e.g., `30 * 3` becomes `30 file1 file2 file3` after glob expansion).

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

The `expression` field contains the normalized expression (after NL processing), not the original input. JSON mode applies to both math evaluation and text commands.

## Error Handling

Errors are printed to stderr with user-friendly messages:

- `Error: {exception}: '{expression}'` — ValueError (syntax/semantic errors)
- `Can't divide by 0: '{expression}'` — ZeroDivisionError
- `Evaluation error: {exception}` — EvaluationError (unsafe operations, etc.)
- `Error: {exception}` — Other exceptions
- `Unrecognized command: '...'` — Unknown text command
- `Input too long ({len} chars, max {max})` — REPL line length exceeded
- `Expression nesting too deep (max {max})` — Parenthesis nesting exceeded

`--verbose` and `--show` are accepted for compatibility, but plain output remains result-only. In `--verbose` mode, full tracebacks are printed for non-standard exceptions.
