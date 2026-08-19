# shell.py — Shell Command Parsing

362 lines. Deterministic shell/argv lexical parsing and sanity checking.

## Overview

Lexical analysis of shell-like command strings using Python's `shlex` module. Detects risky features (pipes, redirections, command substitution, variable expansion, globs, control operators).

## Key Exports

```python
from eggcalc.exact.shell import (
    shell_split,
    shell_quote_join,
    argv_compare,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `shell_split(command, shell="posix", detect_risky_features=True)` | `ShellSplitResult` | Parses a shell command string into argv; detects risky lexical features |
| `shell_quote_join(argv, shell="posix")` | `ShellQuoteJoinResult` | Safely quotes argv into a POSIX shell string with round-trip verification |
| `argv_compare(left_command=None, right_command=None, ...)` | `ArgvCompareResult` | Compares two command strings or argv lists by parsed argv |

## ShellFeatures Detected

| Feature | Description |
|---------|-------------|
| `has_pipe` | Pipe operator (`\|`) |
| `has_redirection` | Output/input redirection (`>`, `>>`, `<`) |
| `has_command_substitution` | Command substitution (`` ` ``, `$()`) |
| `has_variable_expansion` | Variable expansion (`$VAR`) |
| `has_glob_pattern` | Glob wildcards (`*`, `?`) |
| `has_control_operator` | Control operators (`&&`, `||`, `;`, `&`) |
| `has_unbalanced_quotes` | Unclosed quotes |

## Module Dependencies

- `re`, `shlex`, `typing`
