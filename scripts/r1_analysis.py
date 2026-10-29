#!/usr/bin/env python3
"""R1 analysis, written and tested before the replay (docs/R1_REPLAY_CHECAGENS_PRE_REGISTRO_V0.md §8).

    python scripts/r1_analysis.py --reference docs/r1/reference_set_v1.jsonl --captures runs/r1/captures.json --out docs/R1_RESULTADOS.md

captures.json maps each check (occasion) to the list of reference-set ids it caught, after matching and adjudication, plus the
counts needed for precision:

    {"occasions": {"C1:opus:r1": {"caught": ["P1-02", ...], "findings": 23, "true_findings": 9, "docs": ["P1", ...]}, ...},
     "added_items": [{"id": "N-001", "doc": "P3", "class": "NUM", "severity": "G3", ...}]}

Items added by adjudication (real errors that no audit had) join the union set U; recall against the original reference set R is
the primary measure, recall against U is secondary. All numbers are recomputed from these two files; nothing is typed by hand.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import defaultdict
from pathlib import Path

CLASS_ORDER = ["NUM", "MIX", "SCOPE", "STATUS", "META", "METHOD", "PROP", "INTERNAL", "CITE", "TYPO"]
SEV_ORDER = ["G1", "G2", "G3"]
C1_FAMILIES = ["opus", "gpt", "kimi", "deepseek", "mistral", "qwen"]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - h) / d), min(1.0, (c + h) / d))


def chao1(caught_sets: list[set]) -> dict:
    """Chao's lower bound for the number of errors, from the capture frequencies of each item across occasions.

    S = observed items, f1 = items caught by exactly one occasion, f2 = exactly two. N = S + f1^2/(2 f2), or the bias-corrected
    S + f1(f1-1)/2 when f2 = 0. Positive dependence between occasions (same family, same reference) biases it down: a lower bound.
    """
    freq = defaultdict(int)
    for s in caught_sets:
        for i in s:
            freq[i] += 1
    S = len(freq)
    f1 = sum(1 for v in freq.values() if v == 1)
    f2 = sum(1 for v in freq.values() if v == 2)
    n_hat = S + (f1 * f1 / (2 * f2) if f2 > 0 else f1 * (f1 - 1) / 2)
    return {"S": S, "f1": f1, "f2": f2, "N_hat": n_hat, "coverage": S / n_hat if n_hat else float("nan")}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else float("nan")


def load(reference: Path, captures: Path):
    ref = [json.loads(line) for line in reference.read_text(encoding="utf-8").splitlines() if line.strip()]
    cap = json.loads(captures.read_text(encoding="utf-8"))
    return ref, cap


def recall_table(ref_items: list[dict], occasions: dict, key: str) -> list[dict]:
    """Recall of each occasion on the items of each value of `key` (class or severity), over the documents it saw."""
    rows = []
    for name, occ in occasions.items():
        seen_docs = set(occ.get("docs") or [])
        pool = [r for r in ref_items if not seen_docs or r["doc"] in seen_docs]
        caught = set(occ["caught"])
        groups = defaultdict(list)
        for r in pool:
            groups[r[key]].append(r["id"])
        groups["ALL"] = [r["id"] for r in pool]
        for g, ids in groups.items():
            k = sum(1 for i in ids if i in caught)
            lo, hi = wilson(k, len(ids))
            rows.append({"occasion": name, key: g, "k": k, "n": len(ids), "recall": k / len(ids) if ids else float("nan"),
                         "lo": lo, "hi": hi})
    return rows


def pooled(occasions: dict, prefix: str) -> set:
    out = set()
    for name, occ in occasions.items():
        if name.startswith(prefix):
            out |= set(occ["caught"])
    return out


def second_opinion(occasions: dict) -> dict:
    """Song-style comparison: two runs of Claude against one Claude run plus one run of another family (mean over families
    and over the two orderings of Claude runs), in items caught of the primary reference set."""
    def caught(fam, run):
        occ = occasions.get(f"C1:{fam}:r{run}")
        return set(occ["caught"]) if occ else None
    same = [caught("opus", 1), caught("opus", 2)]
    if None in same:
        return {}
    same_pair = len(same[0] | same[1])
    cross = []
    for fam in C1_FAMILIES[1:]:
        for run in (1, 2):
            other = caught(fam, run)
            if other is None:
                continue
            for base in same:
                cross.append(len(base | other))
    return {"same_family_pair": same_pair, "cross_family_pair_mean": sum(cross) / len(cross) if cross else float("nan"),
            "n_cross_pairs": len(cross)}


def predictions(ref_primary: list[dict], occasions: dict) -> list[dict]:
    """The five predictions of §8, evaluated mechanically."""
    def rec(ids, caught):
        return (sum(1 for i in ids if i in caught) / len(ids)) if ids else float("nan")
    meta_status = [r["id"] for r in ref_primary if r["class"] in ("META", "STATUS")]
    num = [r["id"] for r in ref_primary if r["class"] == "NUM"]
    allids = [r["id"] for r in ref_primary]
    c1 = pooled(occasions, "C1:")
    c2 = pooled(occasions, "C2:")
    c3 = set(occasions.get("C3", {}).get("caught", []))
    c3_prec = None
    if "C3" in occasions and occasions["C3"].get("findings"):
        c3_prec = occasions["C3"]["true_findings"] / occasions["C3"]["findings"]
    so = second_opinion(occasions)
    best_single = max((rec(allids, set(o["caught"])) for n, o in occasions.items() if not n.startswith("H")), default=float("nan"))
    out = [
        {"id": 1, "text": "C1 pooled recall on META+STATUS <= 0.20", "value": rec(meta_status, c1),
         "holds": rec(meta_status, c1) <= 0.20},
        {"id": 2, "text": "C2 recall on META+STATUS >= 0.50", "value": rec(meta_status, c2), "holds": rec(meta_status, c2) >= 0.50},
        {"id": 3, "text": "C3 recall on NUM >= 0.50 with precision <= 0.20", "value": [rec(num, c3), c3_prec],
         "holds": rec(num, c3) >= 0.50 and (c3_prec is not None and c3_prec <= 0.20)},
        {"id": 4, "text": "a second opinion from another family adds more than a second run of the same model",
         "value": so, "holds": bool(so) and so["cross_family_pair_mean"] > so["same_family_pair"]},
        {"id": 5, "text": "no single replayed check exceeds 0.50 recall on the whole primary set", "value": best_single,
         "holds": best_single <= 0.50},
    ]
    return out


def continuation_rule(ref_primary: list[dict], occasions: dict) -> dict:
    """R2 is justified if, in some class, a cheap (C3, C4) or records-level (C2) check beats document-only review (C1 pooled)
    by at least 0.3 in recall."""
    c1 = pooled(occasions, "C1:")
    best = {"gap": float("-inf")}
    for cls in CLASS_ORDER:
        ids = [r["id"] for r in ref_primary if r["class"] == cls]
        if not ids:
            continue
        r1 = sum(1 for i in ids if i in c1) / len(ids)
        for name in ("C2", "C3", "C4"):
            caught = pooled(occasions, name)
            if not caught and name not in occasions and not any(n.startswith(name + ":") for n in occasions):
                continue
            r = sum(1 for i in ids if i in caught) / len(ids)
            if r - r1 > best["gap"]:
                best = {"gap": r - r1, "class": cls, "check": name, "recall_check": r, "recall_c1": r1, "n": len(ids)}
    best["continue_to_R2"] = best["gap"] >= 0.3
    return best


def fmt(x, nd=2):
    if isinstance(x, float):
        return "nan" if math.isnan(x) else f"{x:.{nd}f}"
    return str(x)


def report(ref: list[dict], cap: dict) -> tuple[str, dict]:
    occasions = cap["occasions"]
    primary = [r for r in ref if r["primary"]]
    added = cap.get("added_items", [])
    union = primary + [a for a in added if a.get("primary", True)]
    by_class = recall_table(primary, occasions, "class")
    by_sev = recall_table(primary, occasions, "severity")
    replayed = [set(o["caught"]) for n, o in occasions.items() if not n.startswith("H")]
    all_occ = [set(o["caught"]) for o in occasions.values()]
    # capture-recapture over the union set: each occasion's captures among primary + added items
    union_ids = {r["id"] for r in union}
    cr = chao1([s & union_ids for s in all_occ])
    preds = predictions(primary, occasions)
    rule = continuation_rule(primary, occasions)
    pairs = {}
    names = sorted(occasions)
    for a, b in itertools.combinations(names, 2):
        pairs[f"{a} | {b}"] = jaccard(set(occasions[a]["caught"]), set(occasions[b]["caught"]))
    precision = {n: (o["true_findings"] / o["findings"] if o.get("findings") else float("nan"))
                 for n, o in occasions.items() if "findings" in o}
    result = {"n_primary": len(primary), "n_added": len(added), "by_class": by_class, "by_severity": by_sev,
              "capture_recapture": cr, "predictions": preds, "continuation": rule, "jaccard": pairs, "precision": precision,
              "union_recall_replayed": len(set().union(*replayed) & union_ids) / len(union_ids) if union_ids and replayed else
              float("nan")}
    md = ["# R1 — resultados (gerado por scripts/r1_analysis.py)\n",
          f"Conjunto primário: {len(primary)} itens; itens novos adjudicados: {len(added)}.\n",
          "## Recall por checagem (todas as classes)\n", "| checagem | k | n | recall | IC 95% |", "|---|---|---|---|---|"]
    for row in by_class:
        if row["class"] == "ALL":
            md.append(f"| {row['occasion']} | {row['k']} | {row['n']} | {fmt(row['recall'])} | {fmt(row['lo'])}–{fmt(row['hi'])} |")
    md += ["", "## Recall por classe\n", "| checagem | " + " | ".join(CLASS_ORDER) + " |",
           "|---|" + "---|" * len(CLASS_ORDER)]
    for name in sorted(occasions):
        cells = []
        for cls in CLASS_ORDER:
            row = next((r for r in by_class if r["occasion"] == name and r["class"] == cls), None)
            cells.append(f"{row['k']}/{row['n']}" if row else "–")
        md.append(f"| {name} | " + " | ".join(cells) + " |")
    md += ["", "## Captura–recaptura (Chao, limite inferior)\n",
           f"S = {cr['S']}, f1 = {cr['f1']}, f2 = {cr['f2']}, N̂ = {fmt(cr['N_hat'], 1)}, cobertura = {fmt(cr['coverage'])}.\n",
           "## Previsões\n"]
    for p in preds:
        md.append(f"{p['id']}. {p['text']}: valor {p['value']}; {'vale' if p['holds'] else 'não vale'}.")
    md += ["", "## Regra de continuação para o R2\n", json.dumps(rule, ensure_ascii=False), ""]
    return "\n".join(md) + "\n", result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference", type=Path, required=True)
    ap.add_argument("--captures", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    ref, cap = load(a.reference, a.captures)
    md, result = report(ref, cap)
    a.out.write_text(md, encoding="utf-8")
    a.out.with_suffix(".json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
