#!/usr/bin/env python3
"""Parse Unicode confusables.txt and generate confusables.py.

This script downloads the latest confusables.txt from Unicode consortium
and generates a Python dictionary for use in unicode_tools.

The generated module stores data as a zlib-compressed base85 payload
that is decoded lazily on first access, reducing import-time allocation.
"""

from __future__ import annotations

import base64
import re
import urllib.request
import zlib
from datetime import datetime
from pathlib import Path

DEFAULT_URL = "https://www.unicode.org/Public/security/latest/confusables.txt"
OUTPUT_FILE = Path(__file__).parent.parent / "eggcalc" / "exact" / "confusables.py"
COMMENTS_AND_HEADER_LINES = 35  # Approximate header lines to skip
CACHE_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = CACHE_DIR / "confusables.txt"


def get_confusables_url(version: str | None = None) -> str:
    """Get URL for confusables.txt, optionally version-pinned."""
    if version:
        return f"https://www.unicode.org/Public/security/{version}/confusables.txt"
    return DEFAULT_URL


def fetch_confusables_txt(use_cache: bool = False) -> tuple[str, str | None, str | None]:
    """Download the confusables.txt file.

    Returns:
        tuple of (content, source_version, source_date) from file header
        source_version and source_date are extracted from header comments
    """
    if use_cache and CACHE_FILE.exists():
        content = CACHE_FILE.read_text(encoding="utf-8")
        source_version, source_date = _parse_header_metadata(content)
        print(f"Loaded from cache: {CACHE_FILE}")
        return content, source_version, source_date

    url = get_confusables_url()
    print(f"Fetching {url}...")
    with urllib.request.urlopen(url, timeout=30) as response:
        content = response.read().decode("utf-8")
        source_version, source_date = _parse_header_metadata(content)
        return content, source_version, source_date


def _parse_header_metadata(content: str) -> tuple[str | None, str | None]:
    """Parse version and date from confusables.txt header."""
    source_version = None
    source_date = None
    for line in content.split("\n")[:50]:
        if line.startswith("# Version:"):
            source_version = line.split(":", 1)[1].strip()
        elif line.startswith("# Date:"):
            source_date = line.split(":", 1)[1].strip()
    return source_version, source_date


def parse_code_point(s: str) -> str | None:
    """Parse a hex code point like '05AD' or '041F' into Unicode char.

    Returns the character, or None if invalid.
    """
    s = s.strip()
    if not s:
        return None
    match = re.fullmatch(r"([0-9A-Fa-f]{4,6})", s)
    if not match:
        return None
    return chr(int(s, 16))


