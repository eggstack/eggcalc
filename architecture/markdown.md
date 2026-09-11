# markdown.py — Markdown Structure Analysis

642 lines. Regex-based Markdown structure parsing and code fence extraction.

## Overview

Line scanners for document structure (headings, code fences, links, HTML comments, frontmatter, tables) and fenced code block extraction with exact line ranges and SHA-256 fingerprints.

## Key Exports

```python
from eggcalc.exact.markdown import (
    markdown_structure,
    code_fence_extract,
    markdown_link_check_lexical,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `markdown_structure(text, ...)` | `MarkdownStructureResult` | Parses Markdown structure: headings, code fences, links, HTML comments, frontmatter, tables |
| `code_fence_extract(text, language=None, include_content=True)` | `CodeFenceExtractResult` | Extracts fenced code blocks with exact line ranges and fingerprints |
| `markdown_link_check_lexical(text, known_paths=None)` | `MarkdownLinkCheckResult` | Lexically checks Markdown links without filesystem access |

## Module Dependencies

- `hashlib`, `re`, `typing`
