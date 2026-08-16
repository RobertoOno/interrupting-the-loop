#!/usr/bin/env python3
"""Where in the network does the stream freeze, and where does an interruption
reach? Residual-stream capture over a finished reverie: for every cell, one
forward pass over the stream's own tokens (the KV cache makes it exact and
chunked), capturing at selected layers

  - window vectors: mean-pooled hidden state over W-token windows (stride S)
    at each captured layer  -> per-layer trajectory geometry, per-layer
    novelty of judged windows;
  - logit lens per token: entropy of norm+lm_head applied to each captured
    layer, and the "commitment layer" — the first captured layer whose top-1
    already equals the final top-1 (how early the model decides).

Writes <run_dir>/hidden/<cell>.npz. Analysis in hidden_analysis.py.

    python scripts/hidden_states.py runs/dream_scaffold --cells s6_bare s6_bare_reseed s6_scaffold0
    python scripts/hidden_states.py runs/dream_b2 --conds bare_habit clock_reenc --seeds s0 s1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def stream_ids(cell_dir: Path, tokenizer) -> tuple[list[int], int]:
    """Token ids of the whole stream (seed + generated + injected) and the
    number of seed tokens. Exact when tokens.json exists (battery 2+); older
    cells are re-encoded from text.txt."""
    run = json.loads((cell_dir / "run.json").read_text())
    seed_ids = tokenizer.encode(run["seed"])
    tok = cell_dir / "tokens.json"
    if tok.exists():
        return seed_ids + json.loads(tok.read_text())["ids"], len(seed_ids)
    text = (cell_dir / "text.txt").read_text()
    gen = text[len(run["seed"]):] if text.startswith(run["seed"]) else text
    return seed_ids + tokenizer.encode(gen, add_special_tokens=False), len(seed_ids)


def forward_capture(model, ids: list[int], layers: list[int], chunk: int = 512):
    """Run the stream through the model in chunks with a KV cache; return
    (hidden[l] -> (n, d) float16 arrays for captured layers, lens_entropy
    (n, L), commit_layer (n,), final_entropy (n,), final_top1 (n,))."""
    import mlx.core as mx
    from mlx_lm.models.base import create_attention_mask
    from mlx_lm.models.cache import make_prompt_cache

    inner = model.model
    cache = make_prompt_cache(model)
    n_layers = len(inner.layers)
    layers = [l for l in layers if 0 <= l < n_layers]
    if (n_layers - 1) not in layers:
        layers = layers + [n_layers - 1]
    want = set(layers)

    def head(h):
        h = inner.norm(h)
        if model.args.tie_word_embeddings:
            return inner.embed_tokens.as_linear(h)
        return model.lm_head(h)

    hidden = {l: [] for l in layers}
    lens_ent, commit, fin_ent, fin_top = [], [], [], []
    for s in range(0, len(ids), chunk):
        x = mx.array([int(t) for t in ids[s : s + chunk]])[None]
        h = inner.embed_tokens(x)
        mask = create_attention_mask(h, cache[0])
        caps = {}
        for li, (layer, c) in enumerate(zip(inner.layers, cache)):
            h = layer(h, mask, c)
            if li in want:
                caps[li] = h
        # logit lens at every captured layer (final layer included). Evaluate per
        # layer and drop the logits at once: 13 lazily-held fp32 logit tensors of
        # 151k vocab would otherwise pile up (GBs) and push the weights into swap.
        ents, tops = [], []
        for li in layers:
            logits = head(caps[li])[0].astype(mx.float32)
            lp = logits - mx.logsumexp(logits, axis=-1, keepdims=True)
            ent = -mx.sum(mx.exp(lp) * lp, axis=-1)
            top = mx.argmax(logits, axis=-1)
            mx.eval(ent, top)
            ents.append(np.asarray(ent)); tops.append(np.asarray(top))
            hidden[li].append(np.asarray(caps[li][0].astype(mx.float16)))
            del logits, lp, ent, top
        ents = np.stack(ents, axis=1)   # (n, L)
        tops = np.stack(tops, axis=1)   # (n, L)
        final_top = tops[:, -1]
        agree = tops == final_top[:, None]                       # (n, L)
        # commitment layer (index into `layers`): 'stable' = the captured layer from which
        # the top-1 never changes again (0 = decided from the start, L-1 = only at the end)
        L = agree.shape[1]
        any_false = (~agree).any(axis=1)
        k = np.argmax(~agree[:, ::-1], axis=1)                    # first disagreement counted from the end
        stable = np.where(any_false, L - k, 0)
        lens_ent.append(ents); commit.append(stable); fin_ent.append(ents[:, -1]); fin_top.append(final_top)
        mx.eval(h)
        del caps
        mx.clear_cache()  # return freed buffers to the OS between chunks
    out = {l: np.concatenate(v, axis=0) for l, v in hidden.items()}
    return out, np.concatenate(lens_ent), np.concatenate(commit), np.concatenate(fin_ent), np.concatenate(fin_top), layers


def injection_points(cell_dir: Path, tokenizer, n_seed: int) -> list[tuple[int, int]]:
    """(stream position of the injection, number of injected tokens) per reseed.
    Exact from 'pos' (battery 2+); reconstructed for older cells as step +
    injected tokens so far (a few tokens off where re-encoding differs)."""
    run = json.loads((cell_dir / "run.json").read_text())
    pts, injected = [], 0
    for r in run.get("reseeds", []):
        step, text = r[0], r[1]
        meta = r[2] if len(r) > 2 and isinstance(r[2], dict) else {}
        n_inj = len(tokenizer.encode(text, add_special_tokens=False))
        pos = meta["pos"] if "pos" in meta else step + injected
        pts.append((n_seed + pos, n_inj))
        injected += n_inj
    return pts


def premise_vectors(H: dict, layers: list[int], n_seed: int) -> dict:
    """Mean state of the seed tokens per layer (position 0 excluded: attention sink)."""
    out = {}
    for l in layers:
        v = H[l][1:n_seed].astype(np.float32).mean(axis=0) if n_seed > 1 else H[l][:n_seed].astype(np.float32).mean(axis=0)
        out[l] = v / (np.linalg.norm(v) + 1e-6)
    return out


def interruption_depth(H: dict, layers: list[int], points: list[tuple[int, int]], n_total: int, w: int = 64, rng=None, prem: dict | None = None):
    """Per injection and per layer: (a) cosine distance between the mean
    state of the w tokens before the injection and the w tokens after it
    (skipping the injected text); (b) change in cosine similarity to the
    premise state (after − before). Same for matched random positions."""
    def unit(v):
        return v / (np.linalg.norm(v) + 1e-6)
    def delta(p_before_end: int, p_after_start: int):
        row, ret = [], []
        for l in layers:
            a = unit(H[l][p_before_end - w : p_before_end].astype(np.float32).mean(axis=0))
            b = unit(H[l][p_after_start : p_after_start + w].astype(np.float32).mean(axis=0))
            row.append(1.0 - float(a @ b))
            if prem is not None:
                ret.append(float(b @ prem[l]) - float(a @ prem[l]))
        return row, ret
    inj, ctrl, inj_ret, ctrl_ret = [], [], [], []
    for p, n_inj in points:
        if p - w < 0 or p + n_inj + w > n_total:
            continue
        d, r = delta(p, p + n_inj); inj.append(d); inj_ret.append(r)
    rng = rng or np.random.default_rng(0)
    for _ in range(max(len(inj), 8)):
        q = int(rng.integers(w, n_total - w))
        d, r = delta(q, q); ctrl.append(d); ctrl_ret.append(r)
    L = len(layers)
    return (np.array(inj).reshape(-1, L), np.array(ctrl).reshape(-1, L),
            np.array(inj_ret).reshape(-1, L if prem is not None else 0), np.array(ctrl_ret).reshape(-1, L if prem is not None else 0))


def pool_windows(H: np.ndarray, n_seed: int, w: int, stride: int) -> tuple[np.ndarray, list[int]]:
    """Mean-pool the generated part in windows; returns (n_win, d) unit vectors and window end positions."""
    G = H[n_seed:].astype(np.float32)
    ends, vecs = [], []
    for start in range(0, max(1, len(G) - w + 1), stride):
        v = G[start : start + w].mean(axis=0)
        vecs.append(v / (np.linalg.norm(v) + 1e-6)); ends.append(start + w)
    return np.stack(vecs), ends


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir", type=Path)
    p.add_argument("--cells", nargs="*", default=None)
    p.add_argument("--conds", nargs="*", default=None)
    p.add_argument("--seeds", nargs="*", default=None, help="seed prefixes, e.g. s0 s6")
    p.add_argument("--model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    p.add_argument("--layers", default="0,4,8,12,16,20,24,28,32,36,40,44,47")
    p.add_argument("--window", type=int, default=64)
    p.add_argument("--stride", type=int, default=32)
    p.add_argument("--chunk", type=int, default=256)
    p.add_argument("--max-tokens", type=int, default=0, help="truncate the stream (debug)")
    args = p.parse_args()

    from mlx_lm import load
    model, tokenizer = load(str(Path(args.model).expanduser()))
    layers = [int(x) for x in args.layers.split(",")]
    out_dir = args.run_dir / "hidden"
    out_dir.mkdir(exist_ok=True)

    cells = sorted(d for d in args.run_dir.iterdir() if d.is_dir() and (d / "run.json").exists())
    if args.cells:
        cells = [d for d in cells if d.name in set(args.cells)]
    if args.conds:
        cells = [d for d in cells if d.name.split("_", 1)[1] in set(args.conds)]
    if args.seeds:
        cells = [d for d in cells if d.name.split("_", 1)[0] in set(args.seeds)]
    print(f"{len(cells)} cells, layers {layers}", flush=True)
    for d in cells:
        out = out_dir / f"{d.name}.npz"
        if out.exists():
            print(f"skip {d.name}"); continue
        t0 = time.time()
        ids, n_seed = stream_ids(d, tokenizer)
        if args.max_tokens:
            ids = ids[: args.max_tokens]
        H, lens_ent, commit, fin_ent, fin_top, used = forward_capture(model, ids, layers, args.chunk)
        pooled, ends = {}, None
        prem = premise_vectors(H, used, n_seed)
        for l in used:
            pooled[f"win_L{l}"], ends = pool_windows(H[l], n_seed, args.window, args.stride)
            pooled[f"win_prem_L{l}"] = pooled[f"win_L{l}"] @ prem[l]   # similarity of every window to the premise state
        pts = injection_points(d, tokenizer, n_seed)
        inj_delta, ctrl_delta, inj_ret, ctrl_ret = interruption_depth(H, used, pts, len(ids), args.window, prem=prem)
        pooled["inj_delta"], pooled["ctrl_delta"], pooled["inj_return"], pooled["ctrl_return"] = inj_delta, ctrl_delta, inj_ret, ctrl_ret
        pooled["inj_pos"] = np.array([p for p, _ in pts])
        pooled["inj_len"] = np.array([n for _, n in pts])
        # per-window commitment / lens entropy summaries over the generated part
        gen_commit = commit[n_seed:]; gen_lens = lens_ent[n_seed:]; gen_fin = fin_ent[n_seed:]
        win_commit = np.array([gen_commit[e - args.window : e].mean() for e in ends])
        win_lens = np.stack([gen_lens[e - args.window : e].mean(axis=0) for e in ends])
        win_fin = np.array([gen_fin[e - args.window : e].mean() for e in ends])
        np.savez_compressed(out, layers=np.array(used), n_seed=n_seed, n_ids=len(ids), window=args.window, stride=args.stride,
                            win_ends=np.array(ends), win_commit=win_commit, win_lens_entropy=win_lens, win_final_entropy=win_fin,
                            tok_commit=commit.astype(np.int16), tok_lens_entropy=lens_ent.astype(np.float16),
                            tok_final_entropy=fin_ent.astype(np.float16), **pooled)
        print(f"{d.name}: {len(ids)} tokens, {len(ends)} windows, {time.time()-t0:.0f}s -> {out.name}", flush=True)


if __name__ == "__main__":
    main()
