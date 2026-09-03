#!/usr/bin/env python3
"""T5 — the cross-mind whisper, part 2: a PyTorch proposer for frontier_search
with the paper-4 guarded pulse applied during proposal generation.

PulseProposer(model_id, dirs=None, alpha=2.0, guard=True, every=300, burst=32,
              layer=-1, temp=1.0, min_p=0.05)
  .generate(prompt, max_tokens, n) -> list[str]   n samples in one batch, same prompt
Directions rotate per burst; bursts start at generated token 1 (k = 0, 1, ...),
so the idea enters before the program's structure is fixed. The anchor is the
prompt's mean state at the layer; the dose unit is that state's norm.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from creative_machine import state_ops as so  # noqa: E402


class PulseProposer:
    def __init__(self, model_id, dirs=None, alpha=2.0, guard=True, every=300, burst=32, layer=-1, temp=1.0, min_p=0.05):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.dev = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        dtype = torch.bfloat16 if self.dev == "cuda" else (torch.float16 if self.dev == "mps" else torch.float32)
        self.tok = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=dtype).to(self.dev).eval()
        n = self.model.config.num_hidden_layers
        self.L = layer if layer >= 0 else n // 2
        self.dirs = [torch.tensor(np.asarray(d, dtype=np.float32), device=self.dev) for d in (dirs or [])]
        self.alpha, self.guard, self.every, self.burst = alpha, guard, every, burst
        self.temp, self.min_p = temp, min_p
        self.op = {"fn": None}
        self.fired = 0

        def hook(_m, _args, output):
            if self.op["fn"] is None:
                return output
            if isinstance(output, tuple):
                return (self.op["fn"](output[0]),) + tuple(output[1:])
            return self.op["fn"](output)
        self.model.model.layers[self.L].register_forward_hook(hook)

    def _install(self, step, prem, scale):
        """Pulse schedule: bursts of `burst` tokens at the start of each `every` window, from token 1."""
        if not self.dirs or self.alpha == 0:
            self.op["fn"] = None; return
        k, r = divmod(step - 1, self.every)
        if r >= self.burst:
            self.op["fn"] = None; return
        v = self.dirs[k % len(self.dirs)]
        torch, guard, alpha = self.torch, self.guard, self.alpha

        def fn(h):
            hf = h.float()
            pre = so.norms(hf, torch)
            tgt = so.coord(hf, prem, torch)
            hf = so.translate(hf, v, alpha * scale)
            if guard:
                hf = so.restore_coord(hf, prem, tgt, torch)
                hf = so.renorm(hf, pre, torch)
            return hf.to(h.dtype)
        self.op["fn"] = fn
        self.fired += 1

    def plain(self, prompt, max_tokens):
        """One completion with the pulse switched off (recap / agenda writers)."""
        saved, self.dirs = self.dirs, []
        try:
            return self.generate(prompt, max_tokens, n=1)[0]
        finally:
            self.dirs = saved

    def generate(self, prompt, max_tokens, n=1):
        torch = self.torch
        ids = self.tok(prompt, return_tensors="pt").input_ids.to(self.dev)
        self.op["fn"] = None
        with torch.no_grad():
            out = self.model(ids, use_cache=True, output_hidden_states=True)
            hs = out.hidden_states[self.L + 1][0]
            prem_v = hs[1:].float().mean(0) if hs.shape[0] > 1 else hs.mean(0)
            scale = float(prem_v.norm().item()); prem = prem_v / (prem_v.norm() + 1e-12)
            past = out.past_key_values
            logits = out.logits[0, -1].float()
        # replicate the cache for n rows
        B = n
        if hasattr(past, "batch_repeat_interleave"):
            past.batch_repeat_interleave(B)
        else:
            past = tuple(tuple(t.repeat(B, 1, 1, 1) for t in layer) for layer in past)
        logits = logits[None].repeat(B, 1)
        eos = self.tok.eos_token_id
        seqs = [[] for _ in range(B)]; alive = [True] * B
        for step in range(1, max_tokens + 1):
            probs = torch.softmax(logits / max(self.temp, 1e-6), dim=-1)
            if self.min_p > 0:
                top = probs.max(dim=-1, keepdim=True).values
                probs = torch.where(probs >= self.min_p * top, probs, torch.zeros_like(probs))
                probs = probs / probs.sum(-1, keepdim=True)
            nxt = torch.multinomial(probs, 1)[:, 0]
            for b in range(B):
                if alive[b]:
                    t = int(nxt[b].item())
                    if t == eos:
                        alive[b] = False
                    else:
                        seqs[b].append(t)
            if not any(alive) or step == max_tokens:
                break
            self._install(step + 1, prem, scale)
            with torch.no_grad():
                out = self.model(nxt[:, None], past_key_values=past, use_cache=True)
            self.op["fn"] = None
            past = out.past_key_values
            logits = out.logits[:, -1].float()
        return [self.tok.decode(s) for s in seqs]
