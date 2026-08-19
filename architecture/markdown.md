# markdown.py — Markdown Structure Analysis

645 lines. Regex-based Markdown structure parsing and code fence extraction.

## Overview

Line scanners for document structure (headings, code fences, links, HTML comments, frontmatter, tables) and fenced code block extraction with exact line ranges and SHA-256 fingerprints.

## Key Exports

```python
from eggcalc.exact.markdown import (
    markdown_structure,
    code_fence_extract,
)
```

## Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `markdown_structure(text, ...)` | `MarkdownStructureResult` | Parses Markdown structure: headings, code fences, links, HTML comments, frontmatter, tables |
| `code_fence_extract(text, include_content=True, include_fingerprint=True)` | `CodeFenceExtractResult` | Extracts fenced code blocks with exact line ranges and fingerprints |

## Module Dependencies

- `hashlib`, `re`, `typing`
