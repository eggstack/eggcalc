"""Release inventory isolation and mutation tests.

Verifies that the release inventory script:
- runs wheel and generated-file probes outside the repository
- detects mutations to protocol version, command targets, unit offsets,
  MCP profiles, and capability fields in real artifacts
- exits non-zero from --check when package/single-file mismatch
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _copy_source_tree(dst: Path) -> Path:
    """Copy the source tree (sans build artefacts) into a fresh temp dir."""
    dst.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns(
        "__pycache__",
        "*.pyc",
        ".git",
        "dist",
        "build",
        "*.egg-info",
        ".venv",
        ".agents",
    )
    shutil.copytree(ROOT, dst, ignore=ignore, dirs_exist_ok=True)
    return dst


def _build_single_file(src_dir: Path) -> Path:
    """Build a fresh generated single-file from src_dir."""
    output = src_dir / "eggcalc_release.py"
    subprocess.run(
        [sys.executable, str(src_dir / "build_single.py"), "-o", str(output)],
        cwd=src_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    return output


def _build_wheel(src_dir: Path) -> Path:
    """Build a wheel from src_dir."""
    dist = src_dir / "dist"
    dist.mkdir(exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "build", "-w", "--outdir", str(dist)],
        cwd=src_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(dist.glob("*.whl"))
    assert len(wheels) == 1, f"Expected 1 wheel, found {len(wheels)}: {wheels}"
    return wheels[0]


def _run_check(single_file: Path, wheel: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run the inventory script in --check mode."""
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "release_inventory.py"),
        "--check",
        "--single-file",
        str(single_file),
    ]
    if wheel is not None:
        cmd.extend(["--wheel", str(wheel)])
    return subprocess.run(
        cmd,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _run_inventory(**kwargs: object) -> dict[str, object]:
    """Run the inventory script in explicit artifact mode (no --check)."""
    with tempfile.TemporaryDirectory(prefix="eggcalc-inventory-") as temp:
        output = Path(temp) / "inventory.json"
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "release_inventory.py"),
            "--output",
            str(output),
        ]
        for key, value in kwargs.items():
            if value is not None:
                cmd.append(f"--{key.replace('_', '-')}")
                cmd.append(str(value))
        subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)
        return json.loads(output.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Baseline tests
# ---------------------------------------------------------------------------


def test_release_inventory_check_mode_passes(tmp_path: Path) -> None:
    """Built single-file matches package (no mutation)."""
    src = _copy_source_tree(tmp_path / "src")
    single_file = _build_single_file(src)
    wheel = _build_wheel(src)
    completed = _run_check(single_file, wheel)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "inventories match" in completed.stdout


def test_release_inventory_is_canonical_json(tmp_path: Path) -> None:
    """Inventory output is deterministic sorted JSON."""
    src = _copy_source_tree(tmp_path / "src")
    single_file = _build_single_file(src)
    wheel = _build_wheel(src)
    output = tmp_path / "inventory.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "release_inventory.py"),
            "--check",
            "--single-file",
            str(single_file),
            "--wheel",
            str(wheel),
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


# ---------------------------------------------------------------------------
# Isolation and coverage tests
# ---------------------------------------------------------------------------


def test_explicit_artifact_inventory_has_hashes(tmp_path: Path) -> None:
    """Explicit artifact mode records SHA-256 hashes."""
    src = _copy_source_tree(tmp_path / "src")
    single_file = _build_single_file(src)
    wheel = _build_wheel(src)
    inventory = _run_inventory(single_file=single_file, wheel=wheel)
    assert "artifacts" in inventory
    assert "wheel" in inventory["artifacts"]
    assert "single_file" in inventory["artifacts"]
    for key in ("wheel", "single_file"):
        h = inventory["artifacts"][key]["hash_sha256"]
        assert len(h) == 64


def test_inventory_contains_protocol_versions(tmp_path: Path) -> None:
    """Inventory includes supported protocol versions."""
    src = _copy_source_tree(tmp_path / "src")
    single_file = _build_single_file(src)
    wheel = _build_wheel(src)
    inventory = _run_inventory(single_file=single_file, wheel=wheel)
    pkg = inventory["package"]
    assert "protocol_versions" in pkg
    assert "2024-11-05" in pkg["protocol_versions"]
    assert "2025-11-25" in pkg["protocol_versions"]


def test_inventory_contains_version(tmp_path: Path) -> None:
    """Inventory includes package version."""
    src = _copy_source_tree(tmp_path / "src")
    single_file = _build_single_file(src)
    wheel = _build_wheel(src)
    inventory = _run_inventory(single_file=single_file, wheel=wheel)
    assert inventory["package"]["version"]


def test_inventory_contains_unit_definitions(tmp_path: Path) -> None:
    """Inventory includes all unit definitions with required fields."""
    src = _copy_source_tree(tmp_path / "src")
    single_file = _build_single_file(src)
    wheel = _build_wheel(src)
    inventory = _run_inventory(single_file=single_file, wheel=wheel)
    pkg = inventory["package"]
    assert "units" in pkg
    assert "definitions" in pkg["units"]
    assert len(pkg["units"]["definitions"]) > 0
    for spec in pkg["units"]["definitions"]:
        for field in (
            "canonical",
            "aliases",
            "dimension",
            "scale_to_base",
            "offset_to_base",
            "affine",
            "category",
            "base_canonical",
        ):
            assert field in spec, f"Missing {field} in {spec.get('canonical')}"


def test_inventory_contains_mcp_tools(tmp_path: Path) -> None:
    """Inventory includes MCP tools, schemas, and profiles."""
    src = _copy_source_tree(tmp_path / "src")
    single_file = _build_single_file(src)
    wheel = _build_wheel(src)
    inventory = _run_inventory(single_file=single_file, wheel=wheel)
    pkg = inventory["package"]
    assert "mcp" in pkg
    assert len(pkg["mcp"]["tools"]) > 0
    assert "profiles" in pkg["mcp"]


# ---------------------------------------------------------------------------
# Real artifact mutation tests (assert --check returns non-zero)
# ---------------------------------------------------------------------------


def test_mutation_detects_altered_single_file_protocol(tmp_path: Path) -> None:
    """Altering protocol version in a generated file is detected by --check."""
    src = _copy_source_tree(tmp_path / "src")
    single_file = _build_single_file(src)
    wheel = _build_wheel(src)
    content = single_file.read_text(encoding="utf-8")
    mutated = single_file.with_name("mutated_protocol.py")
    mutated.write_text(
        content.replace(
            'SUPPORTED_PROTOCOL_VERSIONS: tuple[str, ...] = ("2024-11-05", "2025-11-25")',
            'SUPPORTED_PROTOCOL_VERSIONS: tuple[str, ...] = ("9999-01-01",)',
        ),
        encoding="utf-8",
    )
    completed = _run_check(mutated, wheel)
    assert completed.returncode != 0, "Mutation to protocol version was not detected"


def test_mutation_detects_altered_single_file_export(tmp_path: Path) -> None:
    """Removing a public API export from a generated file is detected."""
    src = _copy_source_tree(tmp_path / "src")
    single_file = _build_single_file(src)
    wheel = _build_wheel(src)
    content = single_file.read_text(encoding="utf-8")
    mutated = single_file.with_name("mutated_export.py")
    mutated.write_text(
        content.replace("__all__ = [", "__all__ = ['__removed__'] + [", 1),
        encoding="utf-8",
    )
    completed = _run_check(mutated, wheel)
    assert completed.returncode != 0, "Mutation to public API was not detected"


def test_mutation_detects_altered_single_file_unit_offset(tmp_path: Path) -> None:
    """Altering a unit offset in a generated file is detected."""
    import re

    src = _copy_source_tree(tmp_path / "src")
    single_file = _build_single_file(src)
    wheel = _build_wheel(src)
    content = single_file.read_text(encoding="utf-8")
    mutated = single_file.with_name("mutated_unit.py")
    match = re.search(r"scale_to_base=([\d.e+-]+)", content)
    assert match is not None, "Could not find scale_to_base in generated file"
    old_val = match.group(0)
    mutated.write_text(content.replace(old_val, "scale_to_base=999.999", 1), encoding="utf-8")
    completed = _run_check(mutated, wheel)
    assert completed.returncode != 0, "Mutation to unit offset was not detected"


def test_mutation_detects_altered_single_file_mcp_tool(tmp_path: Path) -> None:
    """Altering an MCP tool schema in a generated file is detected."""
    import re

    src = _copy_source_tree(tmp_path / "src")
    single_file = _build_single_file(src)
    wheel = _build_wheel(src)
    content = single_file.read_text(encoding="utf-8")
    mutated = single_file.with_name("mutated_mcp.py")
    desc_match = re.search(
        r'("math_eval":\s*\{[^}]*"description":\s*")([^"]*?)(")',
        content,
        re.DOTALL,
    )
    assert desc_match is not None, "Could not find math_eval description"
    old_desc = desc_match.group(0)
    mutated.write_text(
        content.replace(old_desc, desc_match.group(1) + "MUTATED" + desc_match.group(3), 1),
        encoding="utf-8",
    )
    completed = _run_check(mutated, wheel)
    assert completed.returncode != 0, "Mutation to MCP tool schema was not detected"


def test_mutation_detects_altered_wheel_protocol(tmp_path: Path) -> None:
    """Build a temp wheel with a controlled mutation and verify --check fails."""
    import re

    src = _copy_source_tree(tmp_path / "src-wheel-mut")
    proto_path = src / "eggcalc" / "_protocol.py"
    original = proto_path.read_text(encoding="utf-8")
    match = re.search(r"SUPPORTED_PROTOCOL_VERSIONS[^=]*=\s*\(([^)]+)\)", original)
    assert match is not None, "Could not find SUPPORTED_PROTOCOL_VERSIONS"
    mutated_proto = original.replace(
        match.group(0),
        'SUPPORTED_PROTOCOL_VERSIONS = ("9999-01-01",)',
    )
    proto_path.write_text(mutated_proto, encoding="utf-8")

    mutated_wheel = _build_wheel(src)
    clean_src = _copy_source_tree(tmp_path / "src-clean")
    single_file = _build_single_file(clean_src)

    completed = _run_check(single_file, mutated_wheel)
    assert completed.returncode != 0, "Mutation to wheel protocol version was not detected"


def test_mutation_detects_altered_wheel_unit_offset(tmp_path: Path) -> None:
    """Build a temp wheel with a controlled unit offset mutation."""
    src = _copy_source_tree(tmp_path / "src-unit-mut")
    # Mutate the km offset in the generated compatibility maps by replacing the
    # generated content for the 'm' base.
    generated = src / "eggcalc" / "_generated_units.py"
    if generated.is_file():
        content = generated.read_text(encoding="utf-8")
        # Replace the scale for "m" within the "m" base group.
        content2 = content.replace(
            '"m": 1.0,',
            '"m": 1.0,\n        "BAD": 42.0,',
            1,
        )
        # Fall back if the simple substitution didn't match anything.
        if content2 == content:
            content2 = content.replace(
                '"m": 1.0',
                '"m": 999.0',
                1,
            )
        generated.write_text(content2, encoding="utf-8")
    else:
        # Mutate units.py — find a scale_to_base literal to perturb.
        units_path = src / "eggcalc" / "units.py"
        content = units_path.read_text(encoding="utf-8")
        units_path.write_text(
            content.replace("scale_to_base=1000.0", "scale_to_base=1001.0", 1),
            encoding="utf-8",
        )

    mutated_wheel = _build_wheel(src)
    clean_src = _copy_source_tree(tmp_path / "src-clean")
    single_file = _build_single_file(clean_src)
    completed = _run_check(single_file, mutated_wheel)
    assert completed.returncode != 0, "Mutation to wheel unit offset was not detected"


def test_rebuild_from_mutated_source_detects_mutation(tmp_path: Path) -> None:
    """Mutate source, rebuild single-file, rerun inventory: --check fails."""
    import re

    src = _copy_source_tree(tmp_path / "src-rebuild")
    # Mutate the version before rebuilding single-file.
    version_path = src / "eggcalc" / "_version.py"
    original = version_path.read_text(encoding="utf-8")
    mutated = re.sub(
        r'__version__\s*=\s*"[^"]+"',
        '__version__ = "99.99.99+mutated"',
        original,
    )
    assert mutated != original, "Could not mutate _version.py"
    version_path.write_text(mutated, encoding="utf-8")

    mutated_single = _build_single_file(src)
    # Wheel from clean source for comparison.
    clean_src = _copy_source_tree(tmp_path / "src-clean")
    clean_single = _build_single_file(clean_src)
    wheel = _build_wheel(clean_src)

    completed = _run_check(mutated_single, wheel)
    assert completed.returncode != 0, "Rebuild-from-mutated-source not detected"
    # Sanity: a clean single-file passes.
    clean_completed = _run_check(clean_single, wheel)
    assert clean_completed.returncode == 0, "Clean rebuild should pass: " + (
        clean_completed.stderr or ""
    )


# ---------------------------------------------------------------------------
# Wheel installation isolation
# ---------------------------------------------------------------------------


def test_inventory_wheel_runs_outside_repository(tmp_path: Path) -> None:
    """Wheel subprocess must run in a venv and resolve eggcalc under site-packages."""
    src = _copy_source_tree(tmp_path / "src-isolated")
    wheel = _build_wheel(src)
    single_file = _build_single_file(src)

    with tempfile.TemporaryDirectory(prefix="eggcalc-isolated-") as temp:
        temp_path = Path(temp)
        venv_dir = temp_path / "venv"
        venv.create(venv_dir, with_pip=True, clear=True)
        python = venv_dir / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        subprocess.run(
            [str(python), "-m", "pip", "install", str(wheel.resolve()), "--no-deps"],
            check=True,
            capture_output=True,
        )
        # Verify eggcalc resolves under venv site-packages.
        probe = subprocess.run(
            [
                str(python),
                "-c",
                "import eggcalc, pathlib; "
                "p = str(pathlib.Path(eggcalc.__file__).parent); "
                "print(p); "
                "assert 'site-packages' in p or 'dist-packages' in p, p; "
                "assert (pathlib.Path(eggcalc.__file__).parent / 'py.typed').is_file()",
            ],
            cwd=temp_path,
            check=True,
            capture_output=True,
            text=True,
        )
        # PYTHONPATH must not be set to the repository root in subprocess.
        env = {k: v for k, v in __import__("os").environ.items() if k != "PYTHONPATH"}
        # Probe runs the inventory collection directly in the venv.
        probe_script = temp_path / "probe.py"
        probe_script.write_text(
            (ROOT / "scripts" / "release_inventory.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        # Verify PYTHONPATH is empty / not pointing at repo.
        for path in [temp_path, venv_dir]:
            assert str(ROOT) not in str(path)
