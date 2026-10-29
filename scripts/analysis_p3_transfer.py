#!/usr/bin/env python3
"""Programa 3 — single read of the production/transfer diagnostic (written before the data,
PLANO 2026-09-08). Descriptive: two exposed calibration worlds, no confirmatory test.
Per world: proposers (arm -> bridge valid, visible solved, revisions, cost); recipients (holdout x
condition -> solved); utility of each candidate bridge U = solved(with bridge) - solved(baseline)
per holdout, next to the contemporary oracle. Writes docs/APPENDIX_P3_TRANSFER.md.

    python scripts/analysis_p3_transfer.py
"""
import json
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "runs/p3/transfer_v1"


def main() -> None:
    bp = json.loads((REPO / "docs/p3/transfer_design_draft_v1.json").read_text())
    rows = {}
    for c in bp["cells"]:
        p = OUT / c["cell_id"] / "result.json"
        rows[c["cell_id"]] = json.loads(p.read_text()) if p.exists() else None
    L = ["# Programa 3 — diagnóstico de produção/transferência (leitura única)\n",
         "Dois mundos de calibração expostos (invariante, representação); 6 propositores (D0/D/C2 × mundo), receptores novos nos dois irmãos ocultos com a ponte candidata, baseline (B) e oráculo (O). Descritivo por desenho: não há teste confirmatório.\n"]
    total = 0.0; n_done = 0
    for wid in sorted({c["world_id"] for c in bp["cells"]}):
        fam = next(c["family"] for c in bp["cells"] if c["world_id"] == wid)
        L.append(f"\n## Mundo {wid} ({fam})\n")
        L.append("| propositor | braço | estado | desfecho | ponte válida | visível resolvido | revisões | custo US$ |"); L.append("|---|---|---|---|---|---|---|---|")
        for c in sorted((c for c in bp["cells"] if c["world_id"] == wid and c["role"] == "proposer"), key=lambda c: c["ordinal"]):
            r = rows[c["cell_id"]]; res = (r or {}).get("result") or {}
            cost = float(res.get("cost_usd_at_configured_rates", 0) or 0); total += cost; n_done += bool(res)
            L.append(f"| {c['cell_id']} | {c['arm']} | {res.get('status', '—' if r else 'não rodou')} | {res.get('production_outcome', '—')} | "
                     f"{'sim' if res.get('selected_bridge') else 'não'} | {'sim' if res.get('visible_solved') else 'não'} | {res.get('revisions', '—')} | {cost:.2f} |")
        L.append("\n| irmão | condição | braço/origem | resolvido | revisões | custo US$ |"); L.append("|---|---|---|---|---|---|")
        solved = defaultdict(dict)
        for c in sorted((c for c in bp["cells"] if c["world_id"] == wid and c["role"] == "recipient"), key=lambda c: (c["holdout"], c["ordinal"])):
            r = rows[c["cell_id"]]; res = (r or {}).get("result") or {}
            cost = float(res.get("cost_usd_at_configured_rates", 0) or 0); total += cost; n_done += bool(res)
            st = "pulado: " + r["skipped"] if r and r.get("skipped") else ("sim" if res.get("target_solved") else ("não" if res else "não rodou"))
            key = c["arm"] if c["bridge_kind"] != "candidate" else f"{c['arm']}(ponte de {c['parent_proposer_id']})"
            solved[c["holdout"]][key] = res.get("target_solved") if res else None
            L.append(f"| {c['holdout']} | {c['bridge_kind']} | {key} | {st} | {res.get('revisions', '—')} | {cost:.2f} |")
        L.append("\n**Utilidade das pontes candidatas** (U = resolvido com a ponte − resolvido na baseline, por irmão; oráculo ao lado):\n")
        L.append("| irmão | baseline | oráculo | D0 | D | C2 |"); L.append("|---|---|---|---|---|---|")
        for h in (1, 2):
            s = solved.get(h, {})
            def cell(k):
                m = [v for kk, v in s.items() if kk.startswith(k + "(")]
                if not m: return "—"
                v = m[0]; b = s.get("B")
                return "—" if v is None or b is None else f"{int(v) - int(b):+d}"
            L.append(f"| {h} | {s.get('B', '—')} | {s.get('O', '—')} | {cell('D0')} | {cell('D')} | {cell('C2')} |")
    L.append(f"\nCélulas executadas: {n_done}/26; custo total a tarifas configuradas: US${total:.2f}.\n")
    (REPO / "docs/APPENDIX_P3_TRANSFER.md").write_text("\n".join(L) + "\n"); print("\n".join(L))


if __name__ == "__main__":
    main()
