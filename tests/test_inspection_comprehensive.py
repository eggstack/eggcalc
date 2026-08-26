"""Comprehensive inspection tests (Workstreams E, F, G).

Covers field-level assertions, negative/boundary tests, invariant tests,
security/adversarial tests, and resource bounds for all inspectors.
"""

import json
from pathlib import Path

import pytest

from eggcalc.exact.cargo import (
    _MAX_CARGO_INPUT_LENGTH as _CARGO_MAX_INPUT_LENGTH,
)
from eggcalc.exact.cargo import (
    cargo_toml_inspect,
)
from eggcalc.exact.manifests import (
    _MAX_FINDINGS,
    _MAX_INPUT_LENGTH,
    go_mod_inspect,
    lockfile_summary,
    package_json_inspect,
    pyproject_inspect,
    requirements_inspect,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(rel: str) -> str:
    return (FIXTURES / rel).read_text(encoding="utf-8")


# ========================================================================
# Workstream E: Fixture-loaded tests
# ========================================================================


class TestPythonFixtures:
    """Tests using python manifest fixtures."""

    def test_setuptools_static(self):
        text = _load_fixture("manifests/python/setuptools_static.toml")
        r = pyproject_inspect(text)
        assert r["parse_ok"] is True
        assert r["project_name"] == "my-setuptools-pkg"
        assert r["project_version"] == "1.0.0"
        assert r["build_backend"] == "setuptools.backends._legacy:_Backend"
        assert r["build_requirements"] == ["setuptools>=68.0"]
        assert r["requires_python"] == ">=3.10"
        assert r["dependencies_count"] == 2
        assert r["optional_dependency_groups"] == {"dev": 2, "docs": 1}
        assert r["scripts"] == {"my-cli": "mypkg.cli:main"}
        assert r["entry_points"] == {"my_plugin": {"hello": "mypkg.plugins:hello"}}
        assert r["urls"] == {
            "Homepage": "https://example.com",
            "Repository": "https://github.com/example/my-setuptools-pkg",
        }
        assert "setuptools" in r["package_manager_signals"]
        assert "tool.setuptools" in r["tool_sections"]
        assert r["tool_sections"] == sorted(r["tool_sections"])

    def test_setuptools_dynamic(self):
        text = _load_fixture("manifests/python/setuptools_dynamic.toml")
        r = pyproject_inspect(text)
        assert r["parse_ok"] is True
        assert r["project_name"] == "my-dynamic-pkg"
        assert r["dynamic"] == ["version"]
        assert r["project_version"] is None

    def test_poetry(self):
        text = _load_fixture("manifests/python/poetry.toml")
        r = pyproject_inspect(text)
        assert r["parse_ok"] is True
        assert r["project_name"] is None  # poetry uses [tool.poetry], no [project]
        assert "poetry" in r["package_manager_signals"]
        assert "tool.poetry" in r["tool_sections"]

    def test_hatch(self):
        text = _load_fixture("manifests/python/hatch.toml")
        r = pyproject_inspect(text)
        assert r["parse_ok"] is True
        assert r["project_name"] == "hatch-demo"
        assert "hatch" in r["package_manager_signals"]
        assert "tool.hatch" in r["tool_sections"]

    def test_pdm(self):
        text = _load_fixture("manifests/python/pdm.toml")
        r = pyproject_inspect(text)
        assert r["parse_ok"] is True
        assert r["project_name"] == "pdm-demo"
        assert "pdm" in r["package_manager_signals"]

    def test_uv(self):
        text = _load_fixture("manifests/python/uv.toml")
        r = pyproject_inspect(text)
        assert r["parse_ok"] is True
        assert r["project_name"] == "uv-demo"
        assert "uv" in r["package_manager_signals"]

    def test_flit(self):
        text = _load_fixture("manifests/python/flit.toml")
        r = pyproject_inspect(text)
        assert r["parse_ok"] is True
        assert r["project_name"] == "flit-demo"
        assert "flit" in r["package_manager_signals"]

    def test_multi_tool(self):
        text = _load_fixture("manifests/python/multi_tool.toml")
        r = pyproject_inspect(text)
        assert r["parse_ok"] is True
        assert r["tool_sections"] == [
            "tool.black",
            "tool.mypy",
            "tool.pytest",
            "tool.ruff",
        ]
        assert len(r["tool_sections"]) == len(set(r["tool_sections"]))

    def test_invalid(self):
        text = _load_fixture("manifests/python/invalid.toml")
        r = pyproject_inspect(text)
        assert r["parse_ok"] is False
        assert any(f["code"] == "TOML_PARSE_ERROR" for f in r["findings"])


class TestCargoFixtures:
    """Tests using cargo manifest fixtures."""

    def test_single_package(self):
        text = _load_fixture("manifests/cargo/single_package.toml")
        r = cargo_toml_inspect(text)
        assert r["parse_ok"] is True
        assert r["package"]["name"] == "my-crate"
        assert r["package"]["version"] == "0.1.0"
        assert r["package"]["edition"] == "2021"
        assert "serde" in r["dependencies"]["dependencies"]
        assert "assert_cmd" in r["dependencies"]["dev_dependencies"]
        assert "cc" in r["dependencies"]["build_dependencies"]

    def test_virtual_workspace(self):
        text = _load_fixture("manifests/cargo/virtual_workspace.toml")
        r = cargo_toml_inspect(text)
        assert r["parse_ok"] is True
        assert r["workspace"]["present"] is True
        assert len(r["workspace"]["members"]) == 3
        assert "old-crate" in r["workspace"]["exclude"]

    def test_workspace_package(self):
        text = _load_fixture("manifests/cargo/workspace_package.toml")
        r = cargo_toml_inspect(text)
        assert r["parse_ok"] is True
        assert r["workspace"]["present"] is True

    def test_workspace_deps(self):
        text = _load_fixture("manifests/cargo/workspace_deps.toml")
        r = cargo_toml_inspect(text)
        assert r["parse_ok"] is True
        common = r["dependencies"]["dependencies"]["common"]
        assert common["workspace"] is True

    def test_target_specific(self):
        text = _load_fixture("manifests/cargo/target_specific.toml")
        r = cargo_toml_inspect(text)
        assert r["parse_ok"] is True
        ts = r["dependencies"]["target_specific"]
        assert len(ts) >= 2

    def test_renamed_dep(self):
        text = _load_fixture("manifests/cargo/renamed_dep.toml")
        r = cargo_toml_inspect(text)
        assert r["parse_ok"] is True
        assert "my-serde" in r["dependencies"]["dependencies"]
        assert r["dependencies"]["dependencies"]["my-serde"]["version"] == "1.0"

    def test_git_path_registry(self):
        text = _load_fixture("manifests/cargo/git_path_registry.toml")
        r = cargo_toml_inspect(text)
        assert r["parse_ok"] is True
        local = r["dependencies"]["dependencies"]["local_lib"]
        assert local["path"] == "../local-lib"
        remote = r["dependencies"]["dependencies"]["remote"]
        assert remote["git"] == "https://github.com/example/repo"
        assert len(r["path_dependencies"]) == 1

    def test_confusable_aliases(self):
        text = _load_fixture("manifests/cargo/confusable_aliases.toml")
        r = cargo_toml_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["duplicate_or_confusable_dependency_names"]) > 0

    def test_invalid(self):
        text = _load_fixture("manifests/cargo/invalid.toml")
        r = cargo_toml_inspect(text)
        assert r["parse_ok"] is False


