#!/usr/bin/env python3
"""Route recorder (phase 5, operator 7 — route blocking). For each variant,
find the notebook holding the variant's best candidate in a finished arm,
replay it through the model, and save the route: the top-k principal
directions of the layer-L trajectory (centered states, SVD), orthonormal
rows, float32 .npy — `route_{which}_v{vi}.npy` plus a meta json.

    python scripts/route_record.py --from-arm runs/state_bconf/none \
        --variants train --layer 18 --k 16 --out runs/routes/none_best
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


def best_notebooks(arm_dir: Path, which: str) -> dict[int, str]:
    cands = json.loads((arm_dir / "candidates.json").read_text())
    best: dict[int, tuple[float, str]] = {}
    for c in cands.values():
        if c.get("ok") and c.get("train") is not None and c["which"] == which:
            gap = c["train"] - min(c["bf_train"], c["ff_train"])
            vi = c["variant"]
            if vi not in best or gap < best[vi][0]:
                best[vi] = (gap, c["notebook"])
    return {vi: nb for vi, (_, nb) in best.items()}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from-arm", type=Path, required=True)
    p.add_argument("--variants", default="train")
    p.add_argument("--layer", type=int, default=18)
    p.add_argument("--k", type=int, default=16)
    p.add_argument("--model", default="~/models/mlx/Qwen3-8B-Base-8bit")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    refuse_if_other_model(a.out)

    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.models.base import create_attention_mask as cam
    from mlx_lm.models.cache import make_prompt_cache as mpc

    model, tokenizer = load(str(Path(a.model).expanduser()))
    inner = model.model
    a.out.mkdir(parents=True, exist_ok=True)
    picks = best_notebooks(a.from_arm, a.variants)
    meta = {}
    for vi, nb in sorted(picks.items()):
        outf = a.out / f"route_{a.variants}_v{vi}.npy"
        if outf.exists():
            print(f"skip v{vi}", flush=True)
            continue
        t0 = time.time()
        ids = tokenizer.encode((a.from_arm / f"{nb}.txt").read_text())
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
        H = np.concatenate(states, axis=0)[1:]          # drop the attention sink
        Hc = H - H.mean(axis=0, keepdims=True)          # route = variation structure
        _, sv, vt = np.linalg.svd(Hc, full_matrices=False)
        basis = vt[: a.k].astype(np.float32)            # orthonormal rows (k, d)
        np.save(outf, basis)
        evr = float((sv[: a.k] ** 2).sum() / (sv ** 2).sum())
        meta[f"{a.variants}_v{vi}"] = {"notebook": nb, "tokens": len(ids), "k": a.k,
                                       "explained_var": round(evr, 4)}
        print(f"v{vi}: {nb} ({len(ids)} tok) -> {outf.name}, var explicada top-{a.k}: {evr:.3f}, {time.time()-t0:.0f}s", flush=True)
    mp = a.out / "routes_meta.json"
    old = json.loads(mp.read_text()) if mp.exists() else {}
    old.update(meta)
    mp.write_text(json.dumps(old, indent=2))
    print("ROUTES DONE", flush=True)


if __name__ == "__main__":
    main()
