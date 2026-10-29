#!/usr/bin/env python3
"""Programa 2 — stage-2 AUDIT (2026-09-04, closure; post-hoc, explicit). The single-read script
(analysis_p2_stage2.py, unchanged) classified only best.py: when the seed stayed best there is
no best.py (family None), and best.py holds the candidate WITHOUT the elite prelude it was
verified with (construct_v0.., helpers). This audit:
  1. takes the seed program of every run (stage-1 seeds; harness default for arm A);
  2. replays the island dynamics from history.jsonl (elites = top-3 by score at the start of a
     generation, renamed construct_v{i}; every valid candidate appended; island cut to 12;
     migration of the best every 3rd generation) to rebuild the exact prelude of the best
     candidate, materializes prelude + candidate, and VERIFIES that it reproduces the score;
  3. separates (a) family inherited from the seed, (b) new exit produced by the loop, (c) family
     of the run's final result (= the seed when nothing improved);
  4. aggregates by seed (5 per arm) and by RNG (3 per seed) and tests D vs D0 with the seed as
     the unit, keeping the run-level tests with a dependence caveat.
Pure functions (replay_islands, materialize, exit_flags, aggregate, observed_seed_score) are
unit-tested in tests/test_p2_audit.py.
Amendment 2 (2026-09-04, closure): the seed score is the one OBSERVED in each run (state.json entry
with hash == "seed"; else a re-execution only when the seed program is deterministic, cross-checked
against the 4-decimal log line; else the log value, flagged uncertain) and drives both `improved` and
the elite replay; `family_changed` never counts an unknown (None) family as a change. Writes
docs/APPENDIX_P2_STAGE2_AUDIT_v2.md and runs/p2/stage2_audit_v2.json, with a diff against
runs/p2/stage2_audit.json (amendment 1) when present. Operational amendment: the stable scientific fields
go to the TRACKED docs/p2/stage2_audit_v2_results.json (sorted keys, reproducible hash); the volatile
diagnostic scores of time-budgeted programs go to runs/p2/stage2_audit_v2_diagnostics.json (ignored).
Requires the `analysis` extra (scipy): pip install -e ".[analysis]".

    PYTHONPATH=src python scripts/analysis_p2_stage2_audit.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
R = ROOT / "runs/p2/stage2"; SEEDS = ROOT / "runs/p2/stage1_seeds"
EXIT_T, REF, ENTRY = 1.10, 1.1479, "construct"
N_ELITES, KEEP, N_ISLANDS = 3, 12, 2


# ---------------------------------------------------------------- pure functions (tested)
def replay_islands(rows: list[dict], seed_code: str, seed_score: float, upto_gen: int,
                   n_islands: int = N_ISLANDS, n_elites: int = N_ELITES, keep: int = KEEP) -> list[list[dict]]:
    """Island states at the START of generation `upto_gen`, replaying frontier_search's rules
    (novelty=none: every valid candidate appended; sort desc + cut to `keep`; migration at g % 3 == 2)."""
    islands = [[{"code": seed_code, "score": seed_score, "hash": "seed"}] for _ in range(n_islands)]
    by_gen: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by_gen[r["gen"]].append(r)
    for g in range(upto_gen):
        for r in sorted(by_gen.get(g, []), key=lambda r: (r["island"], r["sample"])):
            if r.get("ok") and r.get("score") is not None and r.get("code"):
                islands[r["island"]].append({"code": r["code"], "score": r["score"], "hash": r.get("hash", "")})
        for isl in islands:
            isl.sort(key=lambda e: e["score"], reverse=True)
            del isl[(max(n_elites * 4, 8) if keep is None else keep):]
        if n_islands > 1 and g % 3 == 2:
            bests = [max(isl, key=lambda e: e["score"]) for isl in islands]
            for k in range(n_islands):
                islands[(k + 1) % n_islands].append(dict(bests[k]))
    return islands


def prelude_for(islands: list[list[dict]], island: int, entry: str = ENTRY, n_elites: int = N_ELITES) -> str:
    shown = sorted(islands[island], key=lambda e: e["score"], reverse=True)[:n_elites]
    return "\n\n".join(e["code"].replace("def " + entry, "def " + entry + "_v" + str(i)) for i, e in enumerate(shown))


def best_row(rows: list[dict], best: float) -> dict | None:
    """The candidate that wrote best.py last: the FIRST valid row reaching the run's best score."""
    for r in sorted(rows, key=lambda r: (r["gen"], r["island"], r["sample"])):
        if r.get("ok") and r.get("score") is not None and abs(r["score"] - best) < 1e-9:
            return r
    return None


