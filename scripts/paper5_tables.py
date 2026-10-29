#!/usr/bin/env python3
"""Paper 5 — tables and the Programa 4 figure, generated from the single-read artifacts (docs/slot/results.json,
docs/slot/results_effects.json) so that every number in the paper traces to the frozen read.

    python scripts/paper5_tables.py      # writes paper5/tables/slot_arms.tex, slot_effects.tex, figures/fig_slot_arms.png
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = json.load(open(ROOT / "docs/slot/results.json"))
EFF = json.load(open(ROOT / "docs/slot/results_effects.json"))
OUT = ROOT / "paper5"
SEEDS = [str(s) for s in RES["seeds"]]
LABEL = {  # arm -> (content, slot, persistence) shown in the table
    "nohint": ("---", "---", "---"), "oracle": ("best hand code", "seed", "by merit"), "selfseed": ("own code from the words", "seed", "by merit"),
    "words": ("words", "hint", "persistent"), "words_g0": ("words", "hint", "gen.\\ 0 only"),
    "wordseed": ("words", "seed", "transient"), "wordseed_pin": ("words", "seed", "pinned"),
    "famseed": ("crude code", "seed", "transient"), "famseed_pin": ("crude code", "seed", "pinned"),
    "codehint": ("crude code", "hint", "persistent"), "codehint_g0": ("crude code", "hint", "gen.\\ 0 only"),
    "famseed_words": ("crude code + words", "seed + hint", "persistent"),
}
ORDER = ["nohint", "words", "words_g0", "wordseed", "wordseed_pin", "famseed", "famseed_pin", "codehint", "codehint_g0", "famseed_words", "selfseed", "oracle"]


def finals(arm):
    return [RES["runs"][arm][s]["final"] for s in SEEDS if s in RES["runs"].get(arm, {})]


def mean_key(arm, key):
    xs = [RES["runs"][arm][s][key] for s in SEEDS if s in RES["runs"].get(arm, {}) and RES["runs"][arm][s].get(key) is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def arms_table() -> str:
    L = [r"\begin{tabular}{llll rrrr}", r"\toprule",
         r"arm & content & slot & persistence & median & range & family & family g0 \\", r"\midrule"]
    for arm in ORDER:
        f = finals(arm); c, s, p = LABEL[arm]; name = arm.replace("_", "\\_")
        L.append(f"{name} & {c} & {s} & {p} & {statistics.median(f):.4f} & {min(f):.4f}--{max(f):.4f} & "
                 f"{mean_key(arm, 'family_rate'):.2f} & {mean_key(arm, 'family_rate_gen0'):.2f}" + " \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


def effects_table() -> str:
    names = {"forma": "form (code $-$ words)", "lugar": "slot (seed $-$ hint)", "persistência": "persistence (transient $-$ persistent)"}
    L = [r"\begin{tabular}{l rr rr rr}", r"\toprule",
         r"factor (level $-$ level) & final & $+/-/0$ & family & $+/-/0$ & family g0 & $+/-/0$ \\", r"\midrule"]
    for k, name in names.items():
        e = EFF[k]
        def cell(o, nd):
            x = e[o]; ties = x["n"] - x["pos"] - x["neg"]
            return f"{x['median']:+.{nd}f} & {x['pos']}/{x['neg']}/{ties}"
        L.append(f"{name} & {cell('final', 4)} & {cell('family_rate', 2)} & {cell('family_rate_gen0', 2)} \\\\")
    L += [r"\midrule"]
    contrasts = [("C1: famseed\\_words $-$ famseed", "famseed_words", "famseed"),
                 ("C4: selfseed $-$ words", "selfseed", "words"),
                 ("R: famseed $-$ words (replication)", "famseed", "words")]
    for name, x, y in contrasts:
        d = [RES["runs"][x][s]["final"] - RES["runs"][y][s]["final"] for s in SEEDS]
        fx, fy = finals(x), finals(y)
        disjoint = max(fx) < min(fy) or max(fy) < min(fx)
        L.append(f"{name} & {statistics.median(d):+.4f} & {sum(1 for v in d if v > 0)}/{sum(1 for v in d if v < 0)}/{sum(1 for v in d if v == 0)} & "
                 f"\\multicolumn{{4}}{{l}}{{ranges {'disjoint' if disjoint else 'overlap'}}} \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


def figure() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    xs = list(range(len(ORDER)))
    for i, arm in enumerate(ORDER):
        f = finals(arm)
        color = "#7a7a7a" if arm in ("nohint",) else ("#c0392b" if LABEL[arm][0].startswith("words") else ("#1f5fa8" if "code" in LABEL[arm][0] and "words" not in LABEL[arm][0] else "#8e44ad"))
        ax.scatter([i] * len(f), f, s=22, color=color, alpha=0.75, zorder=3)
        ax.plot([i - 0.28, i + 0.28], [statistics.median(f)] * 2, color=color, lw=2.2, zorder=4)
    ax.axhline(statistics.median(finals("nohint")), color="#7a7a7a", ls=":", lw=1)
    ax.axhline(0.3816, color="#333", ls="--", lw=0.8)
    ax.text(len(ORDER) - 0.5, 0.3822, "August 600-sample unaided final, MLX 8-bit (0.3816)", ha="right", va="bottom", fontsize=7.5, color="#333")
    ax.set_xticks(xs); ax.set_xticklabels([a.replace("_", "\n") for a in ORDER], fontsize=8)
    ax.set_ylabel("final best after 120 samples"); ax.set_ylim(0.325, 0.386)
    ax.set_title("The same family handed as words (red) or code (blue), by slot and persistence", fontsize=9)
    ax.grid(axis="y", lw=0.4, alpha=0.5)
    fig.tight_layout(); (OUT / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "figures/fig_slot_arms.png", dpi=200)


def main() -> None:
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "tables/slot_arms.tex").write_text(arms_table())
    (OUT / "tables/slot_effects.tex").write_text(effects_table())
    figure()
    print("wrote paper5/tables/slot_arms.tex, slot_effects.tex, figures/fig_slot_arms.png")


if __name__ == "__main__":
    main()
