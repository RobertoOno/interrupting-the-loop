#!/usr/bin/env python3
"""Battery C: consolidation by LoRA (STaR/ReST-style cycle on Qwen3-8B-Base).

Subcommands
  gen     --arm A --cycle k --adapter PATH|none --variants train|heldout --n N --tokens T --out DIR
          notebooks (premise + angle comment every 250 tokens, chunked generation), one
          file per (variant, notebook); candidates = closed `def priority...` functions.
  verify  --out DIR : score every candidate on TRAIN (seeds 100+v, 20x200) and TEST
          (seeds 200+v, 20x200) instances; writes candidates.json with excesses, the
          classic baselines, and the 'find' flag (beats min(BF,FF) on train by margin).
  select  --out DIR --mode finds|random --k K --sft PATH : build the SFT jsonl
          (prompt = notebook premise up to '# Idea 1:', completion = one function).
No LLM judge anywhere; the verifier is the only reader.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from creative_machine.code_exec import run_heuristic_code
from creative_machine.domains.binpack import evaluate, best_fit, first_fit
from creative_machine.problem_premises import VARIANTS_C_TRAIN, VARIANTS_C_HELDOUT, VARIANTS_C_HELDOUT2, FAR_VARIANTS, premise, premise_far, ANGLES
from problem_loop import closed_functions, inside_open_function

N_INST, N_ITEMS = 20, 200
MARGIN = 0.001

def variants(which):
    return {"train": VARIANTS_C_TRAIN, "heldout": VARIANTS_C_HELDOUT, "heldout2": VARIANTS_C_HELDOUT2, "far": FAR_VARIANTS}[which]

def far_items(name, rng, n):
    if name == "weibull_2_030":
        return np.clip(rng.weibull(2.0, n) * 0.30, 0.01, 1.0)
    if name == "weibull_15_025":
        return np.clip(rng.weibull(1.5, n) * 0.25, 0.01, 1.0)
    if name == "tri_002_030_060":
        return rng.triangular(0.02, 0.30, 0.60, n)
    if name == "tri_005_015_050":
        return rng.triangular(0.05, 0.15, 0.50, n)
    if name == "bimodal_small_large":
        m = rng.random(n) < 0.6
        return np.where(m, rng.uniform(0.05, 0.20, n), rng.uniform(0.50, 0.70, n))
    if name == "orlib_20_100_150":
        return rng.integers(20, 101, n) / 150.0
    raise KeyError(name)

def instances(which, vi, seed):
    rng = np.random.default_rng(seed)
    if which == "far":
        return [list(far_items(FAR_VARIANTS[vi][0], rng, N_ITEMS)) for _ in range(N_INST)]
    lo, hi = variants(which)[vi]
    return [list(np.clip(rng.uniform(lo, hi, N_ITEMS), 0.01, 1.0)) for _ in range(N_INST)]

def premise_for(which, vi):
    if which == "far":
        return premise_far(FAR_VARIANTS[vi][1])
    lo, hi = variants(which)[vi]
    return premise(lo, hi)

def vseed(which, vi, base):
    return base + vi + {"train": 0, "heldout": 50, "far": 80}[which]

def norm(code):
    body = "\n".join(l.strip() for l in code.splitlines()[1:] if l.strip() and not l.strip().startswith('"""'))
    return hashlib.md5(re.sub(r"\s+", " ", body).encode()).hexdigest()

def cmd_gen(a):
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    from creative_machine import SamplerConfig
    from creative_machine.adapters.mlx_lm import MLXAntiprobableSampler
    from generate_mlx import eos_ids
    model, tok = load(str(Path(a.model).expanduser()), adapter_path=(None if a.adapter in (None, "none") else a.adapter))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    done = {p.stem for p in out.glob("*.txt")}
    for vi in range(len(variants(a.variants))):
        for nb in range(a.n):
            key = f"{a.variants}_v{vi}_n{nb}"
            if key in done:
                continue
            text = premise_for(a.variants, vi)
            rng = np.random.default_rng(a.seed * 100003 + vi * 101 + nb)
            cfg = SamplerConfig(lam=0.0, entropy_trigger=99.0, no_push_ids=eos_ids(tok),
                                seed=int(rng.integers(0, 2**31)), repetition_window=512, repetition_penalty=1.15)
            n_gen, next_angle, angle_i = 0, 250, int(rng.integers(0, len(ANGLES)))
            while n_gen < a.tokens:
                smp = MLXAntiprobableSampler(model, config=cfg); smp.observe_prompt(tok.encode(text))
                step = min(a.chunk, a.tokens - n_gen)
                chunk = "".join(o.text for o in stream_generate(model, tok, text, max_tokens=step, sampler=smp))
                if not chunk:
                    break
                text += chunk; n_gen += step
                if n_gen >= next_angle and not inside_open_function(text):
                    next_angle += 250; angle_i = (angle_i + 1) % len(ANGLES)
                    text += "\n\n" + ANGLES[angle_i] + "\n"
            (out / f"{key}.txt").write_text(text)
            print(f"{a.arm} c{a.cycle} {key}: {len(closed_functions(text))} fns", flush=True)

