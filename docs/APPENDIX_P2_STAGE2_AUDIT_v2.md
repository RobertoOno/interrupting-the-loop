# Programa 2 — etapa 2: AUDITORIA do endpoint de família — EMENDA 2 (2026-09-04, tarde)

Este documento **não substitui** `docs/APPENDIX_P2_STAGE2.md` (leitura única, preservada) nem a emenda 1
(`docs/APPENDIX_P2_STAGE2_AUDIT.md`, preservada). Diferenças da emenda 2: (i) o escore da semente é o **observado em cada
corrida** (entrada `hash == "seed"` do `state.json`; se cortada da ilha, reexecução só para programas determinísticos, conferida
com a linha de 4 casas do log; senão o valor do log, marcado incerto) e é ele que define `melhorou` e o replay dos elites;
(ii) família desconhecida (`None`) nunca conta como mudança de família. A seção final lista exatamente o que mudou.

## 1. Endpoint pré-registrado e o que o script de leitura mediu

- **Pré-registro (PLANO 03/09)**: S2 = fração de corridas cujo *final* tem saída de família (final válido, θ ≥ 1,10, fora de F0).
- **O script da leitura única** (`analysis_p2_stage2.py`) classificou apenas `best.py`. `best.py` só existe quando o laço
  superou a semente (44 de 108 corridas); quando a semente continuou sendo o melhor, a família ficou `None` e a corrida
  contou como 'sem saída'. Além disso, `best.py` guarda o candidato sem o prelúdio (`construct_v0..2`, auxiliares) com
  que ele foi verificado, então parte dos arquivos não é um programa autônomo.
- **Interpretação corrigida da frase 'nenhuma saída de família em D/D0'**: ela vale para *saídas novas produzidas pelo laço*;
  não é verdade que nenhum final esteja fora de F0 — as sementes do Opus (F_rec/other) já estão fora de F0 e, quando o
  laço não melhora, o final **é** a semente, com a família dela.

## 2. Três quantidades separadas

(a) família **herdada** da semente; (b) saída **nova** produzida pelo laço (final produzido pelo laço, θ ≥ 1,10, fora de F0,
partindo de uma semente que não qualificava); (c) família do **final** da corrida (= semente quando nada melhorou).
`materialização`: `seed` (final = semente), `self-contained` (best.py reproduz o escore sozinho), `prelude` (reproduz
só com o prelúdio reconstruído por replay), `not-materializable` (não reproduz: marcado, não classificado).

| braço | corridas | melhoraram | finais = semente | materialização: self / prelude / não | sementes fora de F0 (a) | finais fora de F0 (c) | saídas novas (b) | famílias mudaram |
|---|---|---|---|---|---|---|---|---|
| A | 3 | 3 | 0 | 2 / 1 / 0 | 0 | 0 | 0 | 0 |
| C1_none | 15 | 3 | 12 | 3 / 0 / 0 | 3 | 3 | 0 | 0 |
| C2_kimi | 15 | 12 | 3 | 5 / 6 / 1 | 0 | 3 | 3 | 3 |
| C2_opus | 15 | 10 | 5 | 6 / 4 / 0 | 3 | 5 | 2 | 0 |
| D0_kimi | 15 | 9 | 6 | 3 / 2 / 4 | 0 | 0 | 0 | 2 |
| D0_opus | 15 | 5 | 10 | 0 / 2 / 3 | 15 | 11 | 0 | 1 |
| D_kimi | 15 | 1 | 14 | 0 / 1 / 0 | 6 | 6 | 0 | 0 |
| D_opus | 15 | 1 | 14 | 0 / 1 / 0 | 15 | 15 | 0 | 0 |

## 3. Unidade de inferência: 5 sementes × 3 RNG por braço

