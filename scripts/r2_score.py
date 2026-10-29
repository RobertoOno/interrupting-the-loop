#!/usr/bin/env python3
"""R2 scoring (docs/R2_REGRAS_DE_ESCRITA_PRE_REGISTRO_V1.md §5): the twelve required claims of each final paper labelled by Kimi
K3 (a family other than both writers) against the record's ground truth, a mechanical count of leftover provisional numbers, and
the facts each W3 review flags.

    python scripts/r2_score.py score   --papers runs/r2/write/W0_opus runs/r2/write/W1_opus ... --out runs/r2/score
    python scripts/r2_score.py reviews --reviews runs/r2/write/W3r_opus runs/r2/write/W3r_gpt --out runs/r2/score_reviews
    python scripts/r2_score.py sample  --scores runs/r2/score --out runs/r2/validation_sample.json     # 60 pairs, arm hidden

HTML comments (the W1 source notes) are removed before scoring, so the scorer does not see which arm a paper comes from.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("r2_write", HERE / "r2_write.py")
rw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rw)
rr = rw.rr
rr.CEILING.update({"r2score": 10.0, "r2revscore": 3.0})
LABELS = {"correct", "stale", "wrong", "omitted", "ambiguous"}
SCORER = "kimi"
SEED = 20261006

SCORE_PROMPT = (
    "You check a research paper against twelve facts. For each fact you get the correct version, from the final record, and the "
    "outdated versions that appear in older parts of the record. Read the paper and label what it says about each fact: "
    "\"correct\" if it states the correct version (a faithful paraphrase or rounding counts); \"stale\" if it states one of the "
    "outdated versions; \"wrong\" if it states something else that is incorrect; \"omitted\" if it says nothing about the fact; "
    "\"ambiguous\" if it is unclear or states both. For each fact quote the sentence of the paper the label rests on (an empty "
    "string if omitted). Return only a JSON list of objects with the keys \"id\", \"label\" and \"quote\", covering all twelve "
    "facts.")
REVIEW_PROMPT = (
    "Below are twelve facts about a study, each with its correct version, and a review of a paper about the study. For each fact, "
    "say whether the review flags the paper's statement of that fact as wrong or outdated. Return only a JSON list of objects with "
    "the keys \"id\" and \"flagged\" (true or false), covering all twelve facts.")


def strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def facts_block(truth: dict) -> str:
    return "\n".join(f"{f['id']}. {f['fact']}: correct = {f['correct']}; outdated = {'; '.join(f['stale'])}" for f in truth["required"])


def leftover_provisional(paper: str, truth: dict) -> dict:
    """Mechanical: which provisional main-effect values, and whether the final one, appear in the paper."""
    nums = set(re.findall(r"[+\-−]?\d+\.\d+", paper.replace("−", "-")))
    absnums = {n.lstrip("+-") for n in nums}
    prov = [f"{abs(p):.2f}" for p in truth["provisional_main"]]
    final = f"{abs(truth['values']['main_effect']):.2f}"
    return {"provisional_present": [p for p in prov if p in absnums and p != final], "final_present": final in absnums}


def parse_list(text: str):
    import importlib.util as iu
    spec = iu.spec_from_file_location("r1_judging", HERE / "r1_judging.py")
    rj = iu.module_from_spec(spec)
    spec.loader.exec_module(rj)
    return rj.parse_findings_lenient(text)


def score(paper_dirs: list[Path], out: Path, label: str, ceiling: float | None) -> None:
    files = sorted(p for d in paper_dirs for p in d.glob("[WN][0-9]*_*.json") if not p.name.startswith("W3r_"))

    def cell(i, log):
        src = json.loads(files[i].read_text())
        truth = json.loads((rw.TRUTH / f"{src['record']}.json").read_text())
        paper = strip_comments(src.get("paper") or "")
        res = {"cell": src["cell"], "arm": src["arm"], "writer": src["writer"], "record": src["record"],
               "mechanical": leftover_provisional(paper, truth) if paper else None}
        if not paper:
            res.update({"status": "no_paper", "labels": None, "usd": 0.0})
        else:
            prompt = SCORE_PROMPT + "\n\nFacts:\n" + facts_block(truth) + "\n\n=== PAPER ===\n" + paper
            r = rw.call(SCORER, prompt, log, f"score_{src['cell']}")
            rows = parse_list(r["text"]) if r["ok"] else None
            labels = {}
            for row in rows or []:
                try:
                    fid, lab = int(row.get("id")), str(row.get("label", "")).strip().lower()
                except (TypeError, ValueError):
                    continue
                if 1 <= fid <= 12 and lab in LABELS:
                    labels[fid] = {"label": lab, "quote": str(row.get("quote", ""))[:400]}
            res.update({"status": "ok" if len(labels) == 12 else ("partial" if labels else "unparsed"), "labels": labels,
                        "usd": round(r["usd"], 4)})
        (out / f"score_{src['cell']}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
        return res
    rr.batch("r2score", out, [(i,) for i in range(len(files))], cell, label, ceiling)


def score_reviews(review_dirs: list[Path], out: Path, label: str, ceiling: float | None) -> None:
    files = sorted(p for d in review_dirs for p in d.glob("W3r_*.json"))

    def cell(i, log):
        src = json.loads(files[i].read_text())
        truth = json.loads((rw.TRUTH / f"{src['record']}.json").read_text())
        prompt = REVIEW_PROMPT + "\n\nFacts:\n" + facts_block(truth) + "\n\n=== REVIEW ===\n" + (src.get("review") or "")
        r = rw.call(SCORER, prompt, log, f"revscore_{src['cell']}")
        rows = parse_list(r["text"]) if r["ok"] else None
        flagged = {}
        for row in rows or []:
            try:
                flagged[int(row.get("id"))] = bool(row.get("flagged"))
            except (TypeError, ValueError):
                continue
        res = {"cell": src["cell"], "record": src["record"], "writer": src["writer"], "flagged": flagged,
               "status": "ok" if len(flagged) == 12 else "partial", "usd": round(r["usd"], 4)}
        (out / f"revscore_{src['cell']}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
        return res
    rr.batch("r2revscore", out, [(i,) for i in range(len(files))], cell, label, ceiling)


def sample(scores: Path, out: Path) -> None:
    """60 (paper, fact) pairs at random, with the arm and writer hidden behind a hash, for blind hand labels."""
    rows = []
    for p in sorted(scores.glob("score_*.json")):
        s = json.loads(p.read_text())
        if s.get("labels"):
            for fid in range(1, 13):
                rows.append((s["cell"], fid))
    rng = random.Random(SEED)
    picked = rng.sample(rows, 60)
    items = []
    for cell, fid in picked:
        uid = hashlib.sha256(f"{cell}#{fid}".encode()).hexdigest()[:10]
        items.append({"uid": uid, "cell": cell, "fact_id": fid})
    rng.shuffle(items)
    out.write_text(json.dumps(items, indent=1))
    print(len(items), "pairs written to", out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["score", "reviews", "sample"])
    ap.add_argument("--papers", type=Path, nargs="*")
    ap.add_argument("--reviews", type=Path, nargs="*")
    ap.add_argument("--scores", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--ceiling", type=float)
    ap.add_argument("--truth", type=Path, help="truth directory (default runs/r2/truth)")
    a = ap.parse_args()
    if a.truth:
        rw.TRUTH = a.truth.resolve()
    if a.step == "score":
        score([p.resolve() for p in a.papers], a.out.resolve(), a.label or "score", a.ceiling)
    elif a.step == "reviews":
        score_reviews([p.resolve() for p in a.reviews], a.out.resolve(), a.label or "reviews", a.ceiling)
    else:
        sample(a.scores.resolve(), a.out.resolve())


if __name__ == "__main__":
    main()
