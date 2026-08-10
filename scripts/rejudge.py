#!/usr/bin/env python3
"""Re-judge an existing blends/hybrids JSON with the current rubric.

Rubrics evolve; couture is expensive to regenerate but judgments are cheap.
Reads cells with a "blend" field, re-applies the judge, writes
<input>_rejudged.json next to the input.

    python scripts/rejudge.py runs/blend1/blends.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from creative_machine.blend import OpenRouterClient, judge  # noqa: E402


def source_desc(cell: dict) -> str:
    if "sentence" in cell:
        return f"surreal seed sentence: {cell['sentence']}"
    return f"concepts {cell['a']} + {cell['b']}"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path)
    p.add_argument("--judge", default="anthropic/claude-sonnet-5")
    args = p.parse_args()

    cells = json.loads(args.input.read_text())
    client = OpenRouterClient()
    out_path = args.input.with_name(args.input.stem + "_rejudged.json")
    for cell in cells:
        if "blend" not in cell:
            continue
        label = cell.get("name") or f"{cell.get('a')}+{cell.get('b')}"
        try:
            cell["judgment"] = judge(client, args.judge, source_desc(cell), cell["blend"])
            v = cell["judgment"]
            print(
                f"{label}: score {v['score']} nearest={v['nearest_equivalent']} "
                f"delta={v['novel_delta']}",
                flush=True,
            )
        except Exception as exc:
            cell["error"] = str(exc)
            print(f"{label}: failed: {exc}", flush=True)
        out_path.write_text(json.dumps(cells, indent=2))

    judged = [c for c in cells if "judgment" in c]
    with_delta = [c for c in judged if c["judgment"].get("novel_delta")]
    print(f"\n{len(judged)} judged; {len(with_delta)} with a genuine novel delta -> {out_path}")


if __name__ == "__main__":
    main()
