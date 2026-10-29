# E3 — o preço de um operador: resultados (leitura única em 2026-09-26 18:24 PDT; status: INTERESSANTE, com achado — a diversidade de famílias compra a estrutura do operador, não a faixa das suas constantes)

*Pré-registro `docs/E3_PRECO_DE_UM_OPERADOR_V1.md` (v1 congelada às 06:13 PDT; emendas 1–5, todas antes de qualquer leitura de amostra
retida; código da bateria v2.2 em `ddde9d3e`, emenda 5 em `d4657169`). Interpretação de cada desfecho escrita antes da leitura:
`docs/e3_results/INTERPRETACAO_PRE_LEITURA.md` (`5bbd16c0`). Trinta corridas (F ∈ {0, 1, 2, 4, 8} × três regimes de saída × duas
sementes) em duas fatias MIG 1g.24gb de RTX PRO 6000 Blackwell alugadas (pod A `urdq67hb42y07y`, semente 1; pod B `frf8oke32pq0wv`,
semente 2; US$0,59/h cada). Leitura por `scripts/e3_analysis.py` (commit `4db6e06f`), uma execução, às 18:24:40 PDT, sobre as cópias
leves verificadas por SHA-256 contra os pods (ver "Operação"); saídas em `docs/e3_results/` (`e3.json`, `e3.md`, `kinds.md`,
`INTERPRETACAO_PRE_LEITURA.md`) e figura `docs/figures/fig_e3_price.png` (`scripts/e3_figures.py`, gerada do JSON). Todas as 30
corridas válidas pela regra M1 da emenda 5; cinco seriam excluídas pela regra estrita original (abaixo); nenhum mundo retido excluído
pelo certificado (M2); zero pausas térmicas. Evidência: `docs/e3_evidence_v1/` (amostras agregadas por mundo, sumários, configurações,
curvas de treino, manifestos e mundos retidos dos corpora, logs; pesos finais e corpora de treino fora do git, em `runs/e3a4` e
`runs/e3b4`, com SHA-256 nos sumários).*

## A tabela da leitura (média das duas sementes por célula; 60 mundos retidos por família, 1 024 amostras por mundo a T = 1)

