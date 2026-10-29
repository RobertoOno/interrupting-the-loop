> **Aviso (auditoria de fechamento, 2026-09-04)**: este apêndice é a leitura única original e foi preservado sem edição.
> O endpoint de família aqui foi calculado só sobre `best.py`, que não existe quando a semente continuou sendo o melhor
> (família `None`) e que omite o prelúdio com que o candidato foi verificado. A frase "nenhuma saída de família em D/D0"
> significa "nenhuma saída **nova** produzida pelo laço", não "nenhum final fora de F0". Leitura corrigida, três quantidades
> separadas (herdada / nova / final), materialização por replay e unidade de inferência por semente:
> `docs/APPENDIX_P2_STAGE2_AUDIT.md`.

# Programa 2 — etapa 2 (laço a partir dos transplantes), leitura única

108 corridas; saída de família = final com θ ≥ 1.1 fora de F0; bits = log2 do índice da primeira amostra válida que atinge a fração do gap semente → 1.1479 (AE no teto), censurado.

| braço | corridas | válidos/corrida | θ semente (média) | melhor θ (média) | melhor do braço | melhorou a semente | saídas | F_rec | bits50 (média) | bits90 (média) |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 3 | 76 | 1.0792 | 1.0976 | 1.10436 | 3 | 0 | 0 | nan (0 atingem) | nan (0 atingem) |
| C1_none | 15 | 63 | 1.0881 | 1.0883 | 1.10379 | 6 | 0 | 0 | nan (0 atingem) | nan (0 atingem) |
| C2_kimi | 15 | 84 | 1.0825 | 1.0889 | 1.10556 | 13 | 3 | 0 | nan (0 atingem) | nan (0 atingem) |
| C2_opus | 15 | 83 | 1.0880 | 1.0921 | 1.10769 | 10 | 2 | 0 | nan (0 atingem) | nan (0 atingem) |
| D0_kimi | 15 | 47 | 1.0720 | 1.0777 | 1.10229 | 14 | 0 | 1 | nan (0 atingem) | nan (0 atingem) |
| D0_opus | 15 | 57 | 1.1192 | 1.1197 | 1.12396 | 7 | 0 | 0 | nan (0 atingem) | nan (0 atingem) |
| D_kimi | 15 | 52 | 1.0989 | 1.0992 | 1.10954 | 6 | 0 | 0 | nan (0 atingem) | nan (0 atingem) |
| D_opus | 15 | 58 | 1.1165 | 1.1165 | 1.11981 | 6 | 0 | 0 | nan (0 atingem) | nan (0 atingem) |

## S2 (primário): saídas de família por corrida, Fisher exato; melhor θ, Mann–Whitney

| contraste | saídas | p Fisher | melhor θ (médias) | p MW |
|---|---|---|---|---|
| D_opus vs C2_opus | 0/15 vs 2/15 | 0.4828 | 1.1165 vs 1.0921 | 0.0000 |
| D_opus vs C1_none | 0/15 vs 0/15 | 1.0000 | 1.1165 vs 1.0883 | 0.0000 |
| D_opus vs D0_opus | 0/15 vs 0/15 | 1.0000 | 1.1165 vs 1.1197 | 0.0006 |
| D_kimi vs C2_kimi | 0/15 vs 3/15 | 0.2241 | 1.0992 vs 1.0889 | 0.0047 |
| D_kimi vs D0_kimi | 0/15 vs 0/15 | 1.0000 | 1.0992 vs 1.0777 | 0.0000 |
| D0_opus vs A | 0/15 vs 0/3 | 1.0000 | 1.1197 vs 1.0976 | 0.0088 |
| D_opus vs A | 0/15 vs 0/3 | 1.0000 | 1.1165 vs 1.0976 | 0.0086 |

## Corridas