class TestJavaScriptFixtures:
    """Tests using JavaScript manifest fixtures."""

    def test_basic(self):
        text = _load_fixture("manifests/javascript/basic.json")
        r = package_json_inspect(text)
        assert r["parse_ok"] is True
        assert r["name"] == "my-app"
        assert r["version"] == "2.0.0"
        assert r["private"] is True
        assert r["package_type"] == "module"
        assert r["dependencies_count"] == 1
        assert r["dev_dependencies_count"] == 2
        assert r["peer_dependencies_count"] == 1
        assert r["optional_dependencies_count"] == 1
        assert r["engines"] == {"node": ">=18"}
        assert r["package_manager"] == "yarn@3.5.0"
        assert r["workspaces"] == ["packages/*"]

    def test_workspaces_object_form(self):
        text = _load_fixture("manifests/javascript/workspaces.json")
        r = package_json_inspect(text)
        assert r["parse_ok"] is True
        assert r["workspaces"] == ["packages/*", "apps/*"]

    def test_invalid(self):
        text = _load_fixture("manifests/javascript/invalid.json")
        r = package_json_inspect(text)
        assert r["parse_ok"] is False


class TestGoFixtures:
    """Tests using Go manifest fixtures."""

    def test_basic(self):
        text = _load_fixture("manifests/go/basic.mod")
        r = go_mod_inspect(text)
        assert r["parse_ok"] is True
        assert r["module_path"] == "github.com/example/project"
        assert r["go_version"] == "1.22"
        assert r["toolchain"] == "go1.22.1"
        assert r["require_count"] == 2

    def test_with_replace(self):
        text = _load_fixture("manifests/go/with_replace.mod")
        r = go_mod_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["replace_directives"]) == 2
        assert len(r["exclude_directives"]) == 1

    def test_invalid(self):
        text = _load_fixture("manifests/go/invalid.mod")
        r = go_mod_inspect(text)
        assert r["parse_ok"] is True
        assert r["module_path"] is None
        assert any(f["code"] == "MISSING_MODULE" for f in r["findings"])


class TestRequirementsFixtures:
    """Tests using requirements fixtures."""

    def test_plain(self):
        text = _load_fixture("requirements/plain.txt")
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert r["total_lines"] > 0
        assert len(r["package_specs"]) >= 4

    def test_extras_specifiers(self):
        text = _load_fixture("requirements/extras_specifiers.txt")
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["package_specs"]) >= 4

    def test_env_markers(self):
        text = _load_fixture("requirements/env_markers.txt")
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["environment_markers"]) >= 2

    def test_direct_refs(self):
        text = _load_fixture("requirements/direct_refs.txt")
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["direct_urls"]) >= 2

    def test_vcs_refs(self):
        text = _load_fixture("requirements/vcs_refs.txt")
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["vcs_refs"]) >= 3

    def test_editable(self):
        text = _load_fixture("requirements/editable.txt")
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["editable_refs"]) >= 2

    def test_includes(self):
        text = _load_fixture("requirements/includes.txt")
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["requirement_includes"]) >= 2
        assert len(r["constraints_includes"]) >= 1

    def test_hash_multiline(self):
        text = _load_fixture("requirements/hash_multiline.txt")
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["hash_options"]) >= 3

    def test_index_options(self):
        text = _load_fixture("requirements/index_options.txt")
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["index_options"]) >= 4

    def test_malformed_extras(self):
        text = _load_fixture("requirements/malformed_extras.txt")
        r = requirements_inspect(text)
        assert r["parse_ok"] is True

    def test_shell_attack(self):
        text = _load_fixture("requirements/shell_attack.txt")
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["suspicious_lines"]) >= 3

    def test_confusable_names(self):
        text = _load_fixture("requirements/confusable_names.txt")
        r = requirements_inspect(text)
        assert r["parse_ok"] is True


class TestLockfileFixtures:
    """Tests using lockfile fixtures."""

    def test_package_lock(self):
        text = _load_fixture("lockfiles/package-lock.json")
        r = lockfile_summary(text)
        assert r["parse_ok"] is True
        assert r["detected_kind"] == "package-lock"
        assert r["ecosystem"] == "npm"
        assert r["approximate_package_count"] >= 2

    def test_poetry_lock(self):
        text = _load_fixture("lockfiles/poetry.lock")
        r = lockfile_summary(text)
        assert r["parse_ok"] is True
        assert r["detected_kind"] == "poetry-lock"
        assert r["ecosystem"] == "poetry"
        assert r["approximate_package_count"] == 3

    def test_cargo_lock(self):
        text = _load_fixture("lockfiles/cargo.lock")
        r = lockfile_summary(text, kind="cargo-lock")
        assert r["parse_ok"] is True
        assert r["detected_kind"] == "cargo-lock"
        assert r["ecosystem"] == "cargo"

    def test_unknown_lockfile(self):
        text = _load_fixture("lockfiles/unknown.lock")
        r = lockfile_summary(text)
        assert r["parse_ok"] is True
        assert r["detected_kind"] == "unknown"


# ========================================================================
# Workstream F: Field-level assertions
# ========================================================================


