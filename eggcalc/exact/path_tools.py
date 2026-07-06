"""
Path lexical analysis tools.

Provides deterministic path parsing without filesystem access.
Analyzes path components, extensions, hidden status, and traversal.
"""

from __future__ import annotations

import re
from typing import TypedDict

from .unicode_tools import detect_confusables


class PathCompareResult(TypedDict):
    equal: bool
    left_normalized: str
    right_normalized: str
    differences: list[str]
    findings: list[str]


class PathScopeCheckResult(TypedDict):
    inside_root: bool
    root_normalized: str
    target_normalized: str
    relative_path: str
    escapes_via_dotdot: bool
    absolute_target: str
    findings: list[str]


class PathAnalyzeResult(TypedDict):
    input: str
    style: str
    absolute: bool
    has_traversal: bool
    components: list[str]
    parent: str | None
    name: str | None
    stem: str | None
    suffix: str | None
    suffixes: list[str]
    hidden: bool
    normalized_lexical: str
    warnings: list[str]
    summary: str


class PathNormalizeResult(TypedDict):
    normalized: str
    is_absolute: bool
    components: list[str]
    warnings: list[str]


def _detect_windows_path(path: str) -> bool:
    """Detect if path uses Windows syntax."""
    if len(path) < 2:
        return False
    if path[1] == ":":
        return True
    if path[:2] == "\\\\":
        return True
    if "\\" in path:
        return True
    return False


def _split_posix_components(path: str) -> tuple[list[str], str | None]:
    """Split POSIX path into components and root.

    Returns (components, root) where root is "/" for absolute paths, None for relative.
    """
    if path == "":
        return [], None

    if path.startswith("/"):
        root = "/"
        rest = path[1:]
        if rest:
            parts = rest.split("/")
            components = [p for p in parts if p]
        else:
            components = []
    else:
        root = None
        parts = path.split("/")
        components = [p for p in parts if p]

    return components, root


def _split_windows_components(path: str) -> tuple[list[str], str | None]:
    """Split Windows path into components and root.

    Returns (components, root) where root is like "C:" or "\\\\server\\share", None for relative.
    """
    if path == "":
        return [], None

    if len(path) >= 2 and path[1] == ":":
        root: str | None = path[:2]
        rest = path[2:]
        if rest:
            parts = re.split(r"[/\\]", rest)
            components = [p for p in parts if p]
        else:
            components = []
        return components, root

    if path.startswith("\\\\"):
        parts = re.split(r"[/\\]", path)
        if len(parts) >= 4:
            root = "\\\\" + parts[1] + "\\" + parts[2]
            components = [p for p in parts[3:] if p]
        else:
            root = path
            components = []
        return components, root

    if "\\" in path:
        parts = re.split(r"[/\\]", path)
        components = [p for p in parts if p]
        root = None
        return components, root

    parts = path.split("/")
    components = [p for p in parts if p]
    root = None
    return components, root


def _get_suffixes(name: str) -> list[str]:
    """Extract all suffixes from a filename.

    For ".tar.gz" returns [".tar.gz", ".gz"]
    For ".txt" returns [".txt"]
    """
    if not name or name == ".":
        return []

    parts = name.split(".")
    if len(parts) <= 1:
        return []

    suffixes = []
    for i in range(1, len(parts)):
        suffix = "." + ".".join(parts[i:])
        suffixes.append(suffix)

    return suffixes


