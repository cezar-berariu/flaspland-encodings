# Benchmark results database

All `analysis/<YYYYMMDD>/**/results-dist-*.xlsx` spreadsheets, collected into one place.

```
python3 benchmarking/analysis/results/build-results.py   # xlsx -> runs.csv, sources.csv, results.duckdb, summary.json
python3 benchmarking/analysis/include-graph.py          # re-embed summary.json into include-graph.html
```

Re-run both after dropping a new `results-dist-<code>.xlsx` into a date folder. The file
name decides the experiment: `results-dist-dc-l3.xlsx` -> experiment `dc`, variant `l3`;
a subfolder (e.g. `20260512/prelim/`) also becomes part of the variant.

## Tables and views (`duckdb benchmarking/analysis/results/results.duckdb`)

| name | what |
|---|---|
| `runs` | one row per (source spreadsheet, instance): all 17 btool measures |
| `sources` | one row per spreadsheet: experiment, variant, date, system, time limit |
| `results` | `runs` + `grounding_time`, `solved`, `outcome` (solved/timeout/memout/killed/other) |
| `summary_by_trains` | aggregates per source x train count (what the web page shows) |
| `summary` | aggregates per source |
| `exp_<code>` | `results` filtered to one experiment, e.g. `exp_ce`, `exp_dlhh4` |

`runs.csv` / `sources.csv` are the same data as plain CSV (readable from R, pandas, etc.).

## Example queries

```sql
-- solved count and median time per experiment, latest main run
SELECT * FROM summary WHERE variant = '' ORDER BY solved DESC, par2_sum;

-- head-to-head on the same instances
SELECT a.instance, a.time AS ms, b.time AS cs
FROM exp_ms a JOIN exp_cs b USING (instance)
WHERE a.variant = '' AND b.variant = '' ORDER BY a.time - b.time DESC LIMIT 10;

-- grounding size vs train count across subnode encodings
SELECT experiment, trains, avg(rules) FROM results
WHERE experiment IN ('ds','ms','cs','mcs') GROUP BY ALL ORDER BY ALL;
```
