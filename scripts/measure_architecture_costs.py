#!/usr/bin/env python3
"""Collect controlled fresh-process architecture cost measurements."""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _stats(values: list[float]) -> dict[str, float | int]:
    return {
        "samples": len(values),
        "median_ms": round(statistics.median(values) * 1000, 4),
        "mean_ms": round(statistics.mean(values) * 1000, 4),
        "stdev_ms": round(statistics.stdev(values) * 1000, 4) if len(values) > 1 else 0.0,
    }


def _timed_python(code: str, samples: int) -> dict[str, object]:
    child = (
        "import json,sys,time,tracemalloc; "
        "tracemalloc.start(); start=time.perf_counter(); "
        f"exec({code!r}, globals()); "
        "elapsed=time.perf_counter()-start; _,peak=tracemalloc.get_traced_memory(); "
        "print(json.dumps({'elapsed':elapsed,'peak_bytes':peak,'modules':len([k for k in sys.modules if k.startswith('eggcalc')])}))"
    )
    values: list[float] = []
    peaks: list[int] = []
    modules: list[int] = []
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for _ in range(samples):
        result = subprocess.run(
            [sys.executable, "-c", child],
            cwd=tempfile.gettempdir(),
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        payload = json.loads(result.stdout)
        values.append(float(payload["elapsed"]))
        peaks.append(int(payload["peak_bytes"]))
        modules.append(int(payload["modules"]))
    return {
        **_stats(values),
        "peak_bytes": max(peaks),
        "loaded_modules": max(modules),
    }


def _timed_command(command: list[str], samples: int) -> dict[str, object]:
    values: list[float] = []
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for _ in range(samples):
        start = time.perf_counter()
        subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=True, timeout=60)
        values.append(time.perf_counter() - start)
    return _stats(values)


def collect(samples: int, single_file: Path | None = None) -> dict[str, object]:
    cases: dict[str, dict[str, object]] = {
        "import_eggcalc": _timed_python("import eggcalc", samples),
        "import_evaluate": _timed_python("from eggcalc import evaluate", samples),
        "cli_help": _timed_command([sys.executable, "-m", "eggcalc", "--help"], samples),
        "normal_expression": _timed_python("from eggcalc import evaluate; evaluate('5+3')", samples),
        "exact_command": _timed_command([sys.executable, "-m", "eggcalc", "count", "hello"], samples),
        "mcp_initialize": _timed_python(
            "from eggcalc.mcp.server import McpServer, McpSessionState; "
            "s=McpServer(); q=s.create_session(McpSessionState.UNINITIALIZED); "
            "s.handle_request({'jsonrpc':'2.0','id':1,'method':'initialize','params':{"
            "'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'bench','version':'1'}}},q); s.close()",
            samples,
        ),
        "tools_list_compact": _timed_python(
            "import json; from eggcalc.mcp.server import McpServer, McpSessionState; "
            "s=McpServer(); q=s.create_session(McpSessionState.READY); "
            "json.dumps(s.handle_request({'jsonrpc':'2.0','id':1,'method':'tools/list','params':{'schema_detail':'compact'}},q), default=lambda value: dict(value) if hasattr(value,'items') else list(value)); s.close()",
            samples,
        ),
        "tools_list_full": _timed_python(
            "import json; from eggcalc.mcp.server import McpServer, McpSessionState; "
            "s=McpServer(); q=s.create_session(McpSessionState.READY); "
            "json.dumps(s.handle_request({'jsonrpc':'2.0','id':1,'method':'tools/list','params':{'schema_detail':'full'}},q), default=lambda value: dict(value) if hasattr(value,'items') else list(value)); s.close()",
            samples,
        ),
        "unit_registry": _timed_python(
            "from eggcalc import units; "
            "getattr(units, 'build_unit_registry', lambda: dict(units.UNIT_BASE))()",
            samples,
        ),
        "unit_parse_normal": _timed_python(
            "from eggcalc import units; "
            "units.parse_unit_expression('kg*m/s**2')",
            samples,
        ),
        "unit_parse_maximum": _timed_python(
            "from eggcalc import units; "
            "units.parse_unit_expression('*'.join(['m']*16+['s']*16))",
            samples,
        ),
        "unitvalue_arithmetic": _timed_python(
            "from eggcalc.units import UnitValue; (UnitValue(2,'m')*UnitValue(3,'m'))/(UnitValue(2,'s'))",
            samples,
        ),
    }
    if single_file is not None:
        cases["single_file_startup"] = _timed_command(
            [sys.executable, str(single_file), "5+3"], samples
        )
    return cases


def _commit_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", default="candidate")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--single-file", type=Path)
    args = parser.parse_args()
    if args.samples < 2:
        raise SystemExit("--samples must be at least 2")
    report = {
        "label": args.label,
        "commit_sha": _commit_sha(),
        "os": platform.system(),
        "architecture": platform.machine(),
        "python": sys.version,
        "command": " ".join(sys.argv),
        "measurements": collect(args.samples, args.single_file),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Written to {args.output}")


if __name__ == "__main__":
    main()