class TestPyprojectFieldLevel:
    """Field-level assertions for pyproject_inspect."""

    def test_project_name_populated(self):
        r = pyproject_inspect('[project]\nname = "x"\n')
        assert r["project_name"] == "x"

    def test_project_name_empty(self):
        r = pyproject_inspect("[build-system]\nrequires = []\n")
        assert r["project_name"] is None

    def test_project_version_populated(self):
        r = pyproject_inspect('[project]\nname = "x"\nversion = "1.0"\n')
        assert r["project_version"] == "1.0"

    def test_project_version_empty(self):
        r = pyproject_inspect('[project]\nname = "x"\n')
        assert r["project_version"] is None

    def test_build_backend_populated(self):
        r = pyproject_inspect('[build-system]\nbuild-backend = "setuptools"\n')
        assert r["build_backend"] == "setuptools"

    def test_build_backend_empty(self):
        r = pyproject_inspect('[build-system]\nrequires = ["x"]\n')
        assert r["build_backend"] is None

    def test_build_requirements_populated(self):
        r = pyproject_inspect('[build-system]\nrequires = ["a", "b"]\n')
        assert r["build_requirements"] == ["a", "b"]

    def test_build_requirements_empty(self):
        r = pyproject_inspect("[build-system]\nrequires = []\n")
        assert r["build_requirements"] == []

    def test_build_backend_path_populated(self):
        r = pyproject_inspect('[build-system]\nbackend-path = ["."]\n')
        assert r["build_backend_path"] == ["."]

    def test_build_backend_path_empty(self):
        r = pyproject_inspect('[build-system]\nrequires = ["x"]\n')
        assert r["build_backend_path"] is None

    def test_requires_python_populated(self):
        r = pyproject_inspect('[project]\nrequires-python = ">=3.10"\n')
        assert r["requires_python"] == ">=3.10"

    def test_requires_python_empty(self):
        r = pyproject_inspect('[project]\nname = "x"\n')
        assert r["requires_python"] is None

    def test_dependencies_count_populated(self):
        r = pyproject_inspect('[project]\nname = "x"\ndependencies = ["a", "b"]\n')
        assert r["dependencies_count"] == 2

    def test_dependencies_count_empty(self):
        r = pyproject_inspect('[project]\nname = "x"\n')
        assert r["dependencies_count"] == 0

    def test_optional_deps_populated(self):
        r = pyproject_inspect(
            '[project]\n[project.optional-dependencies]\ndev = ["a"]\ntest = ["b", "c"]\n'
        )
        assert r["optional_dependency_groups"] == {"dev": 1, "test": 2}

    def test_optional_deps_empty(self):
        r = pyproject_inspect('[project]\nname = "x"\n')
        assert r["optional_dependency_groups"] == {}

    def test_scripts_populated(self):
        r = pyproject_inspect('[project]\n[project.scripts]\ncli = "pkg:main"\n')
        assert r["scripts"] == {"cli": "pkg:main"}

    def test_scripts_empty(self):
        r = pyproject_inspect('[project]\nname = "x"\n')
        assert r["scripts"] == {}

    def test_dynamic_populated(self):
        r = pyproject_inspect('[project]\ndynamic = ["version"]\n')
        assert r["dynamic"] == ["version"]

    def test_dynamic_empty(self):
        r = pyproject_inspect('[project]\nname = "x"\n')
        assert r["dynamic"] is None

    def test_entry_points_populated(self):
        r = pyproject_inspect('[project]\n[project.entry-points.my_plugin]\nhello = "mod:func"\n')
        assert r["entry_points"] == {"my_plugin": {"hello": "mod:func"}}

    def test_entry_points_empty(self):
        r = pyproject_inspect('[project]\nname = "x"\n')
        assert r["entry_points"] == {}

    def test_gui_scripts_populated(self):
        r = pyproject_inspect('[project]\n[project.gui-scripts]\napp = "pkg:run"\n')
        assert r["gui_scripts"] == {"app": "pkg:run"}

    def test_gui_scripts_empty(self):
        r = pyproject_inspect('[project]\nname = "x"\n')
        assert r["gui_scripts"] == {}

    def test_urls_populated(self):
        r = pyproject_inspect('[project]\n[project.urls]\nHome = "https://x.com"\n')
        assert r["urls"] == {"Home": "https://x.com"}

    def test_urls_empty(self):
        r = pyproject_inspect('[project]\nname = "x"\n')
        assert r["urls"] == {}

    def test_tool_sections_populated(self):
        r = pyproject_inspect('[tool.ruff]\nline-length = 88\n[tool.black]\nline-length = 88\n')
        assert r["tool_sections"] == ["tool.black", "tool.ruff"]

    def test_tool_sections_empty(self):
        r = pyproject_inspect('[project]\nname = "x"\n')
        assert r["tool_sections"] == []

    def test_pm_signals_populated(self):
        r = pyproject_inspect('[tool.poetry]\nname = "x"\n')
        assert r["package_manager_signals"] == ["poetry"]

    def test_pm_signals_empty(self):
        r = pyproject_inspect('[project]\nname = "x"\n')
        assert r["package_manager_signals"] == []


