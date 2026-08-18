#!/usr/bin/env python3
"""Document-level judgment: the WHOLE stream of a cell (premise + all generated
tokens, injected sentences removed) read at once and scored on integration,
development, coherence and surprise. Asks the question the 600-token window
judge cannot: does the interrupted loop build a whole, and does keeping the
context (vs resetting it) show at the level of the document?

    AWS_PROFILE=main-account python scripts/judge_document.py runs/dream_b2 runs/dream_b3 runs/dream_scaffold \
        --conds bare bare_habit bare_reseed clock300 nohabit300 sham_break300 reset_reseed300 reset_break300 scaffold0 --k 3

Writes runs/document_judgments.json (one record per cell; medians of k).
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from creative_machine.blend import BedrockClient  # noqa: E402
from dream_rejudge import stream_ids_and_injections  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIMS = ("integration", "development", "coherence", "surprise")

DOC_JUDGE_SYSTEM = (
    "You judge a WHOLE document written by a language model left to write on its own from a one-sentence "
    "premise, with no task. You see the PREMISE and the DOCUMENT (about 4,500 tokens; a few sentences that "
    "were inserted by the experimenters have been removed, so paragraph breaks may look abrupt). Rate four "
    "INDEPENDENT things on 0-10 and return ONLY a JSON object with keys: "
    '"integration" (do the parts of the document connect: are characters, motifs or ideas from earlier parts '
    "taken up later and joined, so that later parts depend on and transform earlier ones? 0 = a sequence of "
    "unrelated pieces, or one loop repeating; 10 = a whole whose parts need each other), "
    '"development" (does something build over the document, an idea, a situation, an image, rather than '
    "restart or repeat? 0 = repetition or a series of restarts; 10 = a clear arc of development), "
    '"coherence" (does it read as one text of some kind? 0 = boilerplate, lists, word salad or collapse; '
    "10 = one document throughout), "
    '"surprise" (does the document as a whole go somewhere a reader of its premise could not have predicted, '
    "in a way that makes sense? 0 = the obvious or nothing at all; 10 = genuinely startling yet not random), "
    '"note" (two blunt sentences: what the document does over its length). '
    "Rate each dimension on its own merits. Score harshly; 7+ must be rare."
)


def document_text(cell_dir: Path, tokenizer, max_tokens: int = 4500) -> str:
    ids, pts, seed = stream_ids_and_injections(cell_dir, tokenizer)
    keep = []
    cut = 0
    for pos, n_inj in pts:
        keep.extend(ids[cut:pos])
        keep.append(None)  # marker for a removed injection
        cut = pos + n_inj
    keep.extend(ids[cut:])
    out, buf, n = [], [], 0
    for t in keep:
        if t is None:
            if buf:
                out.append(tokenizer.decode(buf)); buf = []
            out.append("\n\n")
        else:
            buf.append(t); n += 1
            if n >= max_tokens:
                break
    if buf:
        out.append(tokenizer.decode(buf))
    return seed + "".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dirs", nargs="+", type=Path)
    p.add_argument("--conds", nargs="*", default=None)
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--judge", default="anthropic.claude-opus-5")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--tokenizer-model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    p.add_argument("--out", type=Path, default=ROOT / "runs" / "document_judgments.json")
    args = p.parse_args()

    from mlx_lm.utils import load_tokenizer
    tokenizer = load_tokenizer(Path(args.tokenizer_model).expanduser())
    client = BedrockClient(aws_region=args.region)

    results = json.loads(args.out.read_text()) if args.out.exists() else []
    done = {(r["run"], r["cell"]) for r in results}
    cells = []
    for rd in args.run_dirs:
        for d in sorted(x for x in rd.iterdir() if x.is_dir() and (x / "run.json").exists()):
            cond = d.name.split("_", 1)[1]
            if args.conds and cond not in args.conds:
                continue
            cells.append((rd.name, d, cond))
    print(f"{len(cells)} documents x k={args.k}", flush=True)
    for run, d, cond in cells:
        if (run, d.name) in done:
            continue
        seed = json.loads((d / "run.json").read_text())["seed"]
        doc = document_text(d, tokenizer)
        vs = []
        for _ in range(args.k):
            try:
                raw = client.chat(args.judge, DOC_JUDGE_SYSTEM, f"PREMISE:\n{seed}\n\nDOCUMENT:\n{doc[len(seed):]}", max_tokens=600)
                m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
                v = json.loads(m.group(0))
                vs.append({k: float(v.get(k, 0)) for k in DIMS} | {"note": v.get("note", "")})
            except Exception as exc:
                print(f"  judge error ({d.name}): {str(exc)[:120]}", flush=True)
        if not vs:
            continue
        rec = {"run": run, "cell": d.name, "cond": cond, "seed": d.name.split("_", 1)[0], "k": len(vs), "n_chars": len(doc)}
        for k in DIMS:
            rec[k] = statistics.median([v[k] for v in vs])
        rec["notes"] = [v["note"] for v in vs[:2]]
        results.append(rec)
        print(f"{d.name:<20} I {rec['integration']} D {rec['development']} H {rec['coherence']} S {rec['surprise']}  {rec['notes'][0][:90]}", flush=True)
        args.out.write_text(json.dumps(results, indent=2))
    print("tokens:", client.usage)


if __name__ == "__main__":
    main()
