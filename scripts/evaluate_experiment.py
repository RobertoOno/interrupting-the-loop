#!/usr/bin/env python3
"""The selection funnel over a finished experiment: filter, then rank.

Scores every cell with (a) genre-collapse score from telemetry and (b)
coherence under a judge model from a different family, then ranks the
surviving machine cells by n-gram novelty. Requires the experiment's
manifest.json; uses novelty.json when present.

    python scripts/evaluate_experiment.py --exp runs/exp1 \
        --judge ~/models/mlx/Qwen3-8B-Base-8bit --top 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from creative_machine.evaluator import (  # noqa: E402
    entropy_drop_score,
    judge_perplexity,
    record_entropies,
)
from creative_machine.stats import mean_std  # noqa: E402
from run_experiment import PROMPTS  # noqa: E402

COLLAPSE_THRESHOLD = 0.35


def load_novelty_by_name(exp: Path, manifest: dict) -> dict[str, dict]:
    """Map cell name -> novelty summary. Falls back to manifest order for
    novelty.json written before names were recorded."""
    path = exp / "novelty.json"
    if not path.exists():
        return {}
    per_arm = json.loads(path.read_text())
    out = {}
    order: dict[str, list[dict]] = {arm: list(reps) for arm, reps in per_arm.items()}
    for cell in manifest["cells"]:
        reps = order.get(cell["arm"])
        if not reps:
            continue
        rep = reps.pop(0)
        out[rep.get("name", cell["name"])] = rep
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--exp", type=Path, required=True)
    p.add_argument("--judge", required=True, help="judge model path (different family!)")
    p.add_argument("--top", type=int, default=5)
    args = p.parse_args()

    from mlx_lm import load

    manifest = json.loads((args.exp / "manifest.json").read_text())
    novelty = load_novelty_by_name(args.exp, manifest)
    judge, judge_tok = load(args.judge)

    rows = []
    for cell in manifest["cells"]:
        name = cell["name"]
        text = (args.exp / f"{name}.txt").read_text()
        prompt = PROMPTS[cell["prompt_i"]]
        row = {"name": name, "arm": cell["arm"], **judge_perplexity(judge, judge_tok, text, prompt)}
        tele = args.exp / f"{name}.jsonl"
        if tele.exists():
            records = [json.loads(line) for line in tele.read_text().splitlines()]
            row["collapse"] = entropy_drop_score(record_entropies(records))
        nov = novelty.get(name)
        if nov:
            vals = list(nov["novelty_by_n"].values())
            row["novelty"] = sum(vals) / len(vals)
            row["max_copied"] = nov["longest_copied_len"]
        rows.append(row)
        print(f"scored {name}", flush=True)

    (args.exp / "evaluation.json").write_text(json.dumps(rows, indent=2))

    print("\n== judge perplexity by arm (continuations, judged cross-family) ==")
    arms = sorted({r["arm"] for r in rows})
    for arm in arms:
        vals = [r["judge_ppl"] for r in rows if r["arm"] == arm]
        m, s = mean_std(vals)
        print(f"  {arm:<10} judge_ppl {m:.2f}±{s:.2f}")

    machine = [r for r in rows if r["arm"] != "baseline"]
    print("\n== highest collapse scores (read these: likely register collapses) ==")
    for r in sorted(machine, key=lambda r: -r.get("collapse", 0))[:3]:
        print(f"  {r['name']:<18} collapse {r['collapse']:.2f}  judge_ppl {r['judge_ppl']:.2f}")

    # Two collapse modes, two complementary detectors: recitation collapses
    # crater the entropy (collapse score); document-collage collapses keep
    # entropy high but the cross-family judge flags them (ppl ceiling).
    base_ppls = sorted(r["judge_ppl"] for r in rows if r["arm"] == "baseline")
    ppl_ceiling = 1.5 * base_ppls[len(base_ppls) // 2] if base_ppls else float("inf")
    survivors = [
        r
        for r in machine
        if r.get("collapse", 0) < COLLAPSE_THRESHOLD
        and r["judge_ppl"] < ppl_ceiling
        and "novelty" in r
    ]
    print(f"\n== shortlist: novel survivors ({len(survivors)}/{len(machine)} pass "
          f"collapse<{COLLAPSE_THRESHOLD} and judge_ppl<{ppl_ceiling:.1f}) ==")
    for r in sorted(survivors, key=lambda r: -r["novelty"])[: args.top]:
        print(
            f"  {r['name']:<18} novelty {r['novelty']:.3f}  collapse {r['collapse']:.2f}  "
            f"judge_ppl {r['judge_ppl']:.2f}  -> {args.exp}/{r['name']}.txt"
        )


if __name__ == "__main__":
    main()
