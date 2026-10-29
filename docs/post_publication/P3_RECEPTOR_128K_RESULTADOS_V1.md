# P3-R128 — o receptor sem ponte no teto de saída do modelo: resultados (leitura única em 19/10/2026, 00:53)

*Pré-registro: `docs/P3_RECEPTOR_128K_PRE_REGISTRO_V1.md` (congelado em `7fd223f0b`; verificações do congelamento em
`docs/p3/receptor128k_freeze_v1.md`). Leitura: `scripts/analysis_p3_receptor128k.py read`, congelado. Evidência:
`docs/p3/receptor128k_evidence_v1/` (1.123 arquivos com manifesto SHA-256). A extração do commit histórico (`_hist_b4e23d336`) fica
de fora; ela se refaz com `git archive b4e23d336` e tem o hash do manifesto fixado no pré-registro.*

## 1. Em poucas linhas

- **O receptor sem ponte resolve tudo com 128.000 tokens por resposta.**
  - **Transferência, baseline B**: 4/4 no mundo do invariante e 4/4 no da representação. No arquivo, com 16.384 tokens, tinha sido
    0/4, com as quatro respostas cortadas, só de pensamento.
  - **S16, representação sem ponte**: 4/4. No arquivo, 0/2 em cada limite.
  - **A 7ª receptora censurada** (C2 no irmão 2 da representação): 2/2.
- **Pela regra do pré-registro (§1), é teto: a ponte só poupa tempo, em tokens, não capacidade.** A utilidade U da ponte é zero em
  todos os irmãos.
- **Quanto a ponte poupa**: a mediana do receptor sem ponte foi de 31.276 tokens no invariante e 30.432 na representação, contra
  3.356 e 2.645 das pontes arquivadas (D e C2). São cerca de 9 e 11 vezes menos tokens com a ponte.
- **Os controles com ponte, rodados junto**, resolveram 6/6: o instrumento funciona.
- **Nenhuma trava nossa prendeu**: nenhuma resposta cortada, nenhum re-pedido usado, nenhum turno ou tempo esgotado. Também nenhuma
  falha de infraestrutura.

## 2. Por grupo

| grupo | mundo | n | resolvidas |
|---|---|---|---|
| B (sem ponte, transferência) | invariante | 4 | 4 |
| B (sem ponte, transferência) | representação | 4 | 4 |
| C2 (ponte de fonte sham) | invariante | 2 | 2 |
| C2 | representação | 1 | 1 |
| C2, irmão 2 da representação (a 7ª censurada) | representação | 2 | 2 |
| D (ponte com fonte) | invariante | 2 | 2 |
| D | representação | 2 | 2 |
| O (ponte-oráculo) | invariante | 2 | 2 |
| O | representação | 2 | 2 |
| S16, oráculo | representação | 2 | 2 |
| S16, sem ponte | representação | 4 | 4 |

- O modelo foi o do arquivo, `anthropic.claude-opus-5`, pelo mesmo cliente. Só o teto de saída mudou.
- 27 sessões em 2 blocos completos; 32 respostas no total.

## 3. Custo

- US$14,31 pelos tokens, às taxas de guarda (US$5,50 e US$27,50 por milhão), mais US$0,38 da sonda.

## 4. O que muda

- **A "transferência" do Programa 3 media economia de orçamento, não capacidade.** Com 16.384 tokens, o receptor sem ponte nunca
  terminava, e as pontes "transferiam". Com o teto do modelo, ele resolve sozinho, com cerca de 10 vezes mais tokens.
- **A frase da síntese fica mais forte neste caso**: o que a forma operável comprou foi tempo dentro de um orçamento, não um operador
  que o modelo, com espaço para pensar, não produzisse.
- **A seleção e a produção de pontes continuam medidas como antes** (o D e o C2 produziram pontes válidas). O que cai é a leitura de
  que elas tornavam possível o que antes não era.