class TestPackageJsonFieldLevel:
    """Field-level assertions for package_json_inspect."""

    def test_name_populated(self):
        r = package_json_inspect('{"name": "x"}')
        assert r["name"] == "x"

    def test_name_empty(self):
        r = package_json_inspect("{}")
        assert r["name"] is None

    def test_version_populated(self):
        r = package_json_inspect('{"name": "x", "version": "1.0"}')
        assert r["version"] == "1.0"

    def test_version_empty(self):
        r = package_json_inspect("{}")
        assert r["version"] is None

    def test_private_populated(self):
        r = package_json_inspect('{"name": "x", "private": true}')
        assert r["private"] is True

    def test_private_empty(self):
        r = package_json_inspect("{}")
        assert r["private"] is None

    def test_package_type_populated(self):
        r = package_json_inspect('{"name": "x", "type": "module"}')
        assert r["package_type"] == "module"

    def test_package_type_empty(self):
        r = package_json_inspect("{}")
        assert r["package_type"] is None

    def test_scripts_keys_populated(self):
        r = package_json_inspect('{"name": "x", "scripts": {"build": "tsc", "test": "jest"}}')
        assert r["scripts_keys"] == ["build", "test"]

    def test_scripts_keys_empty(self):
        r = package_json_inspect("{}")
        assert r["scripts_keys"] == []

    def test_dependencies_count_populated(self):
        r = package_json_inspect('{"name": "x", "dependencies": {"a": "1.0", "b": "2.0"}}')
        assert r["dependencies_count"] == 2

    def test_dependencies_count_empty(self):
        r = package_json_inspect("{}")
        assert r["dependencies_count"] == 0

    def test_dev_dependencies_count_populated(self):
        r = package_json_inspect('{"name": "x", "devDependencies": {"a": "1.0"}}')
        assert r["dev_dependencies_count"] == 1

    def test_dev_dependencies_count_empty(self):
        r = package_json_inspect("{}")
        assert r["dev_dependencies_count"] == 0

    def test_peer_dependencies_count_populated(self):
        r = package_json_inspect('{"name": "x", "peerDependencies": {"a": "1.0"}}')
        assert r["peer_dependencies_count"] == 1

    def test_peer_dependencies_count_empty(self):
        r = package_json_inspect("{}")
        assert r["peer_dependencies_count"] == 0

    def test_optional_dependencies_count_populated(self):
        r = package_json_inspect('{"name": "x", "optionalDependencies": {"a": "1.0"}}')
        assert r["optional_dependencies_count"] == 1

    def test_optional_dependencies_count_empty(self):
        r = package_json_inspect("{}")
        assert r["optional_dependencies_count"] == 0

    def test_engines_populated(self):
        r = package_json_inspect('{"name": "x", "engines": {"node": ">=18"}}')
        assert r["engines"] == {"node": ">=18"}

    def test_engines_empty(self):
        r = package_json_inspect("{}")
        assert r["engines"] is None

    def test_package_manager_populated(self):
        r = package_json_inspect('{"name": "x", "packageManager": "yarn@3.5.0"}')
        assert r["package_manager"] == "yarn@3.5.0"

    def test_package_manager_empty(self):
        r = package_json_inspect("{}")
        assert r["package_manager"] is None

    def test_workspaces_populated_list(self):
        r = package_json_inspect('{"name": "x", "workspaces": ["packages/*"]}')
        assert r["workspaces"] == ["packages/*"]

    def test_workspaces_populated_object(self):
        r = package_json_inspect('{"name": "x", "workspaces": {"packages": ["a/*", "b/*"]}}')
        assert r["workspaces"] == ["a/*", "b/*"]

    def test_workspaces_empty(self):
        r = package_json_inspect("{}")
        assert r["workspaces"] is None


class TestRequirementsFieldLevel:
    """Field-level assertions for requirements_inspect."""

    def test_total_lines_populated(self):
        r = requirements_inspect("a\nb\nc\n")
        assert r["total_lines"] == 3

    def test_total_lines_empty(self):
        r = requirements_inspect("")
        assert r["total_lines"] == 0

    def test_package_specs_populated(self):
        r = requirements_inspect("requests\nflask\n")
        assert r["package_specs"] == ["requests", "flask"]

    def test_package_specs_empty(self):
        r = requirements_inspect("# just a comment\n")
        assert r["package_specs"] == []

    def test_editable_refs_populated(self):
        r = requirements_inspect("-e ./mypkg\n")
        assert r["editable_refs"] == ["-e ./mypkg"]

    def test_editable_refs_empty(self):
        r = requirements_inspect("requests\n")
        assert r["editable_refs"] == []

    def test_direct_urls_populated(self):
        r = requirements_inspect("pkg @ https://example.com/pkg.tar.gz\n")
        assert r["direct_urls"] == ["pkg @ https://example.com/pkg.tar.gz"]

    def test_direct_urls_empty(self):
        r = requirements_inspect("requests\n")
        assert r["direct_urls"] == []

    def test_vcs_refs_populated(self):
        r = requirements_inspect("git+https://github.com/x/y.git@main\n")
        assert len(r["vcs_refs"]) == 1

    def test_vcs_refs_empty(self):
        r = requirements_inspect("requests\n")
        assert r["vcs_refs"] == []

    def test_comments_populated(self):
        r = requirements_inspect("# comment\nrequests\n# another\n")
        assert len(r["comments"]) == 2

    def test_comments_empty(self):
        r = requirements_inspect("requests\n")
        assert r["comments"] == []

    def test_requirement_includes_populated(self):
        r = requirements_inspect("-r base.txt\n")
        assert r["requirement_includes"] == ["-r base.txt"]

    def test_requirement_includes_empty(self):
        r = requirements_inspect("requests\n")
        assert r["requirement_includes"] == []

    def test_constraints_includes_populated(self):
        r = requirements_inspect("-c constraints.txt\n")
        assert r["constraints_includes"] == ["-c constraints.txt"]

    def test_constraints_includes_empty(self):
        r = requirements_inspect("requests\n")
        assert r["constraints_includes"] == []

    def test_index_options_populated(self):
        r = requirements_inspect("-i https://pypi.org/simple\n")
        assert r["index_options"] == ["-i https://pypi.org/simple"]

    def test_index_options_empty(self):
        r = requirements_inspect("requests\n")
        assert r["index_options"] == []

    def test_hash_options_populated(self):
        r = requirements_inspect("--hash=sha256:abc\n")
        assert len(r["hash_options"]) >= 1

    def test_hash_options_empty(self):
        r = requirements_inspect("requests\n")
        assert r["hash_options"] == []

    def test_environment_markers_populated(self):
        r = requirements_inspect('pkg; sys_platform == "win32"\n')
        assert len(r["environment_markers"]) == 1

    def test_environment_markers_empty(self):
        r = requirements_inspect("requests\n")
        assert r["environment_markers"] == []

    def test_suspicious_lines_populated(self):
        r = requirements_inspect("`whoami`\n")
        assert r["suspicious_lines"] == ["`whoami`"]

    def test_suspicious_lines_empty(self):
        r = requirements_inspect("requests\n")
        assert r["suspicious_lines"] == []


class TestGoModFieldLevel:
    """Field-level assertions for go_mod_inspect."""

    def test_module_path_populated(self):
        r = go_mod_inspect("module foo\n")
        assert r["module_path"] == "foo"

    def test_module_path_empty(self):
        r = go_mod_inspect("go 1.22\n")
        assert r["module_path"] is None

    def test_go_version_populated(self):
        r = go_mod_inspect("go 1.22\n")
        assert r["go_version"] == "1.22"

    def test_go_version_empty(self):
        r = go_mod_inspect("module foo\n")
        assert r["go_version"] is None

    def test_toolchain_populated(self):
        r = go_mod_inspect("toolchain go1.22.1\n")
        assert r["toolchain"] == "go1.22.1"

    def test_toolchain_empty(self):
        r = go_mod_inspect("module foo\n")
        assert r["toolchain"] is None

    def test_require_count_populated(self):
        text = "module foo\nrequire (\n  a v1.0\n  b v2.0\n  c v3.0\n)\n"
        r = go_mod_inspect(text)
        assert r["require_count"] == 3

    def test_require_count_empty(self):
        r = go_mod_inspect("module foo\n")
        assert r["require_count"] == 0

    def test_replace_directives_populated(self):
        text = "replace foo => bar v1.0\n"
        r = go_mod_inspect(text)
        assert len(r["replace_directives"]) == 1

    def test_replace_directives_empty(self):
        r = go_mod_inspect("module foo\n")
        assert r["replace_directives"] == []

    def test_exclude_directives_populated(self):
        text = "exclude foo v0.1.0\n"
        r = go_mod_inspect(text)
        assert len(r["exclude_directives"]) == 1

    def test_exclude_directives_empty(self):
        r = go_mod_inspect("module foo\n")
        assert r["exclude_directives"] == []


