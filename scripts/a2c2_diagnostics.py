#!/usr/bin/env python3
"""A2 consolidation (replication) — DESCRIPTIVE diagnostics after the pre-registered reads (no rule, no decision).
Per arm: statuses, solved, first-turn solves, shape of the solved proofs (auxiliary lemma / induction / closing tactic), submissions,
responses, output tokens, elapsed, reasoning and content characters, truncated responses, submissions extracted from the reasoning (E5).
Per arm and step: solved, first-turn solves, median output tokens. Coefficient anatomy: the measure written in the FIRST submission
against the reference measure of the world (L2/L3 for the p2 family, L1 for p1).
    python scripts/a2c2_diagnostics.py --runs base=runs/a2c2/a2c2_base_v1 p2=runs/a2c2/a2c2_p2_v1 ... --out docs/a2c2_results/diagnostics.json --md docs/a2c2_results/diagnostics.md
"""
from __future__ import annotations
import argparse, collections, json, re, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
MEASURE = re.compile(r"def\s+measure\s*\([^)]*\)\s*:\s*\w+\s*:=\s*(.+)")
CLOSERS = ("omega", "grind", "decide", "nlinarith", "linarith", "simp", "norm_num", "ring")
ANATOMY = {"p2": ("L2", "L3"), "p2t131": ("L2", "L3"), "p2n131": ("L2", "L3"), "p1": ("L1",)}


def shape(src: str) -> str:
    body = src.split("theorem evaluation_solution", 1)
    aux = len(re.findall(r"^\s*(theorem|lemma)\s+(?!evaluation_solution)", body[0], re.M)) > 0
    ind = "induction" in src
    tail = body[1] if len(body) > 1 else ""
    closer = next((c for c in CLOSERS if re.search(rf"\b{c}\b", tail)), "other")
    return ("aux_lemma" if aux else "no_aux") + (" + induction" if ind else "") + " + " + closer


def measure_of(src: str):
    m = MEASURE.search(src or ""); return m.group(1).strip() if m else None


def reference_measure(world: Path):
    for cand in (world / "Hidden" / "Reference.lean", world / "Reference.lean"):
        if cand.exists():
            return measure_of(cand.read_text())
    return None


def cell_stats(cell: Path) -> dict | None:
    res = cell / "result.json"; ev = cell / "artifacts" / "events.jsonl"
    if not res.exists():
        return None
    r = json.load(open(res))["result"]; events = [json.loads(l) for l in open(ev)] if ev.exists() else []
    responses = [e for e in events if e.get("event") == "response"]; verifs = [e for e in events if e.get("event") == "verification"]
    reasoning = content = truncated = 0
    for e in responses:
        ch = (e.get("body") or {}).get("choices") or [{}]; m = ch[0].get("message") or {}
        reasoning += len(m.get("reasoning_content") or ""); content += len(m.get("content") or ""); truncated += int(ch[0].get("finish_reason") == "length")
    first = verifs[0] if verifs else None
    sol = cell / "workspace" / "Solution.lean"
    return {"cell": cell.name, "step": cell.name.split("_")[1], "instance": cell.name.split("_")[0], "status": r.get("status"), "solved": bool(r.get("target_solved")),
            "first_turn_solved": bool(r.get("target_solved")) and len(verifs) == 1, "submissions": len(verifs), "responses": len(responses),
            "output_tokens": (r.get("tokens") or {}).get("output_tokens") or 0, "elapsed_s": r.get("elapsed_seconds") or 0, "reasoning_chars": reasoning,
            "content_chars": content, "truncated_responses": truncated, "from_reasoning": sum(1 for e in events if e.get("event") == "submission_from_reasoning"),
            "shape": shape(sol.read_text()) if (r.get("target_solved") and sol.exists()) else None,
            "first_measure": measure_of(first.get("source")) if first else None,
            "first_error": ((first.get("report") or {}).get("errors") or [""])[0][:160] if first else None,
            "first_valid": bool((first.get("report") or {}).get("solution_valid")) if first else None, "world": (json.load(open(cell / "workspace_record.json")).get("world") if (cell / "workspace_record.json").exists() else None)}


