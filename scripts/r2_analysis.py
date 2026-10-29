#!/usr/bin/env python3
"""R2 analysis, written and tested before the data (docs/R2_REGRAS_DE_ESCRITA_PRE_REGISTRO_V1.md §6).

    python scripts/r2_analysis.py --scores runs/r2/score --reviews runs/r2/score_reviews --writes runs/r2/write \\
        --truth runs/r2/truth --out runs/r2/R2_analysis.md

E (per paper) = facts labelled stale or wrong, scaled to 12 when fewer than 12 facts were labelled. Contrasts are paired by
record x writer, one-sided exact sign-flip tests on E(arm) - E(reference), Benjamini-Hochberg over H1-H4. Floor rule: mean E(W0)
below 1.2 means the traps did not bite, and H1-H4 are reported but not interpreted.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ERR = {"stale", "wrong"}
KEYED = {1, 2, 3, 7, 8, 9, 10, 11, 12}
PROSE = {4, 5, 6}
HYPOTHESES = [("H1", "W2", "W0"), ("H2", "W1", "W0"), ("H3", "W2", "W1"), ("H4", "W3", "W0")]
FLOOR = 1.2


def exact_signflip_less(diffs: list[float]) -> float:
    """P(sum of randomly sign-flipped |d| <= observed sum): one-sided, small sum = arm better (fewer errors). Exact: the sums of
    the first (up to) 20 pairs are built by doubling an array, and the remaining pairs are enumerated on top of it."""
    a = np.abs(np.asarray(diffs, dtype=float))
    n = len(a)
    if n == 0:
        return float("nan")
    obs = float(np.sum(diffs))
    low = min(n, 20)
    sums = np.zeros(1)
    for x in a[:low]:
        sums = np.concatenate([sums + x, sums - x])
    count = 0
    for h in range(1 << (n - low)):
        s_high = sum((-a[low + b] if (h >> b) & 1 else a[low + b]) for b in range(n - low))
        count += int(np.count_nonzero(sums + s_high <= obs + 1e-9))
    return count / float(1 << n)


def bh(ps: dict) -> dict:
    items = sorted(ps.items(), key=lambda kv: kv[1])
    m = len(items)
    q, prev = {}, 1.0
    for rank in range(m, 0, -1):
        k, p = items[rank - 1]
        prev = min(prev, p * m / rank)
        q[k] = prev
    return q


def load_scores(scores: Path) -> dict:
    out = {}
    for p in sorted(scores.glob("score_*.json")):
        s = json.loads(p.read_text())
        out[(s["arm"], s["writer"], s["record"])] = s
    return out


def E(s: dict, facts=None) -> float | None:
    labels = s.get("labels") or {}
    labels = {int(k): v["label"] for k, v in labels.items()}
    if facts is not None:
        labels = {k: v for k, v in labels.items() if k in facts}
        full = len(facts)
    else:
        full = 12
    if not labels:
        return None
    errs = sum(1 for v in labels.values() if v in ERR)
    return errs * full / len(labels)


def analyse(scores: dict, reviews: dict, writes: dict, truth: dict) -> dict:
    res = {"n_papers": len(scores)}
    by_arm = defaultdict(list)
    for (arm, w, r), s in scores.items():
        e = E(s)
        if e is not None:
            by_arm[arm].append(e)
    res["mean_E"] = {a: float(np.mean(v)) for a, v in sorted(by_arm.items())}
    res["floor"] = res["mean_E"].get("W0", 0.0) < FLOOR
    tests, ps = {}, {}
    for h, arm, ref in HYPOTHESES:
        diffs = []
        for (a, w, r), s in scores.items():
            if a != arm or (ref, w, r) not in scores:
                continue
            e1, e0 = E(s), E(scores[(ref, w, r)])
            if e1 is not None and e0 is not None:
                diffs.append(e1 - e0)
        p = exact_signflip_less(diffs) if diffs else float("nan")
        tests[h] = {"arm": arm, "ref": ref, "n_pairs": len(diffs), "mean_diff": float(np.mean(diffs)) if diffs else float("nan"),
                    "p_one_sided": p}
        ps[h] = p
    q = bh({k: v for k, v in ps.items() if not math.isnan(v)})
    for h in tests:
        tests[h]["q_bh"] = q.get(h, float("nan"))
    res["tests"] = tests
    # secondary
    group = defaultdict(lambda: defaultdict(list))
    omit = defaultdict(list)
    fact8_stale = defaultdict(list)
    for (arm, w, r), s in scores.items():
        for name, facts in (("keyed", KEYED), ("prose", PROSE)):
            e = E(s, facts)
            if e is not None:
                group[name][arm].append(e)
        labels = {int(k): v["label"] for k, v in (s.get("labels") or {}).items()}
        if labels:
            omit[arm].append(sum(1 for v in labels.values() if v == "omitted"))
        if truth[r]["stale_manifest"] and 8 in labels:
            fact8_stale[arm].append(labels[8] in ERR)
    res["by_group"] = {g: {a: float(np.mean(v)) for a, v in sorted(d.items())} for g, d in group.items()}
    res["omissions_mean"] = {a: float(np.mean(v)) for a, v in sorted(omit.items())}
    res["stale_manifest_fact8_error_rate"] = {a: float(np.mean(v)) for a, v in sorted(fact8_stale.items())}
    kfx = defaultdict(list)
    for (arm, w, r), s in scores.items():
        if arm == "W0" and s.get("labels") and "1" in {str(k) for k in s["labels"]}:
            lab = {int(k): v["label"] for k, v in s["labels"].items()}[1]
            kfx[truth[r]["k"]].append(lab in ERR)
    res["W0_fact1_error_by_k"] = {str(k): float(np.mean(v)) for k, v in sorted(kfx.items())}
    corr, new, recall_hits, recall_n = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
    for (arm, w, r), s in scores.items():
        if arm != "W3" or ("W0", w, r) not in scores:
            continue
        l3 = {int(k): v["label"] for k, v in (s.get("labels") or {}).items()}
        l0 = {int(k): v["label"] for k, v in (scores[("W0", w, r)].get("labels") or {}).items()}
        flagged = reviews.get((w, r), {})
        for f in range(1, 13):
            if f in l0 and f in l3:
                if l0[f] in ERR and l3[f] == "correct":
                    corr[w] += 1
                if l0[f] == "correct" and l3[f] in ERR:
                    new[w] += 1
            if f in l0 and l0[f] in ERR and f in flagged:
                recall_n[w] += 1
                recall_hits[w] += int(bool(flagged[f]))
    res["W3"] = {w: {"corrections": corr[w], "new_errors": new[w],
                     "review_recall_on_W0_errors": (recall_hits[w] / recall_n[w]) if recall_n[w] else None,
                     "n_W0_errors_with_review": recall_n[w]} for w in sorted(set(corr) | set(new) | set(recall_n))}
    mech = defaultdict(list)
    for (arm, w, r), s in scores.items():
        m = s.get("mechanical")
        if m:
            mech[arm].append(len(m["provisional_present"]) > 0)
    res["papers_with_leftover_provisional_main"] = {a: float(np.mean(v)) for a, v in sorted(mech.items())}
    comp = [(w.get("placeholders_left"), len(w.get("unknown_placeholders") or [])) for w in writes.values() if w.get("arm") == "W2"]
    res["W2_compliance"] = {"papers": len(comp), "mean_placeholders_kept": float(np.mean([c[0] for c in comp])) if comp else None,
                            "papers_with_unknown_keys": sum(1 for c in comp if c[1])}
    return res


def fmt(x):
    return "nan" if isinstance(x, float) and math.isnan(x) else (f"{x:.3f}" if isinstance(x, float) else str(x))


def report(res: dict) -> str:
    md = ["# R2 — resultados (gerado por scripts/r2_analysis.py)\n", f"Textos pontuados: {res['n_papers']}.\n",
          "## E médio por braço (afirmações superadas ou erradas, de 12)\n",
          "| braço | E médio |", "|---|---|"]
    md += [f"| {a} | {fmt(v)} |" for a, v in res["mean_E"].items()]
    md += ["", f"Piso (E médio do W0 < {FLOOR}): {'SIM, as hipóteses não são interpretadas' if res['floor'] else 'não'}.\n",
           "## Hipóteses (pareadas por registro × escritor; permutação exata unilateral; q de BH)\n",
           "| hipótese | contraste | pares | diferença média | p | q |", "|---|---|---|---|---|---|"]
    for h, t in res["tests"].items():
        md.append(f"| {h} | E({t['arm']}) < E({t['ref']}) | {t['n_pairs']} | {fmt(t['mean_diff'])} | {fmt(t['p_one_sided'])} | "
                  f"{fmt(t['q_bh'])} |")
    md += ["", "## Secundárias\n", "```json", json.dumps({k: v for k, v in res.items() if k not in ("tests", "mean_E", "n_papers")},
                                                         indent=1, ensure_ascii=False), "```", ""]
    return "\n".join(md)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scores", type=Path, required=True)
    ap.add_argument("--reviews", type=Path, required=True)
    ap.add_argument("--writes", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    scores = load_scores(a.scores)
    reviews = {}
    for p in a.reviews.glob("revscore_*.json"):
        r = json.loads(p.read_text())
        reviews[(r["writer"], r["record"])] = {int(k): v for k, v in r["flagged"].items()}
    writes = {}
    for p in a.writes.rglob("W*_*.json"):
        w = json.loads(p.read_text())
        if "arm" in w:
            writes[w["cell"]] = w
    truth = {p.stem: json.loads(p.read_text()) for p in a.truth.glob("R*.json")}
    res = analyse(scores, reviews, writes, truth)
    a.out.write_text(report(res), encoding="utf-8")
    a.out.with_suffix(".json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(report(res))


if __name__ == "__main__":
    main()
