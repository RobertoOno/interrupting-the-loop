#!/usr/bin/env python3
"""Self-copy analysis: how much of each generated-only judged window is a
verbatim reproduction of text the stream had already produced, and whether
the source lies within the 600 tokens the window judge sees. A window is
'copied' when at least half of its 12-token shingles occur earlier in the
stream. Writes runs/selfcopy_flags.json ({run: {cell: {step: {frac, frac_recent}}}})
for analysis_gen.py.

    python scripts/selfcopy.py runs/dream_scaffold runs/dream_b2 runs/dream_b3 [...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dream_rejudge import stream_ids_and_injections, windows_generated  # noqa: E402

OUT = ROOT / "runs" / "selfcopy_flags.json"


def copy_flags(cell_dir: Path, tokenizer, K: int = 12, horizon: int = 600) -> dict:
    ids, pts, seed = stream_ids_and_injections(cell_dir, tokenizer)
    out = {}
    for w in windows_generated(cell_dir, tokenizer):
        ws = w["step"]; win = ids[ws: ws + 96]
        before = ids[:ws]
        seen = set(tuple(before[i:i + K]) for i in range(len(before) - K + 1))
        rec_ids = before[max(0, ws - horizon):]
        recent = set(tuple(rec_ids[i:i + K]) for i in range(len(rec_ids) - K + 1))
        sh = [tuple(win[i:i + K]) for i in range(len(win) - K + 1)]
        n = max(1, len(sh))
        out[str(ws)] = {"frac": sum(1 for g in sh if g in seen) / n, "frac_recent": sum(1 for g in sh if g in recent) / n,
                        "since": w.get("since")}
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dirs", nargs="+", type=Path)
    p.add_argument("--tokenizer-model", default=None, help="default: Qwen tokenizer; pass the OLMo tokenizer for OLMo runs")
    args = p.parse_args()
    from mlx_lm.utils import load_tokenizer
    tok = load_tokenizer(Path(args.tokenizer_model or "~/models/mlx/Qwen3-30B-A3B-Base-8bit").expanduser())
    flags = json.loads(OUT.read_text()) if OUT.exists() else {}
    for rd in args.run_dirs:
        flags.setdefault(rd.name, {})
        for d in sorted(x for x in rd.iterdir() if x.is_dir() and (x / "run.json").exists()):
            if d.name in flags[rd.name]:
                continue
            flags[rd.name][d.name] = copy_flags(d, tok)
        OUT.write_text(json.dumps(flags))
        print(rd.name, len(flags[rd.name]), "cells", flush=True)


if __name__ == "__main__":
    main()
