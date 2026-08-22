#!/usr/bin/env python3
"""Frontier search harness (phase 4): broad proposer + hard verifier + islands + novelty pressure.

A FunSearch-style loop at office scale, instrumented for the factorial we care about:
  proposer     : base model (MLX), T=1, min-p floor; optional adapter (--adapter)
  population   : K islands; each island keeps its top-M programs by score
  prompt       : problem statement + the island's best programs (code + score) + "write an improved version"
  novelty      : optional rejection of candidates whose score (rounded) already exists in the island (--novelty)
  verification : sandboxed run of `construct(...)`, problem verifier -> score
  logging      : every candidate (code hash, score, ok/error, generation, island, prompt_hash) -> history.jsonl
Problems are plugins in creative_machine.domains with `verify(out, *args)` and a statement in PROBLEMS below.

    python scripts/frontier_search.py --problem circlepack26 --gens 20 --samples 8 --islands 2 --out runs/frontier/cp26_base
"""
from __future__ import annotations
import argparse, hashlib, json, random, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from creative_machine.frontier_exec import run_candidate

PROBLEMS = {
    "circlepack26": {
        "module": "circlepack", "entry": "construct", "args": (26,), "maximize": True,
        "best_known": 2.635983,  # ShinkaEvolve 2025 (2.635983283); AlphaEvolve 2.63586276; pre-2025 Friedman 2012: 2.634
        "statement": (
            "Place n = 26 circles inside the unit square [0, 1] x [0, 1] so that no two circles overlap "
            "and every circle lies entirely inside the square, maximizing the SUM OF THE RADII. "
            "Write a Python function `construct(n)` that returns a list of n tuples (x, y, r) "
            "(center coordinates and radius). The verifier checks containment and non-overlap exactly "
            "(tolerance 1e-7) and scores the sum of radii. Use only the standard library and math; "
            "numpy is NOT available. Keep it deterministic and fast (< 10 s)."),
        "seed_program": (
            "def construct(n):\n    import math\n    k = math.ceil(math.sqrt(n)); r = 0.5 / k\n    out = []\n"
            "    for i in range(k):\n        for j in range(k):\n            if len(out) < n:\n"
            "                out.append((r + 2 * r * i, r + 2 * r * j, r))\n    return out\n"),
    },
}

def extract_program(text: str, entry: str) -> str | None:
    """First complete top-level `def entry(...)` block (closed by a dedented non-blank line or end)."""
    m = re.search(rf"^def {entry}\(.*?\):\s*$", text, re.M)
    if not m:
        return None
    lines = text[m.start():].splitlines()
    body = [lines[0]]
    for ln in lines[1:]:
        if ln.strip() == "" or ln.startswith((" ", "\t")):
            body.append(ln)
        else:
            break
    while body and body[-1].strip() == "":
        body.pop()
    return "\n".join(body) + "\n"

def build_prompt(P: dict, elites: list[dict]) -> str:
    parts = [f'"""{P["statement"]}"""\n']
    for i, e in enumerate(sorted(elites, key=lambda e: e["score"], reverse=P["maximize"])):
        parts.append(f"# Version {i} (score {e['score']:.6f}):\n{e['code'].replace('def ' + P['entry'], 'def ' + P['entry'] + '_v' + str(i))}\n")
    parts.append(f"# Improved version (higher score):\ndef {P['entry']}(")
    return "\n".join(parts)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--problem", choices=sorted(PROBLEMS), required=True)
    ap.add_argument("--model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit"); ap.add_argument("--adapter", default="none")
    ap.add_argument("--gens", type=int, default=10); ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--islands", type=int, default=2); ap.add_argument("--elites", type=int, default=3)
    ap.add_argument("--novelty", action="store_true", help="reject candidates whose rounded score already exists in the island")
    ap.add_argument("--max-tokens", type=int, default=700); ap.add_argument("--temp", type=float, default=1.0); ap.add_argument("--min-p", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    P = PROBLEMS[a.problem]
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    model, tok = load(str(Path(a.model).expanduser()), adapter_path=(None if a.adapter == "none" else a.adapter))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    hist = out / "history.jsonl"; state_p = out / "state.json"
    rng = random.Random(a.seed)
    seed_res = run_candidate(P["seed_program"], P["module"], P["entry"], P["args"])
    islands = [[{"code": P["seed_program"], "score": seed_res["score"], "hash": "seed"}] for _ in range(a.islands)]
    gen0 = 0
    if state_p.exists():
        st = json.loads(state_p.read_text()); islands = st["islands"]; gen0 = st["gen"] + 1
    best = max(e["score"] for isl in islands for e in isl)
    print(f"{a.problem}: seed score {seed_res['score']:.4f}; best known {P['best_known']}; resume at gen {gen0}", flush=True)
    sampler = make_sampler(temp=a.temp, min_p=a.min_p)
    for g in range(gen0, a.gens):
        t0 = time.time(); n_ok = n_new = 0
        for k, isl in enumerate(islands):
            elites = sorted(isl, key=lambda e: e["score"], reverse=P["maximize"])[: a.elites]
            prompt = build_prompt(P, elites)
            ph = hashlib.md5(prompt.encode()).hexdigest()[:10]
            seen_scores = {round(e["score"], 6) for e in isl}
            for s in range(a.samples):
                text = "".join(o.text for o in stream_generate(model, tok, prompt, max_tokens=a.max_tokens, sampler=sampler))
                code = extract_program(f"def {P['entry']}(" + text, P["entry"])
                rec = {"gen": g, "island": k, "sample": s, "prompt": ph, "ok": False}
                if code is None:
                    rec["error"] = "no function"
                else:
                    h = hashlib.md5(re.sub(r"\s+", " ", code).encode()).hexdigest()[:12]
                    rec["hash"] = h
                    res = run_candidate(code, P["module"], P["entry"], P["args"])
                    rec["ok"] = bool(res.get("ok"))
                    if res.get("ok"):
                        sc = float(res["score"]); rec["score"] = sc; n_ok += 1
                        dup = round(sc, 6) in seen_scores
                        rec["novel_score"] = not dup
                        if not (a.novelty and dup):
                            isl.append({"code": code, "score": sc, "hash": h}); seen_scores.add(round(sc, 6)); n_new += 1
                        if (sc > best) if P["maximize"] else (sc < best):
                            best = sc; (out / "best.py").write_text(code); print(f"  ** new best {best:.6f} (gen {g}, island {k})", flush=True)
                    else:
                        rec["error"] = str(res.get("error", ""))[:120]
                with open(hist, "a") as f:
                    f.write(json.dumps(rec) + "\n")
            # keep the island bounded
            isl.sort(key=lambda e: e["score"], reverse=P["maximize"]); del isl[max(a.elites * 4, 8):]
        # migration: best of each island visits the next
        if a.islands > 1 and g % 3 == 2:
            bests = [max(isl, key=lambda e: e["score"] if P["maximize"] else -e["score"]) for isl in islands]
            for k in range(a.islands):
                islands[(k + 1) % a.islands].append(dict(bests[k]))
        state_p.write_text(json.dumps({"gen": g, "islands": islands, "best": best}))
        print(f"gen {g}: valid {n_ok}/{a.samples * a.islands}, kept {n_new}, best {best:.6f} "
              f"(gap to best known {P['best_known'] - best:+.4f}), {time.time() - t0:.0f}s", flush=True)
    print(f"DONE best {best:.6f}", flush=True)

if __name__ == "__main__":
    main()