class TestCargoFieldLevel:
    """Field-level assertions for cargo_toml_inspect."""

    def _cargo(self, text):
        return cargo_toml_inspect(text)

    def test_package_name_populated(self):
        r = self._cargo('[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n')
        assert r["package"]["name"] == "x"

    def test_package_name_empty(self):
        r = self._cargo("")
        assert r["package"].get("name") is None

    def test_package_version_populated(self):
        r = self._cargo('[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n')
        assert r["package"]["version"] == "1.0"

    def test_package_version_empty(self):
        r = self._cargo("")
        assert r["package"].get("version") is None

    def test_package_edition_populated(self):
        r = self._cargo('[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n')
        assert r["package"]["edition"] == "2021"

    def test_package_edition_empty(self):
        r = self._cargo('[package]\nname = "x"\nversion = "1.0"\n')
        assert r["package"].get("edition") is None

    def test_package_license_populated(self):
        r = self._cargo(
            '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\nlicense = "MIT"\n'
        )
        assert r["package"]["license"] == "MIT"

    def test_package_license_empty(self):
        r = self._cargo('[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n')
        assert r["package"].get("license") is None

    def test_package_repository_populated(self):
        r = self._cargo(
            '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\nrepository = "https://x.com"\n'
        )
        assert r["package"]["repository"] == "https://x.com"

    def test_package_repository_empty(self):
        r = self._cargo('[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n')
        assert r["package"].get("repository") is None

    def test_package_readme_populated(self):
        r = self._cargo(
            '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\nreadme = "README.md"\n'
        )
        assert r["package"]["readme"] == "README.md"

    def test_package_readme_empty(self):
        r = self._cargo('[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n')
        assert r["package"].get("readme") is None

    def test_workspace_present(self):
        r = self._cargo("[workspace]\nmembers = [\"a\"]\n")
        assert r["workspace"]["present"] is True

    def test_workspace_absent(self):
        r = self._cargo('[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n')
        assert r["workspace"]["present"] is False

    def test_workspace_members_populated(self):
        r = self._cargo("[workspace]\nmembers = [\"a\", \"b\"]\n")
        assert r["workspace"]["members"] == ["a", "b"]

    def test_workspace_members_empty(self):
        r = self._cargo('[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n')
        assert r["workspace"]["members"] == []

    def test_workspace_exclude_populated(self):
        r = self._cargo("[workspace]\nmembers = [\"a\"]\nexclude = [\"old\"]\n")
        assert r["workspace"]["exclude"] == ["old"]

    def test_workspace_exclude_empty(self):
        r = self._cargo("[workspace]\nmembers = [\"a\"]\n")
        assert r["workspace"]["exclude"] == []

    def test_path_dependencies_populated(self):
        r = self._cargo(
            '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n\n[dependencies]\nfoo = { path = "../foo" }\n'
        )
        assert r["path_dependencies"] == ["../foo"]

    def test_path_dependencies_empty(self):
        r = self._cargo(
            '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n\n[dependencies]\nfoo = "1.0"\n'
        )
        assert r["path_dependencies"] == []

    def test_suspicious_names_populated(self):
        r = self._cargo(
            '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n\n[dependencies]\n"0bad" = "1.0"\n'
        )
        assert "0bad" in r["suspicious_dependency_names"]

    def test_suspicious_names_empty(self):
        r = self._cargo(
            '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n\n[dependencies]\nserde = "1.0"\n'
        )
        assert r["suspicious_dependency_names"] == []

    def test_duplicate_names_populated(self):
        r = self._cargo(
            '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n\n[dependencies]\nmy_lib = "1.0"\nmy-lib = "2.0"\n'
        )
        assert len(r["duplicate_or_confusable_dependency_names"]) >= 2

    def test_duplicate_names_empty(self):
        r = self._cargo(
            '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n\n[dependencies]\nserde = "1.0"\ntokio = "1.0"\n'
        )
        assert r["duplicate_or_confusable_dependency_names"] == []


class TestLockfileFieldLevel:
    """Field-level assertions for lockfile_summary."""

    def test_detected_kind_populated(self):
        r = lockfile_summary("{}", kind="poetry-lock")
        assert r["detected_kind"] == "poetry-lock"

    def test_detected_kind_unknown(self):
        r = lockfile_summary("random")
        assert r["detected_kind"] == "unknown"

    def test_ecosystem_populated(self):
        r = lockfile_summary("{}", kind="cargo-lock")
        assert r["ecosystem"] == "cargo"

    def test_ecosystem_none(self):
        r = lockfile_summary("random")
        assert r["ecosystem"] is None

    def test_approx_count_populated(self):
        text = (
            '[metadata]\nlock-version = "2.1"\n\n[[package]]\nname = "a"\n[[package]]\nname = "b"\n'
        )
        r = lockfile_summary(text)
        assert r["approximate_package_count"] == 2

    def test_approx_count_zero(self):
        r = lockfile_summary("{}", kind="cargo-lock")
        assert r["approximate_package_count"] == 0

    def test_warnings_populated(self):
        r = lockfile_summary("random text")
        assert len(r["warnings"]) >= 1

    def test_warnings_empty(self):
        text = '{"lockfileVersion": 3, "packages": {}}'
        r = lockfile_summary(text)
        assert r["warnings"] == []


# ========================================================================
# Workstream F: Negative and boundary tests
# ========================================================================