def path_analyze(path: str, style: str = "auto") -> PathAnalyzeResult:
    """Analyze path components, extensions, hidden status, and traversal.

    This is lexical analysis only. Does NOT call Path.exists, resolve,
    or any filesystem API.

    Args:
        path: Path string to analyze.
        style: "auto", "posix", or "windows". Default "auto" detects from path syntax.

    Returns:
        PathAnalyzeResult with detailed path information.
    """
    warnings: list[str] = []
    input_path = path

    if style == "auto":
        detected = _detect_windows_path(path)
        style = "windows" if detected else "posix"

    if style == "windows":
        raw_components, root = _split_windows_components(path)
        sep = "\\"
    else:
        raw_components, root = _split_posix_components(path)
        sep = "/"

    components = []
    normalized_parts = []

    for i, comp in enumerate(raw_components):
        if comp == ".":
            warnings.append(f"Redundant current directory segment at position {i}")
            components.append(comp)
            normalized_parts.append(comp)
        elif comp == "..":
            warnings.append(f"Parent traversal segment at position {i}")
            components.append(comp)
            normalized_parts.append(comp)
        else:
            components.append(comp)
            normalized_parts.append(comp)

    has_traversal = ".." in raw_components
    absolute = root is not None

    name = components[-1] if components else None

    if name:
        suffixes = _get_suffixes(name)
        suffix = suffixes[-1] if suffixes else None
        if suffixes:
            full_suffix = suffixes[0]
            stem = name[: -len(full_suffix)] if len(full_suffix) > 0 else name
        else:
            stem = name
    else:
        suffixes = []
        suffix = None
        stem = None

    if components:
        parent_parts = components[:-1]
        if parent_parts:
            if root:
                if style == "posix":
                    parent = sep + sep.join(parent_parts)
                else:
                    parent = root + sep + sep.join(parent_parts)
            else:
                parent = sep.join(parent_parts)
        else:
            parent = None
    else:
        parent = None

    hidden = False
    if name and name != "." and name != "..":
        hidden = name.startswith(".")

    normalized = sep.join(normalized_parts) if normalized_parts else ""
    if root and style == "posix":
        normalized = sep + normalized

    confusables = detect_confusables(path)
    if confusables:
        warnings.append(f"Path contains {len(confusables)} confusable character(s)")

    summary_parts = []
    if style != "auto":
        summary_parts.append(f"{style.upper()}")
    if absolute:
        summary_parts.append("absolute")
    else:
        summary_parts.append("relative")
    if hidden:
        summary_parts.append("hidden")
    if has_traversal:
        summary_parts.append("with traversal")
    if len(components) == 1:
        summary_parts.append(f"single component '{components[0]}'")
    elif components:
        summary_parts.append(f"{len(components)} components")
    if suffix:
        if len(suffixes) > 1:
            summary_parts.append(f"suffixes {suffixes}")
        else:
            summary_parts.append(f"suffix '{suffix}'")

    summary = ", ".join(summary_parts) if summary_parts else "empty path"

    return PathAnalyzeResult(
        input=input_path,
        style=style,
        absolute=absolute,
        has_traversal=has_traversal,
        components=components,
        parent=parent,
        name=name,
        stem=stem,
        suffix=suffix,
        suffixes=suffixes,
        hidden=hidden,
        normalized_lexical=normalized,
        warnings=warnings,
        summary=summary,
    )


def _parse_path_root(path: str, platform: str) -> tuple[str, list[str], bool, str]:
    """Parse path into (root_string, tail_components, is_absolute, root_kind).

    root_kind: "none", "drive", "unc", "posix_root"
    root_string: "C:", "\\\\server\\share", "/", or ""
    tail_components: list of path components after root (may include "." and "..")
    """
    if platform == "windows":
        normalized = path.replace("/", "\\")

        if normalized.startswith("\\\\"):
            parts = normalized.split("\\")
            non_empty = [p for p in parts if p]
            if len(non_empty) >= 2:
                root = "\\\\" + non_empty[0] + "\\" + non_empty[1]
                tail = non_empty[2:]
                return root, tail, True, "unc"
            else:
                return "\\\\", [], True, "unc"

        if len(normalized) >= 2 and normalized[1] == ":":
            root = normalized[:2]
            rest = normalized[2:]
            if rest.startswith("\\") or rest.startswith("/"):
                parts = [p for p in rest.split("\\") if p]
                return root, parts, True, "drive"
            else:
                parts = [p for p in rest.split("\\") if p]
                return root, parts, False, "drive"

        parts = [p for p in normalized.split("\\") if p]
        return "", parts, False, "none"

    if path.startswith("/"):
        rest = path[1:]
        parts = [p for p in rest.split("/") if p]
        return "/", parts, True, "posix_root"

    parts = [p for p in path.split("/") if p]
    return "", parts, False, "none"


