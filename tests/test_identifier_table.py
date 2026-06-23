"""Tests for identifier_table_inspect function."""

from eggcalc.exact.identifier_inspect import (
    identifier_table_inspect,
)


class TestIdentifierTableInspect:
    """Tests for the identifier_table_inspect core function."""

    def test_empty_identifiers(self):
        result = identifier_table_inspect([])
        assert result["count"] == 0
        assert result["collisions"] == []
        assert result["reserved_keyword_hits"] == []
        assert result["mixed_style_groups"] == []
        assert result["findings"] == []

    def test_single_identifier_no_collision(self):
        result = identifier_table_inspect([{"name": "myVar"}])
        assert result["count"] == 1
        assert result["collisions"] == []

    def test_casefold_collision(self):
        result = identifier_table_inspect(
            [
                {"name": "myVar"},
                {"name": "myvar"},
            ]
        )
        assert result["count"] == 2
        casefold_collisions = [c for c in result["collisions"] if c["kind"] == "casefold"]
        assert len(casefold_collisions) == 1
        assert set(casefold_collisions[0]["names"]) == {"myVar", "myvar"}

    def test_casefold_no_collision_different_names(self):
        result = identifier_table_inspect(
            [
                {"name": "foo"},
                {"name": "bar"},
            ]
        )
        casefold_collisions = [c for c in result["collisions"] if c["kind"] == "casefold"]
        assert len(casefold_collisions) == 0

    def test_normalization_collision(self):
        result = identifier_table_inspect(
            [
                {"name": "cafe\u0301"},
                {"name": "caf\u00e9"},
            ]
        )
        assert result["count"] == 2
        norm_collisions = [c for c in result["collisions"] if c["kind"] == "normalization"]
        assert len(norm_collisions) == 1

    def test_normalization_no_collision_different_names(self):
        result = identifier_table_inspect(
            [
                {"name": "hello"},
                {"name": "world"},
            ]
        )
        norm_collisions = [c for c in result["collisions"] if c["kind"] == "normalization"]
        assert len(norm_collisions) == 0

    def test_confusable_near_collision(self):
        result = identifier_table_inspect(
            [
                {"name": "paypal"},
                {"name": "paypa1"},
            ]
        )
        conf_collisions = [c for c in result["collisions"] if c["kind"] == "confusable"]
        assert len(conf_collisions) == 1

    def test_style_variant(self):
        result = identifier_table_inspect(
            [
                {"name": "my_var"},
                {"name": "myVar"},
            ]
        )
        style_collisions = [c for c in result["collisions"] if c["kind"] == "style_variant"]
        assert len(style_collisions) == 1

    def test_style_variant_kebab_vs_snake(self):
        result = identifier_table_inspect(
            [
                {"name": "my-var"},
                {"name": "my_var"},
            ]
        )
        style_collisions = [c for c in result["collisions"] if c["kind"] == "style_variant"]
        assert len(style_collisions) == 1

    def test_no_style_variant_same_style(self):
        result = identifier_table_inspect(
            [
                {"name": "my_var"},
                {"name": "your_var"},
            ]
        )
        style_collisions = [c for c in result["collisions"] if c["kind"] == "style_variant"]
        assert len(style_collisions) == 0

    def test_reserved_keyword_python(self):
        result = identifier_table_inspect(
            [
                {"name": "if", "file": "main.py", "line": 10},
                {"name": "my_var"},
            ],
            language="python",
        )
        assert len(result["reserved_keyword_hits"]) == 1
        hit = result["reserved_keyword_hits"][0]
        assert hit["name"] == "if"
        assert hit["language"] == "python"
        assert hit["file"] == "main.py"
        assert hit["line"] == 10

    def test_reserved_keyword_rust(self):
        result = identifier_table_inspect(
            [
                {"name": "fn"},
            ],
            language="rust",
        )
        assert len(result["reserved_keyword_hits"]) == 1
        assert result["reserved_keyword_hits"][0]["name"] == "fn"

    def test_reserved_keyword_javascript(self):
        result = identifier_table_inspect(
            [
                {"name": "const"},
            ],
            language="javascript",
        )
        assert len(result["reserved_keyword_hits"]) == 1

    def test_reserved_keyword_typescript(self):
        result = identifier_table_inspect(
            [
                {"name": "readonly"},
            ],
            language="typescript",
        )
        assert len(result["reserved_keyword_hits"]) == 1

    def test_reserved_keyword_generic_none(self):
        result = identifier_table_inspect(
            [
                {"name": "if"},
            ],
            language="generic",
        )
        assert len(result["reserved_keyword_hits"]) == 0

    def test_mixed_style_groups(self):
        result = identifier_table_inspect(
            [
                {"name": "my_var"},
                {"name": "myVar"},
                {"name": "my-var"},
            ]
        )
        assert len(result["mixed_style_groups"]) == 1
        group = result["mixed_style_groups"][0]
        assert group["stripped"] == "myvar"
        assert len(group["names"]) == 3
        assert len(group["styles"]) == 3

    def test_mixed_style_groups_no_mixed(self):
        result = identifier_table_inspect(
            [
                {"name": "my_var"},
                {"name": "your_var"},
            ]
        )
        assert len(result["mixed_style_groups"]) == 0

    def test_checks_filter_casefold_only(self):
        result = identifier_table_inspect(
            [
                {"name": "myVar"},
                {"name": "myvar"},
            ],
            checks=["casefold"],
        )
        assert len(result["collisions"]) == 1
        assert result["collisions"][0]["kind"] == "casefold"

    def test_checks_filter_reserved_only(self):
        result = identifier_table_inspect(
            [
                {"name": "if"},
                {"name": "my_var"},
            ],
            checks=["reserved"],
        )
        assert len(result["collisions"]) == 0
        assert len(result["reserved_keyword_hits"]) == 1

    def test_checks_empty_list(self):
        result = identifier_table_inspect(
            [
                {"name": "myVar"},
                {"name": "myvar"},
            ],
            checks=[],
        )
        assert len(result["collisions"]) == 0
        assert len(result["reserved_keyword_hits"]) == 0
        assert len(result["mixed_style_groups"]) == 0

    def test_multiple_collisions(self):
        result = identifier_table_inspect(
            [
                {"name": "myVar"},
                {"name": "myvar"},
                {"name": "my_var"},
                {"name": "if"},
            ],
            language="python",
        )
        casefold_collisions = [c for c in result["collisions"] if c["kind"] == "casefold"]
        assert len(casefold_collisions) >= 1
        style_collisions = [c for c in result["collisions"] if c["kind"] == "style_variant"]
        assert len(style_collisions) >= 1
        assert len(result["reserved_keyword_hits"]) == 1

    def test_findings_populated(self):
        result = identifier_table_inspect(
            [
                {"name": "myVar"},
                {"name": "myvar"},
            ]
        )
        assert len(result["findings"]) > 0
        assert any("Casefold" in f for f in result["findings"])

    def test_no_findings_when_clean(self):
        result = identifier_table_inspect(
            [
                {"name": "alpha"},
                {"name": "bravo"},
                {"name": "charlie"},
            ]
        )
        assert result["findings"] == []

    def test_identifier_with_metadata(self):
        result = identifier_table_inspect(
            [
                {"name": "myVar", "kind": "function", "file": "main.py", "line": 5},
                {"name": "myvar", "kind": "variable", "file": "other.py", "line": 10},
            ]
        )
        casefold_collisions = [c for c in result["collisions"] if c["kind"] == "casefold"]
        assert len(casefold_collisions) == 1

    def test_leading_underscore_style(self):
        result = identifier_table_inspect(
            [
                {"name": "_private_var"},
                {"name": "_privateVar"},
            ]
        )
        style_collisions = [c for c in result["collisions"] if c["kind"] == "style_variant"]
        assert len(style_collisions) == 1

    def test_screaming_snake_case(self):
        result = identifier_table_inspect(
            [
                {"name": "MAX_SIZE"},
                {"name": "max_size"},
            ]
        )
        style_collisions = [c for c in result["collisions"] if c["kind"] == "style_variant"]
        assert len(style_collisions) == 1

    def test_pascal_case(self):
        result = identifier_table_inspect(
            [
                {"name": "MyClass"},
                {"name": "my_class"},
            ]
        )
        style_collisions = [c for c in result["collisions"] if c["kind"] == "style_variant"]
        assert len(style_collisions) == 1
