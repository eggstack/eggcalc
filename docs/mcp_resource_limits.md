# MCP Resource Limits Audit

This document tracks resource bounds for every MCP tool. Generated from `TOOL_HANDLERS` and `TOOL_SCHEMAS` in the codebase.

## Server-Level Limits

| Limit | Value | Env Var | Description |
|-------|-------|---------|-------------|
| `MAX_REQUEST_BYTES` | 1,000,000 | `EGGCALC_MCP_MAX_REQUEST_BYTES` | Max size of a single JSON-RPC request body (clamped 1K–100M) |
| `MAX_OUTPUT_BYTES` | 1,000,000 | `EGGCALC_MCP_MAX_OUTPUT_BYTES` | Max size of a tool response payload (clamped 1K–100M) |
| `MAX_REQUESTS_PER_SECOND` | 10 | `EGGCALC_MCP_MAX_REQUESTS_PER_SECOND` | Rate limit for incoming requests (clamped 0.1–1000) |
| `MAX_REQUEST_ID_LENGTH` | 1024 | — | Hard-coded max length for JSON-RPC `id` field |
| `MAX_TOOL_TIMEOUT_SECONDS` | 30 | `EGGCALC_MCP_MAX_TOOL_TIMEOUT_SECONDS` | Timeout for tool invocations (clamped 1–300) |
| `MAX_CANCELLED_REQUESTS` | 10,000 | `EGGCALC_MCP_MAX_CANCELLED_REQUESTS` | FIFO cap for tracking cancelled request IDs (clamped 100–1M) |

Additional server constants:

| Constant | Value | Env Var | Description |
|----------|-------|---------|-------------|
| `_MAX_TOOL_WORKERS` | 16 | `EGGCALC_MCP_MAX_TOOL_WORKERS` | Max threads in the bounded tool executor pool (1–128) |
| `EGGCALC_NO_CONFIG` | `"1"` | `EGGCALC_NO_CONFIG` | Always set to `"1"` at MCP server startup; prevents loading cwd-local config |
| `_active_profile` | `"full"` | `EGGCALC_MCP_PROFILE` | Active tool profile for filtering |
| `_schema_detail` | `"full"` | `EGGCALC_MCP_SCHEMA_DETAIL` | Schema detail level (compact, normal, full) |

## Tool-Level Limits (module constants in `tools.py`)

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_TEXT_LENGTH` | 100,000 | Global max length for string inputs (used by `_require_str`) |
| `MAX_EXPRESSION_LENGTH` | 10,000 | Max length for `math_eval` expression strings |
| `MAX_LIST_ITEMS` | 10,000 | Max items in list/array inputs (used by `_validate_str_list`) |
| `MAX_PAIRWISE_ITEMS` | 1,000 | Max items for O(N²) pairwise operations (confusables, near-match) |
| `MAX_REGEX_SAMPLES` | 100 | Max number of sample strings for `validate_regex` |
| `MAX_REGEX_SAMPLE_LENGTH` | 10,000 | Max length of a single regex sample |
| `MAX_PATTERN_LENGTH_REGEX` | 1,000 | Max regex pattern length for `validate_regex` and `regex_finditer` |
| `MAX_MATCHES_REGEX` | 100 | Default max matches for `regex_finditer` |
| `MAX_TEXT_LENGTH_REGEX` | 100,000 | Max text length for `regex_finditer` |
| `REGEX_TIMEOUT_SECONDS` | 5 | Timeout for subprocess regex execution |
| `MAX_CONCURRENT_SPAWNED` | 4 | Max concurrent child processes (semaphore) |
| `_SPAWN_ACQUIRE_TIMEOUT` | 10 | Seconds to wait for a spawn slot before failing |
| `MAX_ORPHANED_REGEX_PROCESSES` | 256 | Cap on orphaned regex child process handles |

## Tool-Level Limits (patch module)

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_ORIGINAL_LENGTH` | 200,000 | Max length for original text in `patch_apply_check` |
| `MAX_PATCH_LENGTH` | 200,000 | Max length for patch text in all patch/diff tools |

---

## Tool-Level Limits

