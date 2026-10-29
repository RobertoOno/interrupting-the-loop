#!/usr/bin/env python3
"""Programa 4 — Encaixe (the same idea in two slots): single read of the slot battery (pre-registered PLANO
2026-09-09). Reads runs/slot/<arm>_s<seed>/{history.jsonl,state.json} + the run logs, executes every valid proposal
once (cached by hash) to classify it, and writes docs/APPENDIX_SLOT.md + docs/slot/results.json.

Frozen before any data:
  * family detector (`is_family`): a geometric ladder toward the top — >= 3 atoms in the top half whose distances to
    the top form a roughly geometric sequence (consecutive ratios in [0.2, 0.95], coefficient of variation <= 0.35,
    first rung >= 100 positions below the top)
    — AND an atom at zero (p[0] >= 0.1). `ladder` alone (no atom-at-zero requirement) is reported too.
  * copy: the proposal's verifier signature equals the handed program's signature (identical normalized pmf);
    near-copy: the same atom set (positions with p > 1e-4) as the handed program.
  * outcomes per run: final best; seed score; climb = best - seed; per-proposal family/ladder/copy rates over all
    valid proposals and at generation 0 (the single-shot read); best family / best non-family score.
  * factorial form x slot x persistence (8 cells): main effect of each factor = the 4 paired cell contrasts that differ
    only in that factor, per RNG seed (16 paired differences): median, sign count, mean — on the final, the family rate
    and the family rate at generation 0. Pre-registered directions: H-forma code > words; H-encaixe seed > hint;
    H-persistencia transient > persistent (on the final).
  * pre-registered contrasts (per RNG seed): C1 famseed_words - famseed (do persistent words interfere with code?);
    C4 selfseed - words (is the proposer's own translation tuned once the words are gone?); R famseed - words
    (replication of 27/08); S0a / S0b: slot contrast at generation 0 pooled over persistence (codehint+codehint_g0 vs
    famseed+famseed_pin; wordseed+wordseed_pin vs words+words_g0) on the family rate at generation 0 — the tomography gate.

    python scripts/analysis_slot.py [--runs runs/slot] [--seeds 11 12 13 14] [--timeout 90]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
WORKERS = 6   # parallel program executions (operational; see --workers)
ARMS = ["nohint", "words", "words_g0", "wordseed", "wordseed_pin", "famseed", "famseed_pin", "codehint", "codehint_g0",
        "famseed_words", "selfseed", "oracle"]
FACTORIAL = {  # arm -> (form, slot, persistence)
    "words": ("words", "hint", "persistent"), "words_g0": ("words", "hint", "transient"),
    "wordseed": ("words", "seed", "transient"), "wordseed_pin": ("words", "seed", "persistent"),
    "famseed": ("code", "seed", "transient"), "famseed_pin": ("code", "seed", "persistent"),
    "codehint": ("code", "hint", "persistent"), "codehint_g0": ("code", "hint", "transient"),
}
FACTORS = [("forma", 0, "code", "words"), ("lugar", 1, "seed", "hint"), ("persistência", 2, "transient", "persistent")]
GEN0_SLOT = [("S0a", ["codehint", "codehint_g0"], ["famseed", "famseed_pin"]), ("S0b", ["wordseed", "wordseed_pin"], ["words", "words_g0"])]
HANDED = {  # arm -> the program whose content was handed (for copy / near-copy), if any
    "famseed": "docs/hint/seed_family_poor.py", "famseed_pin": "docs/hint/seed_family_poor.py", "codehint": "docs/hint/seed_family_poor.py",
    "codehint_g0": "docs/hint/seed_family_poor.py", "famseed_words": "docs/hint/seed_family_poor.py",
    "oracle": "docs/hint/seed_family_oracle.py", "selfseed": "docs/hint/seed_self_s11.py",
}
CONTRASTS = [("C1", "famseed_words", "famseed"), ("C4", "selfseed", "words"), ("R", "famseed", "words")]
RUNNER = r'''
import sys, json, resource, numpy as np
try:
    resource.setrlimit(resource.RLIMIT_AS, (8 << 30, 8 << 30))
except Exception:
    pass
src = open(sys.argv[1]).read(); L = int(sys.argv[2]); g = {}
exec(compile(src, sys.argv[1], "exec"), g)
p = np.maximum(np.asarray([float(x) for x in g["construct"](L)], dtype=float), 0.0)
p = p / p.sum(); np.save(sys.argv[3], p)
'''


def atoms_of(p: np.ndarray, thr: float = 1e-4) -> np.ndarray:
    return np.flatnonzero(p > thr)


def ladder_rungs(p: np.ndarray, thr: float = 1e-4) -> list[int]:
    """Distances to the top (descending) of the top-half atoms, distance >= 1."""
    L = len(p); top = L - 1
    hi = [int(i) for i in atoms_of(p, thr) if i >= L // 2 - 1 and top - i >= 1]   # the first dyadic rung sits at L/2
    return sorted({top - i for i in hi}, reverse=True)


def is_ladder(p: np.ndarray, min_rungs: int = 3, lo: float = 0.2, hi: float = 0.95, max_cv: float = 0.35, min_top: int = 100) -> dict:
    """Geometric ladder toward the top: >= min_rungs distances whose consecutive ratios lie in [lo, hi] with a
    coefficient of variation <= max_cv, starting at least min_top positions below the top (adjacent atoms at the top,
    distances 3/2/1, are not a ladder). Returns the flag, the rung count and the fitted ratio (median)."""
    d = ladder_rungs(p)
    if len(d) < min_rungs:
        return {"ladder": False, "rungs": len(d), "ratio": None}
    # longest run of consecutive rungs with in-range ratios
    best = []; cur = [d[0]]
    for a, b in zip(d, d[1:]):
        r = b / a
        if lo <= r <= hi:
            cur.append(b)
        else:
            if len(cur) > len(best):
                best = cur
            cur = [b]
    if len(cur) > len(best):
        best = cur
    if len(best) < min_rungs or best[0] < min_top:
        return {"ladder": False, "rungs": len(best), "ratio": None}
    ratios = [b / a for a, b in zip(best, best[1:])]
    m = statistics.mean(ratios); cv = (statistics.pstdev(ratios) / m) if m > 0 else 9.9
    return {"ladder": cv <= max_cv, "rungs": len(best), "ratio": round(statistics.median(ratios), 3), "cv": round(cv, 3)}


def is_family(p: np.ndarray) -> dict:
    lad = is_ladder(p)
    f = {**lad, "atom0": bool(p[0] >= 0.1), "mass0": float(p[0]), "n_atoms": int(len(atoms_of(p)))}
    f["family"] = bool(lad["ladder"] and f["atom0"])
    return f


def execute(src: str, L: int, cache_dir: Path, timeout: int) -> np.ndarray | None:
    h = hashlib.md5(src.encode()).hexdigest()
    npy = cache_dir / f"{h}.npy"
    if npy.exists():
        return np.load(npy)
    pyf = cache_dir / f"{h}.py"; pyf.write_text(src)
    try:
        subprocess.run([sys.executable, "-c", RUNNER, str(pyf), str(L), str(npy)], check=True, timeout=timeout, capture_output=True)
        return np.load(npy)
    except Exception:
        return None


def sig_of(p: np.ndarray) -> str:
    """The verifier's signature of a normalized pmf (frontier_exec: md5 of the rounded output)."""
    return hashlib.md5(repr([round(float(x), 6) for x in p.tolist()]).encode()).hexdigest()[:12]


