import json
from pathlib import Path

import pytest

import multi_model_attribution.run_judges as rj
from multi_model_attribution.cells import row_key
from elicitation.clients import ElicitationError, JudgeResponse


class FakeClient:
    def __init__(self, attribution="step_1", points=(70, 30), fail_first=0):
        self.calls = 0; self.attribution = attribution; self.points = points; self.fail_first = fail_first
    def ask(self, prompt, schema):
        self.calls += 1
        if self.calls <= self.fail_first:
            raise ElicitationError("boom")
        if "step" in schema["properties"]:
            data = {"step": self.attribution, "explanation": "the callee never divides by the count"}
        else:
            data = {"step_1_points": self.points[0], "step_2_points": self.points[1], "explanation": "mostly the callee's fault"}
        return JudgeResponse(data=data, raw_text=json.dumps(data), model="m", usage={"completion_tokens": 5}, thinking="hmm", provider="P")


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(rj.time, "sleep", lambda s: None)


def _opts(tmp_path, **kw):
    base = dict(repeats=2, limit=None, dry_run=False, overwrite=False, max_retries=3, concurrency=4, out_dir=tmp_path / "out")
    base.update(kw); return rj.RunOptions(**base)


def test_validate():
    rj.validate("attribution", {"step": "step_2", "explanation": "because of the caller"})
    with pytest.raises(ElicitationError, match="step not one"):
        rj.validate("attribution", {"step": "step_3", "explanation": "x y z"})
    rj.validate("split", {"step_1_points": 40, "step_2_points": 60, "explanation": "shared"})
    with pytest.raises(ElicitationError, match="sum"):
        rj.validate("split", {"step_1_points": 40, "step_2_points": 50, "explanation": "shared"})
    with pytest.raises(ElicitationError, match="range"):
        rj.validate("split", {"step_1_points": 120, "step_2_points": -20, "explanation": "shared"})
    with pytest.raises(ElicitationError, match="degenerate"):
        rj.validate("attribution", {"step": "step_1", "explanation": "..."})


def test_elicit_one_record_shape(scenario, cfg, judge):
    rows = rj.enumerate_cells([scenario], judge, cfg["questions"]["questions"], 1)
    attr = next(r for r in rows if r["question_kind"] == "attribution" and r["cause"] == "callee")
    rec = rj.elicit_one(FakeClient(), attr, scenario, judge, cfg, 3)
    assert rec["attribution"] == "step_1" and rec["step_1_points"] is None and rec["truth"] == "step_1"
    assert rec["response_provider"] == "P" and rec["thinking"] == "hmm" and rec["prompt_version"] == rj.PROMPT_VERSION
    assert rec["schema_version"] == rj.SCHEMA_VERSION
    assert list(rj.SPLIT_SCHEMA["properties"]) == ["explanation", "step_1_points", "step_2_points"]
    assert "Step 1 (Claude)" in rec["prompt"]
    split = next(r for r in rows if r["question_kind"] == "split")
    rec2 = rj.elicit_one(FakeClient(), split, scenario, judge, cfg, 3)
    assert rec2["step_1_points"] == 70 and rec2["attribution"] is None


def test_prompted_json_mode_for_named_question_kinds(scenario, cfg, judge):
    class Capture(FakeClient):
        def ask(self, prompt, schema):
            self.last = (prompt, schema); return super().ask(prompt, schema if schema is not None else rj.SPLIT_SCHEMA)
    j = {**judge, "prompted_json_for": ["split"]}
    rows = rj.enumerate_cells([scenario], j, cfg["questions"]["questions"], 1)
    split = next(r for r in rows if r["question_kind"] == "split")
    c = Capture(); rec = rj.elicit_one(c, split, scenario, j, cfg, 3)
    assert c.last[1] is None and c.last[0].endswith(rj.PROMPTED_FORMAT_LINE["split"])
    assert rec["schema_version"].endswith("-prompted") and rec["step_1_points"] == 70
    attr = next(r for r in rows if r["question_kind"] == "attribution")
    c2 = Capture(); rec2 = rj.elicit_one(c2, attr, scenario, j, cfg, 3)
    assert c2.last[1] is rj.ATTRIBUTION_SCHEMA and not rec2["schema_version"].endswith("-prompted")


def test_elicit_one_retries_then_fails(scenario, cfg, judge):
    rows = rj.enumerate_cells([scenario], judge, cfg["questions"]["questions"], 1)
    rec = rj.elicit_one(FakeClient(fail_first=2), rows[0], scenario, judge, cfg, 3)
    assert rec["attribution"] == "step_1"
    with pytest.raises(RuntimeError, match="failed after 2 attempts"):
        rj.elicit_one(FakeClient(fail_first=5), rows[0], scenario, judge, cfg, 2)


