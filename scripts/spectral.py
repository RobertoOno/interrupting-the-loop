#!/usr/bin/env python3
"""H3 measurement (phase 5): the spectrum of orbits. Replay dream-format
cells through the model, capture the layer-L trajectory, and compare the
STATE autocorrelation A_state(tau) = mean_t <h_t, h_{t+tau}> (unit-normed,
mean-centered states) against the TOKEN autocorrelation A_tok(tau) =
fraction of positions where token_t == token_{t+tau} (ground truth of the
literal orbit). Prints, per cell, the dominant period and prominence of
each; saves the curves to <out>/<cell>.npz.

The H3-founding question: do habituated cells (flat A_tok) still show
state periodicity — a silent orbit underneath?

    python scripts/spectral.py --out runs/spectral --layer 18 \
        --cells runs/state_band/tr_L30_a4_s0 runs/state_pulse/p0_habit ...
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from state_inject import refuse_if_other_model


def stream_ids(cell: Path, tokenizer) -> list[int]:
    run = json.loads((cell / "run.json").read_text())
    seed_ids = tokenizer.encode(run["seed"])
    tok = cell / "tokens.json"
    if tok.exists():
        return seed_ids + json.loads(tok.read_text())["ids"]
    text = (cell / "text.txt").read_text()
    gen = text[len(run["seed"]):] if text.startswith(run["seed"]) else text
    return seed_ids + tokenizer.encode(gen, add_special_tokens=False)


def autocorr_state(H: np.ndarray, max_lag: int) -> np.ndarray:
    Hc = H - H.mean(axis=0, keepdims=True)
    Hc /= (np.linalg.norm(Hc, axis=1, keepdims=True) + 1e-8)
    n = len(Hc)
    return np.array([float((Hc[:n - t] * Hc[t:]).sum(axis=1).mean())
                     for t in range(1, max_lag + 1)])


def autocorr_tok(ids: list[int], max_lag: int) -> np.ndarray:
    a = np.asarray(ids)
    n = len(a)
    return np.array([float((a[:n - t] == a[t:]).mean()) for t in range(1, max_lag + 1)])


def dominant(curve: np.ndarray, min_period: int = 5, smooth: int = 21):
    """(period, prominence) of the strongest LOCAL peak after detrending:
    subtract a running-median baseline (window `smooth`) so short-lag
    smoothness and slow drifts don't masquerade as periodicity; then take
    the highest detrended local maximum at lag >= min_period."""
    pad = smooth // 2
    padded = np.pad(curve, pad, mode="edge")
    base = np.array([np.median(padded[i:i + smooth]) for i in range(len(curve))])
    d = curve - base
    best_lag, best = 0, 0.0
    for i in range(min_period - 1, len(d) - 1):
        if d[i] > d[i - 1] and d[i] >= d[i + 1] and d[i] > best:
            best, best_lag = float(d[i]), i + 1
    return best_lag, best


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cells", nargs="+", required=True)
    p.add_argument("--out", type=Path, default=Path("runs/spectral"))
    p.add_argument("--layer", type=int, default=18)
    p.add_argument("--max-lag", type=int, default=300)
    p.add_argument("--model", default="~/models/mlx/Qwen3-8B-Base-8bit")
    a = p.parse_args()
    refuse_if_other_model(a.out)

    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.models.base import create_attention_mask as cam
    from mlx_lm.models.cache import make_prompt_cache as mpc

    model, tokenizer = load(str(Path(a.model).expanduser()))
    inner = model.model
    a.out.mkdir(parents=True, exist_ok=True)
    print(f"{'célula':>28} | {'P_tok':>5} {'prom_tok':>8} | {'P_est':>5} {'prom_est':>8}")
    for cd in a.cells:
        cell = Path(cd)
        t0 = time.time()
        ids = stream_ids(cell, tokenizer)
        cache, states = mpc(model), []
        for s in range(0, len(ids), 512):
            x = mx.array([ids[s: s + 512]])
            h = inner.embed_tokens(x)
            m = cam(h, cache[0])
            for li, (layer_m, c) in enumerate(zip(inner.layers, cache)):
                h = layer_m(h, m, c)
                if li == a.layer:
                    g = h[0].astype(mx.float32)
                    mx.eval(g)
                    states.append(np.asarray(g))
        H = np.concatenate(states, axis=0)[1:]
        A_s = autocorr_state(H, a.max_lag)
        A_t = autocorr_tok(ids[1:], a.max_lag)
        ps, prs = dominant(A_s)
        pt, prt = dominant(A_t)
        name = f"{cell.parent.name}/{cell.name}"
        np.savez_compressed(a.out / f"{cell.parent.name}__{cell.name}.npz",
                            a_state=A_s, a_tok=A_t, layer=a.layer)
        print(f"{name:>28} | {pt:5d} {prt:8.3f} | {ps:5d} {prs:8.3f}   ({len(ids)} tok, {time.time()-t0:.0f}s)", flush=True)
    print("SPECTRAL DONE", flush=True)


if __name__ == "__main__":
    main()
