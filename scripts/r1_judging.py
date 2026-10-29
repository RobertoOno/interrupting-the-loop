#!/usr/bin/env python3
"""R1 judging steps (docs/R1_REPLAY_CHECAGENS_PRE_REGISTRO_V0.md §4, §7): coder B, the matcher's validation, matching, clustering
and adjudication of new findings, and the captures file for scripts/r1_analysis.py.

    python scripts/r1_judging.py code-b           --out runs/r1/coder_b
    python scripts/r1_judging.py make-validation  --out runs/r1/match_validation_set
    python scripts/r1_judging.py validate-matcher --validation runs/r1/match_validation_set --out runs/r1/match_validation
    python scripts/r1_judging.py match            --cells runs/r1/c1 runs/r1/c2 runs/r1/c3 runs/r1/c4 --out runs/r1/matches
    python scripts/r1_judging.py cluster          --matches runs/r1/matches --out runs/r1/clusters
    python scripts/r1_judging.py adjudicate       --clusters runs/r1/clusters --out runs/r1/adjudication
    python scripts/r1_judging.py captures         --matches runs/r1/matches --adjudication runs/r1/adjudication --out runs/r1/captures.json

Models: coder B and the second adjudicator are GPT-6.1 Sol; the matcher and the clusterer are Claude Sonnet 5.5 (not a checker);
the validation findings are written by Kimi K3; the first adjudicator is Claude Opus 5.5. Every call goes through r1_replay's
adapters, budget journal and raw log; nothing is rerun once a model has answered.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("r1_replay", HERE / "r1_replay.py")
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)

ROOT = HERE.parent
REFERENCE = ROOT / "docs/r1/reference_set_v1.jsonl"
FROZEN = ROOT / "runs/r1/frozen"
SEED = 20261006
rr.CEILING.update({"codeb": 3.0, "valgen": 2.0, "valmatch": 3.0, "match": 15.0, "cluster": 5.0, "adjud": 20.0})
CHECKER_SEVERITY_KEPT = {"high", "medium"}
SEVERITY_WORDS = {"critical": "high", "major": "high", "high": "high", "medium": "medium", "moderate": "medium",
                  "low": "low", "minor": "low", "trivial": "low"}


def severity_of(f: dict) -> str:
    """The checker's own severity label, normalized to high / medium / low ('' when absent or unrecognized)."""
    word = str(f.get("severity") or "").strip().lower().split()[0] if str(f.get("severity") or "").strip() else ""
    return SEVERITY_WORDS.get(word.strip(".:,;"), "")

CODEBOOK = """Classes:
NUM: a number in the text differs from the record or from the paper's own tables or appendix (including provisional numbers or
values from an older run).
MIX: two different measures or estimands reported as one (for example a pooled mean where per-family means are used elsewhere).
SCOPE: a statement broader than what was measured or than the data support (overgeneralization, overclaimed validation, absolute
claims).
STATUS: a false statement about the progress of the work (in progress, to be reported, planned work that was cancelled).
META: a false statement about the work's own artifacts, process or review (data or code availability, pre-registration status,
provenance tables, who reviewed it, statements about the use of AI).
METHOD: an inaccurate description of what was actually done (model identity, where it ran, what data a model was trained on).
PROP: an error inherited from, or about, a companion paper (attributing to it a result or reading it does not contain or no longer
holds).
INTERNAL: a contradiction between parts of the same document (abstract against body, text against table, a leftover sentence from
an earlier version).
CITE: a bibliographic error (wrong authors, title, category or identifier of a reference).
TYPO: a typographical or formatting error with no consequence for content (duplicated words, broken references).
Severities:
G1: changes a central or declared finding.
G2: changes a secondary claim, or a number by more than rounding.
G3: cosmetic or minor."""

