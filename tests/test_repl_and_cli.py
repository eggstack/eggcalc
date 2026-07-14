"""Tests for REPL mode and CLI flags."""

import json
import subprocess
import sys
from unittest.mock import patch

from eggcalc.normalize import _run_repl, run

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_cli(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    """Run eggcalc as a subprocess and return the result."""
    cmd = [sys.executable, "-m", "eggcalc", *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=stdin,
        timeout=10,
    )


def _get_value(result):
    """Extract numeric value from result, handling UnitValue."""
    from eggcalc import UnitValue

    if isinstance(result, UnitValue):
        return result.value
    return result


# ---------------------------------------------------------------------------
# REPL Tests
# ---------------------------------------------------------------------------


class TestReplBasicEvaluation:
    """Test basic expression evaluation in REPL mode."""

    def test_repl_basic_evaluation(self, capsys):
        """REPL evaluates '5 + 3' and prints 8."""
        with patch("builtins.input", side_effect=["5 + 3", EOFError]):
            exit_code = _run_repl()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "8" in captured.out

    def test_repl_multiple_expressions(self, capsys):
        """REPL evaluates multiple expressions in sequence."""
        with patch("builtins.input", side_effect=["10 * 2", "20 - 4", EOFError]):
            exit_code = _run_repl()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "20" in captured.out
        assert "16" in captured.out


class TestReplCommands:
    """Test REPL built-in commands."""

    def test_repl_help_command(self, capsys):
        """REPL 'help' command prints help text."""
        with patch("builtins.input", side_effect=["help", EOFError]):
            exit_code = _run_repl()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Usage:" in captured.out
        assert "Operators:" in captured.out

    def test_repl_history_command(self, capsys):
        """REPL 'history' command shows evaluated expressions."""
        with patch("builtins.input", side_effect=["5 + 3", "10 * 2", "history", EOFError]):
            exit_code = _run_repl()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "5 + 3 = 8" in captured.out
        assert "10 * 2 = 20" in captured.out

    def test_repl_clear_command(self, capsys):
        """REPL 'clear' command empties history."""
        with patch("builtins.input", side_effect=["5 + 3", "clear", "history", EOFError]):
            exit_code = _run_repl()
        assert exit_code == 0
        captured = capsys.readouterr()
        # After clear, history should show nothing (no " = " lines)
        assert "= 8" not in captured.out

    def test_repl_quit_command(self, capsys):
        """REPL 'quit' exits cleanly."""
        with patch("builtins.input", side_effect=["quit"]):
            exit_code = _run_repl()
        assert exit_code == 0

    def test_repl_exit_command(self, capsys):
        """REPL 'exit' exits cleanly."""
        with patch("builtins.input", side_effect=["exit"]):
            exit_code = _run_repl()
        assert exit_code == 0

    def test_repl_quit_parens(self, capsys):
        """REPL 'quit()' exits cleanly."""
        with patch("builtins.input", side_effect=["quit()"]):
            exit_code = _run_repl()
        assert exit_code == 0

    def test_repl_exit_parens(self, capsys):
        """REPL 'exit()' exits cleanly."""
        with patch("builtins.input", side_effect=["exit()"]):
            exit_code = _run_repl()
        assert exit_code == 0


class TestReplEdgeCases:
    """Test REPL edge cases and error handling."""

    def test_repl_keyboard_interrupt_during_eval(self, capsys):
        """REPL continues after KeyboardInterrupt during expression evaluation."""
        call_count = 0

        def mock_input(prompt=""):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "5 + 3"
            if call_count == 2:
                return "10 + 2"
            raise EOFError()

        original_run = run

        def mock_run(expression, operators, patterns, output_format="plain", show_expression=True):
            if expression == "10 + 2":
                raise KeyboardInterrupt()
            return original_run(expression, operators, patterns, output_format, show_expression)

        with (
            patch("builtins.input", side_effect=mock_input),
            patch("eggcalc.normalize.run", side_effect=mock_run),
        ):
            exit_code = _run_repl()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "8" in captured.out
        assert "12" not in captured.out  # interrupted before result printed

    def test_repl_eoferror_exits_cleanly(self, capsys):
        """REPL exits cleanly on immediate EOFError."""
        with patch("builtins.input", side_effect=EOFError):
            exit_code = _run_repl()
        assert exit_code == 0

    def test_repl_empty_input_ignored(self, capsys):
        """REPL ignores empty input lines."""
        with patch("builtins.input", side_effect=["", "  ", "5 + 3", EOFError]):
            exit_code = _run_repl()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "8" in captured.out

    def test_repl_invalid_expression(self, capsys):
        """REPL handles invalid expressions without crashing."""
        with patch("builtins.input", side_effect=["xyz", "5 + 3", EOFError]):
            exit_code = _run_repl()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "8" in captured.out

    def test_repl_history_not_populated_on_error(self, capsys):
        """REPL does not add failed expressions to history."""
        with patch("builtins.input", side_effect=["xyz", "history", EOFError]):
            exit_code = _run_repl()
        assert exit_code == 0
        captured = capsys.readouterr()
        # "xyz" should not appear in history output
        assert "xyz" not in captured.out

    def test_repl_case_insensitive_quit(self, capsys):
        """REPL accepts 'Quit' and 'EXIT' as quit commands."""
        with patch("builtins.input", side_effect=["Quit"]):
            exit_code = _run_repl()
        assert exit_code == 0

        with patch("builtins.input", side_effect=["EXIT"]):
            exit_code = _run_repl()
        assert exit_code == 0

    def test_repl_show_expression_true(self, capsys):
        """REPL passes show_expression=True to run()."""
        with (
            patch("builtins.input", side_effect=["5 + 3", EOFError]),
            patch("eggcalc.normalize.run", wraps=run) as mock_run,
        ):
            exit_code = _run_repl(show_expression=True)
        assert exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][4] is True  # show_expression positional arg

    def test_repl_show_expression_false(self, capsys):
        """REPL passes show_expression=False to run()."""
        with (
            patch("builtins.input", side_effect=["5 + 3", EOFError]),
            patch("eggcalc.normalize.run", wraps=run) as mock_run,
        ):
            exit_code = _run_repl(show_expression=False)
        assert exit_code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][4] is False  # show_expression positional arg


