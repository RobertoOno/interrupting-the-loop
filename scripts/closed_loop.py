#!/usr/bin/env python3
"""Battery L — the closed loop: verified search feeds weight consolidation, which feeds
search again. Two subcommands, no LLM judge anywhere (the exact verifier is the only reader).

  select  --run DIR --problem P --mode finds|random --k K --sft DIR [--seed S]
          Build the SFT jsonl from a session-1 run: prompt = the bare problem prompt the
          harness would send (no elites, chat-templated when --chat-model is given),
          completion = the candidate program in a ```python block. Records the training
          signatures in sigs.json so the tail metric can exclude memorized programs.

  tails   --problem P --pool DIR --run DIR [--sft DIR]
          Tail metrics of a session-2 run against the session-1 pool: share of valid,
          distinct, non-memorized candidates above the pool's p90 and above its best.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
from frontier_search import PROBLEMS, build_prompt


def seed_score(P):
    from creative_machine.frontier_exec import run_candidate
    return run_candidate(P["seed_program"], P["module"], P["entry"], P["args"])["score"]


def rows(run: Path):
    f = run / "history.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()]


def cand_frac(P, s0, score):
    sgn = 1 if P["maximize"] else -1
    return (sgn * (score - s0)) / max(1e-12, sgn * (P["best_known"] - s0))


def valid_distinct(rs):
    """Valid candidates, first occurrence per behaviour signature, in run order."""
    seen, out = set(), []
    for r in rs:
        if not r.get("ok"):
            continue
        sig = r.get("sig", "")
        if sig in seen:
            continue
        seen.add(sig); out.append(r)
    return out


def user_message(P):
    """The bare prompt (no elites) the harness sends for this problem."""
    prompt = build_prompt(P, [], "verbatim")
    return (prompt.rsplit(f"def {P['entry']}(", 1)[0].rstrip() + "\n\n"
            f"Write the improved version now: a complete, self-contained Python program defining "
            f"`def {P['entry']}(...)` (plus any helpers/imports it needs), returning the construction. "
            f"Reply with ONE ```python code block and nothing else.")


def cmd_select(a):
    P = PROBLEMS[a.problem]; s0 = seed_score(P)
    rs = rows(Path(a.run))
    cands = [r for r in valid_distinct(rs) if r.get("code")]
    if not cands:
        sys.exit(f"no valid candidates with logged code in {a.run}")
    sgn = 1 if P["maximize"] else -1
    if a.mode == "finds":
        cands.sort(key=lambda r: sgn * r["score"], reverse=True)
        chosen = cands[:a.k]
    else:
        rng = np.random.default_rng(a.seed)
        idx = rng.choice(len(cands), size=min(a.k, len(cands)), replace=False)
        chosen = [cands[i] for i in sorted(idx)]

    prompt = user_message(P)
    if a.chat_model != "none":
        from mlx_lm.utils import load_tokenizer
        tok = load_tokenizer(Path(a.chat_model).expanduser())
        prompt = tok.apply_chat_template([{"role": "user", "content": prompt}],
                                         tokenize=False, add_generation_prompt=True)
    out = Path(a.sft); out.mkdir(parents=True, exist_ok=True)
    with open(out / "train.jsonl", "w") as f:
        for c in chosen:
            f.write(json.dumps({"prompt": prompt,
                                "completion": "```python\n" + c["code"].rstrip() + "\n```\n"}) + "\n")
    (out / "sigs.json").write_text(json.dumps({
        "problem": a.problem, "mode": a.mode, "k": len(chosen), "run": str(a.run),
        "sigs": [c.get("sig", "") for c in chosen],
        "fracs": [cand_frac(P, s0, c["score"]) for c in chosen]}, indent=1))
    fr = [cand_frac(P, s0, c["score"]) for c in chosen]
    print(f"{a.problem} {a.mode}: {len(chosen)} programs, frac {min(fr):.3f}..{max(fr):.3f} -> {out}/train.jsonl")


def cmd_tails(a):
    P = PROBLEMS[a.problem]; s0 = seed_score(P)
    pool = [cand_frac(P, s0, r["score"]) for r in valid_distinct(rows(Path(a.pool)))]
    if not pool:
        sys.exit(f"empty pool in {a.pool}")
    p90, pbest = float(np.percentile(pool, 90)), float(np.max(pool))

    trained = set()
    if a.sft and a.sft != "none":
        trained = set(json.loads((Path(a.sft) / "sigs.json").read_text())["sigs"])

    rs = rows(Path(a.run))
    vd = valid_distinct(rs)
    fresh = [r for r in vd if r.get("sig", "") not in trained]
    fr = [cand_frac(P, s0, r["score"]) for r in fresh]
    n_ok = sum(1 for r in rs if r.get("ok"))
    m = {"problem": a.problem, "run": Path(a.run).name, "samples": len(rs),
         "valid": n_ok / max(1, len(rs)), "distinct": len(vd), "fresh": len(fresh),
         "echo": (len(vd) - len(fresh)) / max(1, len(vd)),
         "tail_p90": float(np.mean([f > p90 for f in fr])) if fr else 0.0,
         "tail_best": float(np.mean([f > pbest for f in fr])) if fr else 0.0,
         "div": len(vd) / max(1, n_ok),
         "mean_frac": float(np.mean(fr)) if fr else 0.0,
         "best_frac": float(np.max(fr)) if fr else 0.0,
         "pool_p90": p90, "pool_best": pbest}
    print(json.dumps(m))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("select")
    s.add_argument("--run", required=True); s.add_argument("--problem", required=True, choices=sorted(PROBLEMS))
    s.add_argument("--mode", choices=["finds", "random"], required=True); s.add_argument("--k", type=int, default=40)
    s.add_argument("--sft", required=True); s.add_argument("--seed", type=int, default=0)
    s.add_argument("--chat-model", default="none", help="tokenizer path for chat templating (tokenizer only, no weights)")
    t = sp.add_parser("tails")
    t.add_argument("--problem", required=True, choices=sorted(PROBLEMS))
    t.add_argument("--pool", required=True); t.add_argument("--run", required=True); t.add_argument("--sft", default="none")
    a = ap.parse_args()
    (cmd_select if a.cmd == "select" else cmd_tails)(a)
