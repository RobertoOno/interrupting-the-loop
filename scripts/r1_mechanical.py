#!/usr/bin/env python3
"""R1 mechanical checks, frozen before they see the documents (docs/R1_REPLAY_CHECAGENS_PRE_REGISTRO_V0.md §6).

    python scripts/r1_mechanical.py c3 --frozen runs/r1/frozen --out runs/r1/c3     # numbers in the body vs the paper's tables
    python scripts/r1_mechanical.py c4 --frozen runs/r1/frozen --out runs/r1/c4     # bibliography vs arXiv and Crossref

C3 is document-internal. The body is the text outside table/tabular environments and before \\appendix; the reference numbers are
every decimal or percentage inside those environments or after \\appendix. A body number with d decimals is found when some
reference number agrees with it at d decimals (signs ignored). Each body line with a number not found becomes one finding.

C4 resolves every bibliography entry that carries an arXiv identifier or a DOI, and flags a title that does not match, an author
surname that is not among the record's authors, or an arXiv primary class that differs from the one the entry states. Network failures are recorded
as such, never as findings.

The output is the common findings format of r1_replay.py (one JSON per document).
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

DOCS = ["P1", "PS", "P2", "P3", "P4", "P6"]
NUMBER = re.compile(r"(?<![\w.\\])[+\-−]?\d+\.\d+(?![\w.])|(?<![\w.])\d+(?:\.\d+)?\s*\\%")
SKIP_CMDS = re.compile(r"\\(?:cite[tp]?|ref|label|eqref|url|href|includegraphics|input|citep|citet)\*?(?:\[[^\]]*\])?\{[^}]*\}")


def blank_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.split("\n"))


def split_body(lines: list[str]) -> tuple[list[tuple[int, str]], list[str]]:
    """(body lines with their flat line numbers, reference lines): tables and everything after \\appendix are reference."""
    body, ref = [], []
    depth, after_appendix = 0, False
    for n, line in enumerate(lines, 1):
        if re.search(r"\\appendix\b", line):
            after_appendix = True
        opens = len(re.findall(r"\\begin\{(?:table\*?|tabular\*?|longtable)\}", line))
        closes = len(re.findall(r"\\end\{(?:table\*?|tabular\*?|longtable)\}", line))
        in_table = depth > 0 or opens > 0
        depth = max(0, depth + opens - closes)
        (ref.append(line) if (after_appendix or in_table) else body.append((n, line)))
    return body, ref


def numbers(text: str) -> list[str]:
    text = SKIP_CMDS.sub(" ", text)
    return [m.group(0).replace("−", "-").replace("\\%", "").replace(" ", "") for m in NUMBER.finditer(text)]


def decimals(x: str) -> int:
    return len(x.split(".")[1]) if "." in x else 0


def found(x: str, pool: list[float]) -> bool:
    v, d = abs(float(x)), decimals(x)
    tol = 0.5 * 10 ** (-d) + 1e-12
    return any(abs(abs(p) - v) <= tol for p in pool)


def c3(frozen: Path, doc: str) -> dict:
    lines = blank_comments((frozen / doc / "flat.tex").read_text(encoding="utf-8")).split("\n")
    body, ref = split_body(lines)
    pool = [float(x) for line in ref for x in numbers(line)]
    findings = []
    for n, line in body:
        missing = [x for x in numbers(line) if not found(x, pool)]
        if missing:
            findings.append({"quote": line.strip()[:300], "problem": "number(s) not found in the paper's tables or appendix: "
                             + ", ".join(dict.fromkeys(missing)), "evidence": f"flat line {n}", "severity": "low",
                             "flat_line": n})
    return {"check": "C3", "doc": doc, "status": "ok", "n_reference_numbers": len(pool), "n_findings": len(findings),
            "findings": findings}


# ------------------------------------------------------------------------------------------------------------------- C4
def parse_bib(text: str) -> list[dict]:
    entries = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        start, depth, i = m.end(), 1, m.end()
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[start:i - 1]
        fields = {}
        for f in re.finditer(r"(\w+)\s*=\s*(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}|\"[^\"]*\"|\d+)", body):
            fields[f.group(1).lower()] = f.group(2).strip("{}\"")
        entries.append({"type": m.group(1).lower(), "key": m.group(2), **fields})
    return entries


def arxiv_id(e: dict):
    for k in ("eprint", "arxiv", "journal", "note", "howpublished", "url"):
        m = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", e.get(k, ""))
        if m and (k != "url" or "arxiv" in e.get(k, "").lower()) and (k in ("eprint", "arxiv", "url") or "arxiv" in e.get(k, "").lower()):
            return m.group(1)
    return None


def norm_title(t: str) -> str:
    t = re.sub(r"\\[a-zA-Z]+", " ", t)
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def surname(author_field: str) -> str:
    first = re.split(r"\s+and\s+", author_field.strip())[0]
    first = first.split(",")[0] if "," in first else first.split()[-1] if first.split() else ""
    return norm_title(first)


def fetch(url: str, tries: int = 3) -> bytes:
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "creative-machine-r1/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # transport only; retried, never turned into a finding
            last = e
            time.sleep(3 * (k + 1))
    raise last


def arxiv_meta(ids: list[str]) -> dict:
    out = {}
    ns = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        xml = fetch("http://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": ",".join(chunk),
                                                                                   "max_results": len(chunk)}))
        root = ET.fromstring(xml)
        for e in root.findall("a:entry", ns):
            aid = re.search(r"(\d{4}\.\d{4,5})", e.findtext("a:id", "", ns)).group(1)
            prim = e.find("arxiv:primary_category", ns)
            out[aid] = {"title": e.findtext("a:title", "", ns), "authors": [a.findtext("a:name", "", ns)
                                                                          for a in e.findall("a:author", ns)],
                        "primary": prim.get("term") if prim is not None else None}
        time.sleep(3)
    return out


def crossref_meta(doi: str):
    data = json.loads(fetch("https://api.crossref.org/works/" + urllib.parse.quote(doi)))["message"]
    return {"title": (data.get("title") or [""])[0], "authors": [a.get("family", "") for a in data.get("author", [])]}


def c4(frozen: Path, doc: str) -> dict:
    entries = []
    for b in sorted((frozen / doc / "src").rglob("*.bib")):
        entries += parse_bib(b.read_text(encoding="utf-8", errors="replace"))
    ax = {e["key"]: arxiv_id(e) for e in entries}
    errors, findings = [], []
    try:
        meta = arxiv_meta(sorted({v for v in ax.values() if v}))
    except Exception as e:
        meta, errors = {}, [f"arXiv API: {type(e).__name__}: {e}"]
    for e in entries:
        problems, ref = [], None
        if ax[e["key"]]:
            ref = meta.get(ax[e["key"]])
            if ref is None:
                problems.append(f"arXiv:{ax[e['key']]} not returned by the arXiv API")
        elif e.get("doi"):
            try:
                ref = crossref_meta(e["doi"])
            except Exception as ex:
                errors.append(f"Crossref {e['doi']}: {type(ex).__name__}")
                continue
        else:
            continue
        if ref:
            ratio = difflib.SequenceMatcher(None, norm_title(e.get("title", "")), norm_title(ref["title"])).ratio()
            if ratio < 0.85:
                problems.append(f"title differs from the record ({ratio:.2f}): '{ref['title'][:120]}'")
            if e.get("author") and ref["authors"]:
                record = {norm_title(a.split()[-1]) if " " in a.strip() else norm_title(a) for a in ref["authors"]}
                listed = [surname(a) for a in re.split(r"\s+and\s+", e["author"]) if a.strip().lower() not in ("others", "et al.")]
                absent = [s for s in listed if s and s not in record]
                if absent:
                    problems.append(f"author surname(s) not in the record: {', '.join(absent)} (record: "
                                    f"{', '.join(ref['authors'][:6])}{', ...' if len(ref['authors']) > 6 else ''})")
            if ref.get("primary") and e.get("primaryclass") and e["primaryclass"].strip() != ref["primary"]:
                problems.append(f"primaryClass {e['primaryclass']} vs arXiv {ref['primary']}")
        if problems:
            findings.append({"quote": f"@{e['type']}{{{e['key']}, title = {{{e.get('title', '')[:120]}}}",
                             "problem": "; ".join(problems), "evidence": "arXiv API / Crossref", "severity": "low",
                             "bib_key": e["key"]})
    return {"check": "C4", "doc": doc, "status": "ok" if not errors else "partial", "network_errors": errors,
            "n_entries": len(entries), "n_resolvable": sum(1 for e in entries if ax[e["key"]] or e.get("doi")),
            "n_findings": len(findings), "findings": findings}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("check", choices=["c3", "c4"])
    ap.add_argument("--frozen", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--docs", nargs="*", default=DOCS)
    a = ap.parse_args()
    out = a.out.resolve()
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} is not empty; each R1 check runs once, into a fresh directory")
    out.mkdir(parents=True, exist_ok=True)
    fn = c3 if a.check == "c3" else c4
    for doc in a.docs:
        res = fn(a.frozen.resolve(), doc)
        (out / f"{a.check}_{doc}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
        print(doc, res["status"], res["n_findings"], flush=True)


if __name__ == "__main__":
    main()