def read_run(run: Path, L: int, cache: Path, timeout: int, handed: np.ndarray | None) -> dict | None:
    hist = run / "history.jsonl"
    if not hist.exists():
        return None
    rows = [json.loads(l) for l in hist.read_text().splitlines() if l.strip()]
    log = run.with_suffix(".log")
    final = None
    if log.exists():
        for l in log.read_text().splitlines():
            if l.startswith("DONE best"):
                final = float(l.split()[-1])
    seed_score = None
    if log.exists():
        for l in log.read_text().splitlines():
            if "seed score" in l:
                seed_score = float(l.split("seed score")[1].split(";")[0])
    hs = sig_of(handed) if handed is not None else None
    ha = set(atoms_of(handed).tolist()) if handed is not None else None
    props = []
    ok_rows = [r for r in rows if r.get("ok") and r.get("code")]
    # execution only (each call is its own subprocess); parallelism changes nothing in the computed features
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        pmfs = list(ex.map(lambda r: execute(r["code"], L, cache, timeout), ok_rows))
    for r, p in zip(ok_rows, pmfs):
        if p is None:
            props.append({"gen": r["gen"], "score": r.get("score"), "error": "exec"}); continue
        f = is_family(p)
        f.update({"gen": r["gen"], "score": float(r.get("score", float("nan"))),
                  "copy": bool(hs is not None and sig_of(p) == hs),
                  "near_copy": bool(ha is not None and set(atoms_of(p).tolist()) == ha)})
        props.append(f)
    ok = [q for q in props if "error" not in q]
    g0 = [q for q in ok if q["gen"] == 0]
    fam = [q for q in ok if q["family"]]; non = [q for q in ok if not q["family"]]
    def rate(xs, key):
        return (sum(1 for q in xs if q[key]) / len(xs)) if xs else None
    return {"run": run.name, "final": final, "seed_score": seed_score,
            "climb": (final - seed_score) if (final is not None and seed_score is not None) else None,
            "n_rows": len(rows), "n_valid": len(ok), "n_gen0": len(g0),
            "family_rate": rate(ok, "family"), "ladder_rate": rate(ok, "ladder"), "copy_rate": rate(ok, "copy"),
            "near_copy_rate": rate(ok, "near_copy"), "family_rate_gen0": rate(g0, "family"), "ladder_rate_gen0": rate(g0, "ladder"),
            "best_family": max((q["score"] for q in fam), default=None), "best_nonfamily": max((q["score"] for q in non), default=None),
            "final_is_family": (max(ok, key=lambda q: q["score"])["family"] if ok else None)}


