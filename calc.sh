#!/bin/bash
#
# calc - Natural language calculator
#
# This script runs eggcalc from the command line.
# Usage: calc "five plus two"
#        calc "30m + 100ft"
#

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find Python
if command -v python3 &> /dev/null; then
    PYTHON="python3"
elif command -v python &> /dev/null; then
    PYTHON="python"
else
    echo "Error: Python not found" >&2
    exit 1
fi

# Run eggcalc
exec "$PYTHON" "$SCRIPT_DIR/eggcalc.py" "$@"
