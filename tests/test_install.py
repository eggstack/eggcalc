"""Tests for install.py — install, update, uninstall, and path helpers."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from install import (
    _find_calc_on_path,
    _is_pip_entry_point,
    _validate_shell_path,
    add_to_path,
    create_executable,
    get_calc_path,
    get_install_path,
    install_calc,
    is_installed,
    remove_from_path,
    uninstall_calc,
    update_calc,
)

# ---------------------------------------------------------------------------
# get_install_path / get_calc_path
# ---------------------------------------------------------------------------


class TestGetInstallPath:
    def test_non_windows_returns_home_local_bin(self):
        with patch.object(sys, "platform", "linux"):
            result = get_install_path()
        assert result == os.path.join(os.path.expanduser("~"), ".local", "bin")

    def test_windows_returns_localappdata(self):
        with patch.object(sys, "platform", "win32"):
            with patch.dict(os.environ, {"LOCALAPPDATA": "/tmp/test"}):
                result = get_install_path()
        assert result == os.path.join("/tmp/test", "Programs", "calc")

    def test_windows_fallback_when_no_env(self):
        with patch.object(sys, "platform", "win32"):
            with patch.dict(os.environ, {}, clear=True):
                result = get_install_path()
        assert "Programs" in result
        assert result.endswith("calc")


class TestGetCalcPath:
    def test_joins_dir_and_calc(self):
        assert get_calc_path("/foo/bar") == "/foo/bar/calc"

    def test_empty_dir(self):
        assert get_calc_path("") == "calc"


# ---------------------------------------------------------------------------
# _validate_shell_path
# ---------------------------------------------------------------------------


class TestValidateShellPath:
    def test_clean_path_passes(self):
        _validate_shell_path("/home/user/.local/bin")

    def test_rejects_double_quote(self):
        with pytest.raises(ValueError, match="shell-unsafe"):
            _validate_shell_path('/home/"user"/bin')

    def test_rejects_dollar(self):
        with pytest.raises(ValueError, match="shell-unsafe"):
            _validate_shell_path("/home/$USER/bin")

    def test_rejects_backtick(self):
        with pytest.raises(ValueError, match="shell-unsafe"):
            _validate_shell_path("/home/`cmd`/bin")

    def test_rejects_backslash(self):
        with pytest.raises(ValueError, match="shell-unsafe"):
            _validate_shell_path("/home/user\\bin")

    def test_rejects_bang(self):
        with pytest.raises(ValueError, match="shell-unsafe"):
            _validate_shell_path("/home/user!/bin")


# ---------------------------------------------------------------------------
# _find_calc_on_path
# ---------------------------------------------------------------------------


class TestFindCalcOnPath:
    def test_returns_none_when_no_calc(self, tmp_path):
        with patch.dict(os.environ, {"PATH": str(tmp_path)}):
            assert _find_calc_on_path() is None

    def test_finds_executable_calc(self, tmp_path):
        calc = tmp_path / "calc"
        calc.write_text("#!/bin/sh\necho hi\n")
        calc.chmod(0o755)
        with patch.dict(os.environ, {"PATH": str(tmp_path)}):
            assert _find_calc_on_path() == str(calc)

    def test_ignores_non_executable(self, tmp_path):
        calc = tmp_path / "calc"
        calc.write_text("not executable")
        calc.chmod(0o644)
        with patch.dict(os.environ, {"PATH": str(tmp_path)}):
            assert _find_calc_on_path() is None

    def test_returns_first_match(self, tmp_path):
        dir1 = tmp_path / "a"
        dir2 = tmp_path / "b"
        dir1.mkdir()
        dir2.mkdir()
        (dir1 / "calc").write_text("#!/bin/sh\necho a\n")
        (dir1 / "calc").chmod(0o755)
        (dir2 / "calc").write_text("#!/bin/sh\necho b\n")
        (dir2 / "calc").chmod(0o755)
        with patch.dict(os.environ, {"PATH": f"{dir1}{os.pathsep}{dir2}"}):
            result = _find_calc_on_path()
        assert result == str(dir1 / "calc")

    def test_empty_path_returns_none(self):
        with patch.dict(os.environ, {"PATH": ""}):
            assert _find_calc_on_path() is None

    def test_skips_nonexistent_dirs(self):
        with patch.dict(os.environ, {"PATH": "/nonexistent/dir"}):
            assert _find_calc_on_path() is None


# ---------------------------------------------------------------------------
# _is_pip_entry_point
# ---------------------------------------------------------------------------


class TestIsPipEntryPoint:
    def test_none_returns_false(self):
        assert _is_pip_entry_point(None) is False

    def test_empty_string_returns_false(self):
        assert _is_pip_entry_point("") is False

    def test_nonexistent_file_returns_false(self):
        assert _is_pip_entry_point("/nonexistent/path") is False

    def test_pip_entry_point_with_from_import(self, tmp_path):
        f = tmp_path / "calc"
        f.write_text("#!/usr/bin/python\nfrom eggcalc.normalize import main\nmain()\n")
        assert _is_pip_entry_point(str(f)) is True

    def test_pip_entry_point_with_import(self, tmp_path):
        f = tmp_path / "calc"
        f.write_text("#!/usr/bin/python\nimport eggcalc\neggcalc.main()\n")
        assert _is_pip_entry_point(str(f)) is True

    def test_single_file_not_pip(self, tmp_path):
        f = tmp_path / "calc"
        f.write_text("#!/usr/bin/python\n# standalone eggcalc\nprint('hello')\n")
        assert _is_pip_entry_point(str(f)) is False

    def test_reads_only_first_512_bytes(self, tmp_path):
        f = tmp_path / "calc"
        # Write 600 bytes of junk, then "from eggcalc" after byte 512
        f.write_text("x" * 600 + "from eggcalc import main\n")
        assert _is_pip_entry_point(str(f)) is False

    def test_permission_error_returns_false(self, tmp_path):
        f = tmp_path / "calc"
        f.write_text("from eggcalc import main\n")
        f.chmod(0o000)
        try:
            assert _is_pip_entry_point(str(f)) is False
        finally:
            f.chmod(0o644)


# ---------------------------------------------------------------------------
# is_installed
# ---------------------------------------------------------------------------


class TestIsInstalled:
    def test_true_when_calc_exists_in_dir(self, tmp_path):
        calc = tmp_path / "calc"
        calc.write_text("content")
        assert is_installed(str(tmp_path)) is True

    def test_false_when_no_calc_and_no_pip(self, tmp_path):
        with patch("install._find_calc_on_path", return_value=None):
            assert is_installed(str(tmp_path)) is False

    def test_true_when_pip_installed(self, tmp_path):
        fake_calc = tmp_path / "fake_calc"
        fake_calc.write_text("from eggcalc import main\n")
        with patch("install._find_calc_on_path", return_value=str(fake_calc)):
            assert is_installed(str(tmp_path)) is True

    def test_false_when_pip_calc_not_entry_point(self, tmp_path):
        fake_calc = tmp_path / "fake_calc"
        fake_calc.write_text("standalone script\n")
        with patch("install._find_calc_on_path", return_value=str(fake_calc)):
            assert is_installed(str(tmp_path)) is False


# ---------------------------------------------------------------------------
# create_executable
# ---------------------------------------------------------------------------


class TestCreateExecutable:
    def test_creates_executable(self, tmp_path):
        src = tmp_path / "source.py"
        src.write_text("#!/usr/bin/python\nprint('hello')\n")
        install_dir = tmp_path / "install"
        install_dir.mkdir()
        result = create_executable(str(src), str(install_dir))
        assert os.path.exists(result)
        assert result == str(install_dir / "calc")
        with open(result) as f:
            assert f.read() == "#!/usr/bin/python\nprint('hello')\n"
        assert os.stat(result).st_mode & 0o755

    def test_creates_install_dir_if_missing(self, tmp_path):
        src = tmp_path / "source.py"
        src.write_text("content")
        install_dir = tmp_path / "new_dir" / "nested"
        result = create_executable(str(src), str(install_dir))
        assert os.path.exists(result)

    def test_atomic_write_cleanup_on_failure(self, tmp_path):
        src = tmp_path / "source.py"
        src.write_text("content")
        install_dir = tmp_path / "install"
        install_dir.mkdir()
        with patch("install.os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                create_executable(str(src), str(install_dir))
        # No leftover temp files
        tmp_files = list(install_dir.glob(".calc_tmp_*"))
        assert tmp_files == []


# ---------------------------------------------------------------------------
# add_to_path / remove_from_path
# ---------------------------------------------------------------------------


class TestAddToPath:
    def test_adds_to_zshrc(self, tmp_path):
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text("old content\n")

        def fake_expanduser(p):
            if "zshrc" in p:
                return str(zshrc)
            return str(tmp_path / ".bashrc")

        with patch("os.path.expanduser", side_effect=fake_expanduser):
            result = add_to_path("/custom/bin")
        assert result is True
        content = zshrc.read_text()
        assert 'export PATH="/custom/bin:$PATH"' in content
        assert "# Added by eggcalc install" in content

    def test_adds_to_bashrc_when_no_zshrc(self, tmp_path):
        bashrc = tmp_path / ".bashrc"
        bashrc.write_text("old content\n")

        def fake_expanduser(p):
            return str(bashrc)

        with patch("os.path.expanduser", side_effect=fake_expanduser):
            result = add_to_path("/custom/bin")
        assert result is True
        assert 'export PATH="/custom/bin:$PATH"' in bashrc.read_text()

    def test_idempotent_when_already_added(self, tmp_path):
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text('export PATH="/custom/bin:$PATH"\n')

        def fake_expanduser(p):
            return str(zshrc)

        with patch("os.path.expanduser", side_effect=fake_expanduser):
            result = add_to_path("/custom/bin")
        assert result is True
        assert zshrc.read_text().count("/custom/bin") == 1

    def test_returns_false_when_no_shell_config(self, tmp_path):
        def fake_expanduser(p):
            return str(tmp_path / "nonexistent")

        with patch("os.path.expanduser", side_effect=fake_expanduser):
            result = add_to_path("/custom/bin")
        assert result is False

    def test_returns_false_on_windows(self):
        with patch.object(sys, "platform", "win32"):
            with patch.dict(os.environ, {"PATH": ""}):
                result = add_to_path("/custom/bin")
        assert result is False

    def test_rejects_unsafe_path(self):
        with pytest.raises(ValueError, match="shell-unsafe"):
            add_to_path('/home/"user"/bin')


class TestRemoveFromPath:
    def test_removes_from_zshrc(self, tmp_path):
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text("old\nexport PATH=\"/custom/bin:$PATH\"\nmore\n")

        def fake_expanduser(p):
            return str(zshrc)

        with patch("os.path.expanduser", side_effect=fake_expanduser):
            result = remove_from_path("/custom/bin")
        assert result is True
        content = zshrc.read_text()
        assert "/custom/bin" not in content
        assert "old" in content
        assert "more" in content

    def test_removes_marker_comment(self, tmp_path):
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text(
            "old\n# Added by eggcalc install\nexport PATH=\"/custom/bin:$PATH\"\nmore\n"
        )

        def fake_expanduser(p):
            return str(zshrc)

        with patch("os.path.expanduser", side_effect=fake_expanduser):
            result = remove_from_path("/custom/bin")
        assert result is True
        content = zshrc.read_text()
        assert "# Added by eggcalc install" not in content

    def test_noop_when_not_in_path(self, tmp_path):
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text("old content\n")

        def fake_expanduser(p):
            return str(zshrc)

        with patch("os.path.expanduser", side_effect=fake_expanduser):
            result = remove_from_path("/custom/bin")
        assert result is True
        assert zshrc.read_text() == "old content"

    def test_returns_false_when_no_shell_config(self, tmp_path):
        def fake_expanduser(p):
            return str(tmp_path / "nonexistent")

        with patch("os.path.expanduser", side_effect=fake_expanduser):
            result = remove_from_path("/custom/bin")
        assert result is False

    def test_returns_false_on_windows(self):
        with patch.object(sys, "platform", "win32"):
            result = remove_from_path("/custom/bin")
        assert result is False

    def test_cleans_consecutive_blank_lines(self, tmp_path):
        zshrc = tmp_path / ".zshrc"
        zshrc.write_text("a\n\n\nexport PATH=\"/custom/bin:$PATH\"\n\n\nb\n")

        def fake_expanduser(p):
            return str(zshrc)

        with patch("os.path.expanduser", side_effect=fake_expanduser):
            remove_from_path("/custom/bin")
        content = zshrc.read_text()
        assert "\n\n\n" not in content

    def test_rejects_unsafe_path(self):
        with pytest.raises(ValueError, match="shell-unsafe"):
            remove_from_path('/home/"user"/bin')


# ---------------------------------------------------------------------------
# update_calc
# ---------------------------------------------------------------------------


class TestUpdateCalc:
    def test_pip_path_when_pip_detected(self, tmp_path):
        fake_calc = tmp_path / "calc"
        fake_calc.write_text("from eggcalc import main\n")
        with patch("install._find_calc_on_path", return_value=str(fake_calc)):
            with patch("install.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = update_calc(str(tmp_path))
        assert result is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "pip" in cmd
        assert "--upgrade" in cmd
        assert "eggcalc" in cmd

    def test_pip_path_failure(self, tmp_path):
        fake_calc = tmp_path / "calc"
        fake_calc.write_text("from eggcalc import main\n")
        with patch("install._find_calc_on_path", return_value=str(fake_calc)):
            with patch("install.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1)
                result = update_calc(str(tmp_path))
        assert result is False

    def test_install_script_path_when_not_pip(self, tmp_path):
        calc = tmp_path / "calc"
        calc.write_text("old content")
        # Make it not look like a pip entry point
        with patch("install._find_calc_on_path", return_value=None):
            with patch("install.build_single_file") as mock_build:
                new_file = tmp_path / "new.py"
                new_file.write_text("new content")
                mock_build.return_value = str(new_file)
                result = update_calc(str(tmp_path))
        assert result is True
        assert calc.read_text() == "new content"

    def test_not_installed_returns_false(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with patch("install._find_calc_on_path", return_value=None):
            with patch("install.is_installed", return_value=False):
                result = update_calc(str(empty_dir))
        assert result is False

    def test_atomic_update_replaces_correctly(self, tmp_path):
        calc = tmp_path / "calc"
        calc.write_text("version1")
        with patch("install._find_calc_on_path", return_value=None):
            with patch("install.build_single_file") as mock_build:
                new_file = tmp_path / "new.py"
                new_file.write_text("version2")
                mock_build.return_value = str(new_file)
                update_calc(str(tmp_path))
        assert calc.read_text() == "version2"
        # No temp files left behind
        tmp_files = list(tmp_path.glob(".calc_tmp_*"))
        assert tmp_files == []


# ---------------------------------------------------------------------------
# uninstall_calc
# ---------------------------------------------------------------------------


class TestUninstallCalc:
    def test_removes_calc_file(self, tmp_path):
        calc = tmp_path / "calc"
        calc.write_text("content")
        with patch("install.remove_from_path"):
            result = uninstall_calc(str(tmp_path), force=True)
        assert result is True
        assert not calc.exists()

    def test_removes_empty_directory(self, tmp_path):
        calc = tmp_path / "calc"
        calc.write_text("content")
        with patch("install.remove_from_path"):
            result = uninstall_calc(str(tmp_path), force=True)
        assert result is True
        assert not tmp_path.exists()

    def test_leaves_nonempty_directory(self, tmp_path):
        calc = tmp_path / "calc"
        calc.write_text("content")
        other = tmp_path / "other.txt"
        other.write_text("keep me")
        with patch("install.remove_from_path"):
            result = uninstall_calc(str(tmp_path), force=True)
        assert result is True
        assert tmp_path.exists()
        assert other.exists()

    def test_cleans_temp_files(self, tmp_path):
        calc = tmp_path / "calc"
        calc.write_text("content")
        tmp1 = tmp_path / ".calc_tmp_abc"
        tmp1.write_text("temp")
        tmp2 = tmp_path / ".calc_tmp_def"
        tmp2.write_text("temp")
        with patch("install.remove_from_path"):
            uninstall_calc(str(tmp_path), force=True)
        assert not tmp1.exists()
        assert not tmp2.exists()

    def test_nonexistent_dir_returns_true(self, tmp_path):
        nonexistent = tmp_path / "nope"
        with patch("install.remove_from_path"):
            result = uninstall_calc(str(nonexistent), force=True)
        assert result is True

    def test_user_cancellation(self, tmp_path):
        calc = tmp_path / "calc"
        calc.write_text("content")
        with patch("builtins.input", return_value="n"):
            result = uninstall_calc(str(tmp_path), force=False)
        assert result is False
        assert calc.exists()

    def test_user_confirmation(self, tmp_path):
        calc = tmp_path / "calc"
        calc.write_text("content")
        with patch("builtins.input", return_value="y"):
            with patch("install.remove_from_path"):
                result = uninstall_calc(str(tmp_path), force=False)
        assert result is True
        assert not calc.exists()


# ---------------------------------------------------------------------------
# install_calc
# ---------------------------------------------------------------------------


class TestInstallCalc:
    def test_already_installed_returns_false(self, tmp_path):
        calc = tmp_path / "calc"
        calc.write_text("existing")
        with patch("install.is_installed", return_value=True):
            result = install_calc(str(tmp_path), no_path=True)
        assert result is False

    def test_installs_with_no_path(self, tmp_path):
        with patch("install.is_installed", return_value=False):
            with patch("install.build_single_file") as mock_build:
                src = tmp_path / "source.py"
                src.write_text("#!/usr/bin/python\nprint('hi')\n")
                mock_build.return_value = str(src)
                result = install_calc(str(tmp_path), no_path=True)
        assert result is True
        calc = tmp_path / "calc"
        assert calc.exists()
        assert calc.read_text() == "#!/usr/bin/python\nprint('hi')\n"

    def test_installs_and_adds_to_path(self, tmp_path):
        with patch("install.is_installed", return_value=False):
            with patch("install.build_single_file") as mock_build:
                src = tmp_path / "source.py"
                src.write_text("content")
                mock_build.return_value = str(src)
                with patch("install.add_to_path", return_value=True):
                    with patch("install.subprocess.run"):
                        result = install_calc(str(tmp_path), no_path=False)
        assert result is True
        assert (tmp_path / "calc").exists()


# ---------------------------------------------------------------------------
# main (CLI argument parsing)
# ---------------------------------------------------------------------------


class TestMain:
    def test_install_flag(self, tmp_path):
        with patch("sys.argv", ["install.py", "--install", "--path", str(tmp_path), "--no-path"]):
            with patch("install.install_calc") as mock_install:
                from install import main

                main()
        mock_install.assert_called_once_with(str(tmp_path), True, False)

    def test_install_flag_with_spawn_shell(self, tmp_path):
        with patch("sys.argv", ["install.py", "--install", "--path", str(tmp_path), "--no-path", "--spawn-shell"]):
            with patch("install.install_calc") as mock_install:
                from install import main

                main()
        mock_install.assert_called_once_with(str(tmp_path), True, True)

    def test_update_flag(self, tmp_path):
        with patch("sys.argv", ["install.py", "--update", "--path", str(tmp_path)]):
            with patch("install.update_calc") as mock_update:
                from install import main

                main()
        mock_update.assert_called_once_with(str(tmp_path))

    def test_uninstall_flag(self, tmp_path):
        with patch("sys.argv", ["install.py", "--uninstall", "--path", str(tmp_path)]):
            with patch("install.uninstall_calc") as mock_uninstall:
                from install import main

                main()
        mock_uninstall.assert_called_once_with(str(tmp_path))

    def test_no_flag_shows_menu(self):
        with patch("sys.argv", ["install.py"]):
            with patch("install.show_menu") as mock_menu:
                from install import main

                main()
        mock_menu.assert_called_once()
