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
ax.set_xlabel("construction-hash diversity (distinct hashes / valid)")
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

# ---- Paper 4, fig 1: the temporal law (H2 dose curve + PULSE pair) ----
fig, axes = plt.subplots(1, 3, figsize=(8.6, 2.6), gridspec_kw={"width_ratios": [1.15, 1.15, 0.9]})
alphas = [0.1, 0.25, 0.5, 0.75, 1.0, 1.5]
s_cont = [1.95, 2.38, 1.72, 1.62, 1.78, 0.85]
c_cont = [4.92, 4.57, 4.37, 3.53, 2.77, 1.38]
for ax, ys, base, ttl in ((axes[0], s_cont, 2.38, "judged surprise"), (axes[1], c_cont, 4.83, "judged coherence")):
    ax.plot(alphas, ys, color=VERM, lw=1.6, marker="o", ms=3.5)
    ax.axhline(base, color=GRAY, lw=0.9, ls="--")
    ax.annotate("plain baseline", (alphas[-1], base), xytext=(-2, 4), textcoords="offset points",
                ha="right", fontsize=7.5, color=GRAY)
    ax.set_title(ttl + " (continuous)", fontsize=9); ax.set_xlabel(r"dose $\alpha$")
axes[0].set_ylim(0.4, 5.4); axes[1].set_ylim(0.4, 5.4)
ax = axes[2]
bars = ax.bar([0, 1], [1.88, 2.78], color=[GRAY, BLUE], width=0.6)
ax.set_xticks([0, 1]); ax.set_xticklabels(["habit", "pulsed"], fontsize=8)
for b, v in zip(bars, (1.88, 2.78)):
    ax.annotate(f"{v:.2f}", (b.get_x() + 0.3, v), xytext=(0, 2), textcoords="offset points", ha="center", fontsize=7.5)
ax.annotate("p = 0.006", (0.5, 3.0), ha="center", fontsize=8, color=BLUE)
ax.set_title("same vectors, pulsed", fontsize=9); ax.set_ylim(0.4, 5.4); ax.set_yticks([])
fig.tight_layout(); fig.savefig(OUT / "fig_p4_templaw.png", bbox_inches="tight"); plt.close(fig)

# ---- Paper 4, fig 2: guards license dose (the ladder to parity) ----
fig, ax = plt.subplots(figsize=(4.4, 2.7))
ax.plot([1.0, 1.5, 2.0], [2.10, 3.23, 3.40], color=BLUE, lw=1.6, marker="o", ms=4.5)
ax.scatter([1.0], [2.78], color=PURPLE, marker="s", s=34, zorder=3)
ax.annotate("unguarded pulse", (1.0, 2.78), xytext=(8, -2), textcoords="offset points", fontsize=8, color=PURPLE)
ax.annotate("guarded ladder", (1.5, 3.23), xytext=(8, -10), textcoords="offset points", fontsize=8, color=BLUE)
ax.axhline(3.64, color=GRAY, lw=0.9, ls="--")
ax.annotate("text interruption (3.64)", (2.0, 3.64), xytext=(-2, 4), textcoords="offset points", ha="right", fontsize=8, color="#333333")
ax.set_xlabel(r"dose $\alpha$ (guarded)"); ax.set_ylabel("judged surprise"); ax.set_ylim(1.8, 4.1)
ax.set_xticks([1.0, 1.5, 2.0])
fig.tight_layout(); fig.savefig(OUT / "fig_p4_ladder.png", bbox_inches="tight"); plt.close(fig)

# ---- Paper 4, fig 3: silent orbits and their removal (from runs/spectral npz) ----
def _detrended(a, smooth=21):
    import numpy as _np
    pad = smooth // 2
    padded = _np.pad(a, pad, mode="edge")
    base = _np.array([_np.median(padded[i:i + smooth]) for i in range(len(a))])
    return a - base
try:
    import numpy as _np
    cells = [("state_band__tr_L18_a0.5_s0.npz", "literal loop (P=7)", VERM),
             ("state_pulse__p0_habit.npz", "habituated: the silent orbit (P=30)", BLUE),
             ("state_pulse__p0_inter.npz", "interrupted: flat", GREEN)]
    fig, axes = plt.subplots(1, 3, figsize=(8.6, 2.4), sharey=True)
    for ax, (f, ttl, col) in zip(axes, cells):
        z = _np.load(ROOT / "runs/spectral" / f)
        d = _detrended(z["a_state"])[:150]
        ax.plot(range(1, len(d) + 1), d, color=col, lw=1.1)
        ax.set_title(ttl, fontsize=8.5); ax.set_xlabel(r"lag $\tau$ (tokens)")
        ax.axhline(0, color="#999999", lw=0.6)
    axes[0].set_ylabel("detrended state autocorr.")
    fig.tight_layout(); fig.savefig(OUT / "fig_p4_spectra.png", bbox_inches="tight"); plt.close(fig)
    print("fig_p4_spectra ok")
except FileNotFoundError as e:
    print("fig_p4_spectra SKIPPED:", e)