| regime | family | F | seeds | bits ref (mean of medians) | pass@1 | pass@1024 | valid rate | pi (first sample) | theta given kind |
|---|---|---|---|---|---|---|---|---|---|
| raw | M2 | 0 | 2 | 109.26 | 0.0 | 0.0 | 0 | 0.0 | 0.0 |
| raw | M2 | 1 | 2 | 41.57 | 0.0 | 0.0 | 0 | 1.0 | 0.0 |
| raw | M2 | 2 | 2 | 44.81 | 0.0 | 0.0 | 0 | 1.0 | 0.0 |
| raw | M2 | 4 | 2 | 45.67 | 0.0 | 0.0 | 0 | 1.0 | 0.0 |
| raw | M2 | 8 | 2 | 54.89 | 0.0 | 0.0 | 0 | 1.0 | 0.0 |
| raw | M2 | Spearman(F, bits) = 0.0; F_min(pass@1024 > 0.5) = None |  |  |  |  |  |  |  |  |
| raw | M6 | 0 | 2 | 76.84 | 0.0 | 0.0 | 0 | 0.0 | 0.0 |
| raw | M6 | 1 | 2 | 25.43 | 0.0059 | 0.1667 | 0.00588 | 0.117 | 0.108 |
| raw | M6 | 2 | 2 | 20.33 | 0.0779 | 0.3667 | 0.0779 | 0.258 | 0.279 |
| raw | M6 | 4 | 2 | 14.76 | 0.2113 | 0.5333 | 0.211 | 0.442 | 0.455 |
| raw | M6 | 8 | 2 | 14.23 | 0.2327 | 0.45 | 0.233 | 0.533 | 0.475 |
| raw | M6 | Spearman(F, bits) = -1.0; F_min(pass@1024 > 0.5) = 4 |  |  |  |  |  |  |  |  |
| named | M2 | 0 | 2 | 53.1 | 0.0 | 0.0 | 0 | 0.0 | 0.0 |
| named | M2 | 1 | 2 | 42.55 | 0.0 | 0.0 | 0 | 1.0 | 0.0 |
| named | M2 | 2 | 2 | 40.92 | 0.0 | 0.0 | 0 | 1.0 | 0.0 |
| named | M2 | 4 | 2 | 39.9 | 0.0 | 0.0 | 0 | 0.967 | 0.0 |
| named | M2 | 8 | 2 | 39.39 | 0.0 | 0.0 | 0 | 0.883 | 0.0 |
| named | M2 | Spearman(F, bits) = -1.0; F_min(pass@1024 > 0.5) = None |  |  |  |  |  |  |  |  |
| named | M6 | 0 | 2 | 63.66 | 0.0 | 0.0 | 0 | 0.0 | 0.0 |
| named | M6 | 1 | 2 | 51.91 | 0.0 | 0.0 | 0 | 0.008 | 0.0 |
| named | M6 | 2 | 2 | 17.37 | 0.068 | 0.425 | 0.068 | 0.317 | 0.228 |
| named | M6 | 4 | 2 | 36.94 | 0.0088 | 0.225 | 0.00877 | 0.025 | 0.465 |
| named | M6 | 8 | 2 | 37.55 | 0.0047 | 0.1083 | 0.00469 | 0.042 | 0.101 |
| named | M6 | Spearman(F, bits) = -0.6; F_min(pass@1024 > 0.5) = None |  |  |  |  |  |  |  |  |
| bottleneck | M2 | 0 | 2 | 124.9 | 0.0 | 0.0 | 0 | 0.0 | 0.0 |
| bottleneck | M2 | 1 | 2 | 41.1 | 0.0 | 0.0 | 0 | 0.983 | 0.0 |
| bottleneck | M2 | 2 | 2 | 43.73 | 0.0 | 0.0 | 0 | 1.0 | 0.0 |
| bottleneck | M2 | 4 | 2 | 44.63 | 0.0 | 0.0 | 0 | 1.0 | 0.0 |
| bottleneck | M2 | 8 | 2 | 59.34 | 0.0 | 0.0 | 0 | 0.983 | 0.0 |
| bottleneck | M2 | Spearman(F, bits) = 0.0; F_min(pass@1024 > 0.5) = None |  |  |  |  |  |  |  |  |
| bottleneck | M6 | 0 | 2 | 73.13 | 0.0 | 0.0 | 0 | 0.0 | 0.0 |
| bottleneck | M6 | 1 | 2 | 23.45 | 0.029 | 0.2083 | 0.029 | 0.375 | 0.12 |
| bottleneck | M6 | 2 | 2 | 15.89 | 0.1071 | 0.4833 | 0.107 | 0.392 | 0.285 |
| bottleneck | M6 | 4 | 2 | 8.61 | 0.322 | 0.625 | 0.322 | 0.625 | 0.522 |
| bottleneck | M6 | 8 | 2 | 9.51 | 0.3363 | 0.65 | 0.336 | 0.75 | 0.451 |
| bottleneck | M6 | Spearman(F, bits) = -0.9; F_min(pass@1024 > 0.5) = 4 |  |  |  |  |  |  |  |  |

Por semente (`e3.json`, `cells`), os pontos que decidem as regras: M6 cru, pass@1 024 = 0,283/0,050 (F = 1), 0,400/0,333 (F = 2),
0,483/0,583 (F = 4), **0,600/0,300 (F = 8)**; bits medianos 20,8/30,0, 14,0/26,6, 19,5/10,0, 9,2/19,3. M6 gargalo: 0,017/0,400,
0,517/0,450, 0,567/0,683, 0,633/0,667; bits 30,6/16,3, 19,4/12,4, 10,8/6,4, 10,6/8,4. M6 nomeado: 0/0, 0,383/0,467, 0,133/0,317,
0,167/0,050. M2: zero válidas em todas as 30 células (614 400 amostras por regime, 1 843 200 no total); bits medianos no cru 42,4/40,7
(F = 1) → 50,9/58,9 (F = 8), mínimo por célula entre 21 e 38 bits (o mundo mais barato ainda custa ≥ 21 bits, p < 10⁻⁶ por amostra).

Nível 0 (degraus treinados, guloso): todas as 30 corridas passam a regra da emenda 5 (`e3.md`, tabela final): famílias de `mod` entre
57/60 e 60/60; L1 60/60 em todas; E entre 51/60 e 60/60 (51 e 53 só em cinco corridas de F ≤ 1 da regra estrita, abaixo).

