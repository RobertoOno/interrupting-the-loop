#!/usr/bin/env python3
"""Build a self-contained HTML manuscript from docs/PAPER_DREAM.md, with the
figures embedded (base64), numbered captions, the analysis appendix and the
bibliography. Output: docs/manuscript.html (readable anywhere, no server).

    python scripts/build_manuscript.py
"""

from __future__ import annotations

import base64
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
FIG = DOCS / "figures"

FIGURES = [
    ("traj_dream_scaffold_s6.png",
     "Figure 1. Where the stream goes. Trajectory of the generated text in sentence-embedding space (64-token windows, one PCA per seed so axes are comparable), seed s6. ★ premise, ○ start, × reseed, ◇ judged salience event sized by surprise. Bare generation makes one jump and freezes far from the premise (mean step 0.056, distance 1.00); salience-only wanders (min distance back 0.48); salience+forgetting orbits and returns (0.23); bare+clock reseed jumps across the space in every direction while keeping its context."),
    ("fig1_reverie_distributions.png",
     "Figure 2. Judged surprise, connection and coherence of reviewed windows by condition (10 seeds, Opus 5, median of k=5 per window; violin = distribution, bar = mean). Bare generation is near zero on surprise and connection; every interrupted condition is alive; bare + clock reseed matches the full scaffold on surprise and exceeds it on connection and coherence."),
    ("fig2_surprise_vs_coherence.png",
     "Figure 3. Surprise vs coherence per window. Interruption buys surprise without paying coherence: the upper-right quadrant (both ≥ 5) holds 8/50 scaffold and 12/60 clock-reseed windows and 0/60 bare windows."),
    ("fig3_per_seed_scaffold_vs_bare.png",
     "Figure 4. Per-seed robustness: mean surprise of bare vs scaffold windows, one line per seed. Every seed moves in the same direction."),
    ("fig5_judge_resolution.png",
     "Figure 5. The instrument, measured. Spread of five judgments of the same window (delta rubric, 89 windows). Sonnet 5 concentrates at zero spread by scoring zero on most windows; Opus 5 gives continuous scores at ±0.7 noise. Effects below ~1 point are declared undetectable in this paper."),
    ("fig6_phase1_novelty.png",
     "Figure 6. Phase 1 — objective novelty against the OLMo-2 training corpus (infini-gram): novel 4-grams per cell, 3 prompts × 5 seeds. Paired Δ vs min-p: λ=1 +14.6 pp [7.9, 21.9], λ=2 +24.0 pp [18.2, 29.5]."),
    ("fig7_improbable_input.png",
     "Figure 7. Hypothesis 2 — judged novel delta vs the input's semantic distance from 10k real prompts, per arm (median of 3 judges). No relationship (r ≈ +0.05); the typical request matches or beats every improbable arm."),
]

CSS = """
body{font-family:Georgia,'Times New Roman',serif;max-width:860px;margin:2rem auto;padding:0 1.2rem;line-height:1.55;color:#111;background:#fff}
h1{font-size:1.7rem;line-height:1.25;margin-bottom:.3rem}h2{font-size:1.25rem;margin-top:2rem;border-bottom:1px solid #ddd;padding-bottom:.2rem}
h3{font-size:1.05rem;margin-top:1.4rem}p{margin:.6rem 0}code{font-family:Menlo,monospace;font-size:.88em;background:#f4f4f2;padding:0 .2em}
table{border-collapse:collapse;margin:.8rem 0;font-size:.9rem}th,td{border:1px solid #ccc;padding:.25rem .5rem;text-align:left}th{background:#f4f4f2}
figure{margin:1.6rem 0}figure img{max-width:100%;border:1px solid #eee}figcaption{font-size:.88rem;color:#333;margin-top:.4rem}
blockquote{border-left:3px solid #ccc;margin:.8rem 0;padding:.2rem .9rem;color:#444;font-size:.92rem}
.meta{color:#555;font-size:.9rem}.tbd{background:#fff3cd}
"""


def md_to_html(md: str) -> str:
    """Small markdown subset: headers, paragraphs, bullets, tables, bold/italic/code, blockquotes."""
    out, i, lines = [], 0, md.splitlines()
    def inline(t):
        t = html.escape(t, quote=False)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*(?!\*)", r"<i>\1</i>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\[([a-z][a-zA-Z0-9]+)\]", r"<span class='cite'>[\1]</span>", t)
        t = t.replace("[TBD]", "<span class='tbd'>[TBD]</span>")
        return t
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "): out.append(f"<h1>{inline(ln[2:])}</h1>")
        elif ln.startswith("## "): out.append(f"<h2>{inline(ln[3:])}</h2>")
        elif ln.startswith("### "): out.append(f"<h3>{inline(ln[4:])}</h3>")
        elif ln.startswith("> "):
            block = []
            while i < len(lines) and lines[i].startswith("> "):
                block.append(lines[i][2:]); i += 1
            out.append(f"<blockquote class='meta'>{inline(' '.join(block))}</blockquote>"); continue
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i]); i += 1
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows if not re.match(r"^\|[-| ]+\|$", r)]
            if cells:
                head = "".join(f"<th>{inline(c)}</th>" for c in cells[0])
                body = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in cells[1:])
                out.append(f"<table><tr>{head}</tr>{body}</table>")
            continue
        elif ln.startswith("- "):
            items = []
            while i < len(lines) and (lines[i].startswith("- ") or (lines[i].startswith("  ") and items)):
                if lines[i].startswith("- "): items.append(lines[i][2:])
                else: items[-1] += " " + lines[i].strip()
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>"); continue
        elif ln.strip() == "": pass
        else:
            para = [ln]
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^(#|\||- |> )", lines[i + 1]):
                i += 1; para.append(lines[i])
            out.append(f"<p>{inline(' '.join(para))}</p>")
        i += 1
    return "\n".join(out)


def figure_html(name: str, caption: str) -> str:
    p = FIG / name
    if not p.exists():
        return ""
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"<figure><img src='data:image/png;base64,{b64}' alt='{html.escape(name)}'><figcaption>{html.escape(caption)}</figcaption></figure>"


def main() -> None:
    paper = (DOCS / "PAPER_DREAM.md").read_text()
    # split at section 5 results / section 6 / references to place figures
    body = md_to_html(paper)
    figs = "".join(figure_html(n, c) for n, c in FIGURES)
    # place figures block before "## 6." heading if present, else at end
    marker = "<h2>6. The instrument, measured</h2>"
    if marker in body:
        body = body.replace(marker, "<h2>Figures</h2>" + figs + marker)
    else:
        body += "<h2>Figures</h2>" + figs
    appendix = md_to_html((DOCS / "APPENDIX_ANALYSIS.md").read_text()) if (DOCS / "APPENDIX_ANALYSIS.md").exists() else ""
    bib = html.escape((DOCS / "references.bib").read_text()) if (DOCS / "references.bib").exists() else ""
    doc = f"<!doctype html><html><head><meta charset='utf-8'><title>Where Creativity Lives in a Language Model</title><style>{CSS}</style></head><body>{body}<h2>Appendix A — analysis tables</h2>{appendix}<h2>Appendix B — bibliography (BibTeX)</h2><pre style='font-size:.75rem;white-space:pre-wrap'>{bib}</pre></body></html>"
    (DOCS / "manuscript.html").write_text(doc)
    print("-> docs/manuscript.html", f"{len(doc)/1e6:.1f} MB")


if __name__ == "__main__":
    main()
