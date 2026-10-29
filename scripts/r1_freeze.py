#!/usr/bin/env python3
"""R1: export the frozen pre-audit versions of the six papers, and the records snapshots for the records-level audit (C2).

    python scripts/r1_freeze.py --out runs/r1/frozen                 # documents only
    python scripts/r1_freeze.py --out runs/r1/frozen --snapshots     # plus one records snapshot per document

Per document: the LaTeX sources and the .bib at the frozen commit, a flattened source (\\input resolved) with a line map back to
file:line, and meta.json. MANIFEST.sha256 at the root covers every file written.

A records snapshot holds the text files git tracked at the document's commit, minus reviews, audits, identity and strategy files
(R1_EXCLUDE), scrubbed with the public mirror's replacement rules. The export stops if a rule's source survives the scrub, or if
anything that looks like a credential is found. Nothing under runs/ is ever read. Rule contents are never printed.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

# A private term the scrub replaces; read from a file that is not deposited.
PRIVATE_PATTERN = r"(?i)" + (Path.home() / ".config/creative-machine/private_term.txt").read_text().strip()

ROOT = Path(__file__).resolve().parent.parent

# doc id -> (full commit SHA, paper directory, main file); the commits are fixed in docs/R1_REPLAY_CHECAGENS_PRE_REGISTRO_V0.md §3
DOCS = {
    "P1": ("55345d8baea7fc6daa17313ce202b38ef0a1feb4", "paper", "main.tex"),
    "PS": ("2745b9370011c3700e63e4f9d16f6f0e2c7d8d14", "paper/short/judge2026", "main.tex"),
    "P2": ("e2a79180746da09188ee568b0fe980d0c8fde755", "paper2", "main.tex"),
    "P3": ("403fa55f1ce8a51f69af090ff77d770a1945fe1d", "paper3", "main.tex"),
    "P4": ("c1830d1ce52f4e3b483bb6fd88257069469b675a", "paper4", "main.tex"),
    "P6": ("42d1bec1d9b85cad7fe3a4b942cce457f3bbaf68", "paper6", "main.tex"),
}
RULES = Path.home() / ".config/creative-machine/publish/rules/replacements.txt"
TEXT_EXT = {".md", ".tex", ".bib", ".py", ".txt", ".json", ".jsonl", ".sh", ".yaml", ".yml", ".toml", ".csv", ".cfg", ".ini"}
MAX_FILE_BYTES = 2_000_000
# Reviews and audits stay out (they are other checks), as do identity, strategy and publishing tooling.
R1_EXCLUDE = [
    "runs/*", "docs/reviews/*", "docs/revisor_externo.txt", "docs/parecer_*", "docs/RESPOSTA_PARECER_*", "docs/feddback_*",
    "docs/PLANO_REVISAO_FEEDBACK.md", "docs/correcoes_*", "docs/CORRECOES_*", "docs/funding/*", "docs/MEMORANDO_ESTRATEGIA.md",
    "docs/SUBMISSAO.md", "docs/campo/*", "docs/ESTADO_DO_CAMPO.md", "scripts/publish/*", "docs/blind/*",
]
R1_EXCLUDE_NAME = re.compile(r"(?i)(parecer|revisor|review|feedback|feddback|auditoria|correc)")
CREDENTIAL = re.compile(r"(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}"
                        r"|sk-[A-Za-z0-9_-]{30,}|xox[baprs]-[A-Za-z0-9-]{20,})")
INPUT = re.compile(r"\\(?:input|include)\{([^}]+)\}")


def git(*args: str, binary: bool = False):
    out = subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True)
    return out.stdout if binary else out.stdout.decode("utf-8")


def show(commit: str, path: str) -> str:
    return git("show", f"{commit}:{path}")


def tracked(commit: str, prefix: str = "") -> list[str]:
    args = ["ls-tree", "-r", "--name-only", commit] + (["--", prefix] if prefix else [])
    return [p for p in git(*args).splitlines() if p]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strip_comment(line: str) -> str:
    """The part of a LaTeX line before an unescaped %."""
    m = re.search(r"(?<!\\)%", line)
    return line if m is None else line[:m.start()]


def flatten(commit: str, base: str, rel: str, depth: int = 0) -> list[tuple[str, int, str]]:
    """Lines of `rel` with \\input/\\include resolved recursively, each as (file, line number, text)."""
    if depth > 8:
        raise RuntimeError(f"\\input nesting too deep at {rel}")
    path = f"{base}/{rel}"
    out = []
    for n, line in enumerate(show(commit, path).splitlines(), 1):
        live = strip_comment(line)
        m = INPUT.search(live)
        if m:
            target = m.group(1).strip()
            if not target.endswith(".tex"):
                target += ".tex"
            before, after = live[:m.start()], live[m.end():]
            if before.strip():
                out.append((path, n, before))
            out.extend(flatten(commit, base, target, depth + 1))
            if after.strip():
                out.append((path, n, after))
        else:
            out.append((path, n, line))
    return out


def load_rules(path: Path) -> list[tuple[str, str, object]]:
    """git filter-repo --replace-text rules: 'literal==>repl' or 'regex:pattern==>repl' (repl defaults to ***REMOVED***)."""
    rules = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        lhs, _, repl = raw.partition("==>")
        repl = repl if _ else "***REMOVED***"
        if lhs.startswith("regex:"):
            rules.append(("regex", repl, re.compile(lhs[len("regex:"):])))
        elif lhs.startswith("glob:"):
            rules.append(("regex", repl, re.compile(fnmatch.translate(lhs[len("glob:"):])[:-2])))
        else:
            rules.append(("literal", repl, lhs[len("literal:"):] if lhs.startswith("literal:") else lhs))
    return rules


def scrub(text: str, rules) -> str:
    for kind, repl, pat in rules:
        text = pat.sub(repl, text) if kind == "regex" else text.replace(pat, repl)
    return re.sub(PRIVATE_PATTERN, "org", text)


def survivors(text: str, rules) -> int:
    hits = 0
    for kind, repl, pat in rules:
        if kind == "regex":
            hits += sum(1 for m in pat.finditer(text) if m.group(0) != repl)
        elif pat and pat in text:
            hits += 1
    return hits + len(re.findall(PRIVATE_PATTERN, text))


def excluded(path: str) -> bool:
    if any(fnmatch.fnmatch(path, pat) for pat in R1_EXCLUDE):
        return True
    return bool(R1_EXCLUDE_NAME.search(Path(path).name))


def write(path: Path, data: bytes, manifest: dict, root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    manifest[str(path.relative_to(root))] = sha256(data)


def export_doc(doc: str, out: Path, manifest: dict) -> dict:
    commit, base, main = DOCS[doc]
    d = out / doc
    files = [p for p in tracked(commit, base) if p.endswith((".tex", ".bib"))
             and not (doc == "P1" and p.startswith("paper/short/"))]
    meta_files = {}
    for p in files:
        data = git("show", f"{commit}:{p}", binary=True)
        write(d / "src" / p, data, manifest, out)
        meta_files[p] = sha256(data)
    lines = flatten(commit, base, main)
    flat = "\n".join(t for _, _, t in lines) + "\n"
    write(d / "flat.tex", flat.encode("utf-8"), manifest, out)
    write(d / "linemap.json", json.dumps([[f, n] for f, n, _ in lines]).encode("utf-8"), manifest, out)
    meta = {"doc": doc, "commit": commit, "date": git("log", "-1", "--format=%cI", commit).strip(), "dir": base,
            "main": main, "files": meta_files, "flat_lines": len(lines), "flat_bytes": len(flat.encode("utf-8"))}
    write(d / "meta.json", json.dumps(meta, indent=1).encode("utf-8"), manifest, out)
    return meta


def export_snapshot(doc: str, out: Path, rules, manifest: dict) -> dict:
    """Stream `git archive` of the commit (one process, not one per file) and keep the scrubbed text files."""
    commit = DOCS[doc][0]
    d = out / doc / "snapshot"
    kept, skipped = 0, {"excluded": 0, "not_text": 0, "too_big": 0}
    proc = subprocess.Popen(["git", "-C", str(ROOT), "archive", "--format=tar", commit], stdout=subprocess.PIPE)
    with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
        for member in tar:
            if not member.isfile():
                continue
            p = member.name
            if excluded(p):
                skipped["excluded"] += 1
                continue
            if Path(p).suffix.lower() not in TEXT_EXT:
                skipped["not_text"] += 1
                continue
            if member.size > MAX_FILE_BYTES:
                skipped["too_big"] += 1
                continue
            text = scrub(tar.extractfile(member).read().decode("utf-8", errors="replace"), rules)
            if survivors(text, rules):
                proc.kill()
                sys.exit(f"{doc}: a scrub rule source survived in a snapshot file; stopping (the file is not named here)")
            if CREDENTIAL.search(text):
                proc.kill()
                sys.exit(f"{doc}: something that looks like a credential is in {p}; stopping")
            write(d / p, text.encode("utf-8"), manifest, out)
            kept += 1
    if proc.wait() != 0:
        sys.exit(f"{doc}: git archive failed")
    return {"commit": commit, "files": kept, "skipped": skipped}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--snapshots", action="store_true")
    ap.add_argument("--docs", nargs="*", default=list(DOCS))
    a = ap.parse_args()
    out = a.out.resolve()
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} is not empty; R1 freezes once, into a fresh directory")
    manifest: dict[str, str] = {}
    rules = load_rules(RULES) if a.snapshots else []
    summary = {}
    for doc in a.docs:
        meta = export_doc(doc, out, manifest)
        summary[doc] = {"flat_lines": meta["flat_lines"], "flat_bytes": meta["flat_bytes"]}
        if a.snapshots:
            summary[doc]["snapshot"] = export_snapshot(doc, out, rules, manifest)
        print(doc, json.dumps(summary[doc]), flush=True)
    (out / "MANIFEST.sha256").write_text("".join(f"{h}  {p}\n" for p, h in sorted(manifest.items())))
    (out / "summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