class TestNegativeBoundary:
    """Non-string input, empty input, and size limits."""

    def test_pyproject_non_string_int(self):
        r = pyproject_inspect(123)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INVALID_INPUT" for f in r["findings"])

    def test_pyproject_non_string_list(self):
        r = pyproject_inspect([1, 2, 3])
        assert r["parse_ok"] is False
        assert any(f["code"] == "INVALID_INPUT" for f in r["findings"])

    def test_pyproject_non_string_none(self):
        r = pyproject_inspect(None)
        assert r["parse_ok"] is False

    def test_pyproject_non_string_dict(self):
        r = pyproject_inspect({})
        assert r["parse_ok"] is False

    def test_package_json_non_string_int(self):
        r = package_json_inspect(42)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INVALID_INPUT" for f in r["findings"])

    def test_package_json_non_string_none(self):
        r = package_json_inspect(None)
        assert r["parse_ok"] is False

    def test_requirements_non_string_int(self):
        r = requirements_inspect(3.14)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INVALID_INPUT" for f in r["findings"])

    def test_requirements_non_string_bytes(self):
        r = requirements_inspect(b"requests")
        assert r["parse_ok"] is False

    def test_go_mod_non_string_int(self):
        r = go_mod_inspect(99)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INVALID_INPUT" for f in r["findings"])

    def test_go_mod_non_string_bool(self):
        r = go_mod_inspect(True)
        assert r["parse_ok"] is False

    def test_lockfile_non_string_int(self):
        r = lockfile_summary(123)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INVALID_INPUT" for f in r["findings"])

    def test_lockfile_non_string_list(self):
        r = lockfile_summary([])
        assert r["parse_ok"] is False

    def test_cargo_non_string_int(self):
        with pytest.raises(TypeError):
            cargo_toml_inspect(42)

    def test_cargo_non_string_none(self):
        with pytest.raises(TypeError):
            cargo_toml_inspect(None)

    def test_pyproject_empty_input(self):
        r = pyproject_inspect("")
        assert r["parse_ok"] is True
        assert r["project_name"] is None
        assert any(f["code"] == "MISSING_PROJECT_NAME" for f in r["findings"])

    def test_package_json_empty_input(self):
        r = package_json_inspect("")
        assert r["parse_ok"] is False

    def test_requirements_empty_input(self):
        r = requirements_inspect("")
        assert r["parse_ok"] is True
        assert r["total_lines"] == 0
        assert r["package_specs"] == []

    def test_go_mod_empty_input(self):
        r = go_mod_inspect("")
        assert r["parse_ok"] is True
        assert r["require_count"] == 0

    def test_lockfile_empty_input(self):
        r = lockfile_summary("")
        assert r["parse_ok"] is True

    def test_cargo_empty_input(self):
        r = cargo_toml_inspect("")
        assert r["parse_ok"] is True

    def test_pyproject_at_size_limit(self):
        text = "a" * _MAX_INPUT_LENGTH
        r = pyproject_inspect(text)
        assert r["parse_ok"] is False
        assert not any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_pyproject_over_size_limit(self):
        text = "a" * (_MAX_INPUT_LENGTH + 1)
        r = pyproject_inspect(text)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_package_json_at_size_limit(self):
        text = "a" * _MAX_INPUT_LENGTH
        r = package_json_inspect(text)
        assert r["parse_ok"] is False
        assert not any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_package_json_over_size_limit(self):
        text = "a" * (_MAX_INPUT_LENGTH + 1)
        r = package_json_inspect(text)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_requirements_at_size_limit(self):
        text = "a" * _MAX_INPUT_LENGTH
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert not any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_requirements_over_size_limit(self):
        text = "a" * (_MAX_INPUT_LENGTH + 1)
        r = requirements_inspect(text)
        assert r["parse_ok"] is False

    def test_go_mod_at_size_limit(self):
        text = "a" * _MAX_INPUT_LENGTH
        r = go_mod_inspect(text)
        assert r["parse_ok"] is True
        assert not any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_go_mod_over_size_limit(self):
        text = "a" * (_MAX_INPUT_LENGTH + 1)
        r = go_mod_inspect(text)
        assert r["parse_ok"] is False

    def test_lockfile_at_size_limit(self):
        text = "a" * _MAX_INPUT_LENGTH
        r = lockfile_summary(text)
        assert r["parse_ok"] is True
        assert not any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_lockfile_over_size_limit(self):
        text = "a" * (_MAX_INPUT_LENGTH + 1)
        r = lockfile_summary(text)
        assert r["parse_ok"] is False

    def test_cargo_at_size_limit(self):
        text = "a" * _CARGO_MAX_INPUT_LENGTH
        r = cargo_toml_inspect(text)
        assert r["parse_ok"] is False
        assert not any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_cargo_over_size_limit(self):
        text = "a" * (_CARGO_MAX_INPUT_LENGTH + 1)
        r = cargo_toml_inspect(text)
        assert r["parse_ok"] is False

    def test_cargo_just_under_limit(self):
        text = '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n'
        padding = " " * (_CARGO_MAX_INPUT_LENGTH - len(text))
        r = cargo_toml_inspect(text + padding)
        assert r["parse_ok"] is True

    def test_pyproject_just_under_limit(self):
        text = '[project]\nname = "x"\n'
        padding = "\n#" + " " * (_MAX_INPUT_LENGTH - len(text) - 2)
        r = pyproject_inspect(text + padding)
        assert r["parse_ok"] is True


# ========================================================================
# Workstream F: Invariant tests
# ========================================================================


