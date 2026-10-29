# Fechamento do Programa 2 — Transferência por correspondência estrutural (2026-09-04)

*Documento autocontido. Fontes: `docs/PROGRAMA2_TRANSFERENCIA.md` (tese e desenho), PLANO (pré-registros
de 03/09 e leituras únicas), `docs/APPENDIX_P2.md` (etapa 1), `docs/APPENDIX_P2_STAGE2.md` (etapa 2, leitura
única preservada), `docs/APPENDIX_P2_STAGE2_AUDIT.md` e `_v2.md` (auditoria do endpoint de família, emendas 1 e 2), `docs/MANIFEST_P2.md` e
`docs/MANIFEST_P2_CHECKSUMS.sha256`
(comandos, parâmetros, horários, custos, checksums).*

## 1. Pergunta original

O novo que vale nasce de transferência a distância: uma família de construção trazida de outro problema.
Nenhum sistema publicado tem um órgão automático para isso. O Programa 2 perguntou: **um modelo de
fronteira, dado o enunciado do alvo e uma construção verificada de outro problema, consegue propor uma
correspondência estrutural e escrever um transplante que tire o laço de busca da família em que ele trava?**

## 2. Desenho (pré-registrado em 03/09, antes de qualquer chamada)

- **Alvo**: sum-difference III (`sumdiff3`, θ = log(|U−U|/|U+U|)/log(2 max U + 1) + 1, |U| ≤ 4000, verificador
  exato). Referências: melhor final nosso sem ajuda 1,11228 (20 corridas, todas na família F0 = "somas de
  poucas potências de 2"); família do recorde (codificação mista sem vai-um, Gerbicz/Zheng) instanciada no
  teto = 1,1236; AlphaEvolve 1,1479 com 2003 inteiros; recorde 1,1731.
- **Biblioteca**: 72 programas minerados de 180 corridas em 9 problemas (sumdiff3 excluído) + 12 famílias
  clássicas de outros problemas (Behrend, Salem–Spencer, Stanley, Erdős–Turán, Bose–Chowla, Mian–Chowla,
  Golomb, base de diferenças, Cantor, Zeckendorf, livre de somas, mistura de Bellec–Fritz) = 84 entradas.
  A família do recorde ficou fora (teste cego).
- **Classificador de família** (fixo antes dos dados): F0 = fração de elementos com ≤ 3 bits ligados ≥ 0,8;
  F_rec = existe base b ≤ 2001 com todos os dígitos ≤ (b−1)/2 e |U| ≥ 50 (o limite era 25 e foi corrigido
  em emenda registrada às 23:00 de 03/09, antes da leitura do controle D0); "saída de família" = final
  válido com θ ≥ 1,10 fora de F0.
- **Etapa 1 (transplantes diretos)**, por entrada e por modelo (Claude Opus 5 via Bedrock; Kimi K2.6 via
  OpenRouter): D = correspondência (alvo + fonte + código; 2 tentativas); C2 = sham sintático (mesmo
  modelo, sem o enunciado do alvo); C1 = porte mecânico (sem LLM). Primário S1: fração de entradas com
  saída de família, D vs C2, pareado por entrada.
- **Etapa 2 (laço)**: top-5 transplantes por braço como semente (`--seed-file`), 3 RNG, propositor
  Qwen3-30B-A3B-Base em vLLM (H100). Primário S2: fração de corridas cujo final tem saída de família.
- Sucesso/abandono, leitura única e scripts de análise escritos antes dos dados: PLANO 03/09.

## 3. Etapa 1 — resultados (leitura única, 03/09 22:45)

| braço | válidos | entradas com saída de família | melhor θ |
|---|---|---|---|
| D, Opus | 160/168 | 78 de 84 | 1,1198 |
| C2, Opus | 80/84 | 1 de 84 | 1,1038 |
| D, Kimi | 55/168 | 2 de 84 | 1,1095 |
| C2, Kimi | 69/84 | 0 de 84 | 1,0957 |
| C1, mecânico | 67/84 | 1 de 84 | 1,1038 |

S1 formalmente positivo no Opus (pareado por entrada: D só 78, C2 só 1; sinal exato p < 10⁻²⁰) e nulo no Kimi.

## 4. O confundidor

Os melhores transplantes do Opus não transportam a ideia da fonte: são o mesmo programa (hill-climbing
de um conjunto-semente + potência tensorial em base 2m+1 sem vai-um, o mecanismo da família do recorde),
com a fonte servindo de pretexto para a "correspondência". O sham C2 não via o enunciado do alvo, logo
D − C2 media conhecimento do alvo, não transferência. A taxa de saídas por grupo de origem era uniforme
(geometria, empacotamento, dígitos: 8–16 por grupo) — a fonte não deixava marca.

## 5. Controle D0 (registrado antes de rodar, 03/09 23:35; leitura 04/09 01:10)

D0 = só o enunciado do alvo, sem fonte, 2 tentativas por posição, mesmo modelo e mesmo esforço.

| contraste (Opus) | saídas de família | melhor θ |
|---|---|---|
| D (com fonte) | 78 de 84 | 1,1198 |
| D0 (sem fonte) | 73 de 84 | **1,1240** |

Pareado: D só 11, D0 só 6, p = 0,33. **O D0 iguala o D em saídas e o supera em θ já na etapa 1.** Kimi:
D0 com 0 saídas. Reclassificação com o teste corrigido: 101 dos 160 transplantes válidos do D-Opus e 79
dos 146 do D0-Opus são F_rec (sem vai-um) — reconstrução do mecanismo do recorde a partir do prior.

## 6. Etapa 2 — resultados (leitura única, 04/09 11:40; 108 corridas de 200 propostas = 21.600 propostas, 6.874 válidas)

- O laço praticamente **não melhora as sementes fortes**: D0-Opus 1,1192 → 1,1197 em média (7 de 15 corridas
  melhoram, por milésimos); D-Opus 1,1165 → 1,1165; melhor final = a própria semente do D0 (1,12396).
- **D não supera D0 depois da busca** (θ médio 1,1165 vs 1,1197; Mann–Whitney sobre corridas p = 0,0006 a
  favor de D0, com a ressalva de dependência entre os 3 RNG de cada semente; por semente, n = 5 vs 5,
  p = 0,056 / 0,063 com D0 ≥ D — auditoria).
- **Nenhuma corrida atingiu 50% do gap** entre a semente e 1,1479.
- Laço nu (A) em 200 propostas: 1,0976 (melhor 1,1044), abaixo do 1,1123 de agosto; validade 22–60% nesta
  via (código de teste solto no módulo; listas literais além dos 700 tokens) — afeta todos os braços por igual.
- Desvio registrado: 200 propostas por corrida (o parâmetro `--samples` é por ilha), não as 100 planejadas.

## 7. Correção: famílias herdadas versus novas (auditoria, emendas 1 e 2)

O script da leitura única classificou só `best.py`, que não existe quando a semente continuou sendo o
melhor (64 de 108 corridas) e que omite o prelúdio com que o candidato foi verificado. A auditoria
reconstruiu cada programa final por replay do `history.jsonl` (elites, corte da ilha, migração), verificou
que ele reproduz o escore e separou **quatro quantidades**: família herdada da semente; saída qualificante
nova produzida pelo laço; mudança efetiva de família (ambas conhecidas e diferentes); final não classificável.
Na emenda 2 o escore da semente é o **observado em cada corrida** (93 corridas pela entrada `seed` do
`state.json`; 15 por reexecução de programa determinístico, conferida com o log; 0 incertas) e família
desconhecida nunca conta como mudança.

| braço | melhoraram | finais = semente | materialização self / prelúdio / não | sementes fora de F0 (herdada) | finais fora de F0 | saídas novas | mudança efetiva de família | finais não classificáveis |
|---|---|---|---|---|---|---|---|---|
| A | 3/3 | 0 | 2 / 1 / 0 | 0 | 0 | 0 | 0 | 0 |
| C1 (mecânico) | 3/15 | 12 | 3 / 0 / 0 | 3 | 3 | 0 | 0 | 0 |
| C2 Kimi | 12/15 | 3 | 5 / 6 / 1 | 0 | 3 | 3 | 3 | 1 |
| C2 Opus | 10/15 | 5 | 6 / 4 / 0 | 3 | 5 | 2 | 0 | 0 |
| D0 Kimi | 9/15 | 6 | 3 / 2 / 4 | 0 | 0 | 0 | 2 | 4 |
| D0 Opus | 5/15 | 10 | 0 / 2 / 3 | 15 | 11 | 0 | 1 | 3 |
| D Kimi | 1/15 | 14 | 0 / 1 / 0 | 6 | 6 | 0 | 0 | 0 |
| D Opus | 1/15 | 14 | 0 / 1 / 0 | 15 | 15 | 0 | 0 | 0 |

Totais (emenda 2): 64 finais são a própria semente; 19 `best.py` autônomos; 17 reproduzem o escore só com o
prelúdio reconstruído; 8 não reproduzem (otimizadores com orçamento de tempo ou dependência de elites
estocásticos) e ficam marcados, fora da classificação. Saídas de família nos finais: 43 = **38 herdadas** +
**5 novas**, todas a partir de sementes de sham derivadas da entrada Zeckendorf (1,0887 → 1,10–1,108), nenhuma
em D ou D0; **mudanças efetivas de família: 6** (emenda 1 contava 14 porque somava famílias desconhecidas).
Com a semente como unidade (5 vs 5), D vs D0 no Opus dá p = 0,056 (Mann–Whitney) / 0,063 (permutação), com
D0 ≥ D. Diferenças exatas entre as emendas: seção 8 de `docs/APPENDIX_P2_STAGE2_AUDIT_v2.md`.

## 8. Custos

≈ US$83: Opus US$42,5 a preço de lista (D 17,4; C2 4,5; D0 20,6 — respostas de 4 a 5 mil tokens),
Kimi ≈ US$4 (estimativa), pods ≈ US$36 (duas tentativas, 10,5 h de H100 a US$3,49/h; a primeira abortada
no portão de fumaça por um bug meu na via de completions). Duração: 03/09 21:39 → 04/09 11:30.

## 9. Conclusão

1. S1 (D vs C2) foi formalmente positivo, mas o controle D0 mostrou que o efeito vinha do conhecimento
   do alvo, não da fonte estrutural.
2. D0-Opus alcançou resultado melhor que D-Opus já na etapa 1 (1,1240 vs 1,1198).
3. Na etapa 2 o laço praticamente não melhorou as sementes fortes; D não superou D0 depois da busca.
4. Nenhuma corrida atingiu 50% do gap até 1,1479.
5. **A correspondência estrutural, na formulação testada, não é suportada.**
6. O resultado real: o modelo de fronteira reconstrói a família forte a partir do alvo (prior da
   literatura), enquanto o laço local 30B não consegue levá-la adiante. O modelo barato não faz nem uma
   coisa nem outra.
7. O Programa 2 fica **encerrado nesta formulação** — não é fracasso operacional: pré-registro, controles,
   leitura única e auditoria funcionaram, e a resposta é clara.

## 10. Ativos reutilizáveis

- Biblioteca de famílias executáveis (`docs/transfer_library/`, 84 entradas) e o minerador
  (`scripts/transfer_library.py`).
- Motor de correspondência com braços D/D0/C2/C1 e dois provedores (`scripts/transfer_correspond.py`).
- Classificadores de família (`family_sumdiff3.py`, `family_beatavg.py`) e o achado colateral: a parede
  do beat-the-average é o limite do contínuo, não uma ideia (`docs/APPENDIX_P2_FAMILY.md`).
- Resultados estáveis da auditoria em artefato rastreado (`docs/p2/stage2_audit_v2_results.json`); diagnósticos
  voláteis fora do clone; análise reproduzível com `pip install -e ".[analysis]"` (scipy, numpy).
- Harness com via de completions para modelos base em vLLM (`frontier_search.py --oai-completions`),
  lançador de pod com portão de fumaça (`run_p2_stage2.sh`), auditor com replay testado
  (`analysis_p2_stage2_audit.py`, `tests/test_p2_audit.py`), manifesto com checksums.

## 11. Perguntas que permanecem abertas

- Transferência existe onde o prior está vazio? (instâncias sem literatura; `docs/ALVOS_CEGOS.md`,
  **não iniciado**.)
- Um humano transfere onde o modelo não transfere? (braço H como controle positivo, não iniciado.)
- O que um modelo com prior muito maior (GPT-6 Astra) faz em alvos cegos: ideia ou memória?
- Abdução de regra (Zahavy, "LLMs can't jump"): enunciar a família a partir de exemplos verificados e
  deduzir construções dela — variante não testada.

## 12. Por que encerrar esta formulação

Em alvos famosos, o prior do modelo de fronteira contém a família do recorde e nenhum teste distingue
analogia de memória; o sham registrado não previa isso e o controle D0 o expôs. Continuar com o mesmo
desenho só refinaria uma medida que não pode ver o que procura. A formulação seguinte, se houver, muda o
alvo (prior vazio), a referência (otimizador clássico) e o controle (humano) — e isso é uma decisão de
programa, não um passo deste fechamento.
