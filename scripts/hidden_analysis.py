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
            # exact event positions in the generated stream; older cells (no 'pos') are
            # reconstructed from the injections recorded at capture time
            inj = []
            if "inj_pos" in z and "inj_len" in z:
                acc = 0
                for gp, n in zip(z["inj_pos"], z["inj_len"]):
                    step_i = int(gp) - int(z["n_seed"]) - acc
                    inj.append((step_i, int(n))); acc += int(n)
            def pos_of_event(e):
                if "pos" in e:
                    return e["pos"]
                return e["step"] + sum(n for s_i, n in inj if s_i < e["step"])
            pos_of = {(e["step"], e["kind"]): pos_of_event(e) for e in run["events"]}
            judged = []
            for r in rej.get(cell, []):
                if r.get("surprise") is None:
                    continue
                judged.append({**r, "end": pos_of.get((r["step"], r["kind"]), r["step"])})
            cells.append({"run": rd.name, "cell": cell, "cond": cond, "z": z, "judged": judged,
                          "layers": [int(l) for l in z["layers"]]})
    return cells


def centered(c, l, mu):
    """Window vectors at layer l, mean-centered by the analysis-set mean (removes the
    shared anisotropic component of mean-pooled hidden states) and re-normalized."""
    W = c["z"][f"win_L{l}"].astype(np.float32) - mu[l]
    return W / (np.linalg.norm(W, axis=1, keepdims=True) + 1e-6)


def layer_means(cells):
    mu = {}
    for l in cells[0]["layers"]:
        acc = np.zeros(cells[0]["z"][f"win_L{l}"].shape[1], dtype=np.float64); n = 0
        for c in cells:
            W = c["z"][f"win_L{l}"].astype(np.float64); acc += W.sum(axis=0); n += len(W)
        mu[l] = (acc / max(n, 1)).astype(np.float32)
    return mu


def geometry_per_layer(c, mu):
    out = {}
    for l in c["layers"]:
        W = centered(c, l, mu)
        steps = 1.0 - np.sum(W[1:] * W[:-1], axis=1)
        cen = W.mean(axis=0); cen /= np.linalg.norm(cen) + 1e-6
        out[l] = {"step": float(steps.mean()), "radius": float(np.mean(1.0 - W @ cen))}
    return out


