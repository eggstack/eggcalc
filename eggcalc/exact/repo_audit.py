"""Repository file inventory analysis tools.

Provides deterministic analysis of file inventories for repo structure
signals without filesystem access. All functions are pure and side-effect-free.
"""

from __future__ import annotations

import os
from collections import Counter
from typing import Any, TypedDict

_MAX_PATHS = 50_000
_MAX_PATH_LENGTH = 1_000

_SOURCE_EXTENSIONS = {
    ".py",
    ".pyx",
    ".pxd",
    ".rs",
    ".go",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cc",
    ".cxx",
    ".m",
    ".mm",
    ".java",
    ".kt",
    ".kts",
    ".scala",
    ".clj",
    ".cljs",
    ".rb",
    ".php",
    ".pl",
    ".pm",
    ".r",
    ".R",
    ".jl",
    ".swift",
    ".dart",
    ".ex",
    ".exs",
    ".erl",
    ".hs",
    ".elm",
    ".lua",
    ".zig",
    ".nim",
    ".v",
    ".vlang",
    ".cr",
}

_TEST_EXTENSIONS = {".test.js", ".test.ts", ".test.py", ".spec.js", ".spec.ts"}

_TEST_DIR_MARKERS = {"test", "tests", "__tests__", "spec", "specs", "testing"}
_CONFIG_FILENAMES = {
    "Cargo.toml",
    "pyproject.toml",
    "package.json",
    "go.mod",
    "go.sum",
    "Makefile",
    "CMakeLists.txt",
    "build.gradle",
    "pom.xml",
    "setup.py",
    "setup.cfg",
    "tox.ini",
    "noxfile.py",
    ".eslintrc",
    ".prettierrc",
    "tsconfig.json",
    "jest.config.js",
    "vitest.config.ts",
    "webpack.config.js",
    "vite.config.ts",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".github",
    "Cargo.lock",
    "yarn.lock",
    "pnpm-lock.yaml",
    "package-lock.json",
    "poetry.lock",
    "uv.lock",
    "requirements.txt",
    "requirements-dev.txt",
    ".env",
    ".env.example",
    ".env.local",
}

_DOC_EXTENSIONS = {
    ".md",
    ".rst",
    ".txt",
    ".adoc",
    ".textile",
}

_DATA_EXTENSIONS = {
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".csv",
    ".tsv",
    ".sql",
    ".graphql",
    ".gql",
}

_VENDOR_DIR_MARKERS = {
    "node_modules",
    "vendor",
    "venv",
    ".venv",
    "env",
    ".env",
    "__pycache__",
    ".tox",
    ".nox",
    "dist",
    "build",
    "target",
    ".git",
    ".hg",
    ".svn",
}

_GENERATED_MARKERS = {
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dylib",
    "*.dll",
    "*.o",
    "*.a",
    "*.lib",
    "*.exe",
    "*.bin",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "go.sum",
    "poetry.lock",
    "uv.lock",
}


class RepoInventoryResult(TypedDict, total=False):
    """Result of repo_file_inventory analysis."""

    total_files: int
    by_extension: dict[str, int]
    by_category: dict[str, int]
    language_signals: list[str]
    config_files_found: list[str]
    hidden_files: int
    generated_candidates: list[str]
    vendor_candidates: list[str]
    suspicious_paths: list[str]
    largest_files: list[dict[str, Any]]
    duplicate_hashes: list[list[str]]
    total_size: int | None
    truncation_warning: bool


def _classify_path(path: str) -> str:
    """Classify a file path into a category."""
    basename = os.path.basename(path)
    _, ext = os.path.splitext(basename)

    if basename in _CONFIG_FILENAMES and basename != ".env":
        return "config"

    if basename.startswith(".") and basename.count(".") == 1 and not ext:
        return "hidden"

    if ext in _SOURCE_EXTENSIONS:
        parts = path.replace("\\", "/").split("/")
        for part in parts:
            if part.lower() in _TEST_DIR_MARKERS:
                return "test"
        if basename.endswith((".test.js", ".test.ts", ".spec.js", ".spec.ts", "_test.py")):
            return "test"
        return "source"

    if basename.startswith("."):
        return "config"

    if ext in _DOC_EXTENSIONS:
        return "doc"

    if ext in _DATA_EXTENSIONS:
        return "data"

    return "other"


def _detect_language_signals(paths: list[str]) -> list[str]:
    """Detect programming language/ecosystem signals from file extensions."""
    ext_counter: Counter[str] = Counter()
    for path in paths:
        _, ext = os.path.splitext(path)
        if ext:
            ext_counter[ext.lower()] += 1

    signals: list[str] = []

    py_count = sum(ext_counter.get(e, 0) for e in (".py", ".pyx", ".pxd"))
    if py_count:
        signals.append("python")

    js_count = sum(ext_counter.get(e, 0) for e in (".js", ".jsx"))
    ts_count = sum(ext_counter.get(e, 0) for e in (".ts", ".tsx"))
    if js_count or ts_count:
        signals.append("javascript" if js_count >= ts_count else "typescript")

    rust_count = ext_counter.get(".rs", 0)
    if rust_count:
        signals.append("rust")

    go_count = ext_counter.get(".go", 0)
    if go_count:
        signals.append("go")

    java_count = ext_counter.get(".java", 0)
    if java_count:
        signals.append("java")

    c_count = sum(ext_counter.get(e, 0) for e in (".c", ".h", ".cpp", ".hpp", ".cc", ".cxx"))
    if c_count:
        signals.append("c_cpp")

    rb_count = ext_counter.get(".rb", 0)
    if rb_count:
        signals.append("ruby")

    swift_count = ext_counter.get(".swift", 0)
    if swift_count:
        signals.append("swift")

    return signals


