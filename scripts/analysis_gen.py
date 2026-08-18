#!/usr/bin/env python3
"""Seed-level analysis under the generated-only window protocol (external
review, P0). Unit of inference = the cell (one premise, one condition, 4,500
tokens). Per cell: mean judged score over its windows (offset 32 after each
injection = the primary post-interruption measure; all offsets = the stream
measure; uniform grid for uninterrupted arms). Per condition: mean of cell
means with a bootstrap CI over cells (n = 10 seeds); vs a reference arm:
paired-by-seed differences with an exact sign-flip permutation p-value
(2^10 combinations) and Cliff's delta on cell means. Window-level statistics
are not used here (they are in the appendix as descriptive).

Writes docs/APPENDIX_GEN.md and docs/figures/fig9_*.png.

    python scripts/analysis_gen.py
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RUNS, FIG, DOCS = ROOT / "runs", ROOT / "docs" / "figures", ROOT / "docs"
DIMS = ("surprise", "connection", "coherence")
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5})
PAL = {"bare": "#4a3aa7", "bare_habit": "#7a7a7a", "bare_reseed": "#eda100", "scaffold0": "#2a78d6", "abl_salience": "#1baf7a",
       "clock_reenc": "#2a78d6", "clock_premise": "#eb6834", "clock_self": "#1baf7a", "sal_reenc": "#c2185b",
       "clock75": "#9ecae1", "clock300": "#4292c6", "clock600": "#08306b", "clock900": "#041c3d", "clock900_reenc": "#7b1fa2",
       "nohabit150": "#e07b39", "nohabit300": "#b35a1f", "sham_break300": "#8c8c8c", "sham_cont300": "#5c5c5c",
       "bare_eos": "#3f8f3f", "habit_strong": "#4d4d4d", "reset_reseed300": "#c2185b", "reset_break300": "#e57373"}
LABEL = {"bare": "bare", "bare_habit": "bare + habituation", "bare_reseed": "habituation + reseed 150",
         "scaffold0": "DREAM scaffold", "abl_salience": "salience only", "clock_reenc": "re-encounter stitch 150",
         "clock_premise": "premise 150", "clock_self": "own past 150", "sal_reenc": "salience-timed stitch",
         "clock75": "reseed 75", "clock300": "reseed 300", "clock600": "reseed 600", "clock900": "reseed 900",
         "clock900_reenc": "stitch 900", "nohabit150": "reseed 150, no habituation", "nohabit300": "reseed 300, no habituation",
         "sham_break300": "paragraph break 300 (sham)", "sham_cont300": "continuity connective 300 (sham)",
         "bare_eos": "habituation, EOS allowed", "habit_strong": "habituation 1.3", "reset_reseed300": "reset + new subject 300",
         "reset_break300": "reset + break 300"}


def load_gen(run: str):
    rows = []
    for name in ("rejudge_gen.json", "rejudge_gen_w2.json"):
        p = RUNS / run / name
        if p.exists():
            rows.extend(json.loads(p.read_text()))
    seen, out = set(), []
    for r in rows:
        k = (r["cell"], r["step"])
        if k in seen or r.get("surprise") is None:
            continue
        seen.add(k); r["run"] = run; r["seed"] = r["cell"].split("_", 1)[0]
        out.append(r)
    return out


def cell_means(rows, cond, dim, offset="primary"):
    """{seed: mean over the cell's windows}. offset: 'primary' (since==32 or grid), 'all', or an int."""
    by = {}
    for r in rows:
        if r["cond"] != cond:
            continue
        s = r.get("since")
        if offset == "primary" and s not in (32, None):
            continue
        if isinstance(offset, int) and s != offset:
            continue
        by.setdefault(r["seed"], []).append(r[dim])
    return {k: float(np.mean(v)) for k, v in by.items()}


def boot_ci(x, n=10000, seed=0):
    x = np.asarray(x, float)
    if len(x) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n, len(x)))
    m = x[idx].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def paired(a: dict, b: dict):
    """Paired-by-seed differences a - b: mean, bootstrap CI, exact sign-flip permutation p (two-sided), Cliff's delta on cell means."""
    seeds = sorted(set(a) & set(b))
    if len(seeds) < 3:
        return None
    d = np.array([a[s] - b[s] for s in seeds])
    lo, hi = boot_ci(d)
    obs = abs(d.mean())
    n = len(d)
    count = 0
    for signs in itertools.product((1, -1), repeat=n):
        if abs((d * np.array(signs)).mean()) >= obs - 1e-12:
            count += 1
    p_perm = count / 2 ** n
    av = np.array([a[s] for s in seeds]); bv = np.array([b[s] for s in seeds])
    gt = sum((x > bv).sum() for x in av); lt = sum((x < bv).sum() for x in av)
    delta = (gt - lt) / (len(av) * len(bv))
    return {"n": n, "mean": float(d.mean()), "lo": lo, "hi": hi, "p_perm": p_perm, "delta": float(delta), "d": d}


