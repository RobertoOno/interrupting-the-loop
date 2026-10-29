#!/usr/bin/env python3
"""Programa 2, stage 1 — the correspondence engine (pre-registered PLANO 2026-09-03).
For every library entry (a verified construction for ANOTHER problem) produce a
transplant for the target problem under one of three arms:
  D  : structural correspondence — the model sees the target statement, the source
       statement and the source code; writes what the family exploits, the mapping,
       and a program for the target.
  C2 : syntactic port (sham) — same model, NO target statement: convert the program
       to the target's output contract, preserving the computation; no objective.
  C1 : mechanical port (sham, no LLM) — run the source program and map its numbers
       onto the target's object with a fixed rule.
  D0 : target-only control (added after the single read of S1, before stage 2): the
       model sees the target statement and NO source; it writes its own construction.
       Separates "transfer from the source" from "the model's own prior on the target".
Every transplant goes through the exact verifier (creative_machine.frontier_exec)
and, for sumdiff3, the family classifier (family_sumdiff3.features). One JSONL row
per (entry, attempt): runs/p2/<out>/<arm>_<model>.jsonl.

    PYTHONPATH=src python scripts/transfer_correspond.py --target sumdiff3 --arm D --model kimi --attempts 2 --out stage1
    PYTHONPATH=src AWS_PROFILE=main-account python scripts/transfer_correspond.py --target sumdiff3 --arm D --model opus ...
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("fs", ROOT / "scripts/frontier_search.py")
fs = importlib.util.module_from_spec(spec); spec.loader.exec_module(fs)
PROBLEMS, extract_program = fs.PROBLEMS, fs.extract_program
from creative_machine.frontier_exec import run_candidate  # noqa: E402

CONTRACT = {  # target -> (entry signature, output contract in words)
    "sumdiff3": ("construct()", "a Python list of DISTINCT non-negative integers containing 0, at most 4000 elements"),
    "isofree64": ("construct(n)", "a Python list of distinct (x, y) integer tuples with 0 <= x, y < n (n = 64)"),
    "beatavg": ("construct(L)", "a Python list of L non-negative floats (a pmf on {0..L-1}; the verifier normalizes it)"),
    "autocorr1": ("construct()", "a Python list of 300..5000 non-negative floats (step heights)"),
}
SYSTEM = ("You are an expert in extremal combinatorics, additive number theory and mathematical constructions, "
          "and you write short, correct, self-contained Python programs. Write programs directly, without step-by-step "
          "derivations inside comments; the code block must be complete.")
MODELS = {"opus": ("bedrock", "anthropic.claude-opus-5"), "kimi": ("openrouter", "moonshotai/kimi-k2.6")}
RUNNER = r'''
import sys, json, resource
try:
    resource.setrlimit(resource.RLIMIT_AS, (8 << 30, 8 << 30))
except Exception:
    pass
src = open(sys.argv[1]).read(); g = {}
exec(compile(src, sys.argv[1], "exec"), g)
args = json.loads(sys.argv[2]); out = g[sys.argv[3]](*args)
def flat(o):
    if isinstance(o, (int, float)) and not isinstance(o, bool): yield float(o)
    elif isinstance(o, (list, tuple, set)):
        for x in o: yield from flat(x)
    else:
        try:
            import numpy as np
            for x in np.asarray(o, dtype=float).ravel(): yield float(x)
        except Exception:
            pass
json.dump([x for x in flat(out) if x == x and abs(x) < 1e15], open(sys.argv[4], "w"))
'''


def load_library(lib: Path, target: str) -> list[dict]:
    entries = []
    for row in json.loads((lib / "index.json").read_text()):
        if row["problem"] == target or row["problem"].startswith(target):
            continue
        text = (ROOT / row["file"]).read_text().split("\n")
        code = "\n".join(l for l in text if not l.startswith("# transfer-library entry") and not l.startswith("# statement:"))
        P = PROBLEMS[row["problem"]]
        entries.append({"entry": row["file"], "source_problem": row["problem"], "source_statement": P["statement"],
                        "source_entry": P["entry"], "source_args": list(P["args"]), "code": code.strip() + "\n"})
    for f in sorted((lib / "classical").glob("*.py")):
        lines = f.read_text().split("\n")
        head = next((l for l in lines if l.startswith("# transfer-library entry")), "")
        stmt = next((l[len("# statement:"):].strip() for l in lines if l.startswith("# statement:")), "")
        prob = re.search(r"problem: ([^|]+)", head); fam = re.search(r"classical family: (.+)$", head)
        code = "\n".join(l for l in lines if not l.startswith("# transfer-library entry") and not l.startswith("# statement:") and not l.startswith("# reference:"))
        entries.append({"entry": f.relative_to(ROOT).as_posix(), "source_problem": (prob.group(1).strip() if prob else f.stem) + (f" [{fam.group(1).strip()}]" if fam else ""),
                        "source_statement": stmt, "source_entry": "construct", "source_args": [], "code": code.strip() + "\n"})
    return entries


def prompt_D(target: str, e: dict, timeout: int) -> str:
    sig, contract = CONTRACT[target]
    return (f"TARGET PROBLEM:\n{PROBLEMS[target]['statement']}\n\n"
            f"SOURCE PROBLEM (a different problem):\n{e['source_statement']}\n\n"
            f"SOURCE CONSTRUCTION (a verified program for the source problem):\n```python\n{e['code']}```\n\n"
            "Your task is STRUCTURAL TRANSFER from the source to the target. Answer in three parts.\n"
            "1. WHAT THE SOURCE FAMILY EXPLOITS: the structural idea behind this construction (2-4 sentences).\n"
            "2. CORRESPONDENCE: for the target's object, constraint and objective, say what plays its role in the source "
            "(and what has no counterpart). Be concrete about what maps to what.\n"
            f"3. TRANSPLANT: a complete, self-contained Python program for the TARGET that implements the source's idea in the "
            f"target's terms. It must define `def {sig}` returning {contract}. numpy and scipy are available; deterministic; "
            f"it must finish in under {timeout} seconds. Put the program in ONE ```python block.")


def prompt_D0(target: str, timeout: int) -> str:
    sig, contract = CONTRACT[target]
    return (f"TARGET PROBLEM:\n{PROBLEMS[target]['statement']}\n\n"
            "Write the best construction you can for this problem. First state the structural idea in 2-4 sentences, "
            f"then give a complete, self-contained Python program defining `def {sig}` returning {contract}. numpy and scipy "
            f"are available; deterministic; it must finish in under {timeout} seconds. Put the program in ONE ```python block.")


def prompt_C2(target: str, e: dict, timeout: int) -> str:
    sig, contract = CONTRACT[target]
    return (f"Convert the following Python program into a function `def {sig}` that returns {contract}.\n"
            "Preserve the program's computation as literally as possible: keep its structure, parameters and loops; only adapt "
            "the output type and range so that the contract is met (for example: take absolute values, round to integers, "
            "remove duplicates, include 0, cap the size). Do NOT redesign it and do NOT optimize it for any objective; there "
            f"is no objective here. numpy and scipy are available; deterministic; under {timeout} seconds. Reply with ONE "
            f"```python block.\n\n```python\n{e['code']}```")


def mechanical(target: str, e: dict, timeout: int) -> str | None:
    """C1: run the source, flatten its numbers, map onto the target object with a fixed rule; return a program."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        cp = Path(td) / "src.py"; cp.write_text(e["code"]); op = Path(td) / "out.json"
        try:
            subprocess.run([sys.executable, "-c", RUNNER, str(cp), json.dumps(e["source_args"]), e["source_entry"], str(op)],
                           check=True, timeout=timeout + 10, capture_output=True)
            nums = json.load(open(op))
        except Exception:
            return None
    if not nums:
        return None
    if target == "sumdiff3":
        vals = sorted({int(round(abs(x))) for x in nums} | {0})
        if len(vals) < 2:
            return None
        if vals[-1] < 50:  # scale tiny ranges (pmfs, unit-box coordinates) onto integers
            vals = sorted({int(round(abs(x) * 1000)) for x in nums} | {0})
        vals = vals[:4000]
        return f"def construct():\n    return {vals}\n"
    if target == "isofree64":
        pts = sorted({(int(round(abs(nums[i]))) % 64, int(round(abs(nums[i + 1]))) % 64) for i in range(0, len(nums) - 1, 2)})
        return f"def construct(n):\n    return {pts}\n"
    return None


