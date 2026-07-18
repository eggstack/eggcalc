"""Tests for cargo_toml_inspect (Phase 12).

Tests for:
- Basic package metadata extraction
- Workspace members
- Path dependencies
- Git dependencies
- Missing edition
- Confusable or duplicate dependency names
- MCP wrapper integration
- Invalid TOML input
"""

import json

from eggcalc.exact.cargo import (
    _detect_duplicates,
    _normalize_ident,
    cargo_toml_inspect,
)
from eggcalc.exact.manifests import pyproject_inspect, requirements_inspect
from eggcalc.mcp.tools import cargo_toml_inspect_mcp

BASIC_CARGO_TOML = """\
[package]
name = "my-crate"
version = "0.1.0"
edition = "2021"
license = "MIT"
repository = "https://github.com/example/my-crate"
readme = "README.md"
"""

MINIMAL_CARGO_TOML = """\
[package]
name = "minimal"
version = "1.0.0"
edition = "2021"
"""

WORKSPACE_CARGO_TOML = """\
[workspace]
members = [
    "crates/core",
    "crates/cli",
    "crates/utils",
]
exclude = ["old-crate"]
"""

DEPENDENCY_CARGO_TOML = """\
[package]
name = "dep-test"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = "1.0"
tokio = { version = "1.0", features = ["full"] }

[dev-dependencies]
assert_cmd = "2.0"

[build-dependencies]
cc = "1.0"
"""

PATH_DEP_CARGO_TOML = """\
[package]
name = "path-test"
version = "0.1.0"
edition = "2021"

[dependencies]
my-lib = { path = "../my-lib", version = "0.1.0" }
utils = { path = "crates/utils" }
"""

GIT_DEP_CARGO_TOML = """\
[package]
name = "git-test"
version = "0.1.0"
edition = "2021"

[dependencies]
external = { git = "https://github.com/example/repo", branch = "main" }
pinned = { git = "https://github.com/example/other", tag = "v1.0" }
"""

MISSING_EDITION_TOML = """\
[package]
name = "no-edition"
version = "0.1.0"
"""

CONFUSABLE_DEPS_TOML = """\
[package]
name = "confusable-test"
version = "0.1.0"
edition = "2021"

[dependencies]
my_lib = "1.0"
my-lib = "2.0"
"""

SUSPICIOUS_DEPS_TOML = """\
[package]
name = "suspicious-test"
version = "0.1.0"
edition = "2021"

[dependencies]
0bad = "1.0"
"has spaces" = "2.0"
double__underscore = "3.0"
"""

TARGET_SPECIFIC_TOML = """\
[package]
name = "target-test"
version = "0.1.0"
edition = "2021"

[target.'cfg(unix)'.dependencies]
nix = "0.27"

[target.'cfg(windows)'.dependencies]
winapi = { version = "0.3", features = ["winuser"] }
"""

EMPTY_TOML = """\
"""

INVALID_TOML = """\
[package
name = broken
"""

WORKSPACE_DEPS_TOML = """\
[package]
name = "workspace-dep-test"
version = "0.1.0"
edition = "2021"

[dependencies]
common = { workspace = true }
serde = { version = "1.0", workspace = true }
"""

VIRTUAL_WORKSPACE_TOML = """\
[workspace]
members = [
    "crates/core",
    "crates/cli",
]
"""

EMPTY_VIRTUAL_WORKSPACE_TOML = """\
"""

CYRILLIC_CARGO_TOML = """
[package]
name = "привет"
version = "0.1.0"
edition = "2021"

[dependencies]
"кириллица" = "1.0"
"""

GREEK_CARGO_TOML = """
[package]
name = "myapp"
version = "0.1.0"
edition = "2021"

[dependencies]
"αλφα" = "1.0"
"""

MIXED_SCRIPT_CARGO_TOML = """
[package]
name = "myapp"
version = "0.1.0"
edition = "2021"

[dependencies]
"привет_lib" = "1.0"
"""

CONFUSABLE_COLLISION_TOML = """
[package]
name = "myapp"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = "1.0"
"ＳＥＲＤＥ" = "1.0"
"""

