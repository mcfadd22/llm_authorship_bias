#!/usr/bin/env python3
"""Pre-registered analysis for the multi-model attribution experiment.

    python -m multi_model_attribution.analyze --results-dir multi_model_attribution/results/run1

Writes tests.csv (families F1-F4, WCB + Holm per (family, judge)), descriptives.csv, and
raggedness.csv next to the results.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from multi_model_attribution import _paths  # noqa: F401
from wcb import holm, wcb_test

B_DEFAULT = 4999
SEED = 0


# ----------------------------------------------------------------------------- frame

def load_frame(results_dir: Path) -> List[Dict]:
    rows = []
    for p in sorted(Path(results_dir).glob("*.jsonl")):
        if p.name == "failures.jsonl":
            continue
        for line in p.read_text().splitlines():
            if line.strip():
                rows.append(derive(json.loads(line)))
    return rows


def derive(r: Dict) -> Dict:
    r = dict(r)
    truth = r["truth"]
    at_fault = {"step_1": "step_1", "step_2": "step_2"}.get(truth)
    wrong_step = {"step_1": "step_2", "step_2": "step_1"}.get(truth)
    if r["question_kind"] == "attribution":
        a = r["attribution"]
        r["correct"] = int(a == truth)
        r["cannot_tell"] = int(a == "cannot_tell")
        r["blames_step2"] = int(a == "step_2")
        r["blamed_wrong_step"] = int(a == wrong_step) if wrong_step else None
        r["false_alarm"] = int(a in ("step_1", "step_2")) if truth == "neither" else None
    else:
        p1, p2 = r["step_1_points"], r["step_2_points"]
        r["points_to_wrong_step"] = {"step_1": p2, "step_2": p1}.get(truth)
        r["points_to_at_fault"] = {"step_1": p1, "step_2": p2}.get(truth)
    return r


# ----------------------------------------------------------------------------- design

def _dummies(rows: List[Dict], factor: str, levels: Tuple[str, ...], baseline: str) -> Tuple[np.ndarray, List[str]]:
    cols, names = [], []
    for lv in levels:
        if lv == baseline:
            continue
        cols.append(np.array([1.0 if r[factor] == lv else 0.0 for r in rows])); names.append(f"{factor}={lv}")
    return (np.column_stack(cols) if cols else np.zeros((len(rows), 0))), names


FACTORS = {"fidelity": (("full", "summary", "final_only"), "full"),
           "cause": (("callee", "caller"), "callee"),
           "names": (("frontier_to_small", "small_to_frontier", "self_to_other"), "frontier_to_small"),
           "spin": (("truthful", "overclaiming"), "truthful")}


def design(rows: List[Dict], include: List[str]) -> Tuple[np.ndarray, List[str]]:
    X = [np.ones((len(rows), 1))]; names = ["intercept"]
    for f in include:
        levels, base = FACTORS[f]
        d, n = _dummies(rows, f, levels, base); X.append(d); names += n
    return np.column_stack(X), names


def _test(rows: List[Dict], outcome: str, include: List[str], contrasts: List[str], n_boot: int) -> List[Dict]:
    rows = [r for r in rows if r.get(outcome) is not None]
    if len(rows) < 10:
        return []
    y = np.array([float(r[outcome]) for r in rows]); X, names = design(rows, include)
    clusters = np.array([r["source_item_id"] for r in rows])
    out = []
    for c in contrasts:
        col = names.index(c)
        beta, se, t, p = wcb_test(y, X, clusters, col, n_boot=n_boot, seed=SEED)
        out.append({"outcome": outcome, "contrast": c, "est": beta, "se": se, "t": t, "p_raw": p,
                    "n": len(rows), "clusters": len(set(clusters))})
    return out


FAMILIES = {
    "F1_fidelity": dict(rows=lambda r: r["cause"] != "none" and r["question_kind"] == "attribution",
                        outcomes=["correct"], include=["fidelity", "cause", "names", "spin"],
                        contrasts=["fidelity=summary", "fidelity=final_only"]),
    "F2_last_touch": dict(rows=lambda r: r["cause"] != "none",
                          outcomes=["blamed_wrong_step", "points_to_wrong_step"], include=["cause", "fidelity", "names", "spin"],
                          contrasts=["cause=caller"]),   # negative => wrongly blaming step 2 under cause=callee exceeds the reverse
    "F3_plaintext_trust": dict(rows=lambda r: r["cause"] != "none" and r["fidelity"] != "final_only",
                               outcomes=["correct", "points_to_at_fault"], include=["spin", "fidelity", "cause", "names"],
                               contrasts=["spin=overclaiming"]),
    "F4_status": dict(rows=lambda r: r["cause"] != "none",
                      outcomes=["blames_step2", "step_2_points"], include=["names", "fidelity", "cause", "spin"],
                      contrasts=["names=small_to_frontier", "names=self_to_other"]),
}


def run_families(frame: List[Dict], n_boot: int) -> List[Dict]:
    results = []
    base = [r for r in frame if r["variant"] == "base"]
    for judge in sorted({r["judge_id"] for r in base}):
        jr = [r for r in base if r["judge_id"] == judge]
        for fam, spec in FAMILIES.items():
            rows = [r for r in jr if spec["rows"](r)]
            tests = []
            for outcome in spec["outcomes"]:
                tests += _test(rows, outcome, spec["include"], spec["contrasts"], n_boot)
            adj = holm([t["p_raw"] for t in tests]) if tests else []
            for t, p in zip(tests, adj):
                results.append({"family": fam, "judge": judge, **t, "p_holm": p})
    return results


# ----------------------------------------------------------------------------- descriptives

def _cluster_ci(values: List[float], clusters: List[str], n_boot: int = 1999) -> Tuple[float, float, float]:
    by = defaultdict(list)
    for v, c in zip(values, clusters):
        by[c].append(v)
    keys = list(by); rng = np.random.default_rng(SEED)
    mean = float(np.mean(values))
    boots = []
    for _ in range(n_boot):
        pick = rng.choice(len(keys), len(keys), replace=True)
        vals = [v for i in pick for v in by[keys[i]]]
        boots.append(np.mean(vals))
    return mean, float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def descriptives(frame: List[Dict]) -> List[Dict]:
    out = []
    base = [r for r in frame if r["variant"] == "base" and r["question_kind"] == "attribution"]
    for judge in sorted({r["judge_id"] for r in base}):
        jr = [r for r in base if r["judge_id"] == judge]
        for fidelity in ("full", "summary", "final_only"):
            for cause in ("callee", "caller", "none"):
                rows = [r for r in jr if r["fidelity"] == fidelity and r["cause"] == cause]
                if not rows: continue
                metric = "false_alarm" if cause == "none" else "correct"
                m, lo, hi = _cluster_ci([r[metric] for r in rows], [r["source_item_id"] for r in rows])
                out.append({"judge": judge, "fidelity": fidelity, "cause": cause, "metric": metric, "mean": m, "ci_lo": lo, "ci_hi": hi, "n": len(rows)})
        rows = [r for r in jr if r["cause"] == "callee"]
        m, lo, hi = _cluster_ci([r["blames_step2"] for r in rows], [r["source_item_id"] for r in rows])
        out.append({"judge": judge, "fidelity": "all", "cause": "callee", "metric": "last_touch_rate", "mean": m, "ci_lo": lo, "ci_hi": hi, "n": len(rows)})
    return out


def raggedness(frame: List[Dict]) -> List[Dict]:
    out = []
    for judge in sorted({r["judge_id"] for r in frame}):
        jr = [r for r in frame if r["judge_id"] == judge]
        def key(r, with_variant=True):
            return (r["scenario_id"], r["variant"] if with_variant else None, r["cause"], r["fidelity"], r["names"], r["spin"], r["question_type"])
        by = defaultdict(dict)
        for r in jr:
            by[key(r)][r["repeat_idx"]] = r
        # R1 / R2: between repeats
        flips, gaps, flip_cl, gap_cl = [], [], [], []
        for k, reps in by.items():
            if 0 in reps and 1 in reps:
                a, b = reps[0], reps[1]
                if a["question_kind"] == "attribution":
                    flips.append(int(a["attribution"] != b["attribution"])); flip_cl.append(a["source_item_id"])
                else:
                    gaps.append(abs(a["step_2_points"] - b["step_2_points"])); gap_cl.append(a["source_item_id"])
        for name, vals, cl in (("R1_retest_flip_rate", flips, flip_cl), ("R2_retest_split_gap", gaps, gap_cl)):
            if vals:
                m, lo, hi = _cluster_ci(vals, cl); out.append({"judge": judge, "metric": name, "mean": m, "ci_lo": lo, "ci_hi": hi, "n": len(vals)})
        # R3 / R4: base vs renamed on the cosmetic subset, same repeat, minus the retest rate on those cells
        cos_ids = {r["scenario_id"] for r in jr if r["variant"] == "renamed"}
        cflips, cgaps, ccl, ccl2, rflips, rgaps = [], [], [], [], [], []
        for k, reps in by.items():
            if k[0] not in cos_ids or k[1] != "renamed": continue
            base_key = (k[0], "base") + k[2:]
            if base_key not in by: continue
            for rep in (0, 1):
                if rep in reps and rep in by[base_key]:
                    a, b = by[base_key][rep], reps[rep]
                    if a["question_kind"] == "attribution":
                        cflips.append(int(a["attribution"] != b["attribution"])); ccl.append(a["source_item_id"])
                    else:
                        cgaps.append(abs(a["step_2_points"] - b["step_2_points"])); ccl2.append(a["source_item_id"])
            bk = by[base_key]
            if 0 in bk and 1 in bk:
                if bk[0]["question_kind"] == "attribution": rflips.append(int(bk[0]["attribution"] != bk[1]["attribution"]))
                else: rgaps.append(abs(bk[0]["step_2_points"] - bk[1]["step_2_points"]))
        if cflips:
            m, lo, hi = _cluster_ci(cflips, ccl); out.append({"judge": judge, "metric": "R3_cosmetic_flip_rate", "mean": m, "ci_lo": lo, "ci_hi": hi, "n": len(cflips)})
            out.append({"judge": judge, "metric": "R3_excess_over_retest", "mean": m - (np.mean(rflips) if rflips else 0.0), "ci_lo": None, "ci_hi": None, "n": len(cflips)})
        if cgaps:
            m, lo, hi = _cluster_ci(cgaps, ccl2); out.append({"judge": judge, "metric": "R4_cosmetic_split_gap", "mean": m, "ci_lo": lo, "ci_hi": hi, "n": len(cgaps)})
            out.append({"judge": judge, "metric": "R4_excess_over_retest", "mean": m - (np.mean(rgaps) if rgaps else 0.0), "ci_lo": None, "ci_hi": None, "n": len(cgaps)})
        ctrl = [r for r in jr if r["cause"] == "none" and r["question_kind"] == "attribution"]
        if ctrl:
            m, lo, hi = _cluster_ci([r["false_alarm"] for r in ctrl], [r["source_item_id"] for r in ctrl])
            out.append({"judge": judge, "metric": "R5_control_false_alarm", "mean": m, "ci_lo": lo, "ci_hi": hi, "n": len(ctrl)})
        params = next((r.get("judge_params_b") for r in jr if r.get("judge_params_b")), None)
        out.append({"judge": judge, "metric": "params_b", "mean": params, "ci_lo": None, "ci_hi": None, "n": len(jr)})
    return out


def write_csv(path: Path, rows: List[Dict]) -> None:
    if not rows:
        path.write_text(""); return
    keys = list({k: None for r in rows for k in r})
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results-dir", type=Path, required=True)
    p.add_argument("--n-boot", type=int, default=B_DEFAULT)
    p.add_argument("--exclude-caveated", action="store_true", help="sensitivity: drop scenarios whose item carries any caveat")
    args = p.parse_args(argv)
    frame = load_frame(args.results_dir)
    if args.exclude_caveated:
        scen_dir = args.results_dir.parent.parent / "scenarios"
        caveated = {json.loads(f.read_text())["scenario_id"] for f in scen_dir.glob("*__*.json") if json.loads(f.read_text()).get("caveats")}
        frame = [r for r in frame if r["scenario_id"] not in caveated]
    tests = run_families(frame, args.n_boot)
    suffix = "_nocaveat" if args.exclude_caveated else ""
    write_csv(args.results_dir / f"tests{suffix}.csv", tests)
    write_csv(args.results_dir / f"descriptives{suffix}.csv", descriptives(frame))
    write_csv(args.results_dir / f"raggedness{suffix}.csv", raggedness(frame))
    print(f"rows {len(frame)}; tests {len(tests)}; survives Holm .05: {sum(1 for t in tests if t['p_holm'] < 0.05)}")
    for t in tests:
        flag = "***" if t["p_holm"] < 0.001 else "**" if t["p_holm"] < 0.01 else "*" if t["p_holm"] < 0.05 else ""
        print(f"  {t['family']:<20} {t['judge']:<16} {t['outcome']:<22} {t['contrast']:<24} {t['est']:+.3f}  p_holm={t['p_holm']:.4f} {flag}")


if __name__ == "__main__":
    main()
