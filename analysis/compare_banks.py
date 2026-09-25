#!/usr/bin/env python3
"""Compare two item banks for systematic differences between their generators.

Two banks exist to break the generator-model confound in wave 1, where every
item was Claude-written and a Claude judge told "written by Claude" was told the
truth. That only works if the banks differ in *authorship* and not in anything a
judge could read off the code. A stylistic signature that separates the banks is
itself a confound: it would let a judge distinguish them without the label.

    python analysis/compare_banks.py data/items_gpt5 data/items_gemini25pro
"""
import ast
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load(bank: Path):
    out = {}
    for p in sorted(bank.glob("*.json")):
        if p.name == "failures.jsonl":
            continue
        it = json.loads(p.read_text())
        out[it["cell_id"], it["sample_idx"]] = it
    return out


def features(code: str) -> dict:
    """Surface properties a reader could notice without running anything."""
    tree = ast.parse(code)
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef)), None)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    calls = Counter(
        n.func.id for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    )
    return {
        "lines": len(code.strip().splitlines()),
        "fn_name_words": len((fn.name if fn else "").split("_")),
        "params": len(fn.args.args) if fn else 0,
        "returns": sum(1 for n in ast.walk(tree) if isinstance(n, ast.Return)),
        "ifs": sum(1 for n in ast.walk(tree) if isinstance(n, ast.If)),
        "loops": sum(1 for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While))),
        "comprehensions": sum(
            1 for n in ast.walk(tree)
            if isinstance(n, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp))
        ),
        "tries": sum(1 for n in ast.walk(tree) if isinstance(n, ast.Try)),
        "builtin_helpers": sum(calls[b] for b in ("sum", "sorted", "len", "min", "max", "any", "all")),
        "fstrings": sum(1 for n in ast.walk(tree) if isinstance(n, ast.JoinedStr)),
        "avg_name_len": st.mean([len(n) for n in names]) if names else 0,
    }


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        raise SystemExit(__doc__)
    a_dir, b_dir = Path(argv[0]), Path(argv[1])
    a, b = load(a_dir), load(b_dir)
    shared = sorted(set(a) & set(b))
    print(f"{a_dir.name}: {len(a)} items   {b_dir.name}: {len(b)} items   shared cells: {len(shared)}\n")

    fa = [features(a[k]["code"]) for k in shared]
    fb = [features(b[k]["code"]) for k in shared]
    keys = list(fa[0])

    print(f"{'feature':20s}{a_dir.name:>22s}{b_dir.name:>22s}{'Δ':>9s}{'':>4s}paired")
    print("-" * 80)
    for k in keys:
        xa = [f[k] for f in fa]
        xb = [f[k] for f in fb]
        # Sign test on the within-cell paired difference: same aim, same flavour,
        # so a lopsided split is a generator effect rather than an item effect.
        diffs = [y - x for x, y in zip(xa, xb) if y != x]
        pos = sum(1 for d in diffs if d > 0)
        flag = ""
        if diffs and (pos / len(diffs) >= 0.75 or pos / len(diffs) <= 0.25):
            flag = "  <-- lopsided"
        print(f"{k:20s}{st.mean(xa):>22.2f}{st.mean(xb):>22.2f}"
              f"{st.mean(xb) - st.mean(xa):>9.2f}    {pos}/{len(diffs)}{flag}")

    print("\nfunction names, same cell, both banks (first 12):")
    for k in shared[:12]:
        na = ast.parse(a[k]["code"]).body[-1]
        nb = ast.parse(b[k]["code"]).body[-1]
        na = na.name if isinstance(na, ast.FunctionDef) else "?"
        nb = nb.name if isinstance(nb, ast.FunctionDef) else "?"
        mark = "  same" if na == nb else ""
        print(f"  {k[0][:38]:40s} {na:28s} {nb:28s}{mark}")

    same = sum(1 for k in shared
               if isinstance(ast.parse(a[k]['code']).body[-1], ast.FunctionDef)
               and isinstance(ast.parse(b[k]['code']).body[-1], ast.FunctionDef)
               and ast.parse(a[k]['code']).body[-1].name == ast.parse(b[k]['code']).body[-1].name)
    print(f"\nidentical function names across banks: {same}/{len(shared)}")

    ident = sum(1 for k in shared if a[k]["code"].strip() == b[k]["code"].strip())
    print(f"byte-identical code across banks: {ident}/{len(shared)}")


if __name__ == "__main__":
    main()