RENAMED_DEPENDENCY_TOML = """
[package]
name = "myapp"
version = "0.1.0"
edition = "2021"

[dependencies]
my_dep = { package = "original-name", version = "1.0" }
"""

UPPERCASE_CARGO_TOML = """
[package]
name = "myapp"
version = "0.1.0"
edition = "2021"

[dependencies]
Serde = "1.0"
Tokio = "1.0"
"""

HYPHEN_UNDERSCORE_TOML = """
[package]
name = "myapp"
version = "0.1.0"
edition = "2021"

[dependencies]
my-lib = "1.0"
my_lib = "1.0"
"""


class TestNormalizeIdent:
    """Tests for identifier normalization."""

    def test_basic_lowercase(self):
        assert _normalize_ident("hello") == "hello"

    def test_case_insensitive(self):
        assert _normalize_ident("Hello") == "hello"

    def test_hyphen_to_underscore(self):
        assert _normalize_ident("my-crate") == "my_crate"

    def test_underscore_to_single(self):
        assert _normalize_ident("my__crate") == "my_crate"

    def test_dot_to_underscore(self):
        assert _normalize_ident("my.crate") == "my_crate"

    def test_unicode_nfkc(self):
        assert _normalize_ident("café") == "caf\u00e9"


class TestDetectDuplicates:
    """Tests for duplicate/confusable dependency detection."""

    def test_no_duplicates(self):
        assert _detect_duplicates(["serde", "tokio"]) == []

    def test_exact_duplicate(self):
        result = _detect_duplicates(["serde", "serde"])
        assert result == ["serde"]

    def test_confusable_hyphen_underscore(self):
        result = _detect_duplicates(["my_lib", "my-lib"])
        assert result == ["my-lib", "my_lib"]

    def test_case_confusable(self):
        result = _detect_duplicates(["Serde", "serde"])
        assert result == ["Serde", "serde"]


class TestCargoTomlInspectBasic:
    """Tests for basic package metadata extraction."""

    def test_parse_ok(self):
        result = cargo_toml_inspect(BASIC_CARGO_TOML)
        assert result["parse_ok"] is True

    def test_package_name(self):
        result = cargo_toml_inspect(BASIC_CARGO_TOML)
        assert result["package"]["name"] == "my-crate"

    def test_package_version(self):
        result = cargo_toml_inspect(BASIC_CARGO_TOML)
        assert result["package"]["version"] == "0.1.0"

    def test_package_edition(self):
        result = cargo_toml_inspect(BASIC_CARGO_TOML)
        assert result["package"]["edition"] == "2021"

    def test_package_license(self):
        result = cargo_toml_inspect(BASIC_CARGO_TOML)
        assert result["package"]["license"] == "MIT"

    def test_package_repository(self):
        result = cargo_toml_inspect(BASIC_CARGO_TOML)
        assert result["package"]["repository"] == "https://github.com/example/my-crate"

    def test_package_readme(self):
        result = cargo_toml_inspect(BASIC_CARGO_TOML)
        assert result["package"]["readme"] == "README.md"

    def test_no_findings(self):
        result = cargo_toml_inspect(BASIC_CARGO_TOML)
        assert result["findings"] == []


class TestCargoTomlInspectMinimal:
    """Tests for minimal Cargo.toml."""

    def test_minimal_parse_ok(self):
        result = cargo_toml_inspect(MINIMAL_CARGO_TOML)
        assert result["parse_ok"] is True

    def test_minimal_no_findings(self):
        result = cargo_toml_inspect(MINIMAL_CARGO_TOML)
        assert result["findings"] == []

    def test_minimal_dependencies_empty(self):
        result = cargo_toml_inspect(MINIMAL_CARGO_TOML)
        assert result["dependencies"]["dependencies"] == {}


class TestCargoTomlInspectWorkspace:
    """Tests for workspace section analysis."""

    def test_workspace_present(self):
        result = cargo_toml_inspect(WORKSPACE_CARGO_TOML, check_workspace=True)
        assert result["workspace"]["present"] is True

    def test_workspace_members(self):
        result = cargo_toml_inspect(WORKSPACE_CARGO_TOML, check_workspace=True)
        assert result["workspace"]["members"] == [
            "crates/core",
            "crates/cli",
            "crates/utils",
        ]

    def test_workspace_exclude(self):
        result = cargo_toml_inspect(WORKSPACE_CARGO_TOML, check_workspace=True)
        assert result["workspace"]["exclude"] == ["old-crate"]

    def test_workspace_not_checked(self):
        result = cargo_toml_inspect(WORKSPACE_CARGO_TOML, check_workspace=False)
        assert result["workspace"]["present"] is False


