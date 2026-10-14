"""Assemble a callee + caller into one module, run it in a subprocess, and parse the outcome.

Line numbers: the callee occupies lines 1..n, one blank line, then the caller, one blank
line, then the entry block. Component-local line numbers are assembled numbers minus the
component's offset, so a rendered per-step trace maps exactly onto the per-step code.
"""
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

MODULE_NAME = "pipeline.py"
RESULT_MARKER = "__RESULT__ "
HARNESS_VERSION = "2026-10-13-v1"
BROKEN_EXC_TYPES = {"SyntaxError", "NameError", "ImportError", "ModuleNotFoundError", "IndentationError", "RecursionError"}
_FRAME_RE = re.compile(r'^  File "(?P<file>.+)", line (?P<line>\d+), in (?P<func>.+)$')


@dataclass
class Frame:
    component: str          # callee | caller | harness
    function: str
    lineno_component: int
    lineno_assembled: int
    line: str


@dataclass
class RunResult:
    outcome: str            # ok | wrong_result | exception | timeout
    expected_repr: str
    result_repr: Optional[str] = None
    exc_type: Optional[str] = None
    exc_message: Optional[str] = None
    frames: List[Frame] = field(default_factory=list)
    stdlib_frames_omitted: int = 0
    stdout: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


def assemble(callee_code: str, caller_code: str, entry_call: str) -> str:
    callee = callee_code.rstrip("\n")
    caller = caller_code.rstrip("\n")
    return (f"{callee}\n\n{caller}\n\n"
            f"if __name__ == \"__main__\":\n    print({RESULT_MARKER!r} + repr({entry_call}))\n")


def layout(callee_code: str, caller_code: str) -> Dict[str, int]:
    """First/last assembled line of each component."""
    n_callee = len(callee_code.rstrip("\n").splitlines())
    n_caller = len(caller_code.rstrip("\n").splitlines())
    return {"callee_start": 1, "callee_end": n_callee,
            "caller_start": n_callee + 2, "caller_end": n_callee + 1 + n_caller,
            "harness_start": n_callee + n_caller + 3}


def _component_of(lineno: int, lay: Dict[str, int]) -> str:
    if lay["callee_start"] <= lineno <= lay["callee_end"]:
        return "callee"
    if lay["caller_start"] <= lineno <= lay["caller_end"]:
        return "caller"
    return "harness"


def parse_traceback(stderr: str, lay: Dict[str, int]) -> Dict:
    lines = stderr.rstrip("\n").splitlines()
    frames: List[Frame] = []
    omitted = 0
    i = 0
    while i < len(lines):
        m = _FRAME_RE.match(lines[i])
        if m:
            src = lines[i + 1].strip() if i + 1 < len(lines) and lines[i + 1].startswith("    ") else ""
            if os.path.basename(m["file"]) == MODULE_NAME:
                n = int(m["line"]); comp = _component_of(n, lay)
                local = n - {"callee": lay["callee_start"], "caller": lay["caller_start"], "harness": lay["harness_start"]}[comp] + 1
                frames.append(Frame(comp, m["func"], local, n, src))
            else:
                omitted += 1
            i += 2 if src else 1
            continue
        i += 1
    exc_type = exc_message = None
    for line in reversed(lines):
        if line and not line.startswith(" ") and not line.startswith("Traceback") and not line.startswith("During handling"):
            if ":" in line:
                exc_type, exc_message = line.split(":", 1)
                exc_type, exc_message = exc_type.strip(), exc_message.strip()
            else:
                exc_type, exc_message = line.strip(), ""
            break
    return {"frames": frames, "stdlib_frames_omitted": omitted, "exc_type": exc_type, "exc_message": exc_message}


def run(callee_code: str, caller_code: str, entry_call: str, expected_repr: str,
        timeout_s: float = 5.0, python: Optional[str] = None) -> RunResult:
    module = assemble(callee_code, caller_code, entry_call)
    lay = layout(callee_code, caller_code)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, MODULE_NAME)
        with open(path, "w") as f:
            f.write(module)
        try:
            proc = subprocess.run(
                [python or sys.executable, "-s", "-B", MODULE_NAME],
                cwd=d, capture_output=True, text=True, timeout=timeout_s,
                env={"PYTHONHASHSEED": "0", "PATH": os.environ.get("PATH", "")},
            )
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or b"")
            return RunResult("timeout", expected_repr, stdout=out.decode() if isinstance(out, bytes) else str(out))
    stdout = proc.stdout
    if proc.returncode == 0:
        marker = [l for l in stdout.splitlines() if l.startswith(RESULT_MARKER)]
        if not marker:
            return RunResult("exception", expected_repr, exc_type="NoResult", exc_message="no result marker", stdout=stdout[-2000:])
        got = marker[-1][len(RESULT_MARKER):]
        return RunResult("ok" if got == expected_repr else "wrong_result", expected_repr, result_repr=got,
                         stdout="\n".join(l for l in stdout.splitlines() if not l.startswith(RESULT_MARKER))[-2000:])
    parsed = parse_traceback(proc.stderr, lay)
    return RunResult("exception", expected_repr, exc_type=parsed["exc_type"], exc_message=parsed["exc_message"],
                     frames=parsed["frames"], stdlib_frames_omitted=parsed["stdlib_frames_omitted"], stdout=stdout[-2000:])


def failure_kind(result: RunResult) -> Optional[str]:
    """Where the failure is visible: exception raised in a callee frame, in a caller frame, or a wrong result."""
    if result.outcome == "wrong_result":
        return "wrong_result"
    if result.outcome == "exception":
        comps = [f.component for f in result.frames if f.component != "harness"]
        if not comps:
            return "exception_in_harness"
        return "exception_in_callee" if comps[-1] == "callee" else "exception_in_caller"
    return None
