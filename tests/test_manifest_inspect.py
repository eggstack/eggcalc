"""Tests for manifest/package inspection tools."""

from __future__ import annotations

import sys

import pytest

from eggcalc.exact.manifests import (
    go_mod_inspect,
    lockfile_summary,
    package_json_inspect,
    pyproject_inspect,
    requirements_inspect,
)

_needs_tomllib = pytest.mark.skipif(
    sys.version_info < (3, 11), reason="tomllib requires Python 3.11+"
)

# ---------------------------------------------------------------------------
# pyproject_inspect
# ---------------------------------------------------------------------------


@_needs_tomllib
class TestPyprojectInspect:
    def test_basic_pyproject(self):
        text = """
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "my-package"
version = "1.2.3"
requires-python = ">=3.10"
dependencies = ["requests>=2.0", "click"]

[project.optional-dependencies]
dev = ["pytest", "ruff"]
docs = ["sphinx"]
"""
        r = pyproject_inspect(text)
        assert r["parse_ok"] is True
        assert r["project_name"] == "my-package"
        assert r["project_version"] == "1.2.3"
        assert r["requires_python"] == ">=3.10"
        assert r["dependencies_count"] == 2
        assert r["optional_dependency_groups"] == {"dev": 2, "docs": 1}

    def test_poetry_signal(self):
        text = """
[tool.poetry]
name = "poetry-demo"
version = "0.1.0"
"""
        r = pyproject_inspect(text)
        assert r["parse_ok"] is True
        assert "poetry" in r["package_manager_signals"]

    def test_invalid_toml(self):
        r = pyproject_inspect("this is not [valid toml {{{")
        assert r["parse_ok"] is False
        assert any(f["code"] == "TOML_PARSE_ERROR" for f in r.get("findings", []))

    def test_empty_input(self):
        r = pyproject_inspect("")
        assert r["parse_ok"] is True
        assert r["project_name"] is None
        assert r["dependencies_count"] == 0

    def test_input_too_long(self):
        r = pyproject_inspect("a" * 600_000)
        assert r["parse_ok"] is False
        assert any(f["code"] == "INPUT_TOO_LONG" for f in r.get("findings", []))


# ---------------------------------------------------------------------------
# package_json_inspect
# ---------------------------------------------------------------------------


class TestPackageJsonInspect:
    def test_basic_package_json(self):
        text = """{
  "name": "my-app",
  "version": "2.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "node server.js",
    "test": "jest",
    "build": "webpack"
  },
  "dependencies": {"express": "^4.18.0"},
  "devDependencies": {"jest": "^29.0.0", "webpack": "^5.0.0"},
  "engines": {"node": ">=18"},
  "workspaces": ["packages/*"]
}"""
        r = package_json_inspect(text)
        assert r["parse_ok"] is True
        assert r["name"] == "my-app"
        assert r["version"] == "2.0.0"
        assert r["private"] is True
        assert r["package_type"] == "module"
        assert sorted(r["scripts_keys"]) == ["build", "start", "test"]
        assert r["dependencies_count"] == 1
        assert r["dev_dependencies_count"] == 2
        assert r["engines"] == {"node": ">=18"}
        assert r["workspaces"] == ["packages/*"]

    def test_invalid_json(self):
        r = package_json_inspect("{not valid json")
        assert r["parse_ok"] is False
        assert any(f["code"] == "JSON_PARSE_ERROR" for f in r.get("findings", []))

    def test_root_not_object(self):
        r = package_json_inspect('"just a string"')
        assert r["parse_ok"] is False

    def test_empty_object(self):
        r = package_json_inspect("{}")
        assert r["parse_ok"] is True
        assert r["name"] is None
        assert r["dependencies_count"] == 0


# ---------------------------------------------------------------------------
# requirements_inspect
# ---------------------------------------------------------------------------


class TestRequirementsInspect:
    def test_basic_requirements(self):
        text = """# Core dependencies
requests>=2.28
click
-r other-requirements.txt

# Dev
pytest
-e ./my-package

# VCS
git+https://github.com/user/repo.git@main
"""
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert "requests>=2.28" in r["package_specs"]
        assert "click" in r["package_specs"]
        assert any("-r" in e for e in r["requirement_includes"])
        assert any("-e" in e for e in r["editable_refs"])
        assert any("git+" in v for v in r["vcs_refs"])

    def test_environment_markers(self):
        text = 'pywin32>=1.0; sys_platform == "win32"\n'
        r = requirements_inspect(text)
        assert r["parse_ok"] is True
        assert len(r["environment_markers"]) == 1

    def test_empty_requirements(self):
        r = requirements_inspect("")
        assert r["parse_ok"] is True
        assert r["total_lines"] == 0
        assert r["package_specs"] == []


