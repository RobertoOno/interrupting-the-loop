# creative-machine

Máquina para induzir "erros" férteis em LLMs e gerar o genuinamente novo:
decodificação anti-provável com guarda de coerência, acoplada a um loop de
seleção. A tese, a arquitetura e todas as decisões tomadas estão em
`docs/PLANO.md` — **leia antes de qualquer trabalho**.

## Convenções

- Idioma do projeto: conversa e documentação em PT-BR; código, identificadores
  e mensagens de commit em inglês.
- Branch de desenvolvimento: `claude/llm-unlikely-predictions-fa5yej`.

## Ambientes

- **Mac (M5 Pro, 48 GB RAM unificada)** — ambiente de execução. Roda os
  modelos via MLX (`mlx-lm`, com `logits_processors` em Python puro).
- **Nuvem (Claude Code web)** — oficina de código. Sem GPU e sem acesso ao
  Hugging Face: todo teste aqui usa distribuições sintéticas / modelo de
  brinquedo, nunca pesos reais.

## Estado atual (2026-08-18, noite)

Pacote `creative_machine` em `src/`; testes: `.venv/bin/python -m pytest`
(117). Modelos quantizados locais: `~/models/mlx/Qwen3-8B-Base-8bit`
(~31 tok/s), `~/models/mlx/OLMo-2-13B-8bit` (~17 tok/s) e
`~/models/mlx/Qwen3-30B-A3B-Base-8bit` (MoE, ~53 tok/s; gerador principal
do loop); em preparação (P1/P2 do parecer): `Qwen3-8B-Base-bf16` (sem
quantização) e `Qwen3-8B-8bit` (pós-treinado). Fluxo git: commits na branch
da sessão → fast-forward `main` → push (`origin` GitHub); `runs/` e modelos
fora do git. Juízes via Bedrock com `AWS_PROFILE=main-account` (nunca outros
perfis). Memória: um modelo por vez (o 30B ocupa ~34 GB); scripts offline
carregam só o tokenizer (`mlx_lm.utils.load_tokenizer`).

**Manuscrito-mestre**: LaTeX em `paper/` (`tectonic main.tex` → `main.pdf`;
seções em `paper/sections/`, tabelas do apêndice geradas por
`scripts/appendix_tex.py` a partir de `docs/APPENDIX_*.md`, figuras copiadas
de `docs/figures/` para `paper/figures/`). Título atual: *Interrupting the
Loop: ...* (subtítulo calibrado após o parecer; ver PLANO "Publicação").
`docs/PAPER_DREAM.md`/`_pt.md` e os HTMLs estão **congelados na v1**
(pré-parecer). Bibliografia em `paper/references.bib` (= `docs/references.bib`).

**Parecer externo (2026-08-18, `docs/revisor_externo.txt`) e revisão maior**
— o que mudou: (1) protocolo primário = janelas **só de texto gerado** (96
tokens, 32 após a injeção; a frase injetada nunca dentro da janela julgada;
`--protocol gen`, `rejudge_gen.json`); (2) unidade de inferência = **célula
(premissa)**: médias de célula, IC bootstrap sobre células, permutação exata
pareada por sinal (2^10), Cliff δ, q BH por família (`scripts/analysis_gen.py`
→ `docs/APPENDIX_GEN.md`, `fig9_*`); (3) bateria 3 (`runs/dream_b3`):
interrupção sem habituação, shams (quebra de parágrafo; "And so, as
before,"), EOS permitido, habituação 1.3, contexto **reset** com/sem assunto
novo; (4) bateria confirmatória pré-registrada (`runs/dream_confirm`: 10
premissas novas, RNG 1, 5 braços; H1–H4 no PLANO); (5) reescrita calibrada.

**Resultado do programa (protocolo novo; detalhes no PLANO)**: sampler
anti-provável = novidade só de superfície, sem efeito detectável em ideias;
input improvável = sem benefício nas operacionalizações testadas; a
continuação forçada de um modelo base degenera; habituação (penalidade de
repetição em janela) tira as órbitas literais; a **interrupção** (assunto
novo injetado periodicamente) eleva surpresa 1,6 → 3,0 e conexão 1,3 → 3,7
sobre a habituação (p = 0,002 pareado, 10 premissas), iguala o scaffold em
surpresa e o supera em conexão. Controles: quebra de parágrafo sozinha = nada;
conectivo de continuidade = pior que nada; o assunto novo precisa da
habituação; **funciona igual (ou melhor em coerência) com contexto reset** —
a "conexão" sob reset é retorno à premissa que o juiz (600 tokens de
horizonte) não distingue de integração; premissa/passado próprio injetados =
não interromper; saliência = relógio na mesma frequência (nem melhor nem
pior); **nenhum período bate 150–300** — o achado da v1 "rendimento cresce com
o fio quebrado, ritmo ~300" era o juiz lendo a frase injetada. Replica no 8B
e no OLMo (no OLMo o scaffold é o melhor braço em surpresa/coerência); Kimi ρ
0,7–0,85; humanos (3, rodada 1) reproduzem a ordem; rodada 2 (`blind_pack3.py`,
`docs/blind/pack_v3.html`, 3 dimensões, amostra ao acaso) à espera de
avaliadores. `scaffold0` e `abl_forget` são byte-idênticos (juiz do loop
nunca passou) → teste–reteste do instrumento (91% medianas iguais).

**Infra**: `scripts/dream_run.py` (condições, incl. as da bateria 3),
`scripts/dream_battery2.py` (baterias b2/b3/confirm/ladder3/famílias;
`--premises new --rng-seed`), `scripts/dream_rejudge_surprise.py`
(`--protocol gen|events`, vários trabalhadores: `--order reverse|random`,
`--skip-from`), `scripts/analysis_gen.py` (análise primária),
`scripts/hidden_states.py` + `hidden_analysis.py` (com IC por célula),
`scripts/blind_pack3.py`/`blind_score.py`, `scripts/after_confirm.sh`
(escadas noturnas: 8B bf16 e 8B pós-treinado).

**Noite de 18→19/08 (tudo no paper)**: confirmatória (H1 confirmada, H3
refutada), **auto-cópia** (rotação fixa de 4 frases → o modelo replica
segmentos anteriores fora da vista do juiz; estimativas "só-frescas" são as
primárias: interrupção +1,2–1,4 surpresa, +0,75 conexão), nível de documento
(ninguém constrói um todo; reset é o menos ruim), 8B bf16 ≈ 8-bit, 8B
pós-treinado (escada mais baixa), reset/preservado no 8B e OLMo, segundo
gênero, portão de juiz (Review real: não acrescenta ao relógio). Scripts
novos: `selfcopy.py`, `judge_document.py`, `judge_agreement.py --protocol
gen`, controle `judge_gate`, baterias `confirm/genre/reset_ladder/ladder3/gate`.

**Em aberto**: rodada 2 humana (Roberto contrata 5 avaliadoras;
`docs/blind/pack_v3.html`, só janelas frescas); título final (decisão do
Roberto); repositório público já criado (`RobertoOno/interrupting-the-loop`;
republicar com `scripts/publish/publish_public.sh`);
NOTEBOOK.md (tradução do PLANO); venue (ICLR 2027 25/09; NeurIPS workshops
29/08; ICCC'27; arXiv); paper seguinte: loop interrompido sobre problema com
verificador (item 8).