def arm_summary(cells: list[dict]) -> dict:
    med = lambda k, cs: (statistics.median(c[k] for c in cs) if cs else None)
    out = {"n": len(cells), "statuses": dict(collections.Counter(c["status"] for c in cells)), "solved": sum(c["solved"] for c in cells),
           "solved_first_turn": sum(c["first_turn_solved"] for c in cells), "solved_shapes": dict(collections.Counter(c["shape"] for c in cells if c["shape"])),
           "submissions": sum(c["submissions"] for c in cells), "responses": sum(c["responses"] for c in cells), "mean_output_tokens": round(statistics.mean(c["output_tokens"] for c in cells)) if cells else None,
           "median_output_tokens": med("output_tokens", cells), "mean_elapsed_s": round(statistics.mean(c["elapsed_s"] for c in cells)) if cells else None,
           "median_reasoning_chars": med("reasoning_chars", cells), "median_content_chars": med("content_chars", cells), "truncated_responses": sum(c["truncated_responses"] for c in cells),
           "cells_with_submission_from_reasoning": sum(1 for c in cells if c["from_reasoning"]), "by_step": {}}
    for s in sorted({c["step"] for c in cells}):
        cs = [c for c in cells if c["step"] == s]
        out["by_step"][s] = {"n": len(cs), "solved": sum(c["solved"] for c in cs), "first_turn": sum(c["first_turn_solved"] for c in cs), "median_output_tokens": med("output_tokens", cs),
                             "median_submissions": med("submissions", cs), "shapes": dict(collections.Counter(c["shape"] for c in cs if c["shape"]))}
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", nargs="+", required=True, help="arm=run_dir"); p.add_argument("--out", type=Path, required=True); p.add_argument("--md", type=Path, default=None)
    a = p.parse_args()
    out = {"arms": {}, "anatomy": {}}
    for spec in a.runs:
        arm, run = spec.split("=", 1); run = Path(run)
        cells = [c for c in (cell_stats(d) for d in sorted(run.iterdir()) if d.is_dir() and ".failed" not in d.name) if c]
        out["arms"][arm] = arm_summary(cells)
        for s in ANATOMY.get(arm, ()):
            rows = []
            for c in cells:
                if c["step"] != s:
                    continue
                world = ROOT / "worlds/ladder" / c["instance"] / s
                rows.append({"cell": c["cell"], "first_measure": c["first_measure"], "reference_measure": reference_measure(world), "first_valid": c["first_valid"], "solved": c["solved"],
                             "submissions": c["submissions"], "first_error": c["first_error"]})
            out["anatomy"][f"{arm}_{s}"] = {"n": len(rows), "first_valid": sum(1 for r in rows if r["first_valid"]), "first_measure_equals_reference": sum(1 for r in rows if r["first_measure"] and r["reference_measure"] and r["first_measure"].replace(" ", "") == r["reference_measure"].replace(" ", "")), "rows": rows}
    a.out.write_text(json.dumps(out, indent=1))
    if a.md:
        L = ["# A2 réplica — diagnósticos descritivos (sem regra)", "", "| braço | n | resolvidas | 1º turno | submissões | respostas | tokens saída (mediana) | raciocínio (chars, mediana) | truncadas | extraídas do raciocínio | formas |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for arm, s in out["arms"].items():
            L.append(f"| {arm} | {s['n']} | {s['solved']} | {s['solved_first_turn']} | {s['submissions']} | {s['responses']} | {s['median_output_tokens']} | {s['median_reasoning_chars']} | {s['truncated_responses']} | {s['cells_with_submission_from_reasoning']} | {json.dumps(s['solved_shapes'], ensure_ascii=False)} |")
        L += ["", "## Por degrau (resolvidas/n; 1º turno; tokens mediana)", ""]
        for arm, s in out["arms"].items():
            L.append(f"- **{arm}**: " + "; ".join(f"{st} {v['solved']}/{v['n']} (1º {v['first_turn']}; {v['median_output_tokens']} tok)" for st, v in s["by_step"].items()))
        L += ["", "## Anatomia da primeira submissão (medida escrita vs. referência)", ""]
        for k, v in out["anatomy"].items():
            L.append(f"- **{k}**: n {v['n']}, primeira válida {v['first_valid']}, medida igual à referência {v['first_measure_equals_reference']}")
            for r in v["rows"][:6]:
                L.append(f"  - {r['cell']}: `{r['first_measure']}` vs ref `{r['reference_measure']}` → {'válida' if r['first_valid'] else 'rejeitada'}; resolvida {r['solved']} em {r['submissions']} submissões")
        a.md.write_text("\n".join(L) + "\n")
    print(json.dumps({arm: {"n": s["n"], "solved": s["solved"], "first_turn": s["solved_first_turn"]} for arm, s in out["arms"].items()}))


if __name__ == "__main__":
    main()
