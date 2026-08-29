#!/usr/bin/env python3
"""Phase 5 instrumentation: live generation with state operators applied to
the residual stream at a chosen layer, on a schedule — the manual loop of
`hidden_states.py` turned from measurement into intervention.

Concept directions come from the model's own states (mean hidden state of a
concept text at the target layer, position 0 excluded); operators are the
closed-form rank-1/2 updates in `creative_machine.state_ops`. Cells are
written in the dream format (text.txt / tokens.json / run.json /
insights.json) so the paper-1 judging pipeline reads them unchanged, plus a
`state.json` with the intervention's provenance and the cheap half of the
coherence measure: mean NLL of the generated stream under the SAME model,
untouched (fresh pass, no operators).

    python scripts/state_inject.py --out runs/state_band/s0_translate_L18_a4 \
        --seed-index 0 --op translate --layer 18 --alpha 4.0 \
        --concept-a "seed text A" --concept-b "seed text B"

    --op none gives the bare control under the identical sampler and loop.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from creative_machine import state_ops as so


def refuse_if_other_model(out: Path) -> None:
    """One model at a time on this machine (48 GB): refuse when another local
    model process is live. Same exclusions as frontier_search.py."""
    me = {str(os.getpid()), str(os.getppid())}
    others = []
    for l in subprocess.run(["ps", "-axo", "pid,command"], capture_output=True, text=True).stdout.splitlines():
        parts = l.split(None, 1)
        if len(parts) < 2 or parts[0] in me:
            continue
        cmd = parts[1]
        if "python" not in cmd or "grep" in cmd or "/bin/zsh -c" in cmd or "/bin/sh -c" in cmd or "snapshot-zsh" in cmd:
            continue
        if "--api-model" in cmd and "--api-model none" not in cmd:
            continue
        if str(out) in cmd:
            continue
        if any(k in cmd for k in ("frontier_search.py", "dream_run.py", "consolidate.py gen", "mlx_lm lora",
                                  "dpo_lora.py", "problem_loop.py", "evolve_interrupt.py", "state_inject.py")):
            others.append(l)
    if others and not os.environ.get("CM_ALLOW_MULTI"):
        print("REFUSING TO START: another model process is running (set CM_ALLOW_MULTI=1 to override):\n  "
              + "\n  ".join(o[:120] for o in others), flush=True)
        sys.exit(3)


def forward_chunked(model, cache, ids, layer: int, mx, cam):
    """Feed ids through the model (chunked, cached); returns (last hidden of
    the final layer, sum and count of the target layer's states over
    positions excluding stream position 0)."""
    inner = model.model
    vec_sum, vec_n, h_last, seen = None, 0, None, 0
    for s in range(0, len(ids), 512):
        x = mx.array([int(t) for t in ids[s : s + 512]])[None]
        h = inner.embed_tokens(x)
        mask = cam(h, cache[0])
        for li, (layer_m, c) in enumerate(zip(inner.layers, cache)):
            h = layer_m(h, mask, c)
            if li == layer:
                g = h[0].astype(mx.float32)
                if seen == 0:
                    g = g[1:]  # attention sink
                vec_sum = g.sum(axis=0) if vec_sum is None else vec_sum + g.sum(axis=0)
                vec_n += g.shape[0]
        h_last = h
        seen += x.shape[1]
        mx.eval(h_last, vec_sum)
    return h_last, vec_sum, vec_n


def concept_vector(model, tokenizer, text: str, layer: int, mx, cam, mpc) -> "np.ndarray":
    """Unit mean state of `text` at `layer` (fresh cache, position 0 excluded)."""
    ids = tokenizer.encode(text)
    _, vs, vn = forward_chunked(model, mpc(model), ids, layer, mx, cam)
    v = np.asarray(vs).astype(np.float64) / max(1, vn)
    return v / (np.linalg.norm(v) + 1e-12)


def head_logits(model, h, mx):
    inner = model.model
    g = inner.norm(h)
    if model.args.tie_word_embeddings:
        return inner.embed_tokens.as_linear(g)
    return model.lm_head(g)


def sample_token(logits, temp: float, top_p: float, ban, mx) -> int:
    lg = logits[0, -1].astype(mx.float32)
    for t in ban:
        lg[t] = -1e9
    lg = lg / max(temp, 1e-6)
    if top_p < 1.0:
        idx = mx.argsort(-lg)
        srt = lg[idx]
        p = mx.softmax(srt)
        keep = mx.cumsum(p) - p < top_p          # tokens whose prefix mass is < top_p
        srt = mx.where(keep, srt, -1e9)
        pick = int(mx.random.categorical(srt))
        return int(idx[pick])
    return int(mx.random.categorical(lg))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--model", default="~/models/mlx/Qwen3-8B-Base-8bit")
    p.add_argument("--seed-text", default=None)
    p.add_argument("--seed-index", type=int, default=0)
    p.add_argument("--op", choices=["none", "translate", "rotate", "repel"], default="none")
    p.add_argument("--layer", type=int, default=18)
    p.add_argument("--alpha", type=float, default=0.0, help="dose: translation length (units of premise-state norm), rotor angle (radians), or repel step")
    p.add_argument("--concept-a", default=None, help="direction text A (v = mean_A - mean_B, or mean_A - premise if no B)")
    p.add_argument("--concept-b", default=None)
    p.add_argument("--schedule", default="::", help="start:stop:every over generation steps")
    p.add_argument("--keep-norm", action="store_true", help="renorm h to its pre-op norm (norm-shell guard)")
    p.add_argument("--anchor", action="store_true", help="pin the premise-direction coordinate through the op")
    p.add_argument("--repel-halflife", type=int, default=128, help="EMA half-life (steps) of the trajectory mean for --op repel")
    p.add_argument("--max-tokens", type=int, default=1500)
    p.add_argument("--temp", type=float, default=1.0)
    p.add_argument("--top-p", type=float, default=0.95)
    p.add_argument("--rng-seed", type=int, default=0)
    a = p.parse_args()
    refuse_if_other_model(a.out)

    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.models.base import create_attention_mask as cam
    from mlx_lm.models.cache import make_prompt_cache as mpc

    from dream_run import SEEDS  # scripts/ is on sys.path

    model, tokenizer = load(str(Path(a.model).expanduser()))
    inner = model.model
    n_layers = len(inner.layers)
    assert 0 <= a.layer < n_layers, f"layer {a.layer} outside 0..{n_layers - 1}"
    mx.random.seed(a.rng_seed)
    seed = a.seed_text if a.seed_text else SEEDS[a.seed_index % len(SEEDS)]
    seed_ids = tokenizer.encode(seed)
    ban = sorted(tokenizer.eos_token_ids) if getattr(tokenizer, "eos_token_ids", None) else []
    sched = so.Schedule.parse(a.schedule)

    # --- directions (fresh caches; computed before the generation cache) ---
    prem_np = concept_vector(model, tokenizer, seed, a.layer, mx, cam, mpc)
    v_np, cos_ab = None, None
    if a.op in ("translate", "rotate"):
        assert a.concept_a, f"--op {a.op} needs --concept-a"
        va = concept_vector(model, tokenizer, a.concept_a, a.layer, mx, cam, mpc)
        vb = concept_vector(model, tokenizer, a.concept_b, a.layer, mx, cam, mpc) if a.concept_b else prem_np
        cos_ab = float(va @ vb)
        d = va - vb
        v_np = d / (np.linalg.norm(d) + 1e-12)
    prem = mx.array(prem_np.astype(np.float32))
    v = mx.array(v_np.astype(np.float32)) if v_np is not None else None
    u_hat = w_hat = None
    if a.op == "rotate":
        u_hat, w_hat = so.orthonormal_pair(prem, v, mx)

    # --- prefill (also the premise-state scale for translate's dose unit) ---
    cache = mpc(model)
    h_last, vs, vn = forward_chunked(model, cache, seed_ids, a.layer, mx, cam)
    state_scale = float(np.linalg.norm(np.asarray(vs)) / max(1, vn))  # ||mean premise state||
    mu = mx.array((prem_np * state_scale).astype(np.float32))         # repel EMA start: premise mean
    lam = 1.0 - 0.5 ** (1.0 / max(1, a.repel_halflife))

    def apply_op(h):
        hf = h.astype(mx.float32)
        pre_norm = so.norms(hf, mx)
        tgt = so.coord(hf, prem, mx)
        if a.op == "translate":
            hf = so.translate(hf, v, a.alpha * state_scale)
        elif a.op == "rotate":
            hf = so.rotate(hf, u_hat, w_hat, a.alpha, mx)
        elif a.op == "repel":
            hf = so.repel(hf, mu, a.alpha * state_scale, mx)
        if a.anchor:
            hf = so.restore_coord(hf, prem, tgt, mx)
        if a.keep_norm:
            hf = so.renorm(hf, pre_norm, mx)
        return hf.astype(h.dtype)

    tok = sample_token(head_logits(model, h_last, mx), a.temp, a.top_p, ban, mx)
    ids, fired, t0 = [tok], 0, time.time()
    for step in range(2, a.max_tokens + 1):
        x = mx.array([[ids[-1]]])
        h = inner.embed_tokens(x)
        mask = cam(h, cache[0])
        for li, (layer_m, c) in enumerate(zip(inner.layers, cache)):
            h = layer_m(h, mask, c)
            if li == a.layer:
                if a.op == "repel":
                    mu = (1.0 - lam) * mu + lam * h[0, -1].astype(mx.float32)
                if a.op != "none" and sched.active(step):
                    h = apply_op(h)
                    fired += 1
        tok = sample_token(head_logits(model, h, mx), a.temp, a.top_p, ban, mx)
        ids.append(tok)
        if step % 512 == 0:
            mx.clear_cache()

    text = tokenizer.decode(ids)

    # --- coherence, cheap half: NLL of the stream under the untouched model ---
    full = seed_ids + ids
    nll, cache2 = [], mpc(model)
    for s in range(0, len(full) - 1, 512):
        x = mx.array([full[s : s + 512]])
        lg = model(x, cache=cache2).astype(mx.float32)
        lp = lg - mx.logsumexp(lg, axis=-1, keepdims=True)
        tgts = mx.array([full[s + 1 : s + 1 + x.shape[1]]])
        take = mx.take_along_axis(lp[:, : tgts.shape[1]], tgts[..., None], axis=-1)
        mx.eval(take)
        nll.extend((-np.asarray(take[0, :, 0])).tolist())
    gen_nll = nll[len(seed_ids) - 1 :]
    grams = [tuple(ids[i : i + 4]) for i in range(len(ids) - 3)]
    distinct4 = len(set(grams)) / max(1, len(grams))

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "text.txt").write_text(seed + text)
    (a.out / "tokens.json").write_text(json.dumps({"ids": ids, "step_pos": list(range(1, len(ids) + 1))}))
    (a.out / "insights.json").write_text("[]")
    state = {"op": a.op, "layer": a.layer, "alpha": a.alpha, "schedule": sched.describe(),
             "keep_norm": a.keep_norm, "anchor": a.anchor, "fired": fired,
             "model": a.model, "temp": a.temp, "top_p": a.top_p, "rng_seed": a.rng_seed,
             "concept_a": a.concept_a, "concept_b": a.concept_b, "cos_ab": cos_ab,
             "state_scale": round(state_scale, 4),
             "clean_nll_mean": round(float(np.mean(gen_nll)), 4),
             "clean_nll_p90": round(float(np.percentile(gen_nll, 90)), 4),
             "distinct4": round(distinct4, 4)}
    (a.out / "state.json").write_text(json.dumps(state, indent=2))
    (a.out / "run.json").write_text(json.dumps(
        {"seed": seed, "summary": {"n_tokens": len(ids), "n_events": 0, "n_reviews": 0,
                                   "n_insights": 0, "n_reseeds": 0},
         "events": [], "regime_switches": [], "reseeds": [], "state": state}, indent=2))
    print(f"{a.out.name}: {len(ids)} tokens, op={a.op} L{a.layer} alpha={a.alpha} fired={fired}, "
          f"clean_nll={state['clean_nll_mean']}, distinct4={state['distinct4']}, {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