| braço | semente k | θ semente | melhor: média ± dp (mín–máx) sobre 3 RNG | melhoraram | finais fora de F0 | saídas novas |
|---|---|---|---|---|---|---|
| A | None | 1.0792 | 1.0976 ± 0.0081 (1.0862–1.1044) | 3/3 | 0/3 | 0/3 |
| C1_none | 1 | 1.1038 | 1.1038 ± 0.0000 (1.1038–1.1038) | 0/3 | 3/3 | 0/3 |
| C1_none | 2 | 1.0957 | 1.0957 ± 0.0000 (1.0957–1.0957) | 0/3 | 0/3 | 0/3 |
| C1_none | 3 | 1.0887 | 1.0887 ± 0.0000 (1.0887–1.0887) | 0/3 | 0/3 | 0/3 |
| C1_none | 4 | 1.0815 | 1.0815 ± 0.0000 (1.0815–1.0815) | 0/3 | 0/3 | 0/3 |
| C1_none | 5 | 1.0710 | 1.0720 ± 0.0005 (1.0715–1.0727) | 3/3 | 0/3 | 0/3 |
| C2_kimi | 1 | 1.0957 | 1.0964 ± 0.0006 (1.0957–1.0973) | 2/3 | 0/3 | 0/3 |
| C2_kimi | 2 | 1.0887 | 1.1037 ± 0.0022 (1.1007–1.1056) | 3/3 | 3/3 | 3/3 |
| C2_kimi | 3 | 1.0815 | 1.0815 ± 0.0000 (1.0815–1.0815) | 1/3 | 0/3 | 0/3 |
| C2_kimi | 4 | 1.0734 | 1.0810 ± 0.0021 (1.0785–1.0836) | 3/3 | 0/3 | 0/3 |
| C2_kimi | 5 | 1.0734 | 1.0819 ± 0.0013 (1.0809–1.0837) | 3/3 | 0/3 | 0/3 |
| C2_opus | 1 | 1.1038 | 1.1048 ± 0.0015 (1.1038–1.1069) | 1/3 | 3/3 | 0/3 |
| C2_opus | 2 | 1.0957 | 1.0971 ± 0.0002 (1.0968–1.0973) | 3/3 | 0/3 | 0/3 |
| C2_opus | 3 | 1.0887 | 1.1008 ± 0.0086 (1.0887–1.1077) | 2/3 | 2/3 | 2/3 |
| C2_opus | 4 | 1.0815 | 1.0875 ± 0.0038 (1.0822–1.0911) | 3/3 | 0/3 | 0/3 |
| C2_opus | 5 | 1.0702 | 1.0702 ± 0.0001 (1.0702–1.0703) | 1/3 | 0/3 | 0/3 |
| D0_kimi | 1 | 1.0815 | 1.0832 ± 0.0024 (1.0815–1.0865) | 2/3 | 0/3 | 0/3 |
| D0_kimi | 2 | 1.0737 | 1.0737 ± 0.0000 (1.0737–1.0737) | 0/3 | 0/3 | 0/3 |
| D0_kimi | 3 | 1.0704 | 1.0824 ± 0.0141 (1.0709–1.1023) | 3/3 | 0/3 | 0/3 |
| D0_kimi | 4 | 1.0695 | 1.0760 ± 0.0016 (1.0740–1.0779) | 3/3 | 0/3 | 0/3 |
| D0_kimi | 5 | 1.0651 | 1.0735 ± 0.0118 (1.0651–1.0902) | 1/3 | 0/3 | 0/3 |
| D0_opus | 1 | 1.1240 | 1.1240 ± 0.0000 (1.1240–1.1240) | 0/3 | 3/3 | 0/3 |
| D0_opus | 2 | 1.1178 | 1.1199 ± 0.0001 (1.1198–1.1201) | 3/3 | 0/3 | 0/3 |
| D0_opus | 3 | 1.1188 | 1.1188 ± 0.0000 (1.1188–1.1188) | 0/3 | 3/3 | 0/3 |
| D0_opus | 4 | 1.1179 | 1.1181 ± 0.0003 (1.1179–1.1184) | 1/3 | 3/3 | 0/3 |
| D0_opus | 5 | 1.1177 | 1.1177 ± 0.0000 (1.1177–1.1178) | 1/3 | 2/3 | 0/3 |
| D_kimi | 1 | 1.1095 | 1.1095 ± 0.0000 (1.1095–1.1095) | 0/3 | 3/3 | 0/3 |
| D_kimi | 2 | 1.1089 | 1.1089 ± 0.0000 (1.1089–1.1089) | 0/3 | 3/3 | 0/3 |
| D_kimi | 3 | 1.0987 | 1.1003 ± 0.0023 (1.0987–1.1035) | 1/3 | 0/3 | 0/3 |
| D_kimi | 4 | 1.0899 | 1.0899 ± 0.0000 (1.0899–1.0899) | 0/3 | 0/3 | 0/3 |
| D_kimi | 5 | 1.0874 | 1.0874 ± 0.0000 (1.0874–1.0874) | 0/3 | 0/3 | 0/3 |
| D_opus | 1 | 1.1198 | 1.1198 ± 0.0000 (1.1198–1.1198) | 0/3 | 3/3 | 0/3 |
| D_opus | 2 | 1.1173 | 1.1173 ± 0.0000 (1.1173–1.1173) | 0/3 | 3/3 | 0/3 |
| D_opus | 3 | 1.1159 | 1.1162 ± 0.0003 (1.1159–1.1166) | 1/3 | 3/3 | 0/3 |
| D_opus | 4 | 1.1157 | 1.1157 ± 0.0000 (1.1157–1.1157) | 0/3 | 3/3 | 0/3 |
| D_opus | 5 | 1.1138 | 1.1138 ± 0.0000 (1.1138–1.1138) | 0/3 | 3/3 | 0/3 |

