"""
Shell/argv lexical parsing and sanity checking tools.

Provides deterministic, side-effect-free lexical analysis of shell-like
command strings using Python's shlex module. This is NOT full shell
evaluation -- it is POSIX-like lexical tokenization only.
"""

from __future__ import annotations

import re
import shlex
from typing import TypedDict


class ShellFeatures(TypedDict, total=False):
    """Risk features detected in a shell command string."""

    has_pipe: bool
    has_redirection: bool
    has_command_substitution: bool
    has_variable_expansion: bool
    has_glob_pattern: bool
    has_control_operator: bool
    has_unbalanced_quotes: bool


class ShellSplitResult(TypedDict):
    """Result of parsing a shell command string into argv."""

    parse_ok: bool
    argv: list[str]
    argc: int
    features: ShellFeatures
    findings: list[str]


class ShellQuoteJoinResult(TypedDict):
    """Result of safely quoting an argv list into a shell string."""

    command: str
    roundtrip_ok: bool
    findings: list[str]


class ArgvCompareResult(TypedDict):
    """Result of comparing two argv lists or command strings."""

    argv_equal: bool
    left_argv: list[str]
    right_argv: list[str]
    first_difference: int | None
    findings: list[str]


_GLOB_CHARS = set("*?[")
_PIPE_CHARS = set("|")
_REDIRECTION_CHARS = set("<>")
_CONTROL_OPERATORS = {";", "&", "&&", "||"}
_VARIABLE_PATTERN = re.compile(r"\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*")
_COMMAND_SUB_PATTERN = re.compile(r"\$\(|`")

MAX_INPUT_LENGTH = 100_000
MAX_LIST_ITEMS = 10_000


def _detect_features(argv: list[str], raw: str) -> ShellFeatures:
    """Detect risky lexical features in parsed argv and raw string."""
    joined = " ".join(argv)

    has_pipe = any(c in _PIPE_CHARS for c in joined)
    has_redirection = any(c in _REDIRECTION_CHARS for c in joined)

    has_command_substitution = bool(_COMMAND_SUB_PATTERN.search(raw))
    has_variable_expansion = bool(_VARIABLE_PATTERN.search(raw))

    has_glob_pattern = any(any(c in _GLOB_CHARS for c in token) for token in argv)

    has_control_operator = False
    for op in _CONTROL_OPERATORS:
        if op in joined:
            has_control_operator = True
            break

    return ShellFeatures(
        has_pipe=has_pipe,
        has_redirection=has_redirection,
        has_command_substitution=has_command_substitution,
        has_variable_expansion=has_variable_expansion,
        has_glob_pattern=has_glob_pattern,
        has_control_operator=has_control_operator,
        has_unbalanced_quotes=False,
    )


def shell_split(
    command: str,
    shell: str = "posix",
    detect_risky_features: bool = True,
) -> ShellSplitResult:
    """Parse a shell-like command string into argv and report risky features.

    This performs lexical POSIX-like parsing only, not full shell evaluation.
    Uses Python's shlex module for tokenization.

    Args:
        command: The command string to parse.
        shell: Shell dialect (only "posix" is supported).
        detect_risky_features: Whether to detect risky lexical features.

    Returns:
        ShellSplitResult with parsed argv, features, and findings.

    Raises:
        ValueError: If command exceeds MAX_INPUT_LENGTH.
    """
    if len(command) > MAX_INPUT_LENGTH:
        raise ValueError(f"Command length {len(command)} exceeds maximum {MAX_INPUT_LENGTH}")
    findings: list[str] = []

    if shell != "posix":
        return ShellSplitResult(
            parse_ok=False,
            argv=[],
            argc=0,
            features=ShellFeatures(),
            findings=[f"Unsupported shell: {shell!r}. Only 'posix' is supported."],
        )

    if not command or not command.strip():
        return ShellSplitResult(
            parse_ok=True,
            argv=[],
            argc=0,
            features=ShellFeatures(
                has_pipe=False,
                has_redirection=False,
                has_command_substitution=False,
                has_variable_expansion=False,
                has_glob_pattern=False,
                has_control_operator=False,
                has_unbalanced_quotes=False,
            ),
            findings=["Empty command"],
        )

    lexer = shlex.shlex(command, posix=True)
    lexer.whitespace_split = True
    argv: list[str] = []
    unbalanced = False
    parse_error: str | None = None

    try:
        for token in lexer:
            argv.append(token)
    except ValueError as e:
        unbalanced = True
        parse_error = str(e)
        findings.append(f"Parse error: {parse_error}")

    features = _detect_features(argv, command) if detect_risky_features else ShellFeatures()
    if unbalanced:
        features["has_unbalanced_quotes"] = True

    if detect_risky_features:
        if features.get("has_pipe"):
            findings.append("Contains pipe operator (|)")
        if features.get("has_redirection"):
            findings.append("Contains redirection operator (< or >)")
        if features.get("has_command_substitution"):
            findings.append("Contains command substitution ($( ) or backticks)")
        if features.get("has_variable_expansion"):
            findings.append("Contains variable expansion ($VAR or ${VAR})")
        if features.get("has_glob_pattern"):
            findings.append("Contains glob pattern characters (* ? [)")
        if features.get("has_control_operator"):
            findings.append("Contains control operator (; & && ||)")

    return ShellSplitResult(
        parse_ok=parse_error is None,
        argv=argv,
        argc=len(argv),
        features=features,
        findings=findings,
    )