## Vereditos das regras registradas

- **P1 (o operador entra por diversidade; regime cru: Spearman(F, bits) ≤ −0,5 e pass@1 024 > 0,5 em F = 8, por família retida)**:
  **falha nas duas famílias, por razões opostas.** Em **M2** (módulo fora da faixa do treino) falha por completo: Spearman = 0,0
  (os bits caem de 109 para 42 ao entrar a primeira família de `mod` e depois **sobem** até 55 em F = 8, nas duas sementes: 42,4 → 50,9
  e 40,7 → 58,9) e pass@1 024 = 0 em todo F. Em **M6** (estrutura nova, módulos dentro da faixa) a curva faz o que P1 previa —
  Spearman = −1,0, bits de 77 para 14, pass@1 024 de 0 para 0,53 em F = 4 — e **falha só no limiar de F = 8: 0,45**, média de 0,60 e 0,30
  nas duas sementes. A regra cai; a leitura registrada para "falha nas duas" ("até oito famílias não compram o operador") descreve M2 e
  não descreve M6, onde oito famílias compram a metade do teto. O desfecho não previsto fica na seção "O que a leitura acrescentou".
- **P2 (abstração substitui diversidade; F_min do nomeado ou do gargalo < F_min do cru)**: **falha pela regra.** Em M6, F_min = 4 no
  cru e 4 no gargalo (empate) e "nunca" no nomeado; em M2 nenhum regime atinge pass@1 024 > 0,5 (não avaliável). A grade de F
  (1, 2, 4, 8) não tem resolução para separar 4 de 3; o descritivo fica abaixo.
- **P3 (seleção antes da execução; nomeado ou gargalo com π ≥ 0,5 e taxa de válidas < 0,25 em algum F)**: **vale em M2, falha em M6.**
  Em M2, a partir de F = 1, a primeira amostra é do tipo `linear_mod` em 97–100 % dos mundos (nomeado 77–100 %) e nenhuma das 1 024 é
  válida: a seleção do operador é certa e total, a execução é nula. Em M6, sempre que π ≥ 0,5 a taxa de válidas está acima de 0,25
  (gargalo F = 4: π 0,63, válidas 0,32; F = 8: π 0,75, válidas 0,34) e θ (válidas entre as do tipo certo) fica em 0,45–0,52: seleção e
  execução sobem juntas.
- **Mortes.** M1 (emenda 5): nenhuma corrida inválida. Regra estrita original (0,95 em todo degrau): excluiria `e3-F0-named-s2` (E 0,85),
  `e3-F0-bottleneck-s2` (E 0,883), `e3-F1-named-s1` (E 0,883), `e3-F1-bottleneck-s1` (E 0,883) e `e3-F1-bottleneck-s2` (E 0,85); com
  essas exclusões os vereditos são idênticos: P1 só usa o cru (nenhuma corrida crua excluída), os F_min de P2 vêm de F ≥ 2, e P3 em M2
  vale em F = 2, 4 e 8. M2 (certificado): nenhum mundo retido excluído. Falsificador/acaso: a taxa de acaso da gramática para
  `linear_mod` é a do E2 (≤ 0,005); as células com válidas em M6 estão ordens de grandeza acima; as de M2 estão em zero exato.

## O que os modelos escrevem (diagnóstico com os dados da leitura, `docs/e3_results/kinds.md`; sem regra)

- **M2: o operador certo com constantes do treino, sempre.** Nos três regimes, de F = 1 a F = 8, 94–100 % das 1 024 amostras por mundo
  são `linear_mod` bem formadas, e zero são válidas. O único jeito de uma `linear_mod` bem formada falhar em M2 é o módulo (a
  referência exige n ∈ {11, 13, 17, 19}; o treino só tem {3, 5, 7}); com 1 843 200 amostras sem nenhuma válida, o módulo nunca sai da
  faixa do treino (probabilidade < 10⁻⁶ por amostra). É o W4 do E2, agora com a dose medida: a faixa das constantes não se compra com
  famílias — e mais famílias com os mesmos módulos deixam a referência ainda mais improvável (bits sobem 42 → 55 no cru, 41 → 59 no
  gargalo; no nomeado ficam em ≈ 40).
