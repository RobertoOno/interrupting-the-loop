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
axes[1].annotate("every arm pinned at the 0.0311 ceiling", (2.9, 0.0345), fontsize=8, color="#333333")
fig.tight_layout()
fig.savefig(OUT / "fig_c_mean_vs_best.png", bbox_inches="tight"); plt.close(fig)

# ---- Paper 2, fig 2: the price in the tails (APPENDIX_N.md) ----
arms = ["base", "attract", "qd", "repel\n(anchored)", "repel\n(mode)"]
tail_far = [10.0, 3.9, 0.6, 0.0, 0.0]
at_cls_ho = [20, 72, 25, 100, 2]
CJ = [GRAY, BLUE, GREEN, VERM, PURPLE]
fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.4))
for ax, vals, title, unit in ((axes[0], tail_far, "candidates better than the classic\n(far family)", "%"),
                              (axes[1], at_cls_ho, "candidates exactly at the classic's level\n(held-out)", "%")):
    bars = ax.bar(range(len(arms)), vals, color=CJ, width=0.62)
    for b, v in zip(bars, vals):
        ax.annotate(f"{v:g}{unit}", (b.get_x() + b.get_width() / 2, v), xytext=(0, 2),
                    textcoords="offset points", ha="center", fontsize=8)
    ax.set_xticks(range(len(arms))); ax.set_xticklabels(arms, fontsize=8)
    ax.set_title(title, fontsize=9); ax.set_yticks([])
    for s in ("left",): ax.spines[s].set_visible(False)
axes[0].set_ylim(0, 12.5); axes[1].set_ylim(0, 118)
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
ax.annotate("memory on (blue) moves ↑", (0.385, 0.655), fontsize=8, color=BLUE)
ax.annotate("repulsion on (circles) moves →", (0.385, 0.638), fontsize=8, color="#333333")
ax.annotate("(n) = collapses in 18 runs", (0.385, 0.621), fontsize=8, color=GRAY)
fig.tight_layout()
fig.savefig(OUT / "fig_f23_cube.png", bbox_inches="tight"); plt.close(fig)
import shutil
for name, dests in (("fig_c_mean_vs_best.png", ["paper2/figures"]),
                    ("fig_n_tails.png", ["paper2/figures"]),
                    ("fig_f23_cube.png", ["paper3/figures"])):
    for d in dests:
        (ROOT / d).mkdir(parents=True, exist_ok=True)
        shutil.copy2(OUT / name, ROOT / d / name)
print("wrote and synced fig_c_mean_vs_best.png, fig_n_tails.png, fig_f23_cube.png")
