#!/usr/bin/env python3
"""Human rating, round 2 (external review): a blind pack of GENERATED-ONLY
windows sampled at RANDOM (not stratified by the LLM judge's score), rated on
three dimensions (surprise, connection, coherence), English interface with
the rater guide embedded. One window per sampled cell, cells drawn at random
within each condition, so no cell dominates a condition.

    python scripts/blind_pack3.py --tag v3 --per-cond 8 \
        --conds bare bare_habit nohabit300 clock300 sham_break300 reset_reseed300 scaffold0

Writes docs/blind/pack_<tag>.html (self-contained, guide embedded) and the
hidden key runs/blind/key_<tag>.json. Score with scripts/blind_score.py.
"""

from __future__ import annotations

import argparse
import html
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dream_rejudge import windows_generated  # noqa: E402

RUNS = ROOT / "runs"

GUIDE = """
<h1 style='font-size:1.4rem'>Blind rating of machine-written passages: rater guide (round 2)</h1>
<p>Thank you for helping with a research study on text generation. The task takes about 60&ndash;90 minutes and needs only a web browser.</p>
<h2>What you will see</h2>
<p>This page contains <b>{n} items</b>. Each item shows:</p>
<ul><li><b>Earlier text</b> (grey box): the last ~1,500 characters written before the passage. Read it first: two of the three scores depend on it.</li>
<li><b>The passage</b> (blue box): about 70&ndash;90 words. This is what you rate.</li></ul>
<p>All texts were written by a language model left to write on its own, with no task and no instructions, in English. Some stretches will look odd, repetitive or like web boilerplate; that is normal and part of what we measure. You do not need to know anything about how they were produced, and we deliberately do not tell you. Passages are cut at fixed positions, so a passage may begin or end mid-sentence; do not penalize that.</p>
<h2>The three scores (0&ndash;10 each)</h2>
<p><b>Surprise</b>: how unexpected is the passage <i>given the earlier text</i>: could a reader have predicted where it went?</p>
<ul><li><b>0</b> = obvious continuation. This includes continuing the same loop, list, quiz, product page or web boilerplate that was already there; however odd the text looks on its own, if it is more of the same, it is not surprising.</li>
<li><b>3&ndash;4</b> = a small turn: a new detail or angle that follows naturally.</li>
<li><b>7&ndash;8</b> = a genuine turn you would not have anticipated, and it makes sense.</li>
<li><b>10</b> = startling yet not random: an idea, image or connection that opens something new and holds together with what came before.</li>
<li>Nonsense, word salad and mere topic-hopping stay low: surprise is not weirdness.</li></ul>
<p><b>Connection</b>: does the passage bring together two distant parts of the earlier text, or an old part of it with something new, in a way that makes sense?</p>
<ul><li><b>0</b> = it merely continues one thread (or is boilerplate); nothing from further back is picked up.</li>
<li><b>3&ndash;4</b> = it touches something from earlier in passing.</li>
<li><b>7&ndash;8</b> = it clearly joins two things that were far apart in the earlier text, or an old thing with a new one, and the join makes sense.</li>
<li><b>10</b> = the join is the point of the passage and it illuminates both sides.</li>
<li>Only the earlier text shown counts as &ldquo;earlier&rdquo;; you cannot see the whole document, and that is fine.</li></ul>
<p><b>Coherence</b>: does the passage hold together as text, on its own terms?</p>
<ul><li><b>0</b> = word salad, a bare list, or document boilerplate (footers, menus, quiz keys).</li>
<li><b>5</b> = readable but loose, drifting or slightly broken.</li>
<li><b>10</b> = clear, integrated prose (any genre).</li></ul>
<p>Score the three dimensions <b>independently</b>: a passage can be surprising and incoherent, coherent and dull, or surprising without connecting anything. <b>Use the whole scale</b>: many passages deserve 0&ndash;2 on surprise and connection; a few deserve 7+.</p>
<h2>Practical</h2>
<ol><li>Skim five or six items before scoring, to find your own 0 and your own high.</li>
<li>Score every item on all three dimensions; leave none blank. There is no right answer: we want your independent reading, so please do not discuss items with anyone else who is rating.</li>
<li><b>Please do not use AI tools (ChatGPT, Claude, Gemini, etc.) or web searches for any part of this task.</b> The whole point of the study is to compare human readings with machine readings; an AI-assisted rating would make your work unusable, and we would not be able to pay for it. Your own first impression as a reader is exactly what we need.</li>
<li>When done, click <b>Generate JSON</b> at the bottom, copy the whole text that appears in the box, and send it back (message or email). That is the only deliverable.</li></ol>
<p style='font-size:.85rem;color:#444'>Your ratings will be used only in aggregate, in a research publication, without your name. By returning the JSON you confirm that you rated the passages yourself, without AI assistance.</p>
"""


