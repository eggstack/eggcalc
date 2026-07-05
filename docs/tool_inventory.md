# MCP Tool Inventory

Canonical reference for all MCP tools exposed by `eggcalc.mcp.server.TOOL_HANDLERS`.

**Total: 64 tools**

## Inventory Table

| # | Tool Name | Category | Tier | Implemented | README | docs/mcp.md | Tests | Notes |
|---|-----------|----------|------|-------------|--------|-------------|-------|-------|
| 1 | `argv_compare` | shell | 2 | yes | no | yes | yes | Compare argv lists or command strings by parsed argv |
| 2 | `cargo_toml_inspect` | cargo | 3 | yes | no | yes | yes | Inspect Cargo.toml text (package, workspace, deps) |
| 3 | `canonicalize_text` | unicode | 2 | yes | no | yes | yes | Apply named text canonicalization profile |
| 4 | `code_fence_extract` | markdown | 2 | yes | no | yes | yes | Extract fenced code blocks with line ranges and fingerprints |
| 5 | `command_preflight` | shell | 1 | yes | no | yes | yes | Composite: analyze command before execution |
| 6 | `config_preflight` | config | 1 | yes | no | yes | yes | Composite: validate config text with format auto-detect |
| 7 | `constant_lookup` | math | 2 | yes | no | yes | yes | Physical constant lookup (avogadro, planck, etc.) |
| 8 | `dotenv_validate` | config | 2 | yes | no | yes | yes | Validate .env key=value text with duplicate and expansion detection |
| 9 | `edit_preflight` | patch | 1 | yes | no | yes | yes | Composite: validate edit before applying (replace/patch/line_range) |
| 10 | `escape_text` | text | 1 | yes | no | yes | yes | Escape text for various output formats |
| 11 | `glob_match` | path | 1 | yes | no | yes | yes | Match glob pattern against path |
| 12 | `identifier_analyze` | identifier | 3 | yes | no | yes | yes | Classify identifier naming conventions |
| 13 | `identifier_inspect` | identifier | 1 | yes | no | yes | yes | Detect confusables/collisions in identifiers |
| 14 | `identifier_table_inspect` | identifier | 3 | yes | no | yes | yes | Table-level identifier collision, keyword, and style analysis |
| 15 | `ini_validate` | config | 2 | yes | no | yes | yes | Validate INI config with section and duplicate detection |
| 16 | `json_canonicalize` | json | 1 | yes | no | yes | yes | Deterministic JSON formatting with stable hashes |
| 17 | `json_compare` | json | 1 | yes | no | yes | yes | Semantic JSON comparison |
| 18 | `json_extract` | json | 2 | yes | no | yes | yes | JSON Pointer extraction (RFC 6901) |
| 19 | `json_query` | json | 1 | yes | no | yes | yes | JSON Pointer query (RFC 6901) |
| 20 | `json_shape` | json | 3 | yes | no | yes | yes | Analyze JSON structure without values |
| 21 | `line_range_compare` | text | 2 | yes | no | yes | yes | Compare line ranges from two texts |
| 22 | `line_range_extract` | text | 1 | yes | no | yes | yes | Extract line ranges with offsets and fingerprints |
| 23 | `list_compare` | list | 2 | yes | yes | yes | yes | List comparison (ordered/set/multiset) |
| 24 | `list_dedupe` | list | 1 | yes | no | yes | yes | Deduplicate list with normalization support |
| 25 | `list_sort` | list | 1 | yes | no | yes | yes | Sort list with normalization support |
| 26 | `markdown_structure` | markdown | 2 | yes | no | yes | yes | Markdown document structure analysis |
| 27 | `math_eval` | math | 0 | yes | yes | yes | yes | Evaluate math expressions with NL/unit support |
| 28 | `patch_apply_check` | patch | 2 | yes | no | yes | yes | Validate and simulate unified diff application |
| 29 | `patch_summary` | patch | 2 | yes | no | yes | yes | Summarize unified diff without applying |
| 30 | `path_analyze` | path | 2 | yes | no | yes | yes | Lexical path analysis (no filesystem) |
| 31 | `path_compare` | path | 2 | yes | no | yes | yes | Compare paths under normalization rules |
| 32 | `path_normalize` | path | 0 | yes | no | yes | yes | Normalize path with platform semantics |
| 33 | `path_scope_check` | path | 2 | yes | no | yes | yes | Lexical scope check (no symlink resolution) |
| 34 | `prompt_input_inspect` | text | 2 | yes | no | yes | yes | Detect prompt injection (hidden chars, instruction phrases, ANSI escapes) |
| 35 | `regex_finditer` | regex | 1 | yes | no | yes | yes | Find all regex matches with positions |
| 36 | `regex_safety_check` | regex | 1 | yes | no | yes | yes | Check regex for catastrophic backtracking |
| 37 | `shell_quote_join` | shell | 2 | yes | no | yes | yes | Safely quote argv tokens into shell string |
| 38 | `shell_split` | shell | 2 | yes | no | yes | yes | Parse shell command into argv with risk detection |
| 39 | `structured_data_compare` | json | 2 | yes | no | yes | yes | Composite: compare JSON data with diffs and shape analysis |
| 40 | `text_count` | text | 0 | yes | yes | yes | yes | Character counting and frequency table |
| 41 | `text_diff_explain` | text | 1 | yes | yes | yes | yes | Explain string differences with codepoints |
| 42 | `text_equal` | text | 0 | yes | yes | yes | yes | String comparison with normalization modes |
| 43 | `text_fingerprint` | text | 0 | yes | no | yes | yes | Deterministic SHA-256 fingerprint |
| 44 | `text_hash` | text | 2 | yes | no | yes | yes | Cryptographic hash computation |
| 45 | `text_inspect` | text | 1 | yes | yes | yes | yes | Hidden characters, confusables, mixed scripts |
| 46 | `text_measure` | text | 0 | yes | yes | yes | yes | Comprehensive text metrics |
| 47 | `text_position` | text | 2 | yes | no | yes | yes | Position conversion (byte/cp/line/UTF-16) |
| 48 | `text_replace_check` | text | 1 | yes | no | yes | yes | Pre-edit replacement safety check |
| 49 | `text_security_inspect` | text | 1 | yes | no | yes | yes | Composite security text hygiene (verdict, findings, machine codes) |
| 50 | `text_truncate` | text | 3 | yes | no | yes | yes | Best-effort grapheme-aware truncation |
| 51 | `text_transform` | text | 2 | yes | no | yes | yes | Unicode normalization, casefold, trim, etc. |
| 52 | `text_window` | text | 1 | yes | no | yes | yes | Context window around a text position |
| 53 | `toml_shape` | toml | 2 | yes | no | yes | yes | TOML structure analysis |
| 54 | `unescape_text` | text | 1 | yes | no | yes | yes | Unescape text from various formats |
| 55 | `unicode_policy_check` | unicode | 2 | yes | no | yes | yes | Apply named Unicode safety policy to text |
| 56 | `unit_convert` | math | 2 | yes | no | yes | yes | Unit conversion with factors |
| 57 | `unit_info` | math | 2 | yes | no | yes | yes | Unit metadata (canonical, category) |
| 58 | `validate_brackets` | validation | 1 | yes | yes | yes | yes | Bracket balance checking |
| 59 | `validate_json` | validation | 0 | yes | yes | yes | yes | JSON parsing validation |
| 60 | `validate_regex` | regex | 1 | yes | yes | yes | yes | Regex pattern testing against samples |
| 61 | `validate_schema_light` | validation | 3 | yes | no | yes | yes | Light JSON schema validation |
| 62 | `validate_toml` | validation | 1 | yes | no | yes | yes | TOML parsing validation |
| 63 | `version_compare` | version | 2 | yes | no | yes | yes | Version string comparison (semver/pep440/loose) |
| 64 | `version_constraint_check` | version | 3 | yes | no | yes | yes | Check if version satisfies constraint (semver/cargo) |

