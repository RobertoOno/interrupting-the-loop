#!/usr/bin/env python3
"""A2 sem curador, iteration 2 — POST-HOC descriptive check behind the 19/09 erratum (docs/A2_SEM_CURADOR_ITER2_RESULTADOS_V1.md).

The results document said that the loop's adapters "never declare a measure" in their first L4 submission. That counted the NAME
`measure`, which is the nomenclature of our curated references. This script counts what is actually written in the first submission of
every observed L4 session: a function of the state under any name, a quadratic expression of the state, and the MIXED term (a product of
two factors with different state fields, e.g. (s.x - 4) * (s.z - 3)) that the L4 invariant needs. Heuristic detectors, checked by hand on
the 24 sessions of a2c4_own2_v1 (16 linear forms, 8 diagonal quadratic forms, no mixed term).

  python3 scripts/a2c4_l4_forms.py --evidence docs/a2c4_evidence_v1 --out docs/a2c4_results/l4_first_submission_forms.json
"""
from __future__ import annotations
import argparse, collections, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis_a1 import NOT_OBSERVED  # noqa: E402
from a8_invariant_attempts import FIELD, _factor_left, _factor_right, has_field_product  # noqa: E402

STATEFN = re.compile(r"\b(def|let|have|abbrev)\s+\w+\s*(\(\s*\w+\s*:\s*State\s*\)|:\s*State\s*→|:\s*∀\s*\(?\w+\s*:\s*State)")
ARMS = ("a2c4_own2_v1", "a2c4_curm2_v1", "a2c4_own2t131_v1", "a2c4_curm2t131_v1", "a2c4_baset131_v1")


def has_cross(src: str) -> bool:
    for line in src.splitlines():
        for i, ch in enumerate(line):
            if ch == "*":
                a = {m.group(0).split(".")[1] for m in FIELD.finditer(_factor_left(line, i))}; b = {m.group(0).split(".")[1] for m in FIELD.finditer(_factor_right(line, i))}
                if a and b and a != b:
                    return True
    return False


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--evidence", type=Path, required=True); p.add_argument("--out", type=Path, required=True); p.add_argument("--step", default="L4")
    a = p.parse_args(); out = {}
    for arm in ARMS:
        c = collections.Counter()
        for d in sorted((a.evidence / arm).iterdir()):
            if not d.is_dir() or f"_{a.step}_" not in d.name or ".failed" in d.name or ".interrupted" in d.name or not (d / "result.json").exists():
                continue
            r = json.loads((d / "result.json").read_text())["result"]
            if r.get("status") in NOT_OBSERVED:
                continue
            srcs = [e.get("source") or "" for e in (json.loads(l) for l in (d / "events.jsonl").open() if l.strip()) if e.get("event") == "verification"]
            c["observed"] += 1; c["solved"] += int(bool(r.get("target_solved")))
            if not srcs:
                continue
            f = srcs[0]; c["with_first_submission"] += 1; c["first_names_measure"] += int(bool(re.search(r"\bmeasure\b", f)))
            c["first_state_function"] += int(bool(STATEFN.search(f))); c["first_quadratic"] += int(has_field_product(f)); c["first_mixed_term"] += int(has_cross(f))
            c["any_mixed_term"] += int(any(has_cross(s) for s in srcs))
        out[arm] = dict(c); print(arm, dict(c))
    a.out.write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