- **M6: o que falta é a forma, não o tipo.** Fora das `linear_mod`, a massa das amostras é **inválida** (não analisável pela gramática):
  no cru, a fração de `linear_mod` bem formadas vai de 0,28/0,00 (F = 1) a 0,88/0,18 (F = 8); no gargalo, de 0,00/0,78 a 0,73/0,76; e
  entre as bem formadas do tipo certo, cerca de metade é válida em F ≥ 4 (θ 0,4–0,57). A semente 2 do cru em F = 1 escreve em 75 % das
  amostras a **forma linear exata do plano** (o invariante que se conserva e não separa: a armadilha desenhada, o mesmo modo do E2 em W2
  e do adaptador curado do paper 6); a partir de F = 2 essa forma some (≤ 2 %).
- **Dentro de M6, o que se resolve é a forma de dois campos** (`docs/e3_results/m6_forms.md`). Cerca de 30 % dos mundos retidos de M6
  têm invariante de um só campo (`mod y k`, quando o coeficiente de x é ≡ 0 mod k): esses ficam em zero ou quase em todo F e regime
  (0–4 mundos de 11–21 por corrida; taxa de válidas ≤ 0,04, uma exceção em 0,115), enquanto os de dois campos (`mod (x + c·y) k`) são
  os que a diversidade compra (até 34–37 de ≈ 41 mundos, taxa 0,5–0,59 em F = 8). A forma de dois campos em mundos de três campos
  entra no treino em F = 2 (M10: campo livre z, sem armadilha); a forma de um só campo num mundo de três campos não está no treino
  (M8, `y mod n`, tem dois campos e alvo parametrizado). O ganho de F = 2 para F = 4 (M3, M12) é real nas duas sementes do cru e do
  gargalo; de F = 4 para F = 8, não.
- **O regime nomeado colapsa em M6 a partir de F = 4**: 95–98 % das amostras são chamadas de operador **malformadas** (não analisáveis
  pela DSL), nas duas sementes; em F = 2 (com M10, a primeira família de três campos no treino) o nomeado ainda escrevia `LINMOD` bem
  formada em 28–31 % e chegava a pass@1 024 = 0,38/0,47. O nome do operador não ajuda e a sua sintaxe com aridade variável quebra quando
  as famílias de treino misturam 2, 3 e 4 campos. Em M2 (dois campos, como M1) o nomeado é bem formado em 75–100 %.
- **Variância entre sementes de treino** é grande em M6: em F = 8 cru, 36 contra 18 mundos com alguma válida; π 0,88 contra 0,18. Com
  duas sementes, o limiar de P1 em F = 8 (0,45 contra 0,5) está dentro dessa variância.

## Leitura

O preço de um operador tem, neste substrato, duas partes que a diversidade de famílias trata de modos opostos:

1. **A estrutura** (onde `mod` entra: três campos, geradores num plano com armadilha, alvo novo) **é comprada pela diversidade**,
   monotonicamente até F = 4: os bits da referência caem cinco vezes (77 → 14 no cru, 73 → 9,5 no gargalo) e pass@1 024 vai de 0 a
   0,45–0,65, com metade dos mundos resolvidos a partir de F = 4. Com uma só família de `mod` (F = 1, o regime do E2) a transferência
   é marginal (17 e 3 mundos de 60) e uma das sementes cai na armadilha do plano. Precisão necessária: o que se transfere é uma **forma
   treinada** (`mod` de uma combinação de x e y, que entra em mundos de três campos com M10 em F = 2) para uma família nova que tem a
   armadilha e outros geradores/alvos, e o ganho continua com M3 e M12 em F = 4; a forma de um só campo, que nenhum mundo de três
   campos do treino tem, não é comprada. O "prior é o conjunto de famílias" do E2 é, para a estrutura, o regime de baixa diversidade;
   com diversidade, o prior passa a ser o conjunto de **formas**, aplicáveis a famílias novas.
2. **A faixa das constantes não é comprada** por diversidade de famílias, em dose nenhuma até 8: um módulo fora do treino custa ≈ 40 bits
   por mundo e nunca é escrito. Aqui o E2 se fortalece: o prior é o conjunto de constantes vistas, e mais famílias com as mesmas
   constantes o apertam.