## Legend

- **Tier 0**: Ultra-common, small-schema tools - always available
- **Tier 1**: Default coding-agent sanity tools - low context, recommended default
- **Tier 2**: Heavier analysis tools - moderate context, opt-in for text/unicode/config work
- **Tier 3**: Domain-specific tools - more context, opt-in for specialized workflows

## Summary Statistics

| Field | Count |
|-------|-------|
| Total tools | 64 |
| Documented in README | 10 |
| Documented in docs/mcp.md | 64 |
| Missing from docs/mcp.md | 0 |
| Have tests | 64 |
| Missing tests | 0 |

## Category Breakdown

| Category | Tools |
|----------|-------|
| config | `dotenv_validate`, `ini_validate`, `config_preflight` |
| math | `math_eval`, `unit_convert`, `unit_info`, `constant_lookup` |
| patch | `patch_apply_check`, `patch_summary`, `edit_preflight` |
| text | `text_measure`, `text_equal`, `text_diff_explain`, `text_inspect`, `text_count`, `text_truncate`, `text_transform`, `text_position`, `text_hash`, `text_window`, `text_fingerprint`, `escape_text`, `unescape_text`, `text_replace_check`, `line_range_extract`, `line_range_compare`, `prompt_input_inspect`, `text_security_inspect` |
| json | `json_compare`, `json_extract`, `json_shape`, `json_canonicalize`, `json_query`, `structured_data_compare` |
| validation | `validate_brackets`, `validate_json`, `validate_regex`, `validate_toml`, `validate_schema_light` |
| regex | `regex_finditer`, `regex_safety_check` |
| list | `list_compare`, `list_dedupe`, `list_sort` |
| path | `path_normalize`, `path_analyze`, `path_compare`, `path_scope_check`, `glob_match` |
| identifier | `identifier_analyze`, `identifier_inspect`, `identifier_table_inspect` |
| shell | `shell_split`, `shell_quote_join`, `argv_compare`, `command_preflight` |
| markdown | `markdown_structure`, `code_fence_extract` |
| version | `version_compare`, `version_constraint_check` |
| toml | `toml_shape` |
| cargo | `cargo_toml_inspect` |
| unicode | `unicode_policy_check`, `canonicalize_text` |

## Source of Truth

The canonical tool list lives in `tests/fixtures/mcp_tool_registry_expected.json`.
The test at `tests/test_tool_inventory.py` enforces that `TOOL_HANDLERS` keys match this fixture.
