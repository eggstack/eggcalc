"""
Entry point for running eggcalc as a module.

Usage:
    python -m eggcalc "five plus two"
    python -m eggcalc --help
"""

import sys

if __name__ == "__main__":
    # No sys.path manipulation: `python -m eggcalc` already has the
    # package importable in both source-tree and installed layouts.
    from eggcalc.cli import main

    sys.exit(main())
