#!/usr/bin/env python3
"""Run the confirmatory tests: design.md 6.1 (H1-H3) or 6.5 (H1-H3 plus H4), WCB, Holm.

Each (hypothesis, judge_family, judge_tuning) is its own Holm correction family,
internally corrected across only the four label contrasts inside that cell --
never pooled across hypotheses, families, or tuning states (design.md 6.1).

--plan 6.5 adds the wave-2 H4 tests: pooled rival minus self, two-sided, on
blame (H4a), intentionality (H4b) and ability-vs-diligence (H4c), each its own
family with one contrast per judge cell. H1-H3 are computed exactly as under
6.1, and the default output is unchanged.

    python analysis/run_confirmatory.py                      # wave 1, 6.1 as locked
    python analysis/run_confirmatory.py --item-fe            # robustness variant
    python analysis/run_confirmatory.py --plan 6.5 \
        --elicitation-dir data/elicitation_wave2/gpt5_buggy data/elicitation_wave2/gemini_buggy \
        --items-dir data/items_gpt5 data/items_gemini25pro      # primary (drops aim-visibility "no")
    ... --exclude-caveats aim_visibility_no,aim_visibility_likely_no,aim_visibility_borderline,aim_visibility_likely_borderline
    ... --exclude-caveats ''                                    # full bank
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frame import (CONTRASTS, H4, HYPOTHESES, RIVAL_VS_SELF_COL, design_matrix,  # noqa: E402
                   load_frame, rival_vs_self_matrix)
from wcb import holm, wcb_test  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CAVEATS = ROOT / "analysis" / "item_caveats.csv"
# design.md 6.5: the primary wave-2 analysis leaves out items whose intended bug
# cannot be seen from the judge-facing aim. After adjudication the flags are
# aim_visibility_no; without a human pass, the contract review's likely-no calls.
PRIMARY_EXCLUDE_CAVEATS = "aim_visibility_no,aim_visibility_likely_no"


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


def run_h4(df, n_boot, seed, item_fe=False, code_version="buggy"):
    """design.md 6.5 H4: other_model_pooled - self, one family per (outcome, judge cell)."""
    df = df[df["code_version"] == code_version]
    results = []
    for hyp, question in H4.items():
        for cell, sub in df[df["question_type"] == question].groupby("judge_cell"):
            sub = sub.dropna(subset=["scale_response"]).sort_values("item_id")
            y, X, clusters = rival_vs_self_matrix(sub)
            if item_fe:
                y, X, clusters = add_item_fixed_effects(sub, y, X, clusters)
            beta, se, t, p = wcb_test(y, X, clusters, RIVAL_VS_SELF_COL, n_boot=n_boot, seed=seed)
            # a single contrast per family: Holm leaves it unchanged
            results.append(dict(hypothesis=hyp, question=question, judge_cell=cell,
                                contrast="other_model_pooled - self", estimate=beta, se=se,
                                t=t, p_raw=p, p_holm=p, n=len(sub),
                                clusters=len(np.unique(clusters))))
    return pd.DataFrame(results)


def stars(p):
    return "***" if p < .001 else "**" if p < .01 else "*" if p < .05 else "   "


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--elicitation-dir", nargs="+", default=None,
                    help="one or more directories of elicitation .jsonl (e.g. each wave-2 leg)")
    ap.add_argument("--items-dir", nargs="+", default=None,
                    help="one or more item bank directories")
    ap.add_argument("--n-boot", type=int, default=4999)
    ap.add_argument("--seed", type=int, default=20260924)
    ap.add_argument("--verdicts", nargs="+", default=None,
                    help="CSV(s) of item-bank review verdicts (item_id,verdict,note), e.g. both banks")
    ap.add_argument("--exclude-verdicts", default="drop,not_a_bug",
                    help="comma-separated item verdicts to exclude when --verdicts is given")
    ap.add_argument("--exclude-twin-verdicts", default=None,
                    help="comma-separated twin verdicts to exclude, e.g. "
                         "twin_not_minimal,twin_breaks_contract. A sensitivity check: the twin "
                         "is the clean-code control, so a non-minimal one differs from its item "
                         "in more than the planted bug")
    ap.add_argument("--caveats", default=str(CAVEATS),
                    help="per-item caveats CSV (item_id,caveat,detail)")
    ap.add_argument("--exclude-caveats", default=None,
                    help="comma-separated caveats whose items are left out. Default: none under "
                         f"--plan 6.1; '{PRIMARY_EXCLUDE_CAVEATS}' under --plan 6.5 (its primary "
                         "analysis). Pass '' for the full bank, or add e.g. "
                         "aim_visibility_borderline,aim_visibility_likely_borderline for the "
                         "prespecified sensitivity rerun")
    ap.add_argument("--item-fe", action="store_true",
                    help="add item fixed effects (robustness, NOT the locked 6.1 spec)")
    ap.add_argument("--plan", choices=["6.1", "6.5"], default="6.1",
                    help="6.1: H1-H3 as locked for wave 1 (default). 6.5: the wave-2 plan, "
                         "H1-H3 plus H4 (rival vs. self)")
    ap.add_argument("--out", default=None, help="write results CSV here")
    args = ap.parse_args(argv)

    df = load_frame(args.elicitation_dir, args.items_dir)

    exclude_caveats = args.exclude_caveats
    if exclude_caveats is None:
        exclude_caveats = PRIMARY_EXCLUDE_CAVEATS if args.plan == "6.5" else ""
    if exclude_caveats:
        caveats = pd.read_csv(args.caveats)
        wanted = set(exclude_caveats.split(","))
        excluded = set(caveats.loc[caveats["caveat"].isin(wanted), "item_id"])
        before = df["item_id"].nunique()
        df = df[~df["item_id"].isin(excluded)]
        print(f"caveat in {sorted(wanted)}: dropped {before - df['item_id'].nunique()} of {before} items")

    if args.verdicts:
        verdicts = pd.concat([pd.read_csv(v) for v in args.verdicts], ignore_index=True)
        drop = set(args.exclude_verdicts.split(","))
        excluded = set(verdicts.loc[verdicts["verdict"].isin(drop), "item_id"])
        before = df["item_id"].nunique()
        df = df[~df["item_id"].isin(excluded)]
        after = df["item_id"].nunique()
        print(f"verdict in {sorted(drop)}: dropped {before - after} of {before} items"
              f"{'' if before != after else '  (no item_ids in common -- wrong bank?)'}")

        if args.exclude_twin_verdicts and "twin_verdict" in verdicts.columns:
            tdrop = set(args.exclude_twin_verdicts.split(","))
            texcl = set(verdicts.loc[verdicts["twin_verdict"].isin(tdrop), "item_id"])
            before = df["item_id"].nunique()
            df = df[~df["item_id"].isin(texcl)]
            after = df["item_id"].nunique()
            print(f"twin verdict in {sorted(tdrop)}: dropped {before - after} of {before} items")

    res = run(df, args.n_boot, args.seed, item_fe=args.item_fe)
    hypotheses = dict(HYPOTHESES)
    if args.plan == "6.5":
        res = pd.concat([res, run_h4(df, args.n_boot, args.seed, item_fe=args.item_fe)],
                        ignore_index=True)
        hypotheses.update(H4)

    label = f"{args.plan} CONFIRMATORY" + ("  [+item FE robustness variant]" if args.item_fe else "")
    print(f"\n{label}   wild cluster bootstrap B={args.n_boot}, clustered by item_id")
    print("Holm family = (hypothesis x judge_family x judge_tuning), 4 contrasts each"
          + ("; H4 families hold 1 contrast each" if args.plan == "6.5" else "") + "\n")
    for hyp in hypotheses:
        block = res[res["hypothesis"] == hyp]
        print(f"--- {hyp}: {hypotheses[hyp]}")
        print(f"{'judge':18s}{'contrast':26s}{'est':>8s}{'se':>7s}{'t':>7s}{'p_raw':>9s}{'p_holm':>9s}")
        for cell, g in block.groupby("judge_cell"):
            for _, r in g.iterrows():
                print(f"{cell:18s}{r.contrast:26s}{r.estimate:>8.2f}{r.se:>7.2f}"
                      f"{r.t:>7.2f}{r.p_raw:>9.4f}{r.p_holm:>9.4f} {stars(r.p_holm)}")
        print()

    sig = res[res["p_holm"] < .05]
    print(f"Survives Holm at .05: {len(sig)} of {len(res)} contrasts")
    if len(sig):
        for _, r in sig.iterrows():
            print(f"  {r.hypothesis} {r.judge_cell:16s} {r.contrast:20s} "
                  f"{r.estimate:+.2f}  p={r.p_holm:.4f}")

    stem = "confirmatory" + ("_6.5" if args.plan == "6.5" else "") + ("_item_fe" if args.item_fe else "")
    out = Path(args.out) if args.out else ROOT / "analysis" / f"{stem}.csv"
    res.to_csv(out, index=False)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
