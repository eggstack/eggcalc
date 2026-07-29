# Installation

## Requirements

- Python 3.11 or higher
- pip

## Install from PyPI

```bash
pip install eggcalc
```

## Install from Source

```bash
git clone https://github.com/eggstack/eggcalc.git
cd eggcalc
pip install -e .
```

## Development Installation

For contributing or development:

```bash
git clone https://github.com/eggstack/eggcalc.git
cd eggcalc
pip install -e ".[dev]"
pre-commit install
```

## CLI Installation (Linux/macOS/Windows)

For portable CLI installation using the install script:

```bash
git clone https://github.com/eggstack/eggcalc.git
cd eggcalc
python install.py --install
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--install` | Install calc to PATH |
| `--update` | Update existing calc installation |
| `--uninstall` | Remove calc from PATH |
| `--path`, `-p` | Custom installation directory |
| `--no-path` | Don't modify PATH |

### Interactive Mode

Run `python install.py` without arguments for an interactive menu:

```bash
python install.py
# eggcalc Installer
# Status: Not installed
#
# 1. Install calc
# 2. Update calc
# 3. Uninstall calc
# 4. Exit
#
# Select an option [1-4]:
```

## Verify Installation

```bash
calc --version
# eggcalc 1.1.8

calc "one plus one"
# 2
```

## Shell Completions

### Bash

Add to `~/.bashrc`:

```bash
source /path/to/eggcalc/completions/calc.bash
```

### Zsh

Copy to your fpath:

```bash
cp completions/_calc ~/.zsh/completions/
```

Or add to `~/.zshrc`:

```bash
fpath=(/path/to/eggcalc/completions $fpath)
```

### Fish

Copy to Fish completions directory:

```bash
cp completions/calc.fish ~/.config/fish/completions/
```

## Man Page

Install the man page:

```bash
cp docs/eggcalc.1 /usr/local/share/man/man1/
man calc
```