MATCH_RUBRIC = (
    "A finding identifies a known error only if (1) it points to the same statement (the same sentence, number or claim; for an "
    "omission, the same missing element) and (2) it states the same defect (the same wrong number, the same conflation, the same "
    "overclaim, the same false status, the same contradiction). A different concern about the same sentence does not count. A "
    "finding that names the defect at any of the error's locations counts, even if its proposed correction is wrong. A finding may "
    "identify several known errors, or none."
)


def reference(path: Path = REFERENCE) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def flat_lines(doc: str, frozen: Path = FROZEN) -> list[str]:
    return rr.blank_comments((frozen / doc / "flat.tex").read_text(encoding="utf-8")).split("\n")


def excerpt(item: dict, frozen: Path = FROZEN) -> str:
    if item["omission"]:
        return "(omission: no single location in the text)"
    lines = flat_lines(item["doc"], frozen)
    parts = []
    for loc in item["locations"]:
        if loc["flat_line"]:
            parts.append(lines[loc["flat_line"] - 1].strip()[:300])
        else:
            parts.append(f"[bibliography] {loc['key']}")
    return " || ".join(parts)


def known_errors_block(doc: str, ref: list[dict], frozen: Path = FROZEN) -> str:
    return "\n".join(f"- {r['id']}: statement: \"{excerpt(r, frozen)}\" | defect: {r['defect']}" for r in ref if r["doc"] == doc)


def parse_json(text: str):
    text = text.strip()
    for cand in (text, *(m.group(1) for m in re.finditer(r"```(?:json)?\s*(.+?)```", text, re.S))):
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            pass
    for o, c in (("[", "]"), ("{", "}")):
        i, j = text.find(o), text.rfind(c)
        if 0 <= i < j:
            try:
                return json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                pass
    return None


