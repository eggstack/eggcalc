"""
Low-level Unicode text primitives.

These primitives are deterministic, independently testable, and do not
perform semantic interpretation or call LLMs.
"""

from __future__ import annotations

# Re-export cargo
from .cargo import (
    CargoDependencyForm,
    CargoDepSection,
    CargoInspectResult,
    CargoPackageInfo,
    CargoWorkspaceInfo,
    cargo_toml_inspect,
)

# Re-export config
from .config import (
    DotenvEntry,
    DotenvValidateResult,
    IniKeyValueLine,
    IniSectionLine,
    IniValidateResult,
    dotenv_validate,
    ini_validate,
)

# Re-export diff
from .diff import (
    CommonPrefixSuffix,
    DiffSpan,
    FirstDiff,
    common_prefix_suffix,
    diff_spans,
    first_diff,
    levenshtein_distance,
    longest_common_subsequence,
)

# Re-export diff_analysis
from .diff_analysis import (
    ConflictMarkerLocation,
    DiffFileHeaderEntry,
    DiffFileHeadersResult,
    DiffHunkRangesFile,
    DiffHunkRangesResult,
    DiffTouchedPathsResult,
    HunkDetail,
    ModeChange,
    PatchConflictMarkersResult,
    UnifiedDiffValidateResult,
    diff_file_headers,
    diff_hunk_ranges,
    diff_touched_paths,
    patch_conflict_markers_inspect,
    unified_diff_validate,
)

# Re-export glob
from .glob import (
    GlobMatchResult,
    glob_match,
)

# Re-export identifier
from .identifier import (
    IdentifierAnalyzeResult,
    identifier_analyze,
)

# Re-export identifier_inspect
from .identifier_inspect import (
    CollisionInfo,
    IdentifierInfo,
    IdentifierInspectResult,
    IdentifierTableInspectResult,
    MixedStyleGroup,
    ReservedKeywordHit,
    TableCollisionInfo,
    TableIdentifierEntry,
    identifier_inspect,
    identifier_table_inspect,
)

# Re-export inspect_prompt
from .inspect_prompt import (
    PromptInspectionFinding,
    PromptInspectionResult,
    prompt_input_inspect,
)

# Re-export llm_hygiene
from .llm_hygiene import (
    JsonFixHint,
    LlmJsonCheckResult,
    llm_json_output_check,
)

# Re-export markdown
from .markdown import (
    CodeFenceBlock,
    CodeFenceExtractResult,
    DuplicateAnchor,
    MalformedLink,
    MarkdownCodeFence,
    MarkdownFrontmatter,
    MarkdownHeading,
    MarkdownLink,
    MarkdownLinkCheckResult,
    MarkdownStructureResult,
    UnresolvedRelative,
    code_fence_extract,
    markdown_link_check_lexical,
    markdown_structure,
)

# Re-export measure
from .measure import (
    CharCategoryMetrics,
    LineMetrics,
    WordMetrics,
    char_category_metrics,
    line_metrics,
    word_metrics,
)

# Re-export patch
from .patch import (
    FailedHunk,
    PatchApplyCheckResult,
    PatchFile,
    PatchHunk,
    PatchParseResult,
    PatchSummaryResult,
    patch_apply_check,
    patch_summary,
)

# Re-export path_tools
from .path_tools import (
    PathAnalyzeResult,
    PathCompareResult,
    PathNormalizeResult,
    PathScopeCheckResult,
    path_analyze,
    path_compare,
    path_normalize,
    path_scope_check,
)

# Re-export position
from .position import (
    TextPositionResult,
    text_position,
)

# Re-export primitives
from .primitives import (
    CodepointInfo,
    InvisibleCharInfo,
    MeasureBasic,
    casefold_text,
    codepoints,
    count_graphemes,
    find_invisibles,
    measure_basic,
    normalize_unicode,
    normalized_equal,
    raw_equal,
    truncate_to_grapheme,
    utf8_bytes,
    visible_repr,
)

# Re-export repo_audit
from .repo_audit import (
    RepoInventoryResult,
    repo_file_inventory,
)

# Re-export shell
from .shell import (
    ArgvCompareResult,
    ShellFeatures,
    ShellQuoteJoinResult,
    ShellSplitResult,
    argv_compare,
    shell_quote_join,
    shell_split,
)

