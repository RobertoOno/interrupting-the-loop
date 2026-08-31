#!/usr/bin/env python3
"""PyTorch/transformers twin of state_inject.py (phase 5 generality port).

Same physics, different backend: a forward hook on decoder layer L applies
the state operators (creative_machine.state_ops with xp=torch — verified
bit-identical to the numpy backend) during a manual generation loop with
KV cache. Cells come out in the dream format, with the same state.json
(clean NLL under the untouched model, distinct-4).

Arms ported for the generality test: none / translate (continuous) /
pulse (translate bursts, rotating paper-1 kick directions, guards) /
prompt (text-injection control). Habituation identical (512 / ln 1.15).

    python scripts/torch_state.py --out runs/torch_smoke/none --op none \
        --model Qwen/Qwen3-0.6B-Base --max-tokens 96
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter, deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from creative_machine import state_ops as so
from state_inject import refuse_if_other_model


def pick_device(model_id: str):
    """Three-case dtype policy, both halves learned the hard way (2026-08-31):
    natively-quantized checkpoints (gpt-oss mxfp4) need 'auto' — a forced
    bfloat16 dequantizes them past VRAM; full-precision checkpoints (OLMo-2
    ships fp32) need a bf16 CAP — 'auto' doubles them past VRAM."""
    import torch
    from transformers import AutoConfig
    quant = getattr(AutoConfig.from_pretrained(model_id), "quantization_config", None)
    if torch.cuda.is_available():
        return "cuda", ("auto" if quant is not None else torch.bfloat16)
    if torch.backends.mps.is_available():
        return "mps", torch.float16
    return "cpu", torch.float32


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--model", default="Qwen/Qwen3-0.6B-Base")
    p.add_argument("--seed-text", default=None)
    p.add_argument("--seed-index", type=int, default=0)
    p.add_argument("--op", choices=["none", "translate", "pulse", "prompt"], default="none")
    p.add_argument("--layer", type=int, default=18)
    p.add_argument("--alpha", type=float, default=0.0)
    p.add_argument("--concept-a", default=None)
    p.add_argument("--inject-rotate", action="store_true")
    p.add_argument("--inject-every", type=int, default=300)
    p.add_argument("--pulse-len", type=int, default=32)
    p.add_argument("--anchor", action="store_true")
    p.add_argument("--keep-norm", action="store_true")
    p.add_argument("--habit", action="store_true")
    p.add_argument("--max-tokens", type=int, default=1500)
    p.add_argument("--temp", type=float, default=1.0)
    p.add_argument("--top-p", type=float, default=0.95)
    p.add_argument("--rng-seed", type=int, default=0)
    a = p.parse_args()
    refuse_if_other_model(a.out)

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from creative_machine.dream import DreamConfig
    from dream_run import SEEDS

    device, dtype = pick_device(a.model)
    torch.manual_seed(a.rng_seed)
    tok = AutoTokenizer.from_pretrained(a.model)
    if dtype == "auto":
        # natively-quantized checkpoint: device_map keeps mxfp4 on-GPU during
        # load (a plain .to() dequantizes layer by layer and OOMs — H100 lesson #2)
        model = AutoModelForCausalLM.from_pretrained(a.model, torch_dtype="auto",
                                                     device_map="auto").eval()
    else:
        model = AutoModelForCausalLM.from_pretrained(a.model, torch_dtype=dtype).to(device).eval()
    layers = model.model.layers
    n_layers = len(layers)
    L = min(a.layer, n_layers - 2)
    if L != a.layer:
        print(f"[note] layer {a.layer} > model depth; using {L}", flush=True)

    KICKS = list(DreamConfig().kick_seeds)
    seed = a.seed_text if a.seed_text else SEEDS[a.seed_index % len(SEEDS)]
    seed_ids = tok(seed, return_tensors="pt").input_ids[0].tolist()
    ban = [tok.eos_token_id] if tok.eos_token_id is not None else []

    hook_op = {"fn": None}  # the hook applies whatever the loop installs here

    def hook(_m, _args, output):
        if hook_op["fn"] is None:
            return output
        if isinstance(output, tuple):
            return (hook_op["fn"](output[0]),) + tuple(output[1:])
        return hook_op["fn"](output)

    handle = layers[L].register_forward_hook(hook)

    @torch.no_grad()
    def mean_state(text: str) -> np.ndarray:
        ids = tok(text, return_tensors="pt").input_ids.to(device)
        hs = model(ids, output_hidden_states=True).hidden_states[L + 1][0]
        v = hs[1:].float().mean(dim=0) if hs.shape[0] > 1 else hs.mean(dim=0)
        v = v.cpu().numpy().astype(np.float64)
        return v / (np.linalg.norm(v) + 1e-12)

    prem_np = mean_state(seed)
    prem = torch.tensor(prem_np, dtype=torch.float32, device=device)
    v = None
    if a.op in ("translate",):
        assert a.concept_a, "--op translate needs --concept-a"
        d = mean_state(a.concept_a) - prem_np
        v = torch.tensor(d / (np.linalg.norm(d) + 1e-12), dtype=torch.float32, device=device)
    pulse_dirs = []
    if a.op == "pulse":
        for k in KICKS:
            d = mean_state(k) - prem_np
            pulse_dirs.append(torch.tensor(d / (np.linalg.norm(d) + 1e-12),
                                           dtype=torch.float32, device=device))
    inj_pool = [k + " " for k in KICKS] if a.inject_rotate else []
    assert a.op != "prompt" or inj_pool, "--op prompt needs --inject-rotate (ported subset)"

    @torch.no_grad()
    def forward(ids_step, past):
        x = torch.tensor([ids_step], device=device)
        out = model(x, past_key_values=past, use_cache=True)
        return out.logits[0, -1].float(), out.past_key_values

    recent = deque(maxlen=512)

    def sample(logits) -> int:
        lg = logits.clone()
        for t in ban:
            lg[t] = -1e9
        lg = lg / max(a.temp, 1e-6)
        if a.habit and recent:
            counts = Counter(recent)
            idx = torch.tensor(list(counts.keys()), device=lg.device)
            pen = torch.tensor([c * math.log(1.15) for c in counts.values()], device=lg.device)
            lg[idx] = lg[idx] - pen
        if a.top_p < 1.0:
            srt, order = torch.sort(lg, descending=True)
            pmass = torch.softmax(srt, dim=-1).cumsum(dim=-1)
            keep = (pmass - torch.softmax(srt, dim=-1)) < a.top_p
            srt = torch.where(keep, srt, torch.tensor(-1e9, device=lg.device))
            pick = torch.multinomial(torch.softmax(srt, dim=-1), 1).item()
            return int(order[pick].item())
        return int(torch.multinomial(torch.softmax(lg, dim=-1), 1).item())

    def make_op(step: int):
        """Install (or clear) the layer op for this generation step."""
        active_v = None
        if a.op == "translate":
            active_v = v
        elif a.op == "pulse":
            q, r = (step - 1) // a.inject_every, (step - 1) % a.inject_every
            if q >= 1 and r < a.pulse_len:
                active_v = pulse_dirs[(q - 1) % len(pulse_dirs)]
        if active_v is None:
            hook_op["fn"] = None
            return
        def fn(h):
            hf = h.float()
            pre = so.norms(hf, torch)
            tgt = so.coord(hf, prem, torch)
            hf = so.translate(hf, active_v, a.alpha * state_scale)
            if a.anchor:
                hf = so.restore_coord(hf, prem, tgt, torch)
            if a.keep_norm:
                hf = so.renorm(hf, pre, torch)
            return hf.to(h.dtype)
        hook_op["fn"] = fn

    # prefill (no ops on the prompt) + dose unit
    hook_op["fn"] = None
    t0 = time.time()
    with torch.no_grad():
        ids_t = torch.tensor([seed_ids], device=device)
        out = model(ids_t, use_cache=True, output_hidden_states=True)
        past = out.past_key_values
        hs = out.hidden_states[L + 1][0]
        state_scale = float(hs[1:].float().mean(dim=0).norm().item()) if hs.shape[0] > 1 else float(hs.mean(dim=0).norm().item())
        logits = out.logits[0, -1].float()

    tokid = sample(logits)
    ids, gen_mask, step_pos, reseeds, fired = [tokid], [True], [1], [], 0
    recent.append(tokid)
    n_gen = 1
    while n_gen < a.max_tokens:
        step = n_gen + 1
        make_op(step)
        if hook_op["fn"] is not None:
            fired += 1
        logits, past = forward([ids[-1]], past)
        hook_op["fn"] = None
        tokid = sample(logits)
        ids.append(tokid)
        gen_mask.append(True)
        recent.append(tokid)
        n_gen += 1
        step_pos.append(len(ids))
        if a.op == "prompt" and n_gen % a.inject_every == 0 and n_gen < a.max_tokens:
            txt = inj_pool[len(reseeds) % len(inj_pool)]
            tids = tok(txt, add_special_tokens=False).input_ids
            reseeds.append([n_gen, txt, {"pos": len(ids)}])
            logits, past = forward(tids, past)
            ids.extend(tids)
            recent.extend(tids)
            gen_mask.extend([False] * len(tids))
            tokid = sample(logits)
            ids.append(tokid)
            recent.append(tokid)
            gen_mask.append(True)
            n_gen += 1
            step_pos.append(len(ids))
            fired += 1
            continue

    handle.remove()
    text = tok.decode(ids)

    # clean NLL under the untouched model (single fresh forward, no hooks)
    with torch.no_grad():
        full = torch.tensor([seed_ids + ids], device=device)
        lg = model(full).logits[0].float()
        lp = torch.log_softmax(lg, dim=-1)
        tgts = full[0, 1:]
        nll = (-lp[:-1].gather(1, tgts[:, None])[:, 0]).cpu().numpy()
    off = len(seed_ids) - 1
    gen_nll = [float(nll[off + j]) for j in range(len(ids)) if gen_mask[j] and off + j < len(nll)]
    gids = [t for t, m in zip(ids, gen_mask) if m]
    grams = [tuple(gids[i:i + 4]) for i in range(len(gids) - 3)]
    distinct4 = len(set(grams)) / max(1, len(grams))

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "text.txt").write_text(seed + text)
    (a.out / "tokens.json").write_text(json.dumps({"ids": ids, "step_pos": step_pos}))
    (a.out / "insights.json").write_text("[]")
    state = {"backend": "torch", "device": device, "op": a.op, "layer": L, "alpha": a.alpha,
             "anchor": a.anchor, "keep_norm": a.keep_norm, "habit": a.habit, "fired": fired,
             "model": a.model, "temp": a.temp, "top_p": a.top_p, "rng_seed": a.rng_seed,
             "inject_every": a.inject_every if a.op in ("prompt", "pulse") else None,
             "pulse_len": a.pulse_len if a.op == "pulse" else None,
             "state_scale": round(state_scale, 4),
             "clean_nll_mean": round(float(np.mean(gen_nll)), 4),
             "clean_nll_p90": round(float(np.percentile(gen_nll, 90)), 4),
             "distinct4": round(distinct4, 4)}
    (a.out / "state.json").write_text(json.dumps(state, indent=2))
    (a.out / "run.json").write_text(json.dumps(
        {"seed": seed, "summary": {"n_tokens": len(ids), "n_events": 0, "n_reviews": 0,
                                   "n_insights": 0, "n_reseeds": len(reseeds)},
         "events": [], "regime_switches": [], "reseeds": reseeds, "state": state}, indent=2))
    print(f"{a.out.name}: {len(ids)} tokens [{device}], op={a.op} L{L} alpha={a.alpha} "
          f"fired={fired}, clean_nll={state['clean_nll_mean']}, distinct4={state['distinct4']}, "
          f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
