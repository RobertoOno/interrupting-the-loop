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
         "reset_break300": "reset + break 300", "judge_gate150": "judge-gated interruption 150",
         "schema300": "schematic recap 300 (reset)", "anomaly300": "open question 300 (preserved)"}


def load_gen(run: str):
    rows = []
    for name in ("rejudge_gen.json", "rejudge_gen_w2.json", "rejudge_gen_w3.json"):
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
    """{seed: mean over the cell's windows}. offset: 'primary' (since==32 or grid), 'all', 'deep' (since >= 300), or an int."""
    by = {}
    for r in rows:
        if r["cond"] != cond:
            continue
        s = r.get("since")
        if offset == "primary" and s not in (32, None):
            continue
        if offset == "deep" and (s is None or s < 300):
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


def bh_fdr(ps):
    """Benjamini-Hochberg q-values (monotone) for a family of p-values."""
    ps = list(ps); m = len(ps)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: ps[i])
    q = [0.0] * m; prev = 1.0
    for rank, i in reversed(list(enumerate(order, 1))):
        prev = min(prev, ps[i] * m / rank); q[i] = prev
    return q


def paired(a: dict, b: dict, alternative: str = "two-sided"):
    """Paired-by-seed differences a - b: mean, bootstrap CI, exact sign-flip permutation p
    (two-sided, or one-sided 'greater' = a > b), Cliff's delta on cell means."""
    seeds = sorted(set(a) & set(b))
    if len(seeds) < 3:
        return None
    d = np.array([a[s] - b[s] for s in seeds])
    lo, hi = boot_ci(d)
    n = len(d)
    count = 0
    if alternative == "greater":
        obs = d.mean()
        for signs in itertools.product((1, -1), repeat=n):
            if (d * np.array(signs)).mean() >= obs - 1e-12:
                count += 1
    else:
        obs = abs(d.mean())
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
    prow, ps = [], []
    for c, lab in spec:
        if c == ref_c:
            continue
        for d in DIMS:
            pr = paired(per[c][d], per[ref_c][d])
            if pr is None:
                continue
            star = "**" if (pr["lo"] > 0 or pr["hi"] < 0) else ""
            prow.append([lab, d, f"{star}{pr['mean']:+.2f} [{pr['lo']:+.2f}, {pr['hi']:+.2f}]{star}",
                         f"{pr['p_perm']:.3f}", None, f"{pr['delta']:+.2f}", pr["n"]])
            ps.append(pr["p_perm"])
    for row, q in zip(prow, bh_fdr(ps)):  # BH q-values within this table's family of comparisons
        row[4] = f"{q:.3f}"
    table(f"vs {spec[ref][1]} — paired by seed", prow, ["condition", "dim", "Δ [CI]", "p (perm)", "q (BH)", "Cliff δ", "n seeds"])
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
        fig.suptitle(title.replace(" — ", ": "), fontsize=10, y=1.02); fig.tight_layout()
        fig.savefig(FIG / fname, dpi=170, bbox_inches="tight"); plt.close(fig)
        print("figure ->", FIG / fname)
    return per