class TestInvariants:
    """Structural invariants that must hold for all inspectors."""

    def test_parse_ok_false_implies_error_finding_pyproject(self):
        r = pyproject_inspect("not valid {{{")
        assert r["parse_ok"] is False
        assert any(f["severity"] == "error" for f in r["findings"])

    def test_parse_ok_false_implies_error_finding_package_json(self):
        r = package_json_inspect("{broken")
        assert r["parse_ok"] is False
        assert any(f["severity"] == "error" for f in r["findings"])

    def test_parse_ok_false_implies_error_finding_cargo(self):
        r = cargo_toml_inspect("[package\nbroken")
        assert r["parse_ok"] is False
        assert any(f["severity"] == "error" for f in r["findings"])

    def test_finding_severity_valid_values(self):
        """All findings must have severity in {error, warning, info}."""
        valid = {"error", "warning", "info"}
        for inspector, text in [
            (pyproject_inspect, '[tool.x]\na = 1\n'),
            (package_json_inspect, '{"name": "x"}'),
            (requirements_inspect, "requests\n"),
            (go_mod_inspect, "module foo\ngo 1.22\n"),
            (cargo_toml_inspect, '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n'),
        ]:
            r = inspector(text)
            for f in r.get("findings", []):
                assert f["severity"] in valid, f"Invalid severity: {f['severity']}"

    def test_pyproject_tool_sections_sorted_unique(self):
        r = pyproject_inspect('[tool.b]\na = 1\n[tool.c]\na = 1\n[tool.a]\na = 1\n')
        assert r["tool_sections"] == sorted(r["tool_sections"])
        assert len(r["tool_sections"]) == len(set(r["tool_sections"]))

    def test_pyproject_pm_signals_sorted_unique(self):
        r = pyproject_inspect(
            '[tool.poetry]\nname = "x"\n[tool.pdm]\nname = "y"\n[tool.hatch]\nname = "z"\n'
        )
        assert len(r["package_manager_signals"]) == len(set(r["package_manager_signals"]))

    def test_findings_json_serializable_pyproject(self):
        r = pyproject_inspect('[tool.x]\na = 1\n')
        json.dumps(r["findings"])

    def test_findings_json_serializable_package_json(self):
        r = package_json_inspect('{"name": "x"}')
        json.dumps(r["findings"])

    def test_findings_json_serializable_requirements(self):
        r = requirements_inspect("requests\n")
        json.dumps(r["findings"])

    def test_findings_json_serializable_go_mod(self):
        r = go_mod_inspect("module foo\n")
        json.dumps(r["findings"])

    def test_findings_json_serializable_cargo(self):
        r = cargo_toml_inspect('[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n')
        json.dumps(r["findings"])

    def test_findings_json_serializable_lockfile(self):
        r = lockfile_summary("{}", kind="cargo-lock")
        json.dumps(r["findings"])

    def test_result_json_serializable_pyproject(self):
        r = pyproject_inspect('[project]\nname = "x"\nversion = "1.0"\n')
        json.dumps(r)

    def test_result_json_serializable_package_json(self):
        r = package_json_inspect('{"name": "x", "version": "1.0"}')
        json.dumps(r)

    def test_result_json_serializable_requirements(self):
        r = requirements_inspect("requests\nflask\n")
        json.dumps(r)

    def test_result_json_serializable_go_mod(self):
        r = go_mod_inspect("module foo\ngo 1.22\n")
        json.dumps(r)

    def test_result_json_serializable_cargo(self):
        r = cargo_toml_inspect('[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n')
        json.dumps(r)

    def test_result_json_serializable_lockfile(self):
        r = lockfile_summary("{}", kind="cargo-lock")
        json.dumps(r)

    def test_finding_truncation(self):
        """Generating >200 findings triggers truncation."""
        lines = []
        for i in range(210):
            lines.append(f"pkg_{i}`whoami`")
        text = "\n".join(lines)
        r = requirements_inspect(text)
        assert len(r["findings"]) <= _MAX_FINDINGS + 1
        assert any(f["code"] == "FINDINGS_TRUNCATED" for f in r["findings"])

    def test_finding_truncation_preserves_first_n(self):
        lines = []
        for i in range(210):
            lines.append(f"pkg_{i}`whoami`")
        text = "\n".join(lines)
        r = requirements_inspect(text)
        truncation = [f for f in r["findings"] if f["code"] == "FINDINGS_TRUNCATED"]
        assert len(truncation) == 1
        assert "210" in truncation[0]["message"]


# ========================================================================
# Workstream F: Security/adversarial tests
# ========================================================================


class TestSecurityAdversarial:
    """Adversarial and security-focused tests."""

    def test_long_extras_list(self):
        extras = ",".join(f"extra{i}" for i in range(200))
        text = f"pkg[{extras}]>=1.0\n"
        r = requirements_inspect(text)
        assert r["parse_ok"] is True

    def test_long_marker_expression(self):
        markers = " and ".join('os_name == "posix"' for _ in range(50))
        text = f"pkg; {markers}\n"
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["environment_markers"]) == 1

    def test_repeated_separators(self):
        text = "----------\n" * 100
        r = requirements_inspect(text)
        assert r["parse_ok"] is True

    def test_many_malformed_lines(self):
        lines = [f"line{i}(" for i in range(100)]
        text = "\n".join(lines)
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["suspicious_lines"]) > 0

    def test_unicode_confusable_in_requirements(self):
        text = "requests\nrеquеsts\nрequеsts\n"
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["package_specs"]) == 3

    def test_shell_backtick(self):
        r = requirements_inspect("`whoami`\n")
        assert r["parse_ok"] is True
        assert len(r["suspicious_lines"]) == 1

    def test_shell_dollar_paren(self):
        r = requirements_inspect("$(whoami)\n")
        assert r["parse_ok"] is True
        assert len(r["suspicious_lines"]) == 1

    def test_shell_dollar_brace(self):
        r = requirements_inspect("${HOME}\n")
        assert r["parse_ok"] is True
        assert len(r["suspicious_lines"]) == 1

    def test_unbalanced_parens(self):
        r = requirements_inspect("pkg(a\n")
        assert r["parse_ok"] is True
        assert len(r["suspicious_lines"]) == 1

    def test_unbalanced_brackets(self):
        r = requirements_inspect("pkg[a\n")
        assert r["parse_ok"] is True
        assert len(r["suspicious_lines"]) == 1

    def test_unbalanced_braces(self):
        r = requirements_inspect("pkg{a\n")
        assert r["parse_ok"] is True
        assert len(r["suspicious_lines"]) == 1

    def test_control_character(self):
        r = requirements_inspect("pkg\x01bad\n")
        assert r["parse_ok"] is True
        assert len(r["suspicious_lines"]) == 1

    def test_long_vcs_line(self):
        url = "a" * 10_000
        text = f"git+https://{url}.git@main\n"
        r = requirements_inspect(text)
        assert r["parse_ok"] is True

    def test_cargo_confusable_unicode_name(self):
        text = (
            '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n\n'
            '[dependencies]\nserde = "1.0"\n"serd\u0435" = "2.0"\n'
        )
        r = cargo_toml_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["suspicious_dependency_names"]) >= 1

    def test_cargo_suspicious_starting_with_digit(self):
        text = (
            '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n\n'
            '[dependencies]\n0package = "1.0"\n'
        )
        r = cargo_toml_inspect(text)
        assert "0package" in r["suspicious_dependency_names"]

    def test_cargo_suspicious_double_hyphen(self):
        text = (
            '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n\n'
            '[dependencies]\nmy--lib = "1.0"\n'
        )
        r = cargo_toml_inspect(text)
        assert "my--lib" in r["suspicious_dependency_names"]

    def test_cargo_suspicious_dot(self):
        text = (
            '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n\n'
            '[dependencies]\n"my.lib" = "1.0"\n'
        )
        r = cargo_toml_inspect(text)
        assert "my.lib" in r["suspicious_dependency_names"]

    def test_pyproject_many_tool_sections(self):
        sections = "".join(f"[tool.tool{i}]\nkey = 1\n" for i in range(100))
        r = pyproject_inspect(sections)
        assert r["parse_ok"] is True
        assert len(r["tool_sections"]) == 100
        assert r["tool_sections"] == sorted(r["tool_sections"])

    def test_go_mod_many_replaces(self):
        lines = ["module foo\ngo 1.22\n"]
        for i in range(50):
            lines.append(f"replace pkg{i} => other{i} v{i}.0")
        text = "\n".join(lines)
        r = go_mod_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["replace_directives"]) == 50


