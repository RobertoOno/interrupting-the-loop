#!/usr/bin/env python3
"""A9 — POST-HOC descriptive check, written after the single read and attached to no rule (docs/A9_PAREDES_VIRAM_DEGRAUS_RESULTADOS_V1.md).

Which ROUTE did the accepted proof of every solved W5 session take: the intended composition (a quadratic form of the state conserved
modulo p) or something else? The W5 certificate tested exact linear invariants and single linear forms modulo m; reading the accepted
proofs showed two shortcut families it did not test: ORDER invariants (W5 has no inverse moves, so a region such as x >= a and y >= b
can be closed under the moves while the target lies outside it) and a modular orbit of a PAIR of linear forms (x + z, y + w).
The type of the final accepted submission comes from the classifier validated in A6 (scripts/a6_forms.py).

  python3 scripts/a9_w5_routes.py --evidence docs/a9_evidence_v1 --out docs/a9_results/w5_routes.json
"""
from __future__ import annotations
import argparse, collections, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import a6_forms as F  # noqa: E402
from analysis_a1 import NOT_OBSERVED  # noqa: E402
from creative_machine.paired_stats import signflip  # noqa: E402

ARMS = ("a9_w5base_v1", "a9_w5own2_v1", "a9_w5own3_v1")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--evidence", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(); out = {"arms": {}, "sessions": []}; per = {arm: collections.defaultdict(lambda: [0, 0]) for arm in ARMS}
    for arm in ARMS:
        c = collections.Counter()
        for d in sorted((a.evidence / arm).iterdir()):
            if not d.is_dir() or ".failed" in d.name or ".interrupted" in d.name or not (d / "result.json").exists():
                continue
            R = json.loads((d / "result.json").read_text()); r, cell = R["result"], R["cell"]
            if r.get("status") in NOT_OBSERVED:
                continue
            per[arm][cell["instance"]][0] += 1; c["observed"] += 1
            if not r.get("target_solved"):
                continue
            srcs = [e.get("source") or "" for e in (json.loads(l) for l in (d / "events.jsonl").open() if l.strip()) if e.get("event") == "verification"]
            form = F.classify(srcs[-1]) if srcs else "none"; intended = form == "quad_mod"
            c["solved"] += 1; c["solved_intended"] += int(intended); c["solved_other_route"] += int(not intended)
            per[arm][cell["instance"]][1] += int(intended)
            out["sessions"].append({"arm": arm, "cell": d.name, "instance": cell["instance"], "final_form": form, "intended": intended})
        out["arms"][arm] = dict(c)
    inst = sorted(set(per["a9_w5own3_v1"]) & set(per["a9_w5own2_v1"]))
    d = np.asarray([per["a9_w5own3_v1"][i][1] / per["a9_w5own3_v1"][i][0] - per["a9_w5own2_v1"][i][1] / per["a9_w5own2_v1"][i][0] for i in inst], float)
    out["own3_vs_own2_intended_only"] = {"n_instances": len(inst), "mean_rate_diff": float(d.mean()), "p_rise": signflip(d, "greater")["p"], "note": "post hoc; no rule attached"}
    a.out.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"arms": out["arms"], "own3_vs_own2_intended_only": out["own3_vs_own2_intended_only"]}, indent=1))


if __name__ == "__main__":
    main()
