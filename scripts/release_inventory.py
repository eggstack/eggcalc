#!/usr/bin/env python3
"""Compare package and generated single-file release authority surfaces.

Supports two modes:

1. **Explicit artifact mode** (for production inventory)::

    python scripts/release_inventory.py \\
        --wheel dist/eggcalc-*.whl \\
        --single-file /tmp/eggcalc-release.py \\
        --output /tmp/inventory.json

2. **Quick check mode** (for CI, builds internally)::

    python scripts/release_inventory.py --check

Both modes produce deterministic JSON with artifact hashes, version,
protocol, unit, CLI, MCP, and public API inventories.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Inventory probe code (runs in isolated subprocess)
# ---------------------------------------------------------------------------

INVENTORY_CODE = r'''
import json
import runpy
import sys
from collections.abc import Mapping

def plain(value):
    if isinstance(value, Mapping):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value

mode = sys.argv[1]
if mode == "package":
    import eggcalc as api
    from eggcalc import _protocol, cli, units
    from eggcalc.mcp.server import McpServer
    namespace = vars(api)
elif mode == "single_file":
    namespace = runpy.run_path(sys.argv[2], run_name="eggcalc_single")
    all_names = namespace.get("__all__")
    if all_names is None:
        all_names = [name for name in namespace if not name.startswith("_")]
    api = type("Api", (), {"__version__": namespace["__version__"], "__all__": all_names})
    _protocol = type("Protocol", (), {"SUPPORTED_PROTOCOL_VERSIONS": namespace["SUPPORTED_PROTOCOL_VERSIONS"]})
    cli = type("Cli", (), {"COMMANDS": namespace["COMMANDS"]})
    units = type("Units", (), {name: namespace[name] for name in (
        "UNIT_DEFINITIONS", "UNIT_ALIASES", "UNIT_CATEGORIES", "UNIT_BASE"
    )})
    McpServer = namespace["McpServer"]
else:
    raise SystemExit(f"Unknown mode: {mode}")

server = McpServer()
registry = server.registry
try:
    unit_definitions = []
    for spec in units.UNIT_DEFINITIONS:
        unit_definitions.append({
            "canonical": spec.canonical,
            "aliases": sorted(spec.aliases),
            "dimension": list(spec.dimension._tuple()),
            "scale_to_base": spec.scale_to_base,
            "offset_to_base": spec.offset_to_base,
            "affine": spec.affine,
            "display": spec.display,
            "category": spec.category,
            "base_canonical": spec.base_canonical,
        })
    result = {
        "version": api.__version__,
        "protocol_versions": list(_protocol.SUPPORTED_PROTOCOL_VERSIONS),
        "public_api": sorted(getattr(api, "__all__", [])),
        "cli": [dict(spec) for spec in cli.COMMANDS],
        "units": {
            "definitions": sorted(unit_definitions, key=lambda item: item["canonical"]),
            "aliases": dict(sorted(units.UNIT_ALIASES.items())),
            "categories": dict(sorted(units.UNIT_CATEGORIES.items())),
            "base": {key: dict(sorted(value.items())) for key, value in sorted(units.UNIT_BASE.items())},
        },
        "mcp": {
            "tools": sorted(registry.tool_names),
            "schemas": plain(dict(sorted(registry.schemas.items()))),
            "metadata": plain(dict(sorted(registry.metadata.items()))),
            "profiles": {key: list(value) for key, value in sorted(registry.profiles.items())},
        },
    }
finally:
    server.close()
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
'''


def _probe_in_venv(python: Path, probe_script: Path, mode: str, artifact: Path | None) -> dict:
    """Run the inventory probe in an isolated venv, outside the repository."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH",)}
    args = [str(python), str(probe_script), mode]
    if artifact is not None:
        args.append(str(artifact))
    completed = subprocess.run(
        args,
        cwd=tempfile.gettempdir(),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _collect_package_inventory() -> dict[str, object]:
    """Collect inventory from the source package (for CI --check mode)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        [sys.executable, "-c", INVENTORY_CODE, "package"],
        cwd=tempfile.gettempdir(),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _collect_single_file_inventory(generated: Path) -> dict[str, object]:
    """Collect inventory from a generated single-file."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        [sys.executable, "-c", INVENTORY_CODE, "single_file", str(generated)],
        cwd=tempfile.gettempdir(),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file with normalized line endings."""
    h = hashlib.sha256()
    h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def _collect_with_artifacts(
    wheel: Path | None = None,
    single_file: Path | None = None,
) -> dict[str, object]:
    """Collect inventories from explicit artifact inputs with isolated probes."""
    if wheel is None and single_file is None:
        raise SystemExit(
            "At least one of --wheel or --single-file must be provided for explicit artifact mode."
        )

    with tempfile.TemporaryDirectory(prefix="ec-inv-") as temp:
        temp_path = Path(temp).resolve()
        probe_script = temp_path / "probe.py"
        probe_script.write_text(INVENTORY_CODE, encoding="utf-8")

        result: dict[str, object] = {
            "allowed_differences": [],
            "artifacts": {},
        }

        if wheel is not None:
            venv_dir = temp_path / "wheel-venv"
            venv.create(venv_dir, with_pip=True, clear=True)
            python = (
                venv_dir
                / ("Scripts" if os.name == "nt" else "bin")
                / ("python.exe" if os.name == "nt" else "python")
            )
            subprocess.run(
                [str(python), "-m", "pip", "install", str(wheel.resolve()), "--no-deps"],
                check=True,
                capture_output=True,
            )
            probe = subprocess.run(
                [
                    str(python),
                    "-c",
                    "import eggcalc, pathlib; "
                    "p = pathlib.Path(eggcalc.__file__).parent; "
                    "assert 'site-packages' in str(p) or 'dist-packages' in str(p), "
                    "'eggcalc resolved to {p}'; "
                    "assert (p / 'py.typed').is_file(), 'py.typed missing'; "
                    "import sys; "
                    "assert not any('eggcalc' in str(p) and 'site' not in str(p) "
                    "for p in sys.path if isinstance(p, str)), 'source tree leaked'",
                ],
                cwd=temp_path,
                check=False,
                capture_output=True,
                text=True,
            )
            if probe.returncode != 0:
                raise SystemExit(f"Wheel isolation check failed: {probe.stderr}")
            pkg_inv = _probe_in_venv(python, probe_script, "package", None)
            result["package"] = pkg_inv
            result["artifacts"]["wheel"] = {
                "path": str(wheel),
                "hash_sha256": _sha256(wheel),
            }

        if single_file is not None:
            copied = temp_path / "eggcalc_single.py"
            shutil.copy2(single_file, copied)
            sf_inv = _probe_in_venv(sys.executable, probe_script, "single_file", copied)
            if "package" not in result:
                # No wheel supplied — require explicit wheel input for package comparison.
                raise SystemExit(
                    "Single-file inventory requires --wheel for package comparison; "
                    "provide --wheel or run in --check mode for internal package build."
                )
            result["single_file"] = sf_inv
            result["artifacts"]["single_file"] = {
                "path": str(single_file),
                "hash_sha256": _sha256(single_file),
            }

    return result


def collect() -> dict[str, object]:
    """Build a fresh single-file and compare with package (CI --check mode)."""
    with tempfile.TemporaryDirectory(prefix="ec-inventory-") as temp:
        generated = Path(temp) / "eggcalc.py"
        subprocess.run(
            [sys.executable, str(ROOT / "build_single.py"), "-o", str(generated)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        package = _collect_package_inventory()
        single = _collect_single_file_inventory(generated)
    return {"package": package, "single_file": single, "allowed_differences": []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Build and compare internally")
    parser.add_argument("--wheel", type=Path, help="Path to wheel for explicit inventory")
    parser.add_argument(
        "--single-file", type=Path, help="Path to generated file for explicit inventory"
    )
    parser.add_argument("--output", type=Path, help="Output JSON path")
    args = parser.parse_args()

    if args.wheel or args.single_file:
        inventory = _collect_with_artifacts(wheel=args.wheel, single_file=args.single_file)
    else:
        inventory = collect()

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    if args.check:
        if inventory["package"] != inventory["single_file"]:
            print("Package and single-file authority inventories differ.", file=sys.stderr)
            return 1
        print("Package and single-file authority inventories match.")
    elif not args.output:
        print(json.dumps(inventory, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