# ---------------------------------------------------------------------------
# go_mod_inspect
# ---------------------------------------------------------------------------


class TestGoModInspect:
    def test_basic_go_mod(self):
        text = """module github.com/example/project

go 1.22

toolchain go1.22.1

require (
    github.com/gin-gonic/gin v1.9.1
    golang.org/x/sync v0.6.0
)

replace (
    github.com/foo/bar => ../bar
)

exclude github.com/baz/qux v0.1.0
"""
        r = go_mod_inspect(text)
        assert r["parse_ok"] is True
        assert r["module_path"] == "github.com/example/project"
        assert r["go_version"] == "1.22"
        assert r["toolchain"] == "go1.22.1"
        assert r["require_count"] == 2
        assert len(r["replace_directives"]) == 1
        assert len(r["exclude_directives"]) == 1

    def test_missing_module(self):
        r = go_mod_inspect("go 1.22\n")
        assert r["parse_ok"] is True
        assert r["module_path"] is None
        assert any(f["code"] == "MISSING_MODULE" for f in r.get("findings", []))

    def test_empty_gomod(self):
        r = go_mod_inspect("")
        assert r["parse_ok"] is True
        assert r["require_count"] == 0


# ---------------------------------------------------------------------------
# lockfile_summary
# ---------------------------------------------------------------------------


class TestLockfileSummary:
    def test_package_lock(self):
        text = """{
  "name": "my-app",
  "lockfileVersion": 3,
  "packages": {
    "": {"name": "my-app"},
    "node_modules/express": {"version": "4.18.0"}
  }
}"""
        r = lockfile_summary(text)
        assert r["parse_ok"] is True
        assert r["detected_kind"] == "package-lock"
        assert r["ecosystem"] == "npm"
        assert r["approximate_package_count"] == 2

    def test_poetry_lock(self):
        text = """[metadata]
lock-version = "2.1"
python-versions = "^3.10"

[[package]]
name = "requests"
version = "2.31.0"

[[package]]
name = "click"
version = "8.1.7"
"""
        r = lockfile_summary(text)
        assert r["parse_ok"] is True
        assert r["detected_kind"] == "poetry-lock"
        assert r["ecosystem"] == "poetry"
        assert r["approximate_package_count"] == 2

    def test_explicit_kind(self):
        r = lockfile_summary("anything", kind="cargo-lock")
        assert r["detected_kind"] == "cargo-lock"
        assert r["ecosystem"] == "cargo"

    def test_unknown_lockfile(self):
        r = lockfile_summary("some random text")
        assert r["parse_ok"] is True
        assert r["detected_kind"] == "unknown"

    def test_invalid_input(self):
        r = lockfile_summary(123)
        assert r["parse_ok"] is False


# ---------------------------------------------------------------------------
# MCP wrapper integration
# ---------------------------------------------------------------------------


class TestManifestMCPWrappers:
    """Verify MCP wrappers return proper success envelopes."""

    @_needs_tomllib
    def test_pyproject_inspect_mcp(self):
        from eggcalc.mcp.tools import pyproject_inspect_mcp

        r = pyproject_inspect_mcp("[project]\nname = 'test'\n")
        assert r["ok"] is True
        assert r["result"]["parse_ok"] is True

    def test_package_json_inspect_mcp(self):
        from eggcalc.mcp.tools import package_json_inspect_mcp

        r = package_json_inspect_mcp('{"name": "test"}')
        assert r["ok"] is True

    def test_requirements_inspect_mcp(self):
        from eggcalc.mcp.tools import requirements_inspect_mcp

        r = requirements_inspect_mcp("requests>=2.0\n")
        assert r["ok"] is True

    def test_go_mod_inspect_mcp(self):
        from eggcalc.mcp.tools import go_mod_inspect_mcp

        r = go_mod_inspect_mcp("module test\ngo 1.22\n")
        assert r["ok"] is True

    def test_lockfile_summary_mcp(self):
        from eggcalc.mcp.tools import lockfile_summary_mcp

        r = lockfile_summary_mcp("{}", kind="auto")
        assert r["ok"] is True

    def test_lockfile_summary_invalid_kind(self):
        from eggcalc.mcp.tools import lockfile_summary_mcp

        r = lockfile_summary_mcp("{}", kind="invalid")
        assert r["ok"] is False

    def test_non_string_input(self):
        from eggcalc.mcp.tools import pyproject_inspect_mcp

        r = pyproject_inspect_mcp(123)
        assert r["ok"] is False