class TestCargoTomlInspectDependencies:
    """Tests for dependency analysis."""

    def test_dependencies_section(self):
        result = cargo_toml_inspect(DEPENDENCY_CARGO_TOML, check_dependencies=True)
        deps = result["dependencies"]["dependencies"]
        assert "serde" in deps
        assert deps["serde"]["version"] == "1.0"

    def test_inline_table_dep(self):
        result = cargo_toml_inspect(DEPENDENCY_CARGO_TOML, check_dependencies=True)
        tokio = result["dependencies"]["dependencies"]["tokio"]
        assert tokio["version"] == "1.0"
        assert tokio["inline_table"] is True
        assert "full" in tokio.get("features", [])

    def test_dev_dependencies(self):
        result = cargo_toml_inspect(DEPENDENCY_CARGO_TOML, check_dependencies=True)
        dev_deps = result["dependencies"]["dev_dependencies"]
        assert "assert_cmd" in dev_deps
        assert dev_deps["assert_cmd"]["version"] == "2.0"

    def test_build_dependencies(self):
        result = cargo_toml_inspect(DEPENDENCY_CARGO_TOML, check_dependencies=True)
        build_deps = result["dependencies"]["build_dependencies"]
        assert "cc" in build_deps
        assert build_deps["cc"]["version"] == "1.0"

    def test_dependencies_not_checked(self):
        result = cargo_toml_inspect(DEPENDENCY_CARGO_TOML, check_dependencies=False)
        assert result["dependencies"]["dependencies"] == {}


class TestCargoTomlInspectPathDeps:
    """Tests for path dependency extraction."""

    def test_path_dependencies(self):
        result = cargo_toml_inspect(PATH_DEP_CARGO_TOML)
        paths = result["path_dependencies"]
        assert "../my-lib" in paths
        assert "crates/utils" in paths

    def test_path_dep_form(self):
        result = cargo_toml_inspect(PATH_DEP_CARGO_TOML)
        my_lib = result["dependencies"]["dependencies"]["my-lib"]
        assert my_lib["path"] == "../my-lib"
        assert my_lib["version"] == "0.1.0"


class TestCargoTomlInspectGitDeps:
    """Tests for git dependency analysis."""

    def test_git_dependency(self):
        result = cargo_toml_inspect(GIT_DEP_CARGO_TOML)
        ext = result["dependencies"]["dependencies"]["external"]
        assert ext["git"] == "https://github.com/example/repo"
        assert ext["branch"] == "main"

    def test_git_with_tag(self):
        result = cargo_toml_inspect(GIT_DEP_CARGO_TOML)
        pinned = result["dependencies"]["dependencies"]["pinned"]
        assert pinned["git"] == "https://github.com/example/other"
        assert pinned["tag"] == "v1.0"


class TestCargoTomlInspectMissingEdition:
    """Tests for missing edition detection."""

    def test_missing_edition_finding(self):
        result = cargo_toml_inspect(MISSING_EDITION_TOML)
        assert result["parse_ok"] is True
        assert any("edition" in f["message"].lower() for f in result["findings"])

    def test_missing_edition_package(self):
        result = cargo_toml_inspect(MISSING_EDITION_TOML)
        assert result["package"].get("edition") is None

    def test_cargo_toml_edition_workspace_inherited(self):
        toml_text = (
            '[package]\n' 'name = "member"\n' 'version = "0.1.0"\n' 'edition.workspace = true\n'
        )
        result = cargo_toml_inspect(toml_text)
        edition_findings = [f for f in result["findings"] if "edition" in f["message"].lower()]
        assert edition_findings == []

    def test_cargo_toml_missing_edition_message_updated(self):
        toml_text = '[package]\n' 'name = "lib"\n' 'version = "0.1.0"\n'
        result = cargo_toml_inspect(toml_text)
        edition_findings = [f for f in result["findings"] if "edition" in f["message"].lower()]
        assert len(edition_findings) == 1
        assert "workspace" in edition_findings[0]["message"].lower()