### D vs D0 com a semente como unidade (5 vs 5 médias por semente)

| modelo | D (média das 5 sementes) | D0 | p Mann–Whitney (5×5) | p permutação (médias) | ressalva |
|---|---|---|---|---|---|
| opus | 1.1165 | 1.1197 | 0.056 | 0.063 | as sementes diferem entre braços (top-5 de cada); pareamento por posto k é nominal |
| kimi | 1.0992 | 1.0777 | 0.008 | 0.007 | as sementes diferem entre braços (top-5 de cada); pareamento por posto k é nominal |

*Ressalva à leitura original*: o Mann–Whitney sobre 15 corridas por braço trata 3 RNG da mesma semente como independentes;
as médias por semente acima são a unidade correta (n = 5 por braço); o sentido e a significância de cada contraste estão na tabela
(direção = qual braço tem a média maior; um p pequeno com D > D0 reflete sementes melhores no D, não transferência, quando não há saídas novas).

## 4. Saídas de família por corrida: herdada, nova, final (Fisher exato sobre corridas, com a mesma ressalva de dependência)

| contraste | saídas novas (b) | p | finais fora de F0 (c) | p |
|---|---|---|---|---|
| D_opus vs C2_opus | 0/15 vs 2/15 | 0.483 | 15/15 vs 5/15 | 0.000 |
| D_opus vs D0_opus | 0/15 vs 0/15 | 1.000 | 15/15 vs 11/15 | 0.100 |
| D_opus vs C1_none | 0/15 vs 0/15 | 1.000 | 15/15 vs 3/15 | 0.000 |
| D_kimi vs C2_kimi | 0/15 vs 3/15 | 0.224 | 6/15 vs 3/15 | 0.427 |
| D_kimi vs D0_kimi | 0/15 vs 0/15 | 1.000 | 6/15 vs 0/15 | 0.017 |

## 5. Limitações de materialização

8 corrida(s) com final não materializável (marcadas, não classificadas): C2_kimi_k5_s2 (alone -> None; with replayed prelude -> 1.0808921253738293; expected 1.0810449463470464); D0_kimi_k3_s1 (alone -> None; with replayed prelude -> 1.0697666226305493; expected 1.070906968578738); D0_kimi_k3_s2 (alone -> None; with replayed prelude -> 1.0977679381086345; expected 1.102288282497377); D0_kimi_k4_s0 (alone -> None; with replayed prelude -> 1.0747766589569108; expected 1.0761050922756255); D0_kimi_k4_s1 (alone -> None; with replayed prelude -> 1.0759947374334784; expected 1.0740211661349193); D0_opus_k2_s0 (alone -> None; with replayed prelude -> 1.117757765501543; expected 1.1198105854990457); D0_opus_k2_s1 (alone -> None; with replayed prelude -> 1.1186996305804722; expected 1.1200614117753247); D0_opus_k2_s2 (alone -> None; with replayed prelude -> 1.115433687748179; expected 1.1198105854990457).
O replay reproduz as regras do harness no commit 94fc0ea (`frontier_search.py`): elites = top-3 por escore no início da geração,
renomeados `construct_v{i}`; todo candidato válido entra na ilha (novelty=none); corte em 12; migração do melhor a cada 3 gerações.
A reprodução do escore (tolerância 1e-9) é a prova de que o programa materializado é o que foi verificado na corrida.

