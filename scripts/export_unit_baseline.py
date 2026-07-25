#!/usr/bin/env python3
"""Export the pre-declaration unit behavior as a stable JSON fixture.

This exporter intentionally reads the legacy public unit tables and public
conversion helpers.  It is used from the pre-migration commit once; ordinary
tests only consume the resulting committed fixture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import eggcalc.units as units


def _dimension(unit: str) -> list[int] | None:
    value = units._structural_dimension(unit)
    return list(value._tuple()) if value is not None else None


def _legacy_scale_offset(canonical: str) -> tuple[float | None, float, bool]:
    for variants in units.UNIT_BASE.values():
        if canonical in variants:
            return float(variants[canonical]), 0.0, False

    if canonical == "K":
        return 1.0, 0.0, True
    if canonical == "C":
        return 1.0, 273.15, True
    if canonical == "F":
        return 5.0 / 9.0, 255.3722222222222, True
    if canonical == "Ra":
        return 5.0 / 9.0, 0.0, True
    return None, 0.0, False


def export() -> dict[str, object]:
    aliases: dict[str, dict[str, object]] = {}
    for alias, canonical in sorted(units.UNIT_ALIASES.items()):
        scale, offset, affine = _legacy_scale_offset(canonical)
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = export()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
