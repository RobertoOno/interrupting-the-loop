"""Run generated heuristic code in an isolated subprocess with a timeout.

Generated code defines ``priority(item, remaining)``; the runner script
evaluates it on JSON-passed instances inside ``python -I`` (isolated mode)
and reports the verifier's verdict as JSON on the last stdout line. Loops
that never end hit the timeout; crashes come back as errors — either way
the candidate simply dies in the funnel.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

_RUNNER = """
import json, math, random, sys
sys.path.insert(0, {src_path!r})
from creative_machine.domains import binpack

{code}

instances = json.loads({instances_json!r})
res = binpack.evaluate(priority, instances)
res["excesses"] = [(binpack.simulate(priority, it) - binpack.lower_bound(it)) / binpack.lower_bound(it) for it in instances]
print(json.dumps(res))
"""


def run_heuristic_code(code: str, instances: list[list[float]], timeout_s: float = 10.0) -> dict:
    """Evaluate one generated heuristic. Returns {ok, mean_excess, total_bins} or {ok: False, error}."""
    if "def priority(" not in code:
        return {"ok": False, "error": "no priority() definition"}
    src_path = str(Path(__file__).resolve().parent.parent)
    script = _RUNNER.format(src_path=src_path, code=code, instances_json=json.dumps(instances))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "candidate.py"
        path.write_text(script)
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(path)],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                cwd=tmp,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"timeout after {timeout_s}s"}
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip().splitlines()[-1][:200] if proc.stderr else "crashed"}
    try:
        out = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"ok": False, "error": f"unparseable output: {proc.stdout[:120]!r}"}
    return {"ok": True, **out}
