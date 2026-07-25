#!/usr/bin/env python3
"""Compare package and generated single-file release authority surfaces."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
else:
    namespace = runpy.run_path(sys.argv[2], run_name="eggcalc_single")
    # Derive __all__ from the generated namespace directly, not from the package.
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


def _run(mode: str, generated: Path | None = None) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    args = [sys.executable, "-c", INVENTORY_CODE, mode]
    if generated is not None:
        args.append(str(generated))
    completed = subprocess.run(
        args,
        cwd=tempfile.gettempdir(),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def collect() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="eggcalc-inventory-") as temp:
        generated = Path(temp) / "eggcalc.py"
        subprocess.run(
            [sys.executable, str(ROOT / "build_single.py"), "-o", str(generated)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        package = _run("package")
        single = _run("single", generated)
    return {"package": package, "single_file": single, "allowed_differences": []}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    inventory = collect()
    if args.output is not None:
        args.output.write_text(
            json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if args.check:
        if inventory["package"] != inventory["single_file"]:
            print("Package and single-file authority inventories differ.", file=sys.stderr)
            return 1
        print("Package and single-file authority inventories match.")
    else:
        print(json.dumps(inventory, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
