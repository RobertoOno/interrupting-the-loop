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


FIGURES_PT = [
    ("traj_dream_scaffold_s6.png",
     "Figura 1. Para onde vai o fluxo. Trajetória do texto gerado no espaço de embeddings de sentença (janelas de 64 tokens, uma PCA por semente para eixos comparáveis), semente s6. ★ premissa, ○ início, × reseed, ◇ evento de saliência julgado, dimensionado pela surpresa. A geração nua dá um salto e congela longe da premissa (passo médio 0.056, distância 1.00); só-saliência vaga (distância mínima de volta 0.48); saliência+esquecimento orbita e volta (0.23); nu + reseed por relógio salta pelo espaço em todas as direções mantendo o contexto."),
    ("fig1_reverie_distributions.png",
     "Figura 2. Surpresa, conexão e coerência julgadas das janelas revisadas por condição (10 sementes, Opus 5, mediana de k=5 por janela; violino = distribuição, barra = média). A geração nua está perto de zero em surpresa e conexão; toda condição interrompida está viva; nu + reseed por relógio iguala o arcabouço completo em surpresa e o supera em conexão e coerência."),
    ("fig2_surprise_vs_coherence.png",
     "Figura 3. Surpresa vs coerência por janela. A interrupção compra surpresa sem pagar coerência: o quadrante superior direito (ambas ≥ 5) tem 8/50 janelas do arcabouço e 12/60 do reseed por relógio, e 0/60 das nuas."),
    ("fig3_per_seed_scaffold_vs_bare.png",
     "Figura 4. Robustez por semente: surpresa média das janelas nuas vs do arcabouço, uma linha por semente. Todas as sementes se movem na mesma direção."),
    ("fig5_judge_resolution.png",
     "Figura 5. O instrumento, medido. Dispersão de cinco julgamentos da mesma janela (rubrica de delta, 89 janelas). O Sonnet 5 se concentra em dispersão zero dando zero à maioria das janelas; o Opus 5 dá notas contínuas com ruído de ±0.7. Efeitos abaixo de ~1 ponto são declarados indetectáveis neste artigo."),
    ("fig6_phase1_novelty.png",
     "Figura 6. Fase 1 — novidade objetiva contra o corpus de treino do OLMo-2 (infini-gram): 4-gramas novos por célula, 3 prompts × 5 sementes. Δ pareado vs min-p: λ=1 +14.6 pp [7.9, 21.9], λ=2 +24.0 pp [18.2, 29.5]."),
    ("fig7_improbable_input.png",
     "Figura 7. Hipótese 2 — delta de novidade julgado vs distância semântica do input a 10k prompts reais, por braço (mediana de 3 juízes). Sem relação (r ≈ +0.05); o pedido típico iguala ou supera todo braço improvável."),
    ("fig8_q1_habituation.png",
     "Figura 8. Bateria 2, Q1 — habituação ou interrupção? nu → nu + habituação → nu + habituação + reseed por relógio (150) → arcabouço; 10 sementes, Opus k=5."),
    ("fig8_q2_content.png",
     "Figura 9. Bateria 2, Q2 — do que é feita a interrupção: mudança de assunto neutra vs costura de reencontro vs a própria premissa vs o próprio passado (relógio 150). Injetar uma volta equivale a não interromper."),
    ("fig8_q3_timing.png",
     "Figura 10. Bateria 2, Q3 — quando voltar: reencontro no relógio (150 e 900) vs no evento de saliência vs só-saliência; janelas de evento e janelas uniformes."),
    ("fig8_q4b_phase.png",
     "Figura 11. Bateria 2, Q4 — com que frequência interromper: surpresa por tokens desde a última interrupção (esquerda) e média do fluxo por período (direita). O rendimento de uma interrupção depende do fio que ela quebra e decai com a distância."),
    ("fig8_q5_family8b.png",
     "Figura 12. Segunda família de gerador (Qwen3-8B-Base): a escada nu → habituação → interrupção → arcabouço."),
    ("fig8_q6_familyolmo.png",
     "Figura 12b. Terceira família de gerador (OLMo-2-13B): a mesma escada, com a interrupção simples custando coerência e o esquecimento do arcabouço preservando-a."),
    ("hidden_h1_geometry_scaffold.png",
     "Figura 13. Dentro da rede, H1 — geometria da trajetória do residual por camada e condição (janelas de 64 tokens, vetores centrados): passo médio, raio explorado e camada de compromisso do logit lens. A geração nua congela em todas as camadas, mais na superfície, e decide tarde e com certeza."),
    ("hidden_h2_novelty_scaffold.png",
     "Figura 14. Dentro da rede, H2 — correlação de Spearman entre o movimento da janela julgada (novidade contra todo o passado; passo local) em cada camada e a surpresa julgada, agregada e dentro de cada condição."),
    ("hidden_h3_interruption_scaffold.png",
     "Figura 15. Dentro da rede, H3 — a que profundidade chega uma interrupção: distância antes/depois de cada injeção por camada menos controle em posições aleatórias (esquerda) e volta ao estado da premissa (direita). O reseed com esquecimento move o estado profundo e o traz de volta à premissa; o reseed por relógio sobre contexto preservado quase não o toca — e é o que o juiz premia."),
    ("hidden_h3_interruption_b2.png",
     "Figura 16. Dentro da rede, H3 na bateria 2 — profundidade da interrupção por conteúdo injetado e por período."),
]
FIGURES_EN_EXTRA = [
    ("fig8_q1_habituation.png", "Figure 8. Battery 2, Q1 — habituation or interruption? bare → bare + habituation → bare + habituation + clock reseed (150) → scaffold; 10 seeds, Opus k=5."),
    ("fig8_q2_content.png", "Figure 9. Battery 2, Q2 — what the interruption is made of: neutral subject change vs re-encounter stitch vs the premise itself vs the stream's own past (clock 150). Injecting a return is as bad as not interrupting."),
    ("fig8_q3_timing.png", "Figure 10. Battery 2, Q3 — when to return: re-encounter on the clock (150 and 900) vs on the salience event vs salience only; event windows and uniform windows."),
    ("fig8_q4b_phase.png", "Figure 11. Battery 2, Q4 — how often to interrupt: surprise by tokens since the last interruption (left) and stream mean by period (right). The yield of an interruption depends on the thread it breaks and decays with distance."),
    ("fig8_q5_family8b.png", "Figure 12. Second generator family (Qwen3-8B-Base): the ladder bare → habituation → interruption → scaffold."),
    ("fig8_q6_familyolmo.png", "Figure 12b. Third generator family (OLMo-2-13B): the same ladder, with the plain interruption costing coherence and the scaffold's forgetting preserving it."),
    ("hidden_h1_geometry_scaffold.png", "Figure 13. Inside the network, H1 — residual-stream trajectory geometry per layer and condition (64-token windows, centered vectors): mean step, explored radius, and logit-lens commitment layer. Bare generation freezes at every layer, most at the surface, and decides late and with certainty."),
    ("hidden_h2_novelty_scaffold.png", "Figure 14. Inside the network, H2 — Spearman correlation between the judged window's movement (novelty vs all past; local step) at each layer and judged surprise, pooled and within condition."),
    ("hidden_h3_interruption_scaffold.png", "Figure 15. Inside the network, H3 — how deep an interruption reaches: before/after distance per layer minus random-position control (left) and return to the premise state (right). The forgetting reseed moves the deep state and returns it to the premise; the clock reseed over preserved context barely touches it — and is what the judge rewards."),
    ("hidden_h3_interruption_b2.png", "Figure 16. Inside the network, H3 on battery 2 — interruption depth by injected content and by period."),
]
FIGURES = FIGURES + FIGURES_EN_EXTRA


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["en", "pt"], default="en")
    a = ap.parse_args()
    global FIGURES
    if a.lang == "pt":
        FIGURES = FIGURES_PT
    src = "PAPER_DREAM.md" if a.lang == "en" else "PAPER_DREAM_pt.md"
    paper = (DOCS / src).read_text()
    # split at section 5 results / section 6 / references to place figures
    body = md_to_html(paper)
    figs = "".join(figure_html(n, c) for n, c in FIGURES)
    # place figures block before "## 6." heading if present, else at end
    marker = "<h2>6. The instrument, measured</h2>" if a.lang == "en" else "<h2>6. O instrumento, medido</h2>"
    figs_title = "Figures" if a.lang == "en" else "Figuras"
    if marker in body:
        body = body.replace(marker, f"<h2>{figs_title}</h2>" + figs + marker)
    else:
        body += f"<h2>{figs_title}</h2>" + figs
    apx = ""
    for name, ttl in (("APPENDIX_ANALYSIS.md", "Appendix A — analysis tables"), ("APPENDIX_B2.md", "Appendix B — battery 2 tables"),
                      ("APPENDIX_HIDDEN_scaffold.md", "Appendix C — residual-stream analysis (ablation battery)"),
                      ("APPENDIX_HIDDEN_b2.md", "Appendix D — residual-stream analysis (battery 2)"),
                      ("APPENDIX_HIDDEN_fam8b.md", "Appendix E — residual-stream analysis (Qwen3-8B family)"),
                      ("APPENDIX_HIDDEN_famolmo.md", "Appendix E2 — residual-stream analysis (OLMo-2 family)")):
        if (DOCS / name).exists():
            if a.lang == "pt":
                ttl = ttl.replace("Appendix", "Apêndice").replace("analysis tables", "tabelas de análise").replace("battery 2 tables", "tabelas da bateria 2") \
                         .replace("residual-stream analysis (ablation battery)", "análise do residual (bateria de ablação)") \
                         .replace("residual-stream analysis (battery 2)", "análise do residual (bateria 2)") \
                         .replace("residual-stream analysis (Qwen3-8B family)", "análise do residual (família Qwen3-8B)") \
                         .replace("residual-stream analysis (OLMo-2 family)", "análise do residual (família OLMo-2)")
            apx += f"<h2>{ttl}</h2>" + md_to_html((DOCS / name).read_text())
    bib = html.escape((DOCS / "references.bib").read_text()) if (DOCS / "references.bib").exists() else ""
    title = "Where Creativity Lives in a Language Model" if a.lang == "en" else "Onde mora a criatividade num modelo de linguagem"
    bib_ttl = "Appendix F — bibliography (BibTeX)" if a.lang == "en" else "Apêndice F — bibliografia (BibTeX)"
    doc = f"<!doctype html><html lang='{a.lang}'><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head><body>{body}{apx}<h2>{bib_ttl}</h2><pre style='font-size:.75rem;white-space:pre-wrap'>{bib}</pre></body></html>"
    out = DOCS / ("manuscript.html" if a.lang == "en" else "manuscrito.html")
    out.write_text(doc)
    print("->", out.relative_to(ROOT), f"{len(doc)/1e6:.1f} MB")


if __name__ == "__main__":
    main()
