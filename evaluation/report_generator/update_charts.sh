#!/usr/bin/env bash
# update_charts.sh — Copy eval chart PNGs into report_generator/
#
# Usage:
#   ./update_charts.sh                          # copies from ../test_2000/output/charts/
#   ./update_charts.sh /path/to/eval/output     # copies from custom path
#
# This copies all 16 charts from the eval run into this directory with a
# "chart_" prefix, so the PDF generator (tachiwin_report.py) picks them up.

set -euo pipefail

SRC="${1:-$(dirname "$0")/../test_2000/output/charts}"
SRC="$(cd "$SRC" 2>/dev/null && pwd)" || {
    echo "Error: cannot find source directory '$SRC'"
    echo "Usage: $0 [path/to/eval/output/charts]"
    exit 1
}

DEST="$(cd "$(dirname "$0")" && pwd)"

echo "Copying charts from: $SRC"
echo "             to:     $DEST"

count=0
for f in "$SRC"/*.png; do
    base="$(basename "$f")"
    cp "$f" "$DEST/chart_$base"
    echo "  chart_$base"
    count=$((count + 1))
done

echo "Done. $count charts copied."