md = ["# Appendix — generated-only windows, seed-level inference (auto-generated by scripts/analysis_gen.py)\n",
      "Windows of 96 model-generated tokens starting 32 tokens after each injection (none crossing an injection); "
      "uniform grid for uninterrupted arms; the judge sees the 600 preceding tokens as context. Unit = cell (premise); "
      "CIs are bootstrap over cells; paired comparisons use exact sign-flip permutation p-values on the 10 paired "
      "differences and Cliff's delta on cell means. Opus 5, k=5, median per window.\n"]


def table(title, rows, header):
    md.append(f"\n### {title}\n")
    md.append("| " + " | ".join(header) + " |")
    md.append("|" + "---|" * len(header))
    for r in rows:
        md.append("| " + " | ".join(str(x) for x in r) + " |")


def block(title, pool, spec, ref, fname=None, offset="primary"):
    """spec: list of (cond, label). ref: index. Writes a table + a paired dot figure."""
    per = {c: {d: cell_means(pool, c, d, offset) for d in DIMS} for c, _ in spec}
    rows = []
    for c, lab in spec:
        n = len(per[c]["surprise"])
        if n == 0:
            rows.append([lab, 0, "—", "—", "—"]); continue
        cells = []
        for d in DIMS:
            v = list(per[c][d].values()); lo, hi = boot_ci(v)
            cells.append(f"{np.mean(v):.2f} [{lo:.2f}, {hi:.2f}]")
        rows.append([lab, n] + cells)
    table(title + " — cell means (mean over cells [95% CI over cells])", rows,
          ["condition", "n cells", "surprise", "connection", "coherence"])
    ref_c = spec[ref][0]
    prow = []
    for c, lab in spec:
        if c == ref_c:
            continue
        for d in DIMS:
            pr = paired(per[c][d], per[ref_c][d])
            if pr is None:
                continue
            star = "**" if (pr["lo"] > 0 or pr["hi"] < 0) else ""
            prow.append([lab, d, f"{star}{pr['mean']:+.2f} [{pr['lo']:+.2f}, {pr['hi']:+.2f}]{star}",
                         f"{pr['p_perm']:.3f}", f"{pr['delta']:+.2f}", pr["n"]])
    table(f"vs {spec[ref][1]} — paired by seed", prow, ["condition", "dim", "Δ [CI]", "p (perm)", "Cliff δ", "n seeds"])
    if fname:
        conds = [(c, l) for c, l in spec if per[c]["surprise"]]
        fig, axes = plt.subplots(1, 3, figsize=(3.6 * 3 + 1, 3.8), sharey=True)
        for ax, d in zip(axes, DIMS):
            seeds = sorted(set.intersection(*[set(per[c][d]) for c, _ in conds])) if conds else []
            for s in seeds:
                ys = [per[c][d][s] for c, _ in conds]
                ax.plot(range(len(conds)), ys, "-", color="#999", lw=0.7, alpha=0.7, zorder=1)
            for i, (c, l) in enumerate(conds):
                v = list(per[c][d].values()); lo, hi = boot_ci(v)
                ax.scatter([i] * len(v), v, s=16, color=PAL.get(c, "#666"), zorder=3, alpha=0.85)
                ax.plot([i - 0.25, i + 0.25], [np.mean(v)] * 2, color=PAL.get(c, "#666"), lw=2.5, zorder=4)
                ax.plot([i, i], [lo, hi], color=PAL.get(c, "#666"), lw=1.2, zorder=4)
            ax.set_xticks(range(len(conds))); ax.set_xticklabels([l.replace(" ", "\n", 1) for _, l in conds], fontsize=7)
            ax.set_title(d, fontsize=10); ax.set_ylim(-0.3, 10.3)
        axes[0].set_ylabel("cell mean of judged score (one point per premise)")
        fig.suptitle(title, fontsize=10, y=1.02); fig.tight_layout()
        fig.savefig(FIG / fname, dpi=170, bbox_inches="tight"); plt.close(fig)
        print("figure ->", FIG / fname)
    return per