## 6. Corridas

| corrida | θ semente | fam. semente | melhor | melhorou | válidos | materialização | fam. final | herdada | nova | final fora de F0 |
|---|---|---|---|---|---|---|---|---|---|---|
| A_s0 | 1.0792 | F0 | 1.08618 | sim | 120/200 | self-contained | F0 | não | não | não |
| A_s1 | 1.0792 | F0 | 1.10220 | sim | 44/200 | self-contained | F0 | não | não | não |
| A_s2 | 1.0792 | F0 | 1.10436 | sim | 63/200 | prelude | F0 | não | não | não |
| C1_none_k1_s0 | 1.1038 | other | 1.10379 | não | 139/200 | seed | other | sim | não | sim |
| C1_none_k1_s1 | 1.1038 | other | 1.10379 | não | 44/200 | seed | other | sim | não | sim |
| C1_none_k1_s2 | 1.1038 | other | 1.10379 | não | 125/200 | seed | other | sim | não | sim |
| C1_none_k2_s0 | 1.0957 | F0 | 1.09573 | não | 26/200 | seed | F0 | não | não | não |
| C1_none_k2_s1 | 1.0957 | F0 | 1.09573 | não | 55/200 | seed | F0 | não | não | não |
| C1_none_k2_s2 | 1.0957 | F0 | 1.09573 | não | 57/200 | seed | F0 | não | não | não |
| C1_none_k3_s0 | 1.0887 | other | 1.08865 | não | 0/200 | seed | other | não | não | não |
| C1_none_k3_s1 | 1.0887 | other | 1.08865 | não | 0/200 | seed | other | não | não | não |
| C1_none_k3_s2 | 1.0887 | other | 1.08865 | não | 0/200 | seed | other | não | não | não |
| C1_none_k4_s0 | 1.0815 | other | 1.08149 | não | 53/200 | seed | other | não | não | não |
| C1_none_k4_s1 | 1.0815 | other | 1.08149 | não | 114/200 | seed | other | não | não | não |
| C1_none_k4_s2 | 1.0815 | other | 1.08149 | não | 58/200 | seed | other | não | não | não |
| C1_none_k5_s0 | 1.0710 | other | 1.07187 | sim | 123/200 | self-contained | other | não | não | não |
| C1_none_k5_s1 | 1.0710 | other | 1.07152 | sim | 103/200 | self-contained | other | não | não | não |
| C1_none_k5_s2 | 1.0710 | other | 1.07268 | sim | 49/200 | self-contained | other | não | não | não |
| C2_kimi_k1_s0 | 1.0957 | F0 | 1.09726 | sim | 101/200 | self-contained | F0 | não | não | não |
| C2_kimi_k1_s1 | 1.0957 | F0 | 1.09573 | não | 111/200 | seed | F0 | não | não | não |
| C2_kimi_k1_s2 | 1.0957 | F0 | 1.09628 | sim | 49/200 | prelude | other | não | não | não |
| C2_kimi_k2_s0 | 1.0887 | other | 1.10502 | sim | 39/200 | self-contained | other | não | sim | sim |
| C2_kimi_k2_s1 | 1.0887 | other | 1.10067 | sim | 157/200 | self-contained | other | não | sim | sim |
| C2_kimi_k2_s2 | 1.0887 | other | 1.10556 | sim | 57/200 | self-contained | other | não | sim | sim |
| C2_kimi_k3_s0 | 1.0815 | other | 1.08149 | não | 124/200 | seed | other | não | não | não |
| C2_kimi_k3_s1 | 1.0815 | other | 1.08149 | não | 185/200 | seed | other | não | não | não |
| C2_kimi_k3_s2 | 1.0815 | other | 1.08154 | sim | 117/200 | self-contained | other | não | não | não |
| C2_kimi_k4_s0 | 1.0734 | F0 | 1.07854 | sim | 43/200 | prelude | other | não | não | não |
| C2_kimi_k4_s1 | 1.0734 | F0 | 1.08363 | sim | 37/200 | prelude | F0 | não | não | não |
| C2_kimi_k4_s2 | 1.0734 | F0 | 1.08089 | sim | 84/200 | prelude | F0 | não | não | não |
| C2_kimi_k5_s0 | 1.0734 | F0 | 1.08089 | sim | 23/200 | prelude | F0 | não | não | não |
| C2_kimi_k5_s1 | 1.0734 | F0 | 1.08371 | sim | 23/200 | prelude | other | não | não | não |
| C2_kimi_k5_s2 | 1.0734 | F0 | 1.08104 | sim | 107/200 | not-materializable | None | não | não | não |
| C2_opus_k1_s0 | 1.1038 | other | 1.10379 | não | 66/200 | seed | other | sim | não | sim |
| C2_opus_k1_s1 | 1.1038 | other | 1.10379 | não | 79/200 | seed | other | sim | não | sim |
| C2_opus_k1_s2 | 1.1038 | other | 1.10692 | sim | 15/200 | prelude | other | sim | não | sim |
| C2_opus_k2_s0 | 1.0957 | F0 | 1.09726 | sim | 81/200 | self-contained | F0 | não | não | não |
| C2_opus_k2_s1 | 1.0957 | F0 | 1.09726 | sim | 164/200 | self-contained | F0 | não | não | não |
| C2_opus_k2_s2 | 1.0957 | F0 | 1.09679 | sim | 116/200 | self-contained | F0 | não | não | não |
| C2_opus_k3_s0 | 1.0887 | other | 1.10603 | sim | 11/200 | self-contained | other | não | sim | sim |
| C2_opus_k3_s1 | 1.0887 | other | 1.08865 | não | 93/200 | seed | other | não | não | não |
| C2_opus_k3_s2 | 1.0887 | other | 1.10769 | sim | 92/200 | self-contained | other | não | sim | sim |
| C2_opus_k4_s0 | 1.0815 | other | 1.08900 | sim | 10/200 | prelude | other | não | não | não |
| C2_opus_k4_s1 | 1.0815 | other | 1.09114 | sim | 162/200 | self-contained | other | não | não | não |
| C2_opus_k4_s2 | 1.0815 | other | 1.08224 | sim | 105/200 | prelude | other | não | não | não |
| C2_opus_k5_s0 | 1.0702 | other | 1.07017 | não | 65/200 | seed | other | não | não | não |
| C2_opus_k5_s1 | 1.0702 | other | 1.07017 | não | 157/200 | seed | other | não | não | não |
| C2_opus_k5_s2 | 1.0702 | other | 1.07032 | sim | 25/200 | prelude | other | não | não | não |
| D0_kimi_k1_s0 | 1.0815 | other | 1.08148 | não | 118/200 | seed | other | não | não | não |
| D0_kimi_k1_s1 | 1.0815 | other | 1.08152 | sim | 153/200 | self-contained | other | não | não | não |
| D0_kimi_k1_s2 | 1.0815 | other | 1.08649 | sim | 69/200 | self-contained | other | não | não | não |
| D0_kimi_k2_s0 | 1.0737 | other | 1.07372 | não | 18/200 | seed | other | não | não | não |
| D0_kimi_k2_s1 | 1.0737 | other | 1.07372 | não | 84/200 | seed | other | não | não | não |
| D0_kimi_k2_s2 | 1.0737 | other | 1.07372 | não | 21/200 | seed | other | não | não | não |
| D0_kimi_k3_s0 | 1.0704 | other | 1.07388 | sim | 40/200 | prelude | other | não | não | não |
| D0_kimi_k3_s1 | 1.0704 | other | 1.07091 | sim | 5/200 | not-materializable | None | não | não | não |
| D0_kimi_k3_s2 | 1.0704 | other | 1.10229 | sim | 21/200 | not-materializable | None | não | não | não |
| D0_kimi_k4_s0 | 1.0695 | other | 1.07611 | sim | 16/200 | not-materializable | None | não | não | não |
| D0_kimi_k4_s1 | 1.0695 | other | 1.07402 | sim | 26/200 | not-materializable | None | não | não | não |
| D0_kimi_k4_s2 | 1.0695 | other | 1.07786 | sim | 93/200 | self-contained | F_rec | não | não | não |
| D0_kimi_k5_s0 | 1.0651 | F0 | 1.09017 | sim | 9/200 | prelude | other | não | não | não |
| D0_kimi_k5_s1 | 1.0651 | F0 | 1.06512 | não | 14/200 | seed | F0 | não | não | não |
| D0_kimi_k5_s2 | 1.0651 | F0 | 1.06512 | não | 11/200 | seed | F0 | não | não | não |
| D0_opus_k1_s0 | 1.1240 | other | 1.12396 | não | 54/200 | seed | other | sim | não | sim |
| D0_opus_k1_s1 | 1.1240 | other | 1.12396 | não | 9/200 | seed | other | sim | não | sim |
| D0_opus_k1_s2 | 1.1240 | other | 1.12396 | não | 53/200 | seed | other | sim | não | sim |
| D0_opus_k2_s0 | 1.1178 | F_rec | 1.11981 | sim | 20/200 | not-materializable | None | não | não | não |
| D0_opus_k2_s1 | 1.1157 | F_rec | 1.12006 | sim | 5/200 | not-materializable | None | não | não | não |
| D0_opus_k2_s2 | 1.1187 | F_rec | 1.11981 | sim | 12/200 | not-materializable | None | não | não | não |
| D0_opus_k3_s0 | 1.1188 | F_rec | 1.11877 | não | 144/200 | seed | F_rec | sim | não | sim |
| D0_opus_k3_s1 | 1.1188 | F_rec | 1.11877 | não | 120/200 | seed | F_rec | sim | não | sim |
| D0_opus_k3_s2 | 1.1188 | F_rec | 1.11877 | não | 59/200 | seed | F_rec | sim | não | sim |
| D0_opus_k4_s0 | 1.1179 | F_rec | 1.11843 | sim | 12/200 | prelude | F_rec | sim | não | sim |
| D0_opus_k4_s1 | 1.1179 | F_rec | 1.11786 | não | 49/200 | seed | F_rec | sim | não | sim |
| D0_opus_k4_s2 | 1.1179 | F_rec | 1.11786 | não | 134/200 | seed | F_rec | sim | não | sim |
| D0_opus_k5_s0 | 1.1177 | other | 1.11772 | não | 73/200 | seed | other | sim | não | sim |
| D0_opus_k5_s1 | 1.1177 | other | 1.11776 | sim | 29/200 | prelude | F0 | não | não | não |
| D0_opus_k5_s2 | 1.1177 | other | 1.11772 | não | 81/200 | seed | other | sim | não | sim |
| D_kimi_k1_s0 | 1.1095 | F_rec | 1.10954 | não | 0/200 | seed | F_rec | sim | não | sim |
| D_kimi_k1_s1 | 1.1095 | F_rec | 1.10954 | não | 0/200 | seed | F_rec | sim | não | sim |
| D_kimi_k1_s2 | 1.1095 | F_rec | 1.10954 | não | 0/200 | seed | F_rec | sim | não | sim |
| D_kimi_k2_s0 | 1.1089 | other | 1.10887 | não | 59/200 | seed | other | sim | não | sim |
| D_kimi_k2_s1 | 1.1089 | other | 1.10887 | não | 96/200 | seed | other | sim | não | sim |
| D_kimi_k2_s2 | 1.1089 | other | 1.10887 | não | 53/200 | seed | other | sim | não | sim |
| D_kimi_k3_s0 | 1.0987 | F0 | 1.10355 | sim | 2/200 | prelude | F0 | não | não | não |
| D_kimi_k3_s1 | 1.0987 | F0 | 1.09874 | não | 81/200 | seed | F0 | não | não | não |
| D_kimi_k3_s2 | 1.0987 | F0 | 1.09874 | não | 49/200 | seed | F0 | não | não | não |
| D_kimi_k4_s0 | 1.0899 | other | 1.08988 | não | 131/200 | seed | other | não | não | não |
| D_kimi_k4_s1 | 1.0899 | other | 1.08988 | não | 146/200 | seed | other | não | não | não |
| D_kimi_k4_s2 | 1.0899 | other | 1.08988 | não | 63/200 | seed | other | não | não | não |
| D_kimi_k5_s0 | 1.0874 | other | 1.08737 | não | 9/200 | seed | other | não | não | não |
| D_kimi_k5_s1 | 1.0874 | other | 1.08737 | não | 80/200 | seed | other | não | não | não |
| D_kimi_k5_s2 | 1.0874 | other | 1.08737 | não | 14/200 | seed | other | não | não | não |
| D_opus_k1_s0 | 1.1198 | F_rec | 1.11981 | não | 74/200 | seed | F_rec | sim | não | sim |
| D_opus_k1_s1 | 1.1198 | F_rec | 1.11981 | não | 120/200 | seed | F_rec | sim | não | sim |
| D_opus_k1_s2 | 1.1198 | F_rec | 1.11981 | não | 99/200 | seed | F_rec | sim | não | sim |
| D_opus_k2_s0 | 1.1173 | F_rec | 1.11729 | não | 46/200 | seed | F_rec | sim | não | sim |
| D_opus_k2_s1 | 1.1173 | F_rec | 1.11729 | não | 74/200 | seed | F_rec | sim | não | sim |
| D_opus_k2_s2 | 1.1173 | F_rec | 1.11729 | não | 128/200 | seed | F_rec | sim | não | sim |
| D_opus_k3_s0 | 1.1159 | F_rec | 1.11664 | sim | 40/200 | prelude | F_rec | sim | não | sim |
| D_opus_k3_s1 | 1.1159 | F_rec | 1.11593 | não | 114/200 | seed | F_rec | sim | não | sim |
| D_opus_k3_s2 | 1.1159 | F_rec | 1.11593 | não | 158/200 | seed | F_rec | sim | não | sim |
| D_opus_k4_s0 | 1.1157 | F_rec | 1.11567 | não | 1/200 | seed | F_rec | sim | não | sim |
| D_opus_k4_s1 | 1.1157 | F_rec | 1.11567 | não | 9/200 | seed | F_rec | sim | não | sim |
| D_opus_k4_s2 | 1.1157 | F_rec | 1.11567 | não | 5/200 | seed | F_rec | sim | não | sim |
| D_opus_k5_s0 | 1.1138 | F_rec | 1.11379 | não | 0/200 | seed | F_rec | sim | não | sim |
| D_opus_k5_s1 | 1.1138 | F_rec | 1.11379 | não | 0/200 | seed | F_rec | sim | não | sim |
| D_opus_k5_s2 | 1.1138 | F_rec | 1.11379 | não | 0/200 | seed | F_rec | sim | não | sim |

