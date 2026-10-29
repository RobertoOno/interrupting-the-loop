# Sensibilidade do propositor ao teto de saída (Opus 5; D0 e T5 a 32.768 e 65.536 tokens; leitura única)

Pré-registro em `docs/PLANO.md` (2026-09-11) antes de qualquer chamada; mesmos mundos, prompts, contrato e verificador da ablação do gatilho (`docs/APPENDIX_P3_TRIGGER.md`), que a 16.384 tokens deu D0 0/4 e T5 0/4 com 23/24 sessões no teto. Tetos desta bateria: por resposta 32.768 ou 65.536; por sessão cap + 16.384; 3.600 s por sessão; 2.400 s por requisição; 12 turnos.

Transporte: streaming (emenda prospectiva de 11/09, 14:55 UTC, após as duas primeiras requisições sem streaming a 32.768 expirarem aos 2.400 s sem resposta; as células sem veredito do modelo foram repetidas uma vez sob `<id>_R2`, como o protocolo previa).

| mundo | braço | teto | rep | tentativa | estado | desfecho | ponte válida | visível | revisões | respostas | tokens de saída | tempo (s) | custo US$ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CAL3_I | T5 | 32768 | 1 | R2 | output_limit | no_complete_submission | não | não | 0 | 1 | 32768 | 359.5 | 0.91 |
| CAL3_R | T5 | 32768 | 2 | R2 | both_verified | valid_bridge | sim | sim | 1 | 1 | 14079 | 163.5 | 0.40 |
| CAL3_R | D0 | 32768 | 2 | R2 | output_limit | no_complete_submission | não | não | 0 | 1 | 32768 | 363.2 | 0.91 |
| CAL3_I | D0 | 32768 | 1 | R2 | output_limit | no_complete_submission | não | não | 0 | 1 | 32768 | 369.8 | 0.91 |
| CAL3_R | D0 | 32768 | 1 | 1 | both_verified | valid_bridge | sim | sim | 1 | 1 | 22175 | 239.5 | 0.62 |
| CAL3_R | T5 | 65536 | 1 | 1 | both_verified | valid_bridge | sim | sim | 1 | 1 | 21783 | 242.8 | 0.61 |
| CAL3_I | D0 | 32768 | 2 | 1 | output_limit | no_complete_submission | não | não | 0 | 1 | 32768 | 357.2 | 0.91 |
| CAL3_I | T5 | 65536 | 2 | 1 | output_limit | no_complete_submission | não | não | 0 | 1 | 65536 | 706.1 | 1.82 |
| CAL3_I | T5 | 65536 | 1 | 1 | both_verified | valid_bridge | sim | sim | 3 | 3 | 77940 | 803.3 | 2.88 |
| CAL3_R | T5 | 32768 | 1 | 1 | both_verified | valid_bridge | sim | sim | 2 | 2 | 22365 | 246.8 | 0.75 |
| CAL3_I | D0 | 65536 | 2 | 1 | output_limit | no_complete_submission | não | não | 0 | 1 | 65536 | 692.4 | 1.81 |
| CAL3_R | T5 | 65536 | 2 | 1 | both_verified | valid_bridge | sim | sim | 1 | 1 | 42964 | 466.4 | 1.19 |
| CAL3_I | D0 | 65536 | 1 | 1 | both_verified | valid_bridge | sim | sim | 2 | 2 | 69621 | 730.3 | 2.26 |
| CAL3_R | D0 | 65536 | 2 | 1 | both_verified | valid_bridge | sim | sim | 1 | 1 | 50940 | 578.5 | 1.41 |
| CAL3_I | T5 | 32768 | 2 | 1 | output_limit | no_complete_submission | não | não | 0 | 1 | 32768 | 373.0 | 0.91 |
| CAL3_R | D0 | 65536 | 1 | 1 | both_verified | valid_bridge | sim | sim | 2 | 2 | 48048 | 535.4 | 1.56 |

| braço | teto | pontes válidas / sessões | sessões no teto de saída |
|---|---|---|---|
| D0 | 16.384 (ablação, referência) | 0/4 | 4/4 |
| D0 | 32768 | 1/4 | 3/4 |
| D0 | 65536 | 3/4 | 1/4 |
| T5 | 16.384 (ablação, referência) | 0/4 | 4/4 |
| T5 | 32768 | 2/4 | 2/4 |
| T5 | 65536 | 3/4 | 1/4 |

Custo desta bateria: US$19.88.