def path_normalize(
    path: str,
    platform: str = "posix",
    collapse_dot_segments: bool = True,
    preserve_trailing_separator: bool = False,
) -> PathNormalizeResult:
    """Normalize a path by collapsing dot segments and resolving parent traversal.

    This is lexical normalization only. Does NOT call filesystem APIs.

    Args:
        path: Path string to normalize.
        platform: "posix" or "windows".
        collapse_dot_segments: If True, collapse . and .. segments.
        preserve_trailing_separator: If True, keep trailing separator.

    Returns:
        PathNormalizeResult with normalized path and metadata.
    """
    warnings: list[str] = []
    has_dot_dot = False
    has_dot = False
    had_trailing_separator = path.endswith("/") or path.endswith("\\")

    if platform not in ("posix", "windows"):
        platform = "posix"

    sep = "/" if platform == "posix" else "\\"

    root, tail, is_absolute, root_kind = _parse_path_root(path, platform)

    for comp in tail:
        if comp == ".":
            has_dot = True
        elif comp == "..":
            has_dot_dot = True

    if collapse_dot_segments:
        collapsed: list[str] = []
        for comp in tail:
            if comp == ".":
                warnings.append("Collapsing dot segment")
                continue
            elif comp == "..":
                warnings.append("Collapsing dot-dot segment")
                if collapsed and collapsed[-1] != "..":
                    collapsed.pop()
                elif not is_absolute:
                    collapsed.append(comp)
            else:
                collapsed.append(comp)
        components = collapsed
    else:
        components = tail[:]

    if preserve_trailing_separator and had_trailing_separator and components:
        components = components + [""]

    if components:
        if root:
            if root_kind == "posix_root":
                normalized = root + sep.join(components)
            elif root_kind == "drive" and not is_absolute:
                normalized = root + sep.join(components)
            else:
                normalized = root + sep + sep.join(components)
        else:
            normalized = sep.join(components)
    else:
        if root_kind == "drive" and is_absolute:
            normalized = root + sep
        elif root_kind == "unc" and had_trailing_separator and preserve_trailing_separator:
            normalized = root + sep
        else:
            normalized = root

    if not normalized:
        if platform == "posix" and path.startswith("/"):
            normalized = "/"
        elif platform == "windows" and root_kind == "unc":
            normalized = "\\\\"

    if has_dot and not collapse_dot_segments:
        warnings.append("Path contains dot segments")
    if has_dot_dot and not collapse_dot_segments:
        warnings.append("Path contains parent traversal segments")

    return PathNormalizeResult(
        normalized=normalized,
        is_absolute=is_absolute,
        components=components,
        warnings=warnings,
    )


def path_compare(
    left: str,
    right: str,
    platform: str = "posix",
    case_sensitive: bool = True,
    normalize_separators: bool = True,
    collapse_dot_segments: bool = True,
) -> PathCompareResult:
    """Compare two paths under explicit normalization rules.

    This is lexical comparison only. Does NOT call filesystem APIs.

    Args:
        left: First path string.
        right: Second path string.
        platform: "posix" or "windows".
        case_sensitive: Whether comparison is case-sensitive.
        normalize_separators: Whether to normalize path separators.
        collapse_dot_segments: Whether to collapse . and .. segments.

    Returns:
        PathCompareResult with comparison result.
    """
    findings: list[str] = []

    if platform not in ("posix", "windows"):
        platform = "posix"

    sep = "/" if platform == "posix" else "\\"

    def _normalize_path(p: str) -> str:
        result = p
        if normalize_separators:
            if platform == "posix":
                result = result.replace("\\", "/")
            else:
                result = result.replace("/", "\\")
        norm_result = path_normalize(result, platform, collapse_dot_segments)
        return norm_result["normalized"]

    left_normalized = _normalize_path(left)
    right_normalized = _normalize_path(right)

    left_cmp = left_normalized
    right_cmp = right_normalized

    if not case_sensitive:
        left_cmp = left_cmp.lower()
        right_cmp = right_cmp.lower()

    equal = left_cmp == right_cmp

    differences: list[str] = []
    if not equal:
        differences.append(f"Normalized forms differ: '{left_normalized}' vs '{right_normalized}'")

    if not case_sensitive:
        findings.append("Case-insensitive comparison used")
    if normalize_separators:
        findings.append("Separators normalized to platform default")
    if collapse_dot_segments:
        findings.append("Dot segments collapsed")

    return PathCompareResult(
        equal=equal,
        left_normalized=left_normalized,
        right_normalized=right_normalized,
        differences=differences,
        findings=findings,
    )


