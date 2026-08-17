#!/usr/bin/env python3
"""Build a blind human-rating pack: judged windows sampled across conditions
and stratified by the LLM judge's surprise (low / mid / high), shuffled, no
labels. Writes a self-contained HTML form (docs/blind/pack_<tag>.html) the
rater fills in and a hidden key (runs/blind/key_<tag>.json). Scoring:
scripts/blind_score.py pastes the rater's JSON against the key.

    python scripts/blind_pack.py --tag v1 --per-cond 8 --runs dream_scaffold dream_b2
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
from dream_rejudge import windows_of  # noqa: E402

RUNS = ROOT / "runs"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tag", default="v1")
    p.add_argument("--runs", nargs="+", default=["dream_scaffold", "dream_b2"])
    p.add_argument("--conds", nargs="*", default=["bare", "bare_habit", "bare_reseed", "scaffold0", "clock_reenc", "clock_self", "sal_reenc"])
    p.add_argument("--per-cond", type=int, default=6, help="windows per condition (stratified low/mid/high judged surprise)")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--tokenizer-model", default="~/models/mlx/Qwen3-30B-A3B-Base-8bit")
    p.add_argument("--lang", choices=["pt", "en"], default="pt", help="language of the rating interface (the texts are always English)")
    args = p.parse_args()

    from mlx_lm.utils import load_tokenizer
    tokenizer = load_tokenizer(Path(args.tokenizer_model).expanduser())
    rng = random.Random(args.seed)

    judged = []
    for run in args.runs:
        pth = RUNS / run / "rejudge_surprise.json"
        if not pth.exists():
            continue
        for r in json.loads(pth.read_text()):
            if r.get("surprise") is None or r["cond"] not in args.conds or r["step"] < 100:
                continue  # windows before 100 generated tokens are degenerate fragments (excluded from the analysis too)
            judged.append({**r, "run": run})
    items = []
    for cond in args.conds:
        rows = [r for r in judged if r["cond"] == cond]
        if not rows:
            continue
        rows.sort(key=lambda r: r["surprise"])
        n = len(rows)
        strata = [rows[: n // 3], rows[n // 3 : 2 * n // 3], rows[2 * n // 3 :]]
        per = max(1, args.per_cond // 3)
        for s in strata:
            for r in rng.sample(s, min(per, len(s))):
                items.append(r)
    # recut the exact text of each window
    cache = {}
    out_items = []
    for r in items:
        cell_dir = RUNS / r["run"] / r["cell"]
        key = (r["run"], r["cell"])
        if key not in cache:
            cache[key] = {(w["step"], w["kind"]): w for w in windows_of(cell_dir, tokenizer, 160, 600)}
        w = cache[key].get((r["step"], r["kind"]))
        if not w:
            continue
        out_items.append({"run": r["run"], "cell": r["cell"], "cond": r["cond"], "step": r["step"], "kind": r["kind"],
                          "judge_surprise": r["surprise"], "judge_connection": r.get("connection"), "judge_coherence": r.get("coherence"),
                          "window": w["window"], "earlier": w["earlier"]})
    rng.shuffle(out_items)
    for i, it in enumerate(out_items):
        it["id"] = f"w{i+1:02d}"

    key_dir = RUNS / "blind"; key_dir.mkdir(exist_ok=True)
    (key_dir / f"key_{args.tag}.json").write_text(json.dumps(out_items, indent=1))

    # ---- HTML form
    css = """
    body{font-family:Georgia,serif;max-width:900px;margin:1.5rem auto;padding:0 1rem;line-height:1.5;color:#111}
    .item{border:1px solid #ddd;border-radius:6px;padding:.8rem 1rem;margin:1rem 0}
    .win{white-space:pre-wrap;background:#fbfbf8;padding:.6rem;border-left:3px solid #2a78d6;font-size:.95rem}
    details{margin:.4rem 0;font-size:.85rem;color:#444}details pre{white-space:pre-wrap;background:#f4f4f4;padding:.5rem}
    .q{display:flex;gap:1.5rem;align-items:center;margin-top:.5rem;font-size:.9rem}
    input[type=number]{width:3.5rem}textarea{width:100%;height:9rem;font-family:Menlo,monospace;font-size:.8rem}
    button{padding:.4rem .8rem;font-size:.95rem}
    .rubric{background:#fff8e6;padding:.6rem 1rem;border-radius:6px;font-size:.9rem}
    """
    if args.lang == "en":
        rubric = ("<div class='rubric'><b>How to rate</b> (blind: you do not know where each passage comes from). These are stretches of text "
                  "written by a language model left to write on its own, with no task. For each item, read the <i>earlier text</i> (grey) and then "
                  "the <b>passage</b> (blue), and give two scores from 0 to 10:<br>"
                  "<b>Surprise</b> — how unexpected is the passage <i>given the earlier text</i>: a reader could not have predicted where it went. "
                  "0 = obvious continuation (including continuing the same loop, list, quiz or web boilerplate that was already there, however odd it looks); "
                  "10 = genuinely startling yet not random. Nonsense and mere topic-hopping stay low; reserve 7+ for turns that surprise <i>and</i> make sense.<br>"
                  "<b>Coherence</b> — does the passage hold together as text: 0 = word salad, list, or document boilerplate; 10 = clear, integrated prose. "
                  "Score each dimension on its own: a passage can be surprising and incoherent, or coherent and dull. Use the whole scale. "
                  "When done, click <b>Generate JSON</b>, copy the text and send it back.</div>")
        title = f"Blind rating pack {html.escape(args.tag)}"
        labels = ("earlier text", "Surprise", "Coherence", "Generate JSON", "passages")
    else:
        rubric = ("<div class='rubric'><b>Como avaliar</b> (cego: você não sabe de que condição cada janela vem). Para cada janela, leia o "
                  "<i>contexto anterior</i> (opcional, dobrado) e a <b>janela</b> (o trecho a avaliar), e dê duas notas de 0 a 10:<br>"
                  "<b>Surpresa</b> — quanto o trecho traz algo genuinamente inesperado dado o que veio antes (0 = previsível/boilerplate/repetição; "
                  "10 = uma ideia, imagem ou virada que você não anteciparia e que abre algo). "
                  "<b>Coerência</b> — quanto o trecho se sustenta como texto (0 = colapsado, lista, sem sentido; 10 = prosa clara e integrada). "
                  "Não premie mudança de assunto por si só; premie o que <i>surpreende e faz sentido</i>. Ao terminar, clique em "
                  "<b>Gerar JSON</b>, copie o texto e cole na conversa.</div>")
        title = f"Blind rating pack {html.escape(args.tag)}"
        labels = ("contexto anterior", "Surpresa", "Coerência", "Gerar JSON", "janelas")
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>Blind rating {args.tag}</title><style>{css}</style></head><body>",
             f"<h1>{title}</h1>",
             rubric,
             f"<p>{len(out_items)} {labels[4]}.</p>"]
    for it in out_items:
        parts.append(f"<div class='item' id='{it['id']}'><b>{it['id']}</b>")
        if args.lang == "en":  # context shown, not folded: surprise is relative to it
            parts.append(f"<div style='white-space:pre-wrap;background:#f4f4f4;padding:.5rem;font-size:.85rem;color:#444;max-height:15rem;overflow:auto'>{html.escape(it['earlier'][-1500:])}</div>")
        else:
            parts.append(f"<details><summary>{labels[0]}</summary><pre>{html.escape(it['earlier'][-1800:])}</pre></details>")
        parts.append(f"<div class='win'>{html.escape(it['window'])}</div>")
        parts.append(f"<div class='q'>{labels[1]} <input type='number' min='0' max='10' step='1' data-id='{it['id']}' data-dim='surprise'> "
                     f"{labels[2]} <input type='number' min='0' max='10' step='1' data-id='{it['id']}' data-dim='coherence'></div></div>")
    parts.append(f"<button onclick='gen()'>{labels[3]}</button><p><textarea id='out' placeholder='JSON'></textarea></p>")
    parts.append("""<script>
    function gen(){const o={};document.querySelectorAll('input[data-id]').forEach(i=>{if(i.value==='')return;o[i.dataset.id]=o[i.dataset.id]||{};o[i.dataset.id][i.dataset.dim]=Number(i.value)});
    document.getElementById('out').value=JSON.stringify({tag:'%s',ratings:o});document.getElementById('out').select();}
    </script></body></html>""" % html.escape(args.tag))
    out_dir = ROOT / "docs" / "blind"; out_dir.mkdir(exist_ok=True)
    out = out_dir / f"pack_{args.tag}.html"
    out.write_text("\n".join(parts))
    print(f"{len(out_items)} windows -> {out}   (key: runs/blind/key_{args.tag}.json — do not open before rating)")


if __name__ == "__main__":
    main()
