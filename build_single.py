#!/usr/bin/env python3
"""
Build script to combine eggcalc modules into a single self-contained executable.

Supports both CLI mode (calculator) and MCP server mode (--mcp flag).

Usage:
    python3 build_single.py          # Build eggcalc.py in current directory
    python3 build_single.py -o /path/to/output  # Custom output path
"""

from __future__ import annotations

import argparse
import os
import re

EGGCALC_DIR = os.path.join(os.path.dirname(__file__), "eggcalc")

MODULES_CALC = [
    "units",
    "evaluator",
    "_protocol",
    "normalize",
    "cli",
    "capabilities",
]

MODULES_EXACT = [
    "exact/primitives",
    "exact/diff",
    "exact/diff_analysis",
    "exact/validate",
    "exact/measure",
    "exact/unicode_tools",
    "exact/synthesis",
    "exact/confusables",
    "exact/config",
    "exact/shell",
    "exact/path_tools",
    "exact/markdown",
    "exact/patch",
    "exact/transform",
    "exact/position",
    "exact/identifier",
    "exact/identifier_inspect",
    "exact/glob",
    "exact/unicode_policy",
    "exact/inspect_prompt",
    "exact/cargo",
    "exact/version",
    "exact/manifests",
    "exact/llm_hygiene",
    "exact/repo_audit",
]

MODULES_MCP = [
    "mcp/schemas",
    "mcp/tools",
    "mcp/server",
]

ALL_MODULES = MODULES_CALC + MODULES_EXACT + MODULES_MCP

HEADER = '''#!/usr/bin/env python3
from __future__ import annotations

"""
eggcalc - Natural language math expression calculator + MCP exact tools

Single-file version.

CLI mode:     python3 eggcalc.py "five plus two"
MCP mode:     python3 eggcalc.py --mcp

Or make executable: chmod +x eggcalc.py && ./eggcalc.py "five plus two"
"""

import sys
import os

'''