def get_object(code: str, entry: str, args: list, timeout: int):
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        cp = Path(td) / "c.py"; cp.write_text(code); op = Path(td) / "o.json"
        try:
            subprocess.run([sys.executable, "-c", RUNNER, str(cp), json.dumps(args), entry, str(op)], check=True, timeout=timeout + 10, capture_output=True)
            return json.load(open(op))
        except Exception:
            return None


def classify(target: str, code: str, timeout: int) -> dict:
    if target != "sumdiff3":
        return {}
    from family_sumdiff3 import features
    nums = get_object(code, "construct", [], timeout)
    if not nums:
        return {}
    U = sorted({int(round(x)) for x in nums})
    if len(U) > 4000 or len(U) < 2:
        return {}
    f = features(U)
    # F_rec needs a non-trivial set: tiny sets satisfy the carry-free digit test vacuously (smoke, 2026-09-03)
    f["family"] = "F0" if f["frac_pow2_sums_le3"] >= 0.8 else ("F_rec" if (f["carry_free_base"] and f["n"] >= 50) else "other")
    return f


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="sumdiff3", choices=sorted(CONTRACT))
    ap.add_argument("--library", default="docs/transfer_library")
    ap.add_argument("--arm", required=True, choices=["D", "C2", "C1", "D0"])
    ap.add_argument("--model", default="none", choices=["opus", "kimi", "none"])
    ap.add_argument("--attempts", type=int, default=1)
    ap.add_argument("--effort", default="high")
    ap.add_argument("--max-tokens", type=int, default=4000)
    ap.add_argument("--verify-timeout", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0, help="first N entries only (smoke)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    P = PROBLEMS[a.target]
    entries = load_library(ROOT / a.library, a.target)
    if a.limit:
        entries = entries[: a.limit]
    out = ROOT / "runs/p2" / a.out; out.mkdir(parents=True, exist_ok=True)
    fn = out / f"{a.arm}_{a.model}.jsonl"
    done = set()
    if fn.exists():
        for l in fn.read_text().splitlines():
            r = json.loads(l); done.add((r["entry"], r["attempt"]))
    client = None
    if a.arm in ("D", "C2", "D0"):
        kind, model_id = MODELS[a.model]
        if kind == "bedrock":
            from creative_machine.blend import BedrockClient
            client = BedrockClient(effort=a.effort)
        else:
            from creative_machine.blend import OpenRouterClient
            client = OpenRouterClient()
    else:
        model_id = "none"

    def one(e: dict, attempt: int) -> dict:
        row = {"entry": e["entry"], "source_problem": e["source_problem"], "arm": a.arm, "model": a.model, "attempt": attempt, "t": time.time()}
        if a.arm == "C1":
            code, reply = mechanical(a.target, e, a.verify_timeout), ""
        else:
            prompt = (prompt_D(a.target, e, a.verify_timeout) if a.arm == "D" else prompt_D0(a.target, a.verify_timeout) if a.arm == "D0"
                      else prompt_C2(a.target, e, a.verify_timeout))
            try:
                reply = client.chat(model_id, SYSTEM, prompt, max_tokens=a.max_tokens)
            except Exception as exc:  # noqa: BLE001
                reply = f"(api error: {str(exc)[:160]})"
            code = extract_program(reply, P["entry"])
            row["prompt_chars"] = len(prompt)
        row["reply"] = reply; row["code"] = code
        if not code:
            row.update({"ok": False, "error": "no program"}); return row
        res = run_candidate(code, P["module"], P["entry"], P["args"], timeout_s=a.verify_timeout)
        row.update({"ok": bool(res.get("ok")), "score": res.get("score"), "sig": res.get("sig"), "error": res.get("error")})
        if row["ok"]:
            row.update(classify(a.target, code, a.verify_timeout))
        return row

    jobs = [(e, k) for e in entries for k in range(1, (a.attempts if a.arm != "C1" else 1) + 1) if (e["entry"], k) not in done]
    print(f"{a.arm}/{a.model}: {len(entries)} entries, {len(jobs)} jobs to run ({len(done)} done) -> {fn.relative_to(ROOT)}")
    n_ok = 0
    with fn.open("a") as f, ThreadPoolExecutor(max_workers=a.workers if a.arm != "C1" else 1) as ex:
        for row in ex.map(lambda j: one(*j), jobs):
            f.write(json.dumps(row) + "\n"); f.flush()
            n_ok += bool(row.get("ok"))
            print(f"  {row['entry'][-44:]:44s} a{row['attempt']} ok={row.get('ok')} score={row.get('score')} fam={row.get('family', '')} err={str(row.get('error', ''))[:50]}")
    if client is not None:
        print("usage:", client.usage)
    print(f"done: {n_ok}/{len(jobs)} valid")


if __name__ == "__main__":
    main()
