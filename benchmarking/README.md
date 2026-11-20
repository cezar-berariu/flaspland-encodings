# Benchmarking flaspland environments

## Layout

| folder | contents |
|---|---|
| `experiments/` | only the experiment definitions: `exp-<code>.lp` (which encodings to combine) and `README.md` (what each code means) |
| `analysis/<YYYYMMDD>/` | everything a benchmark run produced on that date: `results-dist-*.xlsx`, raw `output-*` folders, derived CSVs |
| `analysis/results/` | `build-results.py` collects all `analysis/<YYYYMMDD>/**/results-dist-*.xlsx` into `results.duckdb` / CSV (see its README) |
| `analysis/include-graph.py` | builds `analysis/include-graph.html` (experiments → encodings, with results) |
| `analysis/*.R` | R analysis scripts and their outputs |
| `envs/` | benchmark instances, plus the scripts that generate and sample them |
| `zesty/` | runscripts and solver binaries used by `run-local.sh` / `run-dist-*.sh` |

`run-dist-collect.sh <name>` and `run-local.sh <name>` write their `results-*.xlsx` straight into `analysis/<YYYYMMDD>/` (today's date; override with `RESULTS_DATE=YYYYMMDD`). They refuse to overwrite an existing file.

## Install the `btool`

Follow the instructions for setting up the [benchmarking tool](https://github.com/potassco/benchmark-tool/tree/master).

```
git clone https://github.com/potassco/benchmark-tool
cd benchmark-tool
conda create -n <env-name> python=3.10
conda activate <env-name>
pip install .
```

Then run the following command:
```
btool init
```

## Prepare the instance

Follow these steps to run the benchmarks:
1. Modify the runscript to consider the correct encodings and instances (see below)
2. Run the command `btool gen runscripts/runscript-<name>.xml` to generate the necessary folder structure
3. Run the command `python ./output/test-run/local/start.py`
4. To generate a results spreadsheet, run `btool eval runscripts/runscript-<name>.xml | btool conv -o results.xlsx`

---

## Modify the runscript

### Encodings
```
<system name="clasp" version="3.4.0" measures="clasp" config="seq-generic">       
    <setting name="base" cmdline="--stats" tag="basic">
        <encoding file="../move2drive/move-subnodes-two.lp"/>
    </setting>
</system>
```

### Instances
The `<encoding file=""/>` can be edited to consider different encodings.
Furthermore, additional lines can be added to consider additional encodings.

```
<benchmark name="flatland-instances">
    <folder path="toy-env"/>
</benchmark>
```

The `<folder path=""/>` line can be edited to consider different instances.
The benchmarking tool considers all instance files in the folder.