# Re-export synthesis
from .synthesis import (
    CountCharsResult,
    ExplainDiffResult,
    InspectTextResult,
    LineRangeCompareResult,
    LineRangeExtractResult,
    MeasureTextResult,
    TextEqualResult,
    TextReplaceCheckResult,
    TextWindowResult,
    count_chars,
    explain_diff,
    inspect_text,
    line_range_compare,
    line_range_extract,
    list_compare,
    measure_text,
    text_equal,
    text_replace_check,
    text_window,
)

# Re-export transform
from .transform import (
    EscapeTextResult,
    RemovedChar,
    TextFingerprintResult,
    TextTransformResult,
    UnescapeTextResult,
    escape_text,
    text_fingerprint,
    text_hash,
    text_transform,
    unescape_text,
)

# Re-export unicode_policy
from .unicode_policy import (
    CanonicalizeResult,
    CanonicalizeResultWithMapping,
    PolicyFinding,
    UnicodePolicyCheckResult,
    canonicalize_text,
    unicode_policy_check,
)

# Re-export unicode_tools
from .unicode_tools import (
    ConfusableInfo,
    MixedScriptsResult,
    ScriptInfo,
    confusables_count,
    detect_confusables,
    detect_mixed_scripts,
    reverse_confusables,
    unicode_script,
    unicode_scripts,
)

# Re-export validate
from .validate import (
    CheckBracketsResult,
    JsonCompareDiff,
    JsonCompareResult,
    JsonExtractResult,
    JsonShapeKey,
    JsonShapeResult,
    RegexFindIterMatch,
    RegexFindIterResult,
    RegexSafetyFinding,
    RegexSafetyResult,
    RegexTestResult,
    TomlShapeResult,
    ValidateJsonResult,
    ValidateSchemaLightResult,
    ValidateTomlResult,
    VersionCompareResult,
    check_brackets,
    json_compare,
    json_extract,
    json_shape,
    list_dedupe,
    list_sort,
    regex_finditer,
    regex_safety_check,
    regex_test,
    toml_shape,
    validate_json,
    validate_schema_light,
    validate_toml_text,
    version_compare,
)

# Re-export version
from .version import (
    ParsedConstraint,
    ParsedConstraintComponent,
    ParsedVersion,
    VersionConstraintResult,
    check_version_constraint,
    parse_version,
)

