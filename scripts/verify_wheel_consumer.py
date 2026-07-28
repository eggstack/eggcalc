#!/usr/bin/env python3
"""Type-check and execute the public consumer against an installed wheel.

Verifies that the wheel installs cleanly into an isolated venv, that the
consumer type-checks under strict mypy, and that the consumer runs from
outside the source tree (proving no source-tree leakage).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSUMER = ROOT / "tests" / "typing" / "consumer.py"
STRICT_CONFIG = ROOT / "mypy-strict.ini"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ec-wheel-") as temp:
        temp_path = Path(temp).resolve()
        venv = temp_path / "venv"
        consumer = temp_path / "consumer.py"
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        python = (
            venv
            / ("Scripts" if os.name == "nt" else "bin")
            / ("python.exe" if os.name == "nt" else "python")
        )
        subprocess.run([str(python), "-m", "pip", "install", str(args.wheel)], check=True)
        subprocess.run([str(python), "-m", "pip", "install", "mypy>=1.0"], check=True)
        shutil.copy2(CONSUMER, consumer)

        # Copy strict mypy config into the isolated environment
        if STRICT_CONFIG.is_file():
            shutil.copy2(STRICT_CONFIG, temp_path / "mypy-strict.ini")
            mypy_config = str(temp_path / "mypy-strict.ini")
        else:
            mypy_config = ""

        # Verify the package is installed from site-packages, not the source tree
        probe = subprocess.run(
            [
                str(python),
                "-c",
                "import eggcalc, pathlib; p=pathlib.Path(eggcalc.__file__).parent; "
                "assert 'site-packages' in str(p) or 'dist-packages' in str(p); "
                "assert (p / 'py.typed').is_file(); "
                "assert not (p.parent.parent / 'eggcalc').exists(), 'source tree leaked into venv'",
            ],
            cwd=temp_path,
            check=False,
        )
        if probe.returncode:
            return probe.returncode

        # Run strict mypy type check with explicit flags
        mypy_cmd = [
            str(python),
            "-m",
            "mypy",
            "--strict",
            "--follow-imports=normal",
            "--ignore-missing-imports",
        ]
        if mypy_config:
            mypy_cmd.extend(["--config-file", mypy_config])
        mypy_cmd.append(str(consumer))
        subprocess.run(mypy_cmd, check=True, cwd=temp_path)

        # Run the consumer to verify runtime behavior
        subprocess.run([str(python), str(consumer)], check=True, cwd=temp_path)
    print("Installed-wheel consumer passed outside the source tree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
