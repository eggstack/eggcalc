"""
Cargo.toml inspection primitives.

Provides deterministic parsing and analysis of Cargo.toml content
without network or filesystem access.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TypedDict

from eggcalc.exact.manifests import (
    _Finding,
    _finding,
    _truncate_findings,
)

_MAX_CARGO_INPUT_LENGTH = 200_000

_CARGO_PACKAGE_FIELDS = {"name", "version", "edition", "license", "repository", "readme"}

_EDITION_VALUES = {"2015", "2018", "2021", "2024"}

_SUSPICIOUS_NAME_PATTERNS = [
    re.compile(r"^\d"),
    re.compile(r"_{2,}"),
    re.compile(r"--"),
    re.compile(r"\."),
]

_CARGO_TOML_PATH_RE = re.compile(r"^[a-zA-Z0-9_\-]+(?:/[a-zA-Z0-9_\-]+)*\.toml$")


class CargoPackageInfo(TypedDict, total=False):
    """Extracted package metadata."""

    name: str | None
    version: str | None
    edition: str | None
    license: str | None
    repository: str | None
    readme: str | None


class CargoWorkspaceInfo(TypedDict):
    """Workspace section information."""

    present: bool
    members: list[str]
    exclude: list[str]


class CargoDependencyForm(TypedDict, total=False):
    """Form of a single dependency."""

    version: str | None
    path: str | None
    git: str | None
    workspace: bool
    inline_table: bool
    registry: str | None
    branch: str | None
    tag: str | None
    features: list[str]
    optional: bool
    default_features: bool


class CargoDepSection(TypedDict):
    """Dependencies within a specific section."""

    dependencies: dict[str, CargoDependencyForm]
    dev_dependencies: dict[str, CargoDependencyForm]
    build_dependencies: dict[str, CargoDependencyForm]
    target_specific: dict[str, dict[str, CargoDependencyForm]]


class CargoInspectResult(TypedDict):
    """Result of cargo_toml_inspect."""

    parse_ok: bool
    package: CargoPackageInfo
    workspace: CargoWorkspaceInfo
    dependencies: CargoDepSection
    path_dependencies: list[str]
    suspicious_dependency_names: list[str]
    duplicate_or_confusable_dependency_names: list[str]
    findings: list[_Finding]


def _is_cargo_toml_path(path: str) -> bool:
    """Check if a string looks like a Cargo.toml path (lexical check)."""
    return bool(_CARGO_TOML_PATH_RE.match(path))


def _has_confusable_unicode(name: str) -> bool:
    """Check if a name contains Unicode confusables (not just non-ASCII letters)."""
    from .unicode_tools import detect_confusables

    confusables = detect_confusables(name)
    return len(confusables) > 0


def _detect_suspicious_name(name: str) -> list[_Finding]:
    """Detect suspicious patterns in a dependency name.

    Returns a list of findings with distinct codes.
    """
    from .unicode_tools import unicode_script

    findings: list[_Finding] = []

    # Check for non-ASCII characters and script mixing
    has_non_ascii = False
    has_latin = False
    has_non_latin_scripts: set[str] = set()

    for ch in name:
        cp = ord(ch)
        if cp < 128:
            if ch.isalpha():
                has_latin = True
        elif cp > 127:
            has_non_ascii = True
            script = unicode_script(ch)
            if script == "Latin":
                has_latin = True
            elif script not in ("Common", "Unknown"):
                has_non_latin_scripts.add(script)

    if has_non_ascii and has_latin and has_non_latin_scripts:
        findings.append(
            _finding(
                "CARGO_MIXED_SCRIPT_DEPENDENCY_NAME",
                "warning",
                f"Mixed-script dependency name '{name}' contains characters from multiple scripts",
            )
        )
    elif has_non_ascii:
        if _has_confusable_unicode(name):
            findings.append(
                _finding(
                    "CARGO_NON_ASCII_DEPENDENCY_NAME",
                    "info",
                    f"Non-ASCII dependency name '{name}'",
                )
            )

    # Check for non-standard characters (non-letter, non-digit, non-separator)
    has_suspicious_pattern = False
    for ch in name:
        cat = unicodedata.category(ch)
        if not cat.startswith("L") and not cat.startswith("D") and ch not in "-_":
            has_suspicious_pattern = True
            break

    if not has_suspicious_pattern:
        for pat in _SUSPICIOUS_NAME_PATTERNS:
            if pat.search(name):
                has_suspicious_pattern = True
                break

    if has_suspicious_pattern:
        findings.append(
            _finding(
                "CARGO_SUSPICIOUS_DEPENDENCY_NAME",
                "warning",
                f"Suspicious dependency name pattern in '{name}'",
            )
        )

    return findings


def _normalize_ident(name: str) -> str:
    """Normalize an identifier for comparison: lowercase, NFKC, collapse separators."""
    normalized = unicodedata.normalize("NFKC", name)
    normalized = normalized.casefold()
    normalized = re.sub(r"[\-_.]+", "_", normalized)
    return normalized


def _detect_duplicates(names: list[str]) -> list[str]:
    """Detect dependency names that are confusable via normalization."""
    groups: dict[str, list[str]] = {}
    for name in names:
        key = _normalize_ident(name)
        groups.setdefault(key, []).append(name)
    dupes: list[str] = []
    for key, group in groups.items():
        if len(group) > 1:
            dupes.extend(sorted(set(group)))
    return sorted(set(dupes))


def _parse_dep_value(raw: str | dict) -> CargoDependencyForm:
    """Parse a single dependency value into a structured form."""
    if isinstance(raw, dict):
        form: CargoDependencyForm = {"inline_table": True}
        if "version" in raw:
            form["version"] = str(raw["version"])
        if "path" in raw:
            form["path"] = str(raw["path"])
        if "git" in raw:
            form["git"] = str(raw["git"])
        if "branch" in raw:
            form["branch"] = str(raw["branch"])
        if "tag" in raw:
            form["tag"] = str(raw["tag"])
        if "registry" in raw:
            form["registry"] = str(raw["registry"])
        if "workspace" in raw:
            form["workspace"] = bool(raw["workspace"])
        if "features" in raw and isinstance(raw["features"], list):
            form["features"] = [str(f) for f in raw["features"]]
        if "optional" in raw:
            form["optional"] = bool(raw["optional"])
        if "default-features" in raw:
            form["default_features"] = bool(raw["default-features"])
        if "workspace" not in form:
            form["workspace"] = False
        return form
    else:
        return {"version": str(raw), "inline_table": False, "workspace": False}


def _collect_path_deps(deps: dict[str, CargoDependencyForm]) -> list[str]:
    """Extract path dependency values from a dependency dict."""
    paths: list[str] = []
    for _name, form in deps.items():
        path = form.get("path")
        if path:
            paths.append(path)
    return paths


def cargo_toml_inspect(
    text: str,
    check_workspace: bool = True,
    check_dependencies: bool = True,
) -> CargoInspectResult:
    """Inspect Cargo.toml text without network or filesystem access.

    Args:
        text: The Cargo.toml content.
        check_workspace: Whether to analyze workspace section.
        check_dependencies: Whether to analyze dependencies sections.

    Returns:
        CargoInspectResult with package metadata, workspace info,
        dependency analysis, and findings.
    """
    if len(text) > _MAX_CARGO_INPUT_LENGTH:
        return CargoInspectResult(
            parse_ok=False,
            package=CargoPackageInfo(),
            workspace=CargoWorkspaceInfo(present=False, members=[], exclude=[]),
            dependencies=CargoDepSection(
                dependencies={},
                dev_dependencies={},
                build_dependencies={},
                target_specific={},
            ),
            path_dependencies=[],
            suspicious_dependency_names=[],
            duplicate_or_confusable_dependency_names=[],
            findings=[
                _finding(
                    "INPUT_TOO_LONG",
                    "error",
                    f"Input length {len(text)} exceeds maximum {_MAX_CARGO_INPUT_LENGTH}",
                ),
            ],
        )

    try:
        import tomllib
    except ImportError:
        return CargoInspectResult(
            parse_ok=False,
            package=CargoPackageInfo(),
            workspace=CargoWorkspaceInfo(present=False, members=[], exclude=[]),
            dependencies=CargoDepSection(
                dependencies={},
                dev_dependencies={},
                build_dependencies={},
                target_specific={},
            ),
            path_dependencies=[],
            suspicious_dependency_names=[],
            duplicate_or_confusable_dependency_names=[],
            findings=[
                _finding(
                    "TOML_NOT_AVAILABLE",
                    "error",
                    "tomllib not available - Python 3.11+ required",
                ),
            ],
        )

    try:
        parsed = tomllib.loads(text)
    except Exception as e:
        return CargoInspectResult(
            parse_ok=False,
            package=CargoPackageInfo(),
            workspace=CargoWorkspaceInfo(present=False, members=[], exclude=[]),
            dependencies=CargoDepSection(
                dependencies={},
                dev_dependencies={},
                build_dependencies={},
                target_specific={},
            ),
            path_dependencies=[],
            suspicious_dependency_names=[],
            duplicate_or_confusable_dependency_names=[],
            findings=[
                _finding(
                    "TOML_PARSE_ERROR",
                    "error",
                    f"TOML parse error: {e}",
                ),
            ],
        )

    findings: list[_Finding] = []

    # --- Package section ---
    has_package = "package" in parsed
    pkg_raw = parsed.get("package", {})
    if has_package and not isinstance(pkg_raw, dict):
        findings.append(
            _finding("CARGO_INVALID_TABLE", "error", "'[package]' section is not a table")
        )
        pkg_raw = {}

    package: CargoPackageInfo = {}
    for field in _CARGO_PACKAGE_FIELDS:
        val = pkg_raw.get(field)
        if val is not None:
            package[field] = str(val)  # type: ignore[literal-required]

    if has_package:
        if not package.get("name"):
            findings.append(
                _finding(
                    "CARGO_MISSING_PACKAGE_NAME", "warning", "Missing or empty 'name' in [package]"
                )
            )
        if not package.get("version"):
            findings.append(
                _finding(
                    "CARGO_MISSING_PACKAGE_VERSION",
                    "warning",
                    "Missing or empty 'version' in [package]",
                )
            )
        edition = package.get("edition")
        raw_edition = pkg_raw.get("edition")
        if edition is None:
            findings.append(
                _finding(
                    "CARGO_MISSING_EDITION",
                    "info",
                    "Missing 'edition' in [package] (inherits workspace edition or defaults to 2015)",
                )
            )
        elif isinstance(raw_edition, dict) and raw_edition.get("workspace") is True:
            pass
        elif not isinstance(edition, str) or edition not in _EDITION_VALUES:
            findings.append(
                _finding(
                    "CARGO_INVALID_EDITION",
                    "warning",
                    f"Unrecognized edition '{edition!r}'; "
                    f"expected one of: {', '.join(sorted(_EDITION_VALUES))}",
                )
            )
    else:
        # Virtual workspace — no [package] is intentional
        # Only flag if [workspace] is also absent
        if "workspace" not in parsed:
            findings.append(
                _finding(
                    "CARGO_NO_PACKAGE_OR_WORKSPACE",
                    "warning",
                    "No [package] or [workspace] section found",
                )
            )

    # --- Workspace section ---
    workspace: CargoWorkspaceInfo = {"present": False, "members": [], "exclude": []}
    if check_workspace:
        if "workspace" in parsed:
            ws_raw = parsed["workspace"]
            if isinstance(ws_raw, dict):
                workspace["present"] = True
                members = ws_raw.get("members", [])
                if isinstance(members, list):
                    workspace["members"] = [str(m) for m in members]
                exclude = ws_raw.get("exclude", [])
                if isinstance(exclude, list):
                    workspace["exclude"] = [str(e) for e in exclude]
            else:
                findings.append(
                    _finding("CARGO_INVALID_TABLE", "error", "'[workspace]' is not a table")
                )

    # --- Dependencies ---
    dep_section = CargoDepSection(
        dependencies={},
        dev_dependencies={},
        build_dependencies={},
        target_specific={},
    )
    all_dep_names: list[str] = []
    path_deps: list[str] = []

    if check_dependencies:
        dep_tables = {
            "dependencies": "dependencies",
            "dev-dependencies": "dev_dependencies",
            "build-dependencies": "build_dependencies",
        }

        for table_key, section_key in dep_tables.items():
            raw_deps = parsed.get(table_key, {})
            if not isinstance(raw_deps, dict):
                if table_key in parsed:
                    findings.append(
                        _finding("CARGO_INVALID_TABLE", "error", f"'[{table_key}]' is not a table")
                    )
                continue

            parsed_deps: dict[str, CargoDependencyForm] = {}
            for dep_name, dep_value in raw_deps.items():
                form = _parse_dep_value(dep_value)
                parsed_deps[str(dep_name)] = form
                all_dep_names.append(str(dep_name))
                path = form.get("path")
                if path:
                    path_deps.append(path)

            dep_section[section_key] = parsed_deps  # type: ignore[literal-required]

        # Target-specific dependencies: [target.'cfg(...)'.dependencies]
        target_section = parsed.get("target", {})
        if isinstance(target_section, dict):
            for target_key, target_val in target_section.items():
                if isinstance(target_val, dict):
                    target_deps: dict[str, CargoDependencyForm] = {}
                    for dep_table_key in ("dependencies", "dev-dependencies", "build-dependencies"):
                        raw_deps = target_val.get(dep_table_key, {})
                        if isinstance(raw_deps, dict):
                            for dep_name, dep_value in raw_deps.items():
                                form = _parse_dep_value(dep_value)
                                target_deps[str(dep_name)] = form
                                all_dep_names.append(str(dep_name))
                                path = form.get("path")
                                if path:
                                    path_deps.append(path)
                    if target_deps:
                        dep_section["target_specific"][target_key] = target_deps

    # --- Suspicious names ---
    suspicious_names: list[str] = []
    suspicious_findings: list[_Finding] = []
    for n in all_dep_names:
        name_findings = _detect_suspicious_name(n)
        if name_findings:
            suspicious_findings.extend(name_findings)
            if any(f.get("severity") in ("warning", "error") for f in name_findings):
                suspicious_names.append(n)
    findings.extend(suspicious_findings)

    # --- Duplicate/confusable names ---
    dupes = _detect_duplicates(all_dep_names)
    if dupes:
        findings.append(
            _finding(
                "CARGO_CONFUSABLE_NAMES",
                "warning",
                f"Confusable dependency names detected: {', '.join(dupes)}",
            )
        )

    return CargoInspectResult(
        parse_ok=True,
        package=package,
        workspace=workspace,
        dependencies=dep_section,
        path_dependencies=path_deps,
        suspicious_dependency_names=sorted(set(suspicious_names)),
        duplicate_or_confusable_dependency_names=dupes,
        findings=_truncate_findings(findings),
    )
