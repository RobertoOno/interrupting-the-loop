#!/usr/bin/env python3
"""Programa 2 stage-1 analysis (written before the data; pre-registered PLANO 2026-09-03).
S1: fraction of library entries with at least one valid FAMILY-EXIT transplant
(theta >= 1.10 and outside F0), D vs C2 paired by entry within each model; exact
binomial sign test on discordant entries; BH over the two models. Secondaries:
validity rate, best theta per arm, F_rec (record-family rediscovery) counts,
D-opus vs D-kimi. Writes docs/APPENDIX_P2.md.

    python scripts/analysis_p2.py --run stage1
"""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXIT_T = 1.10


def sign_test(pos: int, neg: int) -> float:
    n = pos + neg
    if n == 0:
        return 1.0
    k = max(pos, neg)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n)


def bh(ps: list[float]) -> list[float]:
    m = len(ps); order = sorted(range(m), key=lambda i: ps[i]); q = [0.0] * m; prev = 1.0
    for rank, i in reversed(list(enumerate(order, 1))):
        prev = min(prev, ps[i] * m / rank); q[i] = prev
    return q


def load(run: Path) -> dict[tuple[str, str], list[dict]]:
    """Rows per (arm, model); the family label is overridden by <arm>.reclass.json when present
    (carry-free base bound 25 -> 2001, PLANO amendment 2026-09-03 23:00)."""
    rows = defaultdict(list)
    for f in sorted(run.glob("*.jsonl")):
        rc = run / f"{f.stem}.reclass.json"; over = json.loads(rc.read_text()) if rc.exists() else {}
        for l in f.read_text().splitlines():
            r = json.loads(l); k = f"{r['entry']}|{r['attempt']}"
            if k in over and over[k]:
                r["family"] = over[k]["family"]; r["carry_free_base"] = over[k]["carry_free_base"]
            rows[(r["arm"], r["model"])].append(r)
    return rows


def source_group(entry: str) -> str:
    if "/classical/" in entry:
        n = entry.split("/")[-1]
        return "classical-digit" if any(k in n for k in ("behrend", "salem", "stanley", "cantor", "zeckendorf")) else "classical-other"
    return entry.split("/")[2]


