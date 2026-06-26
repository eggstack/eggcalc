"""
Cargo.toml inspection primitives.

Provides deterministic parsing and analysis of Cargo.toml content
without network or filesystem access.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TypedDict

_MAX_INPUT_LENGTH = 200_000

_CARGO_PACKAGE_FIELDS = {"name", "version", "edition", "license", "repository", "readme"}

_EDITION_VALUES = {"2015", "2018", "2021", "2024"}

_SUSPICIOUS_NAME_PATTERNS = [
    re.compile(r"^\d"),
    re.compile(r"[^a-zA-Z0-9_\-]"),
    re.compile(r"_{2,}"),
    re.compile(r"--"),
    re.compile(r"\."),
    re.compile(r"[A-Z]"),
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
    findings: list[str]


def _is_cargo_toml_path(path: str) -> bool:
    """Check if a string looks like a Cargo.toml path (lexical check)."""
    return bool(_CARGO_TOML_PATH_RE.match(path))


def _detect_suspicious_name(name: str) -> bool:
    """Check if a dependency name has suspicious patterns."""
    for pat in _SUSPICIOUS_NAME_PATTERNS:
        if pat.search(name):
            return True
    return False


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
    if len(text) > _MAX_INPUT_LENGTH:
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
            findings=[f"Input length {len(text)} exceeds maximum {_MAX_INPUT_LENGTH}"],
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
            findings=["tomllib not available - Python 3.11+ required"],
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
            findings=[f"TOML parse error: {e}"],
        )

    findings: list[str] = []

    # --- Package section ---
    pkg_raw = parsed.get("package", {})
    if not isinstance(pkg_raw, dict):
        findings.append("'[package]' section is not a table")
        pkg_raw = {}

    package: CargoPackageInfo = {}
    for field in _CARGO_PACKAGE_FIELDS:
        val = pkg_raw.get(field)
        if val is not None:
            package[field] = str(val)  # type: ignore[literal-required]

    if not package.get("name"):
        findings.append("Missing or empty 'name' in [package]")
    if not package.get("version"):
        findings.append("Missing or empty 'version' in [package]")
    edition = package.get("edition")
    raw_edition = pkg_raw.get("edition")
    if edition is None:
        findings.append(
            "Missing 'edition' in [package] " "(inherits workspace edition or defaults to 2015)"
        )
    elif isinstance(raw_edition, dict) and raw_edition.get("workspace") is True:
        pass
    elif not isinstance(edition, str) or edition not in _EDITION_VALUES:
        findings.append(
            f"Unrecognized edition '{edition!r}; "
            f"expected one of: {', '.join(sorted(_EDITION_VALUES))}"
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
                findings.append("'[workspace]' is not a table")

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
                    findings.append(f"'[{table_key}]' is not a table")
                continue

            parsed_deps: dict[str, CargoDependencyForm] = {}
            for dep_name, dep_value in raw_deps.items():
                form = _parse_dep_value(dep_value)
                parsed_deps[str(dep_name)] = form
                all_dep_names.append(str(dep_name))
                path = form.get("path")
                if path:
                    path_deps.append(path)
                if form.get("git") and _detect_suspicious_name(str(dep_name)):
                    findings.append(f"Git dependency '{dep_name}' has suspicious name pattern")

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
    suspicious = sorted({name for name in all_dep_names if _detect_suspicious_name(name)})

    # --- Duplicate/confusable names ---
    dupes = _detect_duplicates(all_dep_names)
    if dupes:
        findings.append(f"Confusable dependency names detected: {', '.join(dupes)}")

    return CargoInspectResult(
        parse_ok=True,
        package=package,
        workspace=workspace,
        dependencies=dep_section,
        path_dependencies=path_deps,
        suspicious_dependency_names=suspicious,
        duplicate_or_confusable_dependency_names=dupes,
        findings=findings,
    )
