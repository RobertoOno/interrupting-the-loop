#!/usr/bin/env python3
"""Testbed B instrument (phase 5): verified code generation with state
operators — bin-packing notebooks in the battery-C format, so
`consolidate.py verify` reads the output unchanged and the verifier (not a
judge) does the scoring: valid rate, finds vs the classics, tails.

The carrier mirrors battery C: premise + habituation (512 / 1.15) + the
ANGLES text prompts every 250 tokens outside open functions — in EVERY arm.
State ops ride on top during generation: translation bursts toward the
ANGLES' own state directions (or the paper-1 kicks), or EMA repulsion.

    python scripts/state_code.py --out runs/state_code/none --op none \
        --variants train --n 2 --tokens 1500
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from creative_machine import state_ops as so
from creative_machine.problem_premises import (ANGLES, FAR_VARIANTS, VARIANTS_C_TRAIN,
                                               premise, premise_far)
from problem_loop import inside_open_function
from state_inject import concept_vector, head_logits, refuse_if_other_model, sample_token


def variant_premises(which: str) -> list[str]:
    if which == "train":
        return [premise(lo, hi) for lo, hi in VARIANTS_C_TRAIN]
    if which == "far":
        return [premise_far(desc) for _name, desc in FAR_VARIANTS]
    raise SystemExit(f"unknown variants set {which}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--model", default="~/models/mlx/Qwen3-8B-Base-8bit")
    p.add_argument("--variants", choices=["train", "far"], default="train")
    p.add_argument("--n", type=int, default=2, help="notebooks per variant")
    p.add_argument("--tokens", type=int, default=1500)
    p.add_argument("--op", choices=["none", "pulse", "repel"], default="none")
    p.add_argument("--pulse-op", choices=["translate", "rotate"], default="translate")
    p.add_argument("--pulse-source", choices=["angles", "kicks"], default="angles")
    p.add_argument("--layer", type=int, default=18)
    p.add_argument("--alpha", type=float, default=2.0)
    p.add_argument("--inject-every", type=int, default=300)
    p.add_argument("--pulse-len", type=int, default=32)
    p.add_argument("--anchor", action="store_true")
    p.add_argument("--keep-norm", action="store_true")
    p.add_argument("--repel-halflife", type=int, default=128)
    p.add_argument("--rng-seed", type=int, default=0)
    a = p.parse_args()
    refuse_if_other_model(a.out)

    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.models.base import create_attention_mask as cam
    from mlx_lm.models.cache import make_prompt_cache as mpc

    from creative_machine.dream import DreamConfig

    model, tokenizer = load(str(Path(a.model).expanduser()))
    inner = model.model
    a.out.mkdir(parents=True, exist_ok=True)
    prems = variant_premises(a.variants)
    pool_texts = ANGLES if a.pulse_source == "angles" else list(DreamConfig().kick_seeds)

    def generate(seed_text: str, cell_rng: np.random.Generator) -> str:
        mx.random.seed(int(cell_rng.integers(0, 2 ** 31)))
        prem_np = concept_vector(model, tokenizer, seed_text, a.layer, mx, cam, mpc)
        prem = mx.array(prem_np.astype(np.float32))
        dirs = []
        if a.op == "pulse":
            for t in pool_texts:
                vk = concept_vector(model, tokenizer, t, a.layer, mx, cam, mpc)
                d = vk - prem_np
                dirs.append(mx.array((d / (np.linalg.norm(d) + 1e-12)).astype(np.float32)))
            planes = ([so.orthonormal_pair(prem, v, mx) for v in dirs]
                      if a.pulse_op == "rotate" else None)
        cache = mpc(model)
        seed_ids = tokenizer.encode(seed_text)
        # prefill and premise-state scale (dose unit), as in state_inject
        from state_inject import forward_chunked
        h, vs, vn = forward_chunked(model, cache, seed_ids, a.layer, mx, cam)
        state_scale = float(np.linalg.norm(np.asarray(vs)) / max(1, vn))
        mu = mx.array((prem_np * state_scale).astype(np.float32))
        lam = 1.0 - 0.5 ** (1.0 / max(1, a.repel_halflife))
        ban = sorted(tokenizer.eos_token_ids) if getattr(tokenizer, "eos_token_ids", None) else []

        from collections import deque
        recent = deque(maxlen=512)
        text, ids, n_gen, next_angle = seed_text, [], 0, 250
        ang_i = int(cell_rng.integers(0, len(ANGLES)))

        def feed(tids):
            x = mx.array([tids])
            hh = inner.embed_tokens(x)
            m = cam(hh, cache[0])
            for layer_m, c in zip(inner.layers, cache):
                hh = layer_m(hh, m, c)
            return hh

        tok = sample_token(head_logits(model, h, mx), 1.0, 0.95, ban, mx, recent=recent)
        ids.append(tok); recent.append(tok); n_gen = 1
        while n_gen < a.tokens:
            step = n_gen + 1
            x = mx.array([[ids[-1]]])
            hh = inner.embed_tokens(x)
            m = cam(hh, cache[0])
            for li, (layer_m, c) in enumerate(zip(inner.layers, cache)):
                hh = layer_m(hh, m, c)
                if li == a.layer:
                    if a.op == "repel":
                        mu = (1.0 - lam) * mu + lam * hh[0, -1].astype(mx.float32)
                        hf = hh.astype(mx.float32)
                        tgt = so.coord(hf, prem, mx)
                        hf = so.repel(hf, mu, a.alpha * state_scale, mx)
                        if a.anchor:
                            hf = so.restore_coord(hf, prem, tgt, mx)
                        hh = hf.astype(hh.dtype)
                    elif a.op == "pulse":
                        q, r = (step - 1) // a.inject_every, (step - 1) % a.inject_every
                        if q >= 1 and r < a.pulse_len:
                            hf = hh.astype(mx.float32)
                            pre_norm = so.norms(hf, mx)
                            tgt = so.coord(hf, prem, mx)
                            k = (q - 1) % len(dirs)
                            if a.pulse_op == "translate":
                                hf = so.translate(hf, dirs[k], a.alpha * state_scale)
                            else:
                                hf = so.rotate(hf, planes[k][0], planes[k][1], a.alpha, mx)
                            if a.anchor:
                                hf = so.restore_coord(hf, prem, tgt, mx)
                            if a.keep_norm:
                                hf = so.renorm(hf, pre_norm, mx)
                            hh = hf.astype(hh.dtype)
            tok = sample_token(head_logits(model, hh, mx), 1.0, 0.95, ban, mx, recent=recent)
            ids.append(tok); recent.append(tok); n_gen += 1
            if n_gen >= next_angle:
                text_now = seed_text + tokenizer.decode(ids)
                if not inside_open_function(text_now):
                    next_angle += 250
                    ang_i = (ang_i + 1) % len(ANGLES)
                    tids = tokenizer.encode("\n\n" + ANGLES[ang_i] + "\n", add_special_tokens=False)
                    h_after = feed(tids)
                    ids.extend(tids); recent.extend(tids)
                    tok = sample_token(head_logits(model, h_after, mx), 1.0, 0.95, ban, mx, recent=recent)
                    ids.append(tok); recent.append(tok); n_gen += 1
            if n_gen % 512 == 0:
                mx.clear_cache()
        return seed_text + tokenizer.decode(ids)

    for vi in range(len(prems)):
        for nb in range(a.n):
            key = f"{a.variants}_v{vi}_n{nb}"
            outf = a.out / f"{key}.txt"
            if outf.exists():
                print(f"skip {key}", flush=True)
                continue
            rng = np.random.default_rng(a.rng_seed * 100003 + vi * 101 + nb)
            t0 = time.time()
            outf.write_text(generate(prems[vi], rng))
            print(f"{a.out.name} {key}: {time.time() - t0:.0f}s", flush=True)
    print(f"STATE-CODE DONE {a.out.name}", flush=True)


if __name__ == "__main__":
    main()
