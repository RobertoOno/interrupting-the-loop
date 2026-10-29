# E5 — a lista vira régua? Resultados (leitura única em 2026-09-26 23:41 PDT; status: NEGATIVO como registrado — a lista continua lista)

*Pré-registro `docs/E5_LISTA_OU_REGUA_V1.md` (congelado em `7d1b2cb6`; emenda 1 em `5f91a59f`/`df1996d7`, antes de qualquer leitura
de retido: a dose de cinco não aprendeu a lista inteira no orçamento calibrado com a dose de dois e foi refeita com passos
proporcionais ao número de módulos novos). Seis corridas válidas no Mac (PyTorch/MPS, `caffeinate`, guarda térmica sem pausas):
D0 (o modelo E3 F = 8 cru, só avaliado), D2 (+11, +13) e D5 (+11, +13, +19, +23, +29), sementes 1 e 2; bateria 21:34–22:42 e
relançamento da dose 5 22:42–23:41 (≈ 2 h 07 de Mac, custo zero). Leitura por `scripts/e5_analysis.py` (commit `df1996d7`), uma
execução às 23:41:08, sobre 60 mundos retidos por módulo (17, 31, 37; 180 mundos compartilhados por todas as corridas, nenhum
excluído pelo certificado), 1 024 amostras por mundo a T = 1. Saídas em `docs/e5_results/` (`e5.json`, `e5.md`, `organ.json`);
figura `docs/figures/fig_e5_ruler.png`; evidência `docs/e5_evidence_v1/`.*

## Validade

| corrida | base preservada (V1) | lista aprendida (V2; nível 0 guloso) | pausas térmicas |
|---|---|---|---|
| D0 s1 / s2 | 59–60/60 em todos os degraus | — | 0 / 0 |
| D2 s1 / s2 | 59–60/60 | MN11 60/60, MN13 60/60 (ambas) | 0 / 0 |
| D5 s1 / s2 (10 000 passos) | 58–60/60 | MN11 60, MN13 60, MN19 60/59, MN23 59/59, MN29 60/59 | 0 / 0 |

As duas corridas D5 do orçamento original (4 000 passos; `runs/e/e5v1-D5-s{1,2}`) falharam V2 em módulos diferentes (MN29 54/60 e
MN23 55/60): sub-treino, não um módulo difícil; os seus retidos não foram lidos (só `config`, `level0`, `summary` e `train_log`
entram na evidência). Nos módulos consolidados, além do nível 0: pass@1 entre 0,974 e 0,9996 a 256 amostras, 60/60 mundos com
válida, bits da referência 0,0, p(n) = 1 na posição do módulo — **a lista foi aprendida por inteiro, em todas as doses**.

## A leitura nos módulos retidos

| dose | módulo | pass@1 | pass@1 024 (sementes) | mundos com válida | bits medianos | p(n verdadeiro): mediana / máximo | argmax na posição do módulo (s1) | módulo escrito, guloso (s1) |
|---|---|---|---|---|---|---|---|---|
| D0 | 17 | 0 | 0 (0 / 0) | 0 / 0 | 52,0 | ≈ 0 / 4 × 10⁻⁶ | 7: 53, 5: 4, 3: 3 | 7: 43, 5: 13, 3: 4 |
| D2 | 17 | 0 | 0 (0 / 0) | 0 / 0 | 33,1 | 4 × 10⁻⁶ / 8 × 10⁻⁵ | 13: 31, 11: 22, 7: 5 | 13: 27, 11: 25, 7: 6 |
| **D5** | **17** (interior) | 0 | **0,017 (0,017 / 0,017)** | **1 / 1** | 33,1 | **1,2 × 10⁻⁵ / 2,7 × 10⁻³** | 19: 21, 23: 14, 13: 10, 29: 10 | 23: 20, 29: 14, 19: 12, 13: 10 |
| D0 | 31 | 0 | 0 | 0 / 0 | 51,1 | ≈ 0 / 3 × 10⁻⁶ | 7: 53, 5: 5 | 7: 31, 5: 25 |
| D2 | 31 | 0 | 0 | 0 / 0 | 34,7 | 2 × 10⁻⁶ / 7 × 10⁻⁵ | 11: 28, 13: 28 | 13: 35, 11: 18 |
| D5 | 31 | 0 | 0 | 0 / 0 | 34,7 | 1 × 10⁻⁶ / 3 × 10⁻⁵ | 29: 32, 23: 16, 19: 7 | 23: 22, 29: 21, 19: 10 |
| D0 | 37 | 0 | 0 | 0 / 0 | 53,2 | ≈ 0 / 2 × 10⁻⁷ | 7: 58, 5: 2 | 7: 46, 5: 12 |
| D2 | 37 | 0 | 0 | 0 / 0 | 34,0 | 3 × 10⁻⁶ / 7 × 10⁻⁵ | 13: 38, 11: 22 | 13: 33, 11: 21 |
| D5 | 37 | 0 | 0 | 0 / 0 | 34,1 | 1 × 10⁻⁶ / 7 × 10⁻⁵ | 29: 34, 23: 16, 19: 8 | 29: 23, 23: 13, 19: 12 |

A única célula acima de zero é D5 em 17: **um mundo de 60 em cada semente** com alguma válida entre 1 024 amostras. É o que as
probabilidades medidas preveem por acaso de amostragem: somando p(17) × 1 024 sobre os 60 mundos, esperam-se 4,8 (s1) e 6,7 (s2)
amostras com o token 17 na posição certa; observou-se um mundo com válida em cada semente. Não é interpolação; é o token 17 sair
uma vez em 61 440 tentativas.

