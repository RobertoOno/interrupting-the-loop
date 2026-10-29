# Degrau 2 — contraste no modelo aberto (Qwen/Qwen3.8-27B), leitura única

Mesmos mundos e verificadores do diagnóstico com o Opus; protocolo de blocos cercados (sem ferramenta); geração em vLLM, verificação local.

## Receptores: resolvido (✓/✗; — não rodou / falha de infra)

| mundo | orçamento | pensar | irmão 1 sem ponte | irmão 1 oráculo | irmão 2 sem ponte | irmão 2 oráculo | regime? |
|---|---|---|---|---|---|---|---|
| CAL3_I | 4096 | não | ✗L | ✗ | ✗L | ✗ | não |
| CAL3_I | 4096 | sim | ✗L | ✗L | ✗L | ✗L | não |
| CAL3_I | 8192 | não | — | ✗ | ✗ | ✗ | não |
| CAL3_I | 8192 | sim | ✗L | ✗L | — | ✗L | não |
| CAL3_I | 16384 | não | — | ✗ | ✗ | ✗ | não |
| CAL3_I | 16384 | sim | ✗L | ✗L | ✗L | ✓ | não |
| CAL3_R | 4096 | não | ✗L | ✗L | ✗L | ✗L | não |
| CAL3_R | 4096 | sim | ✗L | ✗L | ✗L | ✗L | não |
| CAL3_R | 8192 | não | ✗L | ✗ | ✗L | ✗ | não |
| CAL3_R | 8192 | sim | ✗L | ✗L | ✗L | ✗L | não |
| CAL3_R | 16384 | não | ✗L | ✗ | ✗L | ✗ | não |
| CAL3_R | 16384 | sim | ✗L | ✗L | ✗L | ✓ | não |

✗L = terminou por limite de saída sem submissão.

## Propositores: ponte válida (✓) / visível resolvido

| mundo | orçamento | pensar | D0 | D | C2 |
|---|---|---|---|---|---|
| CAL3_I | 8192 | não | ponte ✗ | ponte ✗ | ponte ✗ |
| CAL3_I | 8192 | sim | ponte ✗ | ponte ✗ | ponte ✗ |
| CAL3_I | 16384 | não | ponte ✗ | ponte ✗ | ponte ✗ |
| CAL3_I | 16384 | sim | ponte ✗ | ponte ✗ | ponte ✗ |
| CAL3_R | 8192 | não | ponte ✗ | ponte ✓ + visível ✓ | ponte ✗ |
| CAL3_R | 8192 | sim | ponte ✗ | ponte ✗ | ponte ✗ |
| CAL3_R | 16384 | não | ponte ✗ | ponte ✗ | ponte ✗ |
| CAL3_R | 16384 | sim | ponte ✗ | ponte ✗ | ponte ✗ |

Regimes de contraste encontrados: 0 → nenhum. Células executadas: 72/72; tokens de saída: 674892.

