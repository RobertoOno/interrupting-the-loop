#!/usr/bin/env python3
"""Build the Zenodo deposit of the errata report (paper 7) into a fresh directory outside the repository.

    python3 scripts/r1_build_deposit.py --out ~/wrk/creative-machine-data/deposits/paper7_v1

The repository's archives stay sealed and byte-exact; the deposit gets copies. A copy that carries a private detail gets it
redacted, and REDACTIONS.json lists every such file with the SHA-256 of the sealed original and of the deposited copy:
- the per-rater statistics of paper 1 v1 (each rater's mean and correlations, which with the raters' profiles in order identified
  each rater) and the payment values, which the corrected paper 1 of 5 October gives as ranges and without values; in the frozen
  paper 1 and in the checker responses that quote them, with the files derived from those responses;
- a colleague's name in two of the 5 October audit documents;
- the workshop reviewer's anonymous OpenReview handle, wherever it is deposited;
- a private term used as a scan pattern in scripts/r1_freeze.py (read from a private file in the deposited copy).
Redactions keep every line break, so line references into the frozen documents stay valid. The private values come from the
public mirror's replacement rules, the reference set and r1_freeze.py at build time; none is written in this script.
The records-level audit's repository snapshots are not deposited (they hold the private notebook); their manifest is.
The build stops if any deposited file still matches a rule of the public mirror, the private term, a per-rater value, a payment
value, the reviewer's handle or a credential pattern. Nothing private is printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ["P1", "PS", "P2", "P3", "P4", "P6"]
RULES = Path.home() / ".config/creative-machine/publish/rules/replacements.txt"
BINARY = {".pdf", ".png", ".xlsx"}

# Hashes fixed before the replay (docs/R1_REPLAY_CHECAGENS_PRE_REGISTRO_V1.md, "Hashes", amendments 1 and 3).
PREREG = {
    "scripts/r1_freeze.py": [("pre-registration v1", "f1f35de4f48d64d1e15927f7f4f58c5e1ee7558be6ef16671bec39f9bf6cb952")],
    "scripts/r1_reference_set.py": [("pre-registration v1", "b46ebb9a0969ed3a3516218897dcf841f00c2b2ed5a331720e8128712a073a43")],
    "scripts/r1_replay.py": [("pre-registration v1", "4c4dbd79909deca03117d6c013e775ac291f5c8fc1f72812b90a2b5a260d17ab"),
                             ("amendment 1", "69eab61e94626efb06d8c4cd909f87c76b4d25920fd230083ab3f02e5b943cda")],
    "scripts/r1_mechanical.py": [("pre-registration v1", "69c6a33c14adf4a380936aba9819b8b77a2d159b0a1112a15875f8bd23595a39")],
    "scripts/r1_judging.py": [("pre-registration v1", "1fd27241934efac7dd3f6f788cf8a4ab4c8934ff150faf074e7a1b36f2368c6e"),
                              ("amendment 3", "a0af920f6f3ab8903c08553ef5942c022a865386a95b4b68c52dfe3a94b11758")],
    "scripts/r1_analysis.py": [("pre-registration v1", "b80159f95f36c72f3e3f25d88e7b00fa602c9064983dffa78769747f13306cd1")],
    "docs/r1/reference_set_v1.jsonl": [("pre-registration v1", "b6adedc92811ac9806d951ed6632fd2412b9636da3304f79741442c24b6a688f")],
    "runs/r1/frozen/MANIFEST.sha256": [("pre-registration v1", "6a0eaa0ea120ec36002492c850bb7103b0626148ac4dbe6e5ef4bc1bae321c09")],
}
AUDITS = "correcoes_2026-10-05"           # the five per-paper audits of 5 October, which the reference set cites by item
RECORDS = ["R1_REPLAY_CHECAGENS_PRE_REGISTRO_V0.md", "R1_REPLAY_CHECAGENS_PRE_REGISTRO_V1.md", "R1_RESULTADOS.md",
           "R2_REGRAS_DE_ESCRITA_PRE_REGISTRO_V0.md", "R2_PILOTO_RESULTADOS.md", "CORRECOES_PAPERS_2026-10-05.md",
           "LITERATURA_VERIFICACAO_SEM_LASTRO_2026-10-06.md", "LITERATURA_R2_2026-10-06.md"]

# The per-rater values of the first human round and the payment values are read from the frozen paper 1 by the shape of its
# sentences, so no value is written in this script; the corrected paper 1 gives them as ranges and without values.
SEP = r"(?:,\s*|,?\s+and\s+)"
VALUES = "[three per-rater values redacted]"


def rater_patterns(frozen_p1: str) -> tuple[list[tuple[str, str]], re.Pattern]:
    """Substitutions for every form a quote of the per-rater values takes (the LaTeX of the paper, plain text in checker responses),
    and a pattern for any value left over."""
    means = re.search(r"mean surprise (\d\.\d), (\d\.\d) and (\d\.\d)\)", frozen_p1)
    rho = re.search(r"Spearman \$\\rho=\+(0\.\d\d)\$, \$\+(0\.\d\d)\$, \$\+(0\.\d\d)\$", frozen_p1)
    coh = re.search(r"and on coherence \(\$\+(0\.\d\d)\$, \$\+(0\.\d\d)\$, \$\+(0\.\d\d)\$\)", frozen_p1)
    pay = re.search(r"Compensation was R\\\$(\d+)--(\d+) per pack \(roughly\s+US\\\$(\d+)--(\d+)\)", frozen_p1)
    pairs = re.search(r"pairwise Spearman on surprise (0\.\d\d), (0\.\d\d), (0\.\d\d),", frozen_p1)
    if not (means and rho and coh and pay and pairs):
        raise SystemExit("the per-rater passages were not found in the frozen paper 1")
    e = re.escape
    subs = [
        (e(rho.group(0)), "Spearman " + VALUES),
        (e(coh.group(0)), "and on coherence (" + VALUES + ")"),
        (r"Compensation was R\\\$" + e(pay.group(1)) + "--" + e(pay.group(2)) + r" per pack \(roughly\s+US\\\$" + e(pay.group(3)) +
         "--" + e(pay.group(4)) + r"\)", "Compensation [values redacted, as in the corrected paper 1]"),
    ]
    subs.append((e(pairs.group(0)), "pairwise Spearman on surprise " + VALUES + ","))
    triples = [means.groups(), rho.groups(), coh.groups(), pairs.groups()]
    for a, b, c in triples:
        plus = r"\+?" if a.startswith("0.") else ""
        subs.append((plus + e(a) + SEP + plus + e(b) + SEP + plus + e(c), VALUES))
    left = [e(a) + r"[^0-9]{1,14}" + e(b) + r"[^0-9]{1,14}" + e(c) for a, b, c in triples]
    left += [e(pay.group(1)) + r"\s*(?:--|–|—|-|to)\s*" + e(pay.group(2)), e(pay.group(3)) + r"\s*(?:--|–|—|-|to)\s*" + e(pay.group(4)),
             r"R\\*\$\s*\d"]
    return subs, re.compile("|".join(left))


CREDENTIAL = re.compile(r"(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}"
                        r"|sk-[A-Za-z0-9_-]{30,}|xox[baprs]-[A-Za-z0-9-]{20,}|rpa_[A-Za-z0-9]{20,})")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sealed(manifest: Path) -> dict[str, str]:
    out = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if "  " in line:
            h, name = line.split("  ", 1)
            out[name.removeprefix("./")] = h
    return out


def load_rules(path: Path) -> list[tuple[str, str, object]]:
    """The public mirror's rules, in git filter-repo --replace-text format (as scripts/r1_freeze.py reads them)."""
    rules = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        lhs, sep, repl = raw.partition("==>")
        repl = repl if sep else "***REMOVED***"
        if lhs.startswith("regex:"):
            rules.append(("regex", repl, re.compile(lhs[len("regex:"):])))
        elif lhs.startswith("glob:"):
            continue
        else:
            rules.append(("literal", repl, lhs[len("literal:"):] if lhs.startswith("literal:") else lhs))
    return rules


