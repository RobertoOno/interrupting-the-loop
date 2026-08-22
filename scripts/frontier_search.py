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
        "best_known": 2.635983,  # ShinkaEvolve 2025 (2.635983283); AlphaEvolve 2.63586276; Friedman 2012: 2.634
        "statement": (
            "Place n = 26 circles inside the unit square [0, 1] x [0, 1] so that no two circles overlap and every "
            "circle lies entirely inside the square, maximizing the SUM OF THE RADII. Write a Python function "
            "`construct(n)` returning a list of n tuples (x, y, r). The verifier checks containment and non-overlap "
            "exactly (tolerance 1e-7) and scores the sum of radii. numpy and scipy (e.g. scipy.optimize) are "
            "available; keep the run deterministic and under 20 seconds."),
        "seed_program": (
            "def construct(n):\n    import math\n    k = math.ceil(math.sqrt(n)); r = 0.5 / k\n    out = []\n"
            "    for i in range(k):\n        for j in range(k):\n            if len(out) < n:\n"
            "                out.append((r + 2 * r * i, r + 2 * r * j, r))\n    return out\n"),
    },
    "autocorr1": {
        "module": "autocorr1", "entry": "construct", "args": (), "maximize": False,
        "best_known": 1.5029,  # Yuksekgonul et al. Jan 2026; AlphaEvolve 1.5032 (Dec 2025); Matolcsi-Vinuesa 2009: 1.50992
        "statement": (
            "First autocorrelation inequality. Find a non-negative step function f on [-1/4, 1/4] with n equal-width "
            "steps that makes 2 n max(a * a) / (sum a)^2 as SMALL as possible, where a is the list of step heights "
            "and a * a is the discrete autocorrelation (numpy.convolve(a, a)). This ratio is an upper bound on the "
            "constant C1 (best known 1.5029; the 2009 record was 1.50992). Write a Python function `construct()` "
            "returning a list of between 300 and 5000 non-negative floats. numpy and scipy are available; "
            "deterministic, under 20 seconds."),
        "seed_program": "def construct():\n    return [1.0] * 300\n",
    },
    "beatavg": {
        "module": "beatavg", "entry": "construct", "args": (5000,), "maximize": True,
        "best_known": 0.400695,  # Bellec-Fritz (best known); AlphaEvolve 0.3890 at L = 20000
        "statement": (
            "Beat-the-average game. Choose a probability mass function p on {0, 1, ..., L-1} (L = 5000) for i.i.d. "
            "variables X1..X4 to MAXIMIZE P[X1 + X2 + X3 < 2 X4]. Write a Python function `construct(L)` returning a "
            "list of L non-negative floats (the verifier normalizes them). The best known value is 0.400695; sparse, "
            "carefully placed atoms do well. numpy and scipy are available; deterministic, under 20 seconds."),
        "seed_program": "def construct(L):\n    return [1.0] * L\n",
    },
    "ringload15": {
        "module": "ringload", "entry": "construct", "args": (15,), "maximize": True,
        "best_known": 1.1190,  # AlphaEvolve new result at m = 15
        "statement": (
            "Ring loading constant. Choose m = 15 pairs (u_i, v_i) with u_i, v_i >= 0 and u_i + v_i <= 1 to MAXIMIZE "
            "alpha = min over all choices z_i in {v_i, -u_i} of max_k |sum(z[:k]) - sum(z[k:])| (k = 1..m-1). "
            "The verifier enumerates all 2^m choices exactly. Values above 1.101 are known to be achievable and the "
            "best known is about 1.119. Write a Python function `construct(m)` returning a list of m (u, v) pairs. "
            "numpy and scipy are available; deterministic, under 20 seconds."),
        "seed_program": "def construct(m):\n    return [(0.5, 0.5)] * m\n",
    },
    "isofree64": {
        "module": "isofree", "entry": "construct", "args": (64,), "maximize": True,
        "best_known": 112.0,  # AlphaEvolve (n = 64); best known before: 110
        "statement": (
            "Isosceles-free subsets of the grid. Find as MANY points as possible with integer coordinates in "
            "{0, ..., 63}^2 such that no three distinct points a, b, c satisfy dist(a, b) == dist(b, c) (no isosceles "
            "triangle, including degenerate collinear ones). Equivalently: from every point, the distances to all "
            "other points are pairwise distinct. Best known: 112 points. Write a Python function `construct(n)` "
            "returning a list of distinct (x, y) integer tuples. numpy and scipy are available; deterministic, under "
            "20 seconds (a greedy or randomized incremental construction with a fast validity check works well)."),
        "seed_program": "def construct(n):\n    return [(0, 0), (1, 0), (3, 0)]\n",
    },
    "sumdiff3": {
        "module": "sumdiff3", "entry": "construct", "args": (), "maximize": True,
        "best_known": 1.1584,  # AlphaEvolve (54265 ints); later improved by Gerbicz (2505.16105) and Zheng (2506.01896)
        "statement": (
            "Sum-difference problem III. Find a set U of distinct non-negative integers containing 0 (at most 4000 "
            "elements) that MAXIMIZES log(|U - U| / |U + U|) / log(2 max(U) + 1) + 1, where U - U and U + U are the "
            "difference and sum sets. Best known values: 1.14465 (2007), 1.1479 with 2003 integers and 1.1584 with "
            "54265 integers (2025). Write a Python function `construct()` returning the list of integers. numpy and "
            "scipy are available; deterministic, under 20 seconds."),
        "seed_program": "def construct():\n    return [0, 1, 3]\n",
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

def build_prompt(P: dict, elites: list[dict], memory: str = "verbatim", recap: str | None = None,
                 agenda: str | None = None, repel: list[str] | None = None) -> str:
    """verbatim: statement + top programs (FunSearch-style). schema: statement + the model's own compressed
    lab notebook (what worked / what failed / open question) + the single best program. agenda: an extra
    line naming the obstacle to attack. repel: constructions (signatures/scores) that must NOT be repeated."""
    better = "higher" if P["maximize"] else "lower"
    parts = [f'"""{P["statement"]}"""\n']
    es = sorted(elites, key=lambda e: e["score"], reverse=P["maximize"])
    if memory == "schema" and recap:
        parts.append("# Lab notebook of this line of attack so far:\n" + recap.rstrip() + "\n")
        es = es[:1]
    for i, e in enumerate(es):
        parts.append(f"# Version {i} (score {e['score']:.6f}):\n{e['code'].replace('def ' + P['entry'], 'def ' + P['entry'] + '_v' + str(i))}\n")
    if repel:
        parts.append("# Constructions already found (do NOT reproduce them; find something structurally different):\n" +
                     "\n".join(f"#   - {r}" for r in repel) + "\n")
    if agenda:
        parts.append(f"# Obstacle to attack in the next version: {agenda.strip()}\n")
    parts.append(f"# Improved version ({better} score):\ndef {P['entry']}(")
    return "\n".join(parts)

def write_recap(model, tok, sampler, P: dict, isl: list[dict], recent: list[dict], max_tokens: int = 220) -> str:
    """The model writes its own compressed notebook (schematic memory) from the island's elites and the
    recent failures: what worked, what failed and why, and the open question. Returned as comment lines."""
    es = sorted(isl, key=lambda e: e["score"], reverse=P["maximize"])[:3]
    fails = [r for r in recent if not r.get("ok")][-6:]
    lows = sorted([r for r in recent if r.get("ok")], key=lambda r: r["score"], reverse=not P["maximize"])[:4]
    cue = [f'"""{P["statement"]}"""\n']
    for i, e in enumerate(es):
        cue.append(f"# Program {i} (score {e['score']:.6f}):\n{e['code']}\n")
    if fails:
        cue.append("# Recent failed attempts (error):\n" + "\n".join(f"#   {f.get('error','?')[:80]}" for f in fails) + "\n")
    if lows:
        cue.append("# Recent valid but weak attempts (score):\n" + "\n".join(f"#   {r['score']:.6f}" for r in lows) + "\n")
    cue.append("# Lab notebook (what has worked, what failed and why, and the single open question that blocks "
               "progress; terse, as comments):\n# What worked:")
    from mlx_lm import stream_generate
    text = "".join(o.text for o in stream_generate(model, tok, "\n".join(cue), max_tokens=max_tokens, sampler=sampler))
    text = "# What worked:" + text
    lines = []
    for ln in text.splitlines():
        if ln.strip() == "":
            if lines:
                break
            continue
        if not ln.lstrip().startswith("#"):
            if ln.lstrip().startswith("def ") or ln.lstrip().startswith("import"):
                break
            ln = "# " + ln.strip()
        lines.append(ln.rstrip())
        if len(lines) >= 12:
            break
    return "\n".join(lines)

def write_agenda(model, tok, sampler, P: dict, best: dict, max_tokens: int = 60) -> str:
    cue = (f'"""{P["statement"]}"""\n# Current best program (score {best["score"]:.6f}):\n{best["code"]}\n'
           "# The one structural obstacle that keeps this construction from a better score is:")
    from mlx_lm import stream_generate
    text = "".join(o.text for o in stream_generate(model, tok, cue, max_tokens=max_tokens, sampler=sampler))
    return text.strip().split("\n")[0].strip(" #")[:200]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--problem", choices=sorted(PROBLEMS), required=True)
    ap.add_argument("--model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit"); ap.add_argument("--adapter", default="none")
    ap.add_argument("--gens", type=int, default=10); ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--islands", type=int, default=2); ap.add_argument("--elites", type=int, default=3)
    ap.add_argument("--novelty", choices=["none", "score", "behavior"], default="none",
                    help="reject candidates that duplicate an island member by rounded score, or by the construction itself (behavior signature)")
    ap.add_argument("--memory", choices=["verbatim", "schema"], default="verbatim", help="prompt memory: top programs verbatim, or the model's own compressed notebook + best program")
    ap.add_argument("--agenda", action="store_true", help="add a model-written 'obstacle to attack' line to the prompt")
    ap.add_argument("--repel-prompt", action="store_true", help="list already-found constructions in the prompt as things not to reproduce")
    ap.add_argument("--max-tokens", type=int, default=700); ap.add_argument("--temp", type=float, default=1.0); ap.add_argument("--min-p", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    P = PROBLEMS[a.problem]
    # one model process at a time: a second 30B instance exhausts unified memory (machine rebooted 2026-08-22)
    import os, subprocess
    others = [l for l in subprocess.run(["ps", "-axo", "pid,command"], capture_output=True, text=True).stdout.splitlines()
              if any(k in l for k in ("frontier_search.py", "dream_run.py", "consolidate.py gen", "mlx_lm lora", "dpo_lora.py", "problem_loop.py", "evolve_interrupt.py"))
              and str(os.getpid()) not in l.split()[0:1] and "grep" not in l]
    if others and not os.environ.get("CM_ALLOW_MULTI"):
        print("REFUSING TO START: another model process is running (set CM_ALLOW_MULTI=1 to override):\n  " + "\n  ".join(o[:120] for o in others), flush=True)
        sys.exit(3)
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    model, tok = load(str(Path(a.model).expanduser()), adapter_path=(None if a.adapter == "none" else a.adapter))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    hist = out / "history.jsonl"; state_p = out / "state.json"
    rng = random.Random(a.seed)
    seed_res = run_candidate(P["seed_program"], P["module"], P["entry"], P["args"])
    islands = [[{"code": P["seed_program"], "score": seed_res["score"], "hash": "seed", "sig": seed_res.get("sig", "")}] for _ in range(a.islands)]
    recent_by_island = [[] for _ in range(a.islands)]
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
            recap = write_recap(model, tok, sampler, P, isl, recent_by_island[k]) if a.memory == "schema" else None
            agenda = write_agenda(model, tok, sampler, P, elites[0]) if a.agenda else None
            repel = [f"score {e['score']:.6f}, signature {e.get('sig','')}" for e in elites] if a.repel_prompt else None
            prompt = build_prompt(P, elites, a.memory, recap, agenda, repel)
            shown = sorted(elites, key=lambda e: e["score"], reverse=P["maximize"])
            if a.memory == "schema" and recap:
                shown = shown[:1]
            prelude = "\n\n".join(e["code"].replace("def " + P["entry"], "def " + P["entry"] + "_v" + str(i)) for i, e in enumerate(shown))
            if recap or agenda:
                with open(out / "notebook.jsonl", "a") as f:
                    f.write(json.dumps({"gen": g, "island": k, "recap": recap, "agenda": agenda}) + "\n")
            ph = hashlib.md5(prompt.encode()).hexdigest()[:10]
            seen_scores = {round(e["score"], 6) for e in isl}
            seen_sigs = {e.get("sig", "") for e in isl}
            recent_by_island[k] = []
            for s in range(a.samples):
                text = "".join(o.text for o in stream_generate(model, tok, prompt, max_tokens=a.max_tokens, sampler=sampler))
                # the prompt ends with `def entry(`; some models repeat the header instead of continuing it
                full = text if re.search(rf"^def {P['entry']}\(", text, re.M) else f"def {P['entry']}(" + text
                code = extract_program(full, P["entry"])
                rec = {"gen": g, "island": k, "sample": s, "prompt": ph, "ok": False}
                if code is None:
                    rec["error"] = "no function"
                else:
                    h = hashlib.md5(re.sub(r"\s+", " ", code).encode()).hexdigest()[:12]
                    rec["hash"] = h
                    res = run_candidate(code, P["module"], P["entry"], P["args"], prelude=prelude)
                    rec["ok"] = bool(res.get("ok"))
                    if res.get("ok"):
                        sc = float(res["score"]); rec["score"] = sc; n_ok += 1
                        sig = res.get("sig", ""); rec["sig"] = sig
                        dup_score = round(sc, 6) in seen_scores; dup_sig = sig in seen_sigs
                        rec["novel_score"] = not dup_score; rec["novel_behavior"] = not dup_sig
                        reject = (a.novelty == "score" and dup_score) or (a.novelty == "behavior" and dup_sig)
                        if not reject:
                            isl.append({"code": code, "score": sc, "hash": h, "sig": sig}); seen_scores.add(round(sc, 6)); seen_sigs.add(sig); n_new += 1
                        if (sc > best) if P["maximize"] else (sc < best):
                            best = sc; (out / "best.py").write_text(code); print(f"  ** new best {best:.6f} (gen {g}, island {k})", flush=True)
                    else:
                        rec["error"] = str(res.get("error", ""))[:120]
                recent_by_island[k].append(rec)
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
