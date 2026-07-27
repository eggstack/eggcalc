#!/usr/bin/env python3
"""Frozen historical unit exporter for baseline commit 5a1bb34c.

This script exports unit behavior from the exact baseline commit and is used
to produce the committed fixture ``legacy-5a1bb34c.json``.  It must be run
against a clean checkout of the baseline commit; it refuses to run if the
working tree is dirty or if ``HEAD`` does not match the expected SHA.

Usage::

    BASELINE_CHECKOUT=/path/to/eggcalc-5a1bb34c
    PYTHONPATH="$BASELINE_CHECKOUT" \\
        python tests/fixtures/units/exporters/export_legacy_5a1bb34c.py \\
        --baseline-checkout "$BASELINE_CHECKOUT" \\
        --output tests/fixtures/units/legacy-5a1bb34c.json

This script uses only the public ``UnitRegistry`` API and the public
normalization helpers available at the baseline commit.  It does not import
or reference any source files from the candidate checkout, nor does it depend
on private declaration inventories (``UNIT_DEFINITIONS``, ``UnitSpec``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

EXPECTED_SHA = "5a1bb34c9efa269ca6159217827f1742faa95d20"


def _verify_baseline(checkout: Path) -> None:
    """Verify that the checkout is the exact expected baseline."""
    if not checkout.is_dir():
        raise SystemExit(f"Baseline checkout not found: {checkout}")

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        capture_output=True,
        text=True,
        check=True,
    )
    actual_sha = result.stdout.strip()
    if actual_sha != EXPECTED_SHA:
        raise SystemExit(
            f"HEAD is {actual_sha}, expected {EXPECTED_SHA}.  "
            "Check out the exact baseline commit."
        )

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=checkout,
        capture_output=True,
        text=True,
        check=True,
    )
    if status.stdout.strip():
        raise SystemExit(
            "Baseline checkout has uncommitted changes.  "
            "Commit or stash before generating the fixture."
        )


def _dimension_tuple(unit: str) -> list[int] | None:
    """Return the dimension tuple for a unit via parse_unit_expression."""
    from eggcalc.units import parse_unit_expression

    try:
        expr = parse_unit_expression(unit)
        return list(expr.dimension._tuple())
    except (ValueError, AttributeError):
        return None


def export() -> dict[str, object]:
    """Export unit behavioral data as a JSON-serializable dict.

    Uses only the public ``UnitRegistry`` API and ``get_unit_category`` /
    ``normalize_unit`` helpers — never reads ``UNIT_DEFINITIONS`` directly.
    """
    from eggcalc.units import (
        MAX_COMPOUND_ATOMS,
        MAX_COMPOUND_DEPTH,
        MAX_UNIT_STRING_LENGTH,
        UNIT_ALIASES,
        UnitValue,
        build_unit_registry,
        get_unit_category,
        normalize_unit,
    )

    registry = build_unit_registry()

    aliases: dict[str, dict[str, object]] = {}
    for alias, canonical in sorted(UNIT_ALIASES.items()):
        ud = registry.by_alias(alias)
        if ud is None:
            scale: float | None = None
            offset: float = 0.0
            affine = False
        else:
            scale = float(ud.scale)
            offset = float(ud.offset)
            affine = bool(ud.affine)
        aliases[alias] = {
            "canonical": canonical,
            "category": get_unit_category(alias),
            "dimension": _dimension_tuple(alias),
            "scale_to_base": scale,
            "offset_to_base": offset,
            "affine": affine,
            "display": canonical,
            "normalized": normalize_unit(alias),
        }

    arithmetic: dict[str, dict[str, object]] = {}
    for label, operation in {
        "m_times_m": lambda: UnitValue(2, "m") * UnitValue(3, "m"),
        "m_div_s": lambda: UnitValue(10, "m") / UnitValue(2, "s"),
        "m_div_m": lambda: UnitValue(5, "m") / UnitValue(2, "m"),
        "m_power_2": lambda: UnitValue(2, "m") ** 2,
        "m_add_cm": lambda: UnitValue(1, "m") + UnitValue(100, "cm"),
        "F_to_C": lambda: UnitValue(68, "F").convert_to("C"),
        "m_floordiv_m": lambda: UnitValue(10, "m") // UnitValue(3, "m"),
        "m_mod_m": lambda: UnitValue(10, "m") % UnitValue(3, "m"),
    }.items():
        result = operation()
        arithmetic[label] = {"unit": result.unit, "display": str(result)}

    return {
        "metadata": {
            "schema_version": 1,
            "source_commit": EXPECTED_SHA,
            "exporter_path": "tests/fixtures/units/exporters/export_legacy_5a1bb34c.py",
            "exporter_sha256": "",
            "python_implementation": sys.implementation.name,
            "python_version": ".".join(map(str, sys.version_info[:3])),
            "platform": sys.platform,
            "generation_command": " ".join(sys.argv),
            "source": "legacy public runtime behavior",
        },
        "aliases": aliases,
        "arithmetic": arithmetic,
        "limits": {
            "max_unit_string_length": MAX_UNIT_STRING_LENGTH,
            "max_compound_depth": MAX_COMPOUND_DEPTH,
            "max_compound_atoms": MAX_COMPOUND_ATOMS,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-checkout",
        type=Path,
        required=True,
        help="Path to a clean checkout of the baseline commit",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output fixture path")
    args = parser.parse_args()

    _verify_baseline(args.baseline_checkout)

    exporter_bytes = Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    exporter_hash = hashlib.sha256(exporter_bytes).hexdigest()

    payload = export()
    payload["metadata"]["exporter_sha256"] = exporter_hash

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Exported fixture to {args.output}")
    print(f"Exporter hash: {exporter_hash}")
    print(f"Aliases: {len(payload['aliases'])}")
    print(f"Arithmetic cases: {len(payload['arithmetic'])}")


if __name__ == "__main__":
    main()
