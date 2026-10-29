#!/usr/bin/env python3
"""Degrau 2 — single read of the open-model contrast (written before the data; PLANO 2026-09-08).
Recipients: solved by world x holdout x condition x budget x thinking; a REGIME is a (world, budget, thinking) where
the oracle-bridge recipient solves both holdouts and the no-bridge recipient solves neither. Proposers: valid bridge
by world x arm x budget x thinking. Writes docs/APPENDIX_P3_OPEN.md.

    python scripts/analysis_p3_open.py
"""
import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "runs/p3/open_contrast_v1"


def main() -> None:
    plan = json.loads((OUT / "plan.json").read_text())
    rows = {}
    for c in plan["cells"]:
        p = OUT / c["cell_id"] / "result.json"
        rows[c["cell_id"]] = json.loads(p.read_text()) if p.exists() else None
    L = [f"# Degrau 2 — contraste no modelo aberto ({plan['model']}), leitura única\n",
         "Mesmos mundos e verificadores do diagnóstico com o Opus; protocolo de blocos cercados (sem ferramenta); geração em vLLM, verificação local.\n",
         "## Receptores: resolvido (✓/✗; — não rodou / falha de infra)\n"]
    rec = defaultdict(dict); prop = defaultdict(dict)
    for c in plan["cells"]:
        r = rows[c["cell_id"]]
        mark = "—" if r is None or r["status"] == "infrastructure_failure" else ("✓" if r["verified"] else ("✗L" if r["status"] == "output_limit" else "✗"))
        if c["role"] == "recipient":
            rec[(c["world_id"], c["budget"], c["thinking"])][(c["holdout"], c["condition"])] = mark
        else:
            prop[(c["world_id"], c["budget"], c["thinking"])][c["arm"]] = (mark, r and r.get("bridge_valid"))
    L.append("| mundo | orçamento | pensar | irmão 1 sem ponte | irmão 1 oráculo | irmão 2 sem ponte | irmão 2 oráculo | regime? |"); L.append("|---|---|---|---|---|---|---|---|")
    regimes = []
    for (w, b, th), d in sorted(rec.items()):
        g = lambda h, c: d.get((h, c), "—")
        reg = g(1, "oracle_bridge") == "✓" and g(2, "oracle_bridge") == "✓" and g(1, "no_bridge").startswith("✗") and g(2, "no_bridge").startswith("✗")
        if reg: regimes.append((w, b, th))
        L.append(f"| {w[:6]} | {b} | {'sim' if th else 'não'} | {g(1,'no_bridge')} | {g(1,'oracle_bridge')} | {g(2,'no_bridge')} | {g(2,'oracle_bridge')} | {'**SIM**' if reg else 'não'} |")
    L.append("\n✗L = terminou por limite de saída sem submissão.\n")
    L.append("## Propositores: ponte válida (✓) / visível resolvido\n")
    L.append("| mundo | orçamento | pensar | D0 | D | C2 |"); L.append("|---|---|---|---|---|---|")
    for (w, b, th), d in sorted(prop.items()):
        f = lambda arm: ("—" if arm not in d else (("ponte ✓" if d[arm][1] else "ponte ✗") + (" + visível ✓" if d[arm][0] == "✓" else "")))
        L.append(f"| {w[:6]} | {b} | {'sim' if th else 'não'} | {f('D0')} | {f('D')} | {f('C2')} |")
    n = sum(1 for r in rows.values() if r); tok = sum((r or {}).get("usage", {}).get("completion_tokens", 0) for r in rows.values() if r)
    L.append(f"\nRegimes de contraste encontrados: {len(regimes)} → {regimes if regimes else 'nenhum'}. Células executadas: {n}/{len(rows)}; tokens de saída: {tok}.\n")
    (REPO / "docs/APPENDIX_P3_OPEN.md").write_text("\n".join(L) + "\n"); print("\n".join(L))


if __name__ == "__main__":
    main()