# ---------------------------------------------------------------------------
# CLI Flag Tests
# ---------------------------------------------------------------------------


class TestCliVersionFlag:
    """Test --version flag."""

    def test_cli_version_flag(self):
        """--version prints version string."""
        result = _run_cli("--version")
        assert result.returncode == 0
        assert "eggcalc" in result.stdout
        assert "1.1.6" in result.stdout

    def test_cli_version_short_flag(self):
        """-v prints version string."""
        result = _run_cli("-v")
        assert result.returncode == 0
        assert "eggcalc" in result.stdout


class TestCliHelpFlag:
    """Test --help and --usage flags."""

    def test_cli_help_flag(self):
        """--help prints help text."""
        result = _run_cli("--help")
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "calc" in result.stdout.lower()

    def test_cli_usage_flag(self):
        """--usage prints full help with examples."""
        result = _run_cli("--usage")
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "Operators:" in result.stdout

    def test_cli_no_args_shows_help(self):
        """No arguments shows help text."""
        result = _run_cli()
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "calc" in result.stdout.lower()


class TestCliExpressionFlag:
    """Test -e / --expression flag."""

    def test_cli_expression_flag_basic(self):
        """-e evaluates expression and prints result."""
        result = _run_cli("-e", "5+3")
        assert result.returncode == 0
        assert result.stdout.strip() == "8"

    def test_cli_expression_flag_nl(self):
        """-e evaluates natural language expression."""
        result = _run_cli("-e", "five plus three")
        assert result.returncode == 0
        assert result.stdout.strip() == "8"

    def test_cli_expression_flag_complex(self):
        """-e evaluates complex expression."""
        result = _run_cli("-e", "2**10")
        assert result.returncode == 0
        assert result.stdout.strip() == "1024"


class TestCliQuietFlag:
    """Test -q / --quiet flag."""

    def test_cli_quiet_flag(self):
        """-q suppresses expression echo in output."""
        result = _run_cli("-q", "-e", "5+3")
        assert result.returncode == 0
        output = result.stdout.strip()
        assert output == "8"
        assert "5+3" not in output


