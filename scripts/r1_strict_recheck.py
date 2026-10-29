#!/usr/bin/env python3
"""Post hoc strict re-check of the matcher (prompted by the fifth review of the report, round 7 in the archive): every match between a
finding and a primary erratum is judged again, one pair at a time, with the matcher's own rubric, by two judges blind to the check,
to the freeze coding and to the hypothesis. Protocol: docs/r1/report_review_v2/strict_recheck/PROTOCOL.md.

    python scripts/r1_strict_recheck.py pairs      # writes pairs.jsonl (what the judges see) and key.json (what they do not)
    python scripts/r1_strict_recheck.py judge-gpt  # GPT-6.1 Sol on Bedrock, budgeted, one call per document and per free-text pair

The second judge, a fresh Claude Fable 5.1 agent, reads pairs.jsonl and writes verdicts_fable.json (instructions in PROTOCOL.md).
The strict counts are computed in scripts/r1_report_numbers.py.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import r1_judging as J  # noqa: E402
import r1_replay as R  # noqa: E402

R.CEILING.update({"strict": 3.0})   # in memory, as scripts/r1_judging.py does for its own batches

EV = ROOT / "docs/r1/evidence_v1"
OUT = ROOT / "docs/r1/report_review_v2/strict_recheck"
SEED = 20261016

QUESTION = ("You check, one pair at a time, whether a reviewer's finding about a research paper identifies a known error in that "
            "paper. " + J.MATCH_RUBRIC + " Judge each pair on its own, from the finding's text and the known error's statement and "
            "defect only.")


def pairs() -> None:
    ref = {r["id"]: r for r in J.reference()}
    rows, key = [], {}
    for p in sorted((EV / "matches_filled").rglob("c[1-4]_*.json")):
        row = json.loads(p.read_text(encoding="utf-8"))
        if row.get("mode") == "findings":
            for f in row["findings"]:
                for i in f.get("matches") or []:
                    if ref[i]["primary"]:
                        rows.append({"doc": row["doc"], "kind": "finding",
                                     "finding": f"quote: \"{str(f.get('quote', ''))[:300]}\" | problem: {str(f.get('problem', ''))[:600]}",
                                     "error": f"statement: \"{J.excerpt(ref[i])}\" | defect: {ref[i]['defect']}",
                                     "_key": {"occasion": row["occasion"], "cell": row["cell"], "n": f["n"], "erratum": i}})
        elif row.get("mode") == "free_text":
            cell = json.loads((EV / "c1" / row["cell"].split("_")[1] / f"{row['cell']}.json").read_text(encoding="utf-8"))
            for i in row.get("matches") or []:
                if ref[i]["primary"]:
                    rows.append({"doc": row["doc"], "kind": "report", "finding": cell.get("text", "")[:60000],
                                 "error": f"statement: \"{J.excerpt(ref[i])}\" | defect: {ref[i]['defect']}",
                                 "_key": {"occasion": row["occasion"], "cell": row["cell"], "n": "free_text", "erratum": i}})
    random.Random(SEED).shuffle(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "pairs.jsonl").open("w", encoding="utf-8") as fh:
        for k, r in enumerate(rows, 1):
            pid = f"p{k:03d}"
            key[pid] = r.pop("_key")
            fh.write(json.dumps({"pair": pid, **r}, ensure_ascii=False) + "\n")
    (OUT / "key.json").write_text(json.dumps(key, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"pairs": len(rows), "free_text": sum(1 for v in key.values() if v["n"] == "free_text")}))


def prompt_for(batch: list[dict]) -> str:
    lines = []
    for r in batch:
        who = "Report" if r["kind"] == "report" else "Finding"
        lines.append(f"Pair {r['pair']}:\n  {who}: {r['finding']}\n  Known error: {r['error']}")
    return (QUESTION + "\n\n" + "\n\n".join(lines) + "\n\nReturn only a JSON list with one object per pair: {\"pair\": <id>, "
            "\"identifies\": \"yes\" or \"no\", \"reason\": <one short sentence>}.")


def run_gpt_cell(key: str, doc: str, run: int, frozen, out: Path, log) -> dict:
    """One budgeted call (cell = one document's finding pairs, or one free-text pair), through r1_replay's adapters."""
    batch = [json.loads(l) for l in (OUT / "pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    batch = [r for r in batch if r["doc"] == doc and (r["kind"] == "finding" if run == 0 else r["pair"] == f"p{run:03d}")]
    cell = f"strict_gpt_{doc}_{'findings' if run == 0 else f'p{run:03d}'}"
    res = J.ask("gpt", prompt_for(batch), log, cell)
    parsed = J.parse_json(res["text"]) if res["ok"] else None
    got = {str(x.get("pair")): x for x in parsed if isinstance(x, dict)} if isinstance(parsed, list) else {}
    row = {"cell": cell, "doc": doc, "pairs": [r["pair"] for r in batch], "verdicts": [got.get(r["pair"]) for r in batch],
           "status": "ok" if res["ok"] and all(got.get(r["pair"]) for r in batch) else "incomplete", "text": res.get("text", ""),
           "usd": res["usd"]}
    (out / f"{cell}.json").write_text(json.dumps(row, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"cell": cell, "status": row["status"], "usd": res["usd"], "n_pairs": len(batch)}


def judge_gpt() -> None:
    rows = [json.loads(l) for l in (OUT / "pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    docs = sorted({r["doc"] for r in rows if r["kind"] == "finding"})
    cells = [("gpt", d, 0, None, OUT / "gpt") for d in docs]
    cells += [("gpt", r["doc"], int(r["pair"][1:]), None, OUT / "gpt") for r in rows if r["kind"] == "report"]
    R.batch("strict", OUT / "gpt", cells, run_gpt_cell, label="gpt", ceiling=3.0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("step", choices=["pairs", "judge-gpt"])
    a = ap.parse_args()
    pairs() if a.step == "pairs" else judge_gpt()


if __name__ == "__main__":
    main()
