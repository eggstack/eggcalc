"""Deterministic manifest/package inspection tools.

Provides lexical/structural inspection of project manifests (pyproject.toml,
package.json, requirements.txt, go.mod, lockfiles) without network or
filesystem access. All functions are pure and side-effect-free.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict, cast

_MAX_INPUT_LENGTH = 500_000
_MAX_FINDINGS = 200


class _Finding(TypedDict, total=False):
    code: str
    severity: str
    message: str
    line: int
    column: int


class PyprojectInspectResult(TypedDict, total=False):
    parse_ok: bool
    project_name: str | None
    project_version: str | None
    build_backend: str | None
    build_requirements: list[str]
    build_backend_path: list[str] | None
    requires_python: str | None
    dependencies_count: int
    optional_dependency_groups: dict[str, int]
    scripts: dict[str, str]
    tool_sections: list[str]
    package_manager_signals: list[str]
    dynamic: list[str] | None
    entry_points: dict[str, str] | None
    gui_scripts: dict[str, str] | None
    urls: dict[str, str] | None
    findings: list[_Finding]


class PackageJsonInspectResult(TypedDict, total=False):
    parse_ok: bool
    name: str | None
    version: str | None
    private: bool | None
    package_type: str | None
    scripts_keys: list[str]
    dependencies_count: int
    dev_dependencies_count: int
    peer_dependencies_count: int
    optional_dependencies_count: int
    engines: dict[str, str] | None
    package_manager: str | None
    workspaces: list[str] | None
    findings: list[_Finding]


class RequirementsInspectResult(TypedDict, total=False):
    parse_ok: bool
    total_lines: int
    package_specs: list[str]
    editable_refs: list[str]
    direct_urls: list[str]
    vcs_refs: list[str]
    comments: list[str]
    requirement_includes: list[str]
    constraints_includes: list[str]
    index_options: list[str]
    hash_options: list[str]
    environment_markers: list[str]
    suspicious_lines: list[str]
    findings: list[_Finding]


class GoModInspectResult(TypedDict, total=False):
    parse_ok: bool
    module_path: str | None
    go_version: str | None
    toolchain: str | None
    require_count: int
    replace_directives: list[dict[str, str]]
    exclude_directives: list[dict[str, str]]
    findings: list[_Finding]


class LockfileSummaryResult(TypedDict, total=False):
    parse_ok: bool
    detected_kind: str
    ecosystem: str | None
    approximate_package_count: int
    warnings: list[str]
    findings: list[_Finding]


def _finding(code: str, severity: str, message: str, line: int = 0, column: int = 0) -> _Finding:
    f: _Finding = {"code": code, "severity": severity, "message": message}
    if line:
        f["line"] = line
    if column:
        f["column"] = column
    return f


def _truncate_findings(findings: list[_Finding]) -> list[_Finding]:
    if len(findings) > _MAX_FINDINGS:
        truncated = findings[:_MAX_FINDINGS]
        truncated.append(
            _finding(
                "FINDINGS_TRUNCATED",
                "warning",
                f"Truncated to {_MAX_FINDINGS} findings ({len(findings)} total)",
            )
        )
        return truncated
    return findings


def pyproject_inspect(text: str) -> PyprojectInspectResult:
    """Inspect pyproject.toml content without network or filesystem access."""
    if not isinstance(text, str):
        return PyprojectInspectResult(
            parse_ok=False,
            findings=[
                _finding("INVALID_INPUT", "error", "Input must be a string"),
            ],
        )
    if len(text) > _MAX_INPUT_LENGTH:
        return PyprojectInspectResult(
            parse_ok=False,
            findings=[
                _finding(
                    "INPUT_TOO_LONG", "error", f"Input exceeds {_MAX_INPUT_LENGTH} character limit"
                ),
            ],
        )

    findings: list[_Finding] = []
    try:
        import tomllib
    except ImportError:
        return PyprojectInspectResult(
            parse_ok=False,
            findings=[
                _finding(
                    "TOML_NOT_AVAILABLE",
                    "error",
                    "tomllib is not available (requires Python 3.11+)",
                ),
            ],
        )
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        line_no = getattr(e, "lineno", None) or getattr(e, "line", 0) or 0
        col_no = getattr(e, "colno", None) or getattr(e, "column", None) or 0
        findings.append(_finding("TOML_PARSE_ERROR", "error", str(e), line_no, col_no))
        return PyprojectInspectResult(parse_ok=False, findings=findings)

    result: dict[str, Any] = {"parse_ok": True}

    project = data.get("project", {})
    result["project_name"] = project.get("name")
    result["project_version"] = project.get("version")
    result["requires_python"] = project.get("requires-python")

    build_system = data.get("build-system", {})
    result["build_backend"] = build_system.get("build-backend")
    build_requires = build_system.get("requires", [])
    result["build_requirements"] = build_requires if isinstance(build_requires, list) else []
    result["build_backend_path"] = build_system.get("backend-path")

    deps = project.get("dependencies", [])
    result["dependencies_count"] = len(deps) if isinstance(deps, list) else 0

    optional = project.get("optional-dependencies", {})
    result["optional_dependency_groups"] = {
        k: len(v) for k, v in optional.items() if isinstance(v, list)
    }

    scripts = project.get("scripts", {})
    result["scripts"] = dict(scripts) if isinstance(scripts, dict) else {}

    dynamic = project.get("dynamic")
    result["dynamic"] = dynamic if isinstance(dynamic, list) else None

    entry_points = project.get("entry-points", {})
    result["entry_points"] = dict(entry_points) if isinstance(entry_points, dict) else None

    gui_scripts = project.get("gui-scripts", {})
    result["gui_scripts"] = dict(gui_scripts) if isinstance(gui_scripts, dict) else None

    urls = project.get("urls", {})
    result["urls"] = dict(urls) if isinstance(urls, dict) else None

    tool_data = data.get("tool", {})
    if isinstance(tool_data, dict):
        tool_sections = sorted(f"tool.{k}" for k in tool_data.keys())
    else:
        tool_sections = []
    result["tool_sections"] = tool_sections

    pm_signals: list[str] = []
    if data.get("tool", {}).get("poetry"):
        pm_signals.append("poetry")
    if data.get("tool", {}).get("pdm"):
        pm_signals.append("pdm")
    if data.get("tool", {}).get("hatch"):
        pm_signals.append("hatch")
    if data.get("tool", {}).get("uv"):
        pm_signals.append("uv")
    if data.get("tool", {}).get("setuptools"):
        pm_signals.append("setuptools")
    if data.get("tool", {}).get("flit"):
        pm_signals.append("flit")
    result["package_manager_signals"] = pm_signals

    if not project.get("name"):
        findings.append(_finding("MISSING_PROJECT_NAME", "warning", "No [project] name found"))
    if not project.get("version"):
        findings.append(_finding("MISSING_PROJECT_VERSION", "info", "No [project] version found"))
    if "build-system" in data and not build_system.get("build-backend"):
        if not any(f["code"] == "MISSING_BUILD_BACKEND" for f in findings):
            findings.append(
                _finding(
                    "MISSING_BUILD_BACKEND",
                    "warning",
                    "No build-system.build-backend found",
                )
            )

    result["findings"] = _truncate_findings(findings)
    return cast(PyprojectInspectResult, result)


def package_json_inspect(text: str) -> PackageJsonInspectResult:
    """Inspect package.json content without network or filesystem access."""
    if not isinstance(text, str):
        return PackageJsonInspectResult(
            parse_ok=False,
            findings=[
                _finding("INVALID_INPUT", "error", "Input must be a string"),
            ],
        )
    if len(text) > _MAX_INPUT_LENGTH:
        return PackageJsonInspectResult(
            parse_ok=False,
            findings=[
                _finding(
                    "INPUT_TOO_LONG", "error", f"Input exceeds {_MAX_INPUT_LENGTH} character limit"
                ),
            ],
        )

    findings: list[_Finding] = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        line_no = getattr(e, "lineno", 0) or 0
        findings.append(_finding("JSON_PARSE_ERROR", "error", str(e), line_no))
        return PackageJsonInspectResult(parse_ok=False, findings=findings)

    if not isinstance(data, dict):
        findings.append(_finding("ROOT_NOT_OBJECT", "error", "Root must be a JSON object"))
        return PackageJsonInspectResult(parse_ok=False, findings=findings)

    result: dict[str, Any] = {"parse_ok": True}
    result["name"] = data.get("name")
    result["version"] = data.get("version")
    result["private"] = data.get("private") if "private" in data else None
    result["package_type"] = data.get("type")
    result["scripts_keys"] = (
        sorted(data.get("scripts", {}).keys()) if isinstance(data.get("scripts"), dict) else []
    )

    def _dep_count(key: str) -> int:
        v = data.get(key)
        return len(v) if isinstance(v, dict) else 0

    result["dependencies_count"] = _dep_count("dependencies")
    result["dev_dependencies_count"] = _dep_count("devDependencies")
    result["peer_dependencies_count"] = _dep_count("peerDependencies")
    result["optional_dependencies_count"] = _dep_count("optionalDependencies")
    result["engines"] = data.get("engines") if isinstance(data.get("engines"), dict) else None
    result["package_manager"] = data.get("packageManager")
    result["workspaces"] = _extract_workspaces(data)

    if not data.get("name"):
        findings.append(_finding("MISSING_NAME", "warning", "No name field"))
    if not data.get("version"):
        findings.append(_finding("MISSING_VERSION", "info", "No version field"))

    result["findings"] = _truncate_findings(findings)
    return cast(PackageJsonInspectResult, result)


def _extract_workspaces(data: dict) -> list[str] | None:
    ws = data.get("workspaces")
    if isinstance(ws, list):
        return [str(w) for w in ws]
    if isinstance(ws, dict) and "packages" in ws:
        pkgs = ws["packages"]
        return [str(w) for w in pkgs] if isinstance(pkgs, list) else None
    return None


_KNOWN_PIP_OPTIONS = frozenset(
    {
        "-c",
        "--constraint",
        "-e",
        "--editable",
        "-f",
        "--find-links",
        "-i",
        "--index-url",
        "-r",
        "--requirement",
        "--extra-index-url",
        "--global-option",
        "--hash",
        "--implementation",
        "--no-binary",
        "--no-clean",
        "--no-compile",
        "--no-deps",
        "--no-index",
        "--no-warn-script-location",
        "--only-binary",
        "--platform",
        "--prefix",
        "--pre",
        "--prefer-binary",
        "--python-version",
        "--require-hashes",
        "--resolver",
        "--target",
        "--trusted-host",
        "--upgrade",
        "--user",
    }
)


def _check_req_suspicious(
    check_line: str,
    line_no: int,
    findings: list[_Finding],
    suspicious_lines: list[str],
    raw: str,
    has_url: bool,
    has_markers: bool,
) -> None:
    if not has_url and not has_markers:
        if "`" in check_line:
            suspicious_lines.append(raw)
            findings.append(
                _finding(
                    "SUSPICIOUS_LINE",
                    "warning",
                    f"Shell backtick in line: {check_line[:80]}",
                    line_no,
                )
            )
            return
        if "$(" in check_line or "${" in check_line:
            suspicious_lines.append(raw)
            findings.append(
                _finding(
                    "SUSPICIOUS_LINE",
                    "warning",
                    f"Shell substitution in line: {check_line[:80]}",
                    line_no,
                )
            )
            return

    if check_line.count("(") != check_line.count(")"):
        suspicious_lines.append(raw)
        findings.append(
            _finding(
                "SUSPICIOUS_LINE",
                "warning",
                f"Unbalanced parentheses: {check_line[:80]}",
                line_no,
            )
        )
        return
    if check_line.count("[") != check_line.count("]"):
        suspicious_lines.append(raw)
        findings.append(
            _finding(
                "SUSPICIOUS_LINE",
                "warning",
                f"Unbalanced brackets: {check_line[:80]}",
                line_no,
            )
        )
        return
    if check_line.count("{") != check_line.count("}"):
        suspicious_lines.append(raw)
        findings.append(
            _finding(
                "SUSPICIOUS_LINE",
                "warning",
                f"Unbalanced braces: {check_line[:80]}",
                line_no,
            )
        )
        return

    for ch in check_line:
        if ord(ch) < 0x20 and ch not in ("\t", "\n", "\r"):
            suspicious_lines.append(raw)
            findings.append(
                _finding(
                    "SUSPICIOUS_LINE",
                    "warning",
                    f"Embedded control character in line: {check_line[:80]}",
                    line_no,
                )
            )
            return


def requirements_inspect(text: str) -> RequirementsInspectResult:
    """Inspect requirements.txt-style content without network access."""
    if not isinstance(text, str):
        return RequirementsInspectResult(
            parse_ok=False,
            findings=[
                _finding("INVALID_INPUT", "error", "Input must be a string"),
            ],
        )
    if len(text) > _MAX_INPUT_LENGTH:
        return RequirementsInspectResult(
            parse_ok=False,
            findings=[
                _finding(
                    "INPUT_TOO_LONG", "error", f"Input exceeds {_MAX_INPUT_LENGTH} character limit"
                ),
            ],
        )

    findings: list[_Finding] = []
    lines = text.splitlines()
    package_specs: list[str] = []
    editable_refs: list[str] = []
    direct_urls: list[str] = []
    vcs_refs: list[str] = []
    comments: list[str] = []
    requirement_includes: list[str] = []
    constraints_includes: list[str] = []
    index_options: list[str] = []
    hash_options: list[str] = []
    environment_markers: list[str] = []
    suspicious_lines: list[str] = []

    in_continuation = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            in_continuation = False
            continue

        if stripped.startswith("#"):
            comments.append(stripped)
            in_continuation = False
            continue

        if in_continuation:
            in_continuation = stripped.endswith("\\")
            continue

        in_continuation = stripped.endswith("\\")
        check_line = stripped[:-1].rstrip() if in_continuation else stripped

        if check_line.startswith("-r ") or check_line.startswith("--requirement "):
            requirement_includes.append(stripped)
            continue

        if check_line.startswith("-c ") or check_line.startswith("--constraint "):
            constraints_includes.append(stripped)
            continue

        if check_line.startswith("-e ") or check_line.startswith("--editable "):
            editable_refs.append(stripped)
            continue

        if (
            check_line.startswith("-i ")
            or check_line.startswith("--index-url ")
            or check_line.startswith("--extra-index-url ")
            or check_line.startswith("-f ")
            or check_line.startswith("--find-links ")
            or check_line.startswith("--trusted-host ")
            or check_line == "--no-index"
        ):
            index_options.append(stripped)
            continue

        if check_line.startswith("--hash="):
            hash_options.append(stripped)
            continue

        has_url = "://" in check_line
        has_vcs = any(check_line.startswith(f"{v}+") for v in ("git", "hg", "svn", "bzr"))
        has_markers = ";" in check_line

        if has_vcs:
            vcs_refs.append(stripped)
            if has_markers:
                environment_markers.append(stripped)
            _check_req_suspicious(
                check_line,
                i,
                findings,
                suspicious_lines,
                stripped,
                has_url=has_url,
                has_markers=has_markers,
            )
            continue

        if has_url:
            direct_urls.append(stripped)
            if has_markers:
                environment_markers.append(stripped)
            _check_req_suspicious(
                check_line,
                i,
                findings,
                suspicious_lines,
                stripped,
                has_url=has_url,
                has_markers=has_markers,
            )
            continue

        if check_line.startswith("-"):
            first_token = check_line.split()[0] if check_line.split() else check_line
            if first_token not in _KNOWN_PIP_OPTIONS:
                suspicious_lines.append(stripped)
                findings.append(
                    _finding(
                        "UNKNOWN_OPTION",
                        "warning",
                        f"Unknown option: {check_line[:80]}",
                        i,
                    )
                )
                continue
            if check_line.startswith("--"):
                index_options.append(stripped)
            else:
                index_options.append(stripped)
            continue

        package_specs.append(stripped)
        if has_markers:
            environment_markers.append(stripped)
        _check_req_suspicious(
            check_line,
            i,
            findings,
            suspicious_lines,
            stripped,
            has_url=has_url,
            has_markers=has_markers,
        )

    result: dict[str, Any] = {
        "parse_ok": True,
        "total_lines": len(lines),
        "package_specs": package_specs,
        "editable_refs": editable_refs,
        "direct_urls": direct_urls,
        "vcs_refs": vcs_refs,
        "comments": comments,
        "requirement_includes": requirement_includes,
        "constraints_includes": constraints_includes,
        "index_options": index_options,
        "hash_options": hash_options,
        "environment_markers": environment_markers,
        "suspicious_lines": suspicious_lines,
    }

    if not package_specs and not editable_refs:
        findings.append(_finding("NO_PACKAGES", "info", "No package specifications found"))

    result["findings"] = _truncate_findings(findings)
    return cast(RequirementsInspectResult, result)


def go_mod_inspect(text: str) -> GoModInspectResult:
    """Inspect go.mod content without network or filesystem access."""
    if not isinstance(text, str):
        return GoModInspectResult(
            parse_ok=False,
            findings=[
                _finding("INVALID_INPUT", "error", "Input must be a string"),
            ],
        )
    if len(text) > _MAX_INPUT_LENGTH:
        return GoModInspectResult(
            parse_ok=False,
            findings=[
                _finding(
                    "INPUT_TOO_LONG", "error", f"Input exceeds {_MAX_INPUT_LENGTH} character limit"
                ),
            ],
        )

    findings: list[_Finding] = []
    module_path: str | None = None
    go_version: str | None = None
    toolchain: str | None = None
    require_count = 0
    replaces: list[dict[str, str]] = []
    excludes: list[dict[str, str]] = []

    in_require = False
    in_replace = False
    in_exclude = False

    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        if stripped.startswith("module "):
            parts = stripped.split(None, 1)
            module_path = parts[1].strip() if len(parts) > 1 else None
            continue

        if stripped.startswith("go "):
            go_version = (
                stripped.split(None, 1)[1].strip() if len(stripped.split(None, 1)) > 1 else None
            )
            continue

        if stripped.startswith("toolchain "):
            toolchain = (
                stripped.split(None, 1)[1].strip() if len(stripped.split(None, 1)) > 1 else None
            )
            continue

        if stripped == "require (":
            in_require = True
            continue
        if stripped == "replace (":
            in_replace = True
            continue
        if stripped == "exclude (":
            in_exclude = True
            continue

        if stripped == ")":
            in_require = in_replace = in_exclude = False
            continue

        if in_require:
            require_count += 1
            continue

        if in_replace:
            r = _parse_go_replace(stripped)
            if r:
                replaces.append(r)
            continue

        if in_exclude:
            e = _parse_go_exclude(stripped)
            if e:
                excludes.append(e)
            continue

        if stripped.startswith("require "):
            require_count += 1
            continue

        if stripped.startswith("replace "):
            r = _parse_go_replace_inline(stripped)
            if r:
                replaces.append(r)
            continue

        if stripped.startswith("exclude "):
            e = _parse_go_exclude_inline(stripped)
            if e:
                excludes.append(e)
            continue

    result: dict[str, Any] = {
        "parse_ok": True,
        "module_path": module_path,
        "go_version": go_version,
        "toolchain": toolchain,
        "require_count": require_count,
        "replace_directives": replaces,
        "exclude_directives": excludes,
    }

    if not module_path:
        findings.append(_finding("MISSING_MODULE", "warning", "No module directive found"))
    if not go_version:
        findings.append(_finding("MISSING_GO_VERSION", "warning", "No go version directive found"))

    result["findings"] = _truncate_findings(findings)
    return cast(GoModInspectResult, result)


def _parse_go_replace(line: str) -> dict[str, str] | None:
    if "=>" in line:
        left, _, right = line.partition("=>")
        left = left.strip()
        right = right.strip()
        if not left or not right:
            return None
        old = left.split(None, 1)[0]
        return {"old": old, "new": right}
    parts = line.split(None, 2)
    if len(parts) >= 2:
        result: dict[str, str] = {"old": parts[0]}
        if len(parts) >= 3:
            result["new"] = parts[2]
        else:
            result["new"] = parts[0]
        return result
    return None


def _parse_go_replace_inline(line: str) -> dict[str, str] | None:
    rest = line[len("replace") :].strip()
    return _parse_go_replace(rest) if rest else None


def _parse_go_exclude(line: str) -> dict[str, str] | None:
    parts = line.split(None, 1)
    if parts:
        return {"module": parts[0], "version": parts[1] if len(parts) > 1 else ""}
    return None


def _parse_go_exclude_inline(line: str) -> dict[str, str] | None:
    rest = line[len("exclude") :].strip()
    return _parse_go_exclude(rest) if rest else None


_LOCKFILE_SIGNATURES: list[tuple[str, str, str]] = [
    ("package-lock.json", "package-lock", "npm"),
    ("pnpm-lock.yaml", "pnpm-lock", "pnpm"),
    ("yarn.lock", "yarn-lock", "yarn"),
    ("poetry.lock", "poetry-lock", "poetry"),
    ("uv.lock", "uv-lock", "uv"),
    ("Cargo.lock", "cargo-lock", "cargo"),
    ("go.sum", "go-sum", "go"),
    ("Pipfile.lock", "pipenv", "pipenv"),
    ("composer.lock", "composer", "php"),
]

_KIND_TO_ECOSYSTEM: dict[str, str] = {k: eco for _, k, eco in _LOCKFILE_SIGNATURES}


def lockfile_summary(text: str, kind: str = "auto") -> LockfileSummaryResult:
    """Produce a shallow summary of a lockfile without full parsing."""
    if not isinstance(text, str):
        return LockfileSummaryResult(
            parse_ok=False,
            detected_kind="unknown",
            findings=[
                _finding("INVALID_INPUT", "error", "Input must be a string"),
            ],
        )
    if len(text) > _MAX_INPUT_LENGTH:
        return LockfileSummaryResult(
            parse_ok=False,
            detected_kind="unknown",
            findings=[
                _finding(
                    "INPUT_TOO_LONG", "error", f"Input exceeds {_MAX_INPUT_LENGTH} character limit"
                ),
            ],
        )

    findings: list[_Finding] = []
    warnings: list[str] = []
    detected = kind
    ecosystem: str | None = _KIND_TO_ECOSYSTEM.get(kind)
    approx_count = 0

    if kind == "auto":
        for filename, k, eco in _LOCKFILE_SIGNATURES:
            if filename in text or f'"name": "{filename}"' in text:
                detected = k
                ecosystem = eco
                break

    if detected == "auto":
        if '"lockfileVersion"' in text:
            detected = "package-lock"
            ecosystem = "npm"
        elif "pnpm" in text and "packages:" in text:
            detected = "pnpm-lock"
            ecosystem = "pnpm"
        elif "resolution:" in text and "__metadata:" in text:
            detected = "yarn-lock"
            ecosystem = "yarn"
        elif "[metadata]" in text and 'lock-version' in text:
            detected = "poetry-lock"
            ecosystem = "poetry"

    if detected == "auto":
        detected = "unknown"
        warnings.append("Could not auto-detect lockfile kind")

    lines = text.splitlines()

    if detected == "package-lock":
        try:
            data = json.loads(text)
            deps = data.get("packages", data.get("dependencies", {}))
            approx_count = len(deps) if isinstance(deps, dict) else 0
        except (json.JSONDecodeError, ValueError):
            warnings.append("Failed to parse package-lock.json")
    elif detected == "pnpm-lock":
        pkg_count = text.count("  /")
        approx_count = max(pkg_count, 0)
    elif detected == "yarn-lock":
        approx_count = text.count('"')
        approx_count = max(approx_count // 4, 0)
    elif detected == "poetry-lock":
        approx_count = text.count('name = "')
    elif detected == "uv-lock":
        approx_count = text.count('name = "')
    elif detected == "cargo-lock":
        approx_count = text.count('name = "')
    elif detected == "go-sum":
        approx_count = len([l for l in lines if l.strip()])
    elif detected == "pipenv":
        try:
            data = json.loads(text)
            default = data.get("default", {})
            develop = data.get("develop", {})
            approx_count = len(default) + len(develop)
        except (json.JSONDecodeError, ValueError):
            warnings.append("Failed to parse Pipfile.lock")
    elif detected == "composer":
        try:
            data = json.loads(text)
            pkgs = data.get("packages", data.get("packages-dev", []))
            approx_count = len(pkgs) if isinstance(pkgs, list) else 0
        except (json.JSONDecodeError, ValueError):
            warnings.append("Failed to parse composer.lock")

    result: dict[str, Any] = {
        "parse_ok": True,
        "detected_kind": detected,
        "ecosystem": ecosystem,
        "approximate_package_count": approx_count,
        "warnings": warnings,
    }

    if detected == "unknown":
        findings.append(
            _finding("UNKNOWN_LOCKFILE", "info", "Lockfile kind could not be determined")
        )

    result["findings"] = _truncate_findings(findings)
    return cast(LockfileSummaryResult, result)
