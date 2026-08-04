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

Item 1 do roadmap concluído (2026-08-03); item 2 em andamento (2026-08-04).
Pacote `creative_machine` em `src/` — sampler anti-provável adaptativo por
entropia, métricas, telemetria, adapter `mlx-lm` e `scripts/generate_mlx.py`.
Testes: `.venv/bin/python -m pytest` (47, todos passam no Mac; `.venv` local
tem `mlx-lm` instalado). Smoke test no `Qwen3-0.6B-Base-8bit` validou o
pipeline ponta a ponta (ver "Primeira execução" no PLANO).

Retomada do item 2 (parado no meio):

1. Completar o download (retoma sozinho; ~3 de 16.4 GB no cache):
   `.venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/Qwen3-8B-Base-bf16')"`
2. Quantizar: `.venv/bin/python -m mlx_lm convert --hf-path mlx-community/Qwen3-8B-Base-bf16 --mlx-path ~/models/mlx/Qwen3-8B-Base-8bit -q --q-bits 8`
3. Sanidade + velocidade com defaults; depois varredura λ ∈ {0, 3, 6, 10}
   (mesma seed/prompt, `--baseline`, telemetria em `runs/`), ler os textos e
   calibrar gatilho/piso. Registrar no PLANO.
