"""Generate and validate the step-2 callers for a source item.

Two callers per item: `correct` (within the contract; its entry input makes the buggy callee
twin misbehave) and `violating` (breaks one named contract clause against the clean callee).
Validation runs the sandbox harness and static checks; a rejection reason is fed back into the
next generation attempt.
"""
import ast
import re
from typing import Dict, Optional

from multi_model_attribution import _paths  # noqa: F401
from multi_model_attribution.harness import BROKEN_EXC_TYPES, RunResult, run
from elicitation.clients import ElicitationError, JudgeClient
from elicitation.orchestrate import RETRYABLE, _ask_with_deadline
from vignette_gen.validate import ValidationError, validate_code

PROMPT_VERSION = "2026-10-13-caller-v1"
LEAK_WORDS = re.compile(r"\b(bug|bugs|buggy|defect|defective|flaw|flawed|trap|trigger|triggers|planted|wrong|broken|test|tests|testing|incorrect|intentional|study)\b", re.I)

CALLER_SCHEMA: Dict = {
    "type": "object",
    "properties": {
        "code": {"type": "string"},
        "function_name": {"type": "string"},
        "purpose": {"type": "string", "description": "One clause, e.g. 'turns a list of readings into a one-line report'."},
        "entry_call": {"type": "string", "description": "A single Python expression calling the caller once."},
        "expected_repr": {"type": "string", "description": "Exact repr() of the correct result of entry_call."},
        "violation": {"type": "string", "description": "Violating mode only: the contract clause violated and how. Empty otherwise."},
    },
    "required": ["code", "function_name", "purpose", "entry_call", "expected_repr", "violation"],
    "additionalProperties": False,
}

TEMPLATE = """You are writing the second component of a two-step Python pipeline for a study of code review.
Step 1 produced the function below (the callee). Its specification is the CONTRACT. You write
step 2: one function (the caller) that uses the callee for a small, realistic downstream task,
an entry expression that calls the caller once, and the exact repr() of the result the entry
expression must produce if the whole pipeline is correct.

MODE: {mode_block}

STATED_AIM: "{aim_text}"
CONTRACT: {contract}

CALLEE (reference, correct implementation):
```python
{clean_code}
```
{bug_note_block}
Requirements for the caller:
- Python only; exactly one self-contained function; a leading import is allowed; no comments, no docstrings; body 3-25 lines.
- The caller must call `{callee_fn}` directly by name, exactly as defined above, and must not re-implement it, wrap it in try/except, or inspect its source.
- Nothing in the code, names, purpose, or violation text may hint at a problem, a check, or this study. Neutral, realistic names only.
- Choose inputs whose correct result has an exact, deterministic repr (prefer ints, short strings, lists; avoid floats that do not round-trip).
- Do not define any other function or class. Do not print.
{previous_block}
Return JSON with exactly these fields:
{{"code": "<caller code>", "function_name": "<name>", "purpose": "<one clause>", "entry_call": "<expression>", "expected_repr": "<repr>", "violation": "<violating mode only, else empty string>"}}
"""

MODE_CORRECT = (
    "CORRECT. Write a caller that uses the callee strictly within the CONTRACT. An alternative "
    "version of the callee contains the problem described in NOTE below; choose entry inputs "
    "that are valid under the CONTRACT and on which that alternative version produces a "
    "different result or raises, so the difference becomes observable in the pipeline. "
    "expected_repr is the correct result per the CONTRACT. violation must be an empty string."
)
MODE_VIOLATING = (
    "VIOLATING. Write a caller that misuses the callee by violating one specific clause of the "
    "CONTRACT (for example: passes input the CONTRACT declares invalid, relies on behaviour the "
    "CONTRACT excludes, misinterprets the return value or its boundary case, passes arguments in "
    "the wrong order or units). The misuse must be a plausible mistake, not an obvious one, and "
    "must make the pipeline raise or return a different result than the task's correct answer "
    "when the callee itself is correct. expected_repr is what the downstream task should "
    "correctly produce. State the violated clause in violation."
)


def callee_function_name(code: str) -> str:
    tree = ast.parse(code)
    return next(n.name for n in tree.body if isinstance(n, ast.FunctionDef))


