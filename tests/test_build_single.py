"""Tests for build_single.py — verifies the single-file build produces correct output."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import pytest

# Path to the build script
BUILD_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "build_single.py")


def _run_eggcalc_module(expr: str) -> str:
    """Run an expression using the package-mode eggcalc and return stdout."""
    result = subprocess.run(
        [sys.executable, "-m", "eggcalc", "-e", expr],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def _run_single_file(path: str, expr: str) -> str:
    """Run an expression using the single-file build and return stdout."""
    result = subprocess.run(
        [sys.executable, path, "-e", expr],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


@pytest.fixture(scope="module")
def single_file_path():
    """Build the single file once for the module."""
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        output_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, BUILD_SCRIPT, "-o", output_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"Build failed: {result.stderr}"
        assert os.path.exists(output_path), "Built file does not exist"
        yield output_path
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


# Representative expressions covering the core pipeline
BUILD_TEST_CASES = [
    # Basic math
    ("5 + 3", "8"),
    ("2 ** 10", "1024"),
    ("sqrt(144)", "12.0"),
    # Constants
    ("pi", "3.141592653589793"),
    ("e", "2.718281828459045"),
    # Functions
    ("sin(0)", "0.0"),
    ("floor(3.7)", "3"),
    ("ceil(3.2)", "4"),
    ("factorial(5)", "120"),
    # Unit conversion via evaluate (direct math)
    ("100 * 1", "100"),
]


class TestBuildSingleFile:
    """Verify single-file build produces correct results."""

    def test_build_succeeds(self, single_file_path):
        assert os.path.exists(single_file_path)
        assert os.access(single_file_path, os.X_OK)

    def test_build_file_parses(self, single_file_path):
        """Built file should parse as valid Python."""
        # Use forward slashes to avoid backslash-escape issues on Windows
        path_str = str(single_file_path).replace("\\", "/")
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import ast; ast.parse(open('{path_str}', encoding='utf-8').read())",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"AST parse failed: {result.stderr}"

    @pytest.mark.parametrize("expr,expected", BUILD_TEST_CASES)
    def test_math_expressions(self, single_file_path, expr, expected):
        """Single-file build should evaluate math expressions correctly."""
        result = _run_single_file(single_file_path, expr)
        assert result == expected, f"Expression '{expr}' gave '{result}', expected '{expected}'"

    def test_blocked_import(self, single_file_path):
        """Single-file build should block dangerous imports."""
        result = subprocess.run(
            [sys.executable, single_file_path, "-e", "import os"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_matches_package_mode(self, single_file_path):
        """Results should match package-mode for a set of expressions."""
        test_exprs = ["5+3", "sqrt(144)", "2**10", "floor(3.7)"]
        for expr in test_exprs:
            pkg_result = _run_eggcalc_module(expr)
            single_result = _run_single_file(single_file_path, expr)
            assert (
                pkg_result == single_result
            ), f"Mismatch for '{expr}': package={pkg_result!r}, single={single_result!r}"

    @pytest.mark.parametrize(
        "expr",
        [
            # Arithmetic operators
            "2 + 3",
            "5 - 3",
            "4 * 5",
            "10 / 3",
            # Floor division and modulo
            "7 // 2",
            "7 % 2",
            # Exponentiation (^ is rewritten to ** by CLI normalization)
            "2 ^ 3",
            "2 + 3 ^ 2",
            "2 * 3 ^ 2",
            "2 ^ 3 ^ 2",
            # Unary minus with exponentiation
            "-2 ^ 2",
            "(-2) ^ 2",
            # Word-form XOR
            "5 xor 3",
            "5 bitxor 3",
            # Precedence
            "2 + 3 * 4",
            "(2 + 3) * 4",
            # Functions and constants
            "sqrt(144)",
            "abs(-7)",
            "pi",
        ],
    )
    def test_operator_matrix_parity(self, single_file_path, expr):
        """Package and single-file should agree across the full operator matrix."""
        pkg_result = _run_eggcalc_module(expr)
        single_result = _run_single_file(single_file_path, expr)
        assert (
            pkg_result == single_result
        ), f"Mismatch for '{expr}': package={pkg_result!r}, single={single_result!r}"