__all__ = [
    # Config
    "dotenv_validate",
    "ini_validate",
    "DotenvEntry",
    "DotenvValidateResult",
    "IniSectionLine",
    "IniKeyValueLine",
    "IniValidateResult",
    # Glob
    "glob_match",
    "GlobMatchResult",
    # Primitives
    "utf8_bytes",
    "codepoints",
    "normalize_unicode",
    "casefold_text",
    "raw_equal",
    "normalized_equal",
    "measure_basic",
    "count_graphemes",
    "truncate_to_grapheme",
    "find_invisibles",
    "visible_repr",
    "CodepointInfo",
    "MeasureBasic",
    "InvisibleCharInfo",
    # Unicode tools
    "unicode_script",
    "unicode_scripts",
    "detect_mixed_scripts",
    "detect_confusables",
    "confusables_count",
    "reverse_confusables",
    "ScriptInfo",
    "ConfusableInfo",
    "MixedScriptsResult",
    # Diff
    "first_diff",
    "common_prefix_suffix",
    "levenshtein_distance",
    "diff_spans",
    "longest_common_subsequence",
    "FirstDiff",
    "CommonPrefixSuffix",
    "DiffSpan",
    # Diff analysis
    "diff_touched_paths",
    "diff_hunk_ranges",
    "diff_file_headers",
    "patch_conflict_markers_inspect",
    "unified_diff_validate",
    "DiffTouchedPathsResult",
    "DiffHunkRangesResult",
    "DiffHunkRangesFile",
    "HunkDetail",
    "DiffFileHeadersResult",
    "DiffFileHeaderEntry",
    "PatchConflictMarkersResult",
    "ConflictMarkerLocation",
    "UnifiedDiffValidateResult",
    "ModeChange",
    # Validate
    "check_brackets",
    "validate_json",
    "validate_toml_text",
    "validate_schema_light",
    "regex_test",
    "regex_finditer",
    "regex_safety_check",
    "json_extract",
    "json_compare",
    "json_shape",
    "CheckBracketsResult",
    "ValidateJsonResult",
    "ValidateSchemaLightResult",
    "ValidateTomlResult",
    "TomlShapeResult",
    "VersionCompareResult",
    "RegexTestResult",
    "RegexFindIterResult",
    "RegexFindIterMatch",
    "RegexSafetyResult",
    "RegexSafetyFinding",
    "JsonExtractResult",
    "JsonCompareDiff",
    "JsonCompareResult",
    "JsonShapeResult",
    "JsonShapeKey",
    # Measure
    "line_metrics",
    "word_metrics",
    "char_category_metrics",
    "LineMetrics",
    "WordMetrics",
    "CharCategoryMetrics",
    # Position
    "text_position",
    "TextPositionResult",
    # Transform
    "escape_text",
    "unescape_text",
    "text_hash",
    "text_transform",
    "text_fingerprint",
    "TextFingerprintResult",
    "EscapeTextResult",
    "UnescapeTextResult",
    "TextTransformResult",
    "RemovedChar",
    # Synthesis
    "measure_text",
    "text_equal",
    "explain_diff",
    "inspect_text",
    "count_chars",
    "list_compare",
    "text_window",
    "text_replace_check",
    "line_range_extract",
    "line_range_compare",
    "MeasureTextResult",
    "TextEqualResult",
    "ExplainDiffResult",
    "InspectTextResult",
    "CountCharsResult",
    "TextWindowResult",
    "TextReplaceCheckResult",
    "LineRangeExtractResult",
    "LineRangeCompareResult",
    # Identifier
    "identifier_analyze",
    "IdentifierAnalyzeResult",
    "identifier_inspect",
    "IdentifierInspectResult",
    "CollisionInfo",
    "IdentifierInfo",
    "identifier_table_inspect",
    "IdentifierTableInspectResult",
    "TableCollisionInfo",
    "ReservedKeywordHit",
    "MixedStyleGroup",
    "TableIdentifierEntry",
    # Markdown
    "markdown_structure",
    "code_fence_extract",
    "markdown_link_check_lexical",
    "MarkdownStructureResult",
    "CodeFenceExtractResult",
    "MarkdownLinkCheckResult",
    "MarkdownHeading",
    "MarkdownCodeFence",
    "MarkdownLink",
    "MarkdownFrontmatter",
    "CodeFenceBlock",
    "MalformedLink",
    "DuplicateAnchor",
    "UnresolvedRelative",
    # LLM hygiene
    "llm_json_output_check",
    "LlmJsonCheckResult",
    "JsonFixHint",
    # Repo audit
    "repo_file_inventory",
    "RepoInventoryResult",
    # Patch
    "patch_apply_check",
    "patch_summary",
    "PatchApplyCheckResult",
    "PatchSummaryResult",
    "PatchParseResult",
    "PatchFile",
    "PatchHunk",
    "FailedHunk",
    # Path
    "path_analyze",
    "path_normalize",
    "path_compare",
    "path_scope_check",
    "PathAnalyzeResult",
    "PathNormalizeResult",
    "PathCompareResult",
    "PathScopeCheckResult",
    # Shell
    "shell_split",
    "shell_quote_join",
    "argv_compare",
    "ShellSplitResult",
    "ShellQuoteJoinResult",
    "ArgvCompareResult",
    "ShellFeatures",
    # Unicode policy
    "unicode_policy_check",
    "canonicalize_text",
    "UnicodePolicyCheckResult",
    "PolicyFinding",
    "CanonicalizeResult",
    "CanonicalizeResultWithMapping",
    # Version
    "check_version_constraint",
    "parse_version",
    "ParsedVersion",
    "ParsedConstraint",
    "ParsedConstraintComponent",
    "VersionConstraintResult",
    # Cargo
    "cargo_toml_inspect",
    "CargoInspectResult",
    "CargoPackageInfo",
    "CargoWorkspaceInfo",
    "CargoDependencyForm",
    "CargoDepSection",
    # Prompt inspection
    "prompt_input_inspect",
    "PromptInspectionFinding",
    "PromptInspectionResult",
    # Validate (re-exported)
    "list_dedupe",
    "list_sort",
    "toml_shape",
    "version_compare",
]
