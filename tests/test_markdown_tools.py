"""Tests for markdown_structure and code_fence_extract tools."""

from eggcalc.exact.markdown import (
    code_fence_extract,
    markdown_structure,
)


class TestMarkdownStructure:
    """Tests for the markdown_structure function."""

    def test_empty_text(self):
        result = markdown_structure("")
        assert result["headings"] == []
        assert result["code_fences"] == []
        assert result["links"] == []
        assert result["html_comments"] == []
        assert result["frontmatter"]["present"] is False
        assert result["tables_detected"] is False
        assert result["findings"] == []

    def test_headings(self):
        text = "# Title\n\nSome text\n\n## Section A\n\n### Sub\n\n## Section B"
        result = markdown_structure(text)
        assert len(result["headings"]) == 4
        assert result["headings"][0] == {
            "level": 1,
            "text": "Title",
            "line": 1,
            "slug": "title",
        }
        assert result["headings"][1]["level"] == 2
        assert result["headings"][1]["text"] == "Section A"
        assert result["headings"][1]["slug"] == "section-a"
        assert result["headings"][2]["level"] == 3
        assert result["headings"][3]["level"] == 2

    def test_headings_with_trailing_hash(self):
        text = "# Title ##\n## Section ##"
        result = markdown_structure(text)
        assert len(result["headings"]) == 2
        assert result["headings"][0]["text"] == "Title"
        assert result["headings"][1]["text"] == "Section"

    def test_code_fences_open_close(self):
        text = "# Heading\n\n```python\nprint('hello')\n```\n\nMore text"
        result = markdown_structure(text)
        assert len(result["code_fences"]) == 1
        fence = result["code_fences"][0]
        assert fence["language"] == "python"
        assert fence["start_line"] == 3
        assert fence["end_line"] == 5
        assert fence["closed"] is True

    def test_code_fences_tilde(self):
        text = "~~~rust\nfn main() {}\n~~~"
        result = markdown_structure(text)
        assert len(result["code_fences"]) == 1
        fence = result["code_fences"][0]
        assert fence["language"] == "rust"
        assert fence["closed"] is True

    def test_multiple_code_fences(self):
        text = "```python\npass\n```\n\n```javascript\nconsole.log('hi');\n```\n\n```python\nx = 1\n```"
        result = markdown_structure(text)
        assert len(result["code_fences"]) == 3
        assert result["code_fences"][0]["language"] == "python"
        assert result["code_fences"][0]["start_line"] == 1
        assert result["code_fences"][0]["end_line"] == 3
        assert result["code_fences"][1]["language"] == "javascript"
        assert result["code_fences"][1]["start_line"] == 5
        assert result["code_fences"][1]["end_line"] == 7
        assert result["code_fences"][2]["language"] == "python"
        assert result["code_fences"][2]["start_line"] == 9
        assert result["code_fences"][2]["end_line"] == 11

    def test_unclosed_code_fence(self):
        text = "```python\nprint('hello')"
        result = markdown_structure(text)
        assert len(result["code_fences"]) == 1
        fence = result["code_fences"][0]
        assert fence["language"] == "python"
        assert fence["start_line"] == 1
        assert fence["end_line"] is None
        assert fence["closed"] is False
        assert any("Unclosed" in f for f in result["findings"])

    def test_heading_inside_code_fence_not_detected(self):
        text = "```markdown\n# Not a heading\n```"
        result = markdown_structure(text)
        assert len(result["headings"]) == 0
        assert len(result["code_fences"]) == 1

    def test_links(self):
        text = "Check [Google](https://google.com) and [docs](./readme.md)"
        result = markdown_structure(text)
        assert len(result["links"]) == 2
        assert result["links"][0]["visible_text"] == "Google"
        assert result["links"][0]["target"] == "https://google.com"
        assert result["links"][0]["mismatch_flags"] == []
        assert result["links"][1]["visible_text"] == "docs"
        assert result["links"][1]["target"] == "./readme.md"

    def test_link_url_mismatch(self):
        text = "[click here](https://google.com)"
        result = markdown_structure(text)
        assert len(result["links"]) == 1
        link = result["links"][0]
        assert link["visible_text"] == "click here"
        assert link["target"] == "https://google.com"
        assert "visible_is_url" not in link["mismatch_flags"]

    def test_link_domain_mismatch(self):
        text = "[example.com](https://other.com)"
        result = markdown_structure(text)
        assert len(result["links"]) == 1
        link = result["links"][0]
        assert link["visible_text"] == "example.com"
        assert link["target"] == "https://other.com"
        assert "visible_is_domain" in link["mismatch_flags"]

    def test_html_comments(self):
        text = "Hello <!-- this is a comment --> world"
        result = markdown_structure(text)
        assert len(result["html_comments"]) == 1
        comment = result["html_comments"][0]
        assert comment["text"] == "<!-- this is a comment -->"
        assert comment["line"] == 1

    def test_multiple_html_comments(self):
        text = "<!-- a -->\n<!-- b -->"
        result = markdown_structure(text)
        assert len(result["html_comments"]) == 2

    def test_frontmatter_yaml(self):
        text = "---\ntitle: Test\nversion: 1.0\n---\n\n# Heading"
        result = markdown_structure(text)
        fm = result["frontmatter"]
        assert fm["present"] is True
        assert fm["format"] == "yaml"
        assert fm["line_start"] == 1
        assert fm["line_end"] == 4

    def test_frontmatter_toml(self):
        text = "+++\ntitle = 'Test'\n+++"
        result = markdown_structure(text)
        fm = result["frontmatter"]
        assert fm["present"] is True
        assert fm["format"] == "toml"
        assert fm["line_start"] == 1
        assert fm["line_end"] == 3  # line 1 = +++, line 2 = title, line 3 = +++

    def test_unclosed_frontmatter(self):
        text = "---\ntitle: Test\n\n# Heading"
        result = markdown_structure(text)
        fm = result["frontmatter"]
        assert fm["present"] is True
        assert fm["line_end"] is None
        assert any("Unclosed frontmatter" in f for f in result["findings"])

    def test_table_detection(self):
        text = "| Name | Value |\n|------|-------|\n| a    | 1     |"
        result = markdown_structure(text)
        assert result["tables_detected"] is True

    def test_no_table_without_separator(self):
        text = "| Name | Value |\n| a    | 1     |"
        result = markdown_structure(text)
        assert result["tables_detected"] is False

    def test_include_flags_false(self):
        text = "# Heading\n\n[link](url)\n\n```python\npass\n```\n\n<!-- comment -->"
        result = markdown_structure(
            text,
            include_sections=False,
            include_links=False,
            include_code_fences=False,
            include_html_comments=False,
        )
        assert result["headings"] == []
        assert result["links"] == []
        assert result["code_fences"] == []
        assert result["html_comments"] == []