## 7. Proveniência do escore da semente por corrida

| fonte | corridas |
|---|---|
| state | 93 |
| reexec-deterministic | 15 |

Corridas com escore de semente incerto (só o log, 4 casas): 0.

## 8. O que mudou em relação à emenda 1 (`runs/p2/stage2_audit.json`)

13 campo(s) alterado(s) em 8 corrida(s).

| corrida | campo | emenda 1 | emenda 2 |
|---|---|---|---|
| C2_kimi_k5_s2 | family_changed | True | False |
| D0_kimi_k3_s1 | family_changed | True | False |
| D0_kimi_k3_s2 | materialization | prelude | not-materializable |
| D0_kimi_k3_s2 | final_family | F0 | None |
| D0_kimi_k3_s2 | family_changed | True | False |
| D0_kimi_k4_s0 | family_changed | True | False |
| D0_kimi_k4_s1 | family_changed | True | False |
| D0_opus_k2_s0 | seed_theta | 1.1169807984444908 | 1.117757765501543 |
| D0_opus_k2_s0 | family_changed | True | False |
| D0_opus_k2_s1 | seed_theta | 1.1169807984444908 | 1.1156969870727171 |
| D0_opus_k2_s1 | family_changed | True | False |
| D0_opus_k2_s2 | seed_theta | 1.1169807984444908 | 1.1186996305804722 |
| D0_opus_k2_s2 | family_changed | True | False |

| total | emenda 1 | emenda 2 |
|---|---|---|
| improved | 44 | 44 |
| inherited_exit | 38 | 38 |
| new_exit | 5 | 5 |
| final_exit | 43 | 43 |
| family_changed | 14 | 6 |
| materialização seed | 64 | 64 |
| materialização self-contained | 19 | 19 |
| materialização prelude | 18 | 17 |
| materialização not-materializable | 7 | 8 |