def parse_line(line: str) -> tuple[str, str] | None:
    """Parse a single line from confusables.txt.

    Returns (source_char, substitution) tuple, or None if skip.
    Format: CODEPOINT ; SUBSTITUTION ; TYPE # ... comment
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    parts = line.split(";")
    if len(parts) < 2:
        return None

    source_str = parts[0].strip()
    substitution_str = parts[1].strip()

    # Parse source code point
    source_char = parse_code_point(source_str)
    if source_char is None:
        return None

    # Parse substitution - may be multiple code points
    sub_parts = substitution_str.split()
    if not sub_parts:
        return None

    try:
        # Handle multi-char substitutions by concatenating
        substitution = "".join(chr(int(p.strip(), 16)) for p in sub_parts)
        return (source_char, substitution)
    except (ValueError, OverflowError):
        return None


def parse_confusables(content: str) -> dict[str, str]:
    """Parse confusables.txt content into a dictionary.

    Returns dict mapping source_char -> substitution (may be multi-char).
    """
    result: dict[str, str] = {}
    lines = content.split("\n")

    data_started = False
    for line in lines:
        stripped = line.strip()
        if not data_started:
            if stripped.startswith("#") or not stripped:
                continue
            if ";" not in stripped:
                continue
            data_started = True

        parsed = parse_line(line)
        if parsed:
            source, sub = parsed
            result[source] = sub

    return result


def generate_python_file(
    confusables: dict[str, str],
    source_version: str | None = None,
    source_date: str | None = None,
) -> str:
    """Generate Python source for confusables.py with compressed payload."""
    lines = [
        '"""',
        "Unicode confusables table.",
        "",
        "Auto-generated from confusables.txt (Unicode UTS #39).",
        f"Source: {DEFAULT_URL}",
    ]

    if source_version:
        lines.append(f"Source-Version: {source_version}")
    if source_date:
        lines.append(f"Source-Date: {source_date}")

    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"Entry-Count: {len(confusables)}")
    lines.append("")
    lines.append("DO NOT EDIT - regenerate with scripts/generate_confusables.py")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("import base64 as _base64")
    lines.append("import zlib as _zlib")
    lines.append("from collections.abc import Iterator, Mapping")
    lines.append("")

    # Build compressed payload from sorted codepoint entries
    sorted_items = sorted(confusables.items(), key=lambda x: ord(x[0]))
    data_lines = []
    for source, sub in sorted_items:
        source_cp = f"U+{ord(source):04X}"
        sub_cps = " ".join(f"U+{ord(c):04X}" for c in sub)
        data_lines.append(f"{source_cp}|{sub_cps}")

    raw = "\n".join(data_lines).encode("utf-8")
    compressed = zlib.compress(raw, 9)
    payload = base64.b85encode(compressed).decode("ascii")

    lines.append(f"# Compressed confusables payload ({len(data_lines)} entries, "
                 f"{len(compressed):,} bytes compressed)")
    lines.append(f"_PAYLOAD = {payload!r}")
    lines.append("")
    lines.append("del _base64, _zlib  # cleanup module namespace")
    lines.append("")
    lines.append("")
    lines.append("class _LazyConfusables(Mapping):")
    lines.append('    """Lazy mapping that decodes the compressed confusables payload on first use."""')
    lines.append("")
    lines.append("    __slots__ = ('_data',)")
    lines.append("")
    lines.append("    def _decode(self) -> dict[str, str]:")
    lines.append("        data = getattr(self, '_data', None)")
    lines.append("        if data is None:")
    lines.append("            import base64 as _b64")
    lines.append("            import zlib as _z")
    lines.append("")
    lines.append("            raw = _z.decompress(_b64.b85decode(_PAYLOAD))")
    lines.append("            data = {}")
    lines.append("            for line in raw.decode('utf-8').splitlines():")
    lines.append("                key, _, value = line.partition('|')")
    lines.append("                data[key] = value")
    lines.append("            object.__setattr__(self, '_data', data)")
    lines.append("        return data")
    lines.append("")
    lines.append("    def __getitem__(self, key: str) -> str:")
    lines.append("        return self._decode()[key]")
    lines.append("")
    lines.append("    def __iter__(self) -> Iterator[str]:")
    lines.append("        return iter(self._decode())")
    lines.append("")
    lines.append("    def __len__(self) -> int:")
    lines.append("        return len(self._decode())")
    lines.append("")
    lines.append("    def __contains__(self, key: object) -> bool:")
    lines.append("        return key in self._decode()")
    lines.append("")
    lines.append("")
    lines.append("CONFUSABLES: Mapping[str, str] = _LazyConfusables()")
    lines.append("")
    lines.append('__all__ = ["CONFUSABLES"]')
    lines.append("")  # trailing newline for ruff W292

    return "\n".join(lines)


def save_cache(content: str) -> None:
    """Save downloaded content to cache for reproducibility."""
    CACHE_DIR.mkdir(exist_ok=True)
    CACHE_FILE.write_text(content, encoding="utf-8")
    print(f"Saved to cache: {CACHE_FILE}")


def main() -> None:
    """Main entry point."""
    # Fetch (try cache first for reproducibility)
    content, source_version, source_date = fetch_confusables_txt(use_cache=True)
    print(f"Downloaded {len(content)} bytes")

    # Parse
    confusables = parse_confusables(content)
    print(f"Parsed {len(confusables)} confusable entries")

    # Generate with metadata
    python_source = generate_python_file(confusables, source_version, source_date)

    # Write
    OUTPUT_FILE.write_text(python_source)
    print(f"Wrote {OUTPUT_FILE}")

    # Save to cache
    save_cache(content)

    # Verify by importing
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    # Reload the module to pick up the regenerated file
    if "eggcalc.exact.confusables" in sys.modules:
        del sys.modules["eggcalc.exact.confusables"]
    from eggcalc.exact import confusables as conf_module

    loaded = conf_module.CONFUSABLES
    print(f"Verified import: {len(loaded)} entries loaded")

    # Spot check
    assert "U+0410" in loaded, "Cyrillic A should be present"
    assert loaded["U+0410"] == "U+0041", "Cyrillic A should map to Latin A"
    print("Spot checks passed!")


if __name__ == "__main__":
    main()
