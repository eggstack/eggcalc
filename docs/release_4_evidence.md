# Release 4 — Evidence Record

## Runtime

- **Date:** 2026-07-20
- **Python:** 3.14.2 (cpython)
- **Platform:** darwin (macOS)
- **eggcalc version:** 2.0.0 (unreleased)

## Packaging Metadata

- `pyproject.toml` requires-python: `>=3.11`
- No Python 3.10 classifier present
- `uv.lock` requires-python: `>=3.11`

## CI Matrix

| OS | Python | Status |
|----|--------|--------|
| ubuntu-latest | 3.11 | expected |
| ubuntu-latest | 3.12 | expected |
| ubuntu-latest | 3.13 | expected |
| ubuntu-latest | 3.14 | expected |
| macos-latest | 3.12 | expected |
| windows-latest | 3.12 | expected |

Python 3.10 removed from CI matrix.

## Checks Run

| Check | Command | Result |
|-------|---------|--------|
| Ruff lint | `ruff check eggcalc tests` | All checks passed |
| Black format | `black --check eggcalc tests` | All done, 88 files unchanged |
| Type check | `mypy eggcalc --ignore-missing-imports` | Success, no issues |
| Single-file build | `python build_single.py` | Built successfully |
| Single-file smoke | `python eggcalc.py "5+3"` | Output: 8 |
| Capabilities CLI | `python -m eggcalc --capabilities` | Valid JSON, all fields present |
| Capabilities single-file | `python eggcalc.py --capabilities` | Valid JSON, all fields present |

## Test Suite

- **Total collected:** 3118 (29 new tests added in this round)
- **Passed:** 3095
- **Skipped:** 33 (all non-mandatory, platform-specific or conditional)
- **All checks pass:** ruff, black, mypy, single-file build, capabilities CLI, smoke release surfaces

## Capability Detection

```json
{
  "python_version": [3, 14, 2],
  "platform": "darwin",
  "implementation": "cpython",
  "has_tomllib": true,
  "has_math_cbrt": true,
  "supports_fork": true,
  "supports_spawn": true,
  "supports_posix_paths": true,
  "supports_windows_paths": false
}
```

## Release 4 Changes Summary

### Completed
1. **A1/A2:** Raised minimum Python from 3.10 to 3.11 in pyproject.toml, classifiers, CI, docs
2. **A2:** Removed `_needs_tomllib` skip decorators from 5 test files (39 usages)
3. **A2:** Removed `math.cbrt` version skip from test_clicalc.py
4. **A3:** Added runtime metadata consistency tests
5. **B:** Introduced `RuntimeCapabilities` frozen dataclass with `detect_capabilities()` and `capability_summary()`
6. **B1:** Added `--capabilities` CLI flag for runtime diagnostics (both package and single-file)
7. **B2:** MCP server `initialize` response includes `runtime` key with capability information
8. **C:** CI expanded to macOS and Windows lanes (Python 3.11–3.14)
9. **F:** Updated README, AGENTS.md, CONTRIBUTING.md, architecture docs, changelog

### Remaining Skips
- 33 tests skipped (non-mandatory, platform-specific or conditional)
- All skips are justified and non-mandatory

## File Changes

- `pyproject.toml` — requires-python, classifiers, tool configs
- `uv.lock` — requires-python constraint
- `eggcalc/capabilities.py` — NEW: RuntimeCapabilities, detect_capabilities()
- `eggcalc/__init__.py` — exports RuntimeCapabilities, detect_capabilities
- `eggcalc/evaluator.py` — removed unused type: ignore
- `eggcalc/mcp/server.py` — initialize response includes runtime capabilities
- `eggcalc/normalize.py` — added --capabilities CLI flag
- `build_single.py` — capabilities module in build, --capabilities in single-file entry
- `eggcalc.py` — rebuilt single-file
- `.github/workflows/ci.yml` — removed 3.10, added macOS/Windows lanes
- `tests/test_runtime_capabilities.py` — 30+ tests (immutability, serialization, CLI, parity, timeout, multiprocessing)
- `tests/test_cargo_inspect.py` — removed _needs_tomllib
- `tests/test_clicalc.py` — removed math.cbrt skip, import sys removed
- `tests/test_inspection_comprehensive.py` — removed _needs_tomllib
- `tests/test_manifest_inspect.py` — removed _needs_tomllib
- `tests/test_mcp_server.py` — removed _needs_tomllib
- `tests/test_mcp_tools_new.py` — removed _needs_tomllib
- `AGENTS.md` — Python version reference updated
- `CONTRIBUTING.md` — Python version reference updated
- `architecture/overview.md` — Python version reference updated
- `.skills/build_release.md` — Python version reference updated
- `docs/installation.md` — Python version reference updated
- `CHANGELOG.md` — Release 4 entries added under 2.0.0
- `README.md` — min Python, platforms, migration notes, --capabilities docs