def test_rate_limiter_spaces_calls():
    now = [0.0]; slept = []
    def sleep(s):
        slept.append(s); now[0] += s
    limiter = rj.RateLimiter(rpm=30, clock=lambda: now[0], sleep=sleep)
    for _ in range(3):
        limiter.wait()
    assert slept == [2.0, 2.0]          # first call goes at once, then one every 60/30 s
    now[0] += 10
    limiter.wait()
    assert slept == [2.0, 2.0]          # an idle gap longer than the interval needs no wait


def test_elicit_one_waits_for_the_limiter_on_every_attempt(scenario, cfg, judge):
    class Counting:
        n = 0
        def wait(self):
            self.n += 1
    rows = rj.enumerate_cells([scenario], judge, cfg["questions"]["questions"], 1)
    limiter = Counting()
    rj.elicit_one(FakeClient(fail_first=2), rows[0], scenario, judge, cfg, 3, limiter=limiter)
    assert limiter.n == 3


def test_elicit_one_logs_each_retried_error(scenario, cfg, judge, capsys):
    rows = rj.enumerate_cells([scenario], judge, cfg["questions"]["questions"], 1)
    rj.elicit_one(FakeClient(fail_first=2), rows[0], scenario, judge, cfg, 3)
    lines = [l for l in capsys.readouterr().out.splitlines() if "retry" in l]
    assert len(lines) == 2 and "attempt 1/3" in lines[0] and "ElicitationError: boom" in lines[0]


def test_run_judge_writes_resumes_and_logs_failures(scenario, cfg, judge, tmp_path):
    opts = _opts(tmp_path)
    summary = rj.run_judge(FakeClient(), judge, [scenario], cfg, opts)
    assert summary == {"generated": 138, "skipped": 0, "failed": 0}
    rows = [json.loads(l) for l in (opts.out_dir / "qwen3-32b.jsonl").read_text().splitlines()]
    assert len({row_key(r) for r in rows}) == 138
    again = rj.run_judge(FakeClient(), judge, [scenario], cfg, opts)
    assert again == {"generated": 0, "skipped": 138, "failed": 0}
    opts2 = _opts(tmp_path, out_dir=tmp_path / "out2", max_retries=1, limit=5)
    bad = rj.run_judge(FakeClient(fail_first=99), judge, [scenario], cfg, opts2)
    assert bad == {"generated": 0, "skipped": 0, "failed": 5}
    assert len((opts2.out_dir / "failures.jsonl").read_text().splitlines()) == 5


def test_dry_run_and_manifest(scenario, cfg, judge, tmp_path, monkeypatch, capsys):
    sdir = tmp_path / "scenarios"; sdir.mkdir()
    (sdir / f"{scenario['scenario_id']}.json").write_text(json.dumps(scenario))
    (sdir / "selection_log.json").write_text("{}")
    out = tmp_path / "run"
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    rj.main(["--dry-run", "--scenarios-dir", str(sdir), "--out-dir", str(out), "--judge", "qwen3-32b"])
    text = capsys.readouterr().out
    assert "planned   138" in text and "$" in text and not (out / rj.MANIFEST).exists()
    with pytest.raises(SystemExit, match="OPENROUTER_API_KEY"):
        rj.main(["--scenarios-dir", str(sdir), "--out-dir", str(out), "--judge", "qwen3-32b", "--limit", "1"])
    # manifest written by the non-dry attempt before the key check; a changed scenario set is refused
    assert (out / rj.MANIFEST).exists()
    (sdir / f"{scenario['scenario_id']}.json").write_text(json.dumps({**scenario, "contract": "changed"}))
    with pytest.raises(SystemExit, match="scenarios_sha256"):
        rj.main(["--dry-run", "--scenarios-dir", str(sdir), "--out-dir", str(out)])


def test_manifest_ignores_routing_changes(scenario, cfg, tmp_path):
    import json as _json
    cdir = tmp_path / "config"; cdir.mkdir()
    for name in ("judges", "names", "questions", "notes"):
        (cdir / f"{name}.json").write_text(_json.dumps(cfg[name]))
    files = [tmp_path / "s.json"]; files[0].write_text(_json.dumps(scenario))
    out = tmp_path / "run"
    rj.check_manifest(out, files, cdir, write=True)
    (cdir / "judges.json").write_text(_json.dumps({"judges": []}))
    rj.check_manifest(out, files, cdir, write=False)          # routing change accepted
    (cdir / "notes.json").write_text(_json.dumps({"step_1": {}}))
    with pytest.raises(SystemExit, match="config_sha256"):
        rj.check_manifest(out, files, cdir, write=False)      # prompt content change refused


def test_require_reviewed(scenario, tmp_path):
    sdir = tmp_path / "s"; sdir.mkdir()
    (sdir / "a.json").write_text(json.dumps(scenario))
    with pytest.raises(SystemExit, match="not reviewed"):
        rj.load_scenarios(sdir, require_reviewed=True)
    (sdir / "a.json").write_text(json.dumps({**scenario, "review": {"violating_caller_reviewed": True, "note": "ok"}}))
    assert len(rj.load_scenarios(sdir, require_reviewed=True)) == 1
