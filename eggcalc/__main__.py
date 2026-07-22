"""
Entry point for running eggcalc as a module.

Usage:
    python -m eggcalc "five plus two"
    python -m eggcalc --help
"""

import os
import sys

if __name__ == "__main__":
    eggcalc_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if eggcalc_dir not in sys.path:
        sys.path.insert(0, eggcalc_dir)

    from eggcalc.cli import main

    sys.exit(main())