class TestCargoTomlInspectConfusables:
    """Tests for confusable/duplicate dependency name detection."""

    def test_confusable_names_detected(self):
        result = cargo_toml_inspect(CONFUSABLE_DEPS_TOML)
        dupes = result["duplicate_or_confusable_dependency_names"]
        assert "my_lib" in dupes
        assert "my-lib" in dupes

    def test_confusable_finding(self):
        result = cargo_toml_inspect(CONFUSABLE_DEPS_TOML)
        assert any("confusable" in f["message"].lower() for f in result["findings"])


class TestCargoTomlInspectSuspicious:
    """Tests for suspicious dependency name detection."""

    def test_suspicious_names(self):
        result = cargo_toml_inspect(SUSPICIOUS_DEPS_TOML)
        suspicious = result["suspicious_dependency_names"]
        assert "0bad" in suspicious
        assert "has spaces" in suspicious
        assert "double__underscore" in suspicious

    def test_clean_names_not_suspicious(self):
        result = cargo_toml_inspect(BASIC_CARGO_TOML)
        assert result["suspicious_dependency_names"] == []


class TestCargoTomlInspectTargetSpecific:
    """Tests for target-specific dependencies."""

    def test_target_specific_deps(self):
        result = cargo_toml_inspect(TARGET_SPECIFIC_TOML)
        target_specific = result["dependencies"]["target_specific"]
        assert len(target_specific) > 0
        first_key = next(iter(target_specific))
        assert "nix" in target_specific[first_key] or "winapi" in target_specific[first_key]


class TestCargoTomlInspectWorkspaceDeps:
    """Tests for workspace dependency inheritance."""

    def test_workspace_dep_flag(self):
        result = cargo_toml_inspect(WORKSPACE_DEPS_TOML)
        common = result["dependencies"]["dependencies"]["common"]
        assert common.get("workspace") is True

    def test_workspace_with_version(self):
        result = cargo_toml_inspect(WORKSPACE_DEPS_TOML)
        serde = result["dependencies"]["dependencies"]["serde"]
        assert serde.get("workspace") is True
        assert serde.get("version") == "1.0"


class TestCargoTomlInspectInvalid:
    """Tests for invalid TOML input."""

    def test_invalid_toml(self):
        result = cargo_toml_inspect(INVALID_TOML)
        assert result["parse_ok"] is False
        assert any("parse" in f["message"].lower() for f in result["findings"])

    def test_empty_toml(self):
        result = cargo_toml_inspect(EMPTY_TOML)
        assert result["parse_ok"] is True
        assert result["package"].get("name") is None
        assert any(
            "missing" in f["message"].lower() or "no" in f["message"].lower()
            for f in result["findings"]
        )


class TestCargoTomlInspectInputLimits:
    """Tests for input size limits."""

    def test_oversized_input(self):
        huge = "[package]\n" + "x" * 200_001
        result = cargo_toml_inspect(huge)
        assert result["parse_ok"] is False
        assert any("exceeds" in f["message"].lower() for f in result["findings"])


class TestCargoTomlInspectMCP:
    """Tests for the MCP wrapper."""

    def test_mcp_success(self):
        response = cargo_toml_inspect_mcp(BASIC_CARGO_TOML)
        assert response["ok"] is True
        assert response["tool"] == "cargo_toml_inspect"
        result = response["result"]
        assert result["parse_ok"] is True
        assert result["package"]["name"] == "my-crate"

    def test_mcp_findings(self):
        response = cargo_toml_inspect_mcp(MISSING_EDITION_TOML)
        assert response["ok"] is True
        assert response.get("findings") is not None
        assert len(response["findings"]) > 0

    def test_mcp_machine_code(self):
        response = cargo_toml_inspect_mcp(INVALID_TOML)
        assert response["ok"] is True
        assert response.get("machine_code") == "CARGO_PARSE_FAILED"

    def test_mcp_oversized_input(self):
        huge = "[package]\n" + "x" * 100_001
        response = cargo_toml_inspect_mcp(huge)
        assert response["ok"] is False
        assert response["error_type"] == "input_too_large"

    def test_mcp_findings_are_structured(self):
        response = cargo_toml_inspect_mcp(MISSING_EDITION_TOML)
        assert response["ok"] is True
        for f in response["findings"]:
            assert "code" in f
            assert "severity" in f
            assert "message" in f


