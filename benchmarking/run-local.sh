#!/bin/bash

btool init

# bash ./build/build-runlim.sh
# bash ./build/build-clasp.sh

ln -s $(which clingo) programs/clingo-5.8.0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "${SCRIPT_DIR}"
ln -sf "${SCRIPT_DIR}/zesty/runlim" programs/runlim
ln -sf "${SCRIPT_DIR}/zesty/clasp" programs/clasp-3.4.0

cp "zesty/runscript-$1-local.xml" runscripts/
mkdir -p resultparsers
cp "zesty/clasp.py" resultparsers/

btool gen ./runscripts/runscript-$1-local.xml

python ./output-$1/clasp-seq/local/start.py
OUT_DIR="${SCRIPT_DIR}/analysis/${RESULTS_DATE:-$(date +%Y%m%d)}"
OUT="${OUT_DIR}/results-$1-local.xlsx"
if [[ -e "$OUT" ]]; then
    echo "Error: $OUT already exists. Move it away or set RESULTS_DATE." >&2
    exit 1
fi
mkdir -p "$OUT_DIR"
btool eval ./runscripts/runscript-$1-local.xml | btool conv -m all -o "$OUT"
echo "Complete. Results saved to ${OUT#"$SCRIPT_DIR"/}"
