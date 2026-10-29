# Programa 3 — diagnóstico de produção/transferência (leitura única)

Dois mundos de calibração expostos (invariante, representação); 6 propositores (D0/D/C2 × mundo), receptores novos nos dois irmãos ocultos com a ponte candidata, baseline (B) e oráculo (O). Descritivo por desenho: não há teste confirmatório.


## Mundo CAL3_I_E87C49876088749B (invariant)

| propositor | braço | estado | desfecho | ponte válida | visível resolvido | revisões | custo US$ |
|---|---|---|---|---|---|---|---|
| T26_9BE9BE8FCC62 | C2 | both_verified | valid_bridge | sim | sim | 1 | 0.37 |
| T26_D7017E013E29 | D0 | output_limit | no_complete_submission | não | não | 0 | 0.46 |
| T26_86C7BD8C99DD | D | both_verified | valid_bridge | sim | sim | 1 | 0.16 |

| irmão | condição | braço/origem | resolvido | revisões | custo US$ |
|---|---|---|---|---|---|
| 1 | oracle | O | sim | 1 | 0.16 |
| 1 | none | B | não | 0 | 0.46 |
| 1 | candidate | D(ponte de T26_86C7BD8C99DD) | sim | 1 | 0.11 |
| 1 | candidate | C2(ponte de T26_9BE9BE8FCC62) | sim | 1 | 0.11 |
| 1 | candidate | D0(ponte de T26_D7017E013E29) | pulado: no_valid_bridge_from_parent | — | 0.00 |
| 2 | candidate | D0(ponte de T26_D7017E013E29) | pulado: no_valid_bridge_from_parent | — | 0.00 |
| 2 | candidate | D(ponte de T26_86C7BD8C99DD) | sim | 1 | 0.11 |
| 2 | none | B | não | 0 | 0.46 |
| 2 | candidate | C2(ponte de T26_9BE9BE8FCC62) | sim | 1 | 0.05 |
| 2 | oracle | O | sim | 1 | 0.14 |

**Utilidade das pontes candidatas** (U = resolvido com a ponte − resolvido na baseline, por irmão; oráculo ao lado):

| irmão | baseline | oráculo | D0 | D | C2 |
|---|---|---|---|---|---|
| 1 | False | True | — | +1 | +1 |
| 2 | False | True | — | +1 | +1 |

## Mundo CAL3_R_F76437525B190ECB (representation)

| propositor | braço | estado | desfecho | ponte válida | visível resolvido | revisões | custo US$ |
|---|---|---|---|---|---|---|---|
| T26_40A8FE16CB8C | D0 | output_limit | no_complete_submission | não | não | 0 | 0.46 |
| T26_778C8EC28AB1 | C2 | both_verified | valid_bridge | sim | sim | 1 | 0.30 |
| T26_AE17ED971452 | D | both_verified | valid_bridge | sim | sim | 2 | 0.50 |

| irmão | condição | braço/origem | resolvido | revisões | custo US$ |
|---|---|---|---|---|---|
| 1 | oracle | O | sim | 1 | 0.08 |
| 1 | candidate | D0(ponte de T26_40A8FE16CB8C) | pulado: no_valid_bridge_from_parent | — | 0.00 |
| 1 | candidate | D(ponte de T26_AE17ED971452) | sim | 1 | 0.07 |
| 1 | none | B | não | 0 | 0.46 |
| 1 | candidate | C2(ponte de T26_778C8EC28AB1) | sim | 2 | 0.61 |
| 2 | none | B | não | 0 | 0.46 |
| 2 | candidate | C2(ponte de T26_778C8EC28AB1) | não | 0 | 0.47 |
| 2 | candidate | D0(ponte de T26_40A8FE16CB8C) | pulado: no_valid_bridge_from_parent | — | 0.00 |
| 2 | candidate | D(ponte de T26_AE17ED971452) | sim | 1 | 0.09 |
| 2 | oracle | O | sim | 1 | 0.10 |

**Utilidade das pontes candidatas** (U = resolvido com a ponte − resolvido na baseline, por irmão; oráculo ao lado):

| irmão | baseline | oráculo | D0 | D | C2 |
|---|---|---|---|---|---|
| 1 | False | True | — | +1 | +1 |
| 2 | False | True | — | +1 | +0 |

Células executadas: 22/26; custo total a tarifas configuradas: US$6.20.

