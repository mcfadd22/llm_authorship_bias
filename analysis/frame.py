"""Load elicitation rows into an analysis frame with the derived columns 6.1 needs.

Also derives `label_is_true`: whether the author named in the label matches the
model that actually generated the item bank. Wave 1's items were all generated
by claude-sonnet-4.5, so this is constant-by-construction for Claude judges'
`self` label -- but the rival rotation means GPT-5 judges saw a truthful
"written by Claude" label on some items, which is the only within-wave handle
on the generator-model confound. See design.md 1 and the wave-1 status doc.
"""
import ast
import json
import statistics as st
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BASELINE = "none"
CONTRASTS = ["self", "human_developer", "generic_ai", "other_model_pooled"]
HYPOTHESES = {"H1": "q_blame", "H2": "q_intentionality", "H3": "q_explanation"}


def _generator_family(generation_model):
    """'anthropic/claude-sonnet-4.5' -> 'claude'."""
    if not generation_model:
        return None
    tail = generation_model.split("/")[-1].lower()
    for fam in ("claude", "gpt", "gemini", "llama"):
        if tail.startswith(fam) or fam in tail:
            return fam
    return None


def _named_author(row):
    """Which model/entity the label names, in rival-pool id space."""
    label = row["author_label"]
    if label == "self":
        return row["judge_family"]
    if label == "other_model_A":
        return row["rival_a"]
    if label == "other_model_B":
        return row["rival_b"]
    return None  # none / generic_ai / human_developer name no specific model


def style_features(code):
    """Surface properties of the code a judge could notice without running it.

    Carried as covariates because the two banks differ systematically here:
    identifier length averages 5.1 characters in the GPT-5 bank against 8.3 in
    the Gemini bank, the same direction in 59 of 64 matched cells. That cannot
    touch H1-H3, which hold code byte-identical across an item's label cells,
    but it is confounded with generator in any cross-bank contrast -- so it
    needs to be measurable rather than assumed harmless.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"avg_name_len": None, "code_lines": None, "n_branches": None}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    return {
        "avg_name_len": st.mean([len(n) for n in names]) if names else None,
        "code_lines": len(code.strip().splitlines()),
        "n_branches": sum(1 for n in ast.walk(tree) if isinstance(n, ast.If)),
    }


def load_items(items_dir=None):
    items_dir = Path(items_dir or ROOT / "data" / "items")
    out = {}
    for p in sorted(items_dir.glob("*.json")):
        it = json.loads(p.read_text())
        out[it["item_id"]] = it
    return out


def load_frame(elicitation_dir=None, items_dir=None):
    elicitation_dir = Path(elicitation_dir or ROOT / "data" / "elicitation")
    rows = []
    for p in sorted(elicitation_dir.glob("*.jsonl")):
        if p.name == "failures.jsonl":
            continue
        with p.open() as fh:
            rows.extend(json.loads(line) for line in fh if line.strip())
    if not rows:
        raise SystemExit(f"no elicitation rows found in {elicitation_dir}")
    df = pd.DataFrame(rows)

    items = load_items(items_dir)
    df["generation_model"] = df["item_id"].map(lambda i: (items.get(i) or {}).get("generation_model"))
    df["generator_family"] = df["generation_model"].map(_generator_family)
    df["generator_tag"] = df["item_id"].map(lambda i: (items.get(i) or {}).get("generator_tag"))

    style = {i: style_features(it.get("code", "")) for i, it in items.items()}
    for feature in ("avg_name_len", "code_lines", "n_branches"):
        df[feature] = df["item_id"].map(lambda i, f=feature: (style.get(i) or {}).get(f))
    df["named_author"] = df.apply(_named_author, axis=1)
    truth = df["named_author"].notna() & (df["named_author"] == df["generator_family"])
    df["label_is_true"] = truth.astype(object).where(df["named_author"].notna(), pd.NA)

    # Wave 1 predates the clean-code control; its rows are all buggy.
    if "code_version" not in df.columns:
        df["code_version"] = "buggy"
    df["code_version"] = df["code_version"].fillna("buggy")

    df["judge_cell"] = df["judge_family"] + "/" + df["judge_tuning"]
    return df


def design_matrix(sub):
    """Intercept + the four 6.1 contrasts against `none`. Returns (y, X, clusters).

    `other_model_pooled` is a single dummy covering other_model_A and
    other_model_B, per 6.1 -- the A-vs-B split is deliberately exploratory.
    """
    import numpy as np

    label = sub["author_label"]
    cols = {
        "self": (label == "self"),
        "human_developer": (label == "human_developer"),
        "generic_ai": (label == "generic_ai"),
        "other_model_pooled": label.isin(["other_model_A", "other_model_B"]),
    }
    X = np.column_stack([np.ones(len(sub))] + [c.to_numpy(dtype=float) for c in cols.values()])
    y = sub["scale_response"].to_numpy(dtype=float)
    clusters = sub["item_id"].to_numpy()
    return y, X, clusters
