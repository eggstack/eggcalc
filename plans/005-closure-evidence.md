# Releases 1–3 Closure Evidence

Date: 2026-07-17
Commit: 98b7477

## Verification Matrix

| Check | Command | Result |
|-------|---------|--------|
| Ruff lint | `ruff check eggcalc tests` | PASS |
| Black format | `black --check eggcalc tests` | PASS |
| Build single-file | `python build_single.py` | PASS |
| Single-file smoke | `python eggcalc.py "5+3"` | PASS |
| Full test suite | `python -m pytest tests/ -v` | PASS |
| Type check | `mypy eggcalc --ignore-missing-imports` | PASS |

## Test Summary

3047 passed, 32 skipped, 598 warnings in 132.33s

## Closure Outcomes Achieved

1. Release 1 calculator semantics consistent across package, CLI, single-file, and public APIs
2. MCP stdio server supports `2025-11-25` with backward compatibility for `2024-11-05`
3. MCP initialization validates required fields and records negotiated client metadata
4. Cargo findings distinguish non-ASCII, mixed-script, and confusable collisions
5. Inspection results preserve structured finding contract and are JSON serializable
6. Reproducible verification record demonstrates all checks pass
7. Documentation accurately states supported protocol versions and syntax contracts

## Changes Made

- `eggcalc/mcp/server.py`: Added `2025-11-25` protocol support, tightened initialization validation, added deprecation warning for sessionless path
- `eggcalc/exact/cargo.py`: Replaced codepoint-range heuristic with proper confusable detection, added distinct finding codes
- `tests/test_mcp_server.py`: Added lifecycle, validation, error conformance, and protocol version tests
- `tests/test_mcp_stdio_smoke.py`: Updated transcripts for `2025-11-25`, added backward compatibility test
- `tests/test_cargo_inspect.py`: Added Unicode/confusable fixtures and inspection contract tests
- `tests/test_mcp_resource_bounds.py`: Updated for new resource bound tests
- `tests/conftest.py`: Fixed `importlib.reload()` test interference by saving/restoring `McpSession` and `McpSessionState` class references
- `architecture/normalize.md`: Fixed stale `^` → XOR mapping documentation
- `docs/natural-language.md`: Fixed stale XOR operator table entry
- `docs/mcp.md`: Updated protocol version, lifecycle, and deprecation notes
- `architecture/mcp.md`: Updated protocol version and sessionless deprecation
- `README.md`: Updated MCP protocol version claim
- `AGENTS.md`: Updated protocol version and sessionless deprecation
- `CHANGELOG.md`: Added Release 2.0.0 entries

## Residual Limitations

None. All acceptance criteria in the closure plan are met.
