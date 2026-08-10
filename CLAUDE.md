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

## Estado atual

Itens 1, 2 e 4 do roadmap concluídos (2026-08-09). Pacote `creative_machine`
em `src/`; testes: `.venv/bin/python -m pytest` (60). Modelos quantizados
locais: `~/models/mlx/Qwen3-8B-Base-8bit` (~31 tok/s) e
`~/models/mlx/OLMo-2-13B-8bit` (~17 tok/s). Fluxo git: commits na branch da
sessão → fast-forward `main` → push (`origin` GitHub); `runs/` e modelos
fora do git.

Resultado central até aqui (ver "Item 4" no PLANO): gerações da máquina no
OLMo não contêm nenhum bloco de 8+ palavras do corpus de treino (baseline:
9), novidade de 4-gramas 3× a do baseline. Scripts:
`generate_mlx.py`, `sweep_lambda.py`, `novelty_check.py` (defaults já
calibrados). Artefatos em `docs/GALERIA.md`.

Itens 3, 4 e 6 (versão mínima) também concluídos; Avaliador mínimo pronto
(juiz cross-family + detector de colapso; funil em
`scripts/evaluate_experiment.py`); loop evolutivo piloto rodado
(`scripts/evolve.py`, linhagem em `runs/evo1/`). Resultados-chave: novidade
de 4-gramas da máquina 2× o baseline (ICs excluem zero); custo de coerência
~+1.2 ppl sob juiz independente; três modos de escape mapeados (recitação,
colagem, paráfrase factual — o último sem detector ainda). Em aberto:
item 5 (Fase 2 conceitual via API — exige chaves/custos, decidir com o
Roberto), detector de paráfrase factual, verificador programático
(FunSearch) para domínios verificáveis.