# ---- Paper 4 revision (review M5/Q1): per-premise points and the 57-cell band map ----
import json as _json
import numpy as _np2


def _cellmeans(run, dim):
    recs = _json.loads((ROOT / "runs" / run / "rejudge_gen.json").read_text())
    by = {}
    for r in recs:
        if r.get(dim) is not None:
            by.setdefault(r["cell"], []).append(r[dim])
    return {c: sum(v) / len(v) for c, v in by.items()}


try:
    S2, C2 = _cellmeans("state_h2", "surprise"), _cellmeans("state_h2", "coherence")
    SP = _cellmeans("state_pulse", "surprise")
    anames = [("0.1", 0.1), ("0.25", 0.25), ("0.5", 0.5), ("0.75", 0.75), ("1", 1.0), ("1.5", 1.5)]
    rng = _np2.random.default_rng(0)
    fig, axes = plt.subplots(1, 3, figsize=(8.6, 2.7), gridspec_kw={"width_ratios": [1.15, 1.15, 0.9]})
    for ax, M, ttl in ((axes[0], S2, "judged surprise"), (axes[1], C2, "judged coherence")):
        means = []
        for an, av in anames:
            ys = [M[f"p{i}_L18_a{an}"] for i in range(10) if f"p{i}_L18_a{an}" in M]
            ax.scatter(av + rng.uniform(-0.03, 0.03, len(ys)), ys, s=9, color=GRAY, alpha=0.55, zorder=2)
            means.append(sum(ys) / len(ys))
        ax.plot([a for _, a in anames], means, color=VERM, lw=1.6, marker="o", ms=3.5, zorder=3)
        base = [M[f"p{i}_bare"] for i in range(10) if f"p{i}_bare" in M]
        ax.axhline(sum(base) / len(base), color=GRAY, lw=0.9, ls="--")
        ax.annotate("plain baseline", (1.5, sum(base) / len(base)), xytext=(-2, 4), textcoords="offset points",
                    ha="right", fontsize=7.5, color=GRAY)
        ax.set_title(ttl + " (continuous, plain carrier)", fontsize=8.5); ax.set_xlabel(r"dose $\alpha$")
        ax.set_ylim(0.4, 5.6)
    ax = axes[2]
    for i in range(10):
        h, p_ = SP.get(f"p{i}_habit"), SP.get(f"p{i}_pulse")
        if h is not None and p_ is not None:
            ax.plot([0, 1], [h, p_], color=GRAY, lw=0.7, alpha=0.6)
            ax.scatter([0, 1], [h, p_], s=10, color=[GRAY, BLUE], zorder=3)
    hm = _np2.mean([SP[f"p{i}_habit"] for i in range(10)]); pm = _np2.mean([SP[f"p{i}_pulse"] for i in range(10)])
    ax.plot([0, 1], [hm, pm], color=BLUE, lw=2.2, marker="_", ms=14, zorder=4)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["habit", "pulsed"], fontsize=8); ax.set_xlim(-0.4, 1.4)
    ax.annotate(f"{hm:.2f}", (0, hm), xytext=(-18, 0), textcoords="offset points", fontsize=7.5, color=GRAY)
    ax.annotate(f"{pm:.2f}  p = 0.006", (1, pm), xytext=(6, 0), textcoords="offset points", fontsize=7.5, color=BLUE)
    ax.set_title("same vectors, pulsed (habituated)", fontsize=8.5); ax.set_ylim(0.4, 5.6); ax.set_yticks([])
    fig.tight_layout(); fig.savefig(OUT / "fig_p4_templaw.png", bbox_inches="tight"); plt.close(fig)

    # ladder with per-premise points
    fig, ax = plt.subplots(figsize=(4.6, 2.8))
    ladder = [(1.0, "pulseG"), (1.5, "pulseG15"), (2.0, "pulseG20")]
    for x, arm in ladder:
        ys = [SP[f"p{i}_{arm}"] for i in range(10) if f"p{i}_{arm}" in SP]
        ax.scatter([x + rng.uniform(-0.04, 0.04) for _ in ys], ys, s=10, color=BLUE, alpha=0.4, zorder=2)
    ax.plot([x for x, _ in ladder], [_np2.mean([SP[f"p{i}_{arm}"] for i in range(10)]) for _, arm in ladder],
            color=BLUE, lw=1.8, marker="o", ms=5, zorder=4)
    ys = [SP[f"p{i}_pulse"] for i in range(10)]
    ax.scatter([1.0 + rng.uniform(-0.04, 0.04) for _ in ys], ys, s=10, color=PURPLE, alpha=0.4, marker="s", zorder=2)
    ax.scatter([1.0], [_np2.mean(ys)], color=PURPLE, marker="s", s=40, zorder=5)
    ax.annotate("unguarded pulse", (1.0, _np2.mean(ys)), xytext=(8, -3), textcoords="offset points", fontsize=8, color=PURPLE)
    ax.annotate("guarded ladder", (1.5, _np2.mean([SP[f"p{i}_pulseG15"] for i in range(10)])), xytext=(8, -12),
                textcoords="offset points", fontsize=8, color=BLUE)
    yi = [SP[f"p{i}_inter"] for i in range(10)]
    ax.scatter([2.35 + rng.uniform(-0.03, 0.03) for _ in yi], yi, s=10, color="#333333", alpha=0.4, zorder=2)
    ax.axhline(_np2.mean(yi), color=GRAY, lw=0.9, ls="--")
    ax.annotate(f"text interruption ({_np2.mean(yi):.2f})", (2.42, _np2.mean(yi)), xytext=(0, 4), textcoords="offset points",
                ha="right", fontsize=8, color="#333333")
    ax.set_xlabel(r"dose $\alpha$ (guarded)   |   inter"); ax.set_ylabel("judged surprise"); ax.set_ylim(0.8, 5.4)
    ax.set_xticks([1.0, 1.5, 2.0, 2.35]); ax.set_xticklabels(["1.0", "1.5", "2.0", "inter"])
    fig.tight_layout(); fig.savefig(OUT / "fig_p4_ladder.png", bbox_inches="tight"); plt.close(fig)
    print("fig_p4_templaw / ladder with per-premise points ok")
