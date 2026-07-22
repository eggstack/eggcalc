#!/usr/bin/env python3
"""Deterministic architecture-cost benchmarking for eggcalc.

Runs selected imports and evaluations in fresh subprocesses and records:
- import wall time
- loaded module count by namespace
- first calculator evaluation time
- CLI --help startup time

Output is deterministic JSON with environment metadata and statistics.

Usage:
    python scripts/measure_architecture_costs.py
    python scripts/measure_architecture_costs.py --output docs/release_6_metrics.json
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import tracemalloc
from statistics import mean, median, stdev

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = 5


def _run_timed(cmd: list[str], label: str) -> dict[str, object]:
    """Run a command in a fresh subprocess, returning timing and module info."""
    module_code = "import sys; mods = sorted([k for k in sys.modules if k.startswith('eggcalc')]); import json; print(json.dumps(mods))"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    # Time the import
    times: list[float] = []
    for _ in range(SAMPLES):
        start = time.perf_counter()
        subprocess.run(cmd, capture_output=True, timeout=30, env=env)
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    # Count modules (single run)
    result = subprocess.run(cmd, capture_output=True, timeout=30, env=env)
    module_count = 0
    try:
        mods_result = subprocess.run(
            [sys.executable, "-c", module_code],
            capture_output=True,
            timeout=30,
            env=env,
        )
        mods = json.loads(mods_result.stdout) if mods_result.returncode == 0 else []
        module_count = len(mods)
    except Exception:
        pass

    return {
        "label": label,
        "command": cmd,
        "samples": SAMPLES,
        "median_s": round(median(times), 6),
        "mean_s": round(mean(times), 6),
        "stdev_s": round(stdev(times), 6) if len(times) > 1 else 0.0,
        "loaded_modules": module_count,
    }


def measure_import_costs() -> dict[str, object]:
    """Measure import and startup costs."""
    results: dict[str, object] = {}

    # Core import
    results["import_eggcalc"] = _run_timed(
        [sys.executable, "-c", "import eggcalc"],
        "import eggcalc",
    )

    # evaluate import
    results["import_evaluate"] = _run_timed(
        [sys.executable, "-c", "from eggcalc import evaluate; evaluate('2+2')"],
        "from eggcalc import evaluate",
    )

    # CLI --help
    results["cli_help"] = _run_timed(
        [sys.executable, "-m", "eggcalc", "--help"],
        "python -m eggcalc --help",
    )

    # Simple calculator expression
    results["cli_calc"] = _run_timed(
        [sys.executable, "-m", "eggcalc", "-e", "5+3"],
        "python -m eggcalc -e 5+3",
    )

    return results


def measure_peak_memory() -> dict[str, object]:
    """Measure peak traced allocation for core import."""
    tracemalloc.start()
    import eggcalc  # noqa: F401

    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"peak_bytes": peak}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Measure eggcalc architecture costs")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    args = parser.parse_args()

    import_costs = measure_import_costs()
    memory = measure_peak_memory()

    report = {
        "python": sys.version,
        "platform": sys.platform,
        "commit": _get_commit_sha(),
        "samples": SAMPLES,
        "import_costs": import_costs,
        "memory": memory,
    }

    output = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Written to {args.output}")
    else:
        print(output)


def _get_commit_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