| corrida | semente | melhor | válidos | família | saída | bits50 | bits90 |
|---|---|---|---|---|---|---|---|
| A_s2 | 1.0792 | 1.10436 | 63/200 | None | não | — | — |
| A_s1 | 1.0792 | 1.10220 | 44/200 | F0 | não | — | — |
| A_s0 | 1.0792 | 1.08618 | 120/200 | F0 | não | — | — |
| C1_none_k1_s0 | 1.1038 | 1.10379 | 139/200 | None | não | — | — |
| C1_none_k1_s1 | 1.1038 | 1.10379 | 44/200 | None | não | — | — |
| C1_none_k1_s2 | 1.1038 | 1.10379 | 125/200 | None | não | — | — |
| C1_none_k2_s0 | 1.0957 | 1.09573 | 26/200 | None | não | — | — |
| C1_none_k2_s1 | 1.0957 | 1.09573 | 55/200 | None | não | — | — |
| C1_none_k2_s2 | 1.0957 | 1.09573 | 57/200 | None | não | — | — |
| C1_none_k3_s0 | 1.0887 | 1.08865 | 0/200 | None | não | — | — |
| C1_none_k3_s1 | 1.0887 | 1.08865 | 0/200 | None | não | — | — |
| C1_none_k3_s2 | 1.0887 | 1.08865 | 0/200 | None | não | — | — |
| C1_none_k4_s0 | 1.0815 | 1.08149 | 53/200 | None | não | — | — |
| C1_none_k4_s1 | 1.0815 | 1.08149 | 114/200 | None | não | — | — |
| C1_none_k4_s2 | 1.0815 | 1.08149 | 58/200 | None | não | — | — |
| C1_none_k5_s2 | 1.0710 | 1.07268 | 49/200 | other | não | — | — |
| C1_none_k5_s0 | 1.0710 | 1.07187 | 123/200 | other | não | — | — |
| C1_none_k5_s1 | 1.0710 | 1.07152 | 103/200 | other | não | — | — |
| C2_kimi_k2_s2 | 1.0887 | 1.10556 | 57/200 | other | sim | — | — |
| C2_kimi_k2_s0 | 1.0887 | 1.10502 | 39/200 | other | sim | — | — |
| C2_kimi_k2_s1 | 1.0887 | 1.10067 | 157/200 | other | sim | — | — |
| C2_kimi_k1_s0 | 1.0957 | 1.09726 | 101/200 | F0 | não | — | — |
| C2_kimi_k1_s2 | 1.0957 | 1.09628 | 49/200 | None | não | — | — |
| C2_kimi_k1_s1 | 1.0957 | 1.09573 | 111/200 | None | não | — | — |
| C2_kimi_k5_s1 | 1.0734 | 1.08371 | 23/200 | None | não | — | — |
| C2_kimi_k4_s1 | 1.0734 | 1.08363 | 37/200 | None | não | — | — |
| C2_kimi_k3_s2 | 1.0815 | 1.08154 | 117/200 | other | não | — | — |
| C2_kimi_k3_s0 | 1.0815 | 1.08149 | 124/200 | None | não | — | — |
| C2_kimi_k3_s1 | 1.0815 | 1.08149 | 185/200 | None | não | — | — |
| C2_kimi_k5_s2 | 1.0734 | 1.08104 | 107/200 | None | não | — | — |
| C2_kimi_k4_s2 | 1.0734 | 1.08089 | 84/200 | None | não | — | — |
| C2_kimi_k5_s0 | 1.0734 | 1.08089 | 23/200 | None | não | — | — |
| C2_kimi_k4_s0 | 1.0734 | 1.07854 | 43/200 | None | não | — | — |
| C2_opus_k3_s2 | 1.0887 | 1.10769 | 92/200 | other | sim | — | — |
| C2_opus_k1_s2 | 1.1038 | 1.10692 | 15/200 | None | não | — | — |
| C2_opus_k3_s0 | 1.0887 | 1.10603 | 11/200 | other | sim | — | — |
| C2_opus_k1_s0 | 1.1038 | 1.10379 | 66/200 | None | não | — | — |
| C2_opus_k1_s1 | 1.1038 | 1.10379 | 79/200 | None | não | — | — |
| C2_opus_k2_s0 | 1.0957 | 1.09726 | 81/200 | F0 | não | — | — |
| C2_opus_k2_s1 | 1.0957 | 1.09726 | 164/200 | F0 | não | — | — |
| C2_opus_k2_s2 | 1.0957 | 1.09679 | 116/200 | F0 | não | — | — |
| C2_opus_k4_s1 | 1.0815 | 1.09114 | 162/200 | other | não | — | — |
| C2_opus_k4_s0 | 1.0815 | 1.08900 | 10/200 | None | não | — | — |
| C2_opus_k3_s1 | 1.0887 | 1.08865 | 93/200 | None | não | — | — |
| C2_opus_k4_s2 | 1.0815 | 1.08224 | 105/200 | None | não | — | — |
| C2_opus_k5_s2 | 1.0702 | 1.07032 | 25/200 | None | não | — | — |
| C2_opus_k5_s0 | 1.0702 | 1.07017 | 65/200 | None | não | — | — |
| C2_opus_k5_s1 | 1.0702 | 1.07017 | 157/200 | None | não | — | — |
| D0_kimi_k3_s2 | 1.0704 | 1.10229 | 21/200 | None | não | — | — |
| D0_kimi_k5_s0 | 1.0651 | 1.09017 | 9/200 | None | não | — | — |
| D0_kimi_k1_s2 | 1.0815 | 1.08649 | 69/200 | other | não | — | — |
| D0_kimi_k1_s1 | 1.0815 | 1.08152 | 153/200 | other | não | — | — |
| D0_kimi_k1_s0 | 1.0815 | 1.08148 | 118/200 | None | não | — | — |
| D0_kimi_k4_s2 | 1.0695 | 1.07786 | 93/200 | F_rec | não | — | — |
| D0_kimi_k4_s0 | 1.0695 | 1.07611 | 16/200 | None | não | — | — |
| D0_kimi_k4_s1 | 1.0695 | 1.07402 | 26/200 | None | não | — | — |
| D0_kimi_k3_s0 | 1.0704 | 1.07388 | 40/200 | None | não | — | — |
| D0_kimi_k2_s0 | 1.0737 | 1.07372 | 18/200 | None | não | — | — |
| D0_kimi_k2_s1 | 1.0737 | 1.07372 | 84/200 | None | não | — | — |
| D0_kimi_k2_s2 | 1.0737 | 1.07372 | 21/200 | None | não | — | — |
| D0_kimi_k3_s1 | 1.0704 | 1.07091 | 5/200 | None | não | — | — |
| D0_kimi_k5_s1 | 1.0651 | 1.06512 | 14/200 | None | não | — | — |
| D0_kimi_k5_s2 | 1.0651 | 1.06512 | 11/200 | None | não | — | — |
| D0_opus_k1_s0 | 1.1240 | 1.12396 | 54/200 | None | não | — | — |
| D0_opus_k1_s1 | 1.1240 | 1.12396 | 9/200 | None | não | — | — |
| D0_opus_k1_s2 | 1.1240 | 1.12396 | 53/200 | None | não | — | — |
| D0_opus_k2_s1 | 1.1157 | 1.12006 | 5/200 | None | não | — | — |
| D0_opus_k2_s0 | 1.1178 | 1.11981 | 20/200 | None | não | — | — |
| D0_opus_k2_s2 | 1.1187 | 1.11981 | 12/200 | None | não | — | — |
| D0_opus_k3_s0 | 1.1188 | 1.11877 | 144/200 | None | não | — | — |
| D0_opus_k3_s1 | 1.1188 | 1.11877 | 120/200 | None | não | — | — |
| D0_opus_k3_s2 | 1.1188 | 1.11877 | 59/200 | None | não | — | — |
| D0_opus_k4_s0 | 1.1179 | 1.11843 | 12/200 | None | não | — | — |
| D0_opus_k4_s1 | 1.1179 | 1.11786 | 49/200 | None | não | — | — |
| D0_opus_k4_s2 | 1.1179 | 1.11786 | 134/200 | None | não | — | — |
| D0_opus_k5_s1 | 1.1177 | 1.11776 | 29/200 | None | não | — | — |
| D0_opus_k5_s0 | 1.1177 | 1.11772 | 73/200 | None | não | — | — |
| D0_opus_k5_s2 | 1.1177 | 1.11772 | 81/200 | None | não | — | — |
| D_kimi_k1_s0 | 1.1095 | 1.10954 | 0/200 | None | não | — | — |
| D_kimi_k1_s1 | 1.1095 | 1.10954 | 0/200 | None | não | — | — |
| D_kimi_k1_s2 | 1.1095 | 1.10954 | 0/200 | None | não | — | — |
| D_kimi_k2_s0 | 1.1089 | 1.10887 | 59/200 | None | não | — | — |
| D_kimi_k2_s1 | 1.1089 | 1.10887 | 96/200 | None | não | — | — |
| D_kimi_k2_s2 | 1.1089 | 1.10887 | 53/200 | None | não | — | — |
| D_kimi_k3_s0 | 1.0987 | 1.10355 | 2/200 | None | não | — | — |
| D_kimi_k3_s1 | 1.0987 | 1.09874 | 81/200 | None | não | — | — |
| D_kimi_k3_s2 | 1.0987 | 1.09874 | 49/200 | None | não | — | — |
| D_kimi_k4_s0 | 1.0899 | 1.08988 | 131/200 | None | não | — | — |
| D_kimi_k4_s1 | 1.0899 | 1.08988 | 146/200 | None | não | — | — |
| D_kimi_k4_s2 | 1.0899 | 1.08988 | 63/200 | None | não | — | — |
| D_kimi_k5_s0 | 1.0874 | 1.08737 | 9/200 | None | não | — | — |
| D_kimi_k5_s1 | 1.0874 | 1.08737 | 80/200 | None | não | — | — |
| D_kimi_k5_s2 | 1.0874 | 1.08737 | 14/200 | None | não | — | — |
| D_opus_k1_s0 | 1.1198 | 1.11981 | 74/200 | None | não | — | — |
| D_opus_k1_s1 | 1.1198 | 1.11981 | 120/200 | None | não | — | — |
| D_opus_k1_s2 | 1.1198 | 1.11981 | 99/200 | None | não | — | — |
| D_opus_k2_s0 | 1.1173 | 1.11729 | 46/200 | None | não | — | — |
| D_opus_k2_s1 | 1.1173 | 1.11729 | 74/200 | None | não | — | — |
| D_opus_k2_s2 | 1.1173 | 1.11729 | 128/200 | None | não | — | — |
| D_opus_k3_s0 | 1.1159 | 1.11664 | 40/200 | None | não | — | — |
| D_opus_k3_s1 | 1.1159 | 1.11593 | 114/200 | None | não | — | — |
| D_opus_k3_s2 | 1.1159 | 1.11593 | 158/200 | None | não | — | — |
| D_opus_k4_s0 | 1.1157 | 1.11567 | 1/200 | None | não | — | — |
| D_opus_k4_s1 | 1.1157 | 1.11567 | 9/200 | None | não | — | — |
| D_opus_k4_s2 | 1.1157 | 1.11567 | 5/200 | None | não | — | — |
| D_opus_k5_s0 | 1.1138 | 1.11379 | 0/200 | None | não | — | — |
| D_opus_k5_s1 | 1.1138 | 1.11379 | 0/200 | None | não | — | — |
| D_opus_k5_s2 | 1.1138 | 1.11379 | 0/200 | None | não | — | — |
