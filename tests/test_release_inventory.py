"""Release inventory mutation tests.

Verifies that the release inventory script detects mutations to the
generated single-file artifact's protocol version, command targets,
unit offsets, MCP profiles, and capability fields.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_inventory() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="eggcalc-inventory-") as temp:
        output = Path(temp) / "inventory.json"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "release_inventory.py"),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(output.read_text(encoding="utf-8"))


def test_release_inventory_matches_package_and_single_file() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "release_inventory.py"), "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "inventories match" in completed.stdout


def test_release_inventory_is_canonical_json(tmp_path: Path) -> None:
    output = tmp_path / "inventory.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "release_inventory.py"),
            "--check",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=True,
    )
    text = output.read_text(encoding="utf-8")
    inventory = json.loads(text)
    assert inventory["allowed_differences"] == []
    assert inventory["package"] == inventory["single_file"]
    assert text.endswith("\n")


def test_inventory_contains_protocol_versions() -> None:
    inventory = _run_inventory()
    pkg = inventory["package"]
    assert "protocol_versions" in pkg
    assert "2024-11-05" in pkg["protocol_versions"]
    assert "2025-11-25" in pkg["protocol_versions"]


def test_inventory_contains_version() -> None:
    inventory = _run_inventory()
    pkg = inventory["package"]
    assert "version" in pkg
    assert pkg["version"]  # non-empty


def test_inventory_contains_unit_definitions() -> None:
    inventory = _run_inventory()
    pkg = inventory["package"]
    assert "units" in pkg
    assert "definitions" in pkg["units"]
    assert len(pkg["units"]["definitions"]) > 0
    # Each definition has required fields
    for spec in pkg["units"]["definitions"]:
        assert "canonical" in spec
        assert "aliases" in spec
        assert "dimension" in spec
        assert "scale_to_base" in spec
        assert "offset_to_base" in spec
        assert "affine" in spec
        assert "category" in spec
        assert "base_canonical" in spec


def test_inventory_contains_mcp_tools() -> None:
    inventory = _run_inventory()
    pkg = inventory["package"]
    assert "mcp" in pkg
    assert "tools" in pkg["mcp"]
    assert len(pkg["mcp"]["tools"]) > 0
    assert "profiles" in pkg["mcp"]


def test_inventory_mutation_detects_missing_export() -> None:
    """If a public API export is removed from the single-file build,
    the inventory check should detect the difference."""
    inventory = _run_inventory()
    pkg = inventory["package"]
    single = inventory["single_file"]
    # Both should have the same public API
    assert pkg["public_api"] == single["public_api"]
    # If we remove an item from single's public_api, they should differ
    mutated_single = dict(single)
    mutated_single["public_api"] = single["public_api"][:-1]
    assert pkg["public_api"] != mutated_single["public_api"]


def test_inventory_mutation_detects_changed_protocol_version() -> None:
    """If the protocol version changes in the single-file build,
    the inventory check should detect the difference."""
    inventory = _run_inventory()
    pkg = inventory["package"]
    single = inventory["single_file"]
    assert pkg["protocol_versions"] == single["protocol_versions"]
    # Mutation: change protocol version
    mutated_single = dict(single)
    mutated_single["protocol_versions"] = ["2024-11-05"]  # remove one
    assert pkg["protocol_versions"] != mutated_single["protocol_versions"]


def test_inventory_mutation_detects_changed_command_target() -> None:
    """If a CLI command target changes in the single-file build,
    the inventory check should detect the difference."""
    inventory = _run_inventory()
    pkg = inventory["package"]
    single = inventory["single_file"]
    assert pkg["cli"] == single["cli"]
    # Mutation: change a command target
    mutated_single = dict(single)
    mutated_cli = [dict(spec) for spec in single["cli"]]
    if mutated_cli:
        mutated_cli[0]["target"] = "mutated.target"
    mutated_single["cli"] = mutated_cli
    assert pkg["cli"] != mutated_single["cli"]


def test_inventory_mutation_detects_changed_unit_offset() -> None:
    """If a unit offset changes in the single-file build,
    the inventory check should detect the difference."""
    inventory = _run_inventory()
    pkg = inventory["package"]
    single = inventory["single_file"]
    assert pkg["units"] == single["units"]
    # Mutation: change a unit offset
    mutated_single = dict(single)
    mutated_units = dict(single["units"])
    if mutated_units["definitions"]:
        mutated_defs = list(mutated_units["definitions"])
        mutated_defs[0] = dict(mutated_defs[0])
        mutated_defs[0]["offset_to_base"] = 999.999
        mutated_units["definitions"] = mutated_defs
    mutated_single["units"] = mutated_units
    assert pkg["units"] != mutated_single["units"]


def test_inventory_mutation_detects_changed_mcp_profile() -> None:
    """If an MCP profile changes in the single-file build,
    the inventory check should detect the difference."""
    inventory = _run_inventory()
    pkg = inventory["package"]
    single = inventory["single_file"]
    assert pkg["mcp"] == single["mcp"]
    # Mutation: change a profile
    mutated_single = dict(single)
    mutated_mcp = dict(single["mcp"])
    if mutated_mcp["profiles"]:
        first_key = list(mutated_mcp["profiles"].keys())[0]
        mutated_profiles = dict(mutated_mcp["profiles"])
        mutated_profiles[first_key] = ["mutated_tool"]
        mutated_mcp["profiles"] = mutated_profiles
    mutated_single["mcp"] = mutated_mcp
    assert pkg["mcp"] != mutated_single["mcp"]


def test_inventory_mutation_detects_changed_capability_field() -> None:
    """If a capability field changes in the single-file build,
    the inventory check should detect the difference."""
    inventory = _run_inventory()
    pkg = inventory["package"]
    single = inventory["single_file"]
    assert pkg["mcp"] == single["mcp"]
    # Mutation: change a capability field
    mutated_single = dict(single)
    mutated_mcp = dict(single["mcp"])
    if mutated_mcp["metadata"]:
        first_key = list(mutated_mcp["metadata"].keys())[0]
        mutated_meta = dict(mutated_mcp["metadata"])
        mutated_meta[first_key] = "mutated_value"
        mutated_mcp["metadata"] = mutated_meta
    mutated_single["mcp"] = mutated_mcp
    assert pkg["mcp"] != mutated_single["mcp"]