def get_version() -> str:
    """Get version from __init__.py"""
    init_path = os.path.join(EGGCALC_DIR, "__init__.py")
    with open(init_path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                import re as _re

                m = _re.match(r'__version__\s*=\s*["\']([^"\']+)["\']', line)
                if m:
                    return m.group(1)
                raise SystemExit(
                    f"ERROR: Malformed __version__ line in {init_path}: {line.strip()!r}"
                )
    raise SystemExit(f"ERROR: __version__ not found in {init_path}")


def get_module_code(module_name: str) -> tuple[str, list[str], list[str]]:
    """Extract code from a module, removing docstring and imports that will be inlined.

    Handles nested paths like 'exact/primitives' or 'mcp/tools'.

    Returns:
        Tuple of (cleaned_code, list_of_import_statements)
    """
    module_path = os.path.join(EGGCALC_DIR, f"{module_name}.py")

    with open(module_path, encoding="utf-8") as f:
        lines = f.readlines()

    # Find where code starts (after docstring)
    in_docstring = False
    start_idx = 0
    for i, line in enumerate(lines):
        if i == 0 and '"""' in line:
            in_docstring = True
        if in_docstring:
            if '"""' in line and i > 0:
                in_docstring = False
                start_idx = i + 1
                break
        elif line.startswith('"""'):
            in_docstring = True

    # Get the code
    code_lines = lines[start_idx:]

    # Modules being inlined (for import cleaning)
    inlined_modules = set()
    for mod in ALL_MODULES:
        if "/" in mod:
            pkg, name = mod.split("/")
            inlined_modules.add(f"{pkg}.{name}")
        else:
            inlined_modules.add(mod)

    # Collect imports separately
    imports: list[str] = []
    cleaned: list[str] = []
    in_main_block = False
    in_multiline_import = False
    exact_import_globals: list[str] = []
    _skip_exact_names: set[str] = set()

    def is_relative_import_stripped(stripped: str) -> bool:
        """Check if a relative import should be skipped because module is inlined."""
        for mod in ALL_MODULES:
            if "/" in mod:
                pkg, name = mod.split("/")
                # Match "from .<pkg>.<name> import" or "from ..exact.<name> import"
                if (
                    f"from .{pkg}.{name} import" in stripped
                    or f"from .{name} import" in stripped
                    or f"from ..exact.{name} import" in stripped
                ):
                    return True
            else:
                if f"from .{mod} import" in stripped:
                    return True
        return False

    def should_replace_import(stripped: str) -> bool:
        """Check if this import should be replaced rather than skipped."""
        if "import _default_evaluator" in stripped:
            return True
        if "from .units import" in stripped:
            return True
        if "from .evaluator import" in stripped:
            return True
        if "from .normalize import" in stripped:
            return True
        return False

    def is_valid_single_line_import(stripped: str, line: str) -> bool:
        """Check if this is a valid single-line import to collect.

        Must be a top-level import (not indented inside a function/class).
        """
        # Must start with "import " or "from "
        if not (stripped.startswith("import ") or stripped.startswith("from ")):
            return False
        # Must be at top level - no leading whitespace (indented lines are local imports)
        if line and line[0] in " \t":
            return False
        # Skip __future__ imports
        if "__future__" in stripped:
            return False
        # Skip relative imports (they reference inlined modules)
        if stripped.startswith("from ."):
            return False
        # Skip eggcalc imports (package reference)
        if "eggcalc" in stripped:
            return False
        # Must be a complete single-line import (ends without_open paren, no backslash)
        if "(" in stripped or ")" in stripped:
            return False
        if "\\" in stripped:
            return False
        return True

    for i, line in enumerate(code_lines):
        stripped = line.strip()

        # Check if we're entering a multi-line import (skip until closed)
        # Need to check for "import (" without ")" on same line = multi-line import start
        # Strip all top-level multi-line imports; also strip local multi-line imports
        # except those from inlined exact modules (primitives, synthesis, etc.)
        if (
            (stripped.startswith("import ") or stripped.startswith("from "))
            and "(" in stripped
            and ")" not in stripped
        ):
            # Check if this is a local import from an inlined exact module
            # Patterns: "from .<module> import" or "from ..exact.<module> import"
            is_inlined_module = False
            for m in MODULES_EXACT:
                mod_name = m.split('/')[-1]
                if stripped.startswith(f"from .{mod_name} import") or stripped.startswith(
                    f"from ..exact.{mod_name} import"
                ):
                    is_inlined_module = True
                    break
            if not (line and line[0] in " \t"):
                # Top-level multi-line import
                # Check if it's from ..exact (with or without submodule) —
                # if so, extract aliases as globals
                if (
                    stripped.startswith("from ..exact ")
                    or stripped.startswith("from .exact ")
                    or stripped.startswith("from ..exact.")
                ):
                    # Collect all names from this multi-line import block
                    _exact_names = []
                    _first_line = stripped.split("import ", 1)[1] if "import " in stripped else ""
                    if "(" in _first_line:
                        _first_part = _first_line.split("(", 1)[1].strip()
                        if _first_part:
                            _exact_names.append(_first_part)
                    i += 1
                    while i < len(code_lines):
                        _l = code_lines[i].strip()
                        if _l.startswith(")"):
                            i += 1
                            break
                        _l = _l.rstrip(",").rstrip(")")
                        if _l:
                            _exact_names.append(_l)
                        i += 1
                    # Generate global assignments for each alias
                    for _name in _exact_names:
                        _name = _name.strip()
                        if " as " in _name:
                            _orig, _alias = _name.split(" as ", 1)
                            exact_import_globals.append(f"{_alias.strip()} = {_orig.strip()}")
                        elif _name:
                            exact_import_globals.append(f"{_name} = {_name}")
                    # Track which lines to skip (the for loop can't be controlled)
                    _skip_exact_names = set(_exact_names)
                    _skip_exact_names.add(")")  # Also skip the closing paren
                    continue
                in_multiline_import = True
                continue
            elif is_inlined_module:
                # Local import from inlined exact module - keep it
                pass
            else:
                in_multiline_import = True
                continue

        # Handle multi-line imports - skip until closed
        if in_multiline_import:
            if ")" in stripped:
                in_multiline_import = False
            continue

        # Handle relative imports (only top-level; local imports inside functions are kept)
        if stripped.startswith("from .") and not (line and line[0] in " \t"):
            if is_relative_import_stripped(stripped):
                continue
            if should_replace_import(stripped):
                continue
            # Skip other relative imports
            continue

        # Remove __future__ imports (will be inlined once)
        if "from __future__" in line:
            continue

        # Handle simple "import X" statements - collect them if top-level
        if stripped.startswith("import ") and not stripped.startswith("import eggcalc"):
            if is_valid_single_line_import(stripped, line):
                imports.append(line)
                continue  # Skip - imported at top level
            # Not a top-level import, fall through to include in code

        # Handle simple "from X import" statements that are NOT relative or inlined
        if stripped.startswith("from ") and " import " in stripped:
            if is_valid_single_line_import(stripped, line):
                imports.append(line)
                continue  # Skip - imported at top level
            # Not a top-level import, fall through to include in code

        # Skip if __name__ == "__main__" blocks
        if line.startswith("if __name__") and "__main__" in line:
            in_main_block = True
            continue
        if in_main_block:
            if line.strip() and not line[0].isspace():
                in_main_block = False
            else:
                continue

        # Skip empty lines at start
        if not cleaned and line.strip() == "":
            continue

        # Skip bare import names and closing paren from ..exact imports
        _check_name = stripped.rstrip(",").rstrip(")").strip()
        if _skip_exact_names and (
            _check_name in _skip_exact_names or stripped.strip() in _skip_exact_names
        ):
            _skip_exact_names.discard(_check_name)
            _skip_exact_names.discard(stripped.strip())
            continue

        cleaned.append(line)

    code = "".join(cleaned)

    # Handle cross-module references within packages being inlined

    # Units module references
    code = code.replace("units.UNIT_BASE", "UNIT_BASE")
    code = code.replace("units.UNIT_ALIASES", "UNIT_ALIASES")
    code = code.replace("units.UNIT_CATEGORIES", "UNIT_CATEGORIES")
    code = code.replace("units.TEMPERATURE_CONVERSIONS", "TEMPERATURE_CONVERSIONS")
    code = code.replace("units._UNITS_LOCK", "_UNITS_LOCK")
    code = code.replace("units._rebuild_conversions()", "_rebuild_conversions()")
    code = code.replace("units._simplify_unit_string", "_simplify_unit_string")
    code = code.replace("units._expand_short_compound", "_expand_short_compound")

    # Normalize references to modules now inlined
    code = code.replace(
        "from eggcalc import __version__", "# __version__ is defined at module level"
    )

    # Rename normalize.main() to normalize_main() to avoid conflict with MCP main()
    if '"""Main entry point for CLI."""' in code:
        code = code.replace("def main() -> int:", "def normalize_main() -> int:")

    # Fix eggcalc import inside normalize.main() - in single file, __version__ is at module level
    # Also fix the MCP import which is a global in single file
    if '"""Main entry point for CLI."""' in code:
        code = code.replace("    import eggcalc\n", "")
        code = code.replace("eggcalc.__version__", "__version__")
        code = code.replace("        from eggcalc.mcp.server import mcp_main\n", "")
        code = code.replace("            from eggcalc.mcp.server import set_active_profile\n", "")
        code = code.replace("            from eggcalc.mcp.server import set_schema_detail\n", "")

    # Exact module internal references (within exact package)
    # These are relative imports that now become direct
    code = code.replace("from .primitives import", "from primitives import")
    code = code.replace("from .diff import", "from diff import")
    code = code.replace("from .validate import", "from validate import")
    code = code.replace("from .measure import", "from measure import")
    code = code.replace("from .unicode_tools import", "from unicode_tools import")
    code = code.replace("from .synthesis import", "from synthesis import")
    code = code.replace("from .confusables import", "from confusables import")
    code = code.replace("from .config import", "from config import")
    code = code.replace("from .shell import", "from shell import")
    code = code.replace("from .path_tools import", "from path_tools import")
    code = code.replace("from .markdown import", "from markdown import")
    code = code.replace("from .patch import", "from patch import")
    code = code.replace("from .transform import", "from transform import")
    code = code.replace("from .position import", "from position import")
    code = code.replace("from .identifier import", "from identifier import")
    code = code.replace("from .identifier_inspect import", "from identifier_inspect import")
    code = code.replace("from .glob import", "from glob import")
    code = code.replace("from .unicode_policy import", "from unicode_policy import")
    code = code.replace("from .inspect_prompt import", "from inspect_prompt import")
    code = code.replace("from .cargo import", "from cargo import")
    code = code.replace("from .version import", "from version import")

    # MCP module internal references
    code = code.replace("from .schemas import", "from schemas import")
    code = code.replace("from .tools import", "from tools import")
    code = code.replace("from .server import", "from server import")

    # Rename MCP server main to mcp_main to avoid conflict with normalize.main()
    # Only replace when it's specifically the MCP server main (has MCP docstring)
    if '"""Main entry point for MCP server.' in code:
        code = code.replace("def main() -> int:", "def mcp_main() -> int:")
        code = code.replace("mcp_main = main", "# MCP main already renamed to mcp_main")

    # Exact imports into synthesis
    code = code.replace("from ..exact import", "from exact import")

    # MCP imports from eggcalc
    code = code.replace(
        "from .. import EvaluationError, evaluate_raw",
        "from evaluator import EvaluationError, evaluate_raw",
    )
    code = code.replace("from ..exact import", "from exact import")

    # MCP server: evaluator module reference
    # In single file, _mcp_mode is a module-level variable (no _evaluator module object)
    code = code.replace(
        "from .. import evaluator as _evaluator",
        "# _evaluator is inlined; _mcp_mode is a module-level variable",
    )
    code = code.replace(
        "_evaluator._mcp_mode = True",
        "_mcp_mode = True",
    )
    # In single file, configure_default_evaluator is a module-level function
    code = code.replace(
        "_evaluator.configure_default_evaluator(",
        "configure_default_evaluator(",
    )
    # In single file, Evaluator class and get_config_generation are module-level
    code = code.replace(
        "_evaluator.Evaluator(",
        "Evaluator(",
    )
    code = code.replace(
        "_evaluator.get_config_generation()",
        "get_config_generation()",
    )
    # Type annotations referencing _evaluator.Evaluator
    code = code.replace(
        "_evaluator.Evaluator:",
        "Evaluator:",
    )
    # In single file, _server_evaluator is a module-level ContextVar
    code = code.replace(
        "_evaluator._server_evaluator",
        "_server_evaluator",
    )
    # MCP server: capabilities module reference
    code = code.replace(
        "from ..capabilities import detect_capabilities",
        "# detect_capabilities is inlined",
    )

    # Synthesis imports from exact submodules
    code = code.replace("from .primitives import (", "# primitives imports handled inline")
    code = code.replace("from .unicode_tools import (", "# unicode_tools imports handled inline")
    code = code.replace("from .diff import (", "# diff imports handled inline")
    code = code.replace("from .validate import (", "# validate imports handled inline")
    code = code.replace("from .measure import (", "# measure imports handled inline")
    code = code.replace("from .synthesis import (", "# synthesis imports handled inline")
    code = code.replace("from .config import (", "# config imports handled inline")
    code = code.replace("from .shell import (", "# shell imports handled inline")
    code = code.replace("from .path_tools import (", "# path_tools imports handled inline")
    code = code.replace("from .markdown import (", "# markdown imports handled inline")
    code = code.replace("from .patch import (", "# patch imports handled inline")
    code = code.replace("from .transform import (", "# transform imports handled inline")
    code = code.replace("from .position import (", "# position imports handled inline")
    code = code.replace("from .identifier import (", "# identifier imports handled inline")
    code = code.replace(
        "from .identifier_inspect import (", "# identifier_inspect imports handled inline"
    )
    code = code.replace("from .glob import (", "# glob imports handled inline")
    code = code.replace("from .unicode_policy import (", "# unicode_policy imports handled inline")

    # MCP imports from ..exact.<module> (indented inside functions)
    code = code.replace("from ..exact.config import (", "# config imports handled inline")
    code = code.replace("from ..exact.identifier import (", "# identifier imports handled inline")
    code = code.replace("from ..exact.markdown import (", "# markdown imports handled inline")
    code = code.replace("from ..exact.path_tools import (", "# path_tools imports handled inline")
    code = code.replace("from ..exact.primitives import (", "# primitives imports handled inline")
    code = code.replace("from ..exact.shell import (", "# shell imports handled inline")
    code = code.replace("from ..exact.synthesis import (", "# synthesis imports handled inline")
    code = code.replace("from ..exact.transform import (", "# transform imports handled inline")
    code = code.replace(
        "from ..exact.unicode_policy import (", "# unicode_policy imports handled inline"
    )
    code = code.replace("from ..exact.cargo import (", "# cargo imports handled inline")
    code = code.replace("from ..exact.version import (", "# version imports handled inline")
    code = code.replace("from ..exact.validate import (", "# validate imports handled inline")
    # Use regex to replace entire multi-line import blocks for patch module
    # (simple str.replace only replaces the header, leaving orphaned continuation lines)
    code = re.sub(
        r"from \.\.exact\.patch import \(\n(?:\s+[^)\n]*\n)*\s*\)",
        "# patch imports handled inline",
        code,
    )

    # Rename aliased primitives imports in synthesis to their actual names
    # (since they're now in the same file and not imported)
    code = code.replace("_measure_basic(", "measure_basic(")
    code = code.replace("_char_category_metrics(", "char_category_metrics(")
    code = code.replace("_line_metrics(", "line_metrics(")
    code = code.replace("_word_metrics(", "word_metrics(")
    code = code.replace("_find_invisibles(", "find_invisibles(")
    code = code.replace("_count_graphemes(", "count_graphemes(")
    code = code.replace("_casefold_text(", "casefold_text(")
    code = code.replace("_normalize_unicode(", "normalize_unicode(")
    code = code.replace("_normalized_equal(", "normalized_equal(")
    code = code.replace("_raw_equal(", "raw_equal(")
    code = code.replace("_visible_repr(", "visible_repr(")
    code = code.replace("_detect_confusables(", "detect_confusables(")
    code = code.replace("_detect_mixed_scripts(", "detect_mixed_scripts(")
    code = code.replace("_common_prefix_suffix(", "common_prefix_suffix(")
    code = code.replace("_diff_spans(", "diff_spans(")
    code = code.replace("_first_diff(", "first_diff(")
    code = code.replace("_levenshtein_distance(", "levenshtein_distance(")

    # _protocol module: capabilities.py uses _SUPPORTED_PROTOCOL_VERSIONS (aliased)
    code = code.replace(
        "supported_protocol_versions=_SUPPORTED_PROTOCOL_VERSIONS,",
        "supported_protocol_versions=SUPPORTED_PROTOCOL_VERSIONS,",
    )

    return code, imports, exact_import_globals


def build_single_file(output_path: str | None = None) -> str:
    """Combine all eggcalc modules into a single file."""
    version = get_version()

    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "eggcalc.py")

    content: list[str] = [HEADER]
    content.append(f'__version__ = "{version}"\n')

    # Collect all imports from all modules
    all_imports: list[str] = []
    all_module_code: list[str] = []
    all_exact_globals: list[str] = []

    # Core calculator modules
    for mod in MODULES_CALC:
        code, imports, _ = get_module_code(mod)
        all_module_code.append(f"\n# === {mod}.py ===\n")
        all_module_code.append(code)
        all_imports.extend(imports)

    # Exact text tools
    all_module_code.append("\n# === Exact text tools ===\n")
    for mod in MODULES_EXACT:
        code, imports, _ = get_module_code(mod)
        all_module_code.append(f"\n# === {mod}.py ===\n")
        all_module_code.append(code)
        all_imports.extend(imports)

    # MCP server - rename functions that conflict with exact module names
    MCP_CONFLICT_FUNCTIONS = [
        "text_equal",
        "text_replace_check",
        "line_range_extract",
        "line_range_compare",
        "text_window",
        "list_compare",
        "shell_split",
        "shell_quote_join",
        "argv_compare",
        "dotenv_validate",
        "ini_validate",
        "markdown_structure",
        "code_fence_extract",
        "patch_apply_check",
        "patch_summary",
        "path_analyze",
        "path_normalize",
        "path_compare",
        "path_scope_check",
        "escape_text",
        "unescape_text",
        "text_hash",
        "text_transform",
        "text_fingerprint",
        "text_position",
        "identifier_analyze",
        "identifier_inspect",
        "glob_match",
        "unicode_policy_check",
        "canonicalize_text",
    ]
    all_module_code.append("\n# === MCP server ===\n")
    for mod in MODULES_MCP:
        code, imports, exact_globals = get_module_code(mod)
        all_exact_globals.extend(exact_globals)
        # Rename conflicting MCP wrapper functions so exact versions aren't overwritten
        for fn_name in MCP_CONFLICT_FUNCTIONS:
            code = code.replace(f"def {fn_name}(", f"def _mcp_{fn_name}(", 1)
            code = code.replace(f'"{fn_name}": {fn_name},', f'"{fn_name}": _mcp_{fn_name},')
        all_module_code.append(f"\n# === {mod}.py ===\n")
        all_module_code.append(code)
        all_imports.extend(imports)

    # Deduplicate imports while preserving order
    seen: set[str] = set()
    unique_imports: list[str] = []
    for imp in all_imports:
        # Normalize for deduplication (strip whitespace and indentation)
        normalized = imp.strip()
        if normalized not in seen:
            seen.add(normalized)
            # Strip any leading indentation so imports are at column 0
            unique_imports.append(normalized + "\n")

    # Add unique imports at the top (after header)
    if unique_imports:
        content.append("\n# === Collected imports ===\n")
        content.extend(unique_imports)
        content.append("\n")

    # Add module code
    content.extend(all_module_code)

    # Add exact module global aliases (from ..exact import ... as _xxx)
    # These are needed because the top-level imports were stripped during processing
    if all_exact_globals:
        content.append("\n# === Exact module global aliases ===\n")
        for g in all_exact_globals:
            content.append(g + "\n")

    # Add patch function aliases needed by MCP tools.
    # The lazy imports in tools.py use "as _patch_apply_check" / "as _patch_summary"
    # but build_single.py strips those import blocks. The unprefixed functions are
    # globals from the inlined patch.py, so we create the aliases at module level.
    content.append("\n# === Patch function aliases for MCP tools ===\n")
    content.append("_patch_apply_check = patch_apply_check\n")
    content.append("_patch_summary = patch_summary\n")

    # Combined entry point
    content.append("\n# === Entry point ===\n")
    content.append("""
# NOTE: All modules are inlined into this file.
# Functions are available in global scope - no import needed.

def _main():
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="eggcalc - Natural language calculator + MCP server")
    parser.add_argument("--mcp", action="store_true", help="Run as MCP server")
    parser.add_argument("expression", nargs="*", help="Math expression to evaluate")
    parser.add_argument("-e", "--expression", dest="single_expr", metavar="<expr>", help="Evaluate a single expression (useful for piping)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress expression in output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--usage", action="store_true", help="Show full usage information and examples")
    parser.add_argument("-v", "--version", action="store_true", help="Show version information")
    parser.add_argument("-i", "--interactive", action="store_true", help="Start interactive REPL mode")
    parser.add_argument("-s", "--show", action="store_true", help="Show expression in output (default for interactive)")
    parser.add_argument("--verbose", action="store_true", help="Show expression in output")
    parser.add_argument("--mcp-profile", metavar="<profile>", help="MCP server tool profile filter")
    parser.add_argument("--mcp-schema-detail", action="store_true", help="Show full JSON Schema in MCP tools/list")
    parser.add_argument("--capabilities", action="store_true", help="Show runtime capabilities as JSON and exit")
    args = parser.parse_args()

    if args.capabilities:
        caps = detect_capabilities()
        print(caps.to_json(indent=2))
        return 0

    if args.mcp:
        sys.argv = ["eggcalc", "--mcp"]
        if args.mcp_profile:
            sys.argv.extend(["--mcp-profile", args.mcp_profile])
        if args.mcp_schema_detail:
            sys.argv.append("--mcp-schema-detail")
        return normalize_main()
    elif args.usage:
        print_help()
        return 0
    elif args.expression or args.single_expr:
        sys.argv = ["eggcalc"]
        if args.single_expr:
            sys.argv.extend(["-e", args.single_expr])
        else:
            sys.argv.extend(args.expression)
        if args.json:
            sys.argv.append("--json")
        if args.quiet:
            sys.argv.append("-q")
        if args.verbose:
            sys.argv.append("--verbose")
        if args.interactive:
            sys.argv.append("-i")
        if args.show:
            sys.argv.append("-s")
        if args.mcp_profile:
            sys.argv.extend(["--mcp-profile", args.mcp_profile])
        if args.mcp_schema_detail:
            sys.argv.append("--mcp-schema-detail")
        return normalize_main()
    else:
        # No expression given - forward recognized flags to normalize_main
        sys.argv = ["eggcalc"]
        if args.version:
            sys.argv.append("-v")
        if args.interactive:
            sys.argv.append("-i")
        if args.show:
            sys.argv.append("-s")
        if args.verbose:
            sys.argv.append("--verbose")
        if args.json:
            sys.argv.append("--json")
        if args.quiet:
            sys.argv.append("-q")
        if args.mcp_profile:
            sys.argv.extend(["--mcp-profile", args.mcp_profile])
        if args.mcp_schema_detail:
            sys.argv.append("--mcp-schema-detail")
        if len(sys.argv) > 1:
            return normalize_main()
        parser.print_help()
        return 0

if __name__ == "__main__":
    raise SystemExit(_main())
""")

    final_content = "".join(content)

    # Post-process: convert local `from <module> import` to global variable assignments.
    # In the single file, modules don't exist as separate packages.
    EXACT_MODULE_NAMES = {m.split("/")[-1] for m in MODULES_EXACT}
    INLINED_NAMES = EXACT_MODULE_NAMES | {"evaluator", "units", "normalize", "capabilities", "cli"}

    def _replace_local_imports(text: str) -> str:
        """Replace local `from <module> import` with global variable assignments."""
        lines = text.split("\n")
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            # Detect indented "from .<module> import" or "from <module> import"
            if (
                line
                and line[0] in " \t"
                and stripped.startswith("from ")
                and " import " in stripped
            ):
                # Handle "from . import X" pattern (implicit relative import)
                if stripped.startswith("from . import ") or stripped.startswith("from .. import "):
                    # Extract the imported names after "import"
                    after_import = stripped.split(" import ", 1)[1]
                    # Check if any imported name is an inlined module
                    skip = False
                    alias = None
                    orig_name = None
                    for name in after_import.split(","):
                        name = name.strip()
                        # Handle "X as Y" aliases
                        if " as " in name:
                            orig_name, alias = name.split(" as ", 1)
                            orig_name = orig_name.strip()
                            alias = alias.strip()
                        else:
                            orig_name = name
                            alias = None
                        if orig_name in INLINED_NAMES or orig_name in EXACT_MODULE_NAMES:
                            skip = True
                            break
                    if skip:
                        # Replace with sys.modules lookup for the module
                        target = alias if alias else orig_name
                        indent = line[: len(line) - len(line.lstrip())]
                        result.append(
                            f"{indent}{target} = sys.modules.get(__name__.rsplit('.', 1)[0] + '.{orig_name}') if '.' in __name__ else sys.modules.get('{orig_name}')"
                        )
                        i += 1
                        continue
                    # Not an inlined module - keep it
                    result.append(line)
                    i += 1
                    continue
                # Extract module name (last component after stripping dots)
                mod_name = stripped.split()[1].lstrip(".").split(".")[-1]
                if mod_name in EXACT_MODULE_NAMES:
                    indent = line[: len(line) - len(line.lstrip())]
                    after_from = stripped[len("from ") :]
                    mod_and_import = after_from.split(" import ", 1)
                    import_part = mod_and_import[1] if len(mod_and_import) > 1 else ""
                    import_part = import_part.rstrip(",").rstrip(")")

                    if "(" not in import_part:
                        # Single-line import
                        for alias in import_part.split(","):
                            alias = alias.strip()
                            if " as " in alias:
                                orig, new_name = alias.split(" as ", 1)
                                result.append(f"{indent}{new_name.strip()} = {orig.strip()}")
                            elif alias:
                                result.append(f"{indent}{alias} = {alias}")
                        i += 1
                        continue
                    else:
                        # Multi-line import
                        all_names = []
                        import_text = import_part.lstrip("(").strip()
                        if import_text:
                            for part in import_text.split(","):
                                part = part.strip().rstrip(",").rstrip(")")
                                if part:
                                    all_names.append(part)
                        i += 1
                        while i < len(lines):
                            l = lines[i].strip()
                            if l.startswith(")"):
                                i += 1
                                break
                            l = l.rstrip(",").rstrip(")")
                            if l:
                                all_names.append(l)
                            i += 1
                        for name in all_names:
                            name = name.strip()
                            if " as " in name:
                                orig, new_name = name.split(" as ", 1)
                                result.append(f"{indent}{new_name.strip()} = {orig.strip()}")
                            elif name:
                                result.append(f"{indent}{name} = {name}")
                        continue
                elif mod_name in INLINED_NAMES:
                    # Non-exact inlined module (evaluator, units, etc.) - just remove import
                    # The names are already globals in the single file
                    # Also remove surrounding try/except block if present
                    # but keep any function calls that follow (e.g. load_user_config())
                    try_start = None
                    for back in range(len(result) - 1, max(len(result) - 5, -1), -1):
                        if result[back].strip() == "try:":
                            try_start = back
                            break
                        elif result[back].strip():
                            break  # non-empty line that isn't try:
                    if try_start is not None:
                        # Look forward for except block after this import
                        j = i + 1
                        while j < len(lines):
                            s = lines[j].strip()
                            if s.startswith("except ") or s.startswith("except("):
                                # Found except - skip except line and its body
                                j += 1
                                except_indent = (
                                    len(lines[j]) - len(lines[j].lstrip()) if j < len(lines) else 0
                                )
                                while j < len(lines):
                                    ls = lines[j].strip()
                                    if not ls or ls.startswith("#") or ls.startswith("pass"):
                                        j += 1
                                    elif len(lines[j]) - len(lines[j].lstrip()) >= except_indent:
                                        j += 1
                                    else:
                                        break
                                # j now points to line after except body
                                # Set i to j - 1 so i += 1 at end makes i = j (the next line)
                                i = j - 1
                                result.pop(try_start)
                                break
                            elif s and not s.startswith("#"):
                                break
                            j += 1
                    i += 1
                    continue
            result.append(line)
            i += 1
        return "\n".join(result)

    final_content = _replace_local_imports(final_content)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_content)

    os.chmod(output_path, os.stat(output_path).st_mode | 0o111)

    print(f"Built: {output_path}")
    print(f"  Core modules: {len(MODULES_CALC)}")
    print(f"  Exact modules: {len(MODULES_EXACT)}")
    print(f"  MCP modules: {len(MODULES_MCP)}")
    print(f"  Unique imports: {len(unique_imports)}")
    return output_path


