#!/usr/bin/env python3
"""Read the residual-stream captures (hidden_states.py) and answer three
questions, with figures and a markdown appendix:

  H1  Where in the network does the stream freeze?  Per-layer trajectory
      geometry (mean step, explored radius) of the window vectors, by condition.
  H2  Which layer's novelty predicts judged surprise?  For every judged window,
      novelty at layer l = cosine distance between the window's mean state and
      the mean state of everything before it; Spearman with judged surprise per
      layer, pooled and within condition. Also the logit-lens commitment layer.
  H3  How deep does an interruption reach?  Cosine distance before/after each
      injection per layer, minus the same at random positions, by condition.

    python scripts/hidden_analysis.py runs/dream_scaffold runs/dream_b2 --tag all
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "docs" / "figures"
PAL = {"scaffold0": "#2a78d6", "abl_forget": "#eb6834", "abl_salience": "#1baf7a", "bare_reseed": "#eda100", "bare": "#4a3aa7",
       "bare_habit": "#7a7a7a", "clock_reenc": "#2a78d6", "clock_premise": "#eb6834", "clock_self": "#1baf7a", "sal_reenc": "#c2185b",
       "clock75": "#9ecae1", "clock300": "#4292c6", "clock600": "#08306b"}
LABEL = {"scaffold0": "DREAM scaffold", "abl_forget": "salience+forgetting", "abl_salience": "salience only",
         "bare_reseed": "bare + clock reseed", "bare": "bare", "bare_habit": "bare + habituation",
         "clock_reenc": "clock: re-encounter", "clock_premise": "clock: premise", "clock_self": "clock: own past",
         "sal_reenc": "salience: re-encounter", "clock75": "clock 75", "clock300": "clock 300", "clock600": "clock 600"}


def boot_ci(x, n=4000, seed=0):
    x = np.asarray(x, dtype=float)
    if len(x) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    m = [rng.choice(x, len(x)).mean() for _ in range(n)]
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def load_cells(run_dirs):
    cells = []
    for rd in run_dirs:
        hid = rd / "hidden"
        if not hid.exists():
            continue
        rej = {}
        rp = rd / "rejudge_surprise.json"
        if rp.exists():
            for r in json.loads(rp.read_text()):
                rej.setdefault(r["cell"], []).append(r)
        for f in sorted(hid.glob("*.npz")):
            z = np.load(f)
            cell = f.stem
            cond = cell.split("_", 1)[1]
            run = json.loads((rd / cell / "run.json").read_text())
            pos_of = {(e["step"], e["kind"]): e.get("pos", e["step"]) for e in run["events"]}
            judged = []
            for r in rej.get(cell, []):
                if r.get("surprise") is None:
                    continue
                judged.append({**r, "end": pos_of.get((r["step"], r["kind"]), r["step"])})
            cells.append({"run": rd.name, "cell": cell, "cond": cond, "z": z, "judged": judged,
                          "layers": [int(l) for l in z["layers"]]})
    return cells


def geometry_per_layer(c):
    out = {}
    for l in c["layers"]:
        W = c["z"][f"win_L{l}"].astype(np.float32)
        steps = 1.0 - np.sum(W[1:] * W[:-1], axis=1)
        cen = W.mean(axis=0); cen /= np.linalg.norm(cen) + 1e-6
        out[l] = {"step": float(steps.mean()), "radius": float(np.mean(1.0 - W @ cen))}
    return out


def judged_features(c, review_tokens=160):
    """Per judged window: novelty per layer (vs all past), local step per layer, commitment, lens entropy."""
    ends = c["z"]["win_ends"]
    rows = []
    for j in c["judged"]:
        e = j["end"]
        cur = (ends > e - review_tokens) & (ends <= e)
        past = ends <= e - review_tokens
        prev = (ends > e - 2 * review_tokens) & (ends <= e - review_tokens)
        if cur.sum() == 0 or past.sum() == 0:
            continue
        feat = {"cond": c["cond"], "cell": c["cell"], "surprise": j["surprise"], "connection": j.get("connection"),
                "coherence": j.get("coherence"), "kind": j["kind"]}
        for l in c["layers"]:
            W = c["z"][f"win_L{l}"].astype(np.float32)
            a = W[cur].mean(axis=0); a /= np.linalg.norm(a) + 1e-6
            b = W[past].mean(axis=0); b /= np.linalg.norm(b) + 1e-6
            feat[f"nov_L{l}"] = float(1.0 - a @ b)
            if prev.sum():
                p = W[prev].mean(axis=0); p /= np.linalg.norm(p) + 1e-6
                feat[f"step_L{l}"] = float(1.0 - a @ p)
        feat["commit"] = float(c["z"]["win_commit"][cur].mean())
        lens = c["z"]["win_lens_entropy"][cur].mean(axis=0)
        for i, l in enumerate(c["layers"]):
            feat[f"lens_L{l}"] = float(lens[i])
        feat["final_entropy"] = float(c["z"]["win_final_entropy"][cur].mean())
        rows.append(feat)
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dirs", nargs="+", type=Path)
    p.add_argument("--tag", default="all")
    p.add_argument("--conds", nargs="*", default=None)
    args = p.parse_args()
    cells = load_cells(args.run_dirs)
    if args.conds:
        cells = [c for c in cells if c["cond"] in set(args.conds)]
    if not cells:
        raise SystemExit("no hidden/*.npz found")
    layers = cells[0]["layers"]
    conds = [c for c in LABEL if any(x["cond"] == c for x in cells)]
    md = [f"# Residual-stream analysis ({args.tag})\n", f"{len(cells)} cells, layers {layers}\n"]

    # ---------------- H1 geometry per layer
    geo = {c["cell"]: geometry_per_layer(c) for c in cells}
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    md.append("\n## H1 — per-layer geometry (mean over cells; 95% bootstrap CI over cells)\n")
    md.append("| condition | n | " + " | ".join(f"radius L{l}" for l in layers) + " |")
    md.append("|---|---|" + "---|" * len(layers))
    for cond in conds:
        cs = [c for c in cells if c["cond"] == cond]
        for ax, key in zip(axes, ("step", "radius")):
            m = [np.mean([geo[c["cell"]][l][key] for c in cs]) for l in layers]
            ci = [boot_ci([geo[c["cell"]][l][key] for c in cs]) for l in layers]
            ax.plot(layers, m, "-o", ms=4, color=PAL.get(cond, "#666"), label=f"{LABEL.get(cond, cond)} (n={len(cs)})")
            ax.fill_between(layers, [a for a, _ in ci], [b for _, b in ci], color=PAL.get(cond, "#666"), alpha=0.12, linewidth=0)
        md.append(f"| {LABEL.get(cond, cond)} | {len(cs)} | " + " | ".join(f"{np.mean([geo[c['cell']][l]['radius'] for c in cs]):.3f}" for l in layers) + " |")
    axes[0].set_title("mean step between consecutive 64-token windows (cosine)", fontsize=9)
    axes[1].set_title("explored radius (mean cosine distance to centroid)", fontsize=9)
    for ax in axes:
        ax.set_xlabel("layer"); ax.grid(alpha=0.25)
    axes[0].legend(fontsize=7, frameon=False)
    fig.suptitle("H1 — where in the network does the stream freeze? residual-stream trajectory geometry per layer", fontsize=10)
    fig.tight_layout(); fig.savefig(FIG / f"hidden_h1_geometry_{args.tag}.png", dpi=170, bbox_inches="tight"); plt.close(fig)

    # ---------------- H2 novelty per layer vs judged surprise
    rows = [r for c in cells for r in judged_features(c)]
    md.append(f"\n## H2 — which layer's novelty predicts judged surprise? ({len(rows)} judged windows)\n")
    if rows:
        def spear(key, subset):
            xs = [r[key] for r in subset if key in r]; ys = [r["surprise"] for r in subset if key in r]
            if len(xs) < 8:
                return float("nan"), float("nan")
            rho, pv = spearmanr(xs, ys)
            return float(rho), float(pv)
        fig, ax = plt.subplots(figsize=(7, 3.8))
        pooled = [spear(f"nov_L{l}", rows)[0] for l in layers]
        ax.plot(layers, pooled, "-o", color="#111", label=f"pooled (n={len(rows)})")
        md.append("| layer | ρ pooled | p | " + " | ".join(f"ρ within {LABEL.get(c, c)}" for c in conds) + " |")
        md.append("|---|---|---|" + "---|" * len(conds))
        within = {}
        for cond in conds:
            sub = [r for r in rows if r["cond"] == cond]
            within[cond] = [spear(f"nov_L{l}", sub)[0] for l in layers]
            if len(sub) >= 8:
                ax.plot(layers, within[cond], "-", alpha=0.7, color=PAL.get(cond, "#666"), label=f"{LABEL.get(cond, cond)} (n={len(sub)})")
        for i, l in enumerate(layers):
            rho, pv = spear(f"nov_L{l}", rows)
            md.append(f"| {l} | {rho:+.2f} | {pv:.1e} | " + " | ".join(f"{within[c][i]:+.2f}" for c in conds) + " |")
        ax.axhline(0, color="#999", lw=0.8); ax.set_xlabel("layer"); ax.set_ylabel("Spearman ρ (novelty at layer, judged surprise)")
        ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25)
        ax.set_title("H2 — novelty of the judged window vs everything before it, per layer, against judged surprise", fontsize=9)
        fig.tight_layout(); fig.savefig(FIG / f"hidden_h2_novelty_{args.tag}.png", dpi=170, bbox_inches="tight"); plt.close(fig)
        rho_c, p_c = spear("commit", rows); rho_f, p_f = spear("final_entropy", rows)
        md.append(f"\nCommitment layer (mean first-agreeing captured layer) vs surprise: ρ={rho_c:+.2f} (p={p_c:.1e}); "
                  f"final entropy vs surprise: ρ={rho_f:+.2f} (p={p_f:.1e}).")
        for cond in conds:
            sub = [r for r in rows if r["cond"] == cond]
            if len(sub) >= 8:
                rc, pc = spear("commit", sub); rf, pf = spear("final_entropy", sub)
                md.append(f"- within {LABEL.get(cond, cond)}: commit ρ={rc:+.2f} (p={pc:.1e}), final entropy ρ={rf:+.2f} (p={pf:.1e}), "
                          f"mean commit {np.mean([r['commit'] for r in sub]):.2f}, mean surprise {np.mean([r['surprise'] for r in sub]):.2f}")

    # ---------------- H3 interruption depth
    md.append("\n## H3 — how deep does an interruption reach? (before/after cosine distance minus random-position control)\n")
    have = [c for c in cells if c["z"]["inj_delta"].shape[0] > 0]
    if have:
        fig, ax = plt.subplots(figsize=(7, 3.8))
        md.append("| condition | n cells | injections | " + " | ".join(f"Δ L{l}" for l in layers) + " |")
        md.append("|---|---|---|" + "---|" * len(layers))
        for cond in conds:
            cs = [c for c in have if c["cond"] == cond]
            if not cs:
                continue
            per_cell = np.array([c["z"]["inj_delta"].mean(axis=0) - c["z"]["ctrl_delta"].mean(axis=0) for c in cs])
            m = per_cell.mean(axis=0)
            ci = [boot_ci(per_cell[:, i]) for i in range(len(layers))]
            ax.plot(layers, m, "-o", ms=4, color=PAL.get(cond, "#666"), label=f"{LABEL.get(cond, cond)} (n={len(cs)})")
            ax.fill_between(layers, [a for a, _ in ci], [b for _, b in ci], color=PAL.get(cond, "#666"), alpha=0.12, linewidth=0)
            md.append(f"| {LABEL.get(cond, cond)} | {len(cs)} | {sum(c['z']['inj_delta'].shape[0] for c in cs)} | " + " | ".join(f"{v:+.3f}" for v in m) + " |")
        ax.axhline(0, color="#999", lw=0.8); ax.set_xlabel("layer"); ax.set_ylabel("Δ cosine (injection − control)")
        ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25)
        ax.set_title("H3 — state change across an injection (64 tokens before vs after), per layer, minus random-position control", fontsize=9)
        fig.tight_layout(); fig.savefig(FIG / f"hidden_h3_interruption_{args.tag}.png", dpi=170, bbox_inches="tight"); plt.close(fig)
    else:
        md.append("(no cells with injections)")

    out = ROOT / "docs" / f"APPENDIX_HIDDEN_{args.tag}.md"
    out.write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print("->", out)


if __name__ == "__main__":
    main()