def main() -> None:
    main30 = load_gen("dream_scaffold") + load_gen("dream_b2") + load_gen("dream_b3")
    fam8b = load_gen("dream_fam8b"); olmo = load_gen("dream_famolmo")
    md.append(f"{len(main30)} judged windows on the main generator, {len(fam8b)} on Qwen3-8B, {len(olmo)} on OLMo-2.\n")

    # Q1: the 2x2 factorial habituation x interruption (+ scaffold, + baselines)
    block("Q1 — habituation × interruption (period 150) and baselines", main30,
          [("bare", "bare"), ("bare_habit", "bare + habituation"), ("nohabit150", "reseed 150, no habituation"),
           ("bare_reseed", "habituation + reseed 150"), ("scaffold0", "DREAM scaffold"),
           ("habit_strong", "habituation 1.3"), ("bare_eos", "habituation, EOS allowed")],
          ref=1, fname="fig9_q1_factorial.png")
    # Q2: content at period 150
    block("Q2 — what is injected (period 150)", main30,
          [("bare_reseed", "neutral subject change"), ("clock_reenc", "re-encounter stitch"),
           ("clock_premise", "the premise itself"), ("clock_self", "the stream's own past")],
          ref=0, fname="fig9_q2_content.png")
    # Q3: boundary vs content vs context at period 300 (the reviewer's factorial)
    block("Q3 — period 300: what carries the effect (context preserved vs reset; semantic change vs neutral boundary)", main30,
          [("bare_habit", "no interruption"), ("sham_break300", "paragraph break (sham)"),
           ("sham_cont300", "continuity connective (sham)"), ("clock300", "subject change, context preserved"),
           ("nohabit300", "subject change, no habituation"), ("reset_reseed300", "subject change, context reset"),
           ("reset_break300", "break, context reset")],
          ref=0, fname="fig9_q3_boundary_context.png")
    # Q4: timing
    block("Q4 — timing: salience vs clock (same stitch)", main30,
          [("clock_reenc", "stitch on the clock 150"), ("clock900_reenc", "stitch on the clock 900"),
           ("clock900", "neutral change 900"), ("sal_reenc", "stitch on salience events"), ("abl_salience", "salience only")],
          ref=1, fname="fig9_q4_timing.png")
    # Q5: period (post-interruption window, offset 32) and decay curve
    block("Q5 — period of the neutral change: the window 32–128 tokens after the injection", main30,
          [("bare_reseed", "150"), ("clock300", "300"), ("clock600", "600"), ("clock900", "900")],
          ref=0, fname="fig9_q5_period.png")
    # decay: cell means by offset for 300/600/900
    md.append("\n### Q5b — decay: cell mean surprise by tokens since the injection (window start), generated text only\n")
    md.append("| period | " + " | ".join(f"offset {o}" for o in (32, 160, 300, 450, 600, 750)) + " |")
    md.append("|---|" + "---|" * 6)
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    for c, lab in (("bare_reseed", "150"), ("clock300", "300"), ("clock600", "600"), ("clock900", "900")):
        xs, ys, es = [], [], []
        row = []
        for o in (32, 160, 300, 450, 600, 750):
            cm = cell_means(main30, c, "surprise", o)
            if len(cm) >= 3:
                v = list(cm.values()); lo, hi = boot_ci(v)
                xs.append(o + 48); ys.append(np.mean(v)); es.append((np.mean(v) - lo, hi - np.mean(v)))
                row.append(f"{np.mean(v):.2f} (n={len(v)})")
            else:
                row.append("—")
        md.append(f"| {lab} | " + " | ".join(row) + " |")
        if xs:
            ax.errorbar(xs, ys, yerr=np.array(es).T, fmt="-o", ms=4, capsize=2, color=PAL.get(c, "#666"), label=f"every {lab}")
    ax.set_xlabel("window centre, tokens since the injection (generated text only)"); ax.set_ylabel("cell mean surprise (95% CI over cells)")
    ax.legend(fontsize=8, frameon=False); ax.set_title("Surprise after an interruption, without the injected text in the window", fontsize=9)
    fig.tight_layout(); fig.savefig(FIG / "fig9_q5b_decay.png", dpi=170, bbox_inches="tight"); plt.close(fig)
    # Q6: families
    for pool, name, tag in ((fam8b, "Qwen3-8B-Base", "fam8b"), (olmo, "OLMo-2-13B", "olmo")):
        block(f"Q6 — the ladder on {name}", pool,
              [("bare", "bare"), ("bare_habit", "bare + habituation"), ("bare_reseed", "habituation + reseed 150"), ("scaffold0", "DREAM scaffold")],
              ref=1, fname=f"fig9_q6_{tag}.png")
    out = DOCS / "APPENDIX_GEN.md"
    out.write_text("\n".join(md) + "\n")
    print("\n".join(md)); print("->", out)


if __name__ == "__main__":
    main()
