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

Item 1 do roadmap concluído (2026-08-03): pacote `creative_machine` em
`src/` — sampler anti-provável adaptativo por entropia, métricas, telemetria,
adapter `mlx-lm` (import preguiçoso) e `scripts/generate_mlx.py`. Suíte
sintética: `python3 -m pytest` (43 testes; os de mlx pulam sem Apple silicon).
Próximo passo: item 2 — primeira execução no Mac (venv com `mlx-lm`,
`Qwen3-8B-Base` 8-bit, calibrar λ / piso / gatilho).
