#!/usr/bin/env python3
"""Manipulation check (paper-4 review, M4): does the injected SUBJECT reach
the judged text? For every generated-only window that starts right after an
intervention (window start = 300k + 32, i.e. the P1 window the surprise judge
graded), a blind judge picks which of the four rotating subjects — if any —
the window engages. Chance = 25% (or 'none'). Habit cells (no subject) give
the judge's base rate. Text-injected cells (inter / reset_inter) are the
positive control: the subject was literally written into the context.

    AWS_PROFILE=main-account python scripts/manip_check.py runs/state_pulse runs/r4

Writes <run_dir>/manip_windows.json (per window) and <run_dir>/manip.json
({arm: {n, hit, none}}) for analysis_r4.py. k = 1 call per window, Opus 5.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from creative_machine.blend import BedrockClient  # noqa: E402
from dream_rejudge import windows_generated  # noqa: E402

SUBJECTS = [  # DreamConfig.kick_seeds, paraphrased as topics (the judge never sees the injected sentence)
    "a dream about something else entirely (a dream, dreaming, dreamed)",
    "a city with no name (an unnamed city, a nameless city)",
    "an older story about this, retold (a legend, a tale from before)",
    "a question nobody had asked yet (an open question raised)",
]
SYSTEM = ("You read a short passage from a longer text and decide which ONE of the listed "
          "subjects the passage engages — as setting, imagery, or explicit topic. If none of them "
          "is present, answer E. Reply with a JSON object only: {\"pick\": \"A\"|\"B\"|\"C\"|\"D\"|\"E\"}.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dirs", nargs="+", type=Path)
    p.add_argument("--judge", default="anthropic.claude-opus-5")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--tokenizer-model", default="~/models/mlx/Qwen3-8B-Base-8bit")
    p.add_argument("--only-immediate", action="store_true", default=True)
    args = p.parse_args()

    from mlx_lm.utils import load_tokenizer
    tok = load_tokenizer(Path(args.tokenizer_model).expanduser())
    client = BedrockClient(aws_region=args.region)

    for rd in args.run_dirs:
        out_w = rd / "manip_windows.json"
        rows = json.loads(out_w.read_text()) if out_w.exists() else []
        done = {(r["cell"], r["step"]) for r in rows}
        cells = sorted(x for x in rd.iterdir() if x.is_dir() and (x / "run.json").exists())
        items = []
        for d in cells:
            cond = d.name.split("_", 1)[1]
            run = json.loads((d / "run.json").read_text())
            state = run.get("state", {})
            wins = windows_generated(d, tok)
            if run.get("reseeds"):
                segs = [w for w in wins if w.get("since") == 32]
                for i, w in enumerate(segs):
                    items.append((d.name, cond, w, i % 4))
            elif state.get("op") == "pulse" or state.get("pulse_len"):
                for w in wins:
                    k, r = divmod(w["step"] - 32, 300)
                    if r == 0 and k >= 1:
                        items.append((d.name, cond, w, (k - 1) % 4))
            else:  # carrier without subject: base rate on the same grid positions
                for w in wins:
                    k, r = divmod(w["step"] - 32, 300)
                    if r == 0 and k >= 1:
                        items.append((d.name, cond, w, None))
        print(f"{rd.name}: {len(items)} windows ({len(done)} done)", flush=True)
        for cell, cond, w, exp in items:
            if (cell, w["step"]) in done:
                continue
            order = list(range(4))
            random.Random(f"{cell}:{w['step']}").shuffle(order)
            letters = "ABCD"
            menu = "\n".join(f"{letters[j]}) {SUBJECTS[s]}" for j, s in enumerate(order)) + "\nE) none of these"
            try:
                raw = client.chat(args.judge, SYSTEM, f"SUBJECTS:\n{menu}\n\nPASSAGE:\n{w['window']}", max_tokens=60)
                m = re.search(r'"pick"\s*:\s*"([A-E])"', raw)
                pick = m.group(1) if m else None
            except Exception as exc:
                print(f"  judge error ({cell} {w['step']}): {str(exc)[:100]}", flush=True)
                pick = None
            if pick is None:
                continue
            picked = None if pick == "E" else order[letters.index(pick)]
            rows.append({"cell": cell, "cond": cond, "step": w["step"], "expected": exp,
                         "picked": picked, "hit": (picked == exp) if exp is not None else None})
            out_w.write_text(json.dumps(rows, indent=1))
            print(f"  {cell:<16} step {w['step']:>5} exp {exp} pick {picked} {'HIT' if picked == exp and exp is not None else ''}", flush=True)

        summary = {}
        for cond in sorted({r["cond"] for r in rows}):
            rs = [r for r in rows if r["cond"] == cond]
            hits = [r["hit"] for r in rs if r["hit"] is not None]
            summary[cond] = {"n": len(rs),
                             "hit": (sum(hits) / len(hits)) if hits else None,
                             "none": sum(1 for r in rs if r["picked"] is None) / len(rs)}
        (rd / "manip.json").write_text(json.dumps(summary, indent=1))
        print(f"\n== {rd.name} (chance 0.25) ==")
        for cond, s in summary.items():
            hit = f"{s['hit']:.2f}" if s["hit"] is not None else "  — "
            print(f"  {cond:<14} n {s['n']:>3}  hit {hit}  none {s['none']:.2f}")


if __name__ == "__main__":
    main()
