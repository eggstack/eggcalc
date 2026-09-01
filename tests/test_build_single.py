"""Tests for build_single.py — verifies the single-file build produces correct output."""

from __future__ import annotations

import filecmp
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

    @pytest.mark.skipif(
        os.name == "nt", reason="dynamic single-file imports cannot spawn on Windows"
    )
    def test_json_and_regex_mcp_wrappers_execute(self, single_file_path):
        """Renamed MCP wrappers must call exact implementations in the build.

        Runs the import + wrapper calls in a fresh subprocess: importing the
        build in-process makes _get_process_context() pick the fork start
        method, which is unsafe (and flaky) inside the multi-threaded pytest
        process.
        """
        path_str = str(single_file_path).replace("\\", "/")
        script = f"""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("eggcalc_single_smoke", r"{path_str}")
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
calls = [
    module._mcp_validate_json('{{"a": 1}}'),
    module._mcp_json_compare('{{"a": 1}}', '{{"a": 1}}'),
    module._mcp_json_extract('{{"a": 1}}', "/a"),
    module._mcp_json_shape('{{"a": 1}}'),
    module._mcp_regex_finditer("a", "a"),
    module._mcp_regex_safety_check("a+"),
    module._mcp_validate_schema_light('{{"a": 1}}', {{"type": "object"}}),
    module._mcp_json_canonicalize('{{"b": 2, "a": 1}}'),
    module._mcp_json_query('{{"a": 1}}', "/a"),
]
assert all(result.get("ok") is True for result in calls), calls
print("OK")
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert (
            result.returncode == 0 and result.stdout.strip() == "OK"
        ), f"Wrapper smoke failed: {result.stderr}"

    def test_mcp_schema_detail_flag_is_forwarded(self, single_file_path):
        """The single-file wrapper accepts and forwards the schema detail value."""
        for args in (
            ["--mcp", "--mcp-schema-detail", "compact"],
            ["--capabilities", "--mcp-schema-detail", "compact"],
        ):
            result = subprocess.run(
                [sys.executable, single_file_path, *args],
                input="",
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0, f"Single-file flags failed: {result.stderr}"

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


class TestBuildDeterminism:
    """Single-file generation must be byte-for-byte deterministic."""

    def test_deterministic_generation(self):
        """Building twice from the same source must produce identical bytes."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            path1 = f.name
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            path2 = f.name
        try:
            for path in (path1, path2):
                result = subprocess.run(
                    [sys.executable, BUILD_SCRIPT, "-o", path],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                assert result.returncode == 0, f"Build failed: {result.stderr}"
            assert filecmp.cmp(
                path1, path2, shallow=False
            ), "Two builds from the same source produced different output"
        finally:
            for p in (path1, path2):
                if os.path.exists(p):
                    os.unlink(p)


class TestBuildManifestValidation:
    """Build manifest must be self-consistent."""

    def test_validate_build_manifest(self):
        """validate_build_manifest() must return no errors."""
        result = subprocess.run(
            [sys.executable, BUILD_SCRIPT, "--validate"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Manifest validation failed: {result.stderr}"
        assert "ERROR" not in result.stdout, f"Manifest validation errors: {result.stdout}"

    def test_no_residual_relative_imports(self, single_file_path):
        """Generated file must not contain package-relative imports."""
        with open(single_file_path, encoding="utf-8") as f:
            content = f.read()
        # Check for "from .." patterns that would fail in single-file mode
        import re

        violations = re.findall(r"from \.\.\w", content)
        assert not violations, f"Residual relative imports found: {violations}"
