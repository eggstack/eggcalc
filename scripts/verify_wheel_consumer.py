#!/usr/bin/env python3
"""Type-check and execute the public consumer against an installed wheel."""

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="eggcalc-wheel-consumer-") as temp:
        temp_path = Path(temp)
        venv = temp_path / "venv"
        consumer = temp_path / "consumer.py"
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        python = venv / ("Scripts" if os.name == "nt" else "bin") / "python"
        subprocess.run([str(python), "-m", "pip", "install", str(args.wheel)], check=True)
        subprocess.run([str(python), "-m", "pip", "install", "mypy>=1.0"], check=True)
        shutil.copy2(CONSUMER, consumer)
        probe = subprocess.run(
            [
                str(python),
                "-c",
                "import eggcalc, pathlib; p=pathlib.Path(eggcalc.__file__).parent; "
                "assert 'site-packages' in str(p) or 'dist-packages' in str(p); "
                "assert (p / 'py.typed').is_file()",
            ],
            cwd=temp_path,
            check=False,
        )
        if probe.returncode:
            return probe.returncode
        subprocess.run([str(python), "-m", "mypy", str(consumer)], check=True, cwd=temp_path)
        subprocess.run([str(python), str(consumer)], check=True, cwd=temp_path)
    print("Installed-wheel consumer passed outside the source tree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
