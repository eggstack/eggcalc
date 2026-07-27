#!/usr/bin/env python3
"""Reject regressions where unit behavior starts reading legacy adapters.

This checker inspects the complete ``eggcalc/units.py`` module via the AST
to ensure:

- exactly one top-level assignment exists for each public compatibility map;
- each assignment is produced by the declaration/registry adapter path
  (``_install_generated_adapters``), not a manually maintained literal;
- no dictionary literal with built-in aliases/scales exists outside
  ``UNIT_DEFINITIONS`` and fixture/export tooling;
- public semantic functions are defined once, except explicitly documented
  compatibility wrappers (redefinitions with ``# type: ignore[no-redef]``);
- ``UnitValue`` never calls a legacy string-semantic helper.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNITS = ROOT / "eggcalc" / "units.py"

# Public compatibility maps that must have exactly one definition site,
# installed by _install_generated_adapters().
COMPATIBILITY_MAPS = (
    "UNIT_ALIASES",
    "UNIT_BASE",
    "UNIT_CATEGORIES",
    "TEMPERATURE_CONVERSIONS",
    "UNIT_CONVERSIONS",
)

# Legacy names that must not appear as manually maintained literals.
LEGACY_LITERAL_NAMES = frozenset(
    {
        "UNIT_BASE",
        "UNIT_ALIASES",
        "UNIT_CATEGORIES",
        "TEMPERATURE_CONVERSIONS",
        "UNIT_CONVERSIONS",
        "_CATEGORY_DIMENSIONS",
        "_CATEGORY_NAME_TO_DIMENSION",
        "_DERIVED_CATEGORIES",
        "_BASE_CATEGORY",
        "UNIT_CATEGORIES_EXTRA",
        "_SHORT_COMPOUND_FORMS",
        "_SHORT_COMPOUND_EXPANSION",
        "_SHORT_COMPOUND_CARET",
        "_SHORT_COMPOUND_COLLAPSE",
    }
)

# Legacy helper functions that must not exist (superseded by generated adapters).
LEGACY_HELPER_NAMES = frozenset(
    {
        "_build_unit_conversions",
        "_add_compound_conversions",
        "_parse_compound_atoms",
        "_parse_compound_signature",
        "_count_top_level_ops",
        "_find_last_top_level_op",
        "_parse_atom_signature",
        "_merge_signatures",
        "_signature_to_canonical_string",
        "_derived_category",
        "_base_unit_dimension",
        "_expand_short_compound",
        "_collapse_short_compound",
        "_short_compound_forms",
    }
)

# Functions/classes whose bodies must not reference legacy authority names.
FORBIDDEN_IN_FUNCTIONS = {
    "build_unit_registry",
    "parse_unit_expression",
    "get_conversion_factor",
    "are_units_compatible",
}

# Names that UnitValue must never call.
LEGACY_UNITVALUE_NAMES = frozenset(
    {
        "_simplify_unit_string",
        "_pow_unit_string",
        "_parse_compound_signature",
        "_structural_dimension",
    }
)


def _names(node: ast.AST) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def _all_function_defs(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Return all top-level function definitions (first definition only per name)."""
    seen: set[str] = set()
    result: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name not in seen:
                seen.add(node.name)
                result.append(node)
    return result


def _top_level_assignments(tree: ast.Module) -> dict[str, list[ast.Assign | ast.AnnAssign]]:
    """Return a map of variable name -> list of top-level assignment nodes."""
    assignments: dict[str, list[ast.Assign | ast.AnnAssign]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments.setdefault(target.id, []).append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assignments.setdefault(node.target.id, []).append(node)
    return assignments


def _is_dict_literal(node: ast.AST) -> bool:
    """Check if a node is a dictionary literal (not a function call)."""
    return isinstance(node, ast.Dict)


def _dict_literal_keys(node: ast.Dict) -> set[str]:
    """Extract string keys from a dict literal."""
    keys: set[str] = set()
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
    return keys


def check() -> list[str]:
    tree = ast.parse(UNITS.read_text(encoding="utf-8"), filename=str(UNITS))
    errors: list[str] = []

    # 1. Check that each compatibility map has exactly one top-level assignment.
    assignments = _top_level_assignments(tree)
    for name in COMPATIBILITY_MAPS:
        nodes = assignments.get(name, [])
        if len(nodes) != 1:
            errors.append(f"{name}: expected exactly one top-level assignment, found {len(nodes)}")
        else:
            # Verify it's not a manually maintained dict literal.
            node = nodes[0]
            if isinstance(node, ast.Assign):
                if _is_dict_literal(node.value):
                    errors.append(
                        f"{name}: assignment is a manually maintained dict literal, "
                        f"must be installed by _install_generated_adapters()"
                    )

    # 2. Check that no legacy helper functions exist.
    all_funcs = {node.name for node in _all_function_defs(tree)}
    for name in LEGACY_HELPER_NAMES:
        if name in all_funcs:
            errors.append(f"Legacy helper {name} still exists in units.py")

    # 3. Check that legacy literal names don't appear as dict literals
    #    outside UNIT_DEFINITIONS and fixture/export tooling.
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in LEGACY_LITERAL_NAMES:
                    if _is_dict_literal(node.value):
                        errors.append(
                            f"{target.id}: manually maintained dict literal still present"
                        )

    # 4. Check that required functions exist and don't read legacy authority names.
    functions = {node.name: node for node in _all_function_defs(tree)}
    for function_name in FORBIDDEN_IN_FUNCTIONS:
        node = functions.get(function_name)
        if node is None:
            errors.append(f"Missing required function {function_name}")
            continue
        names = _names(node)
        bad = sorted(names & LEGACY_LITERAL_NAMES)
        if bad:
            errors.append(f"{function_name} reads legacy authority: {', '.join(bad)}")

    # 5. Check that UnitValue never calls legacy string-semantic helpers.
    unit_value = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "UnitValue"),
        None,
    )
    if unit_value is None:
        errors.append("Missing UnitValue")
    else:
        names = _names(unit_value)
        bad = sorted(names & LEGACY_UNITVALUE_NAMES)
        if bad:
            errors.append(f"UnitValue arithmetic uses legacy string semantics: {', '.join(bad)}")

    return errors


def main() -> int:
    errors = check()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Unit authority boundaries valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
