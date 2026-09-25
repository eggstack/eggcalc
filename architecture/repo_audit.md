# repo_audit.py — Repository File Inventory

422 lines. Deterministic repository file-inventory analysis with zero
filesystem access.

## Table of Contents

- [Overview](#overview)
- [Type Definitions](#type-definitions)
- [Constants / Limits](#constants--limits)
- [Public Functions](#public-functions)
  - [repo_file_inventory](#repo_file_inventory)
- [Internal Helpers](#internal-helpers)
- [Dependencies](#dependencies)
- [Security Notes](#security-notes)
- [See Also](#see-also)

## Overview

Analyzes a caller-supplied file list (plus optional size/hash maps) for
repository structure signals: per-extension and per-category counts,
language/ecosystem signals, config files found, hidden-file count,
vendor and generated candidates, suspicious paths, largest files, and
duplicate content hashes. Purely lexical — the module never touches the
filesystem; inventories produced by `git ls-files`, `find`, or an agent's
directory walk are passed in.

## Type Definitions

```python
class RepoInventoryResult(TypedDict, total=False):
    total_files: int
    by_extension: dict[str, int]       # ".py" → 3 (extensionless → "")
    by_category: dict[str, int]        # source | test | doc | config | data | hidden | other
    language_signals: list[str]        # e.g. ["python", "javascript"]
    config_files_found: list[str]      # matched _CONFIG_FILENAMES entries
    hidden_files: int                  # count of "hidden"-category paths (bare dotfiles like .env)
    generated_candidates: list[str]    # build artifacts, bundles, __pycache__
    vendor_candidates: list[str]       # node_modules, vendor, .git, dist, ...
    suspicious_paths: list[str]        # oversized / control-char / zero-width / deep-vendor
    largest_files: list[dict[str, Any]]  # [{"path","size"}], descending, top 10
    duplicate_hashes: list[list[str]]  # hash groups with >1 path
    total_size: int | None             # sum of sizes (None when sizes=None)
    truncation_warning: bool           # True when input exceeded _MAX_PATHS
```

## Constants / Limits

```python
_MAX_PATHS = 50_000        # longer lists are truncated (sets truncation_warning)
_MAX_PATH_LENGTH = 1_000   # longer paths → suspicious, still counted

_SOURCE_EXTENSIONS = {...}  # .py .js .ts .go .rs .java ... → "source" (+language signal)
_TEST_EXTENSIONS = {".test.js", ".test.ts", ".test.py", ".spec.js", ".spec.ts"}
_TEST_DIR_MARKERS = {"test", "tests", "__tests__", "spec", "specs", "testing"}
_CONFIG_FILENAMES = {...}   # setup.cfg, pyproject.toml, package.json, Dockerfile, ...
_DOC_EXTENSIONS = {...}     # .md .rst .txt ...
_DATA_EXTENSIONS = {...}    # .json .csv .yaml ...
_VENDOR_DIR_MARKERS = {...} # node_modules, vendor, .git, dist, third_party, ...
_GENERATED_MARKERS = {...}  # bundle.js, *.min.js, __pycache__, *.pyc, *.exe, ...
```

Category precedence in `_classify_path`: config filename → bare-dotfile
(`.env`-style: starts with `.`, exactly one dot, no extension) → test
(extension or directory marker) → source → dot-prefixed-with-extension
→ doc → data → other. Note `.env` is deliberately excluded from config
filenames, so it lands in `hidden`.

## Public Functions

### `repo_file_inventory`

```python
def repo_file_inventory(
    paths: list[str],
    sizes: dict[str, int] | None = None,
    hashes: dict[str, str] | None = None,
) -> RepoInventoryResult
```

```python
repo_file_inventory(["src/main.py", "src/util.py", "tests/test_main.py",
                     "README.md", "node_modules/x/y.js", "setup.cfg"])
# → {"total_files": 6,
#     "by_category": {"source": 3, "test": 1, "doc": 1, "config": 1},
#     "language_signals": ["python", "javascript"],
#     "config_files_found": ["setup.cfg"],
#     "vendor_candidates": ["node_modules/x/y.js"], ...}

repo_file_inventory(["a.py", "b.py"], sizes={"a.py": 100, "b.py": 9000})
# → {"largest_files": [{"path": "b.py", "size": 9000},
#                      {"path": "a.py", "size": 100}],
#     "total_size": 9100, ...}

repo_file_inventory(["a.py", "b.py"], hashes={"a.py": "H1", "b.py": "H1"})
# → {"duplicate_hashes": [["a.py", "b.py"]], ...}
```

`suspicious_paths` is deliberately narrow (verified): oversized paths
(>1,000 chars), control characters, zero-width/BOM characters, and
vendor nesting deeper than 2 levels. Secrets (`id_rsa`), binaries, and
dotfiles are categorized elsewhere, not flagged here.

## Internal Helpers

| Helper | Role |
|--------|------|
| `_classify_path(path)` | Path → category (config → hidden → test → source → … → other) |
| `_detect_language_signals(paths)` | Extension → language/ecosystem list |
| `_detect_suspicious_paths(paths)` | Oversized / control-char / zero-width / deep-vendor scan |
| `_detect_vendor_candidates(paths)` | Any segment in `_VENDOR_DIR_MARKERS` |
| `_detect_generated_candidates(paths)` | `_GENERATED_MARKERS` basenames + compiled extensions (`.pyc`, `.exe`, `.dll`, …) |

## Dependencies

```
repo_audit.py
    └── (standard library only: os, collections, typing)
```

No `exact/` imports — fully standalone leaf (uses `os.path` basename/
splitext lexically, never filesystem I/O).

## Security Notes

- Inventory in, report out: paths are untrusted strings, but the module
  only classifies them — no opens, stats, or joins against the real
  filesystem, so symlink/path-traversal payloads are inert here.
- `suspicious_paths` is a triage aid, not a secrets scanner: it will not
  flag `id_rsa`, `.env` contents, or hardcoded credentials. Pair with
  `inspect_prompt` / `unicode_policy` for content-level review.
- 50,000-path cap with `truncation_warning`: very large monorepos get a
  prefix analysis, not a full one — check the flag before quoting
  totals.

## See Also

- [path_tools.md](path_tools.md) — lexical path normalization and scope checks
- [config.md](config.md) — `.env`/INI content validation
- [manifests.md](manifests.md) — manifest content behind the config files found here