def path_scope_check(
    root: str,
    target: str,
    platform: str = "posix",
    case_sensitive: bool = True,
) -> PathScopeCheckResult:
    """Determine whether a target path remains lexically inside a declared root.

    This is lexical only. Does NOT resolve symlinks. Symlink-safe
    enforcement requires filesystem-aware checks outside this tool.

    Args:
        root: Root directory path.
        target: Target path to check.
        platform: "posix" or "windows".
        case_sensitive: Whether comparison is case-sensitive.

    Returns:
        PathScopeCheckResult with scope check result.
    """
    findings: list[str] = []

    if platform not in ("posix", "windows"):
        platform = "posix"

    sep = "/" if platform == "posix" else "\\"

    def _pre_normalize(p: str) -> str:
        result = p
        if platform == "windows":
            result = result.replace("/", "\\")
        else:
            result = result.replace("\\", "/")
        return result

    root_pre = _pre_normalize(root)
    target_pre = _pre_normalize(target)

    root_norm = path_normalize(root_pre, platform, True)
    target_norm = path_normalize(target_pre, platform, True)

    root_normalized = root_norm["normalized"]
    target_normalized = target_norm["normalized"]

    root_is_abs = root_norm["is_absolute"]
    target_is_abs = target_norm["is_absolute"]

    if target_is_abs and not root_is_abs:
        findings.append("Target is absolute but root is relative")

    absolute_target = target_normalized
    if target_is_abs:
        absolute_target = target_normalized
    else:
        if platform == "posix":
            absolute_target = root_normalized.rstrip("/") + "/" + target_normalized
        else:
            absolute_target = root_normalized.rstrip("\\") + "\\" + target_normalized
        abs_norm = path_normalize(absolute_target, platform, True)
        absolute_target = abs_norm["normalized"]

    root_cmp = root_normalized
    target_cmp = absolute_target
    if not case_sensitive:
        root_cmp = root_cmp.lower()
        target_cmp = target_cmp.lower()

    if platform == "posix":
        root_prefix = root_cmp.rstrip("/") + "/"
    else:
        root_prefix = root_cmp.rstrip("\\") + "\\"

    inside_root = target_cmp.startswith(root_prefix) or target_cmp == root_cmp

    escapes_via_dotdot = ".." in target

    relative_path = ""
    if inside_root:
        if platform == "posix":
            relative_path = target_cmp[len(root_prefix) :]
        else:
            relative_path = target_cmp[len(root_prefix) :]
        if not relative_path:
            relative_path = "."

    if not case_sensitive:
        findings.append("Case-insensitive comparison used")
    if escapes_via_dotdot:
        findings.append("Target path contains parent traversal segments")
    if not target_is_abs:
        findings.append("Target is relative, resolved against root")

    return PathScopeCheckResult(
        inside_root=inside_root,
        root_normalized=root_normalized,
        target_normalized=target_normalized,
        relative_path=relative_path,
        escapes_via_dotdot=escapes_via_dotdot,
        absolute_target=absolute_target,
        findings=findings,
    )