def main_effect(res: dict, seeds: list[int], idx: int, hi: str, lo: str, key: str) -> dict:
    """Paired differences (hi - lo) over the 4 cell pairs that differ only in factor idx, per seed."""
    diffs = []
    for arm, lev in FACTORIAL.items():
        if lev[idx] != hi:
            continue
        partner = next(a for a, l in FACTORIAL.items() if l[idx] == lo and all(l[j] == lev[j] for j in range(3) if j != idx))
        for s in seeds:
            x = res.get(arm, {}).get(s, {}).get(key); y = res.get(partner, {}).get(s, {}).get(key)
            if x is not None and y is not None:
                diffs.append(x - y)
    if not diffs:
        return {"n": 0}
    return {"n": len(diffs), "median": statistics.median(diffs), "mean": statistics.mean(diffs),
            "pos": sum(1 for d in diffs if d > 0), "neg": sum(1 for d in diffs if d < 0)}


def pooled(res: dict, seeds: list[int], arms: list[str], key: str) -> list[float]:
    return [res[a][s][key] for a in arms for s in seeds if a in res and s in res[a] and res[a][s].get(key) is not None]


def fmt(x, nd=4):
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs/slot"); ap.add_argument("--seeds", nargs="+", type=int, default=[11, 12, 13, 14])
    ap.add_argument("--arms", nargs="+", default=ARMS); ap.add_argument("--timeout", type=int, default=90); ap.add_argument("--L", type=int, default=5000)
    ap.add_argument("--out-md", default="docs/APPENDIX_SLOT.md"); ap.add_argument("--out-json", default="docs/slot/results.json")
    ap.add_argument("--cache", default="none", help="directory for executed-pmf cache (default: <runs>/_cache)")
    ap.add_argument("--workers", type=int, default=6, help="parallel program executions (operational only)")
    a = ap.parse_args()
    global WORKERS; WORKERS = a.workers
    R = ROOT / a.runs; cache = (R / "_cache") if a.cache == "none" else Path(a.cache); cache.mkdir(parents=True, exist_ok=True)
    handed_p = {arm: execute((ROOT / f).read_text(), a.L, cache, a.timeout) for arm, f in HANDED.items()}
    res: dict[str, dict[int, dict]] = {}
    for arm in a.arms:
        for s in a.seeds:
            rr = read_run(R / f"{arm}_s{s}", a.L, cache, a.timeout, handed_p.get(arm))
            if rr:
                res.setdefault(arm, {})[s] = rr
    L = ["# Programa 4 — Encaixe: a mesma ideia em dois lugares (leitura única, gerada por `scripts/analysis_slot.py`)\n",
         "beatavg (L = 5000), Qwen3-Coder-30B-A3B-Instruct em vLLM (bf16), braço BD, 120 amostras por corrida, 4 sementes RNG. "
         "`família` = escada geométrica rumo ao topo (≥ 3 degraus, razões consecutivas em [0,2; 0,95], CV ≤ 0,35, primeiro degrau ≥ 100 posições abaixo do topo) E átomo em zero (p[0] ≥ 0,1); "
         "`escada` = só a escada; `cópia` = mesma pmf do programa entregue; `quase-cópia` = mesmo conjunto de átomos. Taxas sobre as propostas válidas.\n",
         "## 1. Final por braço e semente\n", "| braço | " + " | ".join(f"s{s}" for s in a.seeds) + " | mediana | mín–máx | escore da semente | subida mediana |", "|---|" + "---|" * (len(a.seeds) + 4)]
    med = {}
    for arm in a.arms:
        row = res.get(arm, {}); finals = [row[s]["final"] for s in a.seeds if s in row and row[s]["final"] is not None]
        m = statistics.median(finals) if finals else None; med[arm] = m
        climbs = [row[s]["climb"] for s in a.seeds if s in row and row[s]["climb"] is not None]
        seed_sc = next((row[s]["seed_score"] for s in a.seeds if s in row and row[s]["seed_score"] is not None), None)
        L.append(f"| {arm} | " + " | ".join(fmt(row[s]["final"]) if s in row else "—" for s in a.seeds) + f" | {fmt(m)} | " +
                 (f"{min(finals):.4f}–{max(finals):.4f}" if finals else "—") + f" | {fmt(seed_sc)} | {fmt(statistics.median(climbs) if climbs else None)} |")
    L += ["\n## 2. O que o modelo propôs (por proposta válida; média das sementes)\n",
          "| braço | válidas/corrida | família | escada | família na ger. 0 | cópia | quase-cópia | melhor em família | melhor fora | final em família |", "|---|---|---|---|---|---|---|---|---|---|"]
    for arm in a.arms:
        row = res.get(arm, {})
        if not row:
            continue
        def mean_of(key):
            xs = [row[s][key] for s in row if row[s].get(key) is not None]
            return (sum(xs) / len(xs)) if xs else None
        def best_of(key):
            xs = [row[s][key] for s in row if row[s].get(key) is not None]
            return max(xs) if xs else None
        nf = sum(1 for s in row if row[s]["final_is_family"]); nn = sum(1 for s in row if row[s]["final_is_family"] is not None)
        L.append(f"| {arm} | {fmt(mean_of('n_valid'), 1)} | {fmt(mean_of('family_rate'), 2)} | {fmt(mean_of('ladder_rate'), 2)} | {fmt(mean_of('family_rate_gen0'), 2)} | "
                 f"{fmt(mean_of('copy_rate'), 2)} | {fmt(mean_of('near_copy_rate'), 2)} | {fmt(best_of('best_family'))} | {fmt(best_of('best_nonfamily'))} | {nf}/{nn} |")
    L += ["\n## 3. Fatorial forma × lugar × persistência — efeitos principais (diferenças pareadas entre células que só diferem no fator; 4 pares × sementes)\n",
          "| fator (nível − nível) | final: mediana | final: sinais +/− | final: média | família: mediana | família: sinais +/− | família ger. 0: mediana | família ger. 0: sinais +/− |", "|---|---|---|---|---|---|---|---|"]
    effects = {}
    for name, idx, hi, lo in FACTORS:
        ef = main_effect(res, a.seeds, idx, hi, lo, "final"); ff = main_effect(res, a.seeds, idx, hi, lo, "family_rate"); fg = main_effect(res, a.seeds, idx, hi, lo, "family_rate_gen0")
        effects[name] = {"final": ef, "family_rate": ff, "family_rate_gen0": fg}
        def cell(e, nd=4):
            return ("—", "—") if not e.get("n") else (f"{e['median']:+.{nd}f}", f"{e['pos']}/{e['neg']} de {e['n']}")
        L.append(f"| {name} ({hi} − {lo}) | {cell(ef)[0]} | {cell(ef)[1]} | " + ("—" if not ef.get("n") else f"{ef['mean']:+.4f}") +
                 f" | {cell(ff, 2)[0]} | {cell(ff, 2)[1]} | {cell(fg, 2)[0]} | {cell(fg, 2)[1]} |")
    L += ["\n## 4. Contrastes pré-registrados (final, por semente; unidade = semente RNG)\n",
          "| contraste | " + " | ".join(f"s{s}" for s in a.seeds) + " | mediana da diferença | sinais (+/−/0) | faixas se sobrepõem? |", "|---|" + "---|" * (len(a.seeds) + 3)]
    for name, x, y in CONTRASTS:
        rx, ry = res.get(x, {}), res.get(y, {})
        diffs = {s: rx[s]["final"] - ry[s]["final"] for s in a.seeds if s in rx and s in ry and rx[s]["final"] is not None and ry[s]["final"] is not None}
        fx = [rx[s]["final"] for s in rx if rx[s]["final"] is not None]; fy = [ry[s]["final"] for s in ry if ry[s]["final"] is not None]
        overlap = (max(min(fx), min(fy)) <= min(max(fx), max(fy))) if (fx and fy) else None
        signs = f"{sum(1 for d in diffs.values() if d > 0)}/{sum(1 for d in diffs.values() if d < 0)}/{sum(1 for d in diffs.values() if d == 0)}"
        L.append(f"| {name}: {x} − {y} | " + " | ".join(f"{diffs[s]:+.4f}" if s in diffs else "—" for s in a.seeds) +
                 f" | {fmt(statistics.median(diffs.values()) if diffs else None)} | {signs} | {'sim' if overlap else ('não' if overlap is not None else '—')} |")
    L += ["\n## 5. Lugar na geração 0 (o portão da tomografia): taxa de família na geração 0, agrupando os dois níveis de persistência (prompts idênticos na geração 0)\n",
          "| contraste | grupo A (média, n corridas) | grupo B (média, n corridas) | diferença | faixas se sobrepõem? |", "|---|---|---|---|---|"]
    for name, A, B in GEN0_SLOT:
        xa = pooled(res, a.seeds, A, "family_rate_gen0"); xb = pooled(res, a.seeds, B, "family_rate_gen0")
        if xa and xb:
            ov = max(min(xa), min(xb)) <= min(max(xa), max(xb))
            L.append(f"| {name}: {'+'.join(A)} vs {'+'.join(B)} | {statistics.mean(xa):.2f} ({len(xa)}) | {statistics.mean(xb):.2f} ({len(xb)}) | {statistics.mean(xa) - statistics.mean(xb):+.2f} | {'sim' if ov else 'não'} |")
        else:
            L.append(f"| {name} | — | — | — | — |")
    L.append("\nLeitura registrada (PLANO 2026-09-09): no final, H-forma prevê o efeito principal de forma (código > palavras) dominante; H-encaixe, o de lugar "
             "(semente > dica); H-persistência, o de persistência (transitório > persistente). Dominante = maior mediana pareada com ≥ 12/16 sinais concordantes; "
             "sem dominante = misto, registrado com as taxas por proposta. Tomografia só se o lugar tiver efeito na geração 0 (S0a/S0b com faixas disjuntas e o mesmo sinal), "
             "porque patching precisa de contraste num único forward com tokens idênticos; um efeito só de persistência é propriedade do laço, não alvo de patching.\n")
    (ROOT / a.out_json).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / a.out_json.replace(".json", "_effects.json")).write_text(json.dumps(effects, indent=1) + "\n")
    (ROOT / a.out_md).write_text("\n".join(L) + "\n")
    oj = ROOT / a.out_json; oj.parent.mkdir(parents=True, exist_ok=True)
    oj.write_text(json.dumps({"arms": a.arms, "seeds": a.seeds, "runs": {arm: {str(s): v for s, v in row.items()} for arm, row in res.items()},
                              "medians": med}, indent=1) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
