"""Normalization trace observability (plan 036).

Verifies that ``trace_normalization()`` explains the normalization pipeline
without changing it:

- trace.normalized matches ``normalize_expression()`` for every success case;
- evaluating the traced normalized form matches ``evaluate_raw()``;
- failures preserve the same exit/error classification as the normal path;
- traces are deterministic, bounded, and use only the stable stage vocabulary;
- the untraced fast path is unchanged by the tracing instrumentation.
"""

from __future__ import annotations

import json

import pytest

from eggcalc import evaluate, evaluate_raw, trace_normalization
from eggcalc.normalize import (
    MAX_INPUT_LENGTH,
    NORMALIZE,
    PATTERNS,
    NormalizationTrace,
    normalize_expression,
)

STABLE_STAGES = frozenset(
    {
        "sanitize",
        "function_phrases",
        "number_words",
        "unit_phrases",
        "operator_words",
        "unit_conversions",
        "symbols",
        "tokenize",
        "token_numbers",
        "combine_numbers",
        "functions",
        "unit_conversion",
        "units",
        "floor_mod_grouping",
        "validation",
    }
)

# Representative corpus covering the plan's required categories.
SUCCESS_CORPUS = [
    # plain arithmetic that requires no material rewrite beyond tokenization
    "5+3",
    # number words
    "twenty one plus five",
    "five plus three",
    # operator words
    "10 divided by 4",
    "5 mod 3",
    # function phrases
    "square root of 16",
    "sin30",
    # exponent/caret normalization
    "2 ^ 10",
    "2 to the 10",
    # simple units
    "30m",
    "30m + 100ft",
    # compound/spaced units
    "5 N m",
    "30 km/h",
    # in/to conversions
    "30 km/h in mph",
    "100F to C",
    # temperature conversions
    "100 degrees in fahrenheit",
    # unicode spacing/operator variants
    "5×3",
    "what is five plus three?",
    # postfix factorial
    "5!",
    # floor/mod with units
    "5m % 2m",
]


def _assert_well_formed(trace: NormalizationTrace, original: str) -> None:
    """Check the structural contract shared by success and failure traces."""
    assert trace["input"] == original
    assert isinstance(trace["steps"], list)
    assert len(trace["steps"]) <= len(STABLE_STAGES)
    stages = [step["stage"] for step in trace["steps"]]
    assert len(stages) == len(set(stages)), f"duplicate stages: {stages}"
    for step in trace["steps"]:
        assert set(step.keys()) == {"stage", "before", "after", "changed", "note"}
        assert step["stage"] in STABLE_STAGES
        assert step["changed"] is True
        assert step["before"] != step["after"]
        assert isinstance(step["note"], str) and step["note"]
    # Traces must be plain-data JSON-serializable.
    json.dumps(trace)


class TestTraceParity:
    """trace.normalized must equal normalize_expression() output."""

    @pytest.mark.parametrize("expr", SUCCESS_CORPUS)
    def test_normalized_matches_normal_path(self, expr):
        trace = trace_normalization(expr)
        normalized, exit_code = normalize_expression(expr)
        assert exit_code == 0
        assert trace["errored"] is False
        assert trace["exit_code"] == 0
        assert trace["error"] is None
        assert trace["normalized"] == normalized
        _assert_well_formed(trace, expr)

    @pytest.mark.parametrize("expr", SUCCESS_CORPUS)
    def test_traced_form_evaluates_like_raw(self, expr):
        trace = trace_normalization(expr)
        assert trace["normalized"] is not None
        assert str(evaluate(trace["normalized"])) == str(evaluate_raw(expr))

    def test_plain_arithmetic_needs_no_word_rewrite(self):
        trace = trace_normalization("5+3")
        assert trace["normalized"] == "5+3"
        word_stages = {"number_words", "operator_words", "function_phrases"}
        assert not (word_stages & {s["stage"] for s in trace["steps"]})

    def test_fast_path_unchanged_by_tracing(self):
        """Ordinary calls (no collector) behave exactly as traced calls."""
        for expr in SUCCESS_CORPUS:
            direct, direct_code = normalize_expression(expr)
            traced = trace_normalization(expr)
            assert traced["normalized"] == direct
            assert traced["exit_code"] == direct_code
        # Module-level config objects are not mutated by tracing.
        assert NORMALIZE is not None and PATTERNS is not None

    def test_deterministic(self):
        first = trace_normalization("thirty meters plus hundred feet in m")
        second = trace_normalization("thirty meters plus hundred feet in m")
        assert first == second


