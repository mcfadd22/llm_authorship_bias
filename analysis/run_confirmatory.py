#!/usr/bin/env python3
"""Run the design.md 6.1 confirmatory tests: H1-H3, WCB, Holm.

Each (hypothesis, judge_family, judge_tuning) is its own Holm correction family,
internally corrected across only the four label contrasts inside that cell --
never pooled across hypotheses, families, or tuning states (design.md 6.1).

    python analysis/run_confirmatory.py                      # wave 1
    python analysis/run_confirmatory.py --item-fe            # robustness variant
    python analysis/run_confirmatory.py --elicitation-dir data/elicitation_wave2/buggy
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frame import CONTRASTS, HYPOTHESES, design_matrix, load_frame  # noqa: E402
from wcb import holm, wcb_test  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def add_item_fixed_effects(sub, y, X, clusters):
    """Robustness variant only -- 6.1 as locked specifies no item FE."""
    items = pd.get_dummies(sub["item_id"], drop_first=True).to_numpy(dtype=float)
    return y, np.column_stack([X, items]), clusters


def run(df, n_boot, seed, item_fe=False, code_version="buggy"):
    df = df[df["code_version"] == code_version]
    results = []
    for hyp, question in HYPOTHESES.items():
        for cell, sub in df[df["question_type"] == question].groupby("judge_cell"):
            sub = sub.dropna(subset=["scale_response"]).sort_values("item_id")
            y, X, clusters = design_matrix(sub)
            if item_fe:
                y, X, clusters = add_item_fixed_effects(sub, y, X, clusters)
            raw = []
            for i, name in enumerate(CONTRASTS, start=1):
                beta, se, t, p = wcb_test(y, X, clusters, i, n_boot=n_boot, seed=seed)
                raw.append(dict(hypothesis=hyp, question=question, judge_cell=cell,
                                contrast=name, estimate=beta, se=se, t=t, p_raw=p,
                                n=len(sub), clusters=len(np.unique(clusters))))
            for r, adj in zip(raw, holm([r["p_raw"] for r in raw])):
                r["p_holm"] = adj
            results.extend(raw)
    return pd.DataFrame(results)


def stars(p):
    return "***" if p < .001 else "**" if p < .01 else "*" if p < .05 else "   "


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--elicitation-dir", default=None)
    ap.add_argument("--items-dir", default=None)
    ap.add_argument("--n-boot", type=int, default=4999)
    ap.add_argument("--seed", type=int, default=20260924)
    ap.add_argument("--item-fe", action="store_true",
                    help="add item fixed effects (robustness, NOT the locked 6.1 spec)")
    ap.add_argument("--out", default=None, help="write results CSV here")
    args = ap.parse_args(argv)

    df = load_frame(args.elicitation_dir, args.items_dir)
    res = run(df, args.n_boot, args.seed, item_fe=args.item_fe)

    label = "6.1 CONFIRMATORY" + ("  [+item FE robustness variant]" if args.item_fe else "")
    print(f"\n{label}   wild cluster bootstrap B={args.n_boot}, clustered by item_id")
    print("Holm family = (hypothesis x judge_family x judge_tuning), 4 contrasts each\n")
    for hyp in HYPOTHESES:
        block = res[res["hypothesis"] == hyp]
        print(f"--- {hyp}: {HYPOTHESES[hyp]}")
        print(f"{'judge':18s}{'contrast':22s}{'est':>8s}{'se':>7s}{'t':>7s}{'p_raw':>9s}{'p_holm':>9s}")
        for cell, g in block.groupby("judge_cell"):
            for _, r in g.iterrows():
                print(f"{cell:18s}{r.contrast:22s}{r.estimate:>8.2f}{r.se:>7.2f}"
                      f"{r.t:>7.2f}{r.p_raw:>9.4f}{r.p_holm:>9.4f} {stars(r.p_holm)}")
        print()

    sig = res[res["p_holm"] < .05]
    print(f"Survives Holm at .05: {len(sig)} of {len(res)} contrasts")
    if len(sig):
        for _, r in sig.iterrows():
            print(f"  {r.hypothesis} {r.judge_cell:16s} {r.contrast:20s} "
                  f"{r.estimate:+.2f}  p={r.p_holm:.4f}")

    out = Path(args.out) if args.out else ROOT / "analysis" / (
        "confirmatory_item_fe.csv" if args.item_fe else "confirmatory.csv")
    res.to_csv(out, index=False)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
