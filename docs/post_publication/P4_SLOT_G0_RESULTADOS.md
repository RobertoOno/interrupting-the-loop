# Programa 4, portão da tomografia na geração 0 (P4-G0) — resultados (leitura única em 18/10/2026)

*Pré-registro: `docs/P4_SLOT_G0_PRE_REGISTRO_V1.md` (congelado em `6beeeaa06`, plano em `6c9496114`). Leitura:
`scripts/analysis_slot_g0.py`, rodada uma vez no pod e relida no Mac só do cache, com saída idêntica. Evidência:
`docs/p4_slot_g0_evidence_v1/` (4.762 arquivos com manifesto SHA-256).*

## 1. Em poucas linhas

- **Portão: FECHADO.** A regra pedia p ≤ 0,05 nas duas formas, com o mesmo sinal.
  - **Código** (dica − semente): +0,083, p = 0,068.
  - **Palavras**: +0,333, p = 0,0002.
  - O sinal é o mesmo nas duas.
- **A censura ficou abaixo de 10% em todos os grupos** (de 0% a 6,2%), então pelo §8 do pré-registro o portão fica **fechado
  "sólido"** com este modelo e esta família.
- **O que não se repetiu**: no arquivo de 10/09, com 12 propostas por corrida, a mesma regra dava p = 0,035 no código. Com 72
  propostas por corrida, a diferença do código caiu de +0,17 para +0,08 e não passou do limiar.

## 2. Os contrastes (permutação exata bilateral, 12.870 partições de 8 contra 8 corridas)

| forma | dica (média) | semente (média) | diferença | p | faixas (dica; semente) |
|---|---|---|---|---|---|
| código: codehint + codehint_g0 − famseed + famseed_pin | 0,479 | 0,396 | +0,083 | 0,068 | 0,423–0,592; 0,239–0,536 |
| palavras: words + words_g0 − wordseed + wordseed_pin | 0,334 | 0,002 | +0,333 | 0,0002 | 0,290–0,368; 0,000–0,014 |

- A medida é a taxa de família entre as propostas válidas da geração 0 de cada corrida, pelo detector congelado de
  `scripts/analysis_slot.py`.
- **A leitura secundária** (a regra de 09/09: faixas disjuntas com o mesmo sinal) também não passa: no código, as faixas se
  sobrepõem.

## 3. As travas

- **Censura por grupo**, sobre 288 propostas cada: de 0 (codehint) a 18 (words_g0, 6,2%). Quase toda a censura é o tempo do
  verificador.
- **O teto de 4.096 tokens prendeu em 3 de 2.304 propostas** (0,1%). As medianas ficaram entre 232 e 332 tokens.
- **O caderno do v1** (300 tokens, igual em todos os grupos, não decide) prendeu em 2 de 384 chamadas.
- **A correção C do prelúdio** passou no teste de identidade sobre pares arquivados antes de qualquer geração. Nenhuma declaração
  do prelúdio foi pulada na geração 0, como previsto.
- **Retentativas HTTP**: nenhuma.

## 4. Observação descritiva (não decide)

- **A diferença nas palavras é grande**: com a ideia em palavras no bloco da semente, quase nenhuma proposta sai na família
  (0,2%); no bloco da dica, um terço sai.
- A semente em palavras é um programa que não implementa a família. É provável que o modelo edite a semente em vez de seguir a
  ideia. Então essa diferença mede lugar e formato juntos, e não sustenta sozinha o alvo da tomografia.

## 5. Custo

- Um pod com uma A100 80 GB por 36 min (15:54–16:31 UTC), cerca de US$1,08.

## 6. O que fica

- **O portão da tomografia na geração 0 fica fechado**, agora com leitura sólida: dado novo, 72 propostas por corrida, censura
  baixa.
- **Pelo §8 do pré-registro**, o efeito de lugar de 10/09 fica como propriedade do laço, não da geração 0.
- **A regra foi escolhida depois de ver o arquivo**, que já a abriria. O dado novo não a confirmou no código.
