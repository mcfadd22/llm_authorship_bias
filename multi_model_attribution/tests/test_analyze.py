import random

import pytest

from multi_model_attribution import analyze
from multi_model_attribution.cells import enumerate_cells


def _frame(scenarios, judge, cfg, answer):
    """Build a complete fake result frame; `answer(row) -> (attribution, step_2_points)`."""
    rows = enumerate_cells(scenarios, judge, cfg["questions"]["questions"], repeats=2)
    out = []
    for r in rows:
        a, p2 = answer(r)
        rec = {**r, "attribution": a if r["question_kind"] == "attribution" else None,
               "step_1_points": (100 - p2) if r["question_kind"] == "split" else None,
               "step_2_points": p2 if r["question_kind"] == "split" else None}
        out.append(analyze.derive(rec))
    return out


def _scenarios(scenario, n):
    out = []
    for i in range(n):
        s = {**scenario, "scenario_id": f"s{i:02d}", "source_item_id": f"s{i:02d}"}
        if i < 3:
            s["cosmetic"] = {"callee_buggy_code": "x", "callee_clean_code": "y", "caller_correct_code": "z",
                             "caller_violating_code": "w", "rename_map": {}, "runs": scenario["runs"], "failure_kind": scenario["failure_kind"]}
        out.append(s)
    return out


def test_derive_columns():
    base = {"question_kind": "attribution", "truth": "step_1", "attribution": "step_2"}
    d = analyze.derive(base)
    assert d["correct"] == 0 and d["blamed_wrong_step"] == 1 and d["blames_step2"] == 1 and d["cannot_tell"] == 0 and d["false_alarm"] is None
    d = analyze.derive({"question_kind": "attribution", "truth": "neither", "attribution": "step_1"})
    assert d["false_alarm"] == 1 and d["correct"] == 0 and d["blamed_wrong_step"] is None
    d = analyze.derive({"question_kind": "split", "truth": "step_2", "step_1_points": 80, "step_2_points": 20})
    assert d["points_to_wrong_step"] == 80 and d["points_to_at_fault"] == 20


def test_design_baselines_and_columns(scenario, cfg, judge):
    frame = _frame(_scenarios(scenario, 2), judge, cfg, lambda r: ("step_1", 50))
    rows = [r for r in frame if r["cause"] != "none" and r["question_kind"] == "attribution"]
    X, names = analyze.design(rows, ["fidelity", "cause", "names", "spin"])
    assert names == ["intercept", "fidelity=summary", "fidelity=final_only", "cause=caller",
                     "names=small_to_frontier", "names=self_to_other", "spin=overclaiming"]
    assert X.shape == (len(rows), 7)


def test_recovers_planted_last_touch_and_fidelity_effects(scenario, cfg, judge):
    rng = random.Random(1)
    def answer(r):
        # judge blames step 2 whenever the cause is the callee at low fidelity (last-touch), else correct
        if r["cause"] == "none":
            return "neither", 50
        if r["cause"] == "callee" and r["fidelity"] == "final_only" and rng.random() < 0.9:
            return "step_2", 80
        return r["truth"], (20 if r["truth"] == "step_1" else 80)
    frame = _frame(_scenarios(scenario, 12), judge, cfg, answer)
    tests = analyze.run_families(frame, n_boot=199)
    f1 = {t["contrast"]: t for t in tests if t["family"] == "F1_fidelity"}
    assert f1["fidelity=final_only"]["est"] < -0.2 and f1["fidelity=summary"]["est"] > -0.05
    f2 = [t for t in tests if t["family"] == "F2_last_touch" and t["outcome"] == "blamed_wrong_step"][0]
    assert f2["est"] < 0  # under cause=caller the wrong-step rate is lower than under cause=callee
    assert {t["family"] for t in tests} == {"F1_fidelity", "F2_last_touch", "F3_plaintext_trust", "F4_status"}
    assert all(0 <= t["p_holm"] <= 1 and t["p_holm"] >= t["p_raw"] - 1e-12 for t in tests)


def test_raggedness_metrics_hand_computed(scenario, cfg, judge):
    counter = {"n": 0}
    def answer(r):
        counter["n"] += 1
        # repeat 1 of attribution flips on every cell; split differs by 10 between repeats
        if r["question_kind"] == "attribution":
            return ("step_1" if r["repeat_idx"] == 0 else "step_2"), 50
        return "step_1", (40 if r["repeat_idx"] == 0 else 50)
    frame = _frame(_scenarios(scenario, 4), judge, cfg, answer)
    rag = {m["metric"]: m for m in analyze.raggedness(frame)}
    assert rag["R1_retest_flip_rate"]["mean"] == 1.0
    assert rag["R2_retest_split_gap"]["mean"] == 10.0
    assert rag["R3_cosmetic_flip_rate"]["mean"] == 0.0        # renamed answers equal base answers at the same repeat
    assert rag["R3_excess_over_retest"]["mean"] == -1.0
    assert rag["R5_control_false_alarm"]["mean"] == 1.0        # every control answer names a step
    assert rag["params_b"]["mean"] == 32


def test_main_excludes_named_scenarios_into_suffixed_outputs(scenario, cfg, judge, tmp_path):
    import json
    frame = _frame(_scenarios(scenario, 4), judge, cfg, lambda r: ("step_1", 30))
    with open(tmp_path / f"{judge['id']}.jsonl", "w") as f:
        for r in frame:
            f.write(json.dumps(r) + "\n")
    analyze.main(["--results-dir", str(tmp_path), "--n-boot", "9", "--exclude-scenarios", "s00,s01"])
    out = (tmp_path / "descriptives_excl.csv").read_text()
    assert out and not (tmp_path / "descriptives.csv").exists()
    n_kept = sum(1 for r in frame if r["scenario_id"] not in ("s00", "s01") and r["variant"] == "base"
                 and r["question_kind"] == "attribution" and r["cause"] == "callee")
    lt = next(l for l in out.splitlines() if "last_touch_rate" in l)
    assert lt.endswith(f",{n_kept}")