def shell_quote_join(
    argv: list[str],
    shell: str = "posix",
) -> ShellQuoteJoinResult:
    """Safely quote a list of argv tokens into a POSIX-like shell string.

    Ensures round-trip safety: shell_split(shell_quote_join(argv)) should
    produce an equivalent argv.

    Args:
        argv: List of argument strings to join.
        shell: Shell dialect (only "posix" is supported).

    Returns:
        ShellQuoteJoinResult with the quoted command string and roundtrip status.

    Raises:
        ValueError: If argv list is too large.
    """
    if len(argv) > MAX_LIST_ITEMS:
        raise ValueError(f"argv count {len(argv)} exceeds maximum {MAX_LIST_ITEMS}")
    findings: list[str] = []

    if shell != "posix":
        return ShellQuoteJoinResult(
            command="",
            roundtrip_ok=False,
            findings=[f"Unsupported shell: {shell!r}. Only 'posix' is supported."],
        )

    parts = [shlex.quote(token) for token in argv]
    command = " ".join(parts)

    # Verify round-trip
    roundtrip_ok = False
    try:
        result = shell_split(command, shell="posix", detect_risky_features=False)
        if result["parse_ok"] and result["argv"] == argv:
            roundtrip_ok = True
        elif result["parse_ok"]:
            findings.append(f"Round-trip mismatch: expected {argv!r}, got {result['argv']!r}")
        else:
            findings.append("Round-trip parse failed")
    except Exception as e:
        findings.append(f"Round-trip verification error: {e}")

    return ShellQuoteJoinResult(
        command=command,
        roundtrip_ok=roundtrip_ok,
        findings=findings,
    )


def argv_compare(
    left_command: str | None = None,
    right_command: str | None = None,
    left_argv: list[str] | None = None,
    right_argv: list[str] | None = None,
    shell: str = "posix",
) -> ArgvCompareResult:
    """Compare two command strings or argv lists by parsed argv rather than raw text.

    Accepts either command strings or pre-parsed argv lists. If both a command
    string and an argv list are provided for the same side, the command string
    takes precedence.

    Args:
        left_command: Left command string to parse and compare.
        right_command: Right command string to parse and compare.
        left_argv: Left pre-parsed argv list.
        right_argv: Right pre-parsed argv list.
        shell: Shell dialect (only "posix" is supported).

    Returns:
        ArgvCompareResult with comparison results.

    Raises:
        ValueError: If command strings exceed MAX_INPUT_LENGTH or argv lists
            exceed MAX_LIST_ITEMS.
    """
    findings: list[str] = []

    # Validate input sizes
    if left_command is not None and len(left_command) > MAX_INPUT_LENGTH:
        raise ValueError(
            f"left_command length {len(left_command)} exceeds maximum {MAX_INPUT_LENGTH}"
        )
    if right_command is not None and len(right_command) > MAX_INPUT_LENGTH:
        raise ValueError(
            f"right_command length {len(right_command)} exceeds maximum {MAX_INPUT_LENGTH}"
        )
    if left_argv is not None and len(left_argv) > MAX_LIST_ITEMS:
        raise ValueError(f"left_argv count {len(left_argv)} exceeds maximum {MAX_LIST_ITEMS}")
    if right_argv is not None and len(right_argv) > MAX_LIST_ITEMS:
        raise ValueError(f"right_argv count {len(right_argv)} exceeds maximum {MAX_LIST_ITEMS}")

    # Resolve left argv
    resolved_left: list[str] | None = left_argv
    if left_command is not None:
        split_left = shell_split(left_command, shell=shell, detect_risky_features=False)
        if not split_left["parse_ok"]:
            return ArgvCompareResult(
                argv_equal=False,
                left_argv=[],
                right_argv=right_argv or [],
                first_difference=0,
                findings=[f"Failed to parse left command: {split_left['findings']}"],
            )
        resolved_left = split_left["argv"]
        if left_argv is not None and split_left["argv"] != left_argv:
            findings.append("Left command parse differs from provided left_argv")

    # Resolve right argv
    resolved_right: list[str] | None = right_argv
    if right_command is not None:
        split_right = shell_split(right_command, shell=shell, detect_risky_features=False)
        if not split_right["parse_ok"]:
            return ArgvCompareResult(
                argv_equal=False,
                left_argv=resolved_left or [],
                right_argv=[],
                first_difference=0,
                findings=[f"Failed to parse right command: {split_right['findings']}"],
            )
        resolved_right = split_right["argv"]
        if right_argv is not None and split_right["argv"] != right_argv:
            findings.append("Right command parse differs from provided right_argv")

    if resolved_left is None:
        resolved_left = []
    if resolved_right is None:
        resolved_right = []

    # Compare
    argv_equal = resolved_left == resolved_right
    first_diff: int | None = None

    if not argv_equal:
        for i in range(min(len(resolved_left), len(resolved_right))):
            if resolved_left[i] != resolved_right[i]:
                first_diff = i
                findings.append(
                    f"First difference at index {i}: {resolved_left[i]!r} != {resolved_right[i]!r}"
                )
                break
        else:
            first_diff = min(len(resolved_left), len(resolved_right))
            if len(resolved_left) > len(resolved_right):
                findings.append(f"Left has {len(resolved_left) - len(resolved_right)} extra tokens")
            else:
                findings.append(
                    f"Right has {len(resolved_right) - len(resolved_left)} extra tokens"
                )

    return ArgvCompareResult(
        argv_equal=argv_equal,
        left_argv=resolved_left,
        right_argv=resolved_right,
        first_difference=first_diff,
        findings=findings,
    )