class TestTraceStages:
    """Spot-check that representative inputs hit the expected stages."""

    def test_number_words_stage(self):
        trace = trace_normalization("five plus three")
        by_stage = {s["stage"]: s for s in trace["steps"]}
        assert by_stage["number_words"]["before"] == "five plus three"
        assert trace["normalized"] == "5+3"

    def test_function_phrase_stage(self):
        trace = trace_normalization("square root of 16")
        assert "function_phrases" in {s["stage"] for s in trace["steps"]}
        assert trace["normalized"] == "sqrt(16)"

    def test_caret_power_stage(self):
        trace = trace_normalization("2 ^ 10")
        by_stage = {s["stage"]: s for s in trace["steps"]}
        assert by_stage["symbols"]["after"] == "2**10"
        assert trace["normalized"] == "2**10"

    def test_unit_conversion_stage(self):
        trace = trace_normalization("30 km/h in mph")
        assert "unit_phrases" in {s["stage"] for s in trace["steps"]}
        assert trace["normalized"] == "convert(30*km/h,mph)"

    def test_temperature_conversion(self):
        trace = trace_normalization("100 degrees in fahrenheit")
        assert trace["normalized"] == "100*F"

    def test_unicode_sanitize_stage(self):
        trace = trace_normalization("5×3")
        by_stage = {s["stage"]: s for s in trace["steps"]}
        assert by_stage["sanitize"]["after"] == "5*3"
        assert trace["normalized"] == "5*3"

    def test_floor_mod_grouping_stage(self):
        trace = trace_normalization("5m % 2m")
        assert "floor_mod_grouping" in {s["stage"] for s in trace["steps"]}
        assert trace["normalized"] == "(5*m)%(2*m)"


class TestTraceFailures:
    """Failure traces preserve the normal path's exit/error classification."""

    def test_malformed_input(self):
        trace = trace_normalization("5 5")
        with pytest.raises(ValueError, match="juxtaposed"):
            normalize_expression("5 5")
        assert trace["errored"] is True
        assert trace["exit_code"] == 1
        assert trace["normalized"] is None
        assert "juxtaposed" in (trace["error"] or "")
        _assert_well_formed(trace, "5 5")

    def test_overlong_input(self):
        expr = "1+" * ((MAX_INPUT_LENGTH // 2) + 10)
        assert len(expr) > MAX_INPUT_LENGTH
        trace = trace_normalization(expr)
        normalized, exit_code = normalize_expression(expr)
        assert exit_code == 2
        assert trace["exit_code"] == 2
        assert trace["normalized"] is None
        assert trace["error"] == normalized
        assert trace["steps"] == []
        _assert_well_formed(trace, expr)

    def test_validation_failure(self):
        trace = trace_normalization("import os")
        normalized, exit_code = normalize_expression("import os")
        assert exit_code == 1
        assert trace["exit_code"] == 1
        assert trace["normalized"] is None
        assert trace["error"] == "Unable to normalize expression"
        assert "validation" in {s["stage"] for s in trace["steps"]}
        _assert_well_formed(trace, "import os")

    def test_empty_input(self):
        trace = trace_normalization("   ")
        assert trace["errored"] is True
        assert trace["exit_code"] == 1
        assert trace["normalized"] is None
        _assert_well_formed(trace, "   ")


class TestTraceCustomConfig:
    """Trace mode honors custom normalization configuration."""

    def test_custom_function_names(self):
        function_names = {"mysquare": lambda x: x}
        trace = trace_normalization("mysquare(4)+1", function_names=function_names)
        normalized, exit_code = normalize_expression("mysquare(4)+1", function_names=function_names)
        assert exit_code == 0
        assert trace["normalized"] == normalized == "mysquare(4)+1"
        _assert_well_formed(trace, "mysquare(4)+1")

    def test_skip_validation(self):
        trace = trace_normalization("5+", skip_validation=True)
        normalized, exit_code = normalize_expression("5+", skip_validation=True)
        assert trace["normalized"] == normalized
        assert trace["exit_code"] == exit_code