def materialize(rows: list[dict], seed_code: str, seed_score: float, best: float, verify, entry: str = ENTRY) -> dict:
    """Rebuild the executable final program. `verify(code) -> score or None`. Returns a dict with
    status in {'seed', 'self-contained', 'prelude', 'not-materializable'} and the program text."""
    if best <= seed_score + 1e-12:
        return {"status": "seed", "program": seed_code, "gen": None, "island": None}
    r = best_row(rows, best)
    if r is None:
        return {"status": "not-materializable", "program": None, "gen": None, "island": None, "why": "no history row at the best score"}
    code = r["code"]; g, k = r["gen"], r["island"]
    s = verify(code)
    if s is not None and abs(s - best) < 1e-9:
        return {"status": "self-contained", "program": code, "gen": g, "island": k}
    full = prelude_for(replay_islands(rows, seed_code, seed_score, g), k, entry) + "\n\n" + code
    s2 = verify(full)
    if s2 is not None and abs(s2 - best) < 1e-9:
        return {"status": "prelude", "program": full, "gen": g, "island": k}
    return {"status": "not-materializable", "program": None, "gen": g, "island": k,
            "why": f"alone -> {s}; with replayed prelude -> {s2}; expected {best}"}


NONDET = ("random", "time.time", "perf_counter", "default_rng", "np.random", "urandom", "shuffle")


def is_deterministic(code: str) -> bool:
    """Heuristic: no RNG and no wall-clock budget in the program text."""
    return not any(w in code for w in NONDET)


def observed_seed_score(islands: list[list[dict]], log_text: str, seed_code: str, verify=None) -> dict:
    """The seed score OBSERVED in this run. Priority: (1) a state.json entry with hash == "seed" (exact);
    (2) if the seed program is deterministic and `verify` is given, a re-execution cross-checked against
    the 4-decimal log line (|diff| < 5e-5); (3) the log value alone, flagged uncertain (4 decimals)."""
    for isl in islands:
        for e in isl:
            if e.get("hash") == "seed" and e.get("score") is not None:
                return {"score": float(e["score"]), "source": "state", "uncertain": False}
    m = re.search(r"seed score ([0-9.]+)", log_text or "")
    logv = float(m.group(1)) if m else None
    if is_deterministic(seed_code) and verify is not None:
        s = verify(seed_code)
        if s is not None and (logv is None or abs(s - logv) < 5e-5):
            return {"score": float(s), "source": "reexec-deterministic", "uncertain": False, "log": logv}
    if logv is not None:
        return {"score": logv, "source": "log-4dp", "uncertain": True}
    return {"score": None, "source": "none", "uncertain": True}


def is_improved(best: float, seed: dict) -> bool:
    """Strictly better than the observed seed; with a 4-decimal seed the margin is half a unit of the last place."""
    if seed.get("score") is None:
        return False
    return best > seed["score"] + (5e-5 if seed.get("uncertain") else 1e-9)


STABLE_FIELDS = ("run", "arm", "k", "rng", "seed_theta", "seed_source", "seed_uncertain", "seed_family", "best", "improved",
                 "n_valid", "n", "materialization", "best_gen", "best_island", "final_family", "has_best_py",
                 "seed_exit", "final_exit", "new_exit", "inherited_exit", "family_changed")
VOLATILE_FIELDS = ("why",)   # diagnostic re-execution scores of time-budgeted programs: vary between audit runs


