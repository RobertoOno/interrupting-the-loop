#!/usr/bin/env python3
"""Where does the reverie go? Trajectories of the stream in sentence-embedding
space, per condition, on the same seed — plus scalar geometry: return to the
premise, explored radius, and loop closures.

Windows of W tokens are embedded (all-mpnet-base-v2), projected with one PCA
fit on ALL runs of the seed (comparable axes), and drawn as a trace. Salience
events (from run.json) are marked; where a rejudge file exists, event windows
are colored by judged surprise. Writes docs/figures/traj_*.png and a table.

    python scripts/trajectories.py runs/dream_scaffold --seed s0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from creative_machine.prompt_space import SentenceEmbedder  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "docs" / "figures"
PAL = {"scaffold0": "#2a78d6", "abl_forget": "#eb6834", "abl_salience": "#1baf7a",
       "bare_reseed": "#eda100", "bare": "#4a3aa7", "none": "#2a78d6", "plain": "#eb6834", "clock": "#1baf7a"}
LABEL = {"scaffold0": "DREAM scaffold", "abl_forget": "salience+forgetting", "abl_salience": "salience only",
         "bare_reseed": "bare+clock reseed", "bare": "bare", "none": "DREAM", "plain": "plain", "clock": "clock"}


def windows(text: str, tokenizer, seed: str, w: int, stride: int):
    gen = text[len(seed):] if text.startswith(seed) else text
    ids = tokenizer.encode(gen, add_special_tokens=False)
    out = []
    for start in range(0, max(1, len(ids) - w + 1), stride):
        out.append((start + w, tokenizer.decode(ids[start:start + w])))
    return out


def geometry(E: np.ndarray, premise: np.ndarray, closure_gap: int = 8, closure_eps: float = 0.35) -> dict:
    """E: (n, d) unit vectors in time order. Cosine distances."""
    d_prem = 1.0 - E @ premise
    centroid = E.mean(axis=0); centroid /= np.linalg.norm(centroid) + 1e-12
    radius = float(np.mean(1.0 - E @ centroid))
    steps = 1.0 - np.sum(E[1:] * E[:-1], axis=1)
    closures = 0
    for i in range(closure_gap, len(E)):
        past = E[: i - closure_gap]
        if len(past) and np.min(1.0 - past @ E[i]) < closure_eps and np.min(1.0 - E[i - closure_gap:i] @ E[i]) > closure_eps:
            closures += 1
    return {
        "n_windows": len(E),
        "min_dist_to_premise_after_half": float(np.min(d_prem[len(E) // 2:])) if len(E) > 2 else float(np.min(d_prem)),
        "mean_dist_to_premise": float(np.mean(d_prem)),
        "final_dist_to_premise": float(d_prem[-1]),
        "explored_radius": radius,
        "mean_step": float(np.mean(steps)) if len(steps) else 0.0,
        "loop_closures": closures,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir", type=Path)
    p.add_argument("--seed", default="s0", help="seed prefix, e.g. s0")
    p.add_argument("--conds", nargs="*", default=None)
    p.add_argument("--window", type=int, default=64)
    p.add_argument("--stride", type=int, default=32)
    p.add_argument("--tokenizer-model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    args = p.parse_args()

    from mlx_lm.utils import load_tokenizer  # tokenizer only: never materialize the weights here
    tokenizer = load_tokenizer(Path(args.tokenizer_model).expanduser())
    embed = SentenceEmbedder()

    cells = sorted(d for d in args.run_dir.iterdir() if d.is_dir() and d.name.startswith(args.seed + "_") and (d / "run.json").exists())
    if args.conds:
        cells = [d for d in cells if d.name.split("_", 1)[1] in args.conds]
    rejudge = {}
    for f in ("rejudge_surprise.json",):
        pth = args.run_dir / f
        if pth.exists():
            for r in json.loads(pth.read_text()):
                rejudge[(r["cell"], r["step"])] = r.get("surprise")

    series = []
    for d in cells:
        run = json.loads((d / "run.json").read_text())
        text = (d / "text.txt").read_text()
        wins = windows(text, tokenizer, run["seed"], args.window, args.stride)
        E = embed([t for _, t in wins])
        premise = embed([run["seed"]])[0]
        cond = d.name.split("_", 1)[1]
        ev = [(e["step"], e["kind"], rejudge.get((d.name, e["step"]))) for e in run["events"]]
        series.append({"cond": cond, "cell": d.name, "steps": [s for s, _ in wins], "E": E, "premise": premise,
                       "events": ev, "reseeds": [r[0] for r in run.get("reseeds", [])], "geom": geometry(E, premise)})

    # common PCA over all runs of this seed
    allE = np.concatenate([s["E"] for s in series] + [series[0]["premise"][None, :]], axis=0)
    mu = allE.mean(axis=0); X = allE - mu
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    P = Vt[:2].T
    prem2 = (series[0]["premise"] - mu) @ P

    n = len(series)
    fig, axes = plt.subplots(1, n, figsize=(3.6 * n, 3.8), squeeze=False)
    for ax, s in zip(axes[0], series):
        Z = (s["E"] - mu) @ P
        c = PAL.get(s["cond"], "#666")
        ax.plot(Z[:, 0], Z[:, 1], color=c, lw=0.9, alpha=0.7)
        ax.scatter(Z[:, 0], Z[:, 1], c=np.linspace(0.15, 1.0, len(Z)), cmap="Greys", s=10, zorder=3, linewidths=0)
        ax.scatter([Z[0, 0]], [Z[0, 1]], marker="o", s=60, facecolor="white", edgecolor=c, zorder=4, label="start")
        ax.scatter([prem2[0]], [prem2[1]], marker="*", s=140, color="#0b0b0b", zorder=5, label="premise")
        # events with judged surprise
        st = np.array(s["steps"])
        for step, kind, sur in s["events"]:
            i = int(np.argmin(np.abs(st - step)))
            if sur is not None:
                ax.scatter([Z[i, 0]], [Z[i, 1]], marker="D", s=30 + 12 * sur, facecolor="none", edgecolor="#e34948", linewidths=1.2, zorder=6)
        for rs in s["reseeds"]:
            i = int(np.argmin(np.abs(st - rs)))
            ax.scatter([Z[i, 0]], [Z[i, 1]], marker="x", s=40, color="#0b0b0b", zorder=6)
        g = s["geom"]
        ax.set_title(f"{LABEL.get(s['cond'], s['cond'])}\nclosures {g['loop_closures']} · radius {g['explored_radius']:.2f} · min→premise {g['min_dist_to_premise_after_half']:.2f}", fontsize=8)
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
    axes[0][0].legend(fontsize=7, frameon=False, loc="lower left")
    fig.suptitle(f"Trajectory of the stream in sentence-embedding space — seed {args.seed} (common PCA; ★ premise, × reseed, ◇ judged event sized by surprise)", fontsize=9, y=1.03)
    fig.tight_layout()
    out = FIG / f"traj_{args.run_dir.name}_{args.seed}.png"
    fig.savefig(out, dpi=200, bbox_inches="tight"); plt.close(fig)
    print("figure ->", out)
    print(f"{'cell':<16} {'windows':>7} {'closures':>8} {'radius':>7} {'min→prem(2nd half)':>19} {'final→prem':>10} {'mean step':>9}")
    for s in series:
        g = s["geom"]
        print(f"{s['cell']:<16} {g['n_windows']:>7} {g['loop_closures']:>8} {g['explored_radius']:>7.3f} {g['min_dist_to_premise_after_half']:>19.3f} {g['final_dist_to_premise']:>10.3f} {g['mean_step']:>9.3f}")


if __name__ == "__main__":
    main()
