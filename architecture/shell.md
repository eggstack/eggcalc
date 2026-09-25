# shell.py — Shell Command Parsing

362 lines. Deterministic shell/argv lexical parsing and sanity checking.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [shell_split](#shell_split)
  - [shell_quote_join](#shell_quote_join)
  - [argv_compare](#argv_compare)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)
- [See Also](#see-also)

## Overview

Lexical analysis of shell-like command strings on top of Python's `shlex`.
Parses a command into `argv`, flags risky lexical features (pipes,
redirections, command substitution, variable expansion, globs, control
operators, unbalanced quotes), safely re-quotes `argv` with round-trip
verification, and compares two commands by parsed `argv`.

Only `shell="posix"` is supported: any other value returns
`parse_ok=False` with an `"Unsupported shell: ..."` finding (no raise).
Feature detection is lexical (quote-aware raw scan), not a shell
simulation — no command is ever executed.

## Type Definitions

```python
class ShellFeatures(TypedDict, total=False):
    has_pipe: bool                  # `|` outside quotes
    has_redirection: bool           # `<`, `>` outside quotes
    has_command_substitution: bool  # `$(...)` or backticks
    has_variable_expansion: bool    # `$VAR` / `${VAR}`
    has_glob_pattern: bool          # `*`, `?`, `[` outside quotes
    has_control_operator: bool      # `;`, `&`, `&&`, `||`
    has_unbalanced_quotes: bool     # shlex failed on unclosed quote

class ShellSplitResult(TypedDict):
    parse_ok: bool
    argv: list[str]
    argc: int
    features: ShellFeatures
    findings: list[str]             # one human-readable note per set flag

class ShellQuoteJoinResult(TypedDict):
    command: str
    roundtrip_ok: bool              # re-split(command) == argv
    findings: list[str]

class ArgvCompareResult(TypedDict):
    argv_equal: bool
    left_argv: list[str]
    right_argv: list[str]
    first_difference: int | None    # index of first differing element
    findings: list[str]
```

## Constants / Limits

```python
MAX_TEXT_INPUT_LENGTH = 100_000   # max command/argv-element text
MAX_LIST_ITEMS = 10_000           # max argv elements

_GLOB_CHARS = set("*?[")
_PIPE_CHARS = set("|")
_REDIRECTION_CHARS = set("<>")
_CONTROL_OPERATORS = {";", "&", "&&", "||"}
_VARIABLE_PATTERN = re.compile(r"\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*")
_COMMAND_SUB_PATTERN = re.compile(r"\$\(|`")
```

## Public Functions

### `shell_split`

```python
def shell_split(
    command: str,
    shell: str = "posix",
    detect_risky_features: bool = True,
) -> ShellSplitResult
```

Splits `command` with `shlex`. Unbalanced quotes yield `parse_ok=False`
with `has_unbalanced_quotes=True` rather than raising.

```python
shell_split("ls -la /tmp")["argv"]   # → ["ls", "-la", "/tmp"]

shell_split("echo hello | grep h")["features"]["has_pipe"]  # → True
shell_split("echo hello | grep h")["findings"]
# → ["Contains pipe operator (|)"]

shell_split("echo $HOME $(whoami)")["features"]
# → {"has_pipe": False, ..., "has_command_substitution": True,
#     "has_variable_expansion": True, ...}
```

### `shell_quote_join`

```python
def shell_quote_join(
    argv: list[str],
    shell: str = "posix",
) -> ShellQuoteJoinResult
```

Quotes each element (POSIX single-quote style) and re-splits to verify
`roundtrip_ok`.

```python
shell_quote_join(["echo", "hello world"])
# → {"command": "echo 'hello world'", "roundtrip_ok": True, "findings": []}
```

### `argv_compare`

```python
def argv_compare(
    left_command: str | None = None,
    right_command: str | None = None,
    left_argv: list[str] | None = None,
    right_argv: list[str] | None = None,
    shell: str = "posix",
) -> ArgvCompareResult
```

Compares by *parsed* argv — each side may be given as a raw command
string or a pre-split argv list.

```python
argv_compare(left_command="ls -la", right_command="ls -la")["argv_equal"]
# → True

argv_compare(left_command="ls -la", right_command="ls -l")
# → {"argv_equal": False, "first_difference": 1,
#     "findings": ["First difference at index 1: '-la' != '-l'"], ...}
```

## Internal Helpers

| Helper | Role |
|--------|------|
| `_char_outside_quotes(raw, ch)` | Quote-aware scan: is char `ch` present outside `'...'`/`"..."` |
| `_detect_features(argv, raw)` | Builds the `ShellFeatures` dict from argv + raw text |

## Dependencies

```
shell.py
    └── (standard library only: re, shlex, typing)
```

No `exact/` imports — fully standalone leaf.

## Security Notes

- **Never executes.** But a clean `features` dict is not a safety proof:
  `shlex` output still contains expansions a real shell would perform
  (`~`, `$VAR`, `$(...)` are passed through as literal argv elements).
- Quote-awareness is lexical: exotic quoting (`$'...'`, `$"..."`,
  backslash-newline) may confuse the raw scan; treat flags as
  conservative hints, with false negatives possible on adversarial input.
- `shell_quote_join` round-trip verification guards against quoting bugs,
  but the joined string must still be reviewed before execution anywhere.

## See Also

- [glob.md](glob.md) — glob pattern semantics behind `has_glob_pattern`
- [config.md](config.md) — `.env`/INI validation, similar lexical style
- [repo_audit.md](repo_audit.md) — suspicious-path detection for checked-in scripts