Os regimes de saída separam-se pelo mesmo eixo. O **gargalo de tipo** (`KIND` antes da expressão) ajuda a estrutura em todos os F ≥ 2
de M6 na média e nas duas sementes em F = 4 e F = 8 (pass@1 024 0,57/0,68 e 0,63/0,67 contra 0,48/0,58 e 0,60/0,30 do cru) e não
move a faixa; o **operador nomeado** não ajuda a faixa e destrói a estrutura por um defeito de forma (chamadas malformadas com
famílias de aridade mista). P2 falha pela regra (a grade não resolve), mas a direção é a que a hipótese esperava para o gargalo e a
contrária para o nome. A dissociação seleção/execução de P3 é, aqui, **um fenômeno de faixa**: total onde a constante está fora do
treino (M2: tipo certo em 100 %, válidas 0) e ausente onde está dentro (M6: θ ≈ 0,5). É a versão exata do "tipo certo, parâmetros
errados" do adaptador do paper 6, com a causa nomeada: o modelo pequeno não tem de onde tirar a constante.

Relação com o que o campo sabe: que constantes fora da faixa de treino não se extrapolam num transformer pequeno é conhecido
(generalização de comprimento e de valores numéricos); que diversidade de tarefas correlaciona com generalização composicional também
(arXiv:2609.13144, qualitativo). O que esta bateria acrescenta é a **separação, dentro de um só operador e sob a mesma manipulação, da
parte que a diversidade compra (estrutura, ×5 em bits, monotônica) e da parte que ela não compra e até encarece (faixa)**, com verificador
exato, e o efeito dos dois regimes de abstração na saída: um gargalo de tipo barateia a estrutura, um nome com sintaxe própria a
encarece. Não é uma lei com fórmula: é uma decomposição medida.

## O que a leitura acrescentou (fora dos blocos escritos antes)

- O desfecho "P1 falha nas duas" não era o previsto para o padrão observado: os blocos pré-escritos separavam "faixa, não forma"
  (vale em M2 e não em M6) de "falha nas duas"; o que ocorreu é **forma, não faixa** (a diversidade compra M6 e não M2), a alternativa
  que o texto pré-leitura chamou de improvável "pelo E2". O E2 mostrou o esqueleto certo com módulos do treino em W4; a inferência de que
  a estrutura também não viria estava errada.
- A divisão de M6 por forma do invariante (um campo contra dois) não estava prevista: mostra que a diversidade compra a transferência
  de formas treinadas a famílias novas, não formas ausentes; "estrutura nova" no protocolo era a família (armadilha, geradores,
  alvo), não a forma do invariante, e a leitura precisa dizer as duas coisas.
- O colapso de forma do regime nomeado com aridade mista não estava previsto; é defeito da DSL (`operators.py`), não evidência sobre
  abstração. Uma DSL com aridade fixa por operador ou um token de aridade corrigiria; não foi testado.
- A diferença entre F = 1 aqui (17/60 e 3/60 mundos de M6 com válida) e o C0 do E2 (0/180 em W2) é de orçamento: o fundo do E3 tem
  duas famílias (L1, E) a 25 000 exemplos e M1 a 15 000, contra seis degraus a ≈ 16 700 no E2; a família de `mod` pesa mais no E3.

## O que não se afirma

Um operador (`mod`), um tamanho de modelo (14 M, fixado no E1), **duas sementes de treino** (a variância entre elas em M6 é da ordem do
efeito entre níveis vizinhos de F), duas famílias retidas (uma por componente do preço), F ≤ 8 numa grade grosseira, famílias desenhadas
por nós numa gramática de brinquedo. O fundo (L1, E) não é medido como resultado. "Inválida" quer dizer não analisável pela gramática e
não foi decomposta. Nada aqui é inferência sobre LLMs pré-treinados sem a medida correspondente no modelo real. Nenhum mecanismo foi
observado nos pesos.

## Operação e custo