class TestCargoTomlInspectVirtualWorkspace:
    """Tests for virtual workspace handling."""

    def test_virtual_workspace_no_findings(self):
        result = cargo_toml_inspect(VIRTUAL_WORKSPACE_TOML)
        assert result["parse_ok"] is True
        assert result["workspace"]["present"] is True
        no_pkg_ws = [f for f in result["findings"] if f["code"] == "CARGO_NO_PACKAGE_OR_WORKSPACE"]
        assert no_pkg_ws == []

    def test_empty_no_package_or_workspace(self):
        result = cargo_toml_inspect(EMPTY_VIRTUAL_WORKSPACE_TOML)
        assert result["parse_ok"] is True
        assert any(f["code"] == "CARGO_NO_PACKAGE_OR_WORKSPACE" for f in result["findings"])

    def test_structured_finding_codes(self):
        result = cargo_toml_inspect(MISSING_EDITION_TOML)
        codes = [f["code"] for f in result["findings"]]
        assert "CARGO_MISSING_EDITION" in codes

    def test_structured_finding_severity(self):
        result = cargo_toml_inspect(INVALID_TOML)
        severities = [f["severity"] for f in result["findings"]]
        assert "error" in severities


class TestCargoScriptDetection:
    """Tests for script-based detection of dependency names."""

    def test_cyrillic_identifier_not_flagged_suspicious(self):
        result = cargo_toml_inspect(CYRILLIC_CARGO_TOML)
        suspicious = result["suspicious_dependency_names"]
        assert "кириллица" not in suspicious
        findings = [
            f for f in result["findings"] if f["code"] == "CARGO_SUSPICIOUS_DEPENDENCY_NAME"
        ]
        assert findings == []

    def test_greek_identifier_not_flagged_suspicious(self):
        result = cargo_toml_inspect(GREEK_CARGO_TOML)
        suspicious = result["suspicious_dependency_names"]
        assert "αλφα" not in suspicious
        findings = [
            f for f in result["findings"] if f["code"] == "CARGO_SUSPICIOUS_DEPENDENCY_NAME"
        ]
        assert findings == []

    def test_mixed_script_detection(self):
        result = cargo_toml_inspect(MIXED_SCRIPT_CARGO_TOML)
        codes = [f["code"] for f in result["findings"]]
        assert "CARGO_MIXED_SCRIPT_DEPENDENCY_NAME" in codes

    def test_confusable_collision_detection(self):
        result = cargo_toml_inspect(CONFUSABLE_COLLISION_TOML)
        dupes = result["duplicate_or_confusable_dependency_names"]
        assert "serde" in dupes
        codes = [f["code"] for f in result["findings"]]
        assert "CARGO_CONFUSABLE_NAMES" in codes

    def test_renamed_dependency_not_suspicious(self):
        result = cargo_toml_inspect(RENAMED_DEPENDENCY_TOML)
        suspicious = result["suspicious_dependency_names"]
        assert "my_dep" not in suspicious

    def test_uppercase_ascii_not_flagged(self):
        result = cargo_toml_inspect(UPPERCASE_CARGO_TOML)
        suspicious = result["suspicious_dependency_names"]
        assert "Serde" not in suspicious
        assert "Tokio" not in suspicious

    def test_hyphen_underscore_confusable(self):
        result = cargo_toml_inspect(HYPHEN_UNDERSCORE_TOML)
        dupes = result["duplicate_or_confusable_dependency_names"]
        assert "my_lib" in dupes
        assert "my-lib" in dupes

    def test_all_findings_have_valid_codes(self):
        known_codes = {
            "INPUT_TOO_LONG",
            "TOML_NOT_AVAILABLE",
            "TOML_PARSE_ERROR",
            "CARGO_INVALID_TABLE",
            "CARGO_MISSING_PACKAGE_NAME",
            "CARGO_MISSING_PACKAGE_VERSION",
            "CARGO_MISSING_EDITION",
            "CARGO_INVALID_EDITION",
            "CARGO_NO_PACKAGE_OR_WORKSPACE",
            "CARGO_CONFUSABLE_NAMES",
            "CARGO_SUSPICIOUS_NAME",
            "CARGO_MIXED_SCRIPT_DEPENDENCY_NAME",
            "CARGO_NON_ASCII_DEPENDENCY_NAME",
            "CARGO_SUSPICIOUS_DEPENDENCY_NAME",
        }
        for toml_text in [
            BASIC_CARGO_TOML,
            SUSPICIOUS_DEPS_TOML,
            CONFUSABLE_DEPS_TOML,
            CYRILLIC_CARGO_TOML,
            GREEK_CARGO_TOML,
            MIXED_SCRIPT_CARGO_TOML,
        ]:
            result = cargo_toml_inspect(toml_text)
            for f in result["findings"]:
                assert f["code"] in known_codes, f"Unknown finding code: {f['code']}"

    def test_findings_are_json_serializable(self):
        result = cargo_toml_inspect(CYRILLIC_CARGO_TOML)
        json_str = json.dumps(result["findings"])
        assert isinstance(json_str, str)