| Tool | Category | Tier | Primary Input Fields | Max Text/Input Length | Max List Length | Max Results Returned | Worst-Case Risk | Current Mitigation | Subprocess Isolated | Existing Tests | Notes |
|------|----------|------|---------------------|----------------------|----------------|---------------------|----------------|-------------------|-------------------|---------------|-------|
| `math_eval` | math | 0 | `expression` | 10,000 | — | — | bounded | `MAX_EXPRESSION_LENGTH=10000`, `evaluate_with_timeout(t=5)`, `_SPAWN_SEMAPHORE(4)` | yes (via `evaluate_with_timeout`) | `test_mcp_server.py`, `test_mcp_tools_new.py` | Spawns child process with 5s timeout and RLIMIT_AS 256MB |
| `unit_convert` | math | 2 | `value`, `from_unit`, `to_unit` | — | — | — | bounded | Rejects NaN/inf, cross-category conversion check | no | `test_mcp_server.py` | Pure computation, no I/O |
| `unit_info` | math | 2 | `unit` | 100,000 | — | — | bounded | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py` | Dict lookup on known aliases |
| `constant_lookup` | math | 2 | `name` | 100,000 | — | — | bounded | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py` | Dict lookup on ~40 constants |
| `text_measure` | text | 0 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) single pass |
| `text_equal` | text | 0 | `a`, `b` | 100,000 each | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` × 2 | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) comparison |
| `text_diff_explain` | text | 1 | `a`, `b` | 100,000 each | — | `max_diffs` ≤ 10,000 | linear | `_require_str(MAX_TEXT_LENGTH)` × 2, `MAX_DIFFS=10000` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | Diff algorithm + bounded output |
| `text_inspect` | text | 1 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) scan for invisibles, confusables, bidi, scripts |
| `text_count` | text | 0 | `text`, `target` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)`, `MAX_TARGET_LENGTH=1000` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) character count or frequency table |
| `text_replace_check` | text | 1 | `text`, `old`, `new` | 100,000 each | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` × 3, `MAX_PREVIEW_CHARS=100000` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) find-all + bounded preview |
| `text_truncate` | text | 3 | `text`, `max_graphemes` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py` | O(n) grapheme counting + truncation |
| `text_transform` | text | 2 | `text`, `operations` | 100,000 | 100 ops max | — | linear | `_require_str(MAX_TEXT_LENGTH)`, `max 100 operations` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | Sequential passes, each O(n) |
| `text_position` | text | 2 | `text` + position args | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) line/column scan |
| `text_window` | text | 1 | `text`, `position` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)`, `MAX_CONTEXT_LINES=10000`, `position ≤ MAX_TEXT_LENGTH*16` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) position resolution + window extract |
| `text_hash` | text | 2 | `text`, `algorithms` | 100,000 | 10 algorithms max | — | linear | `_require_str(MAX_TEXT_LENGTH)`, max 10 algorithms | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) per hash algorithm |
| `text_fingerprint` | text | 0 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) canonicalization + SHA-256 |
| `text_security_inspect` | text | 1 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)`, delegates to sub-tools with their own limits | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | **Composite**: calls text_inspect + unicode_policy_check + canonicalize_text + prompt_input_inspect + identifier_inspect sequentially |
| `validate_brackets` | validation | 1 | `text`, `pairs` | 100,000 | 64 pairs max | — | linear | `_require_str(MAX_TEXT_LENGTH)`, max 64 pairs, key/value ≤ 16 chars | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) stack-based bracket matching |
| `validate_json` | validation | 0 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) JSON parse |
| `validate_regex` | regex | 1 | `pattern`, `samples` | 100,000 total chars | 100 samples, 10,000/sample | — | **exponential** | `MAX_REGEX_SAMPLES=100`, `MAX_REGEX_SAMPLE_LENGTH=10000`, `MAX_TEXT_LENGTH=100000`, `MAX_PATTERN_LENGTH_REGEX=1000`, `_regex_safety_check` pre-filter, **subprocess + RLIMIT_AS 256MB**, `_SPAWN_SEMAPHORE(4)`, 5s timeout | **yes** | `test_mcp_server.py`, `test_mcp_env_limits.py`, `test_mcp_tools_new.py` | ReDoS risk mitigated by safety check + subprocess isolation |
| `regex_finditer` | regex | 1 | `pattern`, `text` | 100,000 text, 1,000 pattern | — | `max_matches` ≤ 1,000 | **exponential** | `MAX_TEXT_LENGTH_REGEX=100000`, `MAX_PATTERN_LENGTH_REGEX=1000`, `max 1000 matches`, `_regex_safety_check` pre-filter, **subprocess + RLIMIT_AS 256MB**, `_SPAWN_SEMAPHORE(4)`, 5s timeout | **yes** | `test_mcp_server.py`, `test_mcp_env_limits.py`, `test_mcp_tools_new.py` | ReDoS risk mitigated by safety check + subprocess isolation |
| `regex_safety_check` | regex | 1 | `pattern` | 1,000 | — | — | bounded | `_require_str(MAX_TEXT_LENGTH)`, `MAX_PATTERN_LENGTH_REGEX=1000` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | Heuristic pattern analysis, no execution |
| `validate_schema_light` | validation | 3 | `text`, `schema` | 100,000 text, 100,000 schema JSON | — | — | quadratic | `_require_str(MAX_TEXT_LENGTH)`, `MAX_SCHEMA_LENGTH=100000`, `MAX_SCHEMA_DEPTH=32` | no | `test_mcp_server.py` | Recursive DFS validation, bounded depth |
| `validate_toml` | validation | 1 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) TOML parse |
| `json_compare` | json | 1 | `a`, `b` | 100,000 each | — | `max_diffs` ≤ 10,000 | linear | `_require_str(MAX_TEXT_LENGTH)` × 2, `MAX_DIFFS=10000` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | Recursive semantic comparison |
| `json_canonicalize` | json | 1 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) JSON parse + key sort |
| `json_extract` | json | 2 | `text`, `pointer` | 100,000 text, 4,096 pointer | — | — | linear | `_require_str(MAX_TEXT_LENGTH)`, pointer ≤ 4096, `max_output_chars ≤ 100000` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | JSON Pointer traversal |
| `json_query` | json | 1 | `text`, `pointer` | 100,000 text, 4,096 pointer | — | — | linear | `_require_str(MAX_TEXT_LENGTH)`, pointer ≤ 4096 | no | `test_mcp_server.py` | **Deprecated** — use json_extract |
| `json_shape` | json | 3 | `text` | 100,000 | — | `max_keys ≤ 10000`, `max_depth ≤ 32` | linear | `_require_str(MAX_TEXT_LENGTH)`, `MAX_SHAPE_DEPTH=32`, `MAX_SHAPE_KEYS=10000`, `MAX_SHAPE_ARRAY_ITEMS=10000` | no | `test_mcp_server.py` | Bounded recursive shape analysis |
| `list_compare` | list | 2 | `a`, `b` | 200,000 total chars | 10,000 items each | — | **quadratic** (near-match) | `MAX_LIST_ITEMS=10000`, total chars ≤ `MAX_TEXT_LENGTH*2`, `include_near_matches` triggers O(n²) pairwise edit distance; **`MAX_PAIRWISE_ITEMS=1000`** caps near-match mode | no | `test_mcp_server.py`, `test_mcp_tools_new.py`, `test_mcp_resource_bounds.py` | Near-match mode bounded by MAX_PAIRWISE_ITEMS |
| `list_dedupe` | list | 1 | `items` | 100,000/item | 10,000 | — | linear | `_validate_str_list(MAX_LIST_ITEMS=10000)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) hash-based dedup |
| `list_sort` | list | 1 | `items` | 100,000/item | 10,000 | — | linear | `_validate_str_list(MAX_LIST_ITEMS=10000)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n log n) sort |
| `patch_apply_check` | patch | 2 | `original_text`, `patch_text` | 200,000 each | — | — | quadratic | `MAX_ORIGINAL_LENGTH=200000`, `MAX_PATCH_LENGTH=200000` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | Hunk-by-hunk application; worst case quadratic in hunk count |
| `patch_summary` | patch | 2 | `patch_text` | 200,000 | — | — | linear | `MAX_PATCH_LENGTH=200000` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) line-by-line parse |
| `patch_conflict_markers_inspect` | patch | 2 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) scan for `<<<<<<<` / `=======` / `>>>>>>>` |
| `diff_touched_paths` | patch | 2 | `patch_text` | 200,000 | — | `max_files ≤ 100` | linear | `MAX_PATCH_LENGTH=200000`, `max_files=100` default | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) line scan |
| `diff_hunk_ranges` | patch | 2 | `patch_text` | 200,000 | — | `max_files ≤ 100` | linear | `MAX_PATCH_LENGTH=200000`, `max_files=100` default | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) line scan |
| `diff_file_headers` | patch | 2 | `patch_text` | 200,000 | — | `max_files ≤ 100` | linear | `MAX_PATCH_LENGTH=200000`, `max_files=100` default | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) line scan |
| `unified_diff_validate` | patch | 2 | `patch_text` | 200,000 | — | — | linear | `MAX_PATCH_LENGTH=200000` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) structural validation |
| `path_analyze` | path | 2 | `path` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) string split + analysis |
| `path_compare` | path | 2 | `left`, `right` | 100,000 each | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` × 2 | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) normalize + compare |
| `path_normalize` | path | 0 | `path` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) posixpath/ntpath normalization |
| `path_scope_check` | path | 2 | `root`, `target` | 100,000 each | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` × 2 | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) lexical containment check |
| `glob_match` | path | 1 | `pattern`, `path` | 100,000 each | — | — | bounded | `_require_str(MAX_TEXT_LENGTH)` × 2 | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | fnmatch-based; **bounded** regardless of input size |
| `shell_split` | shell | 2 | `command` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) POSIX-like lexer |
| `shell_quote_join` | shell | 2 | `argv` | 100,000/item | 10,000 | — | linear | `_validate_str_list(MAX_LIST_ITEMS=10000)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) quote-join |
| `argv_compare` | shell | 2 | `left_command`/`left_argv`, `right_command`/`right_argv` | 100,000 each | 10,000 | — | linear | `_validate_str_list(MAX_LIST_ITEMS=10000)`, `_require_str(MAX_TEXT_LENGTH)` × 2 | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | XOR-validated inputs, shell_split + compare |
| `identifier_analyze` | identifier | 3 | `text` | 100,000 | — | — | bounded | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py` | Single-identifier classification, constant-time per language |
| `identifier_inspect` | identifier | 1 | `identifiers` | 100,000/item | 10,000 | — | **quadratic** (confusables) | `MAX_LIST_ITEMS=10000`, each ≤ `MAX_TEXT_LENGTH`, **`MAX_PAIRWISE_ITEMS=1000`** when `check_confusables=True` | no | `test_mcp_server.py`, `test_mcp_tools_new.py`, `test_mcp_resource_bounds.py` | Confusable check bounded by MAX_PAIRWISE_ITEMS |
| `identifier_table_inspect` | identifier | 3 | `identifiers` (list of dicts) | 100,000/name | 10,000 | — | **quadratic** (confusables) | `MAX_LIST_ITEMS=10000`, each name ≤ `MAX_TEXT_LENGTH`, **`MAX_PAIRWISE_ITEMS=1000`** when confusable check active | no | `test_mcp_server.py`, `test_mcp_tools_new.py`, `test_mcp_resource_bounds.py` | Confusable check bounded by MAX_PAIRWISE_ITEMS |
| `version_compare` | version | 2 | `a`, `b` | 100,000 each | — | — | bounded | `_require_str(MAX_TEXT_LENGTH)` × 2 | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(1) version component comparison |
| `version_constraint_check` | version | 3 | `version`, `constraint` | 100,000 each | — | — | bounded | `_require_str(MAX_TEXT_LENGTH)` × 2 | no | `test_mcp_server.py` | O(1) constraint evaluation |
| `cargo_toml_inspect` | manifest | 3 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py` | TOML parse + metadata extraction |
| `pyproject_inspect` | manifest | 2 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py` | TOML parse + metadata extraction |
| `package_json_inspect` | manifest | 2 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py` | JSON parse + metadata extraction |
| `requirements_inspect` | manifest | 2 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py` | Line-by-line parse |
| `go_mod_inspect` | manifest | 2 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py` | Line-by-line parse |
| `lockfile_summary` | manifest | 2 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py` | Shallow heuristic detection, not full parse |
| `toml_shape` | manifest | 2 | `text` | 100,000 | — | `max_tables ≤ 100000` | linear | `_require_str(MAX_TEXT_LENGTH)`, `max_tables ≤ 100000` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) TOML structure scan |
| `dotenv_validate` | config | 2 | `text`, `key_pattern` | 100,000 | — | — | **exponential** | `_require_str(MAX_TEXT_LENGTH)`, `key_pattern ≤ 1000`, `_regex_safety_check` pre-filter, **subprocess + RLIMIT_AS 256MB**, `_SPAWN_SEMAPHORE(4)`, 5s timeout, rejects inline flags | **yes** | `test_mcp_server.py`, `test_mcp_env_limits.py`, `test_mcp_tools_new.py` | ReDoS risk from user-supplied `key_pattern`; mitigated by safety check + subprocess |
| `ini_validate` | config | 2 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py` | O(n) line-by-line parse |
| `llm_json_output_check` | text_ops | 2 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py` | Detects fences, trailing commas, etc. |
| `markdown_structure` | markdown | 2 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) line scanner |
| `code_fence_extract` | markdown | 2 | `text` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) line scanner + fingerprint |
| `markdown_link_check_lexical` | markdown | 2 | `text`, `known_paths` | 100,000 | 10,000 paths | — | linear | `_require_str(MAX_TEXT_LENGTH)`, `known_paths ≤ 10000` | no | `test_mcp_server.py` | O(n) link extraction + path matching |
| `escape_text` | text_ops | 1 | `text`, `mode` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) string transformation |
| `unescape_text` | text_ops | 1 | `text`, `mode` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) string transformation |
| `line_range_extract` | text_ops | 1 | `text`, `start_line`, `end_line` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) line split + range slice |
| `line_range_compare` | text_ops | 2 | `left_text`, `right_text`, `start_line`, `end_line` | 100,000 each | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` × 2 (manual check) | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) line split + range slice + compare |
| `prompt_input_inspect` | unicode | 2 | `text`, `checks`, `phrase_patterns` | 100,000 | 10,000 phrase_patterns | — | linear | `_require_str(MAX_TEXT_LENGTH)`, `phrase_patterns ≤ MAX_LIST_ITEMS` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | Multiple O(n) scans; phrase matching uses literal search (not regex) |
| `unicode_policy_check` | unicode | 2 | `text`, `policy` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | Policy-dependent checks, each O(n) |
| `canonicalize_text` | unicode | 2 | `text`, `profile` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)` | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | O(n) profile-specific normalization |
| `repo_file_inventory` | repo | 2 | `paths`, `sizes`, `hashes` | 1,000/path | 50,000 paths | `largest_files ≤ 10` | linear | `_MAX_REPO_PATHS=50000`, `_MAX_REPO_PATH_LENGTH=1000` | no | `test_mcp_server.py` | O(n) path classification + stats |
| `ip_inspect` | network | 2 | `address` | 100,000 | — | — | bounded | `_require_str(MAX_TEXT_LENGTH)`, explicit taxonomy lookup | no | `test_utility_parity_integration.py` | IP parse + explicit special-use classification, no network I/O |
| `cidr_inspect` | network | 2 | `cidr`, `contains` | 100,000 each | — | — | bounded | `_require_str(MAX_TEXT_LENGTH)` × 2, same-family check | no | `test_utility_parity_integration.py` | Integer range arithmetic, exact address counts incl. IPv6 `/0` |
| `codec_convert` | encoding | 2 | `value`, `from`, `to` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)`, strict alphabet/padding validation, output ceiling | no | `test_utility_parity_integration.py` | Strict Base64/hex validation before decode |
| `radix_convert` | encoding | 2 | `value`, `from_base`, `to_base` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)`, bases 2..36, magnitude capped at `2**128 - 1` | no | `test_utility_parity_integration.py` | u128 cap bounds resource use |
| `datetime_convert` | temporal | 2 | `value`, `format`, `output_offset` | 100,000 | — | — | bounded | `_require_str(MAX_TEXT_LENGTH)`, fixed-offset grammar, integer-ns arithmetic | no | `test_utility_parity_integration.py` | No float timestamps, no timezone database |
| `cron_inspect` | temporal | 2 | `expression`, `after`, `count` | 100,000 | — | `count ≤ 32` | bounded | `_require_str(MAX_TEXT_LENGTH)`, `count` 1..32, search bounded to 146,097 days | no | `test_utility_parity_integration.py` | Fixed-offset minute-resolution search, no scheduler execution |
| `edit_preflight` | preflight | 1 | `original`, mode-specific args | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)`, delegates to sub-tools with their own limits | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | **Composite**: calls text_replace_check OR patch_apply_check OR line_range_extract + text_fingerprint depending on mode |
| `command_preflight` | preflight | 1 | `command` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)`, delegates to sub-tools | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | **Composite**: calls shell_split + regex_safety_check (when regex-like args detected) |
| `config_preflight` | preflight | 1 | `text`, `format`, `schema` | 100,000 | — | — | linear | `_require_str(MAX_TEXT_LENGTH)`, delegates to format-specific validator | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | **Composite**: auto-detects format → calls validate_json/validate_toml/dotenv_validate/ini_validate/cargo_toml_inspect + optional validate_schema_light |
| `structured_data_compare` | json | 2 | `a`, `b` | 100,000 each | — | `max_diffs ≤ 50` | linear | `_require_str(MAX_TEXT_LENGTH)` × 2, delegates to sub-tools | no | `test_mcp_server.py`, `test_mcp_tools_new.py` | **Composite**: calls validate_json + json_compare + json_shape |
---