Pods criados às 13:50:35 (A) e 13:51:37 (B) PDT, commit `ddde9d3e`; 15 corridas cada, 18–30 min por corrida, zero erros, zero pausas
térmicas; última corrida concluída às 18:19:52 (A) e 18:19:54 (B). O tarball completo dos scripts (pesos finais, checkpoints e corpora,
4,38 GB por pod, porque o `--exclude` do `tar` veio depois dos operandos e não se aplicou) descia a ≈ 0,8–1,3 MB/s; como uma falha
nessa transferência faria o trap remover o pod com os dados, às 18:24 puxei de cada pod uma **cópia leve** (tudo menos pesos, checkpoints
e `train.jsonl`; 7,2 MB; SHA-256 `af9a15ca…` para A e `840f8cf6…` para B, conferidos contra o pod) e fiz a leitura sobre ela. O
download completo continuou pelo script; remoção dos pods, hora e custo final registrados no fechamento abaixo. Saldo RunPod
US$93,69 na hora da leitura. Custo do E3 inteiro: v1 ≈ US$2,90, v2 ≈ US$1,20, v2.1 ≈ US$0,80, lançamento malformado ≈ US$0,06, cheque
em pod ≈ US$0,30, mais a v2.2 (dois pods a US$0,59/h do lançamento à remoção).

## Fechamento (2026-09-26 19:50 PDT)

Downloads completos com checksum: pod B às 19:43:16 (351 min de script), pod A às 19:50:05 (359 min); remoção automática pelo trap
em seguida; a API listou zero pods às 19:50:28, gasto por hora zero. Pod A: 13:50:35 → 19:50:05 = 359,5 min; pod B: 13:51:37 →
19:43:16 = 351,6 min; total 711,1 min = 11,85 h a US$0,59/h = **US$6,99 na v2.2**; E3 inteiro ≈ **US$12,3** (com v1 ≈ 2,90, v2 ≈ 1,20,
v2.1 ≈ 0,80, incidente 0,06, cheque 0,30). Saldo RunPod US$92,07 após a remoção (US$93,69 na leitura, US$97,25 às 15:26).
Verificação: os 135 arquivos da cópia leve de cada pod são byte-idênticos aos mesmos caminhos do download completo (`scripts/e3_close.py`,
SHA-256 por arquivo): a leitura das 18:24 e o download completo são os mesmos dados. Evidência: `docs/e3_evidence_v1/` (312 arquivos,
15 MB, manifesto SHA-256 verificado): por corrida, `config.json`, `eval.jsonl`, `heartbeat.json`, `samples.jsonl`, `summary.json`,
`thermal_log.jsonl`, `train_log.jsonl`, `corpus/heldout.jsonl` e `corpus/manifest.json`, mais os 30 logs de execução, os dois `pod.log`
e os documentos do E3. Pesos finais (`final.safetensors`, 55 MB cada), checkpoints e corpora de treino ficam fora do git em
`runs/e3a4/e3_from_pod` e `runs/e3b4/e3_from_pod` (SHA-256 em `files_sha256` de cada `summary.json`); os 30 modelos com pesos estão
ligados em `runs/e/e3_all_full` para o E4.

## Próximos passos possíveis (decisão com o Roberto; nenhum admitido)

Cada opção com o que o campo já sabe e o que acrescentaria, pela regra permanente:

1. **Mecanismo da compra de estrutura** (o que muda nos pesos entre F = 1 e F = 8 que faz M6 resolvível; um circuito de `mod`
   compartilhado?). Sabido: circuitos modulares em modelos pequenos treinados numa tarefa (grokking de adição modular). Acrescentaria:
   como a diversidade de famílias constrói um circuito reutilizável, medido com o mesmo verificador. Custo: Mac, pesos já baixados.
2. **Por que o gargalo ajuda e o nome atrapalha** (replicar com mais sementes e uma DSL de aridade fixa; ligação com o ramo D, módulos
   de interface). Sabido: tokens de "plano" ou de tipo ajudam composição em contexto (arXiv:2407.12275). Acrescentaria: se um token de
   tipo na saída barateia a estrutura dentro dos pesos. Custo ≈ US$3–5 por rodada de 12 corridas.
3. **A faixa** (mais módulos no treino, retendo alguns: interpolação contra extrapolação). Sabido em boa parte (extrapolação numérica
   falha, interpolação parcial); pouca contribuição — só como controle se um paper precisar, e dizendo que serve ao paper.
4. **O elo com o modelo real**: bits do tipo de invariante necessário no Qwen, separando estrutura e constantes, nas famílias de parede
   do paper 6 e nos adaptadores do laço. Sabido: log-verossimilhança de soluções de referência prevê ganhos de RFT/RL. Acrescentaria:
   se a decomposição estrutura/faixa explica quais paredes o laço subiu (W4 é um módulo fora da faixa; W2 é a armadilha do plano).
   Custo: algumas horas de H200 (≈ US$15–25).