class TestCodeFenceExtract:
    """Tests for the code_fence_extract function."""

    def test_empty_text(self):
        result = code_fence_extract("")
        assert result["blocks"] == []
        assert result["unclosed_fences"] == []
        assert result["findings"] == []

    def test_single_block(self):
        text = "```python\nprint('hello')\nprint('world')\n```"
        result = code_fence_extract(text)
        assert len(result["blocks"]) == 1
        block = result["blocks"][0]
        assert block["index"] == 0
        assert block["language"] == "python"
        assert block["start_line"] == 1
        assert block["end_line"] == 4
        assert block["closed"] is True
        assert block["content"] == "print('hello')\nprint('world')"
        assert block["fingerprint"] is not None

    def test_multiple_blocks(self):
        text = "```python\na\n```\n\n```javascript\nb\n```"
        result = code_fence_extract(text)
        assert len(result["blocks"]) == 2
        assert result["blocks"][0]["language"] == "python"
        assert result["blocks"][0]["start_line"] == 1
        assert result["blocks"][0]["end_line"] == 3
        assert result["blocks"][1]["language"] == "javascript"
        assert result["blocks"][1]["start_line"] == 5
        assert result["blocks"][1]["end_line"] == 7

    def test_language_filter(self):
        text = "```python\na\n```\n\n```rust\nb\n```\n\n```python\nc\n```"
        result = code_fence_extract(text, language="python")
        assert len(result["blocks"]) == 2
        assert all(b["language"] == "python" for b in result["blocks"])

    def test_language_filter_case_insensitive(self):
        text = "```PYTHON\npass\n```"
        result = code_fence_extract(text, language="python")
        assert len(result["blocks"]) == 1

    def test_include_content_false(self):
        text = "```python\nprint('hello')\n```"
        result = code_fence_extract(text, include_content=False)
        assert result["blocks"][0]["content"] is None
        assert result["blocks"][0]["fingerprint"] is not None

    def test_unclosed_fence(self):
        text = "```python\nprint('hello')"
        result = code_fence_extract(text)
        assert len(result["blocks"]) == 1
        block = result["blocks"][0]
        assert block["closed"] is False
        assert block["end_line"] is None
        assert len(result["unclosed_fences"]) == 1
        assert any("Unclosed" in f for f in result["findings"])

    def test_tilde_fence(self):
        text = "~~~rust\nfn main() {}\n~~~"
        result = code_fence_extract(text)
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["language"] == "rust"
        assert result["blocks"][0]["closed"] is True

    def test_fingerprint_deterministic(self):
        text = "```python\nx = 1\n```"
        r1 = code_fence_extract(text)
        r2 = code_fence_extract(text)
        assert r1["blocks"][0]["fingerprint"] == r2["blocks"][0]["fingerprint"]

    def test_different_content_different_fingerprint(self):
        t1 = "```python\na\n```"
        t2 = "```python\nb\n```"
        r1 = code_fence_extract(t1)
        r2 = code_fence_extract(t2)
        assert r1["blocks"][0]["fingerprint"] != r2["blocks"][0]["fingerprint"]

    def test_block_indices_sequential(self):
        text = "```a\n1\n```\n```b\n2\n```\n```c\n3\n```"
        result = code_fence_extract(text)
        assert [b["index"] for b in result["blocks"]] == [0, 1, 2]

    def test_empty_fence(self):
        text = "```\n```"
        result = code_fence_extract(text)
        assert len(result["blocks"]) == 1
        assert result["blocks"][0]["content"] == ""

    def test_no_language_tag(self):
        text = "```\ncode\n```"
        result = code_fence_extract(text)
        assert result["blocks"][0]["language"] == ""
