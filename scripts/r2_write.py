#!/usr/bin/env python3
"""R2 writers (docs/R2_REGRAS_DE_ESCRITA_PRE_REGISTRO_V1.md §4): free (W0), provenance by instruction (W1), provenance by
construction (W2), and review then revision (W3, a fresh Claude Opus 5.5 review of the W0 paper, with the record, followed by a
revision by the same writer).

    python scripts/r2_write.py write  --arm W0 --writer opus --out runs/r2/write/W0_opus
    python scripts/r2_write.py review --w0 runs/r2/write/W0_opus --out runs/r2/write/W3r_opus
    python scripts/r2_write.py revise --w0 runs/r2/write/W0_opus --reviews runs/r2/write/W3r_opus --writer opus --out runs/r2/write/W3_opus

Every call goes through scripts/r1_replay.py's adapters, budget journal and raw log; one call per cell, the replay's retry policy,
nothing rerun once a model has answered. W2 papers are rendered from results/final.json and the record's claim texts, which the
generator derived from manifest.json (stale where the manifest is).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("r1_replay", HERE / "r1_replay.py")
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)

ROOT = HERE.parent
RECORDS = ROOT / "runs/r2/records"
TRUTH = ROOT / "runs/r2/truth"
rr.CEILING.update({"r2w": 30.0, "r2rev": 10.0, "r2fix": 20.0})
WRITERS = ("opus", "gpt")

BASE = ("You are the research assistant who maintains this study's paper. Below is the complete project record: the lab notebook, "
        "the result files, the project manifest, a note on the companion paper, and the draft of the paper, written on 2026-03-10 "
        "from the first read, before the study was finished. Update the draft into the final version of the paper: keep its "
        "structure and about its length, and make everything in it consistent with the final state of the record. Return only the "
        "final paper, in Markdown.")
NARROW = ("You are the research assistant who maintains this study's paper. Below is the complete project record: the lab notebook, "
          "the result files, the project manifest, a note on the companion paper, and the draft of the paper, written on 2026-03-10 "
          "from the first read. The final results are now in. Update the draft with the final results. Return only the updated "
          "paper, in Markdown.")
RULE_W1 = (" Rule for this paper: every number, and every statement about what is released, who reviewed the paper, the status of "
           "analyses, the model used, the registration of hypotheses and the companion paper, must be checked against the record and "
           "must match it. After each such statement add an HTML comment naming its source, for example "
           "<!-- source: results/final.json --> or <!-- source: notebook.md, 2026-04-18 -->.")
RULE_W2 = (" In this draft, numbers and some statements are placeholders that the build fills in: {{val:KEY}} from results/final.json, "
           "and {{claim:KEY}} with a sentence generated from manifest.json. Keep placeholders as placeholders and do not type those "
           "values or statements yourself; you may rewrite, add or remove the prose around them, and change which key a placeholder "
           "uses. Value keys: main, ci_lo, ci_hi, n, h2_est, h2_p, scope_pos, scope_total, mean_per_family, mean_pooled. Claim keys: "
           "release (from the released and withheld fields), review, status_sweep (from analyses), registration, companion "
           "(from companion_effect), model.")
REVIEW = ("You are reviewing a paper before it is deposited, against the complete project record below. List every statement in the "
          "paper that is inconsistent with the final state of the record: numbers, what is released, who reviewed it, the status of "
          "analyses, the model used, the registration of hypotheses, the companion paper, and anything else. Return only a JSON list "
          "of objects with the keys \"quote\", \"problem\" and \"correction\"; return an empty list if everything is consistent.")
REVISE = ("Below are the project record, the paper you wrote from it, and a review of the paper. Revise the paper: fix the problems "
          "in the review that are real, ignore any that are not, and keep everything else. Return only the full revised paper, in "
          "Markdown.")
VAL_FORMAT = {"main": "{:+.2f}", "ci_lo": "{:+.2f}", "ci_hi": "{:+.2f}", "n": "{}", "h2_est": "{:+.2f}", "h2_p": "{}",
              "scope_pos": "{}", "scope_total": "{}", "mean_per_family": "{}", "mean_pooled": "{}"}


def record_text(rid: str, keyed: bool) -> str:
    d = RECORDS / rid
    extra = sorted(str(p.relative_to(d)) for sub in ("results", "release", "reviews") if (d / sub).is_dir()
                   for p in (d / sub).iterdir() if p.is_file())
    names = ["notebook.md", *extra, *(["manifest.json"] if (d / "manifest.json").exists() else []), "companion.md",
             "draft_keyed.md" if keyed else "draft.md"]
    return "\n\n".join(f"=== FILE: {'draft.md' if n == 'draft_keyed.md' else n} ===\n{(d / n).read_text(encoding='utf-8')}"
                       for n in names)


def render(text: str, rid: str) -> tuple[str, list[str]]:
    """Fill {{val:...}} and {{claim:...}}; unknown keys are left in place and listed."""
    truth = json.loads((TRUTH / f"{rid}.json").read_text())
    vals, claims, unknown = truth["keyed_values"], truth["claims_rendered"], []

    def sub(m):
        kind, key = m.group(1), m.group(2).strip()
        if kind == "val" and key in vals:
            return VAL_FORMAT[key].format(vals[key])
        if kind == "claim" and key in claims:
            return claims[key]
        unknown.append(m.group(0))
        return m.group(0)
    return re.sub(r"\{\{\s*(val|claim)\s*:\s*([A-Za-z0-9_]+)\s*\}\}", sub, text), unknown


def strip_fence(text: str) -> str:
    m = re.match(r"^\s*```(?:markdown|md)?\s*\n(.*)\n```\s*$", text, re.S)
    return m.group(1) if m else text


def call(key: str, prompt: str, log, cell: str) -> dict:
    ad = rr.adapter(key)
    for attempt in (1, 2):
        try:
            stop, text, _, usage, raw = ad.step(ad.first(prompt))
            log({"event": "response", "cell": cell, "model": rr.MODELS[key]["id"], "stop": stop, "usage": usage, "raw": raw})
            return {"ok": True, "text": text, "stop": stop, "usage": usage, "usd": rr.cost(key, usage)}
        except Exception as e:
            log({"event": "call_error", "cell": cell, "attempt": attempt, "error": f"{type(e).__name__}: {e}"})
            if attempt == 2:
                return {"ok": False, "text": "", "stop": None, "usage": {}, "usd": 0.0, "error": f"{type(e).__name__}: {e}"[:300]}
            time.sleep(60)


def records() -> list[str]:
    return sorted(p.name for p in RECORDS.iterdir() if p.is_dir())


def write_arm(arm: str, writer: str, out: Path, label: str, ceiling: float | None) -> None:
    head = {"W0": BASE, "W1": BASE + RULE_W1, "W2": BASE + RULE_W2, "N0": NARROW, "N2": NARROW + RULE_W2}[arm]

    def cell(rid, log):
        name = f"{arm}_{writer}_{rid}"
        prompt = head + "\n\n" + record_text(rid, keyed=arm in ("W2", "N2"))
        r = call(writer, prompt, log, name)
        paper = strip_fence(r["text"]) if r["ok"] else ""
        res = {"cell": name, "arm": arm, "writer": writer, "record": rid, "status": "ok" if r["ok"] and paper else "failed",
               "stop": r["stop"], "raw_paper": paper, "usage": r["usage"], "usd": round(r["usd"], 4)}
        if arm in ("W2", "N2") and paper:
            res["paper"], res["unknown_placeholders"] = render(paper, rid)
            res["placeholders_left"] = len(re.findall(r"\{\{\s*(?:val|claim)\s*:", paper))
        else:
            res["paper"] = paper
        (out / f"{name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
        return res
    rr.batch("r2w", out, [(rid,) for rid in records()], cell, label, ceiling)


def review_w0(w0: Path, out: Path, label: str, ceiling: float | None) -> None:
    papers = sorted(w0.glob("W0_*.json"))

    def cell(i, log):
        src = json.loads(papers[i].read_text())
        name = src["cell"].replace("W0_", "W3r_")
        prompt = REVIEW + "\n\n" + record_text(src["record"], keyed=False) + "\n\n=== PAPER TO REVIEW ===\n" + src["paper"]
        r = call("opus", prompt, log, name)
        res = {"cell": name, "record": src["record"], "writer": src["writer"], "status": "ok" if r["ok"] else "failed",
               "review": r["text"], "usage": r["usage"], "usd": round(r["usd"], 4)}
        (out / f"{name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
        return res
    rr.batch("r2rev", out, [(i,) for i in range(len(papers))], cell, label, ceiling)


def revise(w0: Path, reviews: Path, writer: str, out: Path, label: str, ceiling: float | None) -> None:
    papers = sorted(w0.glob(f"W0_{writer}_*.json"))

    def cell(i, log):
        src = json.loads(papers[i].read_text())
        rev = json.loads((reviews / f"{src['cell'].replace('W0_', 'W3r_')}.json").read_text())
        name = src["cell"].replace("W0_", "W3_")
        prompt = (REVISE + "\n\n" + record_text(src["record"], keyed=False) + "\n\n=== YOUR PAPER ===\n" + src["paper"] +
                  "\n\n=== REVIEW ===\n" + rev["review"])
        r = call(writer, prompt, log, name)
        paper = strip_fence(r["text"]) if r["ok"] else ""
        res = {"cell": name, "arm": "W3", "writer": writer, "record": src["record"], "status": "ok" if paper else "failed",
               "stop": r["stop"], "paper": paper, "usage": r["usage"], "usd": round(r["usd"], 4)}
        (out / f"{name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
        return res
    rr.batch("r2fix", out, [(i,) for i in range(len(papers))], cell, label, ceiling)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["write", "review", "revise"])
    ap.add_argument("--arm", choices=["W0", "W1", "W2", "N0", "N2"])
    ap.add_argument("--writer", choices=WRITERS)
    ap.add_argument("--w0", type=Path)
    ap.add_argument("--reviews", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--ceiling", type=float)
    ap.add_argument("--records", type=Path, help="records directory (default runs/r2/records)")
    ap.add_argument("--truth", type=Path, help="truth directory (default runs/r2/truth)")
    a = ap.parse_args()
    global RECORDS, TRUTH
    RECORDS, TRUTH = (a.records or RECORDS).resolve(), (a.truth or TRUTH).resolve()
    out = a.out.resolve()
    if a.step == "write":
        write_arm(a.arm, a.writer, out, a.label or f"{a.arm}-{a.writer}", a.ceiling)
    elif a.step == "review":
        review_w0(a.w0.resolve(), out, a.label or "review", a.ceiling)
    else:
        revise(a.w0.resolve(), a.reviews.resolve(), a.writer, out, a.label or f"W3-{a.writer}", a.ceiling)


if __name__ == "__main__":
    main()