def cmd_verify(a):
    out = Path(a.out)
    cj = out / "candidates.json"
    cands = json.loads(cj.read_text()) if cj.exists() else {}
    base_cache = {}
    for txt in sorted(out.glob("*.txt")):
        which, v, nb = txt.stem.split("_")
        vi = int(v[1:])
        if (which, vi) not in base_cache:
            tr, te = instances(which, vi, vseed(which, vi, 100)), instances(which, vi, vseed(which, vi, 200))
            base_cache[(which, vi)] = (tr, te, {"bf_train": evaluate(best_fit, tr)["mean_excess"], "ff_train": evaluate(first_fit, tr)["mean_excess"],
                                               "bf_test": evaluate(best_fit, te)["mean_excess"], "ff_test": evaluate(first_fit, te)["mean_excess"]})
        tr, te, base = base_cache[(which, vi)]
        for name, src in closed_functions(txt.read_text()):
            h = norm(src); key = f"{txt.stem}:{h}"
            if key in cands:
                continue
            r = run_heuristic_code(src, tr, timeout_s=20.0)
            rec = {"which": which, "variant": vi, "notebook": txt.stem, "name": name, "src": src, "hash": h, "ok": bool(r.get("ok"))}
            if r.get("ok"):
                rec["train"] = r["mean_excess"]
                rt = run_heuristic_code(src, te, timeout_s=20.0)
                rec["test"] = rt["mean_excess"] if rt.get("ok") else None
                rec.update(base)
                rec["find"] = rec["train"] < min(base["bf_train"], base["ff_train"]) - MARGIN
            cands[key] = rec
        cj.write_text(json.dumps(cands, indent=0))
    n = len(cands); ok = [c for c in cands.values() if c["ok"]]
    finds = [c for c in ok if c.get("find")]
    print(f"{out.name}: {n} candidates, {len(ok)} valid, {len({c['hash'] for c in ok})} distinct, {len(finds)} finds "
          f"({100*len(finds)/max(1,len(ok)):.1f}% of valid)", flush=True)

