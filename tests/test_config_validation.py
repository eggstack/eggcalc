"""Tests for .env and INI config validation tools."""

from eggcalc.exact.config import dotenv_validate, ini_validate
from eggcalc.mcp.tools import dotenv_validate_mcp, ini_validate_mcp


class TestDotenvValidate:
    """Tests for dotenv_validate."""

    def test_simple_valid(self):
        text = "KEY=value\nOTHER=hello"
        result = dotenv_validate(text)
        assert result["parse_ok"] is True
        assert len(result["entries"]) == 2
        assert result["entries"][0]["key"] == "KEY"
        assert result["entries"][0]["value"] == "value"
        assert result["duplicates"] == []
        assert result["invalid_lines"] == []

    def test_blank_and_comment_lines(self):
        text = "# comment\n\nKEY=val\n  \n# another comment"
        result = dotenv_validate(text)
        assert result["parse_ok"] is True
        assert len(result["entries"]) == 1
        assert result["entries"][0]["key"] == "KEY"

    def test_duplicate_keys_warn(self):
        text = "KEY=first\nKEY=second"
        result = dotenv_validate(text, duplicate_policy="warn")
        assert result["parse_ok"] is True
        assert len(result["duplicates"]) == 1
        assert result["duplicates"][0]["key"] == "KEY"
        assert result["duplicates"][0]["first_line"] == 1
        assert result["duplicates"][0]["second_line"] == 2

    def test_duplicate_keys_error(self):
        text = "KEY=first\nKEY=second"
        result = dotenv_validate(text, duplicate_policy="error")
        assert result["parse_ok"] is False
        assert len(result["duplicates"]) == 1

    def test_duplicate_keys_allow(self):
        text = "KEY=first\nKEY=second"
        result = dotenv_validate(text, duplicate_policy="allow")
        assert result["parse_ok"] is True
        assert len(result["duplicates"]) == 1

    def test_invalid_key_name(self):
        text = "123BAD=value\nGOOD=value"
        result = dotenv_validate(text)
        assert result["parse_ok"] is False
        assert len(result["invalid_lines"]) == 1
        assert result["invalid_lines"][0]["reason"].startswith("key")
        assert len(result["entries"]) == 1

    def test_missing_equals(self):
        text = "KEYVALUE\nOTHER=val"
        result = dotenv_validate(text)
        assert result["parse_ok"] is False
        assert result["invalid_lines"][0]["reason"] == "missing '=' separator"

    def test_export_prefix_allowed(self):
        text = "export KEY=value\nOTHER=hello"
        result = dotenv_validate(text, allow_export=True)
        assert result["parse_ok"] is True
        assert len(result["entries"]) == 2
        assert result["entries"][0]["key"] == "KEY"
        assert result["entries"][0]["value"] == "value"

    def test_export_prefix_disallowed(self):
        text = "export KEY=value\nOTHER=hello"
        result = dotenv_validate(text, allow_export=False)
        assert result["parse_ok"] is False
        assert result["invalid_lines"][0]["reason"] == "export keyword not allowed"

    def test_quoted_values(self):
        text = 'KEY="hello world"\nOTHER=\'single quoted\''
        result = dotenv_validate(text)
        assert result["parse_ok"] is True
        assert result["entries"][0]["quote_style"] == '"'
        assert result["entries"][0]["value"] == "hello world"
        assert result["entries"][1]["quote_style"] == "'"
        assert result["entries"][1]["value"] == "single quoted"

    def test_empty_value(self):
        text = "KEY=\nOTHER=value"
        result = dotenv_validate(text)
        assert result["parse_ok"] is True
        assert result["entries"][0]["value"] == ""
        assert result["entries"][0]["value_present"] is True

    def test_value_with_hash_comment(self):
        text = "KEY=value # this is a comment"
        result = dotenv_validate(text)
        assert result["parse_ok"] is True
        assert result["entries"][0]["value"] == "value"

    def test_expansion_syntax_detected(self):
        text = "KEY=${HOME}/path\nOTHER=$VAR_NAME"
        result = dotenv_validate(text)
        assert result["parse_ok"] is True
        assert "KEY" in result["contains_expansion_syntax"]
        assert "OTHER" in result["contains_expansion_syntax"]

    def test_requires_quoting(self):
        text = "KEY=hello world\nOTHER=no-space"
        result = dotenv_validate(text)
        assert "KEY" in result["requires_quoting"]
        assert "OTHER" not in result["requires_quoting"]

    def test_custom_key_pattern(self):
        text = "MY-KEY=value"
        result = dotenv_validate(text, key_pattern=r"^[A-Za-z0-9_-]+$")
        assert result["parse_ok"] is True
        assert result["entries"][0]["key"] == "MY-KEY"

    def test_custom_key_pattern_rejects(self):
        text = "MY-KEY=value"
        result = dotenv_validate(text, key_pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
        assert result["parse_ok"] is False

    def test_multiple_entries_various_formats(self):
        text = (
            "# Config file\n"
            "DB_HOST=localhost\n"
            'DB_PORT="5432"\n'
            "export API_KEY=secret\n"
            "\n"
            "LOG_LEVEL=info # debug level\n"
        )
        result = dotenv_validate(text)
        assert result["parse_ok"] is True
        assert len(result["entries"]) == 4
        keys = [e["key"] for e in result["entries"]]
        assert keys == ["DB_HOST", "DB_PORT", "API_KEY", "LOG_LEVEL"]

    def test_empty_input(self):
        result = dotenv_validate("")
        assert result["parse_ok"] is True
        assert result["entries"] == []
        assert "No entries found" in result["findings"]

    def test_comments_only(self):
        result = dotenv_validate("# just a comment\n# another")
        assert result["parse_ok"] is True
        assert "No entries found" in result["findings"]


class TestDotenvValidateMCP:
    """Tests for dotenv_validate MCP wrapper."""

    def test_mcp_success(self):
        result = dotenv_validate_mcp("KEY=value")
        assert result["ok"] is True
        assert result["tool"] == "dotenv_validate"
        assert result["result"]["parse_ok"] is True

    def test_mcp_input_too_large(self):
        result = dotenv_validate_mcp("x" * 200_000)
        assert result["ok"] is False
        assert result["error_type"] == "input_too_large"

    def test_mcp_invalid_duplicate_policy(self):
        result = dotenv_validate_mcp("KEY=val", duplicate_policy="strict")
        assert result["ok"] is False
        assert result["error_type"] == "invalid_arguments"

    def test_mcp_invalid_key_pattern(self):
        result = dotenv_validate_mcp("KEY=val", key_pattern="[invalid")
        assert result["ok"] is False
        assert result["error_type"] == "invalid_arguments"


class TestIniValidate:
    """Tests for ini_validate."""

    def test_simple_valid(self):
        text = "[section]\nkey = value\nother = hello"
        result = ini_validate(text)
        assert result["parse_ok"] is True
        assert result["sections"] == ["section"]
        assert "section" in result["keys_by_section"]
        assert "key" in result["keys_by_section"]["section"]
        assert "other" in result["keys_by_section"]["section"]

    def test_multiple_sections(self):
        text = "[server]\nhost = localhost\n\n[database]\nport = 5432"
        result = ini_validate(text)
        assert result["parse_ok"] is True
        assert result["sections"] == ["server", "database"]
        assert "host" in result["keys_by_section"]["server"]
        assert "port" in result["keys_by_section"]["database"]

    def test_duplicate_keys_warn(self):
        text = "[section]\nkey = first\nkey = second"
        result = ini_validate(text, duplicate_policy="warn")
        assert result["parse_ok"] is True
        assert len(result["duplicates"]) == 1
        assert result["duplicates"][0]["key"] == "key"
        assert result["duplicates"][0]["section"] == "section"

    def test_duplicate_keys_error(self):
        text = "[section]\nkey = first\nkey = second"
        result = ini_validate(text, duplicate_policy="error")
        assert result["parse_ok"] is False
        assert len(result["duplicates"]) == 1

    def test_duplicate_sections_warn(self):
        text = "[section]\nkey = first\n[section]\nkey = second"
        result = ini_validate(text, duplicate_policy="warn")
        assert result["parse_ok"] is True
        assert len(result["duplicates"]) == 2
        assert "Duplicate section" in result["findings"][0]

    def test_duplicate_sections_error(self):
        text = "[section]\nkey = first\n[section]\nkey = second"
        result = ini_validate(text, duplicate_policy="error")
        assert result["parse_ok"] is False

    def test_top_level_keys(self):
        text = "key1 = value1\nkey2 = value2\n[section]\nkey3 = value3"
        result = ini_validate(text)
        assert result["parse_ok"] is True
        assert "(top-level)" in result["keys_by_section"]
        assert "key1" in result["keys_by_section"]["(top-level)"]
        assert "key2" in result["keys_by_section"]["(top-level)"]
        assert "key3" in result["keys_by_section"]["section"]

    def test_comments(self):
        text = "; comment\n# hash comment\n[section]\nkey = value"
        result = ini_validate(text)
        assert result["parse_ok"] is True
        assert len(result["sections"]) >= 1
        assert "key" in result["keys_by_section"]["section"]

    def test_colon_separator(self):
        text = "[section]\nkey:value"
        result = ini_validate(text)
        assert result["parse_ok"] is True
        assert "key" in result["keys_by_section"]["section"]

    def test_empty_section_name(self):
        text = "[]\nkey = value"
        result = ini_validate(text)
        assert result["parse_ok"] is False
        assert result["invalid_lines"][0]["reason"] == "empty section name"

    def test_malformed_line(self):
        text = "[section]\nthis is not valid"
        result = ini_validate(text)
        assert result["parse_ok"] is False
        assert "not a valid key=value line" in result["invalid_lines"][0]["reason"]

    def test_empty_input(self):
        result = ini_validate("")
        assert result["parse_ok"] is True
        assert result["sections"] == []
        assert "No sections or keys found" in result["findings"]

    def test_comments_only(self):
        result = ini_validate("# just a comment\n; another")
        assert result["parse_ok"] is True
        assert "No sections or keys found" in result["findings"]

    def test_duplicate_policy_allow(self):
        text = "[section]\nkey = first\nkey = second"
        result = ini_validate(text, duplicate_policy="allow")
        assert result["parse_ok"] is True
        assert len(result["duplicates"]) == 1

    def test_whitespace_handling(self):
        text = "  [ section ]  \n  key  =  value  "
        result = ini_validate(text)
        assert result["parse_ok"] is True
        assert result["sections"] == ["section"]
        assert "key" in result["keys_by_section"]["section"]


class TestIniValidateMCP:
    """Tests for ini_validate MCP wrapper."""

    def test_mcp_success(self):
        result = ini_validate_mcp("[section]\nkey = value")
        assert result["ok"] is True
        assert result["tool"] == "ini_validate"
        assert result["result"]["parse_ok"] is True

    def test_mcp_input_too_large(self):
        result = ini_validate_mcp("x" * 200_000)
        assert result["ok"] is False
        assert result["error_type"] == "input_too_large"

    def test_mcp_invalid_duplicate_policy(self):
        result = ini_validate_mcp("[s]\nk=v", duplicate_policy="strict")
        assert result["ok"] is False
        assert result["error_type"] == "invalid_arguments"


class TestDotenvValidateComplex:
    """Edge case tests for dotenv_validate."""

    def test_value_with_equals(self):
        text = "KEY=a=b=c"
        result = dotenv_validate(text)
        assert result["parse_ok"] is True
        assert result["entries"][0]["value"] == "a=b=c"

    def test_value_with_special_chars(self):
        text = 'KEY="hello ${WORLD}!"'
        result = dotenv_validate(text)
        assert result["parse_ok"] is True
        assert result["entries"][0]["value"] == "hello ${WORLD}!"
        assert "KEY" in result["contains_expansion_syntax"]

    def test_no_entries_all_invalid(self):
        text = "123BAD\nNO_EQUALS\n"
        result = dotenv_validate(text)
        assert result["parse_ok"] is False
        assert len(result["entries"]) == 0
        assert len(result["invalid_lines"]) == 2


class TestIniValidateComplex:
    """Edge case tests for ini_validate."""

    def test_multiple_keys_same_section(self):
        text = "[db]\nhost = localhost\nport = 5432\nname = mydb"
        result = ini_validate(text)
        assert result["parse_ok"] is True
        assert len(result["keys_by_section"]["db"]) == 3

    def test_section_with_no_keys(self):
        text = "[empty]\n\n[populated]\nkey = val"
        result = ini_validate(text)
        assert result["parse_ok"] is True
        assert "empty" in result["sections"]
        assert result["keys_by_section"]["empty"] == []
