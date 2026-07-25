#!/usr/bin/env python3
"""Export the pre-declaration unit behavior as a stable JSON fixture.

This exporter reads the public unit tables and public conversion helpers.
It is used to produce a committed fixture that tests consume as an external
behavioral oracle.

Usage:
    python scripts/export_unit_baseline.py --output tests/fixtures/units/legacy-5a1bb34c.json
    python scripts/export_unit_baseline.py --verify tests/fixtures/units/legacy-5a1bb34c.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import eggcalc.units as units


def _dimension(unit: str) -> list[int] | None:
    """Return the dimension tuple for a unit via parse_unit_expression."""
    try:
        expr = units.parse_unit_expression(unit)
        return list(expr.dimension._tuple())
    except (ValueError, AttributeError):
        return None


def _scale_offset(canonical: str) -> tuple[float | None, float, bool]:
    """Return (scale_to_base, offset_to_base, affine) for a canonical unit."""
    # Check non-affine units in UNIT_BASE
    for variants in units.UNIT_BASE.values():
        if canonical in variants:
            return float(variants[canonical]), 0.0, False

    # Check affine units via TEMPERATURE_CONVERSIONS
    # Affine units have entries in TEMPERATURE_CONVERSIONS as (canonical, other) keys
    for (source, _target), (_mult, _offset) in units.TEMPERATURE_CONVERSIONS.items():
        if source == canonical:
            # Find the spec to get scale and offset
            for spec in units.UNIT_DEFINITIONS:
                if spec.canonical == canonical and spec.affine:
                    return float(spec.scale_to_base), float(spec.offset_to_base), True
            break

    # Fallback: check UNIT_DEFINITIONS directly
    for spec in units.UNIT_DEFINITIONS:
        if spec.canonical == canonical:
            return float(spec.scale_to_base), float(spec.offset_to_base), bool(spec.affine)

    return None, 0.0, False


def export() -> dict[str, object]:
    aliases: dict[str, dict[str, object]] = {}
    for alias, canonical in sorted(units.UNIT_ALIASES.items()):
        scale, offset, affine = _scale_offset(canonical)
        aliases[alias] = {
            "canonical": canonical,
            "category": units.get_unit_category(alias),
            "dimension": _dimension(alias),
            "scale_to_base": scale,
            "offset_to_base": offset,
            "affine": affine,
            "display": canonical,
            "normalized": units.normalize_unit(alias),
        }

    arithmetic: dict[str, dict[str, object]] = {}
    for label, operation in {
        "m_times_m": lambda: units.UnitValue(2, "m") * units.UnitValue(3, "m"),
        "m_div_s": lambda: units.UnitValue(10, "m") / units.UnitValue(2, "s"),
        "m_div_m": lambda: units.UnitValue(5, "m") / units.UnitValue(2, "m"),
        "m_power_2": lambda: units.UnitValue(2, "m") ** 2,
    }.items():
        result = operation()
        arithmetic[label] = {"unit": result.unit, "display": str(result)}

    return {
        "metadata": {
            "source_commit": "5a1bb34c9efa269ca6159217827f1742faa95d20",
            "source": "legacy public runtime behavior",
            "exporter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "aliases": aliases,
        "arithmetic": arithmetic,
        "limits": {
            "max_unit_string_length": units.MAX_UNIT_STRING_LENGTH,
            "max_compound_depth": units.MAX_COMPOUND_DEPTH,
            "max_compound_atoms": units.MAX_COMPOUND_ATOMS,
        },
    }


def verify(fixture_path: Path) -> bool:
    """Verify that the committed fixture matches current exporter behavior."""
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    expected_hash = fixture["metadata"]["exporter_sha256"]
    actual_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    if actual_hash != expected_hash:
        print(
            f"FAIL: exporter hash mismatch\n"
            f"  expected: {expected_hash}\n"
            f"  actual:   {actual_hash}\n"
            f"  The exporter has changed. Re-run with --output to regenerate the fixture.",
            file=sys.stderr,
        )
        return False

    # Verify alias coverage
    current = export()
    current_aliases = set(current["aliases"].keys())  # type: ignore[union-attr]
    fixture_aliases = set(fixture["aliases"].keys())
    if current_aliases != fixture_aliases:
        missing = current_aliases - fixture_aliases
        extra = fixture_aliases - current_aliases
        print(
            f"FAIL: alias coverage mismatch\n"
            f"  missing from fixture: {sorted(missing)}\n"
            f"  extra in fixture:     {sorted(extra)}",
            file=sys.stderr,
        )
        return False

    # Verify arithmetic results
    for label, expected in fixture.get("arithmetic", {}).items():
        current_arith = current.get("arithmetic", {})  # type: ignore[union-attr]
        if label in current_arith:
            if current_arith[label] != expected:  # type: ignore[index]
                print(
                    f"FAIL: arithmetic mismatch for {label}\n"
                    f"  expected: {expected}\n"
                    f"  actual:   {current_arith[label]}",  # type: ignore[index]
                    file=sys.stderr,
                )
                return False

    print("OK: fixture verified against current exporter.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Output fixture path")
    parser.add_argument("--verify", type=Path, help="Verify fixture against current exporter")
    args = parser.parse_args()

    if args.verify:
        ok = verify(args.verify)
        sys.exit(0 if ok else 1)

    if args.output:
        payload = export()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(f"Exported fixture to {args.output}")
        return

    parser.error("Either --output or --verify is required")


if __name__ == "__main__":
    main()
