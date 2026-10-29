#!/usr/bin/env python3
"""Size of the lab notebook (docs/PLANO.md) at each frozen version's commit, for the report's comparison with the pilot records.

    python3 scripts/r1_notebook_size.py --out docs/r1/report_review_v2/notebook_size.json

Characters and words are exact; tokens use tiktoken's cl100k_base when it is installed. The pilot records of R2 are measured the
same way (as the writer received them: the files joined by scripts/r2_write.py's record_text, without the task instructions), so
the notebook and the pilots can be compared with one tokenizer; the provider counts in the report use each provider's own.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORDS = ROOT / "docs/r2/pilot_evidence_v1/records"
FREEZES = {"P1": "55345d8ba", "PS": "2745b9370", "P2": "e2a791807", "P3": "403fa55f1", "P4": "c1830d1ce", "P6": "42d1bec1d"}


def record_text(d: Path) -> str:
    """The same join as scripts/r2_write.py's record_text(keyed=False), read from the archived records."""
    extra = sorted(str(p.relative_to(d)) for sub in ("results", "release", "reviews") if (d / sub).is_dir()
                   for p in (d / sub).iterdir() if p.is_file())
    names = ["notebook.md", *extra, *(["manifest.json"] if (d / "manifest.json").exists() else []), "companion.md", "draft.md"]
    return "\n\n".join(f"=== FILE: {n} ===\n{(d / n).read_text(encoding='utf-8')}" for n in names)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
    except ImportError:
        enc = None
    rows = {}
    for doc, commit in FREEZES.items():
        text = subprocess.run(["git", "show", f"{commit}:docs/PLANO.md"], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")
        rows[doc] = {"commit": commit, "chars": len(text), "words": len(text.split()),
                     "tokens_cl100k": len(enc.encode(text, disallowed_special=())) if enc else None}
    pilots = {}
    for d in sorted(p for p in RECORDS.iterdir() if p.is_dir()):
        text = record_text(d)
        pilots[d.name] = {"chars": len(text), "tokens_cl100k": len(enc.encode(text, disallowed_special=())) if enc else None}
    out = {"file": "docs/PLANO.md", "tokenizer": "cl100k_base" if enc else None, "by_freeze": rows, "pilot_records": pilots}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
