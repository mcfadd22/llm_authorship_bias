import itertools
import re

import pytest

from multi_model_attribution.cells import CAUSES, FIDELITIES, NAME_LEVELS, SPINS
from multi_model_attribution.render import build_prompt, load_config, render_trace, resolve_names

LEAK = re.compile(r"\b(bug|buggy|clean|rationale|cause|wrong_algorithm|compute_average__)\b", re.I)


def _cell(**kw):
    base = {"variant": "base", "cause": "callee", "fidelity": "full", "names": "frontier_to_small",
            "spin": "truthful", "question_type": "q_attribution"}
    base.update(kw); return base


def test_resolve_names(cfg, judge):
    assert resolve_names("frontier_to_small", cfg["names"], judge) == ("Claude", "Gemma")
    assert resolve_names("small_to_frontier", cfg["names"], judge) == ("Gemma", "Claude")
    assert resolve_names("self_to_other", cfg["names"], judge) == ("Qwen", "Gemini")


def test_config_rejects_judge_colliding_with_ladder(tmp_path, cfg):
    import json
    for name in ("judges", "names", "questions", "notes"):
        (tmp_path / f"{name}.json").write_text(json.dumps(cfg[name]))
    bad = {"judges": [{"id": "x", "family": "gemma", "display_name": "Gemma", "provider": "openrouter", "model": "m"}]}
    (tmp_path / "judges.json").write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="collides"):
        load_config(tmp_path)


def test_fidelity_sections(scenario, cfg, judge):
    full = build_prompt(scenario, _cell(fidelity="full"), judge, cfg)
    summ = build_prompt(scenario, _cell(fidelity="summary"), judge, cfg)
    fin = build_prompt(scenario, _cell(fidelity="final_only"), judge, cfg)
    assert "== Step 1 (Claude) ==" in full and "== Step 2 (Gemma) ==" in full and "Handoff note from step 1" in full
    assert 'File "step2.py"' not in full  # callee bug = wrong result, not a traceback
    assert "Pipeline log:" in summ and "Assembled module (pipeline.py)" in summ and "Handoff note" not in summ
    assert "Pipeline log" not in fin and "Handoff note" not in fin and "Step 1 (Claude) wrote `compute_average`" in fin
    for p in (full, summ, fin):
        assert scenario["contract"] in p and p.endswith(cfg["questions"]["questions"][0]["text"])
        assert "Integration check failed" in p and "expected: 10.0" in p and "got:      30" in p
        assert not LEAK.search(p.replace("compute_average(", "fn(")), LEAK.search(p)


def test_traceback_rendering_per_step_vs_assembled(scenario, cfg, judge):
    full = build_prompt(scenario, _cell(cause="caller", fidelity="full"), judge, cfg)
    fin = build_prompt(scenario, _cell(cause="caller", fidelity="final_only"), judge, cfg)
    assert 'File "step2.py", line 3, in report_average' in full
    assert 'File "pipeline.py", line' in fin and "step2.py" not in fin
    assert "TypeError" in full and "TypeError" in fin


def test_spin_only_on_at_fault_step(scenario, cfg, judge):
    over = cfg["notes"]["step_1"]["overclaiming"].split(". ", 1)[1]  # "Handles all edge cases; ..."
    p = build_prompt(scenario, _cell(cause="callee", spin="overclaiming"), judge, cfg)
    assert p.count("Handles all edge cases") == 1 and "step 1: \"Implemented compute_average as specified. Handles" in p
    p = build_prompt(scenario, _cell(cause="caller", spin="overclaiming"), judge, cfg)
    assert p.count("Handles all edge cases") == 1 and "step 2: \"Implemented report_average" in p
    p = build_prompt(scenario, _cell(cause="none", spin="overclaiming"), judge, cfg)
    assert "Handles all edge cases" not in p and "Integration check passed" in p


def test_code_blocks_identical_across_names_spin_fidelity(scenario, cfg, judge):
    blocks = set()
    for names, spin in itertools.product(NAME_LEVELS, SPINS):
        p = build_prompt(scenario, _cell(names=names, spin=spin), judge, cfg)
        blocks.add(tuple(re.findall(r"```python\n(.*?)\n```", p, re.S)))
    assert len(blocks) == 1


def test_harness_frame_shows_entry_call_not_marker(scenario, cfg, judge):
    p = build_prompt(scenario, _cell(cause="caller", fidelity="full"), judge, cfg)
    assert "__RESULT__" not in p and "repr(" not in p
    assert 'File "integration_check.py", line 1, in <module>\n    report_average([2, 4, 9])' in p
    assert "```python\n" in p and "\n\n```" not in p   # no trailing blank line inside code blocks
    assert "calls compute_average and doubles the mean" in p


def test_render_trace_ok_and_timeout():
    assert render_trace({"outcome": "ok", "result_repr": "5"}, "f(1)", False) == "Integration check passed:\n  call:   f(1)\n  result: 5"
    assert "time limit" in render_trace({"outcome": "timeout"}, "f(1)", False)
