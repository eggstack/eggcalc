from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
