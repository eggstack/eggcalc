"""Schema-validation contract tests for MCP tool schemas."""

import inspect

import pytest

from eggcalc.mcp.schemas import PROFILE_NAMES, TOOL_METADATA, TOOL_PROFILES, TOOL_SCHEMAS
from eggcalc.mcp.server import (
    SUPPORTED_SCHEMA_KEYWORDS,
    TOOL_HANDLERS,
    _validate_value_against_schema,
)


def _walk_schema(schema: dict, path: str = "root"):
    """Yield (path, keyword) for every JSON Schema keyword in a schema tree.

    Property names inside ``properties`` are not keywords — only the values
    (which are sub-schemas) are walked recursively.
    """
    if not isinstance(schema, dict):
        return
    for key, value in schema.items():
        yield (f"{path}.{key}", key)
        if key == "properties" and isinstance(value, dict):
            for prop_name, prop_schema in value.items():
                if isinstance(prop_schema, dict):
                    yield from _walk_schema(prop_schema, f"{path}.{key}.{prop_name}")
        elif key == "items" and isinstance(value, dict):
            yield from _walk_schema(value, f"{path}.{key}")
        elif key not in ("properties",) and isinstance(value, dict):
            yield from _walk_schema(value, f"{path}.{key}")
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    yield from _walk_schema(item, f"{path}.{key}[{i}]")


class TestSchemaKeywordWhitelist:
    """Walk all TOOL_SCHEMAS and reject unsupported keywords."""

    def test_no_unsupported_keywords_in_any_tool(self):
        violations = []
        for tool_name, schema in TOOL_SCHEMAS.items():
            input_schema = schema.get("inputSchema", {})
            for path, keyword in _walk_schema(input_schema, f"{tool_name}.inputSchema"):
                if keyword not in SUPPORTED_SCHEMA_KEYWORDS:
                    violations.append(f"{tool_name}: unsupported keyword '{keyword}' at {path}")
        assert not violations, "Unsupported schema keywords found:\n" + "\n".join(violations)


class TestToolHandlerSchemaConsistency:
    """Ensure every tool handler has a schema entry and vice versa."""

    def test_all_handlers_have_schemas(self):
        for name in TOOL_HANDLERS:
            assert name in TOOL_SCHEMAS, f"Handler '{name}' has no entry in TOOL_SCHEMAS"

    def test_all_non_hidden_schema_tools_have_handlers(self):
        for name, meta in TOOL_METADATA.items():
            if meta.get("llm_exposure") == "hidden":
                continue
            assert (
                name in TOOL_HANDLERS
            ), f"Non-hidden tool '{name}' in TOOL_METADATA has no handler"
            assert name in TOOL_SCHEMAS, f"Non-hidden tool '{name}' in TOOL_METADATA has no schema"

    def test_all_profile_visible_tools_have_schemas_and_handlers(self):
        for profile_name in PROFILE_NAMES:
            tool_list = TOOL_PROFILES.get(profile_name, [])
            for tool_name in tool_list:
                assert (
                    tool_name in TOOL_SCHEMAS
                ), f"Tool '{tool_name}' in profile '{profile_name}' has no schema"
                assert (
                    tool_name in TOOL_HANDLERS
                ), f"Tool '{tool_name}' in profile '{profile_name}' has no handler"


class TestRequiredSchemaMatchesHandlerParams:
    """Ensure required schema properties correspond to handler parameters."""

    def test_required_properties_are_handler_params(self):
        for tool_name, handler in TOOL_HANDLERS.items():
            try:
                sig = inspect.signature(handler)
            except (ValueError, TypeError):
                continue
            handler_params = set(sig.parameters.keys())

            schema = TOOL_SCHEMAS.get(tool_name, {})
            input_schema = schema.get("inputSchema", {})
            required = input_schema.get("required", [])
            properties = input_schema.get("properties", {})

            for prop_name in required:
                if prop_name not in handler_params:
                    # The handler may accept **kwargs
                    has_var_keyword = any(
                        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
                    )
                    if not has_var_keyword:
                        pytest.fail(
                            f"Tool '{tool_name}' schema requires '{prop_name}' "
                            f"but handler does not accept it"
                        )

    def test_no_handler_arg_inaccessible_from_schema(self):
        """Every handler parameter should be either in schema properties or be **kwargs."""
        for tool_name, handler in TOOL_HANDLERS.items():
            try:
                sig = inspect.signature(handler)
            except (ValueError, TypeError):
                continue

            has_var_keyword = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )
            if has_var_keyword:
                continue

            schema = TOOL_SCHEMAS.get(tool_name, {})
            input_schema = schema.get("inputSchema", {})
            properties = set(input_schema.get("properties", {}).keys())

            for param_name, param in sig.parameters.items():
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue
                if param.default is not inspect.Parameter.empty:
                    continue
                assert param_name in properties, (
                    f"Tool '{tool_name}' handler has required param '{param_name}' "
                    f"not in schema properties"
                )