def repair_backslashes(s: str) -> str:
    """Make a reply that quotes LaTeX verbatim parse as JSON (operational amendment 3). Escaped backslash pairs and \\uXXXX stay;
    a one-letter escape stays unless more letters follow (then it is a LaTeX command); any other backslash becomes literal. Only
    used after the strict parse has failed."""
    out, i, n = [], 0, len(s)
    while i < n:
        ch = s[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        nxt = s[i + 1] if i + 1 < n else ""
        if nxt == "\\":
            out.append("\\\\")
            i += 2
        elif nxt == "u" and re.match(r"[0-9a-fA-F]{4}", s[i + 2:i + 6]):
            out.append(s[i:i + 6])
            i += 6
        elif nxt and nxt in '"/bfnrt' and not (nxt.isalpha() and i + 2 < n and s[i + 2].isalpha()):
            out.append(s[i:i + 2])
            i += 2
        else:
            out.append("\\\\")
            i += 1
    return "".join(out)


def parse_findings_lenient(text: str):
    """r1_replay.parse_findings, then the same candidates after repair_backslashes, parsed with strict=False; a JSON object holding
    one list of findings is accepted as that list."""
    found = rr.parse_findings(text)
    if found is not None:
        return found
    s = text.strip()
    cands = [s]
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", s, re.S)
    if m:
        cands.append(m.group(1))
    i, j = s.find("["), s.rfind("]")
    if 0 <= i < j:
        cands.append(s[i:j + 1])
    for c in cands:
        try:
            val = json.loads(repair_backslashes(c), strict=False)
        except json.JSONDecodeError:
            continue
        if isinstance(val, dict):
            lists = [v for v in val.values() if isinstance(v, list)]
            val = lists[0] if len(lists) == 1 else None
        if isinstance(val, list):
            return [f if isinstance(f, dict) else {"problem": str(f)} for f in val]
    return None


def ask(key: str, prompt: str, log, cell: str, max_out: int | None = None) -> dict:
    """One model call with the replay's policy: a call that fails is retried once after 60 s; an answer is final."""
    ad = rr.adapter(key)
    for attempt in (1, 2):
        try:
            stop, text, _, usage, raw = ad.step(ad.first(prompt), max_out=max_out)
            log({"event": "response", "cell": cell, "model": rr.MODELS[key]["id"], "stop": stop, "usage": usage, "raw": raw})
            return {"ok": True, "text": text, "usage": usage, "usd": rr.cost(key, usage), "stop": stop}
        except Exception as e:
            log({"event": "call_error", "cell": cell, "attempt": attempt, "error": f"{type(e).__name__}: {e}"})
            if attempt == 2:
                return {"ok": False, "text": "", "usage": {}, "usd": 0.0, "error": f"{type(e).__name__}: {str(e)[:300]}"}
            time.sleep(60)


# --------------------------------------------------------------------------------------------------------------- coder B
def code_b(out: Path) -> None:
    ref = reference()
    items = "\n".join(f"- {r['id']} (paper {r['doc']}): statement: \"{excerpt(r)}\" | defect: {r['defect']}" for r in ref)
    prompt = ("You are coding a list of known errors in six research papers with the codebook below. For each item choose exactly "
              "one primary class and one severity, using only the information given. Return a JSON list of objects with the keys "
              "\"id\", \"class\" and \"severity\", covering every item.\n\n" + CODEBOOK + "\n\nItems:\n" + items)

    def cell(_, log):
        r = ask("gpt", prompt, log, "coder_b")
        coded = parse_json(r["text"]) if r["ok"] else None
        (out / "coder_b.json").write_text(json.dumps({"raw_text": r["text"], "coded": coded}, ensure_ascii=False, indent=1))
        return {"cell": "coder_b", "status": "ok" if isinstance(coded, list) else "unparsed", "usd": r["usd"]}
    rr.batch("codeb", out, [("coder_b",)], cell)


def kappa(a: list[str], b: list[str]) -> float:
    cats = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


# --------------------------------------------------------------------------------------------------------- validation set
def make_validation(out: Path) -> None:
    ref = [r for r in reference() if r["primary"] and not r["omission"]]
    loc_count = defaultdict(int)
    for r in ref:
        for loc in r["locations"]:
            loc_count[(r["doc"], loc["flat_line"])] += 1
    unique = [r for r in ref if all(loc_count[(r["doc"], l["flat_line"])] == 1 for l in r["locations"])]
    rng = random.Random(SEED)
    picks = rng.sample(unique, 60)
    jobs = [(r, "pos") for r in picks[:30]] + [(r, "neg") for r in picks[30:]]
    pos_t = ("Here is a known error in a research paper. Statement: \"{s}\". Defect: {d}\nWrite one finding as a reviewer would "
             "write it, in your own words, that identifies exactly this defect. Quote a short fragment of the statement. Do not copy "
             "the defect text. Return only JSON: {{\"quote\": ..., \"problem\": ...}}")
    neg_t = ("Here is a statement from a research paper: \"{s}\". Write one plausible reviewer finding about this statement that is "
             "NOT about the following defect and does not mention it: {d}\nIt should be a different concern: a request for "
             "clarification or detail, a presentational point, or another minor issue. Quote a short fragment of the statement. "
             "Return only JSON: {{\"quote\": ..., \"problem\": ...}}")
    rows = []

    def cell(i, log):
        r, label = jobs[i]
        prompt = (pos_t if label == "pos" else neg_t).format(s=excerpt(r), d=r["defect"])
        res = ask("kimi", prompt, log, f"val_{i:02d}")
        f = parse_json(res["text"]) if res["ok"] else None
        rows.append({"vid": f"V{i:02d}", "doc": r["doc"], "target": r["id"], "label": label,
                     "quote": (f or {}).get("quote", ""), "problem": (f or {}).get("problem", ""), "parsed": isinstance(f, dict)})
        (out / "set.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        return {"cell": f"val_{i:02d}", "status": "ok" if isinstance(f, dict) else "unparsed", "usd": res["usd"]}
    rr.batch("valgen", out, [(i,) for i in range(len(jobs))], cell)


# ---------------------------------------------------------------------------------------------------------------- matcher
def match_prompt(doc: str, findings: list[dict], ref: list[dict]) -> str:
    fl = "\n".join(f"{f['n']}. quote: \"{str(f.get('quote', ''))[:300]}\" | problem: {str(f.get('problem', ''))[:600]}"
                   for f in findings)
    return ("You match reviewer findings about a research paper to a list of known errors in that paper. " + MATCH_RUBRIC +
            "\n\nKnown errors:\n" + known_errors_block(doc, ref) + "\n\nFindings:\n" + fl +
            "\n\nReturn only a JSON list with one object per finding: {\"finding\": <number>, \"matches\": [<ids>]}.")


def free_text_prompt(doc: str, text: str, ref: list[dict]) -> str:
    return ("You match a reviewer's free-text report on a research paper to a list of known errors in that paper. " + MATCH_RUBRIC +
            "\n\nKnown errors:\n" + known_errors_block(doc, ref) + "\n\nReport:\n" + text[:60000] +
            "\n\nReturn only a JSON list of the ids of the known errors that the report identifies.")


def run_matcher(doc: str, findings: list[dict], ref: list[dict], log, cell: str) -> tuple[dict, float]:
    """{finding number: [ids]} for findings in chunks of at most 25."""
    out, usd = {}, 0.0
    valid = {r["id"] for r in ref if r["doc"] == doc}
    for k in range(0, len(findings), 25):
        chunk = findings[k:k + 25]
        res = ask("sonnet", match_prompt(doc, chunk, ref), log, f"{cell}_m{k // 25}")
        usd += res["usd"]
        parsed = parse_json(res["text"]) if res["ok"] else None
        got = {}
        if isinstance(parsed, list):
            for row in parsed:
                if isinstance(row, dict) and "finding" in row:
                    got[int(row["finding"])] = [m for m in (row.get("matches") or []) if m in valid]
        for f in chunk:
            out[f["n"]] = got.get(f["n"])          # None marks a finding the matcher did not return
    return out, usd


def validate_matcher(validation: Path, out: Path) -> None:
    ref = reference()
    rows = [r for r in json.loads((validation / "set.json").read_text()) if r["parsed"]]
    rng = random.Random(SEED + 1)
    by_doc = defaultdict(list)
    for r in rows:
        by_doc[r["doc"]].append(r)
    cells = []
    for doc, rs in sorted(by_doc.items()):
        rng.shuffle(rs)
        for k in range(0, len(rs), 12):
            cells.append((doc, rs[k:k + 12]))
    results = []

    def cell(i, log):
        doc, rs = cells[i]
        findings = [{"n": j + 1, "quote": r["quote"], "problem": r["problem"]} for j, r in enumerate(rs)]
        got, usd = run_matcher(doc, findings, ref, log, f"valmatch_{i}")
        for j, r in enumerate(rs):
            results.append({**r, "matches": got.get(j + 1)})
        return {"cell": f"valmatch_{i}", "status": "ok", "usd": usd}
    rr.batch("valmatch", out, [(i,) for i in range(len(cells))], cell)
    pos = [r for r in results if r["label"] == "pos"]
    tp = sum(1 for r in pos if r["matches"] and r["target"] in r["matches"])
    all_matches = sum(len(r["matches"] or []) for r in results)
    correct = sum(1 for r in pos if r["matches"] and r["target"] in r["matches"])
    metrics = {"n_pos": len(pos), "n_neg": len(results) - len(pos), "recall": tp / len(pos) if pos else None,
               "precision": correct / all_matches if all_matches else None,
               "neg_false_matches": sum(1 for r in results if r["label"] == "neg" and r["matches"]),
               "unreturned": sum(1 for r in results if r["matches"] is None)}
    metrics["passes"] = bool(metrics["recall"] is not None and metrics["recall"] >= 0.9 and metrics["precision"] is not None
                             and metrics["precision"] >= 0.9)
    (out / "validation_results.json").write_text(json.dumps({"metrics": metrics, "rows": results}, ensure_ascii=False, indent=1))
    print(json.dumps(metrics))


def occasion_of(cell: str) -> str:
    m = re.match(r"c1_(\w+?)_(P\w+)_r(\d+)$", cell)
    if m:
        return f"C1:{m.group(1)}:r{m.group(3)}"
    m = re.match(r"c2_(\w+?)_(P\w+)$", cell)
    if m:
        return f"C2:{m.group(1)}"
    m = re.match(r"(c3|c4)_(P\w+)$", cell)
    if m:
        return m.group(1).upper()
    raise ValueError(cell)


def match_cells(cell_dirs: list[Path], out: Path, label: str = "", ceiling: float | None = None) -> None:
    ref = reference()
    files = []
    for d in cell_dirs:
        files += sorted(p for p in d.glob("c[1-4]_*.json"))
    jobs = []
    for p in files:
        res = json.loads(p.read_text())
        cell = p.stem
        doc = res.get("doc") or re.search(r"_(P\w+?)(?:_r\d+)?$", cell).group(1)
        jobs.append((cell, doc, res))

    def cell_fn(i, log):
        cell, doc, res = jobs[i]
        row = {"cell": cell, "doc": doc, "occasion": occasion_of(cell), "status": res.get("status")}
        usd = 0.0
        parsed = res.get("findings") if res.get("check") in ("C3", "C4") else (
            parse_findings_lenient(res.get("text", "")) if res.get("status") in ("ok", "unparsed") else None)
        if isinstance(parsed, list):
            findings = [{"n": j + 1, **{k: f.get(k) for k in ("quote", "problem", "evidence", "severity")}}
                        for j, f in enumerate(parsed)]
            got, usd = run_matcher(doc, findings, ref, log, cell)
            row["mode"] = "findings"
            row["findings"] = [{**f, "matches": got.get(f["n"])} for f in findings]
        elif res.get("status") == "unparsed" and res.get("text"):
            r = ask("sonnet", free_text_prompt(doc, res.get("text", ""), ref), log, cell)
            usd = r["usd"]
            ids = parse_json(r["text"]) if r["ok"] else None
            valid = {x["id"] for x in ref if x["doc"] == doc}
            row["mode"] = "free_text"
            row["matches"] = [x for x in ids if x in valid] if isinstance(ids, list) else None
        else:
            row["mode"] = "skipped"
        (out / f"{cell}.json").write_text(json.dumps(row, ensure_ascii=False, indent=1))
        return {"cell": cell, "status": row["mode"], "usd": usd}
    rr.batch("match", out, [(i,) for i in range(len(jobs))], cell_fn, label, ceiling)


def matcher_rows(text: str) -> list[dict] | None:
    """The longest JSON list of {"finding", "matches"} objects anywhere in a matcher reply (a reply may restate its list)."""
    dec, best = json.JSONDecoder(), None
    for i, ch in enumerate(text):
        if ch != "[":
            continue
        try:
            val, _ = dec.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(val, list) and val and all(isinstance(r, dict) and "finding" in r for r in val):
            if best is None or len(val) > len(best):
                best = val
    return best


def refill(matches_in: Path, out: Path) -> None:
    """Operational amendment 6: re-read every stored matcher reply (no model call). A finding the reply lists gets its matches; a
    finding a well-formed, complete reply (end_turn) leaves out is read as 'no match', since the matcher listed only matches; a
    finding whose chunk has no parseable reply stays undecided (None)."""
    out.mkdir(parents=True, exist_ok=True)
    ref = reference()
    for part in sorted(d for d in matches_in.iterdir() if d.is_dir()):
        replies = {}
        for line in (part / "raw.jsonl").read_text().splitlines():
            e = json.loads(line)
            if e.get("event") == "response" and re.search(r"_m\d+$", e.get("cell", "")):
                content = e["raw"]["output"]["message"]["content"]
                replies[e["cell"]] = ("".join(b.get("text", "") for b in content), e.get("stop"))
        for p in sorted(part.glob("c[1-4]_*.json")):
            row = json.loads(p.read_text())
            if row.get("mode") == "findings":
                valid = {r["id"] for r in ref if r["doc"] == row["doc"]}
                for k in range(0, len(row["findings"]), 25):
                    text, stop = replies.get(f"{row['cell']}_m{k // 25}", ("", None))
                    rows = matcher_rows(text)
                    got = {int(r["finding"]): [m for m in (r.get("matches") or []) if m in valid] for r in rows or []}
                    for f in row["findings"][k:k + 25]:
                        if f["n"] in got:
                            f["matches"], f["decision"] = got[f["n"]], "returned"
                        elif rows is not None and stop in ("end_turn", "stop", "stop_sequence"):
                            f["matches"], f["decision"] = [], "omitted_as_no_match"
                        else:
                            f["matches"], f["decision"] = None, "undecided"
            (out / part.name).mkdir(exist_ok=True)
            (out / part.name / p.name).write_text(json.dumps(row, ensure_ascii=False, indent=1))


def fill_undecided(filled: Path, out: Path) -> None:
    """One extra matcher pass, only for findings still undecided after `refill` (same prompt and rubric); what stays undecided
    after it counts as unmatched. Results are written back into the refilled files, marked decision='filled'."""
    ref = reference()
    jobs = []
    for p in sorted(filled.glob("*/c[1-4]_*.json")):
        row = json.loads(p.read_text())
        if row.get("mode") == "findings" and any(f["matches"] is None for f in row["findings"]):
            jobs.append(p)

    def cell(i, log):
        p = jobs[i]
        row = json.loads(p.read_text())
        todo = [f for f in row["findings"] if f["matches"] is None]
        got, usd = run_matcher(row["doc"], todo, ref, log, f"fill_{row['cell']}")
        for f in row["findings"]:
            if f["matches"] is None:
                m = got.get(f["n"])
                f["matches"], f["decision"] = (m, "filled") if m is not None else ([], "undecided_after_fill")
        p.write_text(json.dumps(row, ensure_ascii=False, indent=1))
        return {"cell": f"fill_{row['cell']}", "status": "ok", "usd": usd}
    rr.batch("match", out, [(i,) for i in range(len(jobs))], cell, "fill", 1.0)


# ------------------------------------------------------------------------------------------------- clustering, adjudication
def unmatched(matches: Path) -> dict:
    """Unmatched high/medium findings of the model checks (C1, C2), by document, with stable ids."""
    by_doc = defaultdict(list)
    for p in sorted(matches.rglob("c[12]_*.json")):
        row = json.loads(p.read_text())
        if row.get("mode") != "findings":
            continue
        for f in row["findings"]:
            if f.get("matches") == [] and severity_of(f) in CHECKER_SEVERITY_KEPT:
                by_doc[row["doc"]].append({"fid": f"{row['cell']}#{f['n']}", "quote": f.get("quote"), "problem": f.get("problem")})
    return by_doc


def cluster(matches: Path, out: Path) -> None:
    by_doc = unmatched(matches)
    docs = sorted(by_doc)

    def cell(i, log):
        doc = docs[i]
        fs = by_doc[doc]
        listing = "\n".join(f"{k + 1}. quote: \"{str(f['quote'])[:250]}\" | problem: {str(f['problem'])[:400]}" for k, f in enumerate(fs))
        prompt = ("Below are reviewer findings about one research paper, from several reviewers. Group the findings that point to "
                  "the same statement and state the same defect; a finding that matches no other forms its own group. Return only "
                  "JSON: a list of objects {\"members\": [<finding numbers>], \"summary\": <one sentence>}, covering every finding "
                  "exactly once.\n\nFindings:\n" + listing)
        r = ask("sonnet", prompt, log, f"cluster_{doc}")
        parsed = parse_json(r["text"]) if r["ok"] else None
        clusters, seen = [], set()
        if isinstance(parsed, list):
            for k, c in enumerate(parsed):
                members = [m for m in (c.get("members") or []) if isinstance(m, int) and 1 <= m <= len(fs) and m not in seen]
                seen |= set(members)
                if members:
                    clusters.append({"cid": f"{doc}-K{k + 1:03d}", "members": [fs[m - 1]["fid"] for m in members],
                                     "summary": c.get("summary", "")})
        for k, f in enumerate(fs, 1):          # findings the clusterer dropped become singletons
            if k not in seen:
                clusters.append({"cid": f"{doc}-S{k:03d}", "members": [f["fid"]], "summary": str(f["problem"])[:200]})
        (out / f"clusters_{doc}.json").write_text(json.dumps({"doc": doc, "findings": fs, "clusters": clusters,
                                                              "parsed": isinstance(parsed, list)}, ensure_ascii=False, indent=1))
        return {"cell": f"cluster_{doc}", "status": "ok" if isinstance(parsed, list) else "unparsed", "usd": r["usd"]}
    rr.batch("cluster", out, [(i,) for i in range(len(docs))], cell)


def adjudicate(clusters_dir: Path, out: Path) -> None:
    files = sorted(clusters_dir.glob("clusters_*.json"))
    jobs = [(json.loads(p.read_text()), judge) for p in files for judge in ("opus", "gpt")]

    def cell(i, log):
        data, judge = jobs[i]
        doc = data["doc"]
        fmap = {f["fid"]: f for f in data["findings"]}
        listing = []
        for c in data["clusters"]:
            ex = [fmap[m] for m in c["members"][:3]]
            listing.append(f"{c['cid']}: " + " || ".join(f"quote: \"{str(e['quote'])[:200]}\" problem: {str(e['problem'])[:300]}"
                                                        for e in ex))
        prompt = ("You are checking candidate errors that reviewers reported in the research paper below. For each candidate, decide "
                  "whether it is a real error in this document: a false, inconsistent or unsupported statement, or a wrong number. "
                  "A matter of taste, a request for more detail, or a misreading by the reviewer is not an error. If the question "
                  "cannot be settled from the document, answer \"uncertain\". For each \"yes\", also code it with the codebook. "
                  "Return only a JSON list of objects {\"cid\": ..., \"verdict\": \"yes\"|\"no\"|\"uncertain\", \"class\": ..., "
                  "\"severity\": ..., \"reason\": <one sentence>}.\n\n" + CODEBOOK + "\n\nCandidates:\n" + "\n".join(listing) +
                  "\n\n=== PAPER (LaTeX source) ===\n" + rr.document(FROZEN, doc))
        r = ask(judge, prompt, log, f"adj_{doc}_{judge}")
        parsed = parse_json(r["text"]) if r["ok"] else None
        (out / f"adj_{doc}_{judge}.json").write_text(json.dumps({"doc": doc, "judge": judge, "verdicts": parsed,
                                                                 "raw_text": r["text"]}, ensure_ascii=False, indent=1))
        return {"cell": f"adj_{doc}_{judge}", "status": "ok" if isinstance(parsed, list) else "unparsed", "usd": r["usd"]}
    rr.batch("adjud", out, [(i,) for i in range(len(jobs))], cell)


# ---------------------------------------------------------------------------------------------------------------- captures
def captures(matches: Path, clusters_dir: Path, adjudication: Path, out: Path) -> None:
    ref = reference()
    docs_all = ["P1", "PS", "P2", "P3", "P4", "P6"]
    occ = defaultdict(lambda: {"caught": set(), "findings": 0, "true_findings": 0, "docs": set()})
    # historical occasions: H1 = the JUDGe reviewer (PS only), H2 = the audit of 5 October (everything else in the set)
    for r in ref:
        name = "H1" if r["source"].startswith("JUDGe") else "H2"
        occ[name]["caught"].add(r["id"])
        occ[name]["docs"] |= {"PS"} if name == "H1" else set(docs_all)
    verdict = {}
    for p in sorted(adjudication.glob("adj_*_opus.json")):
        a = json.loads(p.read_text())
        b_path = p.with_name(p.name.replace("_opus", "_gpt"))
        b = json.loads(b_path.read_text()) if b_path.exists() else {"verdicts": []}
        va = {v["cid"]: v for v in (a["verdicts"] or []) if isinstance(v, dict) and "cid" in v}
        vb = {v["cid"]: v for v in (b["verdicts"] or []) if isinstance(v, dict) and "cid" in v}
        for cid in set(va) | set(vb):
            x, y = va.get(cid, {}).get("verdict"), vb.get(cid, {}).get("verdict")
            verdict[cid] = {"new_item": x == "yes" and y == "yes", "agree": x == y, "a": x, "b": y,
                            "class": va.get(cid, {}).get("class"), "severity": va.get(cid, {}).get("severity")}
    member_of = {}
    added = []
    for p in sorted(clusters_dir.glob("clusters_*.json")):
        data = json.loads(p.read_text())
        for c in data["clusters"]:
            v = verdict.get(c["cid"])
            for m in c["members"]:
                member_of[m] = c["cid"]
            if v and v["new_item"]:
                added.append({"id": f"N-{c['cid']}", "doc": data["doc"], "class": v["class"], "severity": v["severity"],
                              "primary": True, "summary": c["summary"]})
    added_ids = {a["id"] for a in added}
    for p in sorted(matches.rglob("c[1-4]_*.json")):
        row = json.loads(p.read_text())
        o = occ[row["occasion"]]
        o["docs"].add(row["doc"])
        if row.get("mode") == "findings":
            for f in row["findings"]:
                ids = f.get("matches") or []
                o["caught"] |= set(ids)
                counted = row["occasion"] in ("C3", "C4") or severity_of(f) in CHECKER_SEVERITY_KEPT
                if not counted:
                    continue
                o["findings"] += 1
                cid = member_of.get(f"{row['cell']}#{f['n']}")
                if ids:
                    o["true_findings"] += 1
                elif cid and f"N-{cid}" in added_ids:
                    o["caught"].add(f"N-{cid}")
                    o["true_findings"] += 1
        elif row.get("mode") == "free_text":
            o["caught"] |= set(row.get("matches") or [])
    payload = {"occasions": {k: {"caught": sorted(v["caught"]), "findings": v["findings"], "true_findings": v["true_findings"],
                                 "docs": sorted(v["docs"])} for k, v in occ.items()},
               "added_items": added, "adjudication": {"n_clusters_judged": len(verdict),
                                                     "agreement": (sum(v["agree"] for v in verdict.values()) / len(verdict))
                                                     if verdict else None}}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    print(json.dumps({k: len(v["caught"]) for k, v in payload["occasions"].items()}))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["code-b", "make-validation", "validate-matcher", "match", "refill", "fill", "cluster",
                                     "adjudicate", "captures"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--validation", type=Path)
    ap.add_argument("--cells", type=Path, nargs="*")
    ap.add_argument("--matches", type=Path)
    ap.add_argument("--clusters", type=Path)
    ap.add_argument("--adjudication", type=Path)
    ap.add_argument("--label", default="")
    ap.add_argument("--ceiling", type=float)
    a = ap.parse_args()
    out = a.out.resolve()
    if a.step == "code-b":
        code_b(out)
    elif a.step == "make-validation":
        make_validation(out)
    elif a.step == "validate-matcher":
        validate_matcher(a.validation.resolve(), out)
    elif a.step == "match":
        match_cells([c.resolve() for c in a.cells], out, a.label, a.ceiling)
    elif a.step == "refill":
        refill(a.matches.resolve(), out)
    elif a.step == "fill":
        fill_undecided(a.matches.resolve(), out)
    elif a.step == "cluster":
        cluster(a.matches.resolve(), out)
    elif a.step == "adjudicate":
        adjudicate(a.clusters.resolve(), out)
    else:
        captures(a.matches.resolve(), a.clusters.resolve(), a.adjudication.resolve(), out)


if __name__ == "__main__":
    main()
