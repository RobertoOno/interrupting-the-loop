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

## Estado atual (2026-08-16)

Pacote `creative_machine` em `src/`; testes: `.venv/bin/python -m pytest`
(117). Modelos quantizados locais: `~/models/mlx/Qwen3-8B-Base-8bit`
(~31 tok/s), `~/models/mlx/OLMo-2-13B-8bit` (~17 tok/s) e
`~/models/mlx/Qwen3-30B-A3B-Base-8bit` (MoE, ~53 tok/s; gerador principal
do loop). Fluxo git: commits na branch da sessão → fast-forward `main` →
push (`origin` GitHub); `runs/` e modelos fora do git. Juízes via Bedrock
com `AWS_PROFILE=main-account` (nunca outros perfis). Memória: um modelo
por vez (o 30B ocupa ~34 GB); scripts offline carregam só o tokenizer
(`mlx_lm.utils.load_tokenizer`).

**Manuscrito principal**: `docs/PAPER_DREAM.md` (inglês) e
`docs/PAPER_DREAM_pt.md` (tradução integral) — rascunho completo v1;
HTMLs autocontidos por `scripts/build_manuscript.py --lang en|pt`
(`docs/manuscript.html`, `docs/manuscrito.html`), figuras em
`docs/figures/`, apêndices `docs/APPENDIX_*.md` gerados por
`scripts/analysis.py`, `scripts/analysis_b2.py`, `scripts/hidden_analysis.py`.
Bibliografia em `docs/references.bib`. `docs/PAPER.md` (Fase 1) e
`docs/PAPER_B.md` (input improvável) são absorvidos por PAPER_DREAM.

**Resultado do programa** (detalhes e datas no PLANO): o sampler
anti-provável compra só novidade de superfície; inputs improváveis são
ruído; a geração nua de um modelo base é morta; o que a ressuscita são
duas operações — habituação (não comer o próprio passado literal) e
**interrupção** (injetar uma frase nova sobre contexto preservado, que
carrega toda a conexão). A interrupção precisa levar para longe (voltar à
premissa ou ao próprio passado = não interromper), rende conforme o fio
que quebra (ritmo ótimo ~300 tokens; a cada 75 é morto) e o relógio bate
a saliência como gatilho (a saliência é boa leitora, mau metrônomo).
Replica no Qwen3-8B. Dentro da rede: o juiz premia partida na superfície
com continuidade profunda; o esquecimento é um reencontro profundo com a
premissa que o juiz premia menos.

**Infra de experimentos**: `scripts/dream_run.py` (condições),
`scripts/dream_battery2.py` (baterias resumíveis; nohup + caffeinate),
`scripts/dream_rejudge_surprise.py` (julgamento offline Opus k=5, dois
trabalhadores + `rejudge_merge.py`), `scripts/hidden_states.py` +
`hidden_analysis.py` (residual por camada, logit lens),
`scripts/trajectories.py`, `scripts/blind_pack.py`/`blind_score.py`
(avaliação humana cega; pacote v1 em `docs/blind/`).

**Em aberto**: avaliação humana cega (hora do Roberto); revisão do texto;
venue (ver "Publicação" no PLANO: ICLR 2027 no Brasil, paper 25/09/2026;
workshops NeurIPS 29/08; ICCC'27 ~março; arXiv); item 8 do roadmap
(fusão: loop interrompido sobre problema com verificador).
