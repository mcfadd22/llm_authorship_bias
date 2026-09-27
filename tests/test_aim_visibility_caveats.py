import csv
import json

import pandas as pd

import apply_aim_visibility as av
import run_confirmatory as rc


def test_adjudication_replaces_provisional_flags_and_keeps_others():
    caveats = [
        {"item_id": "a", "caveat": "aim_visibility_likely_no", "detail": "x"},
        {"item_id": "a", "caveat": "severity_open", "detail": "y"},
        {"item_id": "b", "caveat": "aim_visibility_likely_borderline", "detail": "z"},
        {"item_id": "c", "caveat": "aim_visibility_likely_no", "detail": "w"},
    ]
    flags = [{"item_id": "a", "aim_visible": "yes", "reason": ""},
             {"item_id": "b", "aim_visible": "no", "reason": "contract only"},
             {"item_id": "c", "aim_visible": "", "reason": ""}]
    out = {(r["item_id"], r["caveat"]) for r in av.apply(flags, caveats, "subset")}
    assert out == {("a", "severity_open"), ("b", "aim_visibility_no"), ("c", "aim_visibility_likely_no")}


def _elicitation(tmp_path):
    """Two items, every label, blame only, one judge; enough for run_confirmatory to run."""
    d = tmp_path / "elic"
    d.mkdir()
    labels = ["none", "self", "other_model_A", "other_model_B", "generic_ai", "human_developer"]
    rng = __import__("numpy").random.default_rng(0)
    with (d / "j.jsonl").open("w") as fh:
        for i in range(12):
            for lab in labels:
                fh.write(json.dumps({"item_id": f"x__f__g__{i:03d}", "author_label": lab,
                                     "question_type": "q_blame", "scale_response": int(rng.integers(1, 8)),
                                     "judge_family": "claude", "judge_tuning": "t",
                                     "rival_a": "gpt", "rival_b": "gemini",
                                     "code_version": "buggy"}) + "\n")
    return d


def test_plan_65_drops_aim_visibility_no_by_default(tmp_path, capsys):
    caveats = tmp_path / "c.csv"
    with caveats.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["item_id", "caveat", "detail"])
        w.writeheader()
        w.writerow({"item_id": "x__f__g__000", "caveat": "aim_visibility_likely_no", "detail": ""})
        w.writerow({"item_id": "x__f__g__001", "caveat": "severity_open", "detail": ""})
    items = tmp_path / "items"
    items.mkdir()
    args = ["--elicitation-dir", str(_elicitation(tmp_path)), "--items-dir", str(items),
            "--caveats", str(caveats), "--n-boot", "49", "--out", str(tmp_path / "o.csv")]
    rc.main(args + ["--plan", "6.5"])
    assert "dropped 1 of 12 items" in capsys.readouterr().out
    rc.main(args + ["--plan", "6.5", "--exclude-caveats", ""])
    assert "caveat in" not in capsys.readouterr().out
    rc.main(args)
    assert "caveat in" not in capsys.readouterr().out
    assert pd.read_csv(tmp_path / "o.csv")["clusters"].max() == 12
