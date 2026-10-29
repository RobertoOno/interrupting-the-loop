#!/usr/bin/env python3
"""Paper 6 figure, generated from the single-read JSON files (no number typed by hand).
  .venv/bin/python scripts/paper6_figures.py   -> paper6/figures/fig_loop.png
Panel a: held-out solve rates on the ladder without thinking (docs/a2c4_results/own2.json).
Panel b: solve rates on the four new wall families, thinking (docs/a8_results/narrow_c.json; complete curated arm).
Panel c: what is tried against what is executed on the walls: pi (needed invariant type at the first submission) against the solve rate,
         per arm and family (docs/a6_results/report.json)."""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parent.parent; OUT = ROOT / "paper6/figures"; OUT.mkdir(parents=True, exist_ok=True)
load = lambda p: json.load(open(ROOT / p))
STEPS = ["L1", "L2", "L3", "L4", "L5", "E"]; WALLS = ["W1", "W2", "W3", "W4"]
COL = {"base": "#7f7f7f", "own": "#9ecae1", "own2": "#1f77b4", "own3": "#08306b", "curm2": "#d62728", "p2": "#2ca02c"}

o2 = load("docs/a2c4_results/own2.json")["rates"]; a8 = load("docs/a8_results/narrow_c.json")["families"]; per = load("docs/a6_results/report.json")["per_condition_step"]
fig, axes = plt.subplots(1, 3, figsize=(13.5, 3.9))
# absent bars are zero (the base at W1, several no-thinking cells)
ax = axes[0]; arms = [("base", "base"), ("own", "own (iteration 1)"), ("own2", "own2 (iteration 2)"), ("curm2", "curm2 (template, same cells)"), ("p2", "p2 (template, six forms)")]
w = 0.16; xs = range(len(STEPS))
for i, (arm, lab) in enumerate(arms):
    bars = ax.bar([x + (i - 2) * w for x in xs], [o2[arm][s]["rate"] for s in STEPS], w, label=lab, color=COL[arm])
    for b in bars:   # a measured zero is printed, so that it is not read as "not run"
        if b.get_height() == 0:
            ax.text(b.get_x() + b.get_width() / 2, 0.012, "0", ha="center", va="bottom", fontsize=5.5, color=COL[arm])
ax.set_xticks(list(xs)); ax.set_xticklabels(STEPS); ax.set_ylim(0, 1.02); ax.set_ylabel("solve rate, held-out cells"); ax.set_title("a. the ladder, no thinking", loc="left", fontsize=10)
ax.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3)
ax = axes[1]; arms = [("base", "base"), ("own2", "own2"), ("curm2", "curm2 (template)")]; w = 0.26; xs = range(len(WALLS))
for i, (arm, lab) in enumerate(arms):
    bars = ax.bar([x + (i - 1) * w for x in xs], [a8[f][arm]["rate"] for f in WALLS], w, label=lab, color=COL[arm])
    for b in bars:
        if b.get_height() == 0:
            ax.text(b.get_x() + b.get_width() / 2, 0.012, "0", ha="center", va="bottom", fontsize=6.5, color=COL[arm])
ax.set_xticks(list(xs)); ax.set_xticklabels(WALLS); ax.set_ylim(0, 1.02); ax.set_title("b. four new families, thinking", loc="left", fontsize=10); ax.legend(fontsize=7, frameon=False)
ax = axes[2]; mk = {"W1": "o", "W2": "s", "W3": "^", "W4": "D"}
for arm, key, lab in (("base", "a8_base_v1", "base"), ("own2", "a8_own2_v1", "own2"), ("curm2", "a8c_curm2_v1", "curm2 (template)")):
    for f in WALLS:
        v = per[f"{key}|{f}"]; sat = v["pi"][0] == v["pi"][2]   # every session of every instance has (or lacks) the kind: a smoothing floor/ceiling, not an estimate
        ax.scatter(v["pi"][1], v["rate"][1], marker=mk[f], facecolor="white" if sat else COL[arm], edgecolor=COL[arm] if sat else "black",
                   s=48, linewidth=1.2 if sat else 0.4, label=lab if f == "W1" else None, zorder=3)
        if not sat:
            ax.plot([v["pi"][0], v["pi"][2]], [v["rate"][1]] * 2, color=COL[arm], alpha=0.35, linewidth=1)
        ax.plot([v["pi"][1]] * 2, [v["rate"][0], v["rate"][2]], color=COL[arm], alpha=0.35, linewidth=1)
ax.set_xlim(-0.03, 1.03); ax.set_ylim(-0.03, 1.03); ax.set_xlabel(r"$\pi$: needed kind of invariant at the first submission"); ax.set_ylabel("solve rate")
ax.set_title("c. what is tried against what is solved (walls)", loc="left", fontsize=10)
h, l = ax.get_legend_handles_labels(); leg1 = ax.legend(h, l, fontsize=7, frameon=False, loc="upper left", title="arm", title_fontsize=7)
ax.add_artist(leg1)
fam = [ax.scatter([], [], marker=mk[f], color="white", edgecolor="black", label=f) for f in WALLS]
fam.append(ax.scatter([], [], marker="o", facecolor="white", edgecolor="#555555", linewidth=1.2, label="hollow: saturated cell"))
ax.legend(handles=fam, fontsize=7, frameon=False, loc="center left", bbox_to_anchor=(1.01, 0.5), title="family", title_fontsize=7)
for a in axes:
    a.spines["top"].set_visible(False); a.spines["right"].set_visible(False)
