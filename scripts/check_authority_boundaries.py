#!/usr/bin/env python3
"""Reject regressions where unit behavior starts reading legacy adapters."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNITS = ROOT / "eggcalc" / "units.py"


def _latest_functions(tree: ast.Module) -> dict[str, ast.AST]:
    functions: dict[str, ast.AST] = {}

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            functions[node.name] = node
            self.generic_visit(node)

        visit_AsyncFunctionDef = visit_FunctionDef

    Visitor().visit(tree)
    return functions


def _names(node: ast.AST) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def check() -> list[str]:
    tree = ast.parse(UNITS.read_text(encoding="utf-8"), filename=str(UNITS))
    functions = _latest_functions(tree)
    errors: list[str] = []
    forbidden = {
        "UNIT_BASE",
        "UNIT_ALIASES",
        "UNIT_CATEGORIES",
        "TEMPERATURE_CONVERSIONS",
        "UNIT_CONVERSIONS",
        "_CATEGORY_DIMENSIONS",
        "_CATEGORY_NAME_TO_DIMENSION",
    }
    for function_name in (
        "build_unit_registry",
        "parse_unit_expression",
        "get_conversion_factor",
        "are_units_compatible",
    ):
        node = functions.get(function_name)
        if node is None:
            errors.append(f"Missing required function {function_name}")
            continue
        names = _names(node)
        bad = sorted(names & forbidden)
        if bad:
            errors.append(f"{function_name} reads legacy authority: {', '.join(bad)}")

    unit_value = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "UnitValue"),
        None,
    )
    if unit_value is None:
        errors.append("Missing UnitValue")
    else:
        names = _names(unit_value)
        if "_simplify_unit_string" in names or "_pow_unit_string" in names:
            errors.append("UnitValue arithmetic uses legacy string semantics")

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
