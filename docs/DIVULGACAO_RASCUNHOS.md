# Rascunhos de divulgação (para revisão do Roberto — NADA sai sem seu ok)

*2026-08-24. Coordenar tudo para o dia em que o paper 3 v1 subir ao arXiv
(após sua revisão e a extensão n=9). Ordem: arXiv → thread X + LinkedIn →
e-mails de outreach → HN/Reddit se houver tração.*

## 1. Thread para o X (inglês; ~8 posts; imagens: curva do propositor + best.py comentado)

1/ Over three weeks, on one MacBook, we ran a pre-registered research
program on machine creativity: 2 papers on arXiv, and now a third. The
finding of the last one fits in a sentence: **in verified search, the last
mile is an idea, not a budget.** 🧵

2/ Background: FunSearch/AlphaEvolve move mathematical records with an LLM
proposing programs + a hard verifier + selection. Everyone varies the
scaffolding. Nobody measured *which parts of the proposer's cognition*
matter. We ran the factorial: 5 arms × 6 open problems × 2 replicates,
pre-registered.

3/ The operators came from our earlier work on open-ended generation
(arXiv:2608.19893): a schematic notebook the model writes and carries, a
named obstacle, and behavioural repulsion from constructions already
found. Composed, they help in 5/6 problems (+0.20 of the seed→record gap).
Alone, every one of them fails somewhere.

4/ The cleanest law (5th independent measurement in this program):
**repulsion without an anchor breaks.** Push a model away from what it
already found without a memory holding direction, and on fragile manifolds
the search starves. Composed with memory+agenda: never collapses.

5/ Then we held the loop fixed and swapped only the proposer: local 30B →
Claude Opus 5. [curve figure] The frontier model reaches in ~30 samples
what the local one never reaches in 600 — and passes AlphaEvolve's
reported value on this problem (0.3897 vs 0.3890) within 300 samples,
~US$50 of API.

6/ Then the wall: best known is 0.400695. We ruled out the grid (finer =
worse at equal budget), verifier time (3× → +0.0002), and proposer
strength (two independent models, same plateau). Every LLM proposes the
same construction family; the record lives outside it.

7/ The constructions are legible — the model *comments its own strategy*
[best.py image]. It rediscovers the sparse-atom family, optimizes it
beautifully, and cannot leave it. Search harvests a prior's families to
their best member. Crossing families took, in every case we know, an idea.

8/ Everything is public: harness, every candidate ever sampled, dated
pre-registrations, the negative results at full volume.
[repo link] [papers links]
Done on one Mac + ~US$150 of API, by an independent researcher + Claude.

## 2. LinkedIn (PT-BR, 1 post)

Três semanas, um MacBook, três papers. Começamos perguntando se dá para
tornar um LLM mais criativo; terminamos com um mapa medido: variação é
barata; diversidade se compra; massa se move com treino; e a fronteira —
em busca verificada — para exatamente onde acaba a família de construções
que o modelo conhece. "A última milha é uma ideia, não um orçamento."
Tudo pré-registrado, tudo público, nulos incluídos. [links]

## 3. E-mails de outreach (inglês; 1 parágrafo cada; enviar do gmail)

**a) Adam Zsolt Wagner / equipe do repositório (georgiev-gomez-serrano-tao-wagner)**
Subject: Office-scale runs on your repository of problems (+ a factorial of
proposer-side operators)
> Dear Dr. Wagner, — we ran a pre-registered factorial of proposer-side
> "cognitive operators" (schematic lineage memory, named obstacle,
> behavioural repulsion) on six problems of your repository, at office
> scale (local 30B, 120–600 verified samples), plus a proposer-strength
> ladder on beat-the-average that passes AlphaEvolve's reported value and
> stalls where the sparse-atom family ends — matching your "expert in the
> loop" observation from the other side. Paper: [arXiv]. All candidates
> and pre-registrations are public. If any of it is useful to the
> repository (constructions, per-candidate logs), we would be glad to
> contribute. Thank you for making the problems and verifiers public —
> this work only exists because of that.

**b) Robert Lange / Sakana (ShinkaEvolve)**
Subject: A controlled factorial of proposer-side operators (complements
ShinkaEvolve's novelty machinery)
> ...your novelty-rejection results motivated our "behavioural repulsion"
> arm — we measure it alone and composed, pre-registered, and find it
> unsafe alone / certified for functional diversity (p=0.0156) / best when
> composed with a schematic memory. Also a proposer-strength curve under a
> fixed loop. Thought it might interest you: [arXiv].

**c) Daphne Ippolito / NoveltyBench group**
Subject: Behavioural diversity inside verified search (a downstream use of
your diagnosis)
> ...NoveltyBench diagnoses mode collapse; we measure a repulsion operator
> that provably restores functional diversity inside a verified-search
> loop — and what it costs. [arXiv]

**d) Yue et al. (pass@k) — opcional**
> ...your base-vs-RLVR coverage result predicted our consolidation
> findings; the new paper adds the proposer-strength curve under a fixed
> verified loop. [arXiv]

**e) Rajarshi Haldar e Wenhong Zhu (follow-up pessoal)**
> ...the program you helped at its first step now has three papers; thank
> you again — here is where it went. [links]

## 4. Contribuição ao repositório AlphaEvolve (issue/PR)
Abrir issue em google-deepmind/alphaevolve_repository_of_problems:
"Office-scale runs + candidate logs on problems 36/39/44/48/50/59/61/38
(external)" com link ao nosso repo/paper e oferta das construções e logs.
(Verificar CONTRIBUTING.md antes; tom: gratidão + dados, zero claim.)

## 5. Checklist de consistência antes de publicar qualquer item
- [ ] Números finais = APPENDIX_F/PLANO (após F-ext2)
- [ ] Nenhum claim de "melhor que X" — só "no mesmo nível do valor
      reportado", "com fração do custo"
- [ ] Links: arXiv 1, arXiv 2 (quando subir), arXiv 3, repo público
- [ ] Roberto aprovou o texto final de cada peça
