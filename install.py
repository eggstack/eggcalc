#!/usr/bin/env python3
"""
Install script for eggcalc.

Creates a single self-contained executable and adds it to the user's PATH.
Supports Linux, macOS, and Windows.
"""

import argparse
import os
import shutil
import stat
import subprocess
import sys


def get_install_path() -> str:
    """Get the appropriate installation path for the platform."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        return os.path.join(base, "Programs", "calc")
    else:
        return os.path.join(os.path.expanduser("~"), ".local", "bin")


def get_calc_path(install_dir: str) -> str:
    """Get the full path to the calc executable."""
    return os.path.join(install_dir, "calc")


def is_installed(install_dir: str) -> bool:
    """Check if calc is currently installed (via install script or pip)."""
    if os.path.exists(get_calc_path(install_dir)):
        return True
    return _is_pip_entry_point(_find_calc_on_path())


def build_single_file():
    """Build the single-file version of eggcalc."""
    build_script = os.path.join(os.path.dirname(__file__), "build_single.py")
    if os.path.exists(build_script):
        subprocess.run([sys.executable, build_script], check=True)
        return os.path.join(os.path.dirname(__file__), "eggcalc.py")
    else:
        print("Error: build_single.py not found")
        sys.exit(1)


def create_executable(source_path: str, install_dir: str) -> str:
    """Copy the single-file executable to install directory atomically."""
    os.makedirs(install_dir, exist_ok=True)
    dest_path = os.path.join(install_dir, "calc")

    with open(source_path, "r") as f:
        content = f.read()

    # Write to a temp file first, then rename atomically
    import tempfile
    fd, tmp_path = tempfile.mkstemp(dir=install_dir, prefix=".calc_tmp_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, dest_path)
    except BaseException:
        # Clean up temp file on any failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    os.chmod(dest_path, 0o755)

    return dest_path


_SHELL_UNSAFE_CHARS = set('"$`\\!')


def _validate_shell_path(path: str) -> None:
    """Raise ValueError if path contains characters unsafe for shell config interpolation."""
    bad = _SHELL_UNSAFE_CHARS & set(path)
    if bad:
        raise ValueError(
            f"Path contains shell-unsafe characters: {''.join(sorted(bad))!r}"
        )


def add_to_path(install_dir: str) -> bool:
    """Add install directory to PATH. Returns True if successful."""
    _validate_shell_path(install_dir)
    if sys.platform == "win32":
        current_path = os.environ.get("PATH", "")
        if install_dir not in current_path:
            print("To add to PATH on Windows, run:")
            print(f'  setx PATH "%PATH%;{install_dir}"')
            print("Or manually add this to your PATH:")
            print(f"  {install_dir}")
        return False
    else:
        shell_profile = os.path.expanduser("~/.bashrc")
        zshrc = os.path.expanduser("~/.zshrc")

        target_file = zshrc if os.path.exists(zshrc) else shell_profile

        if os.path.exists(target_file):
            with open(target_file, "r") as f:
                content = f.read()

            export_line = f'export PATH="{install_dir}:$PATH"'

            if export_line in content:
                print(f"{install_dir} is already in your PATH configuration.")
                return True

            with open(target_file, "a") as f:
                f.write(f"\n# Added by eggcalc install\n{export_line}\n")

            print(f"Added {install_dir} to PATH in {target_file}")
            return True
        else:
            print("No shell config found. Add this to your shell profile (~/.bashrc, ~/.zshrc, etc.):")
            print(f'  export PATH="{install_dir}:$PATH"')
            return False


def remove_from_path(install_dir: str) -> bool:
    """Remove install directory from PATH. Returns True if successful."""
    _validate_shell_path(install_dir)
    if sys.platform == "win32":
        print("To remove from PATH on Windows, manually remove the entry from your PATH.")
        return False

    shell_profile = os.path.expanduser("~/.bashrc")
    zshrc = os.path.expanduser("~/.zshrc")
    target_file = zshrc if os.path.exists(zshrc) else shell_profile

    if not os.path.exists(target_file):
        print("No shell config found.")
        return False

    with open(target_file, "r") as f:
        content = f.read()

    export_line = f'export PATH="{install_dir}:$PATH"'
    added_marker = "# Added by eggcalc install"
    removed_marker = "# Removed by eggcalc install"

    lines = content.split('\n')
    new_lines = []
    i = 0
    found_export = False

    while i < len(lines):
        line = lines[i]
        if export_line in line:
            # Found the export line - skip it and any following markers
            found_export = True
            i += 1
            # Skip the added/removed marker on next line if present
            if i < len(lines) and lines[i].strip() in (added_marker, removed_marker):
                i += 1
            continue
        # Handle markers that follow a removed export line
        if line.strip() in (added_marker, removed_marker):
            # Skip if we already found the export (this is its trailing marker)
            if found_export:
                i += 1
                continue
            # This is an orphaned marker without a preceding export
            # Skip it
            i += 1
            continue
        new_lines.append(line)
        i += 1

    # Clean up consecutive blank lines
    result_lines = []
    prev_empty = False
    for line in new_lines:
        if line.strip() == "":
            if not prev_empty:
                result_lines.append(line)
            prev_empty = True
        else:
            prev_empty = False
            result_lines.append(line)

    while result_lines and result_lines[-1].strip() == "":
        result_lines.pop()

    with open(target_file, "w") as f:
        f.write('\n'.join(result_lines))

    if found_export:
        print(f"Removed {install_dir} from PATH in {target_file}")
    else:
        print(f"{install_dir} was not in PATH (already removed).")
    return True


def install_calc(install_dir: str, no_path: bool = False) -> bool:
    """Install calc to the specified directory. Returns True if successful."""
    if is_installed(install_dir):
        print("calc is already installed.")
        print("Use --update to replace the existing installation.")
        return False

    print("Building single-file eggcalc...")
    single_file = build_single_file()

    calc_path = create_executable(single_file, install_dir)
    print(f"Installed calc to: {calc_path}")

    if no_path:
        print("calc is ready to use!")
        return True

    added = add_to_path(install_dir)

    if added:
        print("calc is ready to use!")
        new_path = f"{install_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        shell_bin = "zsh" if os.path.exists(os.path.expanduser("~/.zshrc")) else "bash"
        print(f"\nSpawning shell with calc available...")
        subprocess.run(
            [shell_bin, "-i"],
            env={**os.environ, "PATH": new_path}
        )

    return True


def _find_calc_on_path() -> str | None:
    """Return the full path of the first 'calc' on PATH, or None."""
    for dir_entry in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(dir_entry, "calc")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def _is_pip_entry_point(path: str) -> bool:
    """Return True if *path* is a pip-generated console_scripts entry point."""
    if not path:
        return False
    try:
        with open(path, "r") as f:
            head = f.read(512)
    except OSError:
        return False
    return "from eggcalc" in head or "import eggcalc" in head


def update_calc(install_dir: str) -> bool:
    """Update an existing calc installation. Returns True if successful."""
    calc_on_path = _find_calc_on_path()

    if _is_pip_entry_point(calc_on_path):
        print(f"Detected pip-installed calc at: {calc_on_path}")
        print("Updating via pip...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "eggcalc"],
        )
        if result.returncode == 0:
            print("Updated successfully via pip.")
            return True
        else:
            print("pip update failed. You can try manually:")
            print(f"  {sys.executable} -m pip install --upgrade eggcalc")
            return False

    if not is_installed(install_dir):
        print("calc is not installed.")
        print("Use --install to install it first.")
        return False

    print("Building new single-file eggcalc...")
    single_file = build_single_file()

    calc_path = get_calc_path(install_dir)

    with open(single_file, "r") as f:
        new_content = f.read()

    import tempfile
    fd, tmp_path = tempfile.mkstemp(dir=install_dir, prefix=".calc_tmp_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(new_content)
        os.replace(tmp_path, calc_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    os.chmod(calc_path, 0o755)

    print(f"Updated calc at: {calc_path}")
    return True


def uninstall_calc(install_dir: str, force: bool = False) -> bool:
    """Remove calc from the specified directory and PATH. Returns True if successful."""
    if not os.path.exists(install_dir):
        print(f"calc is not installed at {install_dir}")
        remove_from_path(install_dir)
        return True

    if not force:
        print(f"This will remove all files in: {install_dir}")
        confirm = input("Are you sure? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Uninstall cancelled.")
            return False

    # Only remove files we created (calc and .calc_tmp_*), not the whole directory
    calc_path = get_calc_path(install_dir)
    if os.path.exists(calc_path):
        os.remove(calc_path)
        print(f"Removed {calc_path}")
    # Clean up any leftover temp files
    import glob as _glob
    for tmp in _glob.glob(os.path.join(install_dir, ".calc_tmp_*")):
        try:
            os.remove(tmp)
        except OSError:
            pass
    # Remove directory if empty
    try:
        os.rmdir(install_dir)
        print(f"Removed empty directory {install_dir}")
    except OSError:
        print(f"Left non-empty directory {install_dir} (contains other files)")

    remove_from_path(install_dir)
    return True


def show_menu(install_dir: str):
    """Display interactive menu and handle user choice."""
    menu_lines = [
        "eggcalc Installer",
        f"Status: {'Installed' if is_installed(install_dir) else 'Not installed'}",
        "",
        "1. Install calc",
        "2. Update calc",
        "3. Uninstall calc",
        "4. Exit",
        "",
    ]

    for line in menu_lines:
        print(line)
    choice = input("Select an option [1-4]: ").strip()

    if len(choice) == 0:
        return
    if choice == "1":
        install_calc(install_dir)
    elif choice == "2":
        update_calc(install_dir)
    elif choice == "3":
        uninstall_calc(install_dir)
    elif choice == "4":
        return
    else:
        print("Invalid choice. Please enter 1-4.")


def main():
    parser = argparse.ArgumentParser(description="Install calc command-line tool")
    parser.add_argument("--install", action="store_true", help="Install calc to PATH")
    parser.add_argument("--update", action="store_true", help="Update existing calc installation")
    parser.add_argument("--uninstall", action="store_true", help="Remove calc from PATH")
    parser.add_argument("--path", "-p", help="Custom installation directory")
    parser.add_argument("--no-path", action="store_true", help="Don't modify PATH")
    args = parser.parse_args()

    install_dir = args.path or get_install_path()

    if args.install:
        install_calc(install_dir, args.no_path)
    elif args.update:
        update_calc(install_dir)
    elif args.uninstall:
        uninstall_calc(install_dir)
    else:
        show_menu(install_dir)


if __name__ == "__main__":
    main()
