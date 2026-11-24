#!/usr/bin/env python3
"""Collect btool result spreadsheets into one queryable results database.

Scans benchmarking/analysis/<YYYYMMDD>/**/results-dist-*.xlsx, reads the raw
per-instance block of the "Instances" sheet, and writes:

    results/runs.csv        one row per (source spreadsheet, instance)
    results/sources.csv     one row per source spreadsheet
    results/results.duckdb  tables `runs`, `sources`, plus views (see schema.sql)
    results/summary.json    per-source x trains aggregates for include-graph.html

Always rebuilds everything from the spreadsheets, so re-running is safe. The new
database is built next to the old one and only swapped in when the build succeeds.

Usage:  python3 benchmarking/analysis/results/build-results.py [--expect XLSX ...]
        --expect  fail unless XLSX was loaded with at least one instance row
                  (used by run-dist-collect.sh to check a freshly collected file)
Needs:  openpyxl (python), duckdb CLI on PATH.
"""

import argparse
import csv
import re
import shutil
import subprocess
import sys
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent  # benchmarking/analysis/results
ANALYSIS = HERE.parent
BENCH = ANALYSIS.parent
EXPS = BENCH / "experiments"

MEASURES = ["choices", "conflicts", "constraints", "error", "mem", "memout", "models",
            "overall-time", "par2", "restarts", "rstatus", "rules", "solving-time",
            "status", "time", "timeout", "variables"]
COLS = ["source", "experiment", "variant", "date", "system", "instance", "level", "trains"] + \
       [m.replace("-", "_") for m in MEASURES]


def experiment_codes():
    return sorted((p.stem[len("exp-"):] for p in EXPS.glob("exp-*.lp")), key=len, reverse=True)


def split_code(name, codes):
    """'dc-l3' -> ('dc', 'l3'); 'dc-ef' -> ('dc-ef', ''); unknown -> (name, '')."""
    for c in codes:  # longest first
        if name == c:
            return c, ""
        if name.startswith(c + "-"):
            return c, name[len(c) + 1:]
    return name, ""


def parse_instance(name):
    level = trains = None
    m = re.search(r"Level_(\d+)", name)
    if m:
        level = int(m.group(1))
    m = re.match(r"(\d+)-", name.rsplit("/", 1)[-1])
    if m:
        trains = int(m.group(1))
    return level, trains


def read_sheet(path):
    ws = openpyxl.load_workbook(path, read_only=True, data_only=False)["Instances"]
    rows = ws.iter_rows(values_only=True)
    r1, r2 = next(rows), next(rows)
    # First block = raw values for the (single) system/setting.
    starts = [i for i, c in enumerate(r1) if c and i > 0]
    end = starts[1] if len(starts) > 1 else len(r2)
    system = r1[starts[0]]
    idx = {r2[i]: i for i in range(starts[0], end) if r2[i]}
    missing = [m for m in MEASURES if m not in idx]
    if missing:
        print(f"  ! {path.name}: missing columns {missing}", file=sys.stderr)
    out = []
    for r in rows:
        name = r[0]
        if not isinstance(name, str) or "/" not in name:  # skips SUM/AVG/... footer rows
            continue
        vals = []
        for m in MEASURES:
            v = r[idx[m]] if m in idx else None
            if isinstance(v, str) and v.startswith("="):
                v = None
            vals.append(v)
        out.append((name, vals))
    return system, out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--expect", action="append", default=[], metavar="XLSX",
                    help="fail unless this spreadsheet was loaded with >= 1 instance row")
    args = ap.parse_args()
    duck = shutil.which("duckdb")
    if not duck:
        sys.exit("error: duckdb CLI not found on PATH; results.duckdb was NOT updated")

    codes = experiment_codes()
    runs, sources = [], []
    for path in sorted(ANALYSIS.glob("*/**/results-dist-*.xlsx")):
        relp = path.relative_to(ANALYSIS)
        if not re.fullmatch(r"\d{8}", relp.parts[0]):  # only YYYYMMDD date folders
            continue
        date = relp.parts[0]
        sub = list(relp.parts[1:-1])  # e.g. ['prelim']
        exp, variant = split_code(path.stem[len("results-dist-"):], codes)
        variant = "-".join([*sub, variant] if variant else sub)
        source = "/".join([date, *sub, path.stem[len("results-dist-"):]])
        try:
            system, rows = read_sheet(path)
        except Exception as e:
            sys.exit(f"error: cannot read {path.relative_to(BENCH)}: {e!r}; results.duckdb was NOT updated")
        limits, skipped = set(), []
        for name, vals in rows:
            level, trains = parse_instance(name)
            if trains is None:  # not an instance (e.g. './manifest')
                skipped.append(name)
                continue
            d = dict(zip(MEASURES, vals))
            if d["rstatus"] == "out of time" and isinstance(d["time"], (int, float)):
                limits.add(d["time"])
            runs.append([source, exp, variant, date, system, name, level, trains, *vals])
        sources.append({
            "source": source, "experiment": exp, "variant": variant, "date": date,
            "system": system, "file": path.relative_to(BENCH).as_posix(),
            "n_instances": len(rows) - len(skipped), "timeout_limit": max(limits) if limits else None,
        })
        print(f"  {source:32s} {exp:8s} {variant or '-':10s} {len(rows) - len(skipped):4d} rows  {system}"
              + (f"  (skipped {sorted(set(skipped))})" if skipped else ""))

    with open(HERE / "runs.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerows(runs)
    with open(HERE / "sources.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sources[0]))
        w.writeheader()
        w.writerows(sources)
    print(f"wrote runs.csv ({len(runs)} rows), sources.csv ({len(sources)} sources)")

    # Build into temporary files and swap them in only if everything succeeded,
    # so a failed build never leaves a missing or half-written database.
    db, tmp_db = HERE / "results.duckdb", HERE / "results.duckdb.tmp"
    summ, tmp_summ = HERE / "summary.json", HERE / "summary.json.tmp"
    tmp_db.unlink(missing_ok=True)
    tmp_summ.unlink(missing_ok=True)
    sql = (HERE / "schema.sql").read_text()
    # Per-experiment views: exp_ce, exp_dc_ef, ...
    for code in sorted({s["experiment"] for s in sources}):
        name = "exp_" + re.sub(r"\W", "_", code)
        sql += f"\nCREATE VIEW {name} AS SELECT * FROM results WHERE experiment = '{code}';"
    sql += "\nCOPY (SELECT * FROM summary_by_trains ORDER BY source, trains) " \
           f"TO '{tmp_summ.name}' (FORMAT json, ARRAY true);\n"
    try:
        subprocess.run([duck, "-no-agent", "-bail", str(tmp_db)], input=sql, text=True,
                       cwd=HERE, check=True)
    except subprocess.CalledProcessError:
        tmp_db.unlink(missing_ok=True)
        tmp_summ.unlink(missing_ok=True)
        sys.exit("error: duckdb build failed; results.duckdb was NOT updated")
    tmp_db.replace(db)
    tmp_summ.replace(summ)
    print("wrote results.duckdb, summary.json")

    loaded = {s["file"]: s["n_instances"] for s in sources}
    bad = []
    for x in args.expect:
        rel = Path(x).resolve().relative_to(BENCH).as_posix()
        if loaded.get(rel, 0) < 1:
            bad.append(f"{rel} ({'no instance rows' if rel in loaded else 'not found'})")
    if bad:
        sys.exit("error: expected results missing from the database: " + ", ".join(bad))


if __name__ == "__main__":
    main()