MANY_SUSPICIOUS_DEPS = """\
[package]
name = "truncation-test"
version = "0.1.0"
edition = "2021"

[dependencies]
""" + "\n".join(f'bad_{i}__x = "1.0"' for i in range(210))


class TestInspectionContract:
    """Contract tests for inspection function return shapes."""

    def test_all_findings_are_mappings(self):
        for fn in (cargo_toml_inspect, pyproject_inspect, requirements_inspect):
            result = fn(BASIC_CARGO_TOML if fn is cargo_toml_inspect else "")
            for f in result["findings"]:
                assert isinstance(f, dict)

    def test_finding_has_required_fields(self):
        for fn, inp in (
            (cargo_toml_inspect, MISSING_EDITION_TOML),
            (pyproject_inspect, ""),
            (requirements_inspect, ""),
        ):
            result = fn(inp)
            for f in result["findings"]:
                assert "code" in f, f"Missing 'code' in {f}"
                assert "severity" in f, f"Missing 'severity' in {f}"
                assert "message" in f, f"Missing 'message' in {f}"

    def test_severity_vocabulary(self):
        for fn, inp in (
            (cargo_toml_inspect, INVALID_TOML),
            (pyproject_inspect, "[invalid"),
            (requirements_inspect, ""),
        ):
            result = fn(inp)
            for f in result["findings"]:
                assert f["severity"] in (
                    "error",
                    "warning",
                    "info",
                ), f"Bad severity {f['severity']!r} in {f['code']}"

    def test_findings_json_serializable(self):
        for fn, inp in (
            (cargo_toml_inspect, SUSPICIOUS_DEPS_TOML),
            (pyproject_inspect, ""),
            (requirements_inspect, ""),
        ):
            result = fn(inp)
            json_str = json.dumps(result["findings"])
            assert isinstance(json_str, str)

    def test_max_findings_truncation(self):
        result = cargo_toml_inspect(MANY_SUSPICIOUS_DEPS)
        assert len(result["findings"]) == 201
        assert result["findings"][-1]["code"] == "FINDINGS_TRUNCATED"
        assert result["findings"][-1]["severity"] == "warning"

    def test_parse_failure_produces_error_finding(self):
        for fn, inp in (
            (cargo_toml_inspect, INVALID_TOML),
            (pyproject_inspect, "[invalid"),
            (requirements_inspect, 12345),
        ):
            result = fn(inp)
            severities = [f["severity"] for f in result["findings"]]
            assert "error" in severities, f"{fn.__name__} did not produce an error finding"

    def test_empty_input_behavior(self):
        for fn, inp in (
            (cargo_toml_inspect, EMPTY_TOML),
            (pyproject_inspect, ""),
            (requirements_inspect, ""),
        ):
            result = fn(inp)
            assert "findings" in result
            for f in result["findings"]:
                assert isinstance(f, dict)
                assert "code" in f
