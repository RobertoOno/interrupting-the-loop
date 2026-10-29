# A2 — piloto de competência com Mathlib: resultados (leitura única, 2026-09-13; status: limite pela regra, sinal de instrumento)

*Pré-registro `A2_PILOTO_MATHLIB_V1.md` (emendas E1–E7 antes das células afetadas). Leituras pelos scripts escritos antes dos dados
(`analysis_a2_pilot.py`, `analysis_a2_mathlib.py`). Evidência integral em `docs/a2m_evidence_v1/` (2 288 arquivos, manifesto
SHA-256: sessões, planos, proveniência, logs, leituras, verificação dos 36 mundos, o run abortado antes de leitura).*

## O que foi feito

Instrumento novo: mundos `env=mathlib` (36, verificados), modo provador (molde nativo, transplante do último bloco Lean, mesmo
verificador), 16k/900 s/180 s. Dois modelos rodaram; dois foram dispensados (E7).

| modelo (modo) | L1 | L2 | L3 | L4 | L5 | E | competência | margem | decisão |
|---|---|---|---|---|---|---|---|---|---|
| Pythagoras-Prover-4B (provador) | 0/24 | 0/24 | 0/24 | 0/24 | 0/24 | 0/24 | não | não | `no_competence` |
| Qwen3.8-27B FP8 (ferramenta, pensamento) | 4/24 | 4/24 | 2/24 | 0/24 | 1/24 | 0/24 | não (0,17) | sim | `no_competence` |
| Goedel-Prover-V2-8B, Pythagoras-Prover-32B | — | — | — | — | — | — | — | — | dispensados (E7) |

Veredito entre modelos: `no_open_model_admitted_A2_closes_in_this_domain`. Nenhum modelo aberto ≤ 32B atinge a regra de
competência (L1 ≥ 0,5) neste instrumento.

## Efeito do exemplo no 27B (plano B, descritivo por E6)

| braço | L4 | L5 | bits poupados (L4+L5, 6 instâncias) |
|---|---|---|---|
| nenhum (plano A) | 0/24 | 1/24 | — |
| esqueleto (exemplo genérico de P3) | 0/24 | 10/24 | +0,84, p = 0,031 |
| referência (prova curada de E) | 1/24 | 12/24 | +1,14, p = 0,0156 (mínimo) |

O efeito da forma replica num modelo aberto pela terceira vez (Opus em A1; Thinking-30B 8/24 no piloto Std; 27B 12/24 aqui), com a
mesma assimetria L5 ≫ L4 de A1 (o exemplo de E partilha a forma de L5, não a de L4).

## Diagnósticos posteriores (não alteram escores)

- **4B**: 1 094 submissões, todas rejeitadas; 555 usam `induction`, mas **0 escrevem o lema auxiliar** (medida + passo + ponte); erro
  dominante "unsolved goals" (723). Conhece a palavra, não a forma. Degenera em repetição em respostas longas.
- **27B sem exemplo**: as 11 soluções têm todas indução sobre `Reaches`; 5 com lema auxiliar separado (uma define `I(s) = −3x − 2y + z`
  e prova preservação por passo e por `Reaches`: o esqueleto de referência). 122/144 sessões pensam até o teto de 16k; as que resolvem
  usam o feedback do Lean (3–9 turnos). Raciocínio gravado (E5): ≈ 18,7 mil caracteres por resposta.
- **27B com exemplo**: as 23 soluções têm todas lema auxiliar + indução; 21 de 23 fecham com `nlinarith`/`linarith` ou `sq_nonneg`
  adaptando o fecho `grind` da referência; 2–7 turnos. A forma transfere; o fecho é adaptado à tática que o modelo domina.

## Leitura

1. **Provadores de olimpíada não têm a forma**: o 4B (e, por família, o 8B e o 32B) não escreve o lema-ponte em mil tentativas. O
   treino em enunciados fechados não dá relações indutivas.
2. **O raciocinador geral tem a forma a taxa baixa e a usa quando a vê**: o 27B é o primeiro modelo aberto com soluções sem exemplo
   e o efeito do exemplo é o maior já medido num modelo aberto (L5 0,04 → 0,50).
3. **A regra de competência (L1 ≥ 0,5) falhou por orçamento, não por forma**: 85 % das sessões do 27B terminam pensando no teto. É a
   mesma falha dominante de A1 na Opus ("pensar até o teto sem submeter"), aqui mais forte.
4. Consequência para A2: a consolidação (pré-registrada em `A2_CONSOLIDACAO_V1.md`) tem substrato: pesos abertos, forma presente no
   prior a taxa baixa, teto em contexto medido (L5 0,50), e treino/teste sem pensamento, que remove a falha de orçamento do teste.

## Emendas (todas antes das células afetadas; detalhe no pré-registro)

E1 resposta sem cerca é o bloco; cortada no teto não é submetida · E2 sandbox lê o cache Mathlib e as ferramentas de desenvolvedor,
`git` real sem config de usuário, sonda do preflight anexa o cache, cache somente-leitura · E3 ordem por competência esperada (27B em
segundo) · E4 checkpoint FP8 e parser `qwen3_coder`; imagem `qwen38` e `--max-num-seqs 64` após crash loop do cache Mamba · E5 cliente
grava o campo `reasoning`; run abortado antes de leitura (16 células) e reiniciado · E6 plano B do 27B como descritivo · E7 8B e 32B
dispensados. Correção anterior: rótulo de orçamento lido do plano (tabela do piloto 3b, decisão inalterada).

## Custo e operação

GPU ≈ US$22 (saldo RunPod US$175,78 → US$153,77): 4B ≈ 1,6 h; 27B ≈ 1,9 h de diagnóstico (BF16 não cabe numa H100; crash loop do
cache Mamba; `runpodctl pod logs` deu a causa) + 1,7 h de plano A + 1 h de plano B. Zero Bedrock (plano C da Opus adiado pelo limite
diário). Todos os pods removidos; verificação de ausência pela API.

## O que não se afirma

Nada sobre consolidação ainda. A comparação 4B/27B é descritiva (modos e quantizações diferentes). O efeito do exemplo no 27B foi
medido com pensamento e ferramenta; a consolidação usa outro formato (provador, sem pensamento), e o teto serve só de referência.
