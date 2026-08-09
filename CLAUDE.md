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

Itens 1 e 2 do roadmap concluídos (2026-08-09). Pacote `creative_machine` em
`src/`; modelo calibrado: `~/models/mlx/Qwen3-8B-Base-8bit` (quantizado
local, ~31 tok/s). Calibração, decisões e os quatro mecanismos que saíram
dela (piso global, régua padronizada, `no_push_ids`, banda de entropia) na
seção "Calibração no 8B" do PLANO; artefatos em `docs/GALERIA.md`.
Testes: `.venv/bin/python -m pytest` (53). Gerar:
`scripts/generate_mlx.py` (uma config) / `scripts/sweep_lambda.py`
(varredura; defaults já na calibração recomendada).

Próximo: completar o item 3 (harness multi-seed/prompt) ou partir para o
item 4 (OLMo-2 + novidade via infini-gram) — decidir com o Roberto.