# ========================================================================
# Workstream G: Resource bounds
# ========================================================================


class TestResourceBounds:
    """Resource bounds enforcement tests."""

    def test_pyproject_rejects_over_limit_before_parse(self):
        text = "a" * (_MAX_INPUT_LENGTH + 1)
        r = pyproject_inspect(text)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_package_json_rejects_over_limit_before_parse(self):
        text = "a" * (_MAX_INPUT_LENGTH + 1)
        r = package_json_inspect(text)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_requirements_rejects_over_limit_before_parse(self):
        text = "a" * (_MAX_INPUT_LENGTH + 1)
        r = requirements_inspect(text)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_go_mod_rejects_over_limit_before_parse(self):
        text = "a" * (_MAX_INPUT_LENGTH + 1)
        r = go_mod_inspect(text)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_lockfile_rejects_over_limit_before_parse(self):
        text = "a" * (_MAX_INPUT_LENGTH + 1)
        r = lockfile_summary(text)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_cargo_rejects_over_limit_before_parse(self):
        text = "a" * (_CARGO_MAX_INPUT_LENGTH + 1)
        r = cargo_toml_inspect(text)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INPUT_TOO_LONG" for f in r["findings"])

    def test_cargo_accepts_at_limit(self):
        base = '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n'
        # Pad to exactly the limit
        padding = " " * (_CARGO_MAX_INPUT_LENGTH - len(base))
        r = cargo_toml_inspect(base + padding)
        assert r["parse_ok"] is True

    def test_pyproject_accepts_at_limit(self):
        base = '[project]\nname = "x"\n'
        padding = "\n#" + " " * (_MAX_INPUT_LENGTH - len(base) - 2)
        r = pyproject_inspect(base + padding)
        assert r["parse_ok"] is True

    def test_finding_count_capped_at_max_findings(self):
        """Even pathological input can't produce more than _MAX_FINDINGS + 1 findings."""
        lines = []
        for i in range(300):
            lines.append(f"evil_{i}; rm -rf /")
        text = "\n".join(lines)
        r = requirements_inspect(text)
        assert len(r["findings"]) <= _MAX_FINDINGS + 1

    def test_mcp_result_json_serializable_pyproject(self):
        from eggcalc.mcp.tools import pyproject_inspect_mcp

        r = pyproject_inspect_mcp('[project]\nname = "x"\nversion = "1.0"\n')
        json.dumps(r)

    def test_mcp_result_json_serializable_package_json(self):
        from eggcalc.mcp.tools import package_json_inspect_mcp

        r = package_json_inspect_mcp('{"name": "x", "version": "1.0"}')
        json.dumps(r)

    def test_mcp_result_json_serializable_requirements(self):
        from eggcalc.mcp.tools import requirements_inspect_mcp

        r = requirements_inspect_mcp("requests\n")
        json.dumps(r)

    def test_mcp_result_json_serializable_go_mod(self):
        from eggcalc.mcp.tools import go_mod_inspect_mcp

        r = go_mod_inspect_mcp("module foo\ngo 1.22\n")
        json.dumps(r)

    def test_mcp_result_json_serializable_lockfile(self):
        from eggcalc.mcp.tools import lockfile_summary_mcp

        r = lockfile_summary_mcp("{}", kind="cargo-lock")
        json.dumps(r)

    def test_mcp_result_json_serializable_cargo(self):
        from eggcalc.mcp.tools import cargo_toml_inspect_mcp

        r = cargo_toml_inspect_mcp('[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n')
        json.dumps(r)

    def test_mcp_wrapper_equals_primitive_pyproject(self):
        from eggcalc.mcp.tools import pyproject_inspect_mcp

        text = '[project]\nname = "x"\nversion = "1.0"\n'
        mcp = pyproject_inspect_mcp(text)
        prim = pyproject_inspect(text)
        assert mcp["result"] == prim

    def test_mcp_wrapper_equals_primitive_package_json(self):
        from eggcalc.mcp.tools import package_json_inspect_mcp

        text = '{"name": "x", "version": "1.0"}'
        mcp = package_json_inspect_mcp(text)
        prim = package_json_inspect(text)
        assert mcp["result"] == prim

    def test_mcp_wrapper_equals_primitive_requirements(self):
        from eggcalc.mcp.tools import requirements_inspect_mcp

        text = "requests\n"
        mcp = requirements_inspect_mcp(text)
        prim = requirements_inspect(text)
        assert mcp["result"] == prim

    def test_mcp_wrapper_equals_primitive_go_mod(self):
        from eggcalc.mcp.tools import go_mod_inspect_mcp

        text = "module foo\ngo 1.22\n"
        mcp = go_mod_inspect_mcp(text)
        prim = go_mod_inspect(text)
        assert mcp["result"] == prim

    def test_mcp_wrapper_equals_primitive_lockfile(self):
        from eggcalc.mcp.tools import lockfile_summary_mcp

        text = "{}"
        mcp = lockfile_summary_mcp(text, kind="cargo-lock")
        prim = lockfile_summary(text, kind="cargo-lock")
        assert mcp["result"] == prim

    def test_mcp_wrapper_equals_primitive_cargo(self):
        from eggcalc.mcp.tools import cargo_toml_inspect_mcp

        text = '[package]\nname = "x"\nversion = "1.0"\nedition = "2021"\n'
        mcp = cargo_toml_inspect_mcp(text)
        prim = cargo_toml_inspect(text)
        assert mcp["result"] == prim