fig.tight_layout(); fig.savefig(OUT / "fig_loop.png", dpi=200, bbox_inches="tight"); print("wrote", OUT / "fig_loop.png")


# ---- Figure 2: the design as a matrix (arms x steps): what each adapter was trained on, and where each arm was read
STEPS_ALL = ["L1", "L2", "L3", "L4", "L5", "E", "W1", "W2", "W3", "W4", "W5"]
NEEDED = {"L1": "linear", "L2": "linear\n(hidden)", "L3": "linear\nmod n", "L4": "mixed\nquad., 3 f.", "L5": "mixed\nquad., 2 f.", "E": "diagonal\nquad. (Pell)",
          "W1": "quad.\nmod p", "W2": "linear\nmod k (trap)", "W3": "mixed\nquad., 4 f.", "W4": "linear\nmod p", "W5": "quad.\nmod p, 4 f."}
# T = trained on (blue: the lineage's own accepted proofs; red: template reference proofs); R = read on held-out or fresh instances
ARMS = [("base", {}, ["L1", "L2", "L3", "L4", "L5", "E", "W1", "W2", "W3", "W4", "W5"]),
        ("p1 (template)", {"L5": "t", "E": "t"}, ["L1", "L2", "L3", "L4", "L5", "E"]),
        ("p2 (template)", {s: "t" for s in ["L1", "L2", "L3", "L4", "L5", "E"]}, ["L1", "L2", "L3", "L4", "L5", "E"]),
        ("own (iteration 1)", {"L1": "o", "L2": "o", "L3": "o"}, ["L1", "L2", "L3", "L4", "L5", "E"]),
        ("curm (template, same cells)", {"L1": "t", "L2": "t", "L3": "t"}, ["L1", "L2", "L3", "L4", "L5", "E"]),
        ("own2 (iteration 2)", {s: "o" for s in ["L1", "L2", "L3", "L4", "L5", "E"]}, ["L1", "L2", "L3", "L4", "L5", "E", "W1", "W2", "W3", "W4", "W5"]),
        ("curm2 (template, same cells)", {s: "t" for s in ["L1", "L2", "L3", "L4", "L5", "E"]}, ["L1", "L2", "L3", "L4", "L5", "E", "W1", "W2", "W3", "W4"]),
        ("own3 (iteration 3)", {s: "o" for s in ["L1", "L2", "L3", "L4", "L5", "E", "W1", "W2", "W3", "W4"]}, ["L1", "L2", "L3", "L4", "L5", "E", "W1", "W2", "W3", "W4", "W5"])]
fig2, ax = plt.subplots(figsize=(13.5, 4.6))
nx, ny = len(STEPS_ALL), len(ARMS)
for j, s in enumerate(STEPS_ALL):
    ax.text(j, ny + 0.15, NEEDED[s], ha="center", va="bottom", fontsize=7.5)
    ax.text(j, ny + 0.95, s, ha="center", va="bottom", fontsize=9, fontweight="bold")
for i, (name, trained, read) in enumerate(ARMS):
    y = ny - 1 - i
    ax.text(-0.7, y, name, ha="right", va="center", fontsize=8.5)
    for j, s in enumerate(STEPS_ALL):
        if s in read:   # a ring, so that a trained-and-read cell shows both marks
            ax.scatter(j, y, marker="o", s=220, facecolor="white", edgecolor="#555555", linewidth=1.1, zorder=2)
        if s in trained:
            ax.scatter(j, y, marker="s", s=55, color="#1f77b4" if trained[s] == "o" else "#d62728", zorder=3)
ax.axvline(5.5, color="#999999", linewidth=0.8, linestyle="--")
ax.text(2.5, -0.85, "the ladder (48 training instances per round; 6 held-out)", ha="center", fontsize=8, color="#555555")
ax.text(8, -0.85, "the wall families (6 fresh instances each per node)", ha="center", fontsize=8, color="#555555")
ax.set_xlim(-4.2, nx - 0.5); ax.set_ylim(-1.3, ny + 1.9); ax.axis("off")
ax.scatter([], [], marker="s", s=90, color="#1f77b4", label="trained on the lineage's own accepted proofs of the step")
ax.scatter([], [], marker="s", s=90, color="#d62728", label="trained on the template reference proofs of the same cells")
ax.scatter([], [], marker="o", s=110, facecolor="white", edgecolor="#555555", label="read on held-out or fresh instances (a square inside a ring: trained on the training instances, read on the held-out ones)")
ax.legend(loc="lower left", bbox_to_anchor=(-0.02, -0.12), fontsize=7.5, frameon=False, ncol=3)
fig2.tight_layout(); fig2.savefig(OUT / "fig_design.png", dpi=200, bbox_inches="tight"); print("wrote", OUT / "fig_design.png")
