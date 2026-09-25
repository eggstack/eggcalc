# AGENTS.override.md

## Session-Specific Overrides and Extensions

This file contains overrides and additions specific to this codebase. Items here take precedence over AGENTS.md.

### Build Single File Convention

Runtime code must live in the seven core modules (`_process.py`, `units.py`, `evaluator.py`, `_protocol.py`, `normalize.py`, `capabilities.py`, `cli.py`), `exact/`, or `mcp/` — anything else breaks the single-file build. `__main__.py` is a thin entry point, not in the build manifest. The `normalize_main` / `mcp_main` aliases are created by `build_single.py` during assembly and do not exist in source — never reference them in source or tests.

### Evaluation Paths

- `run()` normalizes first, so it handles natural language AND unit conversions.
- `evaluate()` handles only valid Python syntax (no normalization).
- When testing NL or unit features, use `run()`, `evaluate_raw()`, or the CLI — NOT `evaluate()`.

### Unit Aliases

Prefixed units like `kN`, `mV`, `mA` map to themselves in `UNIT_ALIASES`. Word forms like `kilonewton` alias to the prefixed form (e.g., `"kilonewton": "kN"`). This is correct — the word form converts to the symbol form, which then converts normally.

### exact/ Module Organization

- `confusables.py` is auto-generated (compressed payload, lazy mapping decoded on first access). Edit `scripts/generate_confusables.py`, never the data file.
- `network.py`, `encoding.py`, and `temporal.py` are standalone leaves: stdlib-only, no `exact/` deps.
- `CodecConvertResult` uses functional `TypedDict(...)` syntax because `from` is a Python keyword; its params are `from_format`/`to_format`.
- TypedDict classes live in their logical modules (validate.py, measure.py, unicode_tools.py, etc.), NOT in confusables.py.
- `reverse_confusables()` lives in `unicode_tools.py`, alongside `confusables_count()`.

### Stable Display and Classification Contracts

- In `visible_repr()`, the variation-selector check (U+FE00–U+FE0F) comes BEFORE the combining-mark check. This ordering is intentional per Unicode display recommendations.
- `accent_or_diacritic_difference` from `_classify_difference()` is reachable (NFC-equal strings can differ after casefold when precomposed meets decomposed).

### TypedDict Field Vocabulary

- Results are plain-dict TypedDicts: use `result["equal"]`, never `result.equal`. Exception: `codepoints()` items are `CodepointInfo` named tuples (`cp.idx`).
- `ConfusableInfo` uses `confusable_with` / `confusable_name`. `ScriptInfo` uses `index`, `char`, `script`, `codepoint`. `detect_mixed_scripts()` returns `mixed_scripts` / `scripts` / `positions`. `CommonPrefixSuffix` uses `common_prefix_len` / `common_suffix_len`.
- `validate.py` input limits: `MAX_TEXT_INPUT_length` (bracket/JSON checks) and `MAX_SAMPLE_LENGTH` (regex samples) raise `ValueError` when exceeded, consistent with the MCP layer's `MAX_TEXT_LENGTH`.
- Single authorities: `json_extract()` in `validate.py` owns RFC 6901 traversal (`json_query` is a deprecated compat adapter); `exact/version.py` owns SemVer (`parse_version`/`compare_versions`). Field vocab and finding codes (`code`/`severity`/`message`/`line`/`column`) follow `architecture/authority_inventory.md` — verify against code, never invent names.

### Plan Reference

Planning conventions follow `plans/README.md` and `plans/003-planning-process.md` (codegg-style hierarchy). Active work is tracked in `plans/registry.md`; legacy flat plans live in `plans/archive/legacy/` and are not authoritative. Verification and release policy is defined in AGENTS.md and docs/releasing.md.
