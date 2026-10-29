# A2 — consolidação da forma em pesos (PROPOSTA, 2026-09-13; não é pré-registro; nada executado)

*Para decisão do Roberto depois da leitura do piloto Mathlib. Pergunta de A2 desde a árvore: o operador que poupa ≈ 2 bits em
contexto (o esqueleto curado da prova, A1 v2/v3) pode ser escrito nos pesos de um modelo aberto e transferir para instâncias novas?
A pergunta não exige competência de base: a competência é o desfecho medido. Se aprovada, vira `A2_CONSOLIDACAO_V1.md` congelado,
com análise escrita antes dos dados.*

## Previsões (escritas antes; o experimento existe para falsificá-las)

- **P1 (forma gravada transfere dentro da forma)**: treinar nas provas curadas de E e L5 (forma de Pell/Vieta: `have nt := Int.sq_nonneg t`,
  `grind [measure, start]`) eleva a taxa em E e L5 de instâncias **retidas** acima da base (permutação por sinal sobre instâncias,
  unilateral); em L4 (mesmo `grind`, mas medida quadrática de três campos e `Int.sq_nonneg a/b`) e em L1–L3 (`omega`) não eleva.
- **P2 (currículo de formas)**: treinar nas provas curadas dos seis degraus eleva a taxa em todos os degraus retidos.
- **P3 (controle de sintaxe)**: treinar em provas Lean de mesma dose e táticas, sem a estrutura passo-lema + ponte-por-indução
  (lemas aritméticos soltos com `omega`/`grind`), não eleva nenhum degrau. Se elevar tanto quanto P1/P2, o que se grava é sintaxe,
  não forma, e a leitura de A1 em pesos cai.
- **P4 (descritiva)**: a taxa consolidada em L5 comparada ao teto em contexto do mesmo modelo (na Thinking-30B, 8/24 com a referência).

## Desenho

- **Substrato**: o modelo admitido pelo piloto Mathlib (Qwen3.8-27B, se for admitido; modo ferramenta ou provador, o mesmo do piloto).
  Se nenhum for admitido: **Qwen3-30B-A3B-Thinking-2507**, o único modelo aberto com efeito da forma em contexto medido (L5 8/24), no
  ambiente onde ele foi medido (Std) e em **modo provador** (arquivo completo em bloco `lean`, mesma extração e mesmo verificador),
  para que treino e teste tenham o mesmo formato e o orçamento não seja gasto pensando (`enable_thinking=false` no teste, igual em
  todos os braços). O teto em contexto de 8/24 foi medido com pensamento e ferramenta; entra só como referência descritiva (P4).
- **Dados de treino**: instâncias novas do gerador (fase `a2_train`, ≈ 24 sementes), provas curadas `Hidden/Reference.lean`
  renderizadas no formato exato de teste (prompt do provador → arquivo completo). Braço P1: E e L5 (48 exemplos); P2: seis
  degraus (144); P3: 144 lemas aritméticos gerados com as mesmas táticas e tamanho. Passos de otimização iguais entre braços.
- **Treino**: LoRA (MLX no Mac, como na bateria C; ou `peft` numa H100 se o substrato for o 27B denso), posto e taxa fixados no
  pré-registro; um adaptador por braço; nenhuma seleção por resultado de teste.
- **Teste**: 6 instâncias retidas (fase `a2_heldout`, nunca vistas), seis degraus, 4 tentativas, sem exemplo: 144 sessões por braço;
  braços base / P1 / P2 / P3 = 576 sessões; mesmo laço, verificador, limites e ordem embaralhada do piloto. Leitura única.
- **Regras**: uma taxa "sobe" quando a permutação por sinal sobre as seis instâncias retidas dá p < 0,05 (mínimo 0,0156) e a
  diferença agrupada é ≥ 0,25. P1 confirmada = sobe em E ou L5 e não sobe em L4 nem em L1–L3. P2 confirmada = sobe em ≥ 4 degraus.
  P3 = não sobe em nenhum. Morte: nenhum braço sobe em nenhum degrau (a forma não é gravável com esta dose e escala: limite de A2
  neste domínio); ou P3 sobe como P1/P2 (sintaxe, não forma).

## Custo e tempo

Treino: horas de Mac (30B-A3B em 8 bits) ou ≈ 1 h de H100 (27B). Teste: 576 sessões em modo provador ≈ 2–3 h de GPU ≈ US$10, mais
o Lean local. Zero Bedrock. Total ≈ US$15.

## O que não se afirma

Nada sobre progressão nem invenção: é a transposição de A1 v3 para pesos (a forma transfere dentro da forma). Nada sobre outros
domínios. Um resultado positivo diz que o órgão que falta pode ser alimentado por consolidação curada; um negativo diz que, nesta dose,
não pode. Ambos entram no paper 5 na seção da alavanca.
