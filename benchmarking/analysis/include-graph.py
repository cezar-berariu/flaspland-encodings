#!/usr/bin/env python3
"""Build an interactive include-graph of the benchmark experiments.

Parses every `exp-*.lp` in benchmarking/experiments/, follows `#include` statements
(transitively, through the encodings), and writes `include-graph.html`
next to this script. Open that file in a browser.

    python3 benchmarking/analysis/include-graph.py

Include resolution mirrors clingo: relative to the including file's
directory first, then relative to the repository root. Includes that
cannot be found are shown in an "unresolved" box.
"""

import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent  # benchmarking/analysis
ROOT = HERE.parent.parent
EXPS = HERE.parent / "experiments"
ENC = ROOT / "encodings"
OUT = HERE / "include-graph.html"
TEMPLATE = HERE / "include-graph.template.html"
RESULTS = HERE / "results"  # built by results/build-results.py

INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"\s*\.')
CONST_RE = re.compile(r"^\s*#const\s+(.+?)\.\s*$")


def rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def parse(path: Path):
    """Return (includes, consts, header_comment) of an .lp file."""
    includes, consts, header = [], [], []
    in_header = True
    for line in path.read_text(errors="replace").splitlines():
        s = line.strip()
        if in_header and s.startswith("%"):
            header.append(s.lstrip("%").strip())
        elif s:
            in_header = False
        m = INCLUDE_RE.match(line)
        if m:
            includes.append(m.group(1))
        m = CONST_RE.match(line)
        if m:
            consts.append(m.group(1))
    return includes, consts, " ".join(h for h in header if h)


def resolve(raw: str, from_file: Path):
    """Return (node_id, status) where status is ok | root | missing."""
    cand = (from_file.parent / raw).resolve()
    if cand.is_file():
        return rel(cand), "ok"
    cand2 = (ROOT / raw).resolve()
    if cand2.is_file():
        return rel(cand2), "root"
    return rel(cand), "missing"


def readme_rounds():
    """code -> (round, description, order) from the experiments README."""
    info, rnd, order = {}, None, 0
    readme = EXPS / "README.md"
    if not readme.exists():
        return info
    for line in readme.read_text().splitlines():
        m = re.match(r"^##\s+(.*)", line)
        if m:
            rnd = m.group(1).strip()
            continue
        m = re.match(r"^\s*\d+\.\s*`([^`]+)`:\s*(.*)", line)
        if m and rnd:
            info[m.group(1)] = (rnd, m.group(2).strip(), order)
            order += 1
    return info


def attach_results(experiments):
    """Attach per-source, per-trains aggregates from results/summary.json."""
    summ_path, src_path = RESULTS / "summary.json", RESULTS / "sources.csv"
    if not summ_path.exists() or not src_path.exists():
        print("no results/summary.json - run results/build-results.py to include results")
        return
    sources = {r["source"]: r for r in csv.DictReader(src_path.open())}
    by_exp = {}
    for row in json.loads(summ_path.read_text()):
        by_exp.setdefault(row["experiment"], {}).setdefault(row["source"], []).append(row)
    keep = ["trains", "n", "solved", "timeouts", "memouts", "failed", "median_time", "mean_time",
            "mean_par2", "mean_grounding", "mean_solving", "mean_rules", "mean_variables",
            "mean_constraints", "mean_mem"]
    codes = {e["code"] for e in experiments}
    for code in sorted(set(by_exp) - codes):
        print(f"  ! results for '{code}' have no matching exp-{code}.lp")
    for e in experiments:
        res = []
        for src, rows in by_exp.get(e["code"], {}).items():
            s = sources[src]
            res.append({
                "source": src, "variant": s["variant"], "date": s["date"], "system": s["system"],
                "file": s["file"], "limit": float(s["timeout_limit"]) if s["timeout_limit"] else None,
                "rows": [{k: r[k] for k in keep} for r in sorted(rows, key=lambda r: r["trains"])],
            })
        # Primary source first: no variant, most recent date.
        res.sort(key=lambda r: r["date"], reverse=True)
        res.sort(key=lambda r: r["variant"] != "")
        e["results"] = res


def main():
    files = {}  # id -> node dict
    file_edges = set()  # (src_id, tgt_id)

    def add_node(node_id, status, raw=None):
        if node_id in files:
            return files[node_id]
        p = ROOT / node_id
        if status == "missing":
            kind, group = "missing", "unresolved"
        elif node_id.startswith("encodings/"):
            kind = "encoding"
            d = Path(node_id).parent.relative_to("encodings").as_posix()
            group = d if d != "." else "(encodings root)"
        else:
            kind, group = "other", Path(node_id).parent.as_posix()
        node = {
            "id": node_id,
            "label": Path(node_id).name,
            "kind": kind,
            "group": group,
            "raw": raw,
            "includes": [],
            "comment": "",
        }
        files[node_id] = node
        if kind != "missing":
            incs, _, comment = parse(p)
            node["comment"] = comment[:400]
            for r in incs:
                tid, st = resolve(r, p)
                add_node(tid, st, r)
                node["includes"].append({"raw": r, "target": tid, "status": st})
                file_edges.add((node_id, tid))
        return node

    # Every .lp under encodings/, used or not.
    for p in sorted(ENC.rglob("*.lp")):
        add_node(rel(p), "ok")

    rounds = readme_rounds()
    experiments = []
    for p in sorted(EXPS.glob("exp-*.lp")):
        incs, consts, comment = parse(p)
        code = p.stem[len("exp-"):]
        rnd, desc, order = rounds.get(code, ("Not in README", "", 10_000))
        includes = []
        for r in incs:
            tid, st = resolve(r, p)
            add_node(tid, st, r)
            includes.append({"raw": r, "target": tid, "status": st})
        experiments.append({
            "id": p.name,
            "code": code,
            "path": rel(p),
            "round": rnd,
            "desc": desc,
            "order": order,
            "consts": consts,
            "comment": comment,
            "includes": includes,
        })

    # Transitive reachability per file.
    adj = {fid: [i["target"] for i in n["includes"]] for fid, n in files.items()}
    reach = {}

    def dfs(fid, seen):
        for t in adj.get(fid, []):
            if t not in seen:
                seen.add(t)
                dfs(t, seen)
        return seen

    for fid in files:
        reach[fid] = sorted(dfs(fid, set()) - {fid})

    for e in experiments:
        direct = [i["target"] for i in e["includes"]]
        closure = set(direct)
        for d in direct:
            closure.update(reach[d])
        e["direct"] = direct
        e["closure"] = sorted(closure)

    attach_results(experiments)

    used = set()
    for e in experiments:
        used.update(e["closure"])
    for fid, n in files.items():
        n["used"] = fid in used

    data = {
        "root": ROOT.name,
        "experiments": experiments,
        "files": list(files.values()),
        "fileEdges": sorted(list(e) for e in file_edges),
        "reach": reach,
    }
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", json.dumps(data))
    OUT.write_text(html)
    n_missing = sum(1 for f in files.values() if f["kind"] == "missing")
    print(f"wrote {rel(OUT)}: {len(experiments)} experiments, "
          f"{len(files)} files ({len(used)} used, {n_missing} unresolved)")


if __name__ == "__main__":
    main()
