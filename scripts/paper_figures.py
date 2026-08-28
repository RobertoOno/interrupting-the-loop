#!/usr/bin/env python3
"""Figures for papers 2 and 3, drawn from the certified appendix numbers
(APPENDIX_C.md, APPENDIX_N.md, APPENDIX_F23.md) — no raw-run reprocessing.
Okabe-Ito palette (colorblind-safe); direct labels; one hue job per arm."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/figures"; OUT.mkdir(exist_ok=True)
BLUE, ORANGE, GREEN, VERM, PURPLE, GRAY = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#666666"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.linewidth": 0.8, "figure.dpi": 200})

# ---- Paper 2, fig 1: mean moves, best does not (APPENDIX_C.md per-cycle table) ----
cyc = [1, 2, 3, 4, 5]
mean = {"base":    [0.0562, 0.0583, 0.0644, 0.0532, 0.0556],
        "attract": [0.0559, 0.0430, 0.0516, 0.0420, 0.0386],
        "random":  [0.0708, 0.0697, 0.0653, 0.0510, 0.0695]}
best = {"base":    [0.0327, 0.0317, 0.0414, 0.0323, 0.0325],
        "attract": [0.0319, 0.0312, 0.0311, 0.0311, 0.0311],
        "random":  [0.0332, 0.0310, 0.0312, 0.0307, 0.0311]}
base0_mean, base0_best = 0.0633, 0.0408
COL = {"base": GRAY, "attract": BLUE, "random": ORANGE}
fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.5), sharex=True)
for ax, data, title in ((axes[0], mean, "mean excess (held-out)"), (axes[1], best, "best excess (held-out)")):
    for arm in ("random", "base", "attract"):
        ax.plot(cyc, data[arm], color=COL[arm], lw=1.6, marker="o", ms=3.5)
        if data is mean:
            ax.annotate(arm, (cyc[-1], data[arm][-1]), xytext=(4, 0), textcoords="offset points",
                        color=COL[arm], fontsize=8, va="center")
    ax.plot([0], [base0_mean if data is mean else base0_best], color=GRAY, marker="o", ms=3.5)
    ax.set_title(title, fontsize=9); ax.set_xlabel("consolidation cycle")
    ax.set_xticks([0] + cyc); ax.set_xlim(-0.3, 6.3)
axes[0].set_ylabel("excess over lower bound"); axes[0].set_ylim(0.030, 0.075); axes[1].set_ylim(0.030, 0.075)
axes[1].axhline(0.0311, color=GRAY, lw=0.7, ls=":", zorder=0)
axes[1].annotate("trained arms at the 0.0311 classic level;\nthe base fluctuates above it", (2.4, 0.0350), fontsize=7.5, color="#333333")
fig.tight_layout()
fig.savefig(OUT / "fig_c_mean_vs_best.png", bbox_inches="tight"); plt.close(fig)

# ---- Paper 2, fig 2: the price in the tails (APPENDIX_N.md) ----
arms = ["base", "attract", "qd", "repel\n(anchored)", "repel\n(mode)"]
tail_far = [10.0, 3.9, 0.6, 0.0, 0.0]
tail_n = ["1/18", "5/156", "1/158", "0/79", "0/28"]
at_cls_ho = [20, 72, 25, 100, 2]
CJ = [GRAY, BLUE, GREEN, VERM, PURPLE]
fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.4))
for ax, vals, title, unit in ((axes[0], tail_far, "better than the classic, per-family\naverage rate (far families)", "%"),
                              (axes[1], at_cls_ho, "candidates exactly at the classic's level\n(held-out)", "%")):
    bars = ax.bar(range(len(arms)), vals, color=CJ, width=0.62)
    for i, (b, v) in enumerate(zip(bars, vals)):
        lbl = f"{v:g}{unit}" + (f"\n({tail_n[i]})" if vals is tail_far else "")
        ax.annotate(lbl, (b.get_x() + b.get_width() / 2, v), xytext=(0, 2),
                    textcoords="offset points", ha="center", fontsize=7.5)
    ax.set_xticks(range(len(arms))); ax.set_xticklabels(arms, fontsize=8)
    ax.set_title(title, fontsize=9); ax.set_yticks([])
    for s in ("left",): ax.spines[s].set_visible(False)
axes[0].set_ylim(0, 13.5); axes[1].set_ylim(0, 118)
fig.tight_layout()
fig.savefig(OUT / "fig_n_tails.png", bbox_inches="tight"); plt.close(fig)

# ---- Paper 3: the cube at a glance (APPENDIX_F23.md cell means + collapses) ----
cube = {  # arm: (div, frac, collapses, memory_on, repulsion_on)
    "A":  (0.413, 0.439, 2, False, False), "B":  (0.534, 0.596, 1, True, False),
    "C":  (0.519, 0.534, 1, False, False), "D":  (0.720, 0.498, 3, False, True),
    "BC": (0.590, 0.592, 2, True, False),  "BD": (0.684, 0.610, 0, True, True),
    "CD": (0.798, 0.511, 4, False, True),  "E":  (0.697, 0.635, 1, True, True)}
fig, ax = plt.subplots(figsize=(4.6, 3.4))
for arm, (dv, fr, col, mem, rep) in cube.items():
    ax.scatter(dv, fr, s=64, color=(BLUE if mem else GRAY), marker=("o" if rep else "s"),
               zorder=3, edgecolors="white", linewidths=0.8)
    dx, dy = (6, 5) if arm not in ("C", "BC") else (6, -9)
    ax.annotate(f"{arm} ({col})", (dv, fr), xytext=(dx, dy), textcoords="offset points",
                fontsize=8.5, color=(BLUE if mem else "#333333"))
ax.set_xlabel("functional diversity (distinct behaviours / valid)")
ax.set_ylabel("frac of seed→record gap closed")
ax.set_xlim(0.37, 0.88); ax.set_ylim(0.41, 0.67)
ax.annotate("B-on (blue): the four best means", (0.385, 0.655), fontsize=8, color=BLUE)
ax.annotate("D-on (circles): highest hash diversity", (0.385, 0.638), fontsize=8, color="#333333")
ax.annotate("(n) = collapses in 18 runs", (0.385, 0.621), fontsize=8, color=GRAY)
fig.tight_layout()
fig.savefig(OUT / "fig_f23_cube.png", bbox_inches="tight"); plt.close(fig)
# ---- Paper 3: forest of per-problem E-A effects (APPENDIX_F.md pooled fracs) ----
forest = [("beat-the-average", .528, .413, .643), ("max–min 16", .539, .445, .634),
          ("ring loading", .364, .565, .162), ("circle packing", .289, .014, .563),
          ("autocorr $C_1$", .045, .064, .027), ("Heilbronn 11", .028, -.035, .092),
          ("isosceles-free", 0.0, 0.0, 0.0), ("$180!$", 0.0, 0.0, 0.0),
          ("sum-difference", -.030, -.005, -.056)]
forest.sort(key=lambda x: x[1])
fig, ax = plt.subplots(figsize=(4.6, 2.9))
ys = range(len(forest))
ax.axvline(0, color="#999999", lw=0.8)
ax.axvline(0.196, color=BLUE, lw=1.0, ls="--")
ax.axvline(0.045, color=GRAY, lw=1.0, ls=":")
for y, (_, m, r0, r1) in zip(ys, forest):
    ax.plot([r0, r1], [y, y], color=GRAY, lw=0.7, alpha=0.7, zorder=2)
    ax.scatter([r0, r1], [y, y], s=12, color=GRAY, zorder=2)
ax.scatter([v for _, v, _, _ in forest], list(ys), s=42, color=BLUE, zorder=3)
ax.set_yticks(list(ys)); ax.set_yticklabels([f[0] for f in forest], fontsize=8)
ax.set_xlabel("E $-$ A, frac of seed$\\to$record gap (pooled replicates)")
ax.annotate("mean +0.196", (0.196, len(forest) - 0.6), xytext=(4, 0), textcoords="offset points",
            fontsize=8, color=BLUE)
ax.annotate("median +0.045", (0.045, 1.4), xytext=(4, 0), textcoords="offset points",
            fontsize=8, color=GRAY)
fig.tight_layout()
fig.savefig(OUT / "fig_forest_ea.png", bbox_inches="tight"); plt.close(fig)

# ---- Paper 2: independent replication (C-rep) — paired per-variant, per lineage ----
import json as _json
fig, axes = plt.subplots(1, 4, figsize=(8.6, 2.5), gridspec_kw={"width_ratios": [1, 1, 1, 0.8]})
for li, L in enumerate(("L1", "L2", "L3")):
    ax = axes[li]
    means = {}
    for a in ("base", "attract"):
        by = {}
        cs = _json.load(open(ROOT / f"runs/dream_c_rep/{L}/{a}_c6/candidates.json"))
        for c in cs.values():
            if c.get("ok") and c.get("test") is not None:
                by.setdefault(c["variant"], []).append(c["test"])
        means[a] = {v: sum(x) / len(x) for v, x in by.items()}
    common = sorted(set(means["base"]) & set(means["attract"]))
    for v in common:
        ax.plot([0, 1], [means["base"][v], means["attract"][v]], color=GRAY, lw=0.8, alpha=0.6)
        ax.scatter([0], [means["base"][v]], s=18, color=GRAY, zorder=3)
        ax.scatter([1], [means["attract"][v]], s=18, color=BLUE, zorder=3)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["base", "attract"], fontsize=8)
    ax.set_title(f"lineage {li + 1}", fontsize=9); ax.set_xlim(-0.4, 1.4); ax.set_ylim(0.015, 0.105)
    if li == 0: ax.set_ylabel("mean test excess (held-out 2)")
    else: ax.set_yticklabels([])
ax = axes[3]
bl, al = [0.0247, 0.0243, 0.0243], [0.0210, 0.0210, 0.0210]
for i in range(3):
    ax.plot([0, 1], [bl[i], al[i]], color=GRAY, lw=0.8, alpha=0.6)
    ax.scatter([0], [bl[i]], s=18, color=GRAY, zorder=3); ax.scatter([1], [al[i]], s=18, color=BLUE, zorder=3)
ax.set_xticks([0, 1]); ax.set_xticklabels(["base", "attract"], fontsize=8)
ax.set_title("best (3 lineages)", fontsize=9); ax.set_xlim(-0.4, 1.4); ax.set_ylim(0.015, 0.105); ax.set_yticklabels([])
fig.tight_layout()
fig.savefig(OUT / "fig_crep.png", bbox_inches="tight"); plt.close(fig)

import shutil
for name, dests in (("fig_c_mean_vs_best.png", ["paper2/figures"]),
                    ("fig_n_tails.png", ["paper2/figures"]),
                    ("fig_f23_cube.png", ["paper3/figures"]),
                    ("fig_forest_ea.png", ["paper3/figures"]),
                    ("fig_crep.png", ["paper2/figures"])):
    for d in dests:
        (ROOT / d).mkdir(parents=True, exist_ok=True)
        shutil.copy2(OUT / name, ROOT / d / name)
print("wrote and synced fig_c_mean_vs_best.png, fig_n_tails.png, fig_f23_cube.png")
