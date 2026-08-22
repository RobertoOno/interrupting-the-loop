"""Run a candidate construction program in an isolated subprocess and verify it.

The candidate defines `construct(n)` (or a problem-specific entry point); the
runner imports the problem's verifier, calls the entry point under a timeout, and
prints a JSON verdict. Used by scripts/frontier_search.py for every problem."""
from __future__ import annotations
import json, subprocess, sys, tempfile, textwrap
from pathlib import Path

RUNNER = textwrap.dedent('''
import json, sys, math, signal, resource
sys.path.insert(0, {src!r})
def _alarm(*a): raise TimeoutError("time limit")
signal.signal(signal.SIGALRM, _alarm); signal.alarm({timeout})
try:
    resource.setrlimit(resource.RLIMIT_AS, ({mem}, {mem}))
except Exception:
    pass
ns = {{}}
try:
    exec(compile(open({code_path!r}).read(), "candidate", "exec"), ns)
    from creative_machine.domains import {module} as dom
    out = ns[{entry!r}](*{args!r})
    res = dom.verify(out, *{args!r})
    try:
        import hashlib
        def _r(o):
            if isinstance(o, float): return round(o, 6)
            if isinstance(o, (list, tuple)): return [_r(x) for x in o]
            try:
                import numpy as _np
                if isinstance(o, _np.ndarray): return _r(o.tolist())
                if isinstance(o, (_np.floating,)): return round(float(o), 6)
                if isinstance(o, (_np.integer,)): return int(o)
            except Exception:
                pass
            return o
        res["sig"] = hashlib.md5(repr(_r(out)).encode()).hexdigest()[:12]
    except Exception:
        pass
except BaseException as e:
    res = {{"ok": False, "error": type(e).__name__ + ": " + str(e)[:200]}}
print(json.dumps(res))
''')

def run_candidate(code: str, module: str, entry: str, args: tuple, timeout_s: int = 20, mem_bytes: int = 2 * 1024**3) -> dict:
    if f"def {entry}(" not in code:
        return {"ok": False, "error": f"no `def {entry}(` in candidate"}
    src = str(Path(__file__).resolve().parent.parent)
    with tempfile.TemporaryDirectory() as td:
        cp = Path(td) / "cand.py"; cp.write_text(code)
        rp = Path(td) / "run.py"
        rp.write_text(RUNNER.format(src=src, timeout=int(timeout_s), mem=int(mem_bytes), code_path=str(cp), module=module, entry=entry, args=args))
        try:
            proc = subprocess.run([sys.executable, "-I", str(rp)], capture_output=True, text=True, timeout=timeout_s + 5)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "hard timeout"}
        line = (proc.stdout.strip().splitlines() or [""])[-1]
        try:
            return json.loads(line)
        except Exception:
            return {"ok": False, "error": "no verdict: " + (proc.stderr.strip()[-200:] or line[:200])}
