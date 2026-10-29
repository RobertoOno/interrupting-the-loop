# A2 sem curador — resultados (leitura única, 2026-09-15, 13:19; status: PROVEITOSO)

*Pré-registro `docs/A2_SEM_CURADOR_V1.md` (14/09, 22:10; emenda operacional E1). Pergunta: consolidar as provas que o próprio modelo
produziu e o verificador aceitou, sem curadoria nossa, move o modelo em instâncias retidas? Leitura pelo script escrito antes dos dados
(`scripts/analysis_a2_own.py` → `docs/a2c3_results/own.md`); diagnósticos descritivos em `docs/a2c3_results/diagnostics.md`; evidência
integral em `docs/a2c3_evidence_v1/` (3 219 arquivos, 166 MB, manifesto SHA-256 verificado: produção, dados de treino, metadados e
hashes dos adaptadores, quatro braços, leitura, logs).*

## Fase 1 — produção sem curador

Base Qwen3.8-27B com pensamento a 131 072 tokens, uma tentativa em L1, L2 e L3 de cada uma das 48 instâncias de treino (144 células,
noite de 14→15/09, zero cortes do proxy): **60 provas verificadas** (L1 21/48, L2 23/48, L3 16/48), nenhuma no primeiro turno, mediana de
≈ 100 mil tokens de saída por sessão, 30 respostas truncadas no teto, 12 células com a submissão extraída do raciocínio (E5). As formas
são as do modelo: com e sem lema auxiliar, indução com `omega`, `norm_num`, `simp`, `linarith`. Portão de rendimento (≥ 24) passou; as
60 completions próprias e as 60 curadas pareadas (mesmas células) recompilaram em Lean 120/120. Dois LoRA com a receita da consolidação
(108 passos, ≈ 14 épocas sobre 60 exemplos, semente 2026091501): `a2c3-own` e `a2c3-curm`.

## Fase 2 — leitura pré-registrada (seis instâncias retidas, células idênticas às dos braços de 14/09)

| braço | pensamento | L1 | L2 | L3 | L4 | L5 | E |
|---|---|---|---|---|---|---|---|
| base | não | 4/24 | 0/24 | 0/24 | 0/24 | 1/24 | 0/24 |
| **own** (60 provas próprias) | não | **24/24** | 0/24 | 1/24 | 0/24 | 0/24 | 0/24 |
| curm (60 curadas pareadas) | não | 24/24 | 0/24 | 13/24 | 0/24 | 0/24 | 0/24 |
| p2 (288 curadas, seis formas) | não | 24/24 | 1/24 | 7/24 | 24/24 | 24/24 | 24/24 |
| baset131 | sim | — | 6/24 | 8/24 | — | — | — |
| **ownt131** | sim | — | **21/24** | **19/24** | — | — | — |
| curmt131 | sim | — | 17/24 | 18/24 | — | — | — |
| p2t131 | sim | — | 19/24 | 18/24 | — | — | — |

Regras (subida = sign-flip unilateral p < 0,05 sobre as seis instâncias e diferença agrupada ≥ 0,25):
- **P-próprio-simples ✓**: own sobe contra base em L1 (+0,83, p = 0,016), 23/24 no primeiro turno; nada em L2/L3 sem pensamento.
- **P-próprio-pensamento ✓**: ownt131 sobe contra baset131 em L2 (+0,62, p = 0,016) e em L3 (+0,46, p = 0,016); contra p2t131, +0,08 e
  +0,04 (p = 0,25 e 0,50): igual ao adaptador curado com as seis formas, dentro do ruído.
- **Transferência negativa**: nenhuma (own contra base em L4, L5, E: 0,00, −0,04, 0,00).
- **Valor da curadoria**: curm não sobe contra own em degrau nenhum pela regra (L3 sem pensamento +0,50, p = 0,062: 13/24 contra
  1/24, descritivo); com pensamento, curmt131 fica abaixo de ownt131 em L2 (−0,17) e igual em L3. `curated_matched_rises` ✓ (curm sobe
  contra base em L1).

**Veredito pré-declarado: `self_consolidation_moves`.**

## Leitura

O laço fechou sem curador: o modelo produz, o verificador filtra, os pesos gravam, o raciocínio em contexto completa. Com 60 provas
próprias, não escolhidas nem editadas, o adaptador resolve L1 em instâncias novas no primeiro turno (24/24 contra 4/24 da base) e, com
pensamento, L2 e L3 no mesmo nível do adaptador curado (21/24 e 19/24 contra 19/24 e 18/24), muito acima da base com o mesmo pensamento
(6/24 e 8/24). O controle curado pareado diz o que a curadoria compra: eficiência, não taxa. Sem pensamento, a forma curada resolve L3 no
primeiro turno (13/24) onde a própria não resolve (1/24); com pensamento, a própria alcança o curado gastando 4–7 vezes mais tokens
(medianas 11,7 mil e 20 mil contra 3,2 mil e 0,9 mil), nunca no primeiro turno, e escrevendo o arquivo dentro do raciocínio em 46 das 48
sessões (extração da E5). As formas próprias são piores como forma (heterogêneas, mais longas) e o raciocínio paga a diferença.

O que **não** aconteceu: subir a escada. A produção cobriu L1–L3 e é em L1–L3 que o adaptador próprio transfere; em L4, L5 e E ele fica
onde a base está (zero), porque o modelo nunca produziu provas desses degraus. O p2 tem 24/24 ali porque nós lhe demos essas formas. A
próxima pergunta, então, é a iteração: o adaptador próprio com pensamento produz provas em L4/L5/E de instâncias de treino? Se sim, a
consolidação seguinte sobe um degrau sem curador; se não, o laço estaciona no que a base já alcança com pensamento.

## O que não se afirma

Uma família de alvos (quantidades conservadas em Lean), seis instâncias retidas, um modelo, uma semente de treino, uma iteração. É
transferência dentro dos mesmos degraus para instâncias novas, sem curador; não é descoberta nem subida de degrau. Os comparadores base,
baset131, p2 e p2t131 foram lidos em 14/09 em outra instância do servidor (mesmos pesos, mesma amostragem, mesmas células).

## Operação e custo

Pod da produção `0whv08w3x7tzew` (21:59 → 05:52, 473 min) e pod de treino/teste `a7n6iiklxq9rn2` (06:06 → 13:19, 433 min), ambos
H200 a US$4,59/h, removidos pelos scripts e confirmados pelo guarda e pela API: ≈ 15,1 h ≈ US$69; saldo RunPod US$245,42 → US$175,37.
Zero falhas de infraestrutura nas 528 células; zero Bedrock. Toda a cadeia (produção → dados → treino → testes → leitura) correu sem
intervenção depois do lançamento, sob emenda E1.

## Status: PROVEITOSO

Primeiro positivo do programa sem dica: o laço modelo → verificador → pesos → raciocínio melhora o modelo em instâncias novas sem
curadoria humana. Decisões com o Roberto: (i) iteração 2 (produzir em L4/L5/E com `a2c3-own` + pensamento, consolidar, medir: ≈ US$80,
uma noite) para saber se a escada sobe sem curador; (ii) só depois, um problema que não desenhamos (Mathlib real ou a fronteira do
paper 3); (iii) o paper separado do A2 ganha esta seção.