def load_gen(run: str):
    rows = []
    for name in ("rejudge_gen.json", "rejudge_gen_w2.json", "rejudge_gen_w3.json"):
        p = RUNS / run / name
        if p.exists():
            rows.extend(json.loads(p.read_text()))
    seen, out = set(), []
    for r in rows:
        k = (r["cell"], r["step"])
        if k in seen or r.get("surprise") is None:
            continue
        seen.add(k); out.append({**r, "run": run})
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tag", default="v3")
    p.add_argument("--runs", nargs="+", default=["dream_scaffold", "dream_b2", "dream_b3"])
    p.add_argument("--conds", nargs="*", default=["bare", "bare_habit", "nohabit300", "clock300", "sham_break300", "reset_reseed300", "scaffold0"])
    p.add_argument("--per-cond", type=int, default=8, help="windows per condition, one per cell, cells at random")
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--tokenizer-model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    p.add_argument("--fresh-only", action="store_true", help="exclude windows that are >=50%% verbatim copies of the stream's own earlier text (runs/selfcopy_flags.json)")
    args = p.parse_args()
    flags = json.loads((RUNS / "selfcopy_flags.json").read_text()) if args.fresh_only else {}

    from mlx_lm.utils import load_tokenizer
    tokenizer = load_tokenizer(Path(args.tokenizer_model).expanduser())
    rng = random.Random(args.seed)

    judged = []
    for run in args.runs:
        for r in load_gen(run):
            if r["cond"] not in args.conds or r.get("since") not in (32, None):
                continue
            if args.fresh_only:
                f = flags.get(run, {}).get(r["cell"], {}).get(str(r["step"]))
                if f is None or f["frac"] >= 0.5:
                    continue
            judged.append(r)
    items = []
    for cond in args.conds:
        rows = [r for r in judged if r["cond"] == cond]
        by_cell = {}
        for r in rows:
            by_cell.setdefault(r["cell"], []).append(r)
        cells = sorted(by_cell)
        rng.shuffle(cells)
        for cell in cells[: args.per_cond]:  # random cells, one random post-interruption window each
            items.append(rng.choice(by_cell[cell]))
        if len(cells) < args.per_cond:
            print(f"warning: {cond} has only {len(cells)} judged cells")
    # recut the exact text of each window (generated-only protocol)
    cache, out_items = {}, []
    for r in items:
        cell_dir = RUNS / r["run"] / r["cell"]
        key = (r["run"], r["cell"])
        if key not in cache:
            cache[key] = {w["step"]: w for w in windows_generated(cell_dir, tokenizer)}
        w = cache[key].get(r["step"])
        if not w:
            print("missing window", r["cell"], r["step"]); continue
        f = flags.get(r["run"], {}).get(r["cell"], {}).get(str(r["step"])) if flags else None
        out_items.append({"run": r["run"], "cell": r["cell"], "cond": r["cond"], "step": r["step"], "kind": "gen", "since": r.get("since"),
                          "copy_frac": (f or {}).get("frac"),
                          "judge_surprise": r["surprise"], "judge_connection": r.get("connection"), "judge_coherence": r.get("coherence"),
                          "window": w["window"], "earlier": w["earlier"]})
    rng.shuffle(out_items)
    for i, it in enumerate(out_items):
        it["id"] = f"w{i+1:02d}"
    key_dir = RUNS / "blind"; key_dir.mkdir(exist_ok=True)
    (key_dir / f"key_{args.tag}.json").write_text(json.dumps(out_items, indent=1))

    css = """
    body{font-family:Georgia,serif;max-width:900px;margin:1.5rem auto;padding:0 1rem;line-height:1.5;color:#111}
    .guide{border:1px solid #ddd;border-radius:6px;padding:1rem 1.2rem;margin-bottom:1.5rem;background:#fff}
    .guide h2{font-size:1.1rem;margin:.9rem 0 .3rem}
    .item{border:1px solid #ddd;border-radius:6px;padding:.8rem 1rem;margin:1rem 0}
    .earlier{white-space:pre-wrap;background:#f4f4f4;padding:.5rem;font-size:.85rem;color:#444;max-height:15rem;overflow:auto}
    .win{white-space:pre-wrap;background:#fbfbf8;padding:.6rem;border-left:3px solid #2a78d6;font-size:.95rem}
    .q{display:flex;gap:1.5rem;align-items:center;margin-top:.5rem;font-size:.9rem;flex-wrap:wrap}
    input[type=number]{width:3.5rem}textarea{width:100%;height:9rem;font-family:Menlo,monospace;font-size:.8rem}
    button{padding:.4rem .8rem;font-size:.95rem}
    .short{background:#fff8e6;padding:.5rem .8rem;border-radius:6px;font-size:.85rem;margin:.6rem 0 1rem}
    """
    short = ("<div class='short'><b>Reminder.</b> Read the grey earlier text, then the blue passage. "
             "<b>Surprise</b>: how unexpected given the earlier text (0 = obvious continuation or more of the same boilerplate; 10 = startling yet not random). "
             "<b>Connection</b>: does it join two distant parts of the earlier text, or an old part with something new, in a way that makes sense (0 = merely continues one thread). "
             "<b>Coherence</b>: does it hold together as text (0 = word salad or boilerplate; 10 = clear prose). Score each on its own; use the whole scale.</div>")
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>Blind rating {html.escape(args.tag)}</title><style>{css}</style></head><body>",
             "<div class='guide'>" + GUIDE.format(n=len(out_items)) + "</div>",
             short, f"<p>{len(out_items)} passages.</p>"]
    for it in out_items:
        parts.append(f"<div class='item' id='{it['id']}'><b>{it['id']}</b>")
        parts.append(f"<div class='earlier'>{html.escape(it['earlier'][-1500:])}</div>")
        parts.append(f"<div class='win'>{html.escape(it['window'])}</div>")
        parts.append("<div class='q'>"
                     f"Surprise <input type='number' min='0' max='10' step='1' data-id='{it['id']}' data-dim='surprise'> "
                     f"Connection <input type='number' min='0' max='10' step='1' data-id='{it['id']}' data-dim='connection'> "
                     f"Coherence <input type='number' min='0' max='10' step='1' data-id='{it['id']}' data-dim='coherence'></div></div>")
    parts.append("<button onclick='gen()'>Generate JSON</button><p><textarea id='out' placeholder='JSON'></textarea></p>")
    parts.append("""<script>
    function gen(){const o={};let missing=0;document.querySelectorAll('input[data-id]').forEach(i=>{if(i.value===''){missing++;return}o[i.dataset.id]=o[i.dataset.id]||{};o[i.dataset.id][i.dataset.dim]=Number(i.value)});
    if(missing>0){alert(missing+' score(s) still blank. Please fill every box before generating the JSON.');}
    document.getElementById('out').value=JSON.stringify({tag:'%s',ratings:o});document.getElementById('out').select();}
    </script></body></html>""" % html.escape(args.tag))
    out_dir = ROOT / "docs" / "blind"; out_dir.mkdir(exist_ok=True)
    out = out_dir / f"pack_{args.tag}.html"
    out.write_text("\n".join(parts))
    from collections import Counter
    print(f"{len(out_items)} windows -> {out}   (key: runs/blind/key_{args.tag}.json; do not open before rating)")
    print("per condition:", dict(Counter(it["cond"] for it in out_items)))


if __name__ == "__main__":
    main()