def split_audit_records(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """(stable, diagnostics): the stable list carries only STABLE_FIELDS, ordered by run name, keys sorted, so
    that its serialization is reproducible; the diagnostics list carries run + VOLATILE_FIELDS."""
    stable = [{k: r.get(k) for k in sorted(STABLE_FIELDS)} for r in sorted(rows, key=lambda r: r["run"])]
    diag = [{"run": r["run"], **{k: r.get(k) for k in VOLATILE_FIELDS}} for r in sorted(rows, key=lambda r: r["run"]) if any(r.get(k) for k in VOLATILE_FIELDS)]
    return stable, diag


def is_exit(family: str | None, theta: float | None) -> bool:
    return bool(family is not None and family != "F0" and theta is not None and theta >= EXIT_T)


def exit_flags(seed_family: str | None, seed_theta: float, final_family: str | None, final_theta: float, improved: bool) -> dict:
    """(a) inherited: the seed already qualifies; (b) new: the loop produced a qualifying final from a
    seed that did not qualify; (c) final: the run's final qualifies. family_changed: coarse label differs."""
    se, fe = is_exit(seed_family, seed_theta), is_exit(final_family, final_theta)
    return {"seed_exit": se, "final_exit": fe, "new_exit": bool(improved and fe and not se),
            "inherited_exit": bool(fe and se),
            "family_changed": bool(improved and final_family is not None and seed_family is not None and final_family != seed_family)}


def aggregate(runs: list[dict]) -> dict[str, dict[str, dict]]:
    """arm -> seed key -> stats over RNGs (n, mean/sd/min/max of best, improved count, new/final exits)."""
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in runs:
        groups[(r["arm"], str(r.get("k")))].append(r)
    for (arm, k), rs in groups.items():
        b = [r["best"] for r in rs]
        out[arm][k] = {"n": len(rs), "mean": statistics.fmean(b), "sd": statistics.pstdev(b) if len(b) > 1 else 0.0,
                       "min": min(b), "max": max(b), "seed": rs[0].get("seed_theta"), "improved": sum(bool(r.get("improved")) for r in rs),
                       "new_exit": sum(bool(r.get("new_exit")) for r in rs), "final_exit": sum(bool(r.get("final_exit")) for r in rs)}
    return out


# ---------------------------------------------------------------- statistics
def mannwhitney(x, y):
    try:
        from scipy.stats import mannwhitneyu
        return float(mannwhitneyu(x, y, alternative="two-sided").pvalue)
    except Exception:
        return float("nan")


def perm_mean_diff(x, y, n=20000, seed=0):
    import random
    rng = random.Random(seed); pool = list(x) + list(y); obs = abs(statistics.fmean(x) - statistics.fmean(y)); c = 0
    for _ in range(n):
        rng.shuffle(pool); a, b = pool[:len(x)], pool[len(x):]
        if abs(statistics.fmean(a) - statistics.fmean(b)) >= obs - 1e-15: c += 1
    return (c + 1) / (n + 1)


def fisher(a1, a0, b1, b0):
    from math import comb
    n = a1 + a0 + b1 + b0; r1 = a1 + a0; c1 = a1 + b1
    def p(k): return comb(r1, k) * comb(n - r1, c1 - k) / comb(n, c1)
    obs = p(a1); return min(1.0, sum(p(k) for k in range(max(0, c1 - (n - r1)), min(r1, c1) + 1) if p(k) <= obs + 1e-12))


# ---------------------------------------------------------------- real data
def parse_name(name: str):
    if name.startswith("A_s"):
        return "A", None, int(name[3:])
    m = re.match(r"(.+)_k(\d+)_s(\d+)$", name)
    return m.group(1), int(m.group(2)), int(m.group(3))


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--timeout", type=int, default=25); a = ap.parse_args()
    from creative_machine.frontier_exec import run_candidate
    from transfer_correspond import get_object
    from family_sumdiff3 import features
    spec = importlib.util.spec_from_file_location("fs", ROOT / "scripts/frontier_search.py")
    fs = importlib.util.module_from_spec(spec); spec.loader.exec_module(fs)
    P = fs.PROBLEMS["sumdiff3"]

    def verify(code: str):
        res = run_candidate(code, P["module"], P["entry"], P["args"], timeout_s=a.timeout)
        return float(res["score"]) if res.get("ok") else None

    def classify(code: str):
        nums = get_object(code, ENTRY, [], a.timeout)
        if not nums:
            return None
        U = sorted({int(round(x)) for x in nums})
        if len(U) < 2 or len(U) > 4000:
            return None
        f = features(U)
        return "F0" if f["frac_pow2_sums_le3"] >= 0.8 else ("F_rec" if (f["carry_free_base"] and f["n"] >= 50) else "other")

    seed_family_cache: dict[str, tuple[str | None, float | None]] = {}
    runs = []
    for d in sorted(p for p in R.iterdir() if p.is_dir() and (p / "state.json").exists() and not p.name.startswith("smoke")):
        arm, k, s = parse_name(d.name)
        seed_file = (SEEDS / arm / f"{k}.py") if k is not None else None
        seed_code = seed_file.read_text() if seed_file else P["seed_program"]
        st = json.loads((d / "state.json").read_text()); rows = [json.loads(l) for l in (d / "history.jsonl").read_text().splitlines()]
        key = str(seed_file) if seed_file else "A-default"
        if key not in seed_family_cache:
            seed_family_cache[key] = classify(seed_code)   # family label: coarse, cached per seed program
        seed_fam = seed_family_cache[key]
        log_text = d.with_suffix(".log").read_text() if d.with_suffix(".log").exists() else ""
        seed_obs = observed_seed_score(st["islands"], log_text, seed_code, verify)   # score: per run (amendment 2)
        seed_theta = seed_obs["score"]
        best = float(st["best"]); improved = is_improved(best, seed_obs)
        mat = materialize(rows, seed_code, seed_theta if seed_theta is not None else 0.0, best, verify) if improved else {"status": "seed", "program": seed_code, "gen": None, "island": None}
        final_fam = seed_fam if mat["status"] == "seed" else (classify(mat["program"]) if mat["program"] else None)
        flags = exit_flags(seed_fam, seed_theta, final_fam, best, improved)
        n_valid = sum(1 for r in rows if r.get("ok"))
        runs.append({"run": d.name, "arm": arm, "k": k, "rng": s, "seed_theta": seed_theta, "seed_source": seed_obs["source"], "seed_uncertain": seed_obs["uncertain"], "seed_family": seed_fam, "best": best,
                     "improved": improved, "n_valid": n_valid, "n": len(rows), "materialization": mat["status"], "why": mat.get("why"),
                     "best_gen": mat["gen"], "best_island": mat["island"], "final_family": final_fam, "has_best_py": (d / "best.py").exists(), **flags})
        print(f"{d.name:22s} seed {seed_theta if seed_theta is None else round(seed_theta,5)} [{seed_obs['source']}] {seed_fam} -> best {best:.5f} {mat['status']:18s} final {final_fam} new_exit={flags['new_exit']}", flush=True)
    (ROOT / "runs/p2/stage2_audit_v2.json").write_text(json.dumps(runs, indent=1))   # full record (ignored by git)
    stable, diag = split_audit_records(runs)
    (ROOT / "docs/p2").mkdir(exist_ok=True)
    (ROOT / "docs/p2/stage2_audit_v2_results.json").write_text(json.dumps(stable, indent=1, sort_keys=True) + "\n")   # tracked, reproducible
    (ROOT / "runs/p2/stage2_audit_v2_diagnostics.json").write_text(json.dumps(diag, indent=1, sort_keys=True) + "\n")  # volatile
    v1p = ROOT / "runs/p2/stage2_audit.json"; v1 = {r["run"]: r for r in json.load(v1p.open())} if v1p.exists() else {}

    by_arm: dict[str, list[dict]] = defaultdict(list)
    for r in runs: by_arm[r["arm"]].append(r)
    agg = aggregate(runs)
    L = ["# Programa 2 — etapa 2: AUDITORIA do endpoint de família — EMENDA 2 (2026-09-04, tarde)\n",
         "Este documento **não substitui** `docs/APPENDIX_P2_STAGE2.md` (leitura única, preservada) nem a emenda 1",
         "(`docs/APPENDIX_P2_STAGE2_AUDIT.md`, preservada). Diferenças da emenda 2: (i) o escore da semente é o **observado em cada",
         "corrida** (entrada `hash == \"seed\"` do `state.json`; se cortada da ilha, reexecução só para programas determinísticos, conferida",
         "com a linha de 4 casas do log; senão o valor do log, marcado incerto) e é ele que define `melhorou` e o replay dos elites;",
         "(ii) família desconhecida (`None`) nunca conta como mudança de família. A seção final lista exatamente o que mudou.\n",
         "## 1. Endpoint pré-registrado e o que o script de leitura mediu\n",
         "- **Pré-registro (PLANO 03/09)**: S2 = fração de corridas cujo *final* tem saída de família (final válido, θ ≥ 1,10, fora de F0).",
         "- **O script da leitura única** (`analysis_p2_stage2.py`) classificou apenas `best.py`. `best.py` só existe quando o laço",
         "  superou a semente (44 de 108 corridas); quando a semente continuou sendo o melhor, a família ficou `None` e a corrida",
         "  contou como 'sem saída'. Além disso, `best.py` guarda o candidato sem o prelúdio (`construct_v0..2`, auxiliares) com",
         "  que ele foi verificado, então parte dos arquivos não é um programa autônomo.",
         "- **Interpretação corrigida da frase 'nenhuma saída de família em D/D0'**: ela vale para *saídas novas produzidas pelo laço*;",
         "  não é verdade que nenhum final esteja fora de F0 — as sementes do Opus (F_rec/other) já estão fora de F0 e, quando o",
         "  laço não melhora, o final **é** a semente, com a família dela.\n",
         "## 2. Três quantidades separadas\n",
         "(a) família **herdada** da semente; (b) saída **nova** produzida pelo laço (final produzido pelo laço, θ ≥ 1,10, fora de F0,",
         "partindo de uma semente que não qualificava); (c) família do **final** da corrida (= semente quando nada melhorou).",
         "`materialização`: `seed` (final = semente), `self-contained` (best.py reproduz o escore sozinho), `prelude` (reproduz",
         "só com o prelúdio reconstruído por replay), `not-materializable` (não reproduz: marcado, não classificado).\n",
         "| braço | corridas | melhoraram | finais = semente | materialização: self / prelude / não | sementes fora de F0 (a) | finais fora de F0 (c) | saídas novas (b) | famílias mudaram |",
         "|---|---|---|---|---|---|---|---|---|"]
    for arm, rs in sorted(by_arm.items()):
        c = lambda st: sum(1 for r in rs if r["materialization"] == st)
        L.append(f"| {arm} | {len(rs)} | {sum(r['improved'] for r in rs)} | {c('seed')} | {c('self-contained')} / {c('prelude')} / {c('not-materializable')} | "
                 f"{sum(r['seed_exit'] for r in rs)} | {sum(r['final_exit'] for r in rs)} | {sum(r['new_exit'] for r in rs)} | {sum(r['family_changed'] for r in rs)} |")
    L.append("\n## 3. Unidade de inferência: 5 sementes × 3 RNG por braço\n")
    L.append("| braço | semente k | θ semente | melhor: média ± dp (mín–máx) sobre 3 RNG | melhoraram | finais fora de F0 | saídas novas |"); L.append("|---|---|---|---|---|---|---|")
    for arm in sorted(agg):
        for k in sorted(agg[arm], key=lambda x: (x == "None", x)):
            g = agg[arm][k]
            seed_txt = "—" if g["seed"] is None else "%.4f" % g["seed"]
            L.append("| %s | %s | %s | %.4f ± %.4f (%.4f–%.4f) | %d/%d | %d/%d | %d/%d |" % (arm, k, seed_txt, g["mean"], g["sd"], g["min"], g["max"], g["improved"], g["n"], g["final_exit"], g["n"], g["new_exit"], g["n"]))
    L.append("\n### D vs D0 com a semente como unidade (5 vs 5 médias por semente)\n")
    L.append("| modelo | D (média das 5 sementes) | D0 | p Mann–Whitney (5×5) | p permutação (médias) | ressalva |"); L.append("|---|---|---|---|---|---|")
    for model in ("opus", "kimi"):
        D, D0 = agg.get(f"D_{model}"), agg.get(f"D0_{model}")
        if not D or not D0: continue
        x = [D[k]["mean"] for k in D]; y = [D0[k]["mean"] for k in D0]
        L.append(f"| {model} | {statistics.fmean(x):.4f} | {statistics.fmean(y):.4f} | {mannwhitney(x, y):.3f} | {perm_mean_diff(x, y):.3f} | as sementes diferem entre braços (top-5 de cada); pareamento por posto k é nominal |")
    L.append("\n*Ressalva à leitura original*: o Mann–Whitney sobre 15 corridas por braço trata 3 RNG da mesma semente como independentes;")
    L.append("as médias por semente acima são a unidade correta (n = 5 por braço); o sentido e a significância de cada contraste estão na tabela")
    L.append("(direção = qual braço tem a média maior; um p pequeno com D > D0 reflete sementes melhores no D, não transferência, quando não há saídas novas).\n")
    L.append("## 4. Saídas de família por corrida: herdada, nova, final (Fisher exato sobre corridas, com a mesma ressalva de dependência)\n")
    L.append("| contraste | saídas novas (b) | p | finais fora de F0 (c) | p |"); L.append("|---|---|---|---|---|")
    for a_, b_ in (("D_opus", "C2_opus"), ("D_opus", "D0_opus"), ("D_opus", "C1_none"), ("D_kimi", "C2_kimi"), ("D_kimi", "D0_kimi")):
        if a_ not in by_arm or b_ not in by_arm: continue
        xa, xb = by_arm[a_], by_arm[b_]
        n1, n0 = sum(r["new_exit"] for r in xa), sum(not r["new_exit"] for r in xa); m1, m0 = sum(r["new_exit"] for r in xb), sum(not r["new_exit"] for r in xb)
        f1, f0 = sum(r["final_exit"] for r in xa), sum(not r["final_exit"] for r in xa); g1, g0 = sum(r["final_exit"] for r in xb), sum(not r["final_exit"] for r in xb)
        L.append(f"| {a_} vs {b_} | {n1}/{len(xa)} vs {m1}/{len(xb)} | {fisher(n1, n0, m1, m0):.3f} | {f1}/{len(xa)} vs {g1}/{len(xb)} | {fisher(f1, f0, g1, g0):.3f} |")
    L.append("\n## 5. Limitações de materialização\n")
    nm = [r for r in runs if r["materialization"] == "not-materializable"]
    L.append(f"{len(nm)} corrida(s) com final não materializável (marcadas, não classificadas): " + ("; ".join(f"{r['run']} ({r['why']})" for r in nm) if nm else "nenhuma") + ".")
    L.append("O replay reproduz as regras do harness no commit 94fc0ea (`frontier_search.py`): elites = top-3 por escore no início da geração,")
    L.append("renomeados `construct_v{i}`; todo candidato válido entra na ilha (novelty=none); corte em 12; migração do melhor a cada 3 gerações.")
    L.append("A reprodução do escore (tolerância 1e-9) é a prova de que o programa materializado é o que foi verificado na corrida.\n")
    L.append("## 6. Corridas\n"); L.append("| corrida | θ semente | fam. semente | melhor | melhorou | válidos | materialização | fam. final | herdada | nova | final fora de F0 |"); L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(runs, key=lambda r: (r["arm"], r["k"] if r["k"] is not None else 0, r["rng"])):
        L.append("| %s | %s | %s | %.5f | %s | %d/%d | %s | %s | %s | %s | %s |" % (r["run"], "—" if r["seed_theta"] is None else f"{r['seed_theta']:.4f}", r["seed_family"], r["best"],
                 "sim" if r["improved"] else "não", r["n_valid"], r["n"], r["materialization"], r["final_family"], "sim" if r["inherited_exit"] else "não", "sim" if r["new_exit"] else "não", "sim" if r["final_exit"] else "não"))
    # seed-score provenance and the diff against amendment 1
    from collections import Counter
    src = Counter(r["seed_source"] for r in runs)
    L.append("\n## 7. Proveniência do escore da semente por corrida\n")
    L.append("| fonte | corridas |"); L.append("|---|---|")
    for k_, v_ in src.most_common(): L.append(f"| {k_} | {v_} |")
    unc = [r["run"] for r in runs if r["seed_uncertain"]]
    L.append(f"\nCorridas com escore de semente incerto (só o log, 4 casas): {len(unc)}" + (": " + ", ".join(unc) if unc else "") + ".")
    L.append("\n## 8. O que mudou em relação à emenda 1 (`runs/p2/stage2_audit.json`)\n")
    if v1:
        ch = []
        for r in runs:
            o = v1.get(r["run"])
            if not o: continue
            for f_ in ("seed_theta", "improved", "materialization", "final_family", "new_exit", "inherited_exit", "final_exit", "family_changed"):
                a_, b_ = o.get(f_), r.get(f_)
                if isinstance(a_, float) and isinstance(b_, float):
                    if abs(a_ - b_) > 1e-9: ch.append((r["run"], f_, a_, b_))
                elif a_ != b_: ch.append((r["run"], f_, a_, b_))
        L.append(f"{len(ch)} campo(s) alterado(s) em {len(set(c[0] for c in ch))} corrida(s).\n")
        L.append("| corrida | campo | emenda 1 | emenda 2 |"); L.append("|---|---|---|---|")
        for c in ch: L.append(f"| {c[0]} | {c[1]} | {c[2]} | {c[3]} |")
        def tot(rs, f_): return sum(bool(x.get(f_)) for x in rs)
        L.append("\n| total | emenda 1 | emenda 2 |"); L.append("|---|---|---|")
        for f_ in ("improved", "inherited_exit", "new_exit", "final_exit", "family_changed"):
            L.append(f"| {f_} | {tot(v1.values(), f_)} | {tot(runs, f_)} |")
        for st_ in ("seed", "self-contained", "prelude", "not-materializable"):
            L.append(f"| materialização {st_} | {sum(1 for x in v1.values() if x.get('materialization') == st_)} | {sum(1 for x in runs if x.get('materialization') == st_)} |")
    else:
        L.append("(emenda 1 não encontrada)")
    (ROOT / "docs/APPENDIX_P2_STAGE2_AUDIT_v2.md").write_text("\n".join(L) + "\n"); print("\n".join(L[:40]))


if __name__ == "__main__":
    main()
