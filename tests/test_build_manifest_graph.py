from __future__ import annotations

from pathlib import Path

import pytest

import build_single


def spec(name: str, *depends_on: str) -> build_single.ModuleSpec:
    return build_single.ModuleSpec(name, f"{name.replace('.', '/')}.py", "core", depends_on)


def test_topological_sort_accepts_dependency_declared_after_consumer() -> None:
    manifest = (spec("consumer", "dependency"), spec("dependency"))

    assert [item.name for item in build_single._topological_sort(manifest)] == [
        "dependency",
        "consumer",
    ]


def test_topological_sort_preserves_declaration_order_for_ties() -> None:
    manifest = (spec("first"), spec("second"), spec("consumer", "first", "second"))

    assert [item.name for item in build_single._topological_sort(manifest)] == [
        "first",
        "second",
        "consumer",
    ]


def test_topological_sort_rejects_unknown_dependency() -> None:
    with pytest.raises(ValueError, match="Unknown dependency"):
        build_single._topological_sort((spec("consumer", "missing"),))


def test_topological_sort_rejects_cycle() -> None:
    with pytest.raises(ValueError, match="Dependency cycle"):
        build_single._topological_sort((spec("a", "b"), spec("b", "a")))


def test_validator_rejects_undeclared_relative_import(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "cli.py").write_text("COMMANDS = []\n", encoding="utf-8")
    (tmp_path / "consumer.py").write_text("from .missing import value\n", encoding="utf-8")
    monkeypatch.setattr(build_single, "EGGCALC_DIR", str(tmp_path))
    manifest = (spec("consumer"),)

    errors = build_single.validate_build_manifest(manifest)

    assert any("Undeclared relative import target" in error for error in errors)


def test_validator_rejects_relative_import_without_dependency_edge(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "cli.py").write_text("COMMANDS = []\n", encoding="utf-8")
    (tmp_path / "consumer.py").write_text("from .dependency import value\n", encoding="utf-8")
    (tmp_path / "dependency.py").write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(build_single, "EGGCALC_DIR", str(tmp_path))
    monkeypatch.setattr(build_single, "_literal_cli_targets", lambda: set())

    errors = build_single.validate_build_manifest((spec("consumer"), spec("dependency")))

    assert any("not declared as a dependency" in error for error in errors)


def test_validator_rejects_missing_cli_target(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "cli.py").write_text("COMMANDS = []\n", encoding="utf-8")
    monkeypatch.setattr(build_single, "EGGCALC_DIR", str(tmp_path))
    monkeypatch.setattr(build_single, "_literal_cli_targets", lambda: {"missing"})

    errors = build_single.validate_build_manifest((spec("cli"),))

    assert any("Lazy CLI target 'missing' absent" in error for error in errors)


def test_validator_rejects_duplicate_generated_global(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "cli.py").write_text("COMMANDS = []\n", encoding="utf-8")
    (tmp_path / "first.py").write_text("def collide():\n    return 1\n", encoding="utf-8")
    (tmp_path / "second.py").write_text("def collide():\n    return 2\n", encoding="utf-8")
    monkeypatch.setattr(build_single, "EGGCALC_DIR", str(tmp_path))
    monkeypatch.setattr(build_single, "_literal_cli_targets", lambda: set())

    errors = build_single.validate_build_manifest((spec("first"), spec("second")))

    assert any("Duplicate generated global 'collide'" in error for error in errors)


def test_validator_rejects_residual_relative_import_after_generation(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "cli.py").write_text("COMMANDS = []\n", encoding="utf-8")
    (tmp_path / "module.py").write_text("from .other import value\n", encoding="utf-8")
    monkeypatch.setattr(build_single, "EGGCALC_DIR", str(tmp_path))
    monkeypatch.setattr(build_single, "_literal_cli_targets", lambda: set())
    monkeypatch.setattr(
        build_single,
        "get_module_code",
        lambda _module: ("from .other import value\n", [], []),
    )

    errors = build_single.validate_build_manifest((spec("module"),))

    assert any("Residual package-relative import" in error for error in errors)
