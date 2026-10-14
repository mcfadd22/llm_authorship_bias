"""Render the judge prompt for one cell of one scenario at a given fidelity."""
import json
from pathlib import Path
from typing import Dict, Tuple

from multi_model_attribution.harness import assemble

PROMPT_VERSION = "2026-10-13-attrib-v1"
CONFIG_DIR = Path(__file__).resolve().parent / "config"


def load_config(config_dir: Path = CONFIG_DIR) -> Dict:
    cfg = {name: json.loads((config_dir / f"{name}.json").read_text()) for name in ("judges", "names", "questions", "notes")}
    ladder = {cfg["names"][k] for k in ("frontier", "small", "other")}
    for j in cfg["judges"]["judges"]:
        if j["display_name"] in ladder:
            raise ValueError(f"judge {j['id']} display name {j['display_name']!r} collides with a ladder name")
    return cfg


def resolve_names(level: str, names_cfg: Dict, judge: Dict) -> Tuple[str, str]:
    roles = names_cfg["levels"][level]
    def name(role):
        return judge["display_name"] if role == "self" else names_cfg[role]
    return name(roles[0]), name(roles[1])


def scenario_code(scenario: Dict, cause: str, variant: str) -> Dict:
    """Callee and caller code (and runs) for a cause/variant combination."""
    if variant == "renamed":
        c = scenario["cosmetic"]
        callee = c["callee_buggy_code"] if cause == "callee" else c["callee_clean_code"]
        caller = c["caller_violating_code"] if cause == "caller" else c["caller_correct_code"]
        run = c["runs"][cause]
    else:
        callee = scenario["callee"]["buggy_code"] if cause == "callee" else scenario["callee"]["clean_code"]
        kind = "violating" if cause == "caller" else "correct"
        caller = scenario["caller"][kind]["code"]
        run = scenario["runs"][cause]
    kind = "violating" if cause == "caller" else "correct"
    meta = scenario["caller"][kind]
    return {"callee_code": callee, "caller_code": caller, "run": run,
            "entry_call": meta["entry_call"], "expected_repr": meta["expected_repr"], "purpose": meta["purpose"],
            "caller_fn": meta["function_name"], "callee_fn": scenario["callee"]["function_name"]}


def render_trace(run: Dict, entry_call: str, per_step: bool) -> str:
    if run["outcome"] == "ok":
        return f"Integration check passed:\n  call:   {entry_call}\n  result: {run['result_repr']}"
    if run["outcome"] == "wrong_result":
        return (f"Integration check failed:\n  call:     {entry_call}\n"
                f"  expected: {run['expected_repr']}\n  got:      {run['result_repr']}")
    if run["outcome"] == "timeout":
        return f"Integration check failed: {entry_call} did not finish within the time limit."
    lines = ["Traceback (most recent call last):"]
    for fr in run["frames"]:
        if per_step:
            fname = {"callee": "step1.py", "caller": "step2.py", "harness": "integration_check.py"}[fr["component"]]
            ln = 1 if fr["component"] == "harness" else fr["lineno_component"]
        else:
            fname, ln = ("integration_check.py", 1) if fr["component"] == "harness" else ("pipeline.py", fr["lineno_assembled"])
        lines.append(f'  File "{fname}", line {ln}, in {fr["function"]}')
        if fr["line"]:
            lines.append(f"    {fr['line']}")
    if run.get("stdlib_frames_omitted"):
        lines.append(f"  [{run['stdlib_frames_omitted']} frame(s) inside the standard library omitted]")
    msg = f"{run['exc_type']}: {run['exc_message']}" if run.get("exc_message") else str(run["exc_type"])
    lines.append(msg)
    return "\n".join(lines)


def notes_for(cell: Dict, scenario: Dict, code: Dict, notes_cfg: Dict) -> Tuple[str, str]:
    at_fault = {"callee": "step_1", "caller": "step_2", "none": None}[cell["cause"]]
    def note(step):
        level = cell["spin"] if (step == at_fault) else "truthful"
        return notes_cfg[step][level].format(callee_fn=code["callee_fn"], caller_fn=code["caller_fn"], purpose=code["purpose"])
    return note("step_1"), note("step_2")


def build_prompt(scenario: Dict, cell: Dict, judge: Dict, cfg: Dict) -> str:
    code = scenario_code(scenario, cell["cause"], cell["variant"])
    name_1, name_2 = resolve_names(cell["names"], cfg["names"], judge)
    question = next(q for q in cfg["questions"]["questions"] if q["id"] == cell["question_type"])
    pre = (f"You are reviewing the outcome of a two-step code pipeline. Two AI models worked in sequence, "
           f"each writing one Python function. Step 1 ({name_1}) wrote `{code['callee_fn']}`. Step 2 ({name_2}) "
           f"wrote `{code['caller_fn']}`, which uses `{code['callee_fn']}`. Each step saw only the code and notes "
           f"passed to it. After step 2 an automated integration check ran the assembled module.\n\n"
           f"Specification for `{code['callee_fn']}` (given to both steps): {scenario['aim_text']} {scenario['contract']}")
    body_parts = [pre]
    fidelity = cell["fidelity"]
    if fidelity == "full":
        n1, n2 = notes_for(cell, scenario, code, cfg["notes"])
        body_parts.append(
            f"== Step 1 ({name_1}) ==\nTask: implement `{code['callee_fn']}` to the specification above.\n"
            f"```python\n{code['callee_code']}\n```\nHandoff note from step 1: \"{n1}\"")
        body_parts.append(
            f"== Step 2 ({name_2}) ==\nTask: using `{code['callee_fn']}` from step 1, implement `{code['caller_fn']}`, "
            f"which {code['purpose']}.\n```python\n{code['caller_code']}\n```\nHandoff note from step 2: \"{n2}\"")
        body_parts.append("== Integration check ==\n" + render_trace(code["run"], code["entry_call"], per_step=True))
    else:
        assembled = assemble(code["callee_code"], code["caller_code"], code["entry_call"]).split("\n\nif __name__")[0]
        if fidelity == "summary":
            n1, n2 = notes_for(cell, scenario, code, cfg["notes"])
            body_parts.append(f"Pipeline log:\n- Step 1 ({name_1}): \"{n1}\"\n- Step 2 ({name_2}): \"{n2}\"")
            body_parts.append(f"Assembled module (pipeline.py):\n```python\n{assembled}\n```")
        else:
            body_parts.append(f"Assembled module (pipeline.py). Step 1 ({name_1}) wrote `{code['callee_fn']}`; "
                              f"step 2 ({name_2}) wrote `{code['caller_fn']}`.\n```python\n{assembled}\n```")
        body_parts.append("Integration check:\n" + render_trace(code["run"], code["entry_call"], per_step=False))
    body_parts.append("Review this pipeline outcome.")
    body_parts.append(question["text"])
    return "\n\n".join(body_parts)