def _detect_suspicious_paths(paths: list[str]) -> list[str]:
    """Detect suspicious patterns in file paths."""
    suspicious: list[str] = []

    for path in paths:
        if len(path) > _MAX_PATH_LENGTH:
            suspicious.append(f"Oversized path ({len(path)} chars): {path[:100]}...")
            continue

        has_control = any(ord(c) < 32 or ord(c) == 127 for c in path)
        if has_control:
            suspicious.append(f"Control characters in path: {path[:100]}")

        if "\u200b" in path or "\u200c" in path or "\u200d" in path or "\ufeff" in path:
            suspicious.append(f"Zero-width/BOM characters in path: {path[:100]}")

        parts = path.replace("\\", "/").split("/")
        vendor_depth = 0
        for part in parts:
            if part in _VENDOR_DIR_MARKERS:
                vendor_depth += 1
        if vendor_depth > 2:
            suspicious.append(
                f"Deeply nested vendor directory ({vendor_depth} levels): {path[:100]}"
            )

    return suspicious


def _detect_vendor_candidates(paths: list[str]) -> list[str]:
    """Detect paths that appear to be in vendor directories."""
    candidates: list[str] = []
    for path in paths:
        parts = path.replace("\\", "/").split("/")
        for part in parts:
            if part in _VENDOR_DIR_MARKERS:
                candidates.append(path)
                break
    return candidates


def _detect_generated_candidates(paths: list[str]) -> list[str]:
    """Detect paths that appear to be generated files."""
    candidates: list[str] = []
    for path in paths:
        basename = os.path.basename(path)
        _, ext = os.path.splitext(basename)

        if basename in _GENERATED_MARKERS:
            candidates.append(path)
            continue
        if ext in (".pyc", ".pyo", ".so", ".dylib", ".dll", ".o", ".a", ".exe", ".bin"):
            candidates.append(path)
            continue
        if basename.startswith("__pycache__"):
            candidates.append(path)

    return candidates


def repo_file_inventory(
    paths: list[str],
    sizes: dict[str, int] | None = None,
    hashes: dict[str, str] | None = None,
) -> RepoInventoryResult:
    """Analyze file inventory for repo structure signals.

    Accepts a list of file paths from the harness (no filesystem reads)
    and produces deterministic summaries of language/ecosystem signals,
    file counts by category, and suspicious patterns.

    Args:
        paths: List of file paths to analyze.
        sizes: Optional mapping of path to file size in bytes.
        hashes: Optional mapping of path to content hash.

    Returns:
        RepoInventoryResult with analysis details.
    """
    if not isinstance(paths, list):
        return RepoInventoryResult(
            total_files=0,
            by_extension={},
            by_category={},
            language_signals=[],
            config_files_found=[],
            hidden_files=0,
            generated_candidates=[],
            vendor_candidates=[],
            suspicious_paths=[],
            largest_files=[],
            duplicate_hashes=[],
            total_size=None,
            truncation_warning=False,
        )

    truncation_warning = len(paths) > _MAX_PATHS
    if truncation_warning:
        paths = paths[:_MAX_PATHS]

    non_str = [i for i, p in enumerate(paths) if not isinstance(p, str)]
    if non_str:
        paths = [p for p in paths if isinstance(p, str)]

    ext_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    config_files: list[str] = []
    hidden_count = 0
    total_size: int = 0

    for path in paths:
        _, ext = os.path.splitext(path)
        if ext:
            ext_counter[ext.lower()] += 1

        cat = _classify_path(path)
        category_counter[cat] += 1

        basename = os.path.basename(path)
        if basename in _CONFIG_FILENAMES:
            config_files.append(path)

        if cat == "hidden":
            hidden_count += 1

        if sizes and path in sizes:
            total_size += sizes[path]

    language_signals = _detect_language_signals(paths)
    suspicious = _detect_suspicious_paths(paths)
    vendor_candidates = _detect_vendor_candidates(paths)
    generated_candidates = _detect_generated_candidates(paths)

    largest_files: list[dict[str, Any]] = []
    if sizes:
        sorted_sizes = sorted(sizes.items(), key=lambda x: x[1], reverse=True)
        for path, size in sorted_sizes[:10]:
            largest_files.append({"path": path, "size": size})

    duplicate_groups: list[list[str]] = []
    if hashes:
        hash_to_paths: dict[str, list[str]] = {}
        for path, h in hashes.items():
            hash_to_paths.setdefault(h, []).append(path)
        for h, group in hash_to_paths.items():
            if len(group) > 1:
                duplicate_groups.append(sorted(group))

    return RepoInventoryResult(
        total_files=len(paths),
        by_extension=dict(ext_counter.most_common()),
        by_category=dict(category_counter),
        language_signals=language_signals,
        config_files_found=config_files,
        hidden_files=hidden_count,
        generated_candidates=generated_candidates,
        vendor_candidates=vendor_candidates,
        suspicious_paths=suspicious,
        largest_files=largest_files,
        duplicate_hashes=duplicate_groups,
        total_size=total_size if sizes else None,
        truncation_warning=truncation_warning,
    )