## Vereditos das regras registradas (expectativa registrada: todas falham)

- **R1 (interpolação; D5 em 17: pass@1 024 ≥ 0,5 e p(17) mediana ≥ 10⁻²)**: **falha** (0,017 e 1,2 × 10⁻⁵); nem "parcial" (< 0,05).
- **R2 (extrapolação; 31 ou 37 com pass@1 024 ≥ 0,5)**: **falha**; zero em todas as doses, 0 de 720 mundos-corrida.
- **R3 (dose; D5 − D2 em 17 ≥ 0,25 nas duas sementes)**: **falha** (+0,017 e +0,017).
- **R4 (eixo numérico; Spearman(n, projeção) ≥ 0,5 nos retidos em D5 e < 0,5 em D0)**: **falha**: melhor camada 0,32/0,39 em D5,
  0,15/0,10 em D0, 0,16/0,13 em D2.
- Validade: seis de seis válidas; nenhum mundo excluído; zero pausas térmicas.

## O que mudou com a consolidação (descritivo)

- **O preço do módulo novo caiu de ≈ 52 para ≈ 33 bits, igual em D2 e D5** — não porque o modelo se aproximou de 17, 31 ou 37, mas
  porque espalhou a massa por uma lista maior: por papel, em 17 (s1), coeficiente 16 → 12 → 14 bits e módulo 28 → 18 → 16 bits
  (D0 → D2 → D5). A mediana de p(n verdadeiro) sobe de ≈ 10⁻⁸ para ≈ 10⁻⁵ e para por aí.
- **O que o modelo escreve é sempre um membro da lista, com preferência pelos maiores**: em D0, 7; em D2, 13 e 11 (metade cada,
  para 17, 31 e 37 igualmente); em D5, para 31 e 37, o 29 (32–34 de 60 no argmax) e depois 23; para 17, espalha por 19, 23, 13 e
  29. O módulo escrito não acompanha o verdadeiro; o "maior conhecido" do E4 reaparece a cada lista.
- **A sonda**: os módulos do treino continuam legíveis (acurácia validada 0,96–0,99 nas camadas 5–7, oito classes em D5). Para os
  retidos, a projeção numérica em D5 coloca 17 em ≈ 16–19 (entre 13 e 19) e 31 e 37 em ≈ 23,5 (abaixo de 29): há ordem no interior
  e saturação no exterior, mas com variância grande (Spearman 0,26–0,39) e **já presente na camada 0** (17 → 16,2; 31 → 20,4;
  37 → 19,8 na saída do primeiro bloco): é sobretudo a magnitude dos números do enunciado, não um índice calculado. A acurácia
  validada entre os três retidos fica em 0,44–0,59 (acaso 0,33), como no E4.

## Leitura

Consolidar soluções verificadas com constantes novas, produzidas pelo órgão externo (proposta do modelo + busca sob o verificador:
191 de 200 recuperadas no controle), **acrescenta entradas à lista e nada mais**: cada módulo consolidado passa a ser resolvido no
teto; nenhum módulo entre os consolidados ou além deles é escrito com probabilidade acima de ≈ 10⁻⁵; a constante escrita é sempre
uma entrada da lista, de preferência das maiores; e o eixo numérico que ordenaria os valores novos não aparece por dentro além do
que as magnitudes do enunciado já dão. O resultado registrado como esperado é o que ocorreu, nas duas sementes, com a lista
integralmente aprendida (o que retira a explicação "faltou treino").

É o teste mais exato e mais barato que a série tinha da tese "consolidação = massa em alvos conhecidos, não fronteira" (paper 2,
paper 6, E2, E3): no substrato onde o prior é conhecido por construção, o laço que verifica e consolida move o teto para dentro
da lista e não move a lista para fora de si. Junto com o E3/E4: a diversidade compra a **forma** (onde o operador entra); a
consolidação compra **entradas**; nenhum dos dois compra a **régua**.

## O que não se afirma

Um operador, uma família (a rede 2D de índice n), duas sementes de treino, doses de 2 e 5, mistura 50/50 e 2 000 exemplos por
módulo; um modelo de 14 M. Não se testou dose maior que 5 nem módulos consolidados mais densos (por exemplo todos os primos até
29 exceto 17) — o desenho pré-registrado não os previa, e não serão acrescentados agora para "achar" o contraste. A parte "parcial"
da sonda pode ser toda de entrada. Nenhuma inferência sobre LLMs pré-treinados, que têm semântica numérica do pré-treino.

## Operação e custo

Mac só; PyTorch em MPS; treino 554–556 s (D2) e 1 390–1 393 s (D5 v2); amostragem 224–331 s por corrida; sondas em CPU/MPS; zero
pausas térmicas, nenhum aviso térmico do sistema. Custo zero. Pesos finais (55 MB cada), checkpoints e os corpora de consolidação
(`corpus/train_new.jsonl`, regeneráveis pelas sementes `e5-D<dose>-s<semente>-MN<n>-<i>`; SHA-256 em `summary.json`) ficam fora
do git em `runs/e/e5-*`; a evidência arquivada tem configurações, nível 0, amostras agregadas por mundo, inspeção da posição do
módulo, sondas, corpora retidos e de sonda, logs de treino e térmicos, e os logs da bateria.