def judged_features(c, mu, review_tokens=160):
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
            W = centered(c, l, mu)
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
    mu = layer_means(cells)
    md = [f"# Residual-stream analysis ({args.tag})\n", f"{len(cells)} cells, layers {layers}. Window vectors are mean-centered per layer "
          f"over all cells of this set before cosine geometry (anisotropy of mean-pooled states); premise similarity and injection deltas are raw.\n"]

    # ---------------- H1 geometry per layer (+ logit-lens commitment per condition)
    geo = {c["cell"]: geometry_per_layer(c, mu) for c in cells}
    fig, axes = plt.subplots(1, 3, figsize=(15, 3.8))
    md.append("\n## H1 — per-layer geometry (mean over cells; 95% bootstrap CI over cells)\n")
    md.append("| condition | n | " + " | ".join(f"radius L{l}" for l in layers) + " | commit layer (idx) | final entropy |")
    md.append("|---|---|" + "---|" * len(layers) + "---|---|")
    commit_rows = []
    for cond in conds:
        cs = [c for c in cells if c["cond"] == cond]
        for ax, key in zip(axes[:2], ("step", "radius")):
            m = [np.mean([geo[c["cell"]][l][key] for c in cs]) for l in layers]
            ci = [boot_ci([geo[c["cell"]][l][key] for c in cs]) for l in layers]
            ax.plot(layers, m, "-o", ms=4, color=PAL.get(cond, "#666"), label=f"{LABEL.get(cond, cond)} (n={len(cs)})")
            ax.fill_between(layers, [a for a, _ in ci], [b for _, b in ci], color=PAL.get(cond, "#666"), alpha=0.12, linewidth=0)
        # commitment: per cell, mean over windows of the first captured layer agreeing with the final top-1
        commit = [float(np.mean(c["z"]["win_commit"])) for c in cs]
        fent = [float(np.mean(c["z"]["win_final_entropy"])) for c in cs]
        commit_rows.append((cond, commit, fent))
        md.append(f"| {LABEL.get(cond, cond)} | {len(cs)} | " + " | ".join(f"{np.mean([geo[c['cell']][l]['radius'] for c in cs]):.3f}" for l in layers)
                  + f" | {np.mean(commit):.2f} [{boot_ci(commit)[0]:.2f}, {boot_ci(commit)[1]:.2f}] | {np.mean(fent):.2f} |")
    axes[0].set_title("mean step between consecutive 64-token windows (cosine)", fontsize=9)
    axes[1].set_title("explored radius (mean cosine distance to centroid)", fontsize=9)
    for ax in axes[:2]:
        ax.set_xlabel("layer"); ax.grid(alpha=0.25)
    axes[0].legend(fontsize=7, frameon=False)
    ax = axes[2]
    for i, (cond, commit, fent) in enumerate(commit_rows):
        ax.scatter([i] * len(commit), commit, color=PAL.get(cond, "#666"), s=14, alpha=0.7)
        lo, hi = boot_ci(commit)
        ax.plot([i - 0.25, i + 0.25], [np.mean(commit)] * 2, color=PAL.get(cond, "#666"), lw=2)
        ax.plot([i, i], [lo, hi], color=PAL.get(cond, "#666"), lw=1)
    ax.set_xticks(range(len(commit_rows))); ax.set_xticklabels([LABEL.get(c, c) for c, _, _ in commit_rows], fontsize=7, rotation=20, ha="right")
    ax.set_ylabel("mean commitment (index into captured layers)"); ax.grid(alpha=0.25)
    ax.set_title("logit lens: how early the top-1 is already decided (per cell)", fontsize=9)
    fig.suptitle("H1 — where in the network does the stream freeze? residual-stream trajectory geometry per layer, and early commitment", fontsize=10)
    fig.tight_layout(); fig.savefig(FIG / f"hidden_h1_geometry_{args.tag}.png", dpi=170, bbox_inches="tight"); plt.close(fig)

    # ---------------- H2 novelty per layer vs judged surprise
    rows = [r for c in cells for r in judged_features(c, mu)]
    md.append(f"\n## H2 — which layer's novelty predicts judged surprise? ({len(rows)} judged windows)\n")
    if rows:
        def spear(key, subset):
            xs = [r[key] for r in subset if key in r]; ys = [r["surprise"] for r in subset if key in r]
            if len(xs) < 8:
                return float("nan"), float("nan")
            rho, pv = spearmanr(xs, ys)
            return float(rho), float(pv)
        fig, axes = plt.subplots(1, 2, figsize=(13, 3.8), sharey=True)
        for ax, feat, ttl in zip(axes, ("nov", "step"), ("novelty vs everything before the window", "local step vs the previous 160 tokens")):
            pooled = [spear(f"{feat}_L{l}", rows)[0] for l in layers]
            ax.plot(layers, pooled, "-o", color="#111", label=f"pooled (n={len(rows)})")
            md.append(f"\n**{ttl}** — Spearman with judged surprise\n")
            md.append("| layer | ρ pooled | p | " + " | ".join(f"ρ within {LABEL.get(c, c)}" for c in conds) + " |")
            md.append("|---|---|---|" + "---|" * len(conds))
            within = {}
            for cond in conds:
                sub = [r for r in rows if r["cond"] == cond]
                within[cond] = [spear(f"{feat}_L{l}", sub)[0] for l in layers]
                if len(sub) >= 8:
                    ax.plot(layers, within[cond], "-", alpha=0.7, color=PAL.get(cond, "#666"), label=f"{LABEL.get(cond, cond)} (n={len(sub)})")
            for i, l in enumerate(layers):
                rho, pv = spear(f"{feat}_L{l}", rows)
                md.append(f"| {l} | {rho:+.2f} | {pv:.1e} | " + " | ".join(f"{within[c][i]:+.2f}" for c in conds) + " |")
            ax.axhline(0, color="#999", lw=0.8); ax.set_xlabel("layer"); ax.grid(alpha=0.25); ax.set_title(ttl, fontsize=9)
        axes[0].set_ylabel("Spearman ρ with judged surprise"); axes[0].legend(fontsize=7, frameon=False)
        fig.suptitle("H2 — which layer's movement predicts judged surprise?", fontsize=10)
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

    # ---------------- H1b similarity to the premise state per layer (whole stream), by condition
    if all(f"win_prem_L{layers[0]}" in c["z"] for c in cells):
        fig, ax = plt.subplots(figsize=(7, 3.8))
        md.append("\n## H1b — similarity of the stream to the premise state, per layer (mean over windows, then cells)\n")
        md.append("| condition | " + " | ".join(f"L{l}" for l in layers) + " |")
        md.append("|---|" + "---|" * len(layers))
        for cond in conds:
            cs = [c for c in cells if c["cond"] == cond]
            per_cell = np.array([[float(np.mean(c["z"][f"win_prem_L{l}"])) for l in layers] for c in cs])
            m = per_cell.mean(axis=0); ci = [boot_ci(per_cell[:, i]) for i in range(len(layers))]
            ax.plot(layers, m, "-o", ms=4, color=PAL.get(cond, "#666"), label=f"{LABEL.get(cond, cond)} (n={len(cs)})")
            ax.fill_between(layers, [a for a, _ in ci], [b for _, b in ci], color=PAL.get(cond, "#666"), alpha=0.12, linewidth=0)
            md.append(f"| {LABEL.get(cond, cond)} | " + " | ".join(f"{v:.3f}" for v in m) + " |")
        ax.set_xlabel("layer"); ax.set_ylabel("cosine similarity to premise state"); ax.grid(alpha=0.25); ax.legend(fontsize=7, frameon=False)
        ax.set_title("H1b — how close the stream stays to the premise, in the network's own representation, per layer", fontsize=9)
        fig.tight_layout(); fig.savefig(FIG / f"hidden_h1b_premise_{args.tag}.png", dpi=170, bbox_inches="tight"); plt.close(fig)

    # ---------------- H3 interruption depth (+ return to premise)
    md.append("\n## H3 — how deep does an interruption reach? (before/after cosine distance minus random-position control; and return to the premise)\n")
    have = [c for c in cells if c["z"]["inj_delta"].shape[0] > 0]
    if have:
        has_ret = all("inj_return" in c["z"] and c["z"]["inj_return"].shape[1] == len(layers) for c in have)
        fig, axes = plt.subplots(1, 2 if has_ret else 1, figsize=(13 if has_ret else 7, 3.8), squeeze=False)
        ax = axes[0][0]
        md.append("| condition | n cells | injections | " + " | ".join(f"Δ L{l}" for l in layers) + " |")
        md.append("|---|---|---|" + "---|" * len(layers))
        ret_rows = []
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
            if has_ret:
                pr = np.array([c["z"]["inj_return"].mean(axis=0) - c["z"]["ctrl_return"].mean(axis=0) for c in cs])
                ret_rows.append((cond, len(cs), pr.mean(axis=0), [boot_ci(pr[:, i]) for i in range(len(layers))]))
        ax.axhline(0, color="#999", lw=0.8); ax.set_xlabel("layer"); ax.set_ylabel("Δ cosine distance (injection − control)")
        ax.legend(fontsize=7, frameon=False); ax.grid(alpha=0.25)
        ax.set_title("state change across an injection (64 tokens before vs after), minus random-position control", fontsize=9)
        if has_ret:
            ax = axes[0][1]
            md.append("\n**Return to the premise** (Δ similarity to the premise state, after − before, minus control):\n")
            md.append("| condition | " + " | ".join(f"L{l}" for l in layers) + " |")
            md.append("|---|" + "---|" * len(layers))
            for cond, n, m, ci in ret_rows:
                ax.plot(layers, m, "-o", ms=4, color=PAL.get(cond, "#666"), label=f"{LABEL.get(cond, cond)} (n={n})")
                ax.fill_between(layers, [a for a, _ in ci], [b for _, b in ci], color=PAL.get(cond, "#666"), alpha=0.12, linewidth=0)
                md.append(f"| {LABEL.get(cond, cond)} | " + " | ".join(f"{v:+.3f}" for v in m) + " |")
            ax.axhline(0, color="#999", lw=0.8); ax.set_xlabel("layer"); ax.set_ylabel("Δ similarity to premise (after − before) − control")
            ax.grid(alpha=0.25); ax.set_title("does the injection bring the state back toward the premise?", fontsize=9)
        fig.suptitle("H3 — how deep does an interruption reach?", fontsize=10)
        fig.tight_layout(); fig.savefig(FIG / f"hidden_h3_interruption_{args.tag}.png", dpi=170, bbox_inches="tight"); plt.close(fig)
    else:
        md.append("(no cells with injections)")

    out = ROOT / "docs" / f"APPENDIX_HIDDEN_{args.tag}.md"
    out.write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print("->", out)


if __name__ == "__main__":
    main()
