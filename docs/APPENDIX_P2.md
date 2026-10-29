# Programa 2 — etapa 1 (transplantes diretos), corrida `stage1`

Saída de família = transplante válido com θ ≥ 1.1 fora de F0 (classificador pré-registrado).

| braço | modelo | entradas | tentativas | válidos | entradas c/ saída | entradas c/ F_rec | melhor θ |
|---|---|---|---|---|---|---|---|
| C1 | none | 84 | 84 | 67 (80%) | 1 | 21 | 1.10379 |
| C2 | kimi | 84 | 84 | 69 (82%) | 0 | 10 | 1.09573 |
| C2 | opus | 84 | 84 | 80 (95%) | 1 | 8 | 1.10379 |
| D | kimi | 84 | 168 | 55 (33%) | 2 | 7 | 1.10954 |
| D | opus | 84 | 168 | 160 (95%) | 78 | 70 | 1.11981 |
| D0 | kimi | 84 | 168 | 57 (34%) | 0 | 12 | 1.08148 |
| D0 | opus | 84 | 168 | 146 (87%) | 73 | 58 | 1.12396 |

## S1 (primário): D vs C2, pareado por entrada

| modelo | D só | C2 só | ambos | nenhum | p (sinal exato) | q (BH) |
|---|---|---|---|---|---|---|
| opus | 78 | 1 | 0 | 5 | 0.0000 | 0.0000 |
| kimi | 2 | 0 | 0 | 82 | 0.5000 | 0.5000 |

## Controle D0 (só o alvo, sem fonte): D vs D0, pareado por entrada (índice = mesma posição da biblioteca)

- opus: D só 11, D0 só 6, p = 0.3323; melhor θ D 1.11981 vs D0 1.12396; entradas c/ saída D 78 vs D0 73
- kimi: D só 2, D0 só 0, p = 0.5000; melhor θ D 1.10954 vs D0 1.08148; entradas c/ saída D 2 vs D0 0

## θ por família (melhor transplante válido por braço e família)

| braço | modelo | F0 | F_rec (sem vai-um) | other |
|---|---|---|---|---|
| C1 | none | 1.09573 (n=1) | 1.07045 (n=21) | 1.10379 (n=45) |
| C2 | kimi | 1.09573 (n=14) | 1.07045 (n=10) | 1.08865 (n=45) |
| C2 | opus | 1.09573 (n=1) | 1.04758 (n=8) | 1.10379 (n=71) |
| D | kimi | 1.09874 (n=3) | 1.10954 (n=7) | 1.10887 (n=45) |
| D | opus | 1.11533 (n=27) | 1.11981 (n=101) | 1.11362 (n=32) |
| D0 | kimi | 1.06512 (n=1) | 1.04397 (n=12) | 1.08148 (n=44) |
| D0 | opus | 1.11401 (n=36) | 1.12006 (n=79) | 1.12396 (n=31) |

## Depende da fonte? Família do transplante por grupo de origem (braço D)


D-opus:

| origem | F0 | F_rec | other | saídas (θ≥1.1) |
|---|---|---|---|---|
| autocorr1 | 3 | 8 | 4 | 9 |
| beatavg | 3 | 9 | 3 | 10 |
| beatavg20k | 5 | 6 | 4 | 9 |
| circlepack26 | 0 | 12 | 4 | 16 |
| classical-digit | 1 | 7 | 1 | 8 |
| classical-other | 2 | 9 | 3 | 11 |
| factn180 | 2 | 11 | 3 | 14 |
| heiltri11 | 4 | 8 | 1 | 9 |
| isofree64 | 2 | 10 | 3 | 13 |
| maxmin16 | 3 | 11 | 2 | 13 |
| ringload15 | 2 | 10 | 4 | 12 |

D-kimi:

| origem | F0 | F_rec | other | saídas (θ≥1.1) |
|---|---|---|---|---|
| autocorr1 | 0 | 0 | 11 | 0 |
| beatavg | 0 | 0 | 4 | 1 |
| beatavg20k | 1 | 1 | 7 | 1 |
| circlepack26 | 0 | 1 | 2 | 0 |
| classical-digit | 0 | 2 | 0 | 0 |
| classical-other | 0 | 1 | 3 | 0 |
| factn180 | 0 | 0 | 2 | 0 |
| heiltri11 | 1 | 0 | 1 | 0 |
| isofree64 | 0 | 0 | 6 | 0 |
| maxmin16 | 0 | 1 | 0 | 0 |
| ringload15 | 1 | 1 | 9 | 0 |