def per_entry(rows: list[dict]) -> dict[str, dict]:
    d = {}
    for r in rows:
        e = d.setdefault(r["entry"], {"n": 0, "valid": 0, "exit": 0, "best": None, "rec": 0})
        d_ = e; d_["n"] += 1
        if r.get("ok"):
            d_["valid"] += 1
            sc = r.get("score")
            if sc is not None and (d_["best"] is None or sc > d_["best"]): d_["best"] = sc
            if sc is not None and sc >= EXIT_T and r.get("family") not in (None, "F0"): d_["exit"] += 1
            if r.get("family") == "F_rec": d_["rec"] += 1
    return d


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--run", default="stage1"); a = ap.parse_args()
    run = ROOT / "runs/p2" / a.run; rows = load(run)
    lines = [f"# Programa 2 — etapa 1 (transplantes diretos), corrida `{a.run}`\n",
             f"Saída de família = transplante válido com θ ≥ {EXIT_T} fora de F0 (classificador pré-registrado).\n",
             "| braço | modelo | entradas | tentativas | válidos | entradas c/ saída | entradas c/ F_rec | melhor θ |", "|---|---|---|---|---|---|---|---|"]
    stats = {}
    for (arm, model), rs in sorted(rows.items()):
        pe = per_entry(rs); stats[(arm, model)] = pe
        n_valid = sum(1 for r in rs if r.get("ok")); best = max((r["score"] for r in rs if r.get("ok") and r.get("score") is not None), default=None)
        lines.append(f"| {arm} | {model} | {len(pe)} | {len(rs)} | {n_valid} ({n_valid/len(rs):.0%}) | {sum(1 for e in pe.values() if e['exit'])} | "
                     f"{sum(1 for e in pe.values() if e['rec'])} | {best if best is None else f'{best:.5f}'} |")
    lines.append("\n## S1 (primário): D vs C2, pareado por entrada\n")
    lines.append("| modelo | D só | C2 só | ambos | nenhum | p (sinal exato) | q (BH) |"); lines.append("|---|---|---|---|---|---|---|")
    tests = []
    for model in ("opus", "kimi"):
        D, C = stats.get(("D", model)), stats.get(("C2", model))
        if not D or not C: continue
        ents = sorted(set(D) & set(C)); pos = sum(1 for e in ents if D[e]["exit"] and not C[e]["exit"]); neg = sum(1 for e in ents if C[e]["exit"] and not D[e]["exit"])
        both = sum(1 for e in ents if D[e]["exit"] and C[e]["exit"]); none = len(ents) - pos - neg - both
        tests.append((model, pos, neg, both, none, sign_test(pos, neg)))
    qs = bh([t[5] for t in tests]) if tests else []
    for t, q in zip(tests, qs):
        lines.append(f"| {t[0]} | {t[1]} | {t[2]} | {t[3]} | {t[4]} | {t[5]:.4f} | {q:.4f} |")
    lines.append("\n## Controle D0 (só o alvo, sem fonte): D vs D0, pareado por entrada (índice = mesma posição da biblioteca)\n")
    for model in ("opus", "kimi"):
        D, D0 = stats.get(("D", model)), stats.get(("D0", model))
        if not D or not D0: continue
        ents = sorted(set(D) & set(D0)); pos = sum(1 for e in ents if D[e]["exit"] and not D0[e]["exit"]); neg = sum(1 for e in ents if D0[e]["exit"] and not D[e]["exit"])
        bD = max((e["best"] for e in D.values() if e["best"] is not None), default=float("nan")); bD0 = max((e["best"] for e in D0.values() if e["best"] is not None), default=float("nan"))
        lines.append(f"- {model}: D só {pos}, D0 só {neg}, p = {sign_test(pos, neg):.4f}; melhor θ D {bD:.5f} vs D0 {bD0:.5f}; entradas c/ saída D {sum(1 for e in D.values() if e['exit'])} vs D0 {sum(1 for e in D0.values() if e['exit'])}")
    lines.append("\n## θ por família (melhor transplante válido por braço e família)\n")
    lines.append("| braço | modelo | F0 | F_rec (sem vai-um) | other |"); lines.append("|---|---|---|---|---|")
    for (arm, model), rs in sorted(rows.items()):
        cell = {}
        for fam in ("F0", "F_rec", "other"):
            v = [r["score"] for r in rs if r.get("ok") and r.get("family") == fam and r.get("score") is not None]
            cell[fam] = f"{max(v):.5f} (n={len(v)})" if v else "—"
        lines.append(f"| {arm} | {model} | {cell['F0']} | {cell['F_rec']} | {cell['other']} |")
    lines.append("\n## Depende da fonte? Família do transplante por grupo de origem (braço D)\n")
    for model in ("opus", "kimi"):
        rs = rows.get(("D", model))
        if not rs: continue
        tab = defaultdict(lambda: defaultdict(int))
        for r in rs:
            if r.get("ok"): tab[source_group(r["entry"])][r.get("family") or "?"] += 1
        lines.append(f"\nD-{model}:\n\n| origem | F0 | F_rec | other | saídas (θ≥{EXIT_T}) |\n|---|---|---|---|---|")
        for g, d in sorted(tab.items()):
            ex = sum(1 for r in rs if r.get("ok") and source_group(r["entry"]) == g and r.get("score", 0) >= EXIT_T and r.get("family") not in (None, "F0"))
            lines.append(f"| {g} | {d.get('F0', 0)} | {d.get('F_rec', 0)} | {d.get('other', 0)} | {ex} |")
    C1 = stats.get(("C1", "none"))
    if C1:
        lines.append(f"\nC1 (mecânico): {sum(1 for e in C1.values() if e['exit'])} entradas com saída de família de {len(C1)}; melhor θ "
                     f"{max((e['best'] for e in C1.values() if e['best'] is not None), default=float('nan')):.5f}.")
    Do, Dk = stats.get(("D", "opus")), stats.get(("D", "kimi"))
    if Do and Dk:
        ents = sorted(set(Do) & set(Dk)); pos = sum(1 for e in ents if Do[e]["exit"] and not Dk[e]["exit"]); neg = sum(1 for e in ents if Dk[e]["exit"] and not Do[e]["exit"])
        lines.append(f"\nD-opus vs D-kimi (precisa de fronteira?): opus só {pos}, kimi só {neg}, p = {sign_test(pos, neg):.4f}.")
    text = "\n".join(lines) + "\n"; (ROOT / "docs/APPENDIX_P2.md").write_text(text); print(text)


if __name__ == "__main__":
    main()