def cmd_select(a):
    out = Path(a.out)
    cands = json.loads((out / "candidates.json").read_text())
    ok = {c["hash"]: c for c in cands.values() if c["ok"] and c["which"] == "train"}  # never train on held-out variants
    rng = np.random.default_rng(a.seed)
    if a.mode in ("qd", "pairs_mode"):
        # behaviour vectors (per-instance excess on the variant's training instances) for valid distinct train candidates
        bcache_p = out / "behaviour.json"
        bcache = json.loads(bcache_p.read_text()) if bcache_p.exists() else {}
        from creative_machine.domains.binpack import best_fit as _bf, first_fit as _ff
        byv = {}
        for c in ok.values():
            byv.setdefault(c["variant"], []).append(c)
        elites, clones = [], {}
        for v, cs in sorted(byv.items()):
            tr = instances("train", v, vseed("train", v, 100))
            ref = {}
            for nm, fn in (("bf", _bf), ("ff", _ff)):
                r = run_heuristic_code("def priority(item: float, remaining: list[float]) -> list[float]:\n    return " +
                                       ("[-(r - item) for r in remaining]" if nm == "bf" else "[0.0] * len(remaining)") + "\n", tr, timeout_s=20.0)
                ref[nm] = np.array(r["excesses"])
            vecs = []
            for c in cs:
                if c["hash"] not in bcache:
                    r = run_heuristic_code(c["src"], tr, timeout_s=20.0)
                    bcache[c["hash"]] = r.get("excesses") if r.get("ok") else None
                if bcache[c["hash"]] is not None:
                    vecs.append((c, np.array(bcache[c["hash"]])))
            bcache_p.write_text(json.dumps(bcache))
            # clones of the classic attractor: behaviour identical to best fit or first fit on every instance
            cl = [c for c, x in vecs if np.allclose(x, ref["bf"], atol=1e-9) or np.allclose(x, ref["ff"], atol=1e-9)]
            clones[v] = cl
            rest = [(c, x) for c, x in vecs if c not in cl]
            # k-means (k=4) on behaviour; elite = best train excess per niche; one niche reserved for the clone mode
            k = 3
            if len(rest) >= k:
                X = np.stack([x for _, x in rest]); rs = np.random.default_rng(a.seed + v)
                cent = X[rs.choice(len(X), k, replace=False)]
                for _ in range(20):
                    lab = np.argmin(((X[:, None, :] - cent[None]) ** 2).sum(-1), axis=1)
                    for j in range(k):
                        if np.any(lab == j):
                            cent[j] = X[lab == j].mean(0)
                for j in range(k):
                    members = [rest[i][0] for i in range(len(rest)) if lab[i] == j]
                    if members:
                        elites.append(min(members, key=lambda c: c["train"]))
            else:
                elites.extend(c for c, _ in rest)
            if cl:
                elites.append(min(cl, key=lambda c: c["train"]))   # the attractor keeps one seat
        elites = elites[: a.k] if len(elites) > a.k else elites
        Path(a.sft).parent.mkdir(parents=True, exist_ok=True)
        with open(a.sft, "w") as f:
            if a.mode == "qd":
                for c in elites:
                    lo, hi = VARIANTS_C_TRAIN[c["variant"]]
                    f.write(json.dumps({"prompt": premise(lo, hi), "completion": c["src"] + "\n"}) + "\n")
                print(f"qd: {len(elites)} elites -> {a.sft} (clone niches {sum(1 for v in clones if clones[v])}/{len(clones)}; "
                      f"mean excess {np.mean([c['train'] for c in elites]):.4f})", flush=True)
            else:   # pairs_mode: chosen = non-clone elites, rejected = a best-fit clone of the same variant
                n = 0
                for c in elites:
                    cl = clones.get(c["variant"], [])
                    if not cl or c in cl:
                        continue
                    r = cl[n % len(cl)]
                    lo, hi = VARIANTS_C_TRAIN[c["variant"]]
                    f.write(json.dumps({"prompt": premise(lo, hi), "chosen": c["src"] + "\n", "rejected": r["src"] + "\n",
                                        "chosen_excess": c["train"], "rejected_excess": r["train"]}) + "\n"); n += 1
                print(f"pairs_mode: {n} pairs -> {a.sft}", flush=True)
        return
    if a.mode == "pairs":   # DPO pairs: chosen = the attract set, rejected = the worst valid of the same variant
        chosen = [c for c in ok.values() if c.get("find")]
        if len(chosen) < a.k:
            chosen = sorted(ok.values(), key=lambda c: c["train"])[: a.k]
        chosen_h = {c["hash"] for c in chosen}
        rows = []
        for v in sorted({c["variant"] for c in chosen}):
            ch = [c for c in chosen if c["variant"] == v]
            worst = sorted([c for c in ok.values() if c["variant"] == v and c["hash"] not in chosen_h], key=lambda c: -c["train"])
            if not worst:
                continue
            lo, hi = VARIANTS_C_TRAIN[v]; pre = premise(lo, hi)
            for i, c in enumerate(ch):
                r = worst[i % len(worst)]
                rows.append({"prompt": pre, "chosen": c["src"] + "\n", "rejected": r["src"] + "\n",
                             "chosen_excess": c["train"], "rejected_excess": r["train"]})
        Path(a.sft).parent.mkdir(parents=True, exist_ok=True)
        with open(a.sft, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        print(f"pairs: {len(rows)} -> {a.sft} (chosen mean {np.mean([r['chosen_excess'] for r in rows]):.4f}, rejected mean {np.mean([r['rejected_excess'] for r in rows]):.4f})", flush=True)
        return
    if a.mode == "finds":
        pool = [c for c in ok.values() if c.get("find")]
        if len(pool) < a.k:   # pre-registered fallback: top-k by train excess
            pool = sorted(ok.values(), key=lambda c: c["train"])[: a.k]
    else:                       # random: same size, unfiltered valid distinct
        pool = list(ok.values()); rng.shuffle(pool); pool = pool[: a.k]
    rows = []
    for c in pool:
        lo, hi = VARIANTS_C_TRAIN[c["variant"]]
        pre = premise(lo, hi)
        rows.append({"prompt": pre, "completion": c["src"] + "\n"})
    Path(a.sft).parent.mkdir(parents=True, exist_ok=True)
    with open(a.sft, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"{a.mode}: {len(rows)} examples -> {a.sft}", flush=True)

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("gen"); g.add_argument("--model", default="~/models/mlx/Qwen3-8B-Base-8bit"); g.add_argument("--adapter", default="none")
    g.add_argument("--arm", required=True); g.add_argument("--cycle", type=int, default=0); g.add_argument("--variants", choices=["train", "heldout", "heldout2", "far"], default="train")
    g.add_argument("--n", type=int, default=3); g.add_argument("--tokens", type=int, default=1500); g.add_argument("--chunk", type=int, default=125)
    g.add_argument("--seed", type=int, default=0); g.add_argument("--out", required=True)
    v = sp.add_parser("verify"); v.add_argument("--out", required=True)
    s = sp.add_parser("select"); s.add_argument("--out", required=True); s.add_argument("--mode", choices=["finds", "random", "pairs", "qd", "pairs_mode"], required=True)
    s.add_argument("--k", type=int, default=60); s.add_argument("--sft", required=True); s.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    {"gen": cmd_gen, "verify": cmd_verify, "select": cmd_select}[a.cmd](a)