def main() -> None:
    main30 = load_gen("dream_scaffold") + load_gen("dream_b2") + load_gen("dream_b3") + load_gen("dream_m")
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
    # Q3b: direct pairs of the factorial (interruption arms against each other)
    md.append("\n### Q3b — direct paired contrasts among the interruption arms\n")
    md.append("| contrast | dim | Δ [CI] | p (perm) | Cliff δ | n |")
    md.append("|---|---|---|---|---|---|")
    for a, b, lab in (("reset_reseed300", "clock300", "reset vs preserved (300)"),
                      ("clock300", "nohabit300", "with vs without habituation (300)"),
                      ("bare_reseed", "nohabit150", "with vs without habituation (150)"),
                      ("reset_reseed300", "reset_break300", "subject change vs break, both reset (300)"),
                      ("clock300", "sham_break300", "subject change vs break, both preserved (300)")):
        for d in DIMS:
            pr = paired(cell_means(main30, a, d), cell_means(main30, b, d))
            if pr:
                star = "**" if (pr["lo"] > 0 or pr["hi"] < 0) else ""
                md.append(f"| {lab} | {d} | {star}{pr['mean']:+.2f} [{pr['lo']:+.2f}, {pr['hi']:+.2f}]{star} | {pr['p_perm']:.3f} | {pr['delta']:+.2f} | {pr['n']} |")
    # Q4: timing
    block("Q4 — timing: salience vs clock (same stitch)", main30,
          [("clock_reenc", "stitch on the clock 150"), ("clock900_reenc", "stitch on the clock 900"),
           ("clock900", "neutral change 900"), ("sal_reenc", "stitch on salience events"), ("abl_salience", "salience only")],
          ref=1, fname="fig9_q4_timing.png")
    # Q4b: deep into the segment (>= 300 generated tokens after the last injection): where the stream is left alone
    block("Q4b — deep windows (at least 300 tokens after the last injection): the stream when it is left alone", main30,
          [("clock900_reenc", "stitch on the clock 900"), ("clock900", "neutral change 900"), ("clock600", "neutral change 600"),
           ("sal_reenc", "stitch on salience events"), ("scaffold0", "DREAM scaffold")],
          ref=0, fname=None, offset="deep")
    # Q5: period (post-interruption window, offset 32) and decay curve
    block("Q5 — period of the neutral change: the window 32–128 tokens after the injection", main30,
          [("bare_reseed", "150"), ("clock300", "300"), ("clock600", "600"), ("clock900", "900")],
          ref=0, fname="fig9_q5_period.png")
    # decay: cell means by offset for 300/600/900
    md.append("\n### Q5b — decay: cell mean surprise by tokens since the injection (window start), generated text only; "
              "stream estimate = offset means weighted by the stretch of the segment each window represents\n")
    md.append("| period | " + " | ".join(f"offset {o}" for o in (32, 160, 300, 450, 600, 750)) + " | stream estimate (S / C / H) |")
    md.append("|---|" + "---|" * 7)
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    for c, lab, period in (("bare_reseed", "150", 150), ("clock300", "300", 300), ("clock600", "600", 600), ("clock900", "900", 900)):
        xs, ys, es = [], [], []
        row = []
        offs = [o for o in (32, 160, 300, 450, 600, 750) if o + 96 <= period]
        stream = {}
        for d in DIMS:
            num = den = 0.0
            for i, o in enumerate(offs):
                cm = cell_means(main30, c, d, o)
                if len(cm) >= 3:
                    w = (offs[i + 1] if i + 1 < len(offs) else period) - (0 if i == 0 else o)
                    num += w * np.mean(list(cm.values())); den += w
            stream[d] = num / den if den else float("nan")
        for o in (32, 160, 300, 450, 600, 750):
            cm = cell_means(main30, c, "surprise", o)
            if len(cm) >= 3:
                v = list(cm.values()); lo, hi = boot_ci(v)
                xs.append(o + 48); ys.append(np.mean(v)); es.append((np.mean(v) - lo, hi - np.mean(v)))
                row.append(f"{np.mean(v):.2f} (n={len(v)})")
            else:
                row.append("—")
        md.append(f"| {lab} | " + " | ".join(row) + f" | {stream['surprise']:.2f} / {stream['connection']:.2f} / {stream['coherence']:.2f} |")
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
    # protocol agreement: condition means under the event protocol (first version) vs generated-only
    md.append("\n### Protocol agreement — condition means, event windows (v1) vs generated-only windows (unit = cell)\n")
    ev = []
    for run in ("dream_scaffold", "dream_b2", "dream_b3"):
        pth = RUNS / run / "rejudge_surprise.json"
        if pth.exists():
            for r in json.loads(pth.read_text()):
                if r.get("surprise") is not None and r["step"] >= 100:
                    ev.append({**r, "run": run, "seed": r["cell"].split("_", 1)[0]})
    md.append("| condition | " + " | ".join(f"{d} event / gen" for d in DIMS) + " | n cells (event / gen) |")
    md.append("|---|" + "---|" * (len(DIMS) + 1))
    xs, ys = {d: [] for d in DIMS}, {d: [] for d in DIMS}
    for c in sorted({r["cond"] for r in main30} & {r["cond"] for r in ev}):
        row = [LABEL.get(c, c)]
        ne = ng = 0
        for d in DIMS:
            e = cell_means(ev, c, d, "all"); g = cell_means(main30, c, d, "primary")
            ne, ng = len(e), len(g)
            if e and g:
                xs[d].append(np.mean(list(e.values()))); ys[d].append(np.mean(list(g.values())))
                row.append(f"{np.mean(list(e.values())):.2f} / {np.mean(list(g.values())):.2f}")
            else:
                row.append("—")
        row.append(f"{ne} / {ng}")
        md.append("| " + " | ".join(row) + " |")
    from scipy.stats import spearmanr
    for d in DIMS:
        if len(xs[d]) >= 4:
            rho, pv = spearmanr(xs[d], ys[d])
            md.append(f"\nSpearman across conditions ({d}): rho = {rho:+.2f} (n = {len(xs[d])} conditions).")
    # ---- self-copy: how much of a judged window is a verbatim reproduction of the stream's own earlier text
    flags_p = RUNS / "selfcopy_flags.json"
    if flags_p.exists():
        flags = json.loads(flags_p.read_text())
        def flag(r):
            return flags.get(r["run"], {}).get(r["cell"], {}).get(str(r["step"]))
        md.append("\n## Self-copy — verbatim reproduction of the stream's own earlier text inside the judged windows\n")
        md.append("A window is *copied* when at least half of its 12-token shingles occur earlier in the same stream; "
                  "*visible* when they occur within the 600 tokens the judge sees. Post-interruption / grid windows only. "
                  "Fresh = not copied.\n")
        md.append("| condition | n windows | copied | copied, source outside the judge's 600 tokens | fresh windows: S / C / H (cell means, n cells) | copied windows: S / C / H |")
        md.append("|---|---|---|---|---|---|")
        fresh_means = {}
        for c in ["bare", "bare_habit", "habit_strong", "bare_eos", "nohabit150", "bare_reseed", "nohabit300", "clock300", "clock600", "clock900",
                  "clock_reenc", "clock900_reenc", "clock_premise", "clock_self", "sal_reenc", "sham_break300", "sham_cont300",
                  "reset_reseed300", "reset_break300", "scaffold0", "schema300", "anomaly300"]:
            rs = [r for r in main30 if r["cond"] == c and r.get("since") in (32, None) and flag(r) is not None]
            if not rs:
                continue
            cop = [r for r in rs if flag(r)["frac"] >= 0.5]; fr = [r for r in rs if flag(r)["frac"] < 0.5]
            hidden = [r for r in cop if flag(r)["frac_recent"] < 0.5]
            fm = {}
            for d in DIMS:
                by = {}
                for r in fr:
                    by.setdefault(r["seed"], []).append(r[d])
                fm[d] = {k: float(np.mean(v)) for k, v in by.items()}
            fresh_means[c] = fm
            fs = " / ".join(f"{np.mean(list(fm[d].values())):.2f}" for d in DIMS) if fm["surprise"] else "—"
            cs = " / ".join(f"{np.mean([r[d] for r in cop]):.2f}" for d in DIMS) if cop else "—"
            md.append(f"| {LABEL.get(c, c)} | {len(rs)} | {100*len(cop)/len(rs):.0f}% | {100*len(hidden)/len(rs):.0f}% | {fs} (n={len(fm['surprise'])}) | {cs} |")
        # the same on the other generators (ladder arms)
        md.append("\n### Self-copy on the other generators (ladder arms; copied = >= 50% shingles seen earlier in the stream)\n")
        md.append("| generator | condition | n windows | copied | fresh windows: S / C / H (n cells) |")
        md.append("|---|---|---|---|---|")
        for pool, gname in ((fam8b, "Qwen3-8B-Base"), (olmo, "OLMo-2-13B")):
            for c in ("bare", "bare_habit", "bare_reseed", "scaffold0"):
                rs = [r for r in pool if r["cond"] == c and r.get("since") in (32, None) and flag(r) is not None]
                if not rs:
                    continue
                cop = [r for r in rs if flag(r)["frac"] >= 0.5]; fr = [r for r in rs if flag(r)["frac"] < 0.5]
                by = {}
                for r in fr:
                    by.setdefault(r["seed"], []).append(r)
                fs = " / ".join(f"{np.mean([np.mean([x[d] for x in v]) for v in by.values()]):.2f}" for d in DIMS) if by else "—"
                md.append(f"| {gname} | {LABEL.get(c, c)} | {len(rs)} | {100*len(cop)/len(rs):.0f}% | {fs} (n={len(by)}) |")
        md.append("\n### Fresh windows only — paired contrasts (cells with at least one fresh window)\n")
        md.append("| contrast | dim | Δ [CI] | p (perm) | Cliff δ | n seeds |")
        md.append("|---|---|---|---|---|---|")
        for a, b, lab in (("bare_reseed", "bare_habit", "interruption 150 vs habituation"), ("clock300", "bare_habit", "interruption 300 vs habituation"),
                          ("reset_reseed300", "bare_habit", "reset + subject change 300 vs habituation"), ("reset_reseed300", "clock300", "reset vs preserved (300)"),
                          ("scaffold0", "bare_habit", "scaffold vs habituation"), ("clock900", "bare_habit", "interruption 900 vs habituation"),
                          ("schema300", "reset_reseed300", "schematic recap vs reset (300)"), ("anomaly300", "clock300", "open question vs neutral subject (300)")):
            for d in DIMS:
                if a in fresh_means and b in fresh_means:
                    pr = paired(fresh_means[a][d], fresh_means[b][d])
                    if pr:
                        star = "**" if (pr["lo"] > 0 or pr["hi"] < 0) else ""
                        md.append(f"| {lab} | {d} | {star}{pr['mean']:+.2f} [{pr['lo']:+.2f}, {pr['hi']:+.2f}]{star} | {pr['p_perm']:.3f} | {pr['delta']:+.2f} | {pr['n']} |")
    # ---- document-level judgment (whole streams, injected sentences removed; one score per cell)
    DDIMS = ("integration", "development", "coherence", "surprise")
    docs = []
    for name in ("document_judgments_a.json", "document_judgments_b.json", "document_judgments_c.json", "document_judgments_gate.json", "document_judgments_m.json"):
        pth = RUNS / name
        if pth.exists():
            docs.extend(json.loads(pth.read_text()))
    if docs:
        md.append(f"\n## Document level — the whole 4,500-token stream, injected sentences removed, Opus k=3 ({len(docs)} documents)\n")
        md.append("Unit = cell (one document each). Integration: parts taken up and joined later; development: something builds rather "
                  "than restarts or repeats; coherence: reads as one text; surprise: the whole goes somewhere unpredictable yet sensible.\n")
        conds_doc = ["bare", "bare_habit", "bare_reseed", "clock300", "nohabit300", "sham_break300", "reset_reseed300", "reset_break300", "scaffold0", "judge_gate150", "schema300", "anomaly300"]
        others = sorted({r["cond"] for r in docs} - set(conds_doc))
        md.append("| condition | n | " + " | ".join(DDIMS) + " |")
        md.append("|---|---|" + "---|" * len(DDIMS))
        dmeans = {}
        for c in conds_doc + others:
            rs = [r for r in docs if r["cond"] == c]
            if not rs:
                continue
            cells = []
            for d in DDIMS:
                v = [r[d] for r in rs]; lo, hi = boot_ci(v)
                cells.append(f"{np.mean(v):.2f} [{lo:.2f}, {hi:.2f}]")
                dmeans[(c, d)] = {r["seed"]: r[d] for r in rs}
            md.append(f"| {LABEL.get(c, c)} | {len(rs)} | " + " | ".join(cells) + " |")
        md.append("\n### Document level — paired contrasts\n")
        md.append("| contrast | dim | Δ [CI] | p (perm) | Cliff δ | n |")
        md.append("|---|---|---|---|---|---|")
        for a, b, lab in (("bare_reseed", "bare_habit", "interruption 150 vs habituation"),
                          ("clock300", "bare_habit", "interruption 300 (preserved) vs habituation"),
                          ("reset_reseed300", "bare_habit", "reset + subject change 300 vs habituation"),
                          ("reset_reseed300", "clock300", "reset vs preserved (300)"),
                          ("scaffold0", "bare_habit", "scaffold vs habituation"),
                          ("sham_break300", "bare_habit", "sham break vs habituation"),
                          ("bare_habit", "bare", "habituation vs bare"),
                          ("judge_gate150", "bare_reseed", "judge-gated vs clock 150"),
                          ("judge_gate150", "bare_habit", "judge-gated vs habituation"),
                          ("schema300", "reset_reseed300", "schematic recap vs reset (300)"),
                          ("schema300", "clock300", "schematic recap vs preserved (300)"),
                          ("anomaly300", "clock300", "open question vs neutral subject (300)")):
            for d in DDIMS:
                if (a, d) in dmeans and (b, d) in dmeans:
                    pr = paired(dmeans[(a, d)], dmeans[(b, d)])
                    if pr:
                        star = "**" if (pr["lo"] > 0 or pr["hi"] < 0) else ""
                        md.append(f"| {lab} | {d} | {star}{pr['mean']:+.2f} [{pr['lo']:+.2f}, {pr['hi']:+.2f}]{star} | {pr['p_perm']:.3f} | {pr['delta']:+.2f} | {pr['n']} |")
        # battery M pre-registered document contrasts (M1-M3 one-sided; docsum = mean of integration and development)
        if any(r["cond"] == "schema300" for r in docs):
            md.append("\n### Battery M — pre-registered document-level contrasts (docsum = (integration+development)/2; one-sided)\n")
            md.append("| hypothesis | contrast | Δ [CI] | p | n |"); md.append("|---|---|---|---|---|")
            def docsum(c):
                return {r["seed"]: (r["integration"] + r["development"]) / 2 for r in docs if r["cond"] == c}
            for hyp, a, b in (("M1 (primary)", "schema300", "reset_reseed300"), ("M2", "schema300", "clock300"), ("M3", "anomaly300", "clock300")):
                pr = paired(docsum(a), docsum(b), "greater")
                if pr:
                    md.append(f"| {hyp} | {a} vs {b} | {pr['mean']:+.2f} [{pr['lo']:+.2f}, {pr['hi']:+.2f}] | {pr['p_perm']:.4f} | {pr['n']} |")
        # figure: document-level dots
        show = [c for c in conds_doc if any(r["cond"] == c for r in docs)]
        fig, axes = plt.subplots(1, 4, figsize=(14, 3.6), sharey=True)
        for ax, d in zip(axes, DDIMS):
            for i, c in enumerate(show):
                v = [r[d] for r in docs if r["cond"] == c]; lo, hi = boot_ci(v)
                ax.scatter([i] * len(v), v, s=14, color=PAL.get(c, "#666"), alpha=0.8, zorder=3)
                ax.plot([i - 0.25, i + 0.25], [np.mean(v)] * 2, color=PAL.get(c, "#666"), lw=2.5, zorder=4)
                ax.plot([i, i], [lo, hi], color=PAL.get(c, "#666"), lw=1.2, zorder=4)
            ax.set_xticks(range(len(show))); ax.set_xticklabels([LABEL.get(c, c).replace(" ", "\n", 1) for c in show], fontsize=6, rotation=45, ha="right")
            ax.set_title(d, fontsize=10); ax.set_ylim(-0.3, 10.3)
        axes[0].set_ylabel("document score (one point per premise)")
        fig.suptitle("The whole document, injected sentences removed (Opus, k=3)", fontsize=10, y=1.02); fig.tight_layout()
        fig.savefig(FIG / "fig9_document.png", dpi=170, bbox_inches="tight"); plt.close(fig)
    # ---- overnight follow-ups: unquantized 8B, post-trained 8B, reset ladders on 8B/OLMo, second genre, judge gate
    bf16 = load_gen("dream_fam8b_bf16"); inst = load_gen("dream_instruct8b")
    if bf16:
        block("P2 — the ladder on Qwen3-8B-Base without quantization (bf16)", bf16,
              [("bare", "bare"), ("bare_habit", "bare + habituation"), ("bare_reseed", "habituation + reseed 150")], ref=1, fname="fig9_bf16.png")
    if inst:
        block("P1 — the ladder on the post-trained Qwen3-8B (8-bit), no chat template", inst,
              [("bare", "bare"), ("bare_habit", "bare + habituation"), ("bare_reseed", "habituation + reseed 150")], ref=1, fname="fig9_instruct.png")
    for run, base, name in (("dream_fam8b_reset", "dream_fam8b", "Qwen3-8B-Base"), ("dream_famolmo_reset", "dream_famolmo", "OLMo-2-13B")):
        rr = load_gen(run)
        if rr:
            pool = rr + [r for r in load_gen(base) if r["cond"] == "bare_habit"]
            block(f"Reset vs preserved vs sham at period 300 on {name}", pool,
                  [("bare_habit", "no interruption"), ("sham_break300", "paragraph break (sham)"),
                   ("clock300", "subject change, context preserved"), ("reset_reseed300", "subject change, context reset")],
                  ref=0, fname=f"fig9_reset_{run.split('_')[1]}.png")
    genre = load_gen("dream_genre")
    if genre:
        block("Second genre — expository openings on the main generator (period 300)", genre,
              [("bare_habit", "no interruption"), ("clock300", "subject change, context preserved"), ("reset_reseed300", "subject change, context reset")],
              ref=0, fname="fig9_genre.png")
    gate = load_gen("dream_gate")
    if gate:
        pool = gate + [r for r in main30 if r["cond"] in ("bare_reseed", "clock300", "bare_habit")]
        block("Judge-gated interruption (DREAM's Review with a gate that opens) vs the clock", pool,
              [("bare_habit", "no interruption"), ("bare_reseed", "clock 150"), ("clock300", "clock 300"), ("judge_gate150", "judge-gated 150")],
              ref=1, fname="fig9_gate.png")
        # gate statistics: reads, finds, resulting period
        import glob as _glob
        reads = finds = 0; cells = 0
        for f in _glob.glob(str(RUNS / "dream_gate" / "s*_judge_gate150" / "run.json")):
            ev = json.loads(Path(f).read_text())["events"]; cells += 1
            reads += sum(1 for e in ev if e.get("kind") == "gate"); finds += sum(1 for e in ev if e.get("kind") == "gate" and e.get("passed"))
        if cells:
            md.append(f"\nGate: {reads} reads in {cells} cells, {finds} finds left to run ({100*finds/max(1,reads):.0f}%).")
    # ---- confirmatory battery (new premises, RNG seed 1): pre-registered contrasts (docs/PLANO.md, 2026-08-18)
    conf = load_gen("dream_confirm")
    if conf:
        md.append(f"\n## Confirmatory battery — ten new premises, RNG seed 1 ({len(conf)} judged windows)\n")
        block("Confirmatory — period 300 on new premises", conf,
              [("bare_habit", "no interruption"), ("clock300", "subject change, context preserved"),
               ("sham_break300", "paragraph break (sham)"), ("nohabit300", "subject change, no habituation"),
               ("reset_reseed300", "subject change, context reset")],
              ref=0, fname="fig9_confirm.png")
        md.append("\n### Pre-registered contrasts (exact one-sided sign-flip permutation unless stated)\n")
        md.append("| hypothesis | contrast | dim | Δ (mean of paired differences) [CI] | p | n seeds |")
        md.append("|---|---|---|---|---|---|")
        per = {c: {d: cell_means(conf, c, d, "primary") for d in DIMS} for c in ("bare_habit", "clock300", "sham_break300", "nohabit300", "reset_reseed300")}
        for hyp, a, b, d, alt in (("H1 (primary)", "clock300", "bare_habit", "surprise", "greater"),
                                  ("H2", "clock300", "sham_break300", "surprise", "greater"),
                                  ("H3", "clock300", "reset_reseed300", "connection", "greater"),
                                  ("H4 (two-sided)", "clock300", "nohabit300", "surprise", "two-sided")):
            pr = paired(per[a][d], per[b][d], alt)
            if pr:
                md.append(f"| {hyp} | {a} vs {b} | {d} | {pr['mean']:+.2f} [{pr['lo']:+.2f}, {pr['hi']:+.2f}] | {pr['p_perm']:.4f} | {pr['n']} |")
    # fresh-only versions of the pre-registered contrasts (self-copy flags), as a robustness check
    if conf and (RUNS / "selfcopy_flags.json").exists():
        flags = json.loads((RUNS / "selfcopy_flags.json").read_text())
        def fresh_cm(cond, dim):
            by = {}
            for r in conf:
                if r["cond"] != cond or r.get("since") not in (32, None):
                    continue
                f = flags.get("dream_confirm", {}).get(r["cell"], {}).get(str(r["step"]))
                if f is None or f["frac"] >= 0.5:
                    continue
                by.setdefault(r["seed"], []).append(r[dim])
            return {k: float(np.mean(v)) for k, v in by.items()}
        md.append("\n### Confirmatory — self-copy rates and the pre-registered contrasts on fresh windows only\n")
        md.append("| condition | copied |")
        md.append("|---|---|")
        for c in ("bare_habit", "sham_break300", "clock300", "nohabit300", "reset_reseed300"):
            rs = [r for r in conf if r["cond"] == c and r.get("since") in (32, None)]
            fl = [flags.get("dream_confirm", {}).get(r["cell"], {}).get(str(r["step"])) for r in rs]
            fl = [f for f in fl if f is not None]
            if fl:
                md.append(f"| {LABEL.get(c, c)} | {100*np.mean([f['frac'] >= 0.5 for f in fl]):.0f}% |")
        md.append("\n| hypothesis (fresh only) | contrast | dim | Δ [CI] | p | n seeds |")
        md.append("|---|---|---|---|---|---|")
        for hyp, a, b, d, alt in (("H1", "clock300", "bare_habit", "surprise", "greater"), ("H2", "clock300", "sham_break300", "surprise", "greater"),
                                  ("H3", "clock300", "reset_reseed300", "connection", "greater"), ("H4 (two-sided)", "clock300", "nohabit300", "surprise", "two-sided")):
            pr = paired(fresh_cm(a, d), fresh_cm(b, d), alt)
            if pr:
                md.append(f"| {hyp} | {a} vs {b} | {d} | {pr['mean']:+.2f} [{pr['lo']:+.2f}, {pr['hi']:+.2f}] | {pr['p_perm']:.4f} | {pr['n']} |")
    # document level on the confirmatory premises
    pth = RUNS / "document_judgments_confirm.json"
    if pth.exists():
        cdocs = json.loads(pth.read_text())
        DD = ("integration", "development", "coherence", "surprise")
        md.append(f"\n### Confirmatory premises — document level ({len(cdocs)} documents)\n")
        md.append("| condition | n | " + " | ".join(DD) + " |")
        md.append("|---|---|" + "---|" * len(DD))
        cm = {}
        for c in ("bare_habit", "sham_break300", "clock300", "nohabit300", "reset_reseed300"):
            rs = [r for r in cdocs if r["cond"] == c]
            if not rs:
                continue
            md.append(f"| {LABEL.get(c, c)} | {len(rs)} | " + " | ".join(f"{np.mean([r[d] for r in rs]):.2f}" for d in DD) + " |")
            for d in DD:
                cm[(c, d)] = {r["seed"]: r[d] for r in rs}
        md.append("\n| contrast | dim | Δ [CI] | p (perm) | n |")
        md.append("|---|---|---|---|---|")
        for a, b, lab in (("clock300", "bare_habit", "preserved vs habituation"), ("reset_reseed300", "bare_habit", "reset vs habituation"),
                          ("reset_reseed300", "clock300", "reset vs preserved")):
            for d in DD:
                if (a, d) in cm and (b, d) in cm:
                    pr = paired(cm[(a, d)], cm[(b, d)])
                    if pr:
                        star = "**" if (pr["lo"] > 0 or pr["hi"] < 0) else ""
                        md.append(f"| {lab} | {d} | {star}{pr['mean']:+.2f} [{pr['lo']:+.2f}, {pr['hi']:+.2f}]{star} | {pr['p_perm']:.3f} | {pr['n']} |")
    out = DOCS / "APPENDIX_GEN.md"
    out.write_text("\n".join(md) + "\n")
    print("\n".join(md)); print("->", out)


if __name__ == "__main__":
    main()
