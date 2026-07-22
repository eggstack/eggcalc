"""
CLI dispatch for eggcalc.

Handles argument parsing, REPL, text subcommands, help output, and top-level
dispatch.  Separated from the pure normalization pipeline in normalize.py so
that ``import eggcalc`` never loads argparse, exact-tool implementations, or
MCP modules.

Usage:
    python -m eggcalc "five plus two"
    python -m eggcalc --help
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Any, TypedDict

from .evaluator import EvaluationError, evaluate
from .exact import (
    count_chars,
    dotenv_validate,
    inspect_text,
    line_range_extract,
    markdown_structure,
    patch_apply_check,
    regex_test,
    shell_split,
    text_replace_check,
)
from .normalize import NORMALIZE, PATTERNS, error_message, normalize_expression
from .units import UNIT_CATEGORIES

__all__ = [
    "main",
    "print_help",
    "run_cli",
]

_DELIM = "|||"


# ---------------------------------------------------------------------------
# Declarative command registry (C2)
# ---------------------------------------------------------------------------


class CommandSpec(TypedDict, total=False):
    """Immutable metadata for a CLI text command."""

    name: str
    aliases: tuple[str, ...]
    description: str
    usage: str
    min_args: int
    category: str
    json_output: bool
    handler: str


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec(
        name="inspect",
        aliases=(),
        description="Detect hidden characters and confusables in text",
        usage="calc inspect <text>",
        min_args=2,
        category="text",
        json_output=True,
        handler="inspect_text",
    ),
    CommandSpec(
        name="count",
        aliases=(),
        description="Count characters or show frequency table",
        usage="calc count <text> [char]",
        min_args=2,
        category="text",
        json_output=True,
        handler="count_chars",
    ),
    CommandSpec(
        name="regex",
        aliases=(),
        description="Test a regex pattern against text",
        usage="calc regex <pattern> <text>",
        min_args=3,
        category="validation",
        json_output=True,
        handler="regex_test",
    ),
    CommandSpec(
        name="replace-check",
        aliases=(),
        description="Preview text replacement results",
        usage=f"calc replace-check <old> {_DELIM} <new> {_DELIM} <text>",
        min_args=2,
        category="text",
        json_output=True,
        handler="text_replace_check",
    ),
    CommandSpec(
        name="lines",
        aliases=(),
        description="Extract a line range from text",
        usage="calc lines <start[-end]> <text>",
        min_args=3,
        category="text",
        json_output=True,
        handler="line_range_extract",
    ),
    CommandSpec(
        name="patch-check",
        aliases=(),
        description="Preview patch application results",
        usage=f"calc patch-check <original> {_DELIM} <patch>",
        min_args=2,
        category="patch",
        json_output=True,
        handler="patch_apply_check",
    ),
    CommandSpec(
        name="shell-split",
        aliases=(),
        description="Split a shell command into argv tokens",
        usage="calc shell-split <command>",
        min_args=2,
        category="shell",
        json_output=True,
        handler="shell_split",
    ),
    CommandSpec(
        name="md-structure",
        aliases=(),
        description="Analyze markdown structure (headings, fences, links)",
        usage="calc md-structure <text>",
        min_args=2,
        category="markdown",
        json_output=True,
        handler="markdown_structure",
    ),
    CommandSpec(
        name="dotenv-check",
        aliases=(),
        description="Validate .env file format",
        usage="calc dotenv-check <text>",
        min_args=2,
        category="validation",
        json_output=True,
        handler="dotenv_validate",
    ),
)

_COMMAND_NAME_TO_SPEC: dict[str, CommandSpec] = {}
for _spec in COMMANDS:
    _COMMAND_NAME_TO_SPEC[_spec["name"]] = _spec
    for _alias in _spec.get("aliases", ()):
        _COMMAND_NAME_TO_SPEC[_alias] = _spec


def _get_handler(name: str) -> Any:
    """Look up a handler function by name, supporting both package and single-file modes."""
    _HANDLER_MAP: dict[str, Any] = {
        "inspect_text": inspect_text,
        "count_chars": count_chars,
        "regex_test": regex_test,
        "text_replace_check": text_replace_check,
        "line_range_extract": line_range_extract,
        "patch_apply_check": patch_apply_check,
        "shell_split": shell_split,
        "markdown_structure": markdown_structure,
        "dotenv_validate": dotenv_validate,
    }
    return _HANDLER_MAP[name]


def run_cli(
    expression: str,
    output_format: str = "plain",
    show_expression: bool = True,
) -> tuple[Any, int]:
    """Process a single expression: normalize, evaluate, and print result.

    Returns:
        tuple: (result, exit_code)
    """
    original = expression
    try:
        joined, exit_code = normalize_expression(expression, NORMALIZE, PATTERNS)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return None, 1
    except Exception as e:
        error_message(original, e)
        return None, 1

    if exit_code != 0:
        if exit_code == 2:
            print(joined, file=sys.stderr)
        return None, exit_code

    try:
        result = evaluate(joined)
        display = str(result)
        if output_format == "json":
            import json

            print(json.dumps({"expression": joined, "result": display}))
        else:
            print(display)
        return result, 0
    except ZeroDivisionError as e:
        error_message(original, e)
        return None, 1
    except EvaluationError as e:
        error_message(original, e)
        return None, 1
    except Exception as e:
        error_message(original, e)
        return None, 1


def _run_repl(show_expression: bool = True) -> int:
    """Run interactive REPL mode."""

    import atexit
    import os

    try:
        import readline
    except ImportError:
        readline = None  # type: ignore[assignment]

    print("eggcalc interactive mode. Type 'help' for available commands, 'quit' or 'exit' to exit.")
    print()

    history: list[tuple[str, Any]] = []

    history_path = os.path.expanduser("~/.eggcalc_history")
    if readline is not None:
        try:
            readline.read_history_file(history_path)
        except OSError:
            pass

        def _save_history() -> None:
            try:
                readline.write_history_file(history_path)
                os.chmod(history_path, 0o600)
            except OSError:
                pass

        atexit.register(_save_history)

    MAX_REPL_LINE_LENGTH = 100_000
    while True:
        try:
            line = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if len(line) > MAX_REPL_LINE_LENGTH:
            print(f"Input too long ({len(line)} chars, max {MAX_REPL_LINE_LENGTH})")
            continue

        if not line:
            continue

        if line.lower() in ("quit", "quit()", "exit", "exit()"):
            break

        if line.lower() == "help":
            print_help()
            continue

        if line.lower() == "history":
            for expr, result in history:
                print(f"{expr} = {result}")
            continue

        if line.lower() == "clear":
            history.clear()
            continue

        try:
            result, exit_code = run_cli(line, "plain", show_expression)
        except KeyboardInterrupt:
            print()
            continue

        if exit_code == 0 and result is not None:
            history.append((line, result))

    return 0


def _get_units_by_category() -> dict[str, list[str]]:
    """Get units organized by category from UNIT_CATEGORIES."""
    categories: dict[str, set[str]] = {}
    for unit, category in UNIT_CATEGORIES.items():
        if category not in categories:
            categories[category] = set()
        categories[category].add(unit)
    # Sort units within each category
    result = {}
    for cat in sorted(categories.keys()):
        result[cat] = sorted(categories[cat])
    return result


def print_help() -> None:
    """Print available operators, functions, and units."""
    # Get units by category programmatically
    units_by_cat = _get_units_by_category()

    lines = [
        "Usage:",
        "  calc <expression>          Evaluate math expression",
        "  calc inspect <text>       Check for hidden characters/confusables",
        "  calc count <text>         Count characters (or count <text> <char>)",
        "  calc regex <pat> <text>  Test regex pattern against text",
        "",
        "Text tools:",
        "  calc replace-check <old> ||| <new> ||| <text>",
        "  calc lines <start[-end]> <text>",
        "  calc patch-check <original> ||| <patch>",
        "  calc shell-split <command>",
        "  calc md-structure <text>",
        "  calc dotenv-check <text>",
        "",
        "Flags:",
        "  --json                    Output result as JSON",
        "",
        "Operators:",
        "  Arithmetic: +  -  *  /  **",
        "  Words: plus, minus, times, divided by, over, raised to",
        "",
        "Functions:",
        "  Trigonometry: sin, cos, tan, asin, acos, atan, atan2",
        "  Hyperbolic: sinh, cosh, tanh, asinh, acosh, atanh",
        "  Logarithmic: log, log10, log2, log1p, exp, expm1",
        "  Rounding: abs, floor, ceil, trunc, round, sign",
        "  Other: sqrt, pow, factorial, gcd, lcm, mean, median",
        "",
        "Constants:",
        "  pi, e, tau",
        "  avogadro, gasconstant, planck, boltzmann",
        "  c (speed of light), elementarycharge, faraday, amu",
        "",
        "Units:",
    ]

    unit_lines = []
    for category, units in units_by_cat.items():
        if len(units) > 15:
            display_units = units[:12] + ["..."]
        else:
            display_units = units
        unit_lines.append(f"  {category.capitalize()}: {', '.join(display_units)}")

    lines += unit_lines + [
        "",
        "Unit conversion examples:",
        "  calc 30m + 100ft",
        "  calc 1km in miles",
        "  calc 100F to C",
        "  calc 1kg in lb",
        "",
        "Text tools examples:",
        '  calc inspect "hello"',
        "  calc inspect \"p\u0430ypal\"  ( Cyrillic 'a' instead of Latin)",
        '  calc count "hello world"',
        '  calc count "hello" l',
        '  calc regex "^\\d+$" "12345"',
        '  calc replace-check "foo" ||| "bar" ||| "foo baz foo"',
        '  calc lines 2-4 "line1\\nline2\\nline3\\nline4\\nline5"',
        '  calc shell-split "git commit -m \\"fix\\""',
        '  calc md-structure "# Hello\\n\\nA [link](http://x.com)"',
        '  calc dotenv-check "DB_HOST=localhost\\nDB_PORT=5432"',
        "",
        "All text commands support --json for machine-readable output.",
    ]

    for line in lines:
        print(line)


def _cli_text_command(
    expression: str, json_output: bool = False, argv: list[str] | None = None
) -> int:
    """Handle text commands before math evaluation.

    Dispatches through the declarative :data:`COMMANDS` registry.  If ``argv``
    is provided it is used directly (preserving quoted shell arguments);
    otherwise ``expression`` is whitespace-split.

    Returns:
        0 if command was handled, 1 if expression should continue to math eval
    """
    if argv is not None:
        parts = argv
    else:
        parts = expression.split()

    if not parts:
        return 1

    cmd = parts[0].lower()
    spec = _COMMAND_NAME_TO_SPEC.get(cmd)
    if spec is None:
        return 1

    if len(parts) < spec.get("min_args", 2):
        print(f"Usage: {spec['usage']}", file=sys.stderr)
        return 1

    handler_name = spec["handler"]
    handler = _get_handler(handler_name)

    if cmd == "inspect":
        text = " ".join(parts[1:])
        try:
            result: Any = handler(text, include_codepoints=False, include_confusables=True)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        if json_output:
            import json

            print(json.dumps(result))
            return 0
        if result["warnings"]:
            for w in result["warnings"]:
                kind = w["kind"].upper()
                print(f"\u2717 {kind}: {w['message']}")
        else:
            print("\u2713 No hidden characters")
        if result["confusables"]:
            print(f"\nConfusables found: {len(result['confusables'])}")
            for c in result["confusables"][:5]:
                print(f"  '{c['char']}' (looks like '{c['confusable_with']}') at {c['index']}")
        return 0

    if cmd == "count":
        text = " ".join(parts[1:])
        if len(parts) >= 3 and len(parts[-1]) == 1:
            char = parts[-1]
            text = " ".join(parts[1:-1])
            try:
                result = handler(text, target=char)
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
            if json_output:
                import json

                print(json.dumps(result))
                return 0
            print(f"'{char}' appears {result['count']} time(s) in \"{text}\"")
            return 0
        try:
            if " " in text:
                result = handler(text)
                if json_output:
                    import json

                    print(json.dumps(result))
                    return 0
                if isinstance(result, dict):
                    print(f"\"{text}\":")
                    print(f"  {len(text)} characters")
                    sorted_chars = sorted(result.items(), key=lambda x: (-x[1], x[0]))
                    for char, count in sorted_chars[:10]:
                        display = repr(char) if char != " " else "(space)"
                        print(f"  {display}: {count}")
                    if len(result) > 10:
                        print(f"  ... and {len(result) - 10} more unique chars")
                return 0
            else:
                result = handler(text)
                if json_output:
                    import json

                    print(json.dumps(result))
                    return 0
                print(f"\"{text}\": {len(text)} character(s)")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    if cmd == "regex":
        pattern = parts[1]
        text = " ".join(parts[2:])
        try:
            result = handler(pattern, [text])
        except re.error as e:
            print(f"Error: Invalid regex pattern: {e}", file=sys.stderr)
            return 1
        if not result["valid_pattern"]:
            print(f"\u2717 Invalid regex pattern: {pattern}", file=sys.stderr)
            return 1
        if json_output:
            import json

            print(json.dumps(result))
            return 0
        if result["results"]:
            r = result["results"][0]
            if r["matches"]:
                print(f"\u2713 Match: '{r['sample']}'")
                if r["groups"]:
                    print(f"  Groups: {r['groups']}")
                if r["groupdict"]:
                    print(f"  Named groups: {r['groupdict']}")
            else:
                print("\u2717 No match")
        else:
            print("\u2717 No match")
        return 0

    if cmd == "replace-check":
        raw = " ".join(parts[1:]).strip()
        if _DELIM not in raw:
            print(f"Usage: {spec['usage']}", file=sys.stderr)
            return 1
        segments = raw.split(_DELIM, 2)
        if len(segments) < 3:
            print(f"Usage: {spec['usage']}", file=sys.stderr)
            return 1
        old = segments[0].strip()
        new = segments[1].strip()
        text = segments[2].strip()
        try:
            result = handler(text, old, new, return_preview=True)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        if json_output:
            import json

            print(json.dumps(result))
            return 0
        count = result["match_count"]
        if count == 0:
            print("\u2717 No match for replacement.")
        elif count == 1:
            print("\u2713 Replacement would apply cleanly to 1 match.")
        else:
            print(f"\u221d Replacement is ambiguous: {count} matches found.")
        for f in result["findings"]:
            print(f"  {f['kind']}: {f['message']}")
        return 0

    if cmd == "lines":
        split_parts = expression.strip().split(None, 2)
        if len(split_parts) < 3:
            print(f"Usage: {spec['usage']}", file=sys.stderr)
            return 1
        range_str = split_parts[1]
        text = split_parts[2]
        if "-" in range_str:
            try:
                start_str, end_str = range_str.split("-", 1)
                start_line = int(start_str)
                end_line = int(end_str)
            except ValueError:
                print(f"Error: Invalid line range '{range_str}'", file=sys.stderr)
                return 1
        else:
            try:
                start_line = int(range_str)
                end_line = start_line
            except ValueError:
                print(f"Error: Invalid line number '{range_str}'", file=sys.stderr)
                return 1
        try:
            result = handler(text, start_line, end_line, include_line_numbers=True)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        if json_output:
            import json

            print(json.dumps(result))
            return 0
        if not result["valid_range"]:
            for f in result["findings"]:
                print(f"  {f['kind']}: {f['message']}")
            return 1
        for line_info in result["lines"]:
            num = line_info.get("line", "")
            content = line_info.get("text", "")
            print(f"{num}: {content}")
        return 0

    if cmd == "patch-check":
        raw = " ".join(parts[1:]).strip()
        if _DELIM not in raw:
            print(f"Usage: {spec['usage']}", file=sys.stderr)
            return 1
        segments = raw.split(_DELIM, 1)
        if len(segments) < 2:
            print(f"Usage: {spec['usage']}", file=sys.stderr)
            return 1
        original = segments[0].strip()
        patch_text = segments[1].strip()
        try:
            result = handler(original, patch_text)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        if json_output:
            import json

            print(json.dumps(result))
            return 0
        if not result["patch_parse_ok"]:
            print("\u2717 Failed to parse patch.")
            for f in result["findings"]:
                print(f"  {f}")
            return 1
        total = result["hunks_total"]
        applied = result["hunks_applied"]
        failed = result["hunks_failed"]
        if result["applies"]:
            print(f"\u2713 Patch applies cleanly. {applied}/{total} hunks applied.")
        else:
            print(f"\u2717 Patch fails: {failed}/{total} hunks failed.")
        for f in result["findings"]:
            print(f"  {f}")
        return 0

    if cmd == "shell-split":
        command = " ".join(parts[1:])
        try:
            result = handler(command)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        if json_output:
            import json

            print(json.dumps(result))
            return 0
        if not result["parse_ok"]:
            print("\u2717 Parse failed.")
            for f in result["findings"]:
                print(f"  {f}")
            return 1
        argv_out = result["argv"]
        print(f"Parsed {result['argc']} token(s): {argv_out}")
        features = result["features"]
        active = [k.replace("has_", "") for k, v in features.items() if v]
        if active:
            print(f"Contains: {', '.join(active)}")
        for f in result["findings"]:
            print(f"  {f}")
        return 0

    if cmd == "md-structure":
        split_parts = expression.strip().split(None, 1)
        if len(split_parts) < 2:
            print(f"Usage: {spec['usage']}", file=sys.stderr)
            return 1
        text = split_parts[1]
        try:
            result = handler(text)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        if json_output:
            import json

            print(json.dumps(result))
            return 0
        headings = result["headings"]
        fences = result["code_fences"]
        links = result["links"]
        unclosed = [f for f in fences if not f["closed"]]
        parts_out = []
        if headings:
            parts_out.append(f"{len(headings)} heading(s)")
        if fences:
            label = "code fence(s)" if len(fences) != 1 else "code fence"
            if unclosed:
                parts_out.append(f"{len(fences)} {label} ({len(unclosed)} unclosed)")
            else:
                parts_out.append(f"{len(fences)} {label}")
        if links:
            parts_out.append(f"{len(links)} link(s)")
        if result["frontmatter"]["present"]:
            parts_out.append(f"frontmatter ({result['frontmatter']['format']})")
        if result["tables_detected"]:
            parts_out.append("table(s)")
        if parts_out:
            print(f"Markdown contains: {', '.join(parts_out)}.")
        else:
            print("Markdown is empty or has no structural elements.")
        for f in result["findings"]:
            print(f"  {f}")
        return 0

    if cmd == "dotenv-check":
        text = " ".join(parts[1:])
        try:
            result = handler(text)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        if json_output:
            import json

            print(json.dumps(result))
            return 0
        entries = result["entries"]
        if result["parse_ok"] and not result["invalid_lines"]:
            print(f"\u2713 Valid .env: {len(entries)} entry/entries.")
        else:
            print(f"\u2717 Invalid .env: {len(result['invalid_lines'])} invalid line(s).")
        for f in result["findings"]:
            print(f"  {f}")
        return 0

    return 1


def maybe_load_cli_config() -> None:
    """Load user config for CLI usage if not disabled.

    This is the CLI-owned config loading entry point. It is called once
    during CLI startup (single-expression, -e, interactive modes). It is
    intentionally NOT called from library API functions like evaluate_raw()
    so that ``import eggcalc`` never executes cwd-local Python.

    Config loading can be disabled by setting EGGCALC_NO_CONFIG=1.
    """
    import os

    if os.environ.get("EGGCALC_NO_CONFIG", ""):
        return
    try:
        from eggcalc.evaluator import load_user_config
    except (ImportError, ModuleNotFoundError):
        pass  # single-file mode: load_user_config is a module-level global
    load_user_config()


def main() -> int:
    """Main entry point for CLI."""
    import os
    import signal

    import eggcalc

    maybe_load_cli_config()

    try:
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    except (AttributeError, OSError):
        pass

    def _sigterm_handler(signum: int, frame: object) -> None:
        raise SystemExit(0)

    try:
        signal.signal(signal.SIGTERM, _sigterm_handler)
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(
        description="Natural language math expression calculator",
        add_help=False,
    )
    parser.add_argument(
        "expression", nargs="*", help="Expression to evaluate (e.g., 'five plus two')"
    )
    parser.add_argument(
        "-h", "--help", action="store_true", help="Show help and available operators"
    )
    parser.add_argument(
        "--usage", action="store_true", help="Show full usage information and examples"
    )
    parser.add_argument("-v", "--version", action="store_true", help="Show version information")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress expression in output")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Accepted for compatibility; plain output remains result-only",
    )
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    parser.add_argument(
        "-e",
        "--expression",
        dest="single_expr",
        metavar="<expr>",
        help="Evaluate a single expression (useful for piping)",
    )
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Start interactive REPL mode"
    )
    parser.add_argument(
        "-s",
        "--show",
        action="store_true",
        help="Accepted for compatibility; plain output remains result-only",
    )
    parser.add_argument("--mcp", action="store_true", help="Run as MCP server for exact text tools")
    parser.add_argument(
        "--mcp-profile",
        default=None,
        help="MCP profile to use (default: full, or EGGCALC_MCP_PROFILE env var)",
    )
    parser.add_argument(
        "--mcp-schema-detail",
        default=None,
        choices=["compact", "normal", "full"],
        help="MCP schema detail level (default: full, or EGGCALC_MCP_SCHEMA_DETAIL env var)",
    )
    parser.add_argument(
        "--capabilities",
        action="store_true",
        help="Show runtime capabilities (Python, platform, features) as JSON and exit",
    )

    args = parser.parse_args()

    if args.capabilities:
        from .capabilities import detect_capabilities

        caps = detect_capabilities()
        print(caps.to_json(indent=2))
        return 0

    if args.mcp:
        if args.mcp_profile:
            from eggcalc.mcp.server import set_active_profile

            set_active_profile(args.mcp_profile)
        if args.mcp_schema_detail:
            from eggcalc.mcp.server import set_schema_detail

            set_schema_detail(args.mcp_schema_detail)
        from eggcalc.mcp.server import mcp_main

        return mcp_main()

    if args.version:
        print(f"eggcalc {eggcalc.__version__}")
        return 0

    if args.usage:
        print_help()
        return 0

    if args.help or (not args.expression and not args.single_expr and not args.interactive):
        parser.print_help()
        return 0

    if args.interactive:
        return _run_repl(show_expression=True)

    if args.single_expr:
        expression = args.single_expr
        quiet_by_default = True
    else:
        expression = " ".join(args.expression)
        quiet_by_default = False

    # Detect shell glob expansion (e.g., "python eggcalc.py 30 * 3" expands "*" to files)
    if args.expression and len(args.expression) > 1:
        # Check if any argument is a file or directory that exists (likely from glob expansion)
        cwd = os.getcwd()
        glob_indicators = []
        for arg in args.expression:
            path = os.path.join(cwd, arg)
            if (
                os.path.exists(path)
                and arg not in (".", "..")
                and not arg.startswith("./")
                and not arg.startswith("../")
            ):
                glob_indicators.append(arg)

        if glob_indicators:
            error_lines = [
                "Error: Possible shell glob expansion detected.",
                f"The '*' character was expanded to file(s): {glob_indicators[:5]}{'...' if len(glob_indicators) > 5 else ''}",
                "Please quote your expression:",
                f'  calc "{" ".join(args.expression)}"',
                "Or use -e flag:",
                f'  calc -e "{" ".join(args.expression)}"',
            ]
            for line in error_lines:
                print(line, file=sys.stderr)
            return 1

    # Try text commands first (inspect, count, regex, etc.)
    # When invoked with positional args, pass the argv list directly so quoted
    # arguments (e.g. text containing spaces) are preserved verbatim.
    text_argv = args.expression if args.expression else None
    cmd_result = _cli_text_command(expression, json_output=args.json, argv=text_argv)
    if cmd_result == 0:
        return 0  # Command was handled

    output_format = "json" if args.json else "plain"
    show_expression = not args.quiet and ((args.verbose or args.show) or not quiet_by_default)

    _, exit_code = run_cli(expression, output_format, show_expression)
    return exit_code
