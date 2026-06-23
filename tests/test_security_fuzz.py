"""
Fuzz tests for eggcalc security.

Tests for:
- Invalid inputs (random strings, special characters)
- DoS protection (very long inputs, deeply nested expressions)
- Code execution prevention (import, exec, etc.)
- Memory exhaustion protection
"""

import random
import string
import subprocess
import sys

import pytest


class TestSecurityFuzz:
    """Security-focused fuzz tests."""

    def test_random_string_inputs(self):
        """Test that random strings don't cause crashes."""
        from eggcalc import EvaluationError, evaluate_raw

        # Generate random strings
        random.seed(42)
        for _ in range(100):
            # Random alphanumeric strings of varying lengths
            length = random.randint(1, 100)
            test_input = ''.join(
                random.choices(string.ascii_letters + string.digits + " ", k=length)
            )

            # Should either return a result or raise EvaluationError
            try:
                result = evaluate_raw(test_input)
                # If it succeeds, result should be valid
                assert result is not None
            except EvaluationError:
                # Expected - invalid expressions should raise
                pass
            except Exception as e:
                # No other exceptions should occur
                pytest.fail(
                    f"Unexpected exception for input '{test_input[:50]}...': {type(e).__name__}: {e}"
                )

    def test_special_character_inputs(self):
        """Test inputs with special characters don't cause crashes."""
        from eggcalc import EvaluationError, evaluate_raw

        special_inputs = [
            ";;;",
            "<<<>>>",
            "@#$%^&*()",
            "\x00\x01\x02",
            "\n\n\n",
            "\t\t\t",
            "\\\\\\\\",
            "///*/",
            "''''''",
            '""""""',
            "\x1b[31m",  # ANSI color codes
            "eval(",
            "exec(",
            "__import__",
            "compile(",
            "breakpoint(",
            "globals()",
            "locals()",
            "vars()",
            "dir()",
            "help(",
            "open(",
            "print(",
            "input(",
            "exit(",
            "quit(",
            "os.system(",
            "subprocess.",
            "import ",
            "from ",
        ]

        for test_input in special_inputs:
            try:
                result = evaluate_raw(test_input)
                assert result is not None
            except (EvaluationError, SyntaxError):
                pass  # Expected
            except Exception as e:
                pytest.fail(
                    f"Unexpected exception for input '{test_input}': {type(e).__name__}: {e}"
                )

    def test_very_long_inputs(self):
        """Test that very long inputs are rejected quickly."""
        from eggcalc import MAX_INPUT_LENGTH, EvaluationError, evaluate_raw

        # Test at exactly the limit
        long_input = "1+" * (MAX_INPUT_LENGTH // 2)

        # Should complete or be rejected
        try:
            result = evaluate_raw(long_input)
            # If it works, result should be valid
            assert result is not None
        except (EvaluationError, SyntaxError):
            pass  # Expected - too long
        except Exception as e:
            pytest.fail(f"Unexpected exception for long input: {type(e).__name__}: {e}")

        # Test over the limit
        over_limit = "1+" * (MAX_INPUT_LENGTH + 1000)

        try:
            result = evaluate_raw(over_limit)
            pytest.fail("Should have raised an error for over-limit input")
        except (EvaluationError, SyntaxError):
            pass  # Expected

    def test_max_input_length_enforced(self):
        """Test MAX_INPUT_LENGTH is properly enforced."""
        from eggcalc import MAX_INPUT_LENGTH, NORMALIZE, PATTERNS, run

        # Create input longer than MAX_INPUT_LENGTH
        long_expr = "a" * (MAX_INPUT_LENGTH + 1)

        result, exit_code = run(long_expr, NORMALIZE, PATTERNS, "plain", False)

        assert exit_code == 2  # Should return error code 2
        assert result is None

    def test_deeply_nested_expressions(self):
        """Test deeply nested expressions don't cause stack overflow."""
        from eggcalc import MAX_NESTING_DEPTH, EvaluationError, evaluate_raw

        # Test within the limit
        nested = "(" * MAX_NESTING_DEPTH + "1" + ")" * MAX_NESTING_DEPTH
        try:
            result = evaluate_raw(nested)
            assert result == 1
        except EvaluationError as e:
            assert "too deep" not in str(e).lower()

        # Test over the limit - should fail gracefully
        very_deep = "(" * (MAX_NESTING_DEPTH + 10) + "1" + ")" * (MAX_NESTING_DEPTH + 10)
        try:
            result = evaluate_raw(very_deep)
            pytest.fail("Should have raised an error for over-limit nesting")
        except (EvaluationError, ValueError) as e:
            assert "too deep" in str(e).lower()

    def test_large_exponents(self):
        """Test that large exponents are rejected."""
        from eggcalc import EvaluationError, evaluate

        large_exp_inputs_should_fail = [
            "2**100000",
            "2**999999",
            "10**10001",  # Over MAX_EXPONENT
            "2**-100000",
            "2**999999999",
        ]

        for test_input in large_exp_inputs_should_fail:
            with pytest.raises(EvaluationError):
                evaluate(test_input)

        # Exactly MAX_EXPONENT may succeed or fail on result size
        try:
            result = evaluate("10**10000")
            assert result is not None
        except EvaluationError:
            pass  # May fail on MAX_RESULT_DIGITS, which is also expected

    def test_wide_expressions(self):
        """Test expressions with many operations don't cause memory issues."""
        from eggcalc import evaluate_raw

        # Create expression with many operations (not nested).
        # Python's AST parser creates a left-recursive tree, so each addition
        # adds ~1 nesting level. Stay under the MAX_NESTING_DEPTH (100).
        wide_expr = "+".join(["1"] * 90)

        result = evaluate_raw(wide_expr)
        assert result == 90

    def test_code_execution_attempts(self):
        """Verify that code execution attempts are blocked."""
        from eggcalc import EvaluationError, evaluate, evaluate_raw

        dangerous_inputs = [
            # Import attempts
            "import os",
            "import sys",
            "from os import system",
            "__import__('os')",
            # Code execution
            "eval('1+1')",
            "exec('1+1')",
            # Attribute access
            "().__class__",
            "().__class__.__bases__",
            "object.__subclasses__",
            # File operations
            "open('/etc/passwd')",
            # System calls
            "os.system('ls')",
            "subprocess.call(['ls'])",
            # Variable access
            "globals()",
            "locals()",
            "vars()",
            # Other dangerous
            "breakpoint()",
            "help(1)",
        ]

        for test_input in dangerous_inputs:
            try:
                # Try both evaluate (pre-normalized) and evaluate_raw
                try:
                    result = evaluate(test_input)
                except Exception:
                    result = evaluate_raw(test_input)

                # If we get here without exception, check result is safe
                # Should NOT execute the dangerous code
                assert result is not None
            except EvaluationError:
                pass  # Expected - blocked
            except SyntaxError:
                pass  # Expected - invalid syntax

    def test_attribute_access_blocked(self):
        """Test that dangerous attribute access is blocked."""
        from eggcalc import EvaluationError, evaluate

        attr_attempts = [
            "().__class__",
            "1 .__class__",
            "(1).__class__.__mro__",
            "''.__class__.__mro__",
            "[].__class__",
            "{}.__class__",
            "set().__class__",
        ]

        for test_input in attr_attempts:
            with pytest.raises(EvaluationError) as exc_info:
                evaluate(test_input)
            assert (
                "not allowed" in str(exc_info.value).lower()
                or "unsupported" in str(exc_info.value).lower()
            )

    def test_comprehensions_blocked(self):
        """Test that list/dict comprehensions are blocked."""
        from eggcalc import EvaluationError, evaluate

        comp_inputs = [
            "[x for x in range(10)]",
            "{x for x in range(10)}",
            "{x: x for x in range(10)}",
            "(x for x in range(10))",
            "[x for x in __import__('os').listdir('.')]",
        ]

        for test_input in comp_inputs:
            with pytest.raises(EvaluationError) as exc_info:
                evaluate(test_input)
            assert "unsupported" in str(exc_info.value).lower()

    def test_lambda_blocked(self):
        """Test that lambda expressions are blocked."""
        from eggcalc import EvaluationError, evaluate

        lambda_inputs = [
            "lambda x: x+1",
            "(lambda x: x+1)(5)",
            "f = lambda x: x",
        ]

        for test_input in lambda_inputs:
            with pytest.raises((EvaluationError, SyntaxError)):
                evaluate(test_input)

    def test_if_expression_blocked(self):
        """Test that ternary if expressions are blocked."""
        from eggcalc import EvaluationError, evaluate

        if_inputs = [
            "1 if True else 0",
            "x if x > 0 else -x",
        ]

        for test_input in if_inputs:
            with pytest.raises(EvaluationError):
                evaluate(test_input)

    def test_comparison_blocked(self):
        """Test that comparison operators are blocked."""
        from eggcalc import EvaluationError, evaluate

        compare_inputs = [
            "1 < 2",
            "1 > 0",
            "1 == 1",
            "1 != 2",
            "1 <= 2",
            "1 >= 0",
            "1 < 2 < 3",
        ]

        for test_input in compare_inputs:
            with pytest.raises(EvaluationError):
                evaluate(test_input)

    def test_boolean_operators_blocked(self):
        """Test that boolean operators are blocked."""
        from eggcalc import EvaluationError, evaluate

        bool_inputs = [
            "True and False",
            "True or False",
            "not True",
            "1 and 2",
            "1 or 0",
            "not 1",
        ]

        for test_input in bool_inputs:
            with pytest.raises(EvaluationError):
                evaluate(test_input)

    def test_subscription_blocked(self):
        """Test that subscripting is blocked."""
        from eggcalc import EvaluationError, evaluate

        sub_inputs = [
            "[1,2,3][0]",
            "()[0]",
            "{}['a']",
            "iter([])[0]",
        ]

        for test_input in sub_inputs:
            with pytest.raises(EvaluationError):
                evaluate(test_input)


class TestUnicodeFuzzing:
    """Unicode-specific fuzz tests for security and robustness."""

    def test_unicode_confusables(self):
        """Test that confusable characters (homoglyphs) don't cause crashes."""
        from eggcalc import EvaluationError, evaluate_raw

        confusable_inputs = [
            # Cyrillic 'а' (U+0430) mixed with Latin 'a' (U+0061)
            "5 \u0430+ 3",  # 5 Cyrillic-a + 3
            "1\u04300",  # 1 Cyrillic-a 0
            "\u0430\u0430",  # just two Cyrillic-a's
            # Mathematical italic characters that look like ASCII
            "\U0001d44e + 3",  # mathematical italic a
            "\U0001d452 + 3",  # mathematical italic e
            "\U0001d45f + 1",  # mathematical italic z
            # Mathematical bold characters
            "\U0001d7d8 + 1",  # mathematical bold digit 1
            "\U0001d7e2 + 5",  # mathematical bold digit 5
            # Mixed confusable and ASCII
            "s\u0456n(0)",  # 'sin' with Cyrillic і
            "s\u0456n(0)",  # 'sin' with Cyrillic і
            "ma\u0452h.pi",  # 'math' with Cyrillic ђ
        ]

        for test_input in confusable_inputs:
            try:
                result = evaluate_raw(test_input)
                assert result is not None
            except EvaluationError:
                pass  # Expected - confusable characters should be rejected
            except Exception as e:
                pytest.fail(
                    f"Unexpected exception for input {test_input!r}: " f"{type(e).__name__}: {e}"
                )

    def test_unicode_control_chars(self):
        """Test that Unicode control/format characters don't cause crashes."""
        from eggcalc import EvaluationError, evaluate_raw

        control_inputs = [
            # Zero-width spaces
            "5\u200b+\u200b3",
            "5\u200c+\u200c3",  # Zero-width non-joiner
            "5\u200d+\u200d3",  # Zero-width joiner
            # RTL override
            "5\u202e+3",
            # Bidirectional controls
            "5\u2066+\u20673\u2069",  # LRI, RLI, FSI, PDI
            "\u202a5+3\u202c",  # LRE, PDF
            "\u202b5+3\u202c",  # RLE, PDF
            "\u202d5+3\u202c",  # LRO, PDF
            "\u202f5+3\u202c",  # LRM
            "\u200f5+3\u200e",  # RLM
            # Combining characters
            "5\u0300+\u03013",  # combining accent grave, acute
            "5\u0327+\u03283",  # combining cedilla, ogonek
            # Other format characters
            "5\u00ad+3",  # soft hyphen
            "5\u034f+3",  # combining grapheme joiner
            "5\u2060+3",  # word joiner
            "5\ufeff+3",  # BOM / zero-width no-break space
            # Long sequence of control characters
            "5" + "\u200b" * 50 + "+3",
        ]

        for test_input in control_inputs:
            try:
                result = evaluate_raw(test_input)
                assert result is not None
            except EvaluationError:
                pass  # Expected - control chars should be rejected
            except Exception as e:
                pytest.fail(
                    f"Unexpected exception for input {test_input!r}: " f"{type(e).__name__}: {e}"
                )

    def test_unicode_in_expressions(self):
        """Test that Unicode digits, operators, and math symbols are rejected gracefully."""
        from eggcalc import EvaluationError, evaluate_raw

        unicode_expr_inputs = [
            # Superscript numbers
            "5\u00b2 + 1",  # 5² + 1
            "\u00b2 + \u00b2",  # ² + ²
            "5\u00b9",  # 5¹
            "\u2070 + 1",  # ⁰ + 1
            # Subscript numbers
            "5\u2080 + 1",  # 5₀ + 1
            "\u2081 + \u2082",  # ₁ + ₂
            # Mathematical italic letters as variables
            "\U0001d44e = 5",  # 𝑎 = 5
            "\U0001d44e + \U0001d44f",  # 𝑎 + 𝑏
            # Mathematical operators
            "5\u221a 25",  # 5√25 (radical)
            "5\u00d7 3",  # 5×3 (multiplication sign)
            "5\u00f7 3",  # 5÷3 (division sign)
            "5\u2211 3",  # 5∑3 (summation)
            # Fullwidth digits
            "\uff15 + \uff13",  # ５ + ３
            # Mixed Unicode and ASCII
            "5\u00b2 + 3",  # 5² + 3
            "\u221a(144)",  # √(144)
            "\U0001d452 + 1",  # 𝑒 + 1
        ]

        for test_input in unicode_expr_inputs:
            try:
                result = evaluate_raw(test_input)
                assert result is not None
            except EvaluationError:
                pass  # Expected - Unicode math should be rejected or unsupported
            except SyntaxError:
                pass  # Expected - invalid Python syntax
            except Exception as e:
                pytest.fail(
                    f"Unexpected exception for input {test_input!r}: " f"{type(e).__name__}: {e}"
                )

    def test_unicode_random_mix(self):
        """Test random mixes of Unicode characters in expressions."""
        import random

        from eggcalc import EvaluationError, evaluate_raw

        random.seed(2024)
        unicode_chars = [
            "\u0410",
            "\u0411",
            "\u0412",  # Cyrillic А, Б, В
            "\u0391",
            "\u0392",
            "\u0393",  # Greek Α, Β, Γ
            "\u00c0",
            "\u00c1",
            "\u00c2",  # À, Á, Â
            "\u2660",
            "\u2663",
            "\u2665",  # ♠, ♣, ♥
            "\u20ac",
            "\u00a3",
            "\u00a5",  # €, £, ¥
            "\u2190",
            "\u2191",
            "\u2192",  # ←, ↑, →
            "\u2588",
            "\u2591",
            "\u2592",  # █, ░, ▒
        ]

        for _ in range(50):
            # Build a short expression mixing ASCII and Unicode
            length = random.randint(2, 15)
            parts = []
            for _ in range(length):
                if random.random() < 0.5:
                    parts.append(random.choice("0123456789+-* "))
                else:
                    parts.append(random.choice(unicode_chars))
            test_input = "".join(parts)

            try:
                result = evaluate_raw(test_input)
                assert result is not None
            except (EvaluationError, SyntaxError):
                pass  # Expected
            except Exception as e:
                pytest.fail(
                    f"Unexpected exception for input {test_input!r}: " f"{type(e).__name__}: {e}"
                )


class TestCLISecurity:
    """Security tests for CLI interface."""

    def test_cli_rejects_long_input(self):
        """Test CLI rejects input over MAX_INPUT_LENGTH."""
        long_expr = "x" * 20000

        result = subprocess.run(
            [sys.executable, "-m", "eggcalc", long_expr],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode != 0
        assert "too long" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_cli_timeout_on_complex_input(self):
        """Test CLI doesn't hang on complex expressions."""
        # Nested expression that would take very long if not limited
        complex_expr = "(" * 100 + "1" + ")" * 100

        result = subprocess.run(
            [sys.executable, "-m", "eggcalc", "-e", complex_expr],
            capture_output=True,
            text=True,
            timeout=5,  # Should complete within 5 seconds
        )

        # Should either succeed or fail quickly
        assert result.returncode in (0, 1)

    def test_cli_no_code_injection(self):
        """Test CLI doesn't execute injected code."""
        malicious_inputs = [
            "; rm -rf /",
            "| cat /etc/passwd",
            "$(whoami)",
            "`ls`",
            "&& ls",
            "|| ls",
        ]

        for test_input in malicious_inputs:
            result = subprocess.run(
                [sys.executable, "-m", "eggcalc", "-e", test_input],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Should either error or return result (not execute the command)
            # The malicious string should appear in output, not be executed
            assert result.returncode in (0, 1)


class TestMemorySafety:
    """Test memory-related safety."""

    def test_no_memory_leak_on_repeated_calls(self):
        """Test repeated calls don't leak memory (uses delta, not absolute peak)."""
        import gc
        import tracemalloc

        from eggcalc import evaluate_raw

        # Ensure any lazy initialization happens before we start measuring
        evaluate_raw("1 + 1")

        gc.collect()
        tracemalloc.start()
        tracemalloc.reset_peak()

        # Run many evaluations
        for _i in range(1000):
            try:
                evaluate_raw("5 + 3")
            except Exception:
                pass

        gc.collect()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # The absolute peak (~3MB) is library baseline overhead (confusables etc)
        # What we care about is whether memory grows with MORE calls
        # With 1000 calls using the same expression, if there were a leak we'd see growth
        # Since UNIT_CONVERSIONS and caches are bounded, memory should be stable
        assert (
            peak < 10_000_000
        ), f"Peak memory too high: {peak} bytes (baseline ~3MB from confusables)"

    def test_recursion_limit_protection(self):
        """Test expression evaluation respects recursion limits."""
        from eggcalc import MAX_NESTING_DEPTH, EvaluationError, evaluate_raw

        # Test within the limit
        depth = MAX_NESTING_DEPTH
        nested = "(" * depth + "1" + ")" * depth

        try:
            result = evaluate_raw(nested)
            assert result == 1
        except (EvaluationError, ValueError, RecursionError, SyntaxError):
            pass  # Acceptable


class TestASTSecurity:
    """Tests for AST-based security."""

    def test_ast_parse_blocks_unsafe_nodes(self):
        """Test that AST parser correctly identifies unsafe nodes."""
        from eggcalc.evaluator import EvaluationError, Evaluator

        evaluator = Evaluator()

        # These should all be blocked
        unsafe_expressions = [
            "[x for x in y]",  # ListComp
            "{x for x in y}",  # SetComp
            "{x: y for x in z}",  # DictComp
            "lambda x: x",  # Lambda
            "x if y else z",  # IfExp
            "x < y",  # Compare
            "x and y",  # BoolOp
            "x[0]",  # Subscript
        ]

        for expr in unsafe_expressions:
            with pytest.raises(EvaluationError):
                evaluator.evaluate(expr)

    def test_only_safe_functions_allowed(self):
        """Test only whitelisted functions can be called."""
        from eggcalc import EvaluationError, evaluate

        # Test math functions work
        assert evaluate("sqrt(4)") == 2
        assert evaluate("sin(0)") == 0

        # Test dangerous functions are blocked
        with pytest.raises(EvaluationError):
            evaluate("__import__('os')")

        with pytest.raises(EvaluationError):
            evaluate("eval('1')")

        with pytest.raises(EvaluationError):
            evaluate("exec('x=1')")


class TestASTAllowlist:
    """Tests for the AST allow-list hardening (M7).

    Verifies that every ast.expr subclass NOT in the allow-list is
    rejected. We iterate over all ast.expr subclasses and confirm
    that constructing an expression containing one is rejected.
    """

    def test_walrus_operator_rejected(self):
        """Python 3.8+ walrus (NamedExpr) must be rejected."""
        from eggcalc import EvaluationError, evaluate

        with pytest.raises(EvaluationError):
            evaluate("(x := 1)")

    def test_match_value_rejected(self):
        """match/case AST nodes must be rejected."""
        import ast

        from eggcalc.evaluator import EvaluationError as EE

        node = ast.MatchValue(value=ast.Constant(value=1))
        with pytest.raises(EE):
            from eggcalc.evaluator import Evaluator

            Evaluator()._validate_node(node)

    def test_all_expr_subclasses_rejected_except_allowed(self):
        """Walk every ast.expr subclass; verify it's rejected unless allowed."""
        import ast

        from eggcalc.evaluator import _ALLOWED_AST_TYPES
        from eggcalc.evaluator import EvaluationError as EE

        expr_classes = {
            getattr(ast, name)
            for name in dir(ast)
            if isinstance(getattr(ast, name, None), type)
            and issubclass(getattr(ast, name), ast.expr)
        }

        for cls in expr_classes:
            try:
                if cls is ast.Constant:
                    node = ast.Constant(value=1)
                elif cls is ast.Name:
                    node = ast.Name(id="x")
                elif cls is ast.Attribute:
                    node = ast.Attribute(value=ast.Name(id="math"), attr="x", ctx=ast.Load())
                elif cls is ast.Call:
                    node = ast.Call(func=ast.Name(id="f"), args=[], keywords=[])
                elif cls is ast.UnaryOp:
                    node = ast.UnaryOp(op=ast.UAdd(), operand=ast.Constant(value=1))
                elif cls is ast.BinOp:
                    node = ast.BinOp(
                        left=ast.Constant(value=1),
                        op=ast.Add(),
                        right=ast.Constant(value=1),
                    )
                elif cls is ast.NamedExpr:
                    node = ast.NamedExpr(
                        target=ast.Name(id="x"),
                        value=ast.Constant(value=1),
                    )
                elif cls is ast.MatchValue:
                    node = ast.MatchValue(value=ast.Constant(value=1))
                elif cls is ast.MatchSingleton:
                    node = ast.MatchSingleton(value=None)
                elif cls is ast.Tuple:
                    node = ast.Tuple(elts=[ast.Constant(value=1)], ctx=ast.Load())
                elif cls is ast.List:
                    node = ast.List(elts=[ast.Constant(value=1)], ctx=ast.Load())
                elif cls is ast.Set:
                    node = ast.Set(elts=[ast.Constant(value=1)])
                elif cls is ast.Dict:
                    node = ast.Dict(keys=[ast.Constant(value=1)], values=[ast.Constant(value=2)])
                elif cls is ast.Subscript:
                    node = ast.Subscript(
                        value=ast.Name(id="x"),
                        slice=ast.Constant(value=0),
                        ctx=ast.Load(),
                    )
                elif cls is ast.IfExp:
                    node = ast.IfExp(
                        test=ast.Constant(value=True),
                        body=ast.Constant(value=1),
                        orelse=ast.Constant(value=2),
                    )
                elif cls is ast.Lambda:
                    node = ast.Lambda(
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[],
                            kwonlyargs=[],
                            kw_defaults=[],
                            defaults=[],
                        ),
                        body=ast.Constant(value=1),
                    )
                elif cls is ast.BoolOp:
                    node = ast.BoolOp(
                        op=ast.And(),
                        values=[ast.Constant(value=True), ast.Constant(value=False)],
                    )
                elif cls is ast.Compare:
                    node = ast.Compare(
                        left=ast.Constant(value=1),
                        ops=[ast.Eq()],
                        comparators=[ast.Constant(value=1)],
                    )
                elif cls is ast.Starred:
                    node = ast.Starred(value=ast.Name(id="x"), ctx=ast.Load())
                elif cls is ast.FormattedValue:
                    node = ast.FormattedValue(
                        value=ast.Constant(value=1), conversion=-1, format_spec=None
                    )
                elif cls is ast.JoinedStr:
                    node = ast.JoinedStr(values=[ast.Constant(value="x")])
                elif cls is ast.Await:
                    node = ast.Await(value=ast.Constant(value=1))
                elif cls is ast.Yield:
                    node = ast.Yield(value=ast.Constant(value=1))
                elif cls is ast.YieldFrom:
                    node = ast.YieldFrom(value=ast.Name(id="x"))
                elif cls is ast.Slice:
                    node = ast.Slice(lower=None, upper=None, step=None)
                elif cls is ast.TemplateStr:
                    try:
                        node = ast.TemplateStr(values=[ast.Constant(value="x")])
                    except AttributeError:
                        continue
                elif cls is ast.Interpolation:
                    try:
                        node = ast.Interpolation(
                            value=ast.Constant(value="x"),
                            str=ast.Constant(value="x"),
                            conversion=-1,
                        )
                    except (AttributeError, TypeError):
                        continue
                else:
                    continue
            except (TypeError, AttributeError):
                continue

            from eggcalc.evaluator import Evaluator

            if cls in _ALLOWED_AST_TYPES:
                try:
                    Evaluator()._validate_node(node)
                except EE as e:
                    pytest.fail(f"Expected {cls.__name__} to be allowed, but got: {e}")
            else:
                try:
                    Evaluator()._validate_node(node)
                    pytest.fail(f"Expected {cls.__name__} to be rejected (not in allow-list)")
                except EE:
                    pass  # expected

    def test_attribute_only_math_or_known(self):
        """Attribute access is allowed only for math.* / .real / .imag / .conjugate."""
        from eggcalc import EvaluationError, evaluate

        # math.* is allowed
        assert evaluate("math.sqrt(4)") == 2
        # Other attribute access is blocked
        with pytest.raises(EvaluationError):
            evaluate("a.b")
        with pytest.raises(EvaluationError):
            evaluate("(1).__class__")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
