# A2 — consolidação da forma em pesos: resultados (leitura única, 2026-09-14, 01:06; status: PROVEITOSO)

*Pré-registro `A2_CONSOLIDACAO_V1.md` (congelado 13/09 17:40; sem emendas). Leitura pelo script escrito antes dos dados
(`analysis_a2_consolidation.py`; `docs/a2c_results/consolidation.{md,json}`). Evidência integral em `docs/a2c_evidence_v1/` (3 459
arquivos, manifesto SHA-256: 576 sessões, planos, proveniência, manifesto e verificação dos dados, manifestos e curvas de treino dos
adaptadores, hashes dos pesos, logs do pod e da cadeia). Pesos dos adaptadores (3 × 304 MB) em `runs/a2c/adapters/`, fora do git,
hashes em `adapter_weights.sha256`.*

## Veredito pré-declarado: `form_written_and_form_specific`

| braço | L1 | L2 | L3 | L4 | L5 | E |
|---|---|---|---|---|---|---|
| base (Qwen3.8-27B BF16, sem pensamento) | 4/24 | 1/24 | 0/24 | 0/24 | 0/24 | 0/24 |
| p1: forma de E/L5 gravada (96 exemplos) | 0/24 | 0/24 | 0/24 | 0/24 | **24/24** | **24/24** |
| p2: seis formas gravadas (288) | **24/24** | 0/24 | 7/24 | **24/24** | **24/24** | **24/24** |
| p3: controle de sintaxe (288) | 0/24 | 0/24 | 0/24 | 0/24 | 0/24 | 0/24 |

Regras (permutação por sinal sobre as seis instâncias retidas, unilateral, e diferença agrupada ≥ 0,25): **P1 confirmada**: p1 sobe em
L5 (+1,00, p = 0,016) e E (+1,00, p = 0,016) e em nenhum de L1–L4. **P2 confirmada**: p2 sobe em L1, L4, L5 e E (todos +0,83 a +1,00,
p = 0,016); L3 +0,29 (p = 0,062) e L2 não sobem. **P3 limpa**: o controle não sobe em degrau nenhum. Zero sessões não observadas.

## O que se mediu

1. **A forma curada pode ser escrita nos pesos e transfere para instâncias nunca vistas.** Com 96 exemplos (E e L5 de 48 instâncias de
   treino) e um LoRA de posto 16, o modelo resolve 48/48 alvos retidos de E e L5, todos no primeiro turno, todos com o esqueleto
   treinado (medida, lema do passo, ponte por indução, `Int.sq_nonneg` + `grind`). A base, no mesmo formato, resolve 0/48 (e 5/144 no
   total, sempre após vários turnos, com 15,6 mil tokens por sessão). O teto em contexto medido no piloto, com pensamento e
   ferramenta, era L5 0,50; gravado, sem pensamento, é 1,00 com 3 mil tokens por sessão.
2. **A transferência respeita a forma.** O p1 não move L1–L4; pior, aplica a forma de Pell a L1 (escreve `x·x − y·y` como medida em
   24/24 primeiras submissões, `grind` falha) e perde os 4/24 da base: transferência negativa entre formas, o mesmo fenômeno de A1 v3
   (a prova própria modular servia a L5 e não a L4), agora em pesos.
3. **O currículo escreve cada forma, e o que fica de fora é a inferência de parâmetros.** O p2 acerta 24/24 em L1, L4, L5 e E, cujas
   medidas se leem diretamente dos movimentos (diferença; deslocamentos; k; D). Em L2 (forma linear escondida α·x + β·y + z) escreve o
   esqueleto certo com coeficientes **chutados** (`1·x − 2·y + z`, `2·x + 2·y + z`… onde a verdadeira é, por exemplo, `−x − y + z`),
   e em L3 chuta c e n em `(x + c·y) % n` (7/24 certos). A forma foi gravada; resolver o sistema linear dos movimentos, não. É "forma,
   não ideia" dentro dos pesos: o que se consolida é o esqueleto, e o cálculo que preenche o esqueleto continua sendo do modelo.
4. **Sintaxe sozinha não escreve nada.** O p3, treinado com os mesmos mundos, cabeçalho e táticas num alvo não indutivo, produz 1 728
   arquivos em 144 sessões (12 turnos cada) e não resolve nenhum; também apaga os 4/24 da base em L1. O ganho de p1/p2 não é formato.

## Diagnósticos (não alteram escores; `docs/a2c_results/diagnostics.json`)

Soluções no primeiro turno: base 0/5, p1 48/48, p2 103/103. Tokens de saída por sessão: base 15 612, p1 3 078, p2 1 780, p3 3 971.
Formas das soluções: p1 100 % `aux_lemma + induction + grind`; p2 72 `grind` (L4/L5/E) e 31 `omega` (L1/L3); base sem lema auxiliar.
Perdas de treino: p1 0,47 → 2,5e-6 (9 épocas), p2 0,37 → 3,4e-3 (3), p3 0,22 → 2,4e-6 (3): os adaptadores decoraram os exemplos; a
transferência é para constantes novas, não para os exemplos.

## Operação e custo

Uma H200 (`8ff6i3zvid8p0c`), 413 min ≈ US$32 (saldo RunPod US$153,77 → US$121,96): instalação, fumaça de treino e de LoRA no vLLM
("OK"), portão de dados (576/576 exemplos aceitos pelo verificador real antes do treino), três adaptadores de ≈ 15 min, servidor BF16 +
LoRA, 576 sessões (base 1 h 50, p1 47 min, p2 45 min, p3 2 h 30), leitura e remoção pelo encadeamento. Zero Bedrock. Primeira tentativa
de pod caiu na instalação (PEP 668), 1,5 min, removido pelo trap. Stack: vLLM 0.29.0, transformers 5.17.0, peft 0.20.0, torch 2.13.

## O que não se afirma

Uma família de mundos, seis instâncias retidas, uma semente de treino: replicar com outra semente e outro sorteio antes de generalizar.
Nada sobre progressão nem invenção: a forma gravada é a curada, e L2 mostra que o que a forma não contém não aparece. A base sem
pensamento é fraca por formato; a comparação relevante é dentro do formato (as quatro condições), e o teto em contexto é referência
descritiva. Não se afirma nada sobre outros modelos, nem sobre o que o LoRA muda por dentro (A6 e a frente mecanística ficam com isso).

## Consequências

O programa tem o seu primeiro positivo em pesos abertos: o órgão que falta pode ser alimentado por consolidação curada, e o que ele
grava é a forma, com transferência dentro da forma e negativa entre formas. Próximos, por ordem: (1) replicação com nova semente de
treino e novo sorteio retido (≈ US$30); (2) A6, o modelo bayesiano do prior sobre formas, como análise secundária deste conjunto
(π: a forma aparece; θ: executa; L2 é o caso π sem θ); (3) paper 5, seção da alavanca: a tabela acima e a leitura de L2; (4) a pergunta
de composição: um adaptador com p2 mais exemplos de inferência de parâmetros escreve L2? é o teste de "forma + cálculo".
