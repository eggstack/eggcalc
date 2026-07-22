#!/usr/bin/env python3
"""Audit the eggcalc import graph.

Records which modules are loaded after various import and CLI scenarios,
wall-clock import timing, and subpackage counts.  Output is deterministic
JSON written to stdout or a file.

Standard-library only -- no external deps.

Usage:
    python scripts/audit_import_graph.py
    python scripts/audit_import_graph.py --output report.json
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from typing import Any

PYTHON = sys.executable
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMED_SAMPLES = 3
TIMEOUT = 30.0

# Code snippets executed in fresh subprocesses.  Each prints a JSON array of
# eggcalc.* module names collected from sys.modules.

_SNIPPET_IMPORT_EGGCALC = (
    "import sys, json, eggcalc;"
    "print(json.dumps(sorted(k for k in sys.modules if k.startswith('eggcalc'))))"
)

_SNIPPET_FROM_EVALUATE = (
    "import sys, json;"
    "from eggcalc import evaluate;"
    "print(json.dumps(sorted(k for k in sys.modules if k.startswith('eggcalc'))))"
)

_SNIPPET_IMPORT_NORMALIZE = (
    "import sys, json;"
    "import eggcalc.normalize;"
    "print(json.dumps(sorted(k for k in sys.modules if k.startswith('eggcalc'))))"
)

_SNIPPET_TIMED = (
    "import sys, json, time;"
    "_t0 = time.monotonic();"
    "import eggcalc;"
    "_elapsed = time.monotonic() - _t0;"
    "print(json.dumps({'elapsed': _elapsed, "
    "'modules': sorted(k for k in sys.modules if k.startswith('eggcalc'))}))"
)


def _run_subprocess(code: str, timeout: float = TIMEOUT) -> str:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([REPO_ROOT, env.get("PYTHONPATH", "")])
    result = subprocess.run(
        [PYTHON, "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"subprocess failed (rc={result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _modules_after(expr: str) -> list[str]:
    return json.loads(_run_subprocess(expr))


def _timed_import() -> dict[str, Any]:
    raw = _run_subprocess(_SNIPPET_TIMED)
    return json.loads(raw)


def _wall_time_samples(n: int) -> list[dict[str, Any]]:
    return [_timed_import() for _ in range(n)]


def _cli_import_modules(args: list[str]) -> list[str]:
    code = (
        "import sys, json\n"
        "sys.argv = ['eggcalc'] + " + json.dumps(args) + "\n"
        "from eggcalc.normalize import main as _m\n"
        "try:\n"
        "    _m()\n"
        "except (SystemExit, Exception):\n"
        "    pass\n"
        "print(json.dumps(sorted(k for k in sys.modules if k.startswith('eggcalc'))))\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([REPO_ROOT, env.get("PYTHONPATH", "")])
    result = subprocess.run(
        [PYTHON, "-c", code],
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        env=env,
    )
    lines = result.stdout.strip().splitlines()
    for line in reversed(lines):
        line = line.strip()
        if line.startswith("["):
            return json.loads(line)
    raise RuntimeError(
        f"No JSON array found in CLI output (rc={result.returncode}): "
        f"{result.stdout[:200]!r}"
    )


def _subpackage_counts(modules: list[str]) -> dict[str, int]:
    exact = sum(1 for m in modules if m.startswith("eggcalc.exact"))
    mcp = sum(1 for m in modules if m.startswith("eggcalc.mcp"))
    return {"eggcalc.exact": exact, "eggcalc.mcp": mcp}


def audit() -> dict[str, Any]:
    import_eggcalc = _modules_after(_SNIPPET_IMPORT_EGGCALC)
    from_evaluate = _modules_after(_SNIPPET_FROM_EVALUATE)
    import_normalize = _modules_after(_SNIPPET_IMPORT_NORMALIZE)

    cli_help_modules = _cli_import_modules(["--help"])
    cli_expr_modules = _cli_import_modules(["5+3"])
    cli_inspect_modules = _cli_import_modules(["inspect", "hello"])

    timed_samples = _wall_time_samples(TIMED_SAMPLES)
    timed_modules = timed_samples[-1]["modules"] if timed_samples else []

    all_modules = sorted(
        set(import_eggcalc) | set(from_evaluate) | set(import_normalize)
        | set(cli_help_modules) | set(cli_expr_modules)
        | set(cli_inspect_modules) | set(timed_modules)
    )

    return {
        "environment": {
            "python": sys.version,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": platform.platform(),
            "os": os.name,
            "executable": PYTHON,
        },
        "import_graph": {
            "import_eggcalc": import_eggcalc,
            "from_eggcalc_import_evaluate": from_evaluate,
            "import_eggcalc_normalize": import_normalize,
        },
        "cli_scenarios": {
            "eggcalc_help": cli_help_modules,
            "eggcalc_expression": cli_expr_modules,
            "eggcalc_inspect": cli_inspect_modules,
        },
        "wall_time": {
            "samples": timed_samples,
        },
        "subpackage_counts": {
            "import_eggcalc": _subpackage_counts(import_eggcalc),
            "from_eggcalc_import_evaluate": _subpackage_counts(from_evaluate),
            "cli_help": _subpackage_counts(cli_help_modules),
            "cli_expression": _subpackage_counts(cli_expr_modules),
        },
        "all_modules_observed": all_modules,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path (default: stdout)",
    )
    args = parser.parse_args()

    data = audit()
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(text, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
