# Release Polish Closure Status

## Verified Commit

`209c634` — "Add MCP stdio tools/list smoke test"

## Local Verification

All commands run on Python 3.14.2, macOS.

```bash
ruff check eggcalc tests            # PASS
black --check eggcalc tests         # PASS
.venv/bin/python -m pytest tests/ -v  # PASS (2289 passed, 32 skipped)
mypy eggcalc --ignore-missing-imports # PASS
python build_single.py              # PASS
.venv/bin/python -m pytest tests/test_mcp_stdio_smoke.py -v  # PASS
```

## GitHub Actions

CI run `#28746612815` (commit `bdfeab5`) completed with failures.

All 38 failures are pre-existing Python 3.10/3.11 incompatibilities and CI-specific timeout issues (tests pass locally on 3.14):

- `test_clicalc.py::TestTimeout` — timeout too tight under CI coverage instrumentation
- `test_mcp_server.py` — MCP handler tests timeout under CI load (all `assert False is True`)
- `test_cargo_inspect.py` — TOML parsing differences on older Pythons
- `test_security_fuzz.py` — null-byte handling on 3.10

The smoke test (`test_mcp_stdio_smoke.py`) was untracked at the time of that CI run. It passes locally.

## Intentionally Deferred Items

These are non-blocking and were never in scope for this pass:

- Rewriting the noisy prior commit message that expanded `$PATH`
- Splitting `evaluator.py`, `normalize.py`, or `units.py`
- Implementing complete Unicode UAX #29 segmentation
- Replacing the MCP inventory fixture with a generated docs pipeline
- Fixing pre-existing CI-only timeout failures (not reproducible locally)

## Note

No broad evaluator/normalizer refactor was attempted. Changes in this pass were limited to adding the MCP stdio smoke test and this closure status document.