## Composite Tool Sub-call Summary

These tools invoke other tools internally. Their worst-case cost is the sum of their sub-calls.

| Composite Tool | Sub-calls | Total Worst-Case |
|----------------|-----------|-----------------|
| `text_security_inspect` | text_inspect → unicode_policy_check → canonicalize_text → prompt_input_inspect → identifier_inspect | O(5n) linear |
| `edit_preflight` | text_replace_check OR patch_apply_check OR line_range_extract → text_fingerprint → text_diff_explain | O(n) linear (mode-dependent) |
| `command_preflight` | shell_split → regex_safety_check (conditional) | O(n) linear |
| `config_preflight` | validate_json/validate_toml/dotenv_validate/ini_validate/cargo_toml_inspect → optional validate_schema_light | O(n) linear |
| `structured_data_compare` | validate_json × 2 → json_compare → json_shape × 2 | O(n) linear |

## Tools Needing Attention

The following tools have worst-case risk profiles that warrant monitoring:

| Tool | Risk | Concern | Current Bound |
|------|------|---------|---------------|
| `identifier_inspect` | quadratic | O(N²) pairwise collision check | `MAX_PAIRWISE_ITEMS=1000` when `check_confusables=True` |
| `identifier_table_inspect` | quadratic | O(N²) pairwise collision check | `MAX_PAIRWISE_ITEMS=1000` when confusable check active |
| `list_compare` (with `include_near_matches`) | quadratic | O(N²) edit-distance computation | `MAX_PAIRWISE_ITEMS=1000` when near-match mode enabled |
| `validate_regex` | exponential | Catastrophic backtracking in pathological patterns | Subprocess + RLIMIT_AS + safety pre-filter + 5s timeout |
| `regex_finditer` | exponential | Catastrophic backtracking in pathological patterns | Subprocess + RLIMIT_AS + safety pre-filter + 5s timeout |
| `dotenv_validate` | exponential | User-supplied `key_pattern` regex | Subprocess + RLIMIT_AS + safety pre-filter + 5s timeout |
| `validate_schema_light` | quadratic | Deeply nested schema validation | `MAX_SCHEMA_DEPTH=32`, `MAX_SCHEMA_LENGTH=100000` |

## Subprocess Isolation Summary

Only regex-related tools spawn child processes. All use the same isolation pattern:

1. `_SPAWN_SEMAPHORE` (max 4 concurrent) with 10s acquire timeout
2. `multiprocessing.get_context("spawn")` for process creation
3. `RLIMIT_AS = 256MB` in child (falls back to `RLIMIT_CPU = 5s/10s` on macOS)
4. `REGEX_TIMEOUT_SECONDS = 5` for queue.get timeout
5. `_cleanup_child_process()` with terminate → kill → orphan tracking
6. `_orphaned_regex_processes` capped at 256 handles

| Tool | Uses Subprocess |
|------|----------------|
| `validate_regex` | **yes** |
| `regex_finditer` | **yes** |
| `dotenv_validate` | **yes** (due to user-supplied regex in `key_pattern`) |
| `math_eval` | **yes** (via `evaluate_with_timeout` for timeout enforcement) |
| All others | no |