class TestSchemaValidationBounds:
    """Adversarial tests for _validate_value_against_schema bounds."""

    def test_max_recursive_depth_rejection(self):
        # Build a schema with depth > 10
        deep_schema = {"type": "object", "properties": {"a": {}}}
        inner = deep_schema["properties"]["a"]
        for _ in range(15):
            inner["type"] = "object"
            inner["properties"] = {"b": {}}
            inner = inner["properties"]["b"]

        result = _validate_value_against_schema(
            {"a": {"b": {"b": {"b": {"b": {}}}}}},
            deep_schema,
            "root",
            max_depth=3,
        )
        assert result is not None
        assert "nesting too deep" in result

    def test_pattern_rejects_invalid_regex(self):
        schema = {"type": "string", "pattern": "([invalid"}
        result = _validate_value_against_schema("test", schema, "test_field")
        assert result is not None
        assert "invalid pattern" in result

    def test_min_max_items(self):
        schema = {"type": "array", "minItems": 2, "maxItems": 3}
        assert _validate_value_against_schema([1], schema, "x") is not None
        assert _validate_value_against_schema([1, 2], schema, "x") is None
        assert _validate_value_against_schema([1, 2, 3], schema, "x") is None
        assert _validate_value_against_schema([1, 2, 3, 4], schema, "x") is not None

    def test_unique_items_rejects_duplicates(self):
        schema = {"type": "array", "uniqueItems": True}
        assert _validate_value_against_schema([1, 2, 3], schema, "x") is None
        assert _validate_value_against_schema([1, 2, 2], schema, "x") is not None

    def test_unique_items_with_dicts(self):
        schema = {"type": "array", "uniqueItems": True}
        assert _validate_value_against_schema([{"a": 1}, {"a": 2}], schema, "x") is None
        assert _validate_value_against_schema([{"a": 1}, {"a": 1}], schema, "x") is not None

    def test_boolean_schema_rejected(self):
        schema = True
        result = _validate_value_against_schema("test", schema, "x")
        assert result is not None
        assert "must be an object" in result

    def test_string_length_min_max(self):
        schema = {"type": "string", "minLength": 3, "maxLength": 5}
        assert _validate_value_against_schema("ab", schema, "x") is not None
        assert _validate_value_against_schema("abc", schema, "x") is None
        assert _validate_value_against_schema("abcde", schema, "x") is None
        assert _validate_value_against_schema("abcdef", schema, "x") is not None

    def test_number_range_constraints(self):
        schema = {"type": "number", "minimum": 0, "maximum": 10}
        assert _validate_value_against_schema(-1, schema, "x") is not None
        assert _validate_value_against_schema(0, schema, "x") is None
        assert _validate_value_against_schema(10, schema, "x") is None
        assert _validate_value_against_schema(11, schema, "x") is not None

    def test_exclusive_minimum_maximum(self):
        schema = {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 10}
        assert _validate_value_against_schema(0, schema, "x") is not None
        assert _validate_value_against_schema(0.1, schema, "x") is None
        assert _validate_value_against_schema(10, schema, "x") is not None
        assert _validate_value_against_schema(9.9, schema, "x") is None

    def test_multiple_of(self):
        schema = {"type": "integer", "multipleOf": 3}
        assert _validate_value_against_schema(9, schema, "x") is None
        assert _validate_value_against_schema(10, schema, "x") is not None

    def test_const_rejects_wrong_value(self):
        schema = {"type": "string", "const": "exact"}
        assert _validate_value_against_schema("exact", schema, "x") is None
        assert _validate_value_against_schema("other", schema, "x") is not None

    def test_enum_rejects_out_of_set(self):
        schema = {"type": "string", "enum": ["a", "b", "c"]}
        assert _validate_value_against_schema("a", schema, "x") is None
        assert _validate_value_against_schema("d", schema, "x") is not None

    def test_nan_rejected_for_number(self):

        schema = {"type": "number"}
        assert _validate_value_against_schema(float("nan"), schema, "x") is not None
        assert _validate_value_against_schema(float("inf"), schema, "x") is not None
        assert _validate_value_against_schema(float("-inf"), schema, "x") is not None

    def test_bool_rejected_for_integer(self):
        schema = {"type": "integer"}
        assert _validate_value_against_schema(True, schema, "x") is not None