def private_term(freeze_source: str) -> tuple[str, re.Pattern]:
    """The private term r1_freeze.py scrubs, taken from its source, and a pattern for mentions of it (a match inside a longer
    base64-like run, as in the signatures of the raw responses, is not a mention)."""
    m = re.search(r're\.sub\(r"\(\?i\)(\w+)", "org", text\)', freeze_source)
    if not m:
        raise SystemExit("could not find the scrub term in r1_freeze.py")
    return m.group(1), re.compile(r"(?i)(?<![A-Za-z0-9+/])" + re.escape(m.group(1)) + r"(?![A-Za-z0-9+/])")


def check_json(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        json.loads(text)
    elif path.suffix == ".jsonl":
        for line in text.splitlines():
            if line.strip():
                json.loads(line)


def redact(path: Path, out: Path, subs, log: list, original_sha: str, why: str) -> None:
    text = path.read_text(encoding="utf-8")
    lines_before = text.count("\n")
    total = 0
    for pat, rep in subs:
        text, n = re.subn(pat, lambda m, rep=rep: rep + "\n" * m.group(0).count("\n"), text)
        total += n
    if total == 0:
        raise SystemExit(f"redaction found nothing to redact in {path.relative_to(out)}")
    if text.count("\n") != lines_before:
        raise SystemExit(f"redaction changed the line count of {path.relative_to(out)}")
    path.write_text(text, encoding="utf-8")
    check_json(path)
    log.append({"file": str(path.relative_to(out)), "replacements": total, "why": why,
                "sha256_sealed_original": original_sha, "sha256_deposited": sha(path)})


def redact_freeze(path: Path, out: Path, term: str, log: list, original_sha: str) -> None:
    """Replace the private scan term in r1_freeze.py by a pattern read from a private file."""
    text = path.read_text(encoding="utf-8")
    literal = 'r"(?i)' + term + '"'
    n = text.count(literal)
    text = text.replace(literal, "PRIVATE_PATTERN")
    anchor = "from pathlib import Path\n"
    if n == 0 or anchor not in text:
        raise SystemExit("r1_freeze.py: scan term or anchor not found")
    text = text.replace(anchor, anchor + "\n# A private term the scrub replaces; read from a file that is not deposited.\n"
                        'PRIVATE_PATTERN = r"(?i)" + (Path.home() / ".config/creative-machine/private_term.txt").read_text().strip()\n', 1)
    path.write_text(text, encoding="utf-8")
    log.append({"file": str(path.relative_to(out)), "replacements": n,
                "why": "a private term used as a scan pattern (read from a private file in the deposited copy)",
                "sha256_sealed_original": original_sha, "sha256_deposited": sha(path)})


def text_of(p: Path) -> str:
    if p.suffix == ".xlsx":
        with zipfile.ZipFile(p) as z:
            return "\n".join(z.read(n).decode("utf-8", errors="replace") for n in z.namelist() if n.endswith(".xml"))
    return p.read_text(encoding="utf-8", errors="replace")


def problems_in(out: Path, rules, term: re.Pattern, leftover: re.Pattern) -> list[tuple[str, str]]:
    problems = []
    for p in sorted(out.rglob("*")):
        if not p.is_file() or p.suffix in BINARY - {".xlsx"}:
            continue
        t = text_of(p)
        low = t.lower()
        name = str(p.relative_to(out))
        if leftover.search(t):
            problems.append((name, "per-rater value or payment"))
        if term.search(t):
            problems.append((name, "private term"))
        if CREDENTIAL.search(t):
            problems.append((name, "credential pattern"))
        for kind, repl, pat in rules:
            if kind == "regex" and any(m.group(0) != repl for m in pat.finditer(t)):
                problems.append((name, "public mirror rule (regex)"))
            elif kind == "literal" and pat and pat.lower() in low:
                problems.append((name, "public mirror rule (literal)"))
    return problems


README = """# Errata in AI-executed research: deposit of the report and its evidence

This deposit accompanies the report *{title}* (Roberto I. Ono Filho, independent researcher, {date}).
Every number in the report is a macro in `report/numbers.tex`, generated by `scripts/r1_report_numbers.py` from the files below.

## Where things are

| deposit folder | repository path | what it holds |
|---|---|---|
| `report/` | `paper7/` | the report (PDF and LaTeX sources) |
| `evidence/r1_replay/` | `docs/r1/evidence_v1/` | the blind replay of the checks: raw responses with the size of each request, parsed findings, matches, clusters, both adjudicators' verdicts, captures, analyses; `MANIFEST.sha256` is the sealed manifest of the repository archive |
| `evidence/reference_set_v1.jsonl` | `docs/r1/reference_set_v1.jsonl` | the audited errata (86 items, 80 primary), as frozen before any model call |
| `evidence/r2_pilots/` | `docs/r2/pilot_evidence_v1/` | the pilot writes on synthetic records |
| `frozen/<doc>/` | `runs/r1/frozen/<doc>/` | the six documents as the checks saw them: flattened LaTeX, line map to the sources, bibliography, metadata |
| `frozen/MANIFEST_sealed.sha256` | `runs/r1/frozen/MANIFEST.sha256` | the sealed manifest of the frozen corpus, which also lists the snapshots of the records-level audit (not deposited: they hold the private notebook) |
| `records/` | `docs/` | the pre-registrations (R1 v0 and v1 with its amendments, R2 v0), the results notes, the 5 October audit (consolidated, and in `correcoes_2026-10-05/` the five per-paper audits whose items the reference set's `source` field cites) and the literature notes, in Portuguese as kept |
| `scripts/` | `scripts/`, `tests/`, `src/creative_machine/aws_daily_budget.py` | every script of the replay, the pilots and the report, with their synthetic tests |
| `review/round0_2026-10-08/` | `docs/r1/report_review_v1/` | the first reviews of an earlier draft |
| `review/rounds_2026-10-15_onward/` | `docs/r1/report_review_v2/` | the review rounds of this report, the post hoc coding of each erratum's status at its freeze (`freeze_status/`) and the notebook sizes (`notebook_size.json`) |

The scripts read the repository paths in the second column.

## Hashes fixed before the replay, and final hashes

| file | fixed before the replay | final (repository) | deposited copy |
|---|---|---|---|
{hash_rows}

`scripts/r1_judging.py` changed after amendment 3: the label and cost ceiling of the parallel matching parts (amendment 5) and the
re-read and fill of the matcher's missing decisions (amendment 6), committed with the results. The other scripts of the replay are
as fixed before it, except for the redaction described below. Every deposited file is in `MANIFEST.sha256`.

## Redactions

The repository's archives stay sealed; the deposit holds copies, and {n_red} copies differ from their sealed originals. Each is in
`REDACTIONS.json` with the SHA-256 of the sealed original and of the deposited copy:
- the per-rater statistics of paper 1 v1 (each rater's mean and correlations, which with the raters' profiles in order identified
  each rater) and the payment values, which the corrected paper 1 of 5 October gives as ranges and without values: in the frozen
  paper 1 and in the {n_ev} evidence files that quote some of them (checker responses and the files derived from them);
- a colleague's name in two of the 5 October audit documents (the consolidated one and the audit of paper 2);
- the workshop reviewer's anonymous OpenReview handle, in the {n_handle} files that carry it (the reference set, the script that builds
  it, the audit of paper 1 and the short paper, and one review round): the reference set's `source` reads `JUDGe reviewer [handle],
  item k`;
- a private term used as a scan pattern in `scripts/r1_freeze.py`, which the deposited copy reads from a private file.

Redactions keep every line break, so line references into the frozen documents hold. Requests rebuilt from the redacted paper 1
differ in size from those the checks received (the raw logs give each request's size). The `MANIFEST.sha256` inside
`evidence/r1_replay/` and the sealed corpus manifest are deposited as sealed, so they list the hashes of the originals. Individual
human ratings from the series are not released.

## Records with a wording the report corrects

Sealed files are deposited as they were. Where one of them says something the report corrects, the report is right:
- `evidence/r1_replay/hand_check.json` and `records/R1_RESULTADOS.md` say the 30 matches were checked "by hand" ("à mão"): they
  were checked one by one by the assistant (Claude Opus 5.5), not by a person.
- `scripts/r1_strict_recheck.py` dates the strict re-check to "the fifth review of the report": in the report's own numbering it was
  prompted by the eighth round (round 7 in the archive), as `review/rounds_2026-10-15_onward/strict_recheck/PROTOCOL.md` says.
- `evidence/r1_replay/README.md` carries two dated corrections of 16 October on the checker responses that quote per-rater data.

## Review rounds

Appendix A of the report counts the rounds from the first reviews of 8 October: `review/round0_2026-10-08/` is its first round, and
the folders `round1_*` to `round{last}_*` in `review/rounds_2026-10-15_onward/` are its second to {last_ordinal} rounds.
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this script's repository)")
    a = ap.parse_args()
    root = a.root.resolve()
    out = a.out
    if out.exists():
        raise SystemExit(f"{out} exists; the deposit is built once, into a fresh directory")
    out.mkdir(parents=True)
    log: list = []
    rules = load_rules(RULES)
    freeze_src = (root / "scripts/r1_freeze.py").read_text(encoding="utf-8")
    term, mention = private_term(freeze_src)
    colleague = [pat for kind, repl, pat in rules if kind == "literal" and repl.strip() == "the external reviewer"]
    if not colleague:
        raise SystemExit("no public mirror rule for the colleague's name")
    sealed_r1 = sealed(root / "docs/r1/evidence_v1/MANIFEST.sha256")
    sealed_frozen = sealed(root / "runs/r1/frozen/MANIFEST.sha256")
    rater_stats, leftover = rater_patterns((root / "runs/r1/frozen/P1/flat.tex").read_text(encoding="utf-8"))

    # 1. the report
    rep = out / "report"
    rep.mkdir()
    for f in ("main.pdf", "main.tex", "numbers.tex", "references.bib"):
        shutil.copy2(root / "paper7" / f, rep / f)

    # 2. evidence: the replay (R1) with its quotes of per-rater values redacted, the reference set, the pilots (R2)
    ev = out / "evidence"
    shutil.copytree(root / "docs/r1/evidence_v1", ev / "r1_replay", symlinks=False)
    n_ev = 0
    for p in sorted((ev / "r1_replay").rglob("*")):
        if p.is_file() and p.suffix not in BINARY and leftover.search(p.read_text(encoding="utf-8", errors="replace")):
            rel = str(p.relative_to(ev / "r1_replay"))
            redact(p, out, rater_stats, log, sealed_r1[rel],
                   "quotes per-rater statistics of paper 1 v1 (a checker response, or a file derived from one)")
            n_ev += 1
    shutil.copy2(root / "docs/r1/reference_set_v1.jsonl", ev / "reference_set_v1.jsonl")
    shutil.copytree(root / "docs/r2/pilot_evidence_v1", ev / "r2_pilots", symlinks=False)

    # 3. the frozen versions the checks saw; the snapshots stay private, their manifest is deposited
    fz = out / "frozen"
    for d in DOCS:
        (fz / d).mkdir(parents=True)
        for f in ("flat.tex", "linemap.json", "meta.json"):
            shutil.copy2(root / f"runs/r1/frozen/{d}/{f}", fz / d / f)
        bibs = sorted((root / f"runs/r1/frozen/{d}/src").rglob("*.bib"))
        if len({b.name for b in bibs}) != len(bibs):
            raise SystemExit(f"{d}: two bibliographies with the same name")
        for b in bibs:
            shutil.copy2(b, fz / d / b.name)
    redact(fz / "P1/flat.tex", out, rater_stats, log, sealed_frozen["P1/flat.tex"],
           "per-rater statistics and payment values of paper 1 v1, given as ranges and without values in its corrected version")
    shutil.copy2(root / "runs/r1/frozen/MANIFEST.sha256", fz / "MANIFEST_sealed.sha256")

    # 4. records
    rec = out / "records"
    rec.mkdir()
    for f in RECORDS:
        shutil.copy2(root / "docs" / f, rec / f)
    (rec / AUDITS).mkdir()
    for f in sorted((root / "docs" / AUDITS).glob("*.md")):
        shutil.copy2(f, rec / AUDITS / f.name)
    col_subs = [(r"\b" + re.escape(c) + r"\b", "[colega]") for c in colleague]
    n_col = 0
    for f in sorted(rec.rglob("*.md")):
        if any(re.search(pat, f.read_text(encoding="utf-8")) for pat, _ in col_subs):
            redact(f, out, col_subs, log, sha(root / "docs" / f.relative_to(rec)), "a colleague's first name")
            n_col += 1
    if n_col != 2:
        raise SystemExit(f"expected the colleague's name in two audit documents, found it in {n_col}")

    # 5. scripts and tests
    sc = out / "scripts"
    (sc / "tests").mkdir(parents=True)
    (sc / "src").mkdir()
    scripts = sorted(root.glob("scripts/r1_*.py")) + sorted(root.glob("scripts/r2_*.py"))
    for p in scripts:
        shutil.copy2(p, sc / p.name)
    for p in sorted(root.glob("tests/test_r1_*.py")) + sorted(root.glob("tests/test_r2_*.py")):
        shutil.copy2(p, sc / "tests" / p.name)
    shutil.copy2(root / "src/creative_machine/aws_daily_budget.py", sc / "src/aws_daily_budget.py")
    redact_freeze(sc / "r1_freeze.py", out, term, log, sha(root / "scripts/r1_freeze.py"))

    # 6. the review rounds of this report
    rv = out / "review"
    shutil.copytree(root / "docs/r1/report_review_v1", rv / "round0_2026-10-08", symlinks=False)
    shutil.copytree(root / "docs/r1/report_review_v2", rv / "rounds_2026-10-15_onward", symlinks=False)

    # the workshop reviewer's anonymous OpenReview handle, from the reference set's source field
    handles = sorted({json.loads(l)["source"].split()[2].rstrip(",")
                      for l in (root / "docs/r1/reference_set_v1.jsonl").read_text(encoding="utf-8").splitlines()
                      if l.strip() and json.loads(l)["source"].startswith("JUDGe reviewer ")})
    if len(handles) != 1:
        raise SystemExit("expected one workshop reviewer handle in the reference set")
    handle_re = re.compile(r"\b" + re.escape(handles[0]) + r"\b")
    origin = {out / "evidence/reference_set_v1.jsonl": root / "docs/r1/reference_set_v1.jsonl",
              sc / "r1_reference_set.py": root / "scripts/r1_reference_set.py"}
    n_handle = 0
    for p in sorted(out.rglob("*")):
        if not p.is_file() or p.suffix in BINARY or not handle_re.search(p.read_text(encoding="utf-8", errors="replace")):
            continue
        rel = p.relative_to(out)
        if any(x["file"] == str(rel) for x in log):
            raise SystemExit(f"{rel} would be redacted twice")
        if p in origin:
            src = origin[p]
        elif rel.parts[0] == "records":
            src = root / "docs" / rel.relative_to("records")
        elif rel.parts[:2] == ("review", "rounds_2026-10-15_onward"):
            src = root / "docs/r1/report_review_v2" / rel.relative_to("review/rounds_2026-10-15_onward")
        else:
            raise SystemExit(f"unexpected place for the reviewer handle: {rel}")
        if sha(src) != sha(p):
            raise SystemExit(f"{rel} differs from its source before the handle's redaction")
        redact(p, out, [(handle_re.pattern, "[handle]")], log, sha(src), "the workshop reviewer's anonymous OpenReview handle")
        n_handle += 1

    # 7. README with the hashes, redaction log, checks, manifest
    deposited = {f"scripts/{p.name}": sc / p.name for p in scripts}
    deposited["docs/r1/reference_set_v1.jsonl"] = ev / "reference_set_v1.jsonl"
    deposited["runs/r1/frozen/MANIFEST.sha256"] = fz / "MANIFEST_sealed.sha256"
    rows = []
    for rel in sorted(deposited):
        final = sha(root / rel)
        fixed = "; ".join(f"{label}: `{h[:16]}…`" for label, h in PREREG.get(rel, [])) or "(written later)"
        copy = sha(deposited[rel])
        rows.append(f"| `{rel}` | {fixed} | `{final}` | {'same' if copy == final else '`' + copy + '` (redacted)'} |")
    tex = (root / "paper7/main.tex").read_text(encoding="utf-8")
    title = re.search(r"\\title\{(.+?)\}\s*\n", tex, re.S).group(1)
    title = re.sub(r"\\\\|\\thanks\{.*", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    date = re.search(r"\\newcommand\{\\reportdate\}\{([^}]+)\}", tex).group(1)
    last = max(int(m.group(1)) for d in (rv / "rounds_2026-10-15_onward").iterdir() if (m := re.match(r"round(\d+)_", d.name)))
    ordinal = ["second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth",
               "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth", "nineteenth", "twentieth"][last - 1]
    (out / "README.md").write_text(README.format(title=title, date=date, hash_rows="\n".join(rows), n_red=len(log), n_ev=n_ev, n_handle=n_handle,
                                                 last=last, last_ordinal=ordinal), encoding="utf-8")
    (out / "REDACTIONS.json").write_text(json.dumps(log, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    problems = problems_in(out, rules, mention, leftover)
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.suffix not in BINARY and handle_re.search(text_of(p)):
            problems.append((str(p.relative_to(out)), "reviewer handle"))
    lines = [f"{sha(p)}  {p.relative_to(out)}" for p in sorted(out.rglob("*")) if p.is_file() and p != out / "MANIFEST.sha256"]
    (out / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(lines), "redacted_files": len(log), "evidence_files_redacted": n_ev, "problems": problems},
                     indent=1))
    if problems:
        raise SystemExit("privacy check failed; see problems above")


if __name__ == "__main__":
    main()
