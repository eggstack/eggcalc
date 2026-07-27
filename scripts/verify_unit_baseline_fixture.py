#!/usr/bin/env python3
"""Verify the committed unit baseline fixture against current runtime behavior.

This script reads the committed fixture as immutable expected data and
compares the candidate runtime against every field.  It never regenerates
expected values, never imports the frozen exporter as a current-runtime
oracle, and never updates the fixture.

Ordinary CI verification::

    python scripts/verify_unit_baseline_fixture.py \\
        tests/fixtures/units/legacy-5a1bb34c.json

Historical reproduction (separate command)::

    python scripts/verify_unit_baseline_fixture.py \\
        tests/fixtures/units/legacy-5a1bb34c.json \\
        --regenerate --baseline-checkout /path/to/eggcalc-5a1bb34c
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _verify_metadata(fixture: dict[str, object]) -> list[str]:
    """Validate fixture metadata fields."""
    errors: list[str] = []
    meta = fixture.get("metadata")
    if not isinstance(meta, dict):
        errors.append("metadata: missing or not a dict")
        return errors

    required = ["schema_version", "source_commit", "exporter_path", "exporter_sha256"]
    for field in required:
        if field not in meta:
            errors.append(f"metadata: missing required field {field!r}")

    commit = meta.get("source_commit", "")
    if not isinstance(commit, str) or len(commit) != 40:
        errors.append("metadata.source_commit: must be a 40-character hex SHA")
    elif commit != "5a1bb34c9efa269ca6159217827f1742faa95d20":
        errors.append(f"metadata.source_commit: expected 5a1bb34c..., got {commit[:12]}...")

    exporter_hash = meta.get("exporter_sha256", "")
    exporter_path = ROOT / meta.get("exporter_path", "")
    if exporter_path.is_file():
        actual = hashlib.sha256(exporter_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if actual != exporter_hash:
            errors.append(
                f"metadata.exporter_sha256: mismatch\n"
                f"  expected from fixture: {exporter_hash}\n"
                f"  actual from file:      {actual}"
            )
    else:
        errors.append(f"metadata.exporter_path: file not found: {exporter_path}")

    return errors


def _verify_aliases(fixture: dict[str, object]) -> list[str]:
    """Compare fixture alias data against current runtime."""
    from eggcalc.units import (
        UNIT_ALIASES,
        build_unit_registry,
        get_unit_category,
        normalize_unit,
        parse_unit_expression,
    )

    errors: list[str] = []
    aliases = fixture.get("aliases")
    if not isinstance(aliases, dict):
        errors.append("aliases: missing or not a dict")
        return errors

    registry = build_unit_registry()

    # Check fixture aliases match current runtime
    current_aliases = set(UNIT_ALIASES.keys())
    fixture_aliases = set(aliases.keys())

    missing = current_aliases - fixture_aliases
    extra = fixture_aliases - current_aliases
    if missing:
        errors.append(f"aliases: {len(missing)} aliases in runtime not in fixture")
    if extra:
        errors.append(f"aliases: {len(extra)} aliases in fixture not in runtime")

    for alias in sorted(current_aliases & fixture_aliases):
        canonical = UNIT_ALIASES[alias]
        fixture_data = aliases[alias]
        if not isinstance(fixture_data, dict):
            errors.append(f"aliases.{alias}: not a dict")
            continue

        # Check canonical
        if fixture_data.get("canonical") != canonical:
            errors.append(
                f"aliases.{alias}.canonical: expected {canonical}, "
                f"got {fixture_data.get('canonical')}"
            )
            continue

        # Check dimension
        try:
            expr = parse_unit_expression(alias)
            expected_dim = list(expr.dimension._tuple())
            expected_scale = expr.scale_to_base
        except (ValueError, AttributeError):
            expected_dim = None
            expected_scale = None
        if fixture_data.get("dimension") != expected_dim:
            errors.append(f"aliases.{alias}.dimension: mismatch")
            continue

        # Check category
        expected_cat = get_unit_category(alias)
        if fixture_data.get("category") != expected_cat:
            errors.append(
                f"aliases.{alias}.category: expected {expected_cat}, "
                f"got {fixture_data.get('category')}"
            )
            continue

        # Check normalized
        expected_norm = normalize_unit(alias)
        if fixture_data.get("normalized") != expected_norm:
            errors.append(
                f"aliases.{alias}.normalized: expected {expected_norm}, "
                f"got {fixture_data.get('normalized')}"
            )
            continue

        # Check scale_to_base via public registry
        ud = registry.by_alias(alias)
        actual_scale = float(ud.scale) if ud is not None else None
        expected_scale_from_fixture = fixture_data.get("scale_to_base")
        if expected_scale_from_fixture is None:
            if actual_scale is not None:
                errors.append(f"aliases.{alias}.scale_to_base: expected None, got {actual_scale}")
        elif actual_scale is None:
            errors.append(
                f"aliases.{alias}.scale_to_base: fixture expects "
                f"{expected_scale_from_fixture}, runtime returned None"
            )
        elif abs(actual_scale - expected_scale_from_fixture) > 1e-12:
            errors.append(
                f"aliases.{alias}.scale_to_base: fixture={expected_scale_from_fixture}, "
                f"runtime={actual_scale}"
            )

        # Check offset_to_base
        actual_offset = float(ud.offset) if ud is not None else 0.0
        expected_offset = fixture_data.get("offset_to_base", 0.0)
        if abs(actual_offset - expected_offset) > 1e-9:
            errors.append(
                f"aliases.{alias}.offset_to_base: fixture={expected_offset}, "
                f"runtime={actual_offset}"
            )

        # Check affine flag
        actual_affine = bool(ud.affine) if ud is not None else False
        if fixture_data.get("affine") != actual_affine:
            errors.append(
                f"aliases.{alias}.affine: expected {actual_affine}, "
                f"got {fixture_data.get('affine')}"
            )

        # Check display value (should equal canonical for simple cases)
        expected_display = fixture_data.get("display")
        if expected_display is not None and expected_display != canonical:
            errors.append(
                f"aliases.{alias}.display: expected {canonical!r}, " f"got {expected_display!r}"
            )

    return errors


def _verify_arithmetic(fixture: dict[str, object]) -> list[str]:
    """Compare fixture arithmetic data against current runtime."""
    from eggcalc.units import UnitValue

    errors: list[str] = []
    arithmetic = fixture.get("arithmetic")
    if not isinstance(arithmetic, dict):
        errors.append("arithmetic: missing or not a dict")
        return errors

    cases = {
        "m_times_m": lambda: UnitValue(2, "m") * UnitValue(3, "m"),
        "m_div_s": lambda: UnitValue(10, "m") / UnitValue(2, "s"),
        "m_div_m": lambda: UnitValue(5, "m") / UnitValue(2, "m"),
        "m_power_2": lambda: UnitValue(2, "m") ** 2,
    }

    for label, operation in cases.items():
        expected = arithmetic.get(label)
        if expected is None:
            errors.append(f"arithmetic.{label}: missing from fixture")
            continue
        try:
            result = operation()
            actual_unit = result.unit
            actual_display = str(result)
        except Exception as exc:
            errors.append(f"arithmetic.{label}: runtime raised {exc}")
            continue
        if expected.get("unit") != actual_unit:
            errors.append(
                f"arithmetic.{label}.unit: expected {expected.get('unit')!r}, "
                f"got {actual_unit!r}"
            )
        if expected.get("display") != actual_display:
            errors.append(
                f"arithmetic.{label}.display: expected {expected.get('display')!r}, "
                f"got {actual_display!r}"
            )

    return errors


def _verify_limits(fixture: dict[str, object]) -> list[str]:
    """Compare fixture limits against current runtime."""
    from eggcalc.units import MAX_COMPOUND_ATOMS, MAX_COMPOUND_DEPTH, MAX_UNIT_STRING_LENGTH

    errors: list[str] = []
    limits = fixture.get("limits")
    if not isinstance(limits, dict):
        errors.append("limits: missing or not a dict")
        return errors

    expected = {
        "max_unit_string_length": MAX_UNIT_STRING_LENGTH,
        "max_compound_depth": MAX_COMPOUND_DEPTH,
        "max_compound_atoms": MAX_COMPOUND_ATOMS,
    }
    for key, value in expected.items():
        if limits.get(key) != value:
            errors.append(f"limits.{key}: expected {value}, got {limits.get(key)}")

    return errors


def verify_fixture(fixture_path: Path) -> list[str]:
    """Run all verification checks against the fixture."""
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    errors.extend(_verify_metadata(fixture))
    errors.extend(_verify_aliases(fixture))
    errors.extend(_verify_arithmetic(fixture))
    errors.extend(_verify_limits(fixture))
    return errors


def regenerate_fixture(fixture_path: Path, baseline_checkout: Path) -> list[str]:
    """Regenerate the fixture from the baseline and compare."""
    import subprocess
    import tempfile

    exporter = ROOT / "tests" / "fixtures" / "units" / "exporters" / "export_legacy_5a1bb34c.py"
    if not exporter.is_file():
        return [f"Frozen exporter not found: {exporter}"]

    with tempfile.TemporaryDirectory(prefix="eggcalc-fixture-repro-") as temp:
        output = Path(temp) / "regenerated.json"
        env = {"PYTHONPATH": str(baseline_checkout)}
        result = subprocess.run(
            [
                sys.executable,
                str(exporter),
                "--baseline-checkout",
                str(baseline_checkout),
                "--output",
                str(output),
            ],
            cwd=str(baseline_checkout),
            env={**dict(__import__("os").environ), **env},
            capture_output=True,
            text=True,
        )
        if result.returncode:
            return [f"Frozen exporter failed (exit {result.returncode}):\n{result.stderr}"]

        expected = fixture_path.read_text(encoding="utf-8")
        actual = output.read_text(encoding="utf-8")
        if expected != actual:
            return ["Reproduction mismatch: regenerated fixture differs from committed fixture"]

    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="Path to committed fixture JSON")
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Run frozen exporter against baseline checkout and compare",
    )
    parser.add_argument(
        "--baseline-checkout",
        type=Path,
        help="Path to clean baseline checkout (required with --regenerate)",
    )
    args = parser.parse_args()

    if not args.fixture.is_file():
        print(f"Fixture not found: {args.fixture}", file=sys.stderr)
        return 1

    if args.regenerate:
        if not args.baseline_checkout:
            print("--baseline-checkout is required with --regenerate", file=sys.stderr)
            return 1
        errors = regenerate_fixture(args.fixture, args.baseline_checkout)
    else:
        errors = verify_fixture(args.fixture)

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print("OK: fixture verified against current runtime.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