def build_caller_prompt(record: Dict, aim: Dict, mode: str, previous_error: Optional[str] = None) -> str:
    callee_fn = callee_function_name(record["clean_code"])
    bug_note = ""
    if mode == "correct":
        bug_note = (f"NOTE (the alternative version and what differs; never mention this in your output):\n"
                    f"```python\n{record['buggy_code']}\n```\n{record['bug_rationale']}\n")
    previous = f"\nYour previous attempt was rejected: {previous_error}\nProduce a different caller that avoids this.\n" if previous_error else ""
    return TEMPLATE.format(
        mode_block=MODE_CORRECT if mode == "correct" else MODE_VIOLATING,
        aim_text=aim["text"], contract=aim["contract"], clean_code=record["clean_code"],
        bug_note_block=bug_note, callee_fn=callee_fn, previous_block=previous,
    )


class _Try(ast.NodeVisitor):
    def __init__(self, callee_fn):
        self.callee_fn = callee_fn; self.calls = 0; self.call_in_try = False; self._depth = 0
    def visit_Try(self, node):
        self._depth += 1; self.generic_visit(node); self._depth -= 1
    visit_TryStar = visit_Try
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == self.callee_fn:
            self.calls += 1
            if self._depth: self.call_in_try = True
        self.generic_visit(node)


def static_checks(caller: Dict, callee_fn: str) -> None:
    code = caller["code"]
    try:
        validate_code(code)
    except ValidationError as exc:
        raise ElicitationError(f"caller failed code validation: {exc}")
    tree = ast.parse(code)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
    if fn.name != caller["function_name"]:
        raise ElicitationError(f"function_name {caller['function_name']!r} does not match the defined {fn.name!r}")
    if fn.name == callee_fn:
        raise ElicitationError("caller must not reuse the callee's name")
    v = _Try(callee_fn); v.visit(tree)
    if v.calls == 0:
        raise ElicitationError(f"caller never calls {callee_fn}")
    if v.call_in_try:
        raise ElicitationError(f"the call to {callee_fn} is wrapped in try/except")
    for field in ("code", "purpose", "violation"):
        m = LEAK_WORDS.search(caller.get(field, "") or "")
        if m:
            raise ElicitationError(f"leak word {m.group(0)!r} in {field}")
    if not caller["entry_call"].strip() or fn.name not in caller["entry_call"]:
        raise ElicitationError("entry_call must call the caller")


def validate_runs(mode: str, record: Dict, caller: Dict) -> Dict[str, RunResult]:
    """Returns the sandbox runs this caller is responsible for; raises ElicitationError on a miss."""
    entry, expected = caller["entry_call"], caller["expected_repr"]
    if mode == "correct":
        ok_run = run(record["clean_code"], caller["code"], entry, expected)
        if ok_run.outcome != "ok":
            raise ElicitationError(f"clean callee + caller did not pass: outcome={ok_run.outcome} "
                                   f"exc={ok_run.exc_type}: {ok_run.exc_message} got={ok_run.result_repr!r} expected={expected!r}")
        bad_run = run(record["buggy_code"], caller["code"], entry, expected)
        if bad_run.outcome not in ("exception", "wrong_result"):
            raise ElicitationError(f"alternative callee + caller still passed (outcome={bad_run.outcome}); choose inputs that expose the difference")
        return {"none": ok_run, "callee": bad_run}
    bad_run = run(record["clean_code"], caller["code"], entry, expected)
    if bad_run.outcome not in ("exception", "wrong_result"):
        raise ElicitationError(f"clean callee + violating caller did not fail (outcome={bad_run.outcome})")
    if bad_run.exc_type in BROKEN_EXC_TYPES:
        raise ElicitationError(f"caller is broken rather than violating: {bad_run.exc_type}: {bad_run.exc_message}")
    return {"caller": bad_run}


def generate_caller(client: JudgeClient, record: Dict, aim: Dict, mode: str, max_retries: int = 4) -> Dict:
    callee_fn = callee_function_name(record["clean_code"])
    last = None
    for attempt in range(max_retries):
        prompt = build_caller_prompt(record, aim, mode, last)
        try:
            resp = _ask_with_deadline(client, prompt, CALLER_SCHEMA)
            caller = {k: (resp.data.get(k) or "") for k in CALLER_SCHEMA["properties"]}
            static_checks(caller, callee_fn)
            runs = validate_runs(mode, record, caller)
            return {**caller, "mode": mode, "callee_function_name": callee_fn,
                    "generation_model": resp.model, "prompt_version": PROMPT_VERSION,
                    "attempts": attempt + 1, "runs": {k: v.to_dict() for k, v in runs.items()}}
        except RETRYABLE as exc:
            last = f"{type(exc).__name__}: {exc}"
    raise RuntimeError(f"{mode} caller failed after {max_retries} attempts: {last}")