C1 (mecânico): 1 entradas com saída de família de 84; melhor θ 1.10379.

D-opus vs D-kimi (precisa de fronteira?): opus só 76, kimi só 0, p = 0.0000.

## Sementes da etapa 2 (top-5 por braço: saídas de família primeiro, depois θ)

| braço | k | θ | família | saída | origem (posição na biblioteca) |
|---|---|---|---|---|---|
| C1_none | 1 | 1.10379 | other | sim | classical/golomb_rulers.py |
| C1_none | 2 | 1.09573 | F0 | não | classical/two_block_difference_basis.py |
| C1_none | 3 | 1.08865 | other | não | classical/zeckendorf_sums.py |
| C1_none | 4 | 1.08149 | other | não | classical/bose_chowla_sidon.py |
| C1_none | 5 | 1.07104 | other | não | heiltri11/02_bddd5aed.py |
| C2_kimi | 1 | 1.09573 | F0 | não | classical/two_block_difference_basis.py |
| C2_kimi | 2 | 1.08865 | other | não | classical/zeckendorf_sums.py |
| C2_kimi | 3 | 1.08149 | other | não | classical/bose_chowla_sidon.py |
| C2_kimi | 4 | 1.07344 | F0 | não | autocorr1/01_1639b16d.py |
| C2_kimi | 5 | 1.07344 | F0 | não | autocorr1/03_e36f052c.py |
| C2_opus | 1 | 1.10379 | other | sim | classical/golomb_rulers.py |
| C2_opus | 2 | 1.09573 | F0 | não | classical/two_block_difference_basis.py |
| C2_opus | 3 | 1.08865 | other | não | classical/zeckendorf_sums.py |
| C2_opus | 4 | 1.08149 | other | não | classical/bose_chowla_sidon.py |
| C2_opus | 5 | 1.07017 | other | não | isofree64/01_77624586.py |
| D0_kimi | 1 | 1.08148 | other | não | beatavg/05_0f530018.py |
| D0_kimi | 2 | 1.07372 | other | não | classical/sum_free_upper_third.py |
| D0_kimi | 3 | 1.07038 | other | não | heiltri11/06_dac1c4f2.py |
| D0_kimi | 4 | 1.06947 | other | não | beatavg20k/03_e051a625.py |
| D0_kimi | 5 | 1.06512 | F0 | não | isofree64/07_2e0226ad.py |
| D0_opus | 1 | 1.12396 | other | sim | classical/cantor_integers.py |
| D0_opus | 2 | 1.12006 | F_rec | sim | ringload15/08_c9da13a0.py |
| D0_opus | 3 | 1.11877 | F_rec | sim | classical/sum_free_upper_third.py |
| D0_opus | 4 | 1.11786 | F_rec | sim | autocorr1/03_e36f052c.py |
| D0_opus | 5 | 1.11772 | other | sim | autocorr1/05_13b8d385.py |
| D_kimi | 1 | 1.10954 | F_rec | sim | beatavg20k/01_591c9e04.py |
| D_kimi | 2 | 1.10887 | other | sim | beatavg/01_0de334b1.py |
| D_kimi | 3 | 1.09874 | F0 | não | beatavg20k/05_1ad80c7c.py |
| D_kimi | 4 | 1.08988 | other | não | beatavg20k/03_e051a625.py |
| D_kimi | 5 | 1.08737 | other | não | beatavg20k/04_55d2cb8c.py |
| D_opus | 1 | 1.11981 | F_rec | sim | heiltri11/08_ed2de131.py |
| D_opus | 2 | 1.11729 | F_rec | sim | ringload15/06_8a33f5c7.py |
| D_opus | 3 | 1.11593 | F_rec | sim | circlepack26/06_261efad0.py |
| D_opus | 4 | 1.11567 | F_rec | sim | beatavg/03_30cf347e.py |
| D_opus | 5 | 1.11379 | F_rec | sim | maxmin16/05_71be1318.py |
