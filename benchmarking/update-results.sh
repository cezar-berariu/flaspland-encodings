#!/bin/bash
# update-results.sh [XLSX ...]
# Rebuilds the standing results database (analysis/results/results.duckdb, plus
# runs.csv, sources.csv, summary.json) from every analysis/<YYYYMMDD>/**/results-dist-*.xlsx,
# then refreshes analysis/include-graph.html. Any XLSX given must end up in the
# database with at least one instance, or the script fails.
# Run this after adding, moving or removing a results spreadsheet by hand;
# run-dist-collect.sh calls it automatically.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

expect=()
for f in "$@"; do expect+=(--expect "$f"); done

python3 "${SCRIPT_DIR}/analysis/results/build-results.py" "${expect[@]}"
python3 "${SCRIPT_DIR}/analysis/include-graph.py"
