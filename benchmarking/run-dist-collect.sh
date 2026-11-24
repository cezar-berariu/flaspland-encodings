#!/bin/bash
# run-dist-collect.sh <name>
# Collects the results of `run-dist-submit.sh <name>` into analysis/<YYYYMMDD>/
# and updates the results database (analysis/results/results.duckdb).
# Set RESULTS_DATE=YYYYMMDD to file the results under a different date (e.g. the submit date).
set -euo pipefail

# Fail if jobs are still running
if squeue -u "$USER" -h | grep -q .; then
    echo "Error: you still have jobs in the queue. Wait for them to finish."
    squeue -u "$USER"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${SCRIPT_DIR}/analysis/${RESULTS_DATE:-$(date +%Y%m%d)}"
OUT="${OUT_DIR}/results-dist-$1.xlsx"
if [[ -e "$OUT" ]]; then
    echo "Error: $OUT already exists. Move it away or set RESULTS_DATE." >&2
    exit 1
fi
mkdir -p "$OUT_DIR"

btool eval ./runscripts/runscript-$1-dist.xml | \
    btool conv -m all -o "$OUT"

echo "Results saved to ${OUT#"$SCRIPT_DIR"/}"

echo "Updating results database..."
if ! bash "${SCRIPT_DIR}/update-results.sh" "$OUT"; then
    echo "Error: the spreadsheet is saved, but the database update failed." >&2
    echo "Fix the problem above, then run: bash update-results.sh ${OUT#"$SCRIPT_DIR"/}" >&2
    exit 1
fi