class TestCliVerboseFlag:
    """Test --verbose flag."""

    def test_cli_verbose_flag(self):
        """--verbose is accepted but plain output remains result-only."""
        result = _run_cli("--verbose", "-e", "5+3")
        assert result.returncode == 0
        assert result.stdout == "8\n"


class TestCliJsonFlag:
    """Test --json flag."""

    def test_cli_json_flag(self):
        """--json outputs valid JSON with expression and result."""
        result = _run_cli("--json", "-e", "5+3")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "result" in data
        assert data["result"] == "8"
        assert "expression" in data

    def test_cli_json_flag_nl(self):
        """--json outputs valid JSON for natural language."""
        result = _run_cli("--json", "-e", "five plus three")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["result"] == "8"
        assert data["expression"] == "5+3"


class TestCliInteractiveFlag:
    """Test -i / --interactive flag."""

    def test_cli_interactive_flag(self):
        """-i starts REPL mode that evaluates expressions."""
        result = _run_cli("-i", stdin="5 + 3\nquit\n")
        assert result.returncode == 0
        assert "8" in result.stdout

    def test_cli_interactive_multiple(self):
        """-i handles multiple expressions."""
        result = _run_cli("-i", stdin="10 * 2\n20 - 4\nquit\n")
        assert result.returncode == 0
        assert "20" in result.stdout
        assert "16" in result.stdout


class TestCliUnknownFlag:
    """Test unknown flag handling."""

    def test_cli_unknown_flag_rejected(self):
        """Unknown flags produce an error."""
        result = _run_cli("--bogus")
        assert result.returncode != 0
        assert "error" in result.stderr.lower() or "unrecognized" in result.stderr.lower()


class TestCliExpressionArg:
    """Test positional expression arguments."""

    def test_cli_positional_expression(self):
        """Positional arguments are joined and evaluated."""
        result = _run_cli("5+3")
        assert result.returncode == 0
        assert "8" in result.stdout

    def test_cli_positional_nl_expression(self):
        """Positional natural language is evaluated."""
        result = _run_cli("five plus three")
        assert result.returncode == 0
        assert "8" in result.stdout


class TestCliStdinExpression:
    """Test reading expression from stdin pipe."""

    def test_cli_stdin_expression_with_e_flag(self):
        """Expression via -e works with piped stdin ignored."""
        result = _run_cli("-e", "5 + 3", stdin="ignored input\n")
        assert result.returncode == 0
        assert "8" in result.stdout

    def test_cli_stdin_interactive_mode(self):
        """Stdin is consumed by interactive mode."""
        result = _run_cli("-i", stdin="5 + 3\nquit\n")
        assert result.returncode == 0
        assert "8" in result.stdout


# ---------------------------------------------------------------------------
# Output Format Tests
# ---------------------------------------------------------------------------


class TestOutputFormat:
    """Test output formatting details."""

    def test_output_no_echo_of_input(self):
        """Single expression mode (-e) does not echo the expression."""
        result = _run_cli("-e", "5+3")
        assert result.returncode == 0
        output = result.stdout.strip()
        # Should be just the number, no echo of "5+3"
        assert output == "8"

    def test_output_no_extra_whitespace(self):
        """Output has no trailing whitespace beyond the single newline."""
        result = _run_cli("-e", "5+3")
        assert result.returncode == 0
        output = result.stdout
        assert output.endswith("8\n")
        assert not output.endswith("8\n\n")
        assert " 8 " not in output
        assert output == output.strip() + "\n"

    def test_json_output_structure(self):
        """--json produces valid JSON with expected fields."""
        result = _run_cli("--json", "-e", "5+3")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        assert "result" in data
        assert "expression" in data
        assert data["result"] == "8"
        assert data["expression"] == "5+3"

    def test_output_integer_result_no_decimal(self):
        """Integer results display without decimal point."""
        result = _run_cli("-e", "5+3")
        assert result.returncode == 0
        output = result.stdout.strip()
        assert "." not in output

    def test_output_float_result_has_decimal(self):
        """Float results display with decimal point."""
        result = _run_cli("-e", "5/2")
        assert result.returncode == 0
        output = result.stdout.strip()
        assert "." in output