def validate_build_manifest() -> list[str]:
    """Validate the build manifest for correctness.

    Checks:
    - No duplicate modules across MODULES_CALC, MODULES_EXACT, MODULES_MCP
    - Every declared module file exists on disk
    - Import dependency order is valid (units before evaluator before normalize)

    Returns a list of error strings (empty if valid).
    """
    errors: list[str] = []

    all_modules = MODULES_CALC + MODULES_EXACT + MODULES_MCP
    seen: set[str] = set()
    for mod in all_modules:
        if mod in seen:
            errors.append(f"Duplicate module in build manifest: {mod!r}")
        seen.add(mod)

    for mod in all_modules:
        path = os.path.join(EGGCALC_DIR, mod.replace("/", os.sep) + ".py")
        if not os.path.exists(path):
            errors.append(f"Module file not found: {path}")

    # Verify required ordering constraints
    calc_indices = {m: i for i, m in enumerate(MODULES_CALC)}
    required_order = [
        ("units", "evaluator"),
        ("evaluator", "normalize"),
        ("normalize", "cli"),
        ("evaluator", "cli"),
    ]
    for before, after in required_order:
        if before in calc_indices and after in calc_indices:
            if calc_indices[before] >= calc_indices[after]:
                errors.append(
                    f"Order violation: {before!r} must come before {after!r} " f"in MODULES_CALC"
                )

    return errors


def main():
    parser = argparse.ArgumentParser(description="Build single-file eggcalc")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate build manifest without building",
    )
    args = parser.parse_args()

    if args.validate:
        errors = validate_build_manifest()
        if errors:
            for e in errors:
                print(f"ERROR: {e}")
            raise SystemExit(1)
        print("Build manifest valid.")
        return

    build_single_file(args.output)


if __name__ == "__main__":
    main()