except FileNotFoundError as e:
    print("per-premise figures SKIPPED:", e)

# the 57-cell band map (exploratory, proxies) + the judged H2 grid
try:
    layers, alphas_b = [6, 18, 30], [0.25, 0.5, 1, 2, 4, 8]
    grid = {"clean_nll_mean": _np2.full((3, 6), _np2.nan), "distinct4": _np2.full((3, 6), _np2.nan)}
    for li, L in enumerate(layers):
        for ai, a in enumerate(alphas_b):
            an = str(a).rstrip("0").rstrip(".") if isinstance(a, float) else str(a)
            vals = {k: [] for k in grid}
            for s in range(3):
                f = ROOT / "runs/state_band" / f"tr_L{L}_a{an}_s{s}" / "state.json"
                if f.exists():
                    st = _json.loads(f.read_text())
                    for k in grid:
                        vals[k].append(st[k])
            for k in grid:
                if vals[k]:
                    grid[k][li, ai] = _np2.mean(vals[k])
    jl, ja = [14, 18, 22], [("0.25", 0.25), ("0.5", 0.5), ("0.75", 0.75)]
    jg = {"surprise": _np2.full((3, 3), _np2.nan), "coherence": _np2.full((3, 3), _np2.nan)}
    for dim, M in (("surprise", S2), ("coherence", C2)):
        for li, L in enumerate(jl):
            for ai, (an, _) in enumerate(ja):
                ys = [M[f"p{i}_L{L}_a{an}"] for i in range(10) if f"p{i}_L{L}_a{an}" in M]
                if ys:
                    jg[dim][li, ai] = _np2.mean(ys)
    fig, axes = plt.subplots(1, 4, figsize=(10.2, 2.5), gridspec_kw={"width_ratios": [1.3, 1.3, 0.9, 0.9]})
    panels = [(axes[0], grid["clean_nll_mean"], layers, [str(a) for a in alphas_b], "clean NLL (proxy, 57 cells)", "Reds"),
              (axes[1], grid["distinct4"], layers, [str(a) for a in alphas_b], "distinct-4 (proxy, 57 cells)", "Blues_r"),
              (axes[2], jg["surprise"], jl, [a for a, _ in ja], "judged surprise (H2)", "Blues"),
              (axes[3], jg["coherence"], jl, [a for a, _ in ja], "judged coherence (H2)", "Greens")]
    for ax, G, rows, cols, ttl, cmap in panels:
        im = ax.imshow(G, cmap=cmap, aspect="auto")
        ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, fontsize=7.5)
        ax.set_yticks(range(len(rows))); ax.set_yticklabels([f"L{r}" for r in rows], fontsize=7.5)
        ax.set_title(ttl, fontsize=8.5); ax.set_xlabel(r"dose $\alpha$", fontsize=8)
        for i in range(G.shape[0]):
            for j in range(G.shape[1]):
                if not _np2.isnan(G[i, j]):
                    ax.text(j, i, f"{G[i, j]:.2f}", ha="center", va="center", fontsize=6.5,
                            color="white" if (G[i, j] - _np2.nanmin(G)) / (_np2.nanmax(G) - _np2.nanmin(G) + 1e-9) > 0.6 else "black")
    fig.tight_layout(); fig.savefig(OUT / "fig_p4_bandmap.png", bbox_inches="tight"); plt.close(fig)
    print("fig_p4_bandmap ok")
except Exception as e:
    print("fig_p4_bandmap SKIPPED:", e)

import shutil as _sh
for name in ("fig_p4_templaw.png", "fig_p4_ladder.png", "fig_p4_spectra.png", "fig_p4_bandmap.png"):
    src = OUT / name
    if src.exists():
        (ROOT / "paper4/figures").mkdir(parents=True, exist_ok=True)
        _sh.copy2(src, ROOT / "paper4/figures" / name)
print("paper4 figures synced")
