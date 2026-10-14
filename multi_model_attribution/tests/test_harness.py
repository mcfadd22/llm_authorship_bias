from multi_model_attribution.harness import assemble, failure_kind, layout, parse_traceback, run

CLEAN = "def compute_average(values):\n    if not values:\n        return None\n    total = 0\n    for v in values:\n        total += v\n    return total / len(values)"
BUGGY = "def compute_average(values):\n    if not values:\n        return None\n    total = 0\n    for v in values:\n        total += v\n    return total"
CALLER = "def report_average(values):\n    avg = compute_average(values)\n    return round(avg * 2, 1)"
ENTRY = "report_average([2, 4, 9])"


def test_assemble_and_layout():
    mod = assemble(CLEAN, CALLER, ENTRY)
    lay = layout(CLEAN, CALLER)
    lines = mod.splitlines()
    assert lines[lay["callee_start"] - 1].startswith("def compute_average")
    assert lines[lay["caller_start"] - 1].startswith("def report_average")
    assert lines[lay["harness_start"] - 1].startswith("if __name__")
    assert lay["callee_end"] == 7 and lay["caller_start"] == 9 and lay["caller_end"] == 11


def test_clean_correct_is_ok():
    r = run(CLEAN, CALLER, ENTRY, "10.0")
    assert r.outcome == "ok" and r.result_repr == "10.0"
    assert failure_kind(r) is None


def test_buggy_correct_is_wrong_result():
    r = run(BUGGY, CALLER, ENTRY, "10.0")
    assert r.outcome == "wrong_result" and r.result_repr == "30"
    assert failure_kind(r) == "wrong_result"


def test_exception_in_callee_frame_maps_lines():
    callee = "def compute_average(values):\n    total = 0\n    for v in values:\n        total += v\n    return total / len(values)"
    r = run(callee, CALLER, "report_average([])", "0")
    assert r.outcome == "exception" and r.exc_type == "ZeroDivisionError"
    comps = [f.component for f in r.frames]
    assert comps == ["harness", "caller", "callee"]
    callee_frame = r.frames[-1]
    assert callee_frame.lineno_component == 5 and callee_frame.lineno_assembled == 5
    assert "len(values)" in callee_frame.line
    caller_frame = r.frames[1]
    assert caller_frame.lineno_component == 2 and caller_frame.function == "report_average"
    assert failure_kind(r) == "exception_in_callee"


def test_exception_in_caller_frame():
    r = run(CLEAN, CALLER, "report_average([])", "0")   # avg is None -> None * 2 in the caller
    assert r.outcome == "exception" and r.exc_type == "TypeError"
    assert r.frames[-1].component == "caller"
    assert failure_kind(r) == "exception_in_caller"


def test_timeout():
    r = run(CLEAN, "def report_average(values):\n    while True:\n        pass\n    return 1", ENTRY, "1", timeout_s=1.0)
    assert r.outcome == "timeout"


def test_stdlib_frames_are_collapsed():
    caller = "import json\ndef report_average(values):\n    return json.loads(compute_average(values))"
    r = run(CLEAN, caller, "report_average([1])", "x")
    assert r.outcome == "exception"
    assert r.stdlib_frames_omitted >= 1
    assert all(f.component in ("harness", "caller", "callee") for f in r.frames)


def test_parse_traceback_handles_bare_exception_line():
    lay = layout(CLEAN, CALLER)
    parsed = parse_traceback('Traceback (most recent call last):\n  File "pipeline.py", line 10, in report_average\n    x\nKeyboardInterrupt\n', lay)
    assert parsed["exc_type"] == "KeyboardInterrupt" and parsed["exc_message"] == ""
    assert parsed["frames"][0].component == "caller"
