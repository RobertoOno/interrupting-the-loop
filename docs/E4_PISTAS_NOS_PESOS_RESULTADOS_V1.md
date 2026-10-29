# E4 — pistas nos pesos: resultados (execução única em 2026-09-26 19:50–19:53 PDT; diagnóstico descritivo, sem veredito)

*Protocolo `docs/E4_PISTAS_NOS_PESOS_V1.md` (escrito antes de qualquer medida; script `scripts/e4_weights.py` publicado em `ff53b08c`,
teste de auxiliares corrigido em `1ba3e774`; execução sob `543fb2d0`). Trinta modelos do E3 com pesos (`runs/e/e3_all_full`, download
completo verificado byte a byte contra a cópia lida às 18:24), CPU do Mac, 2 min 58 s, custo zero. Forçamento da prova de referência de
cada mundo retido (60 de M2, 60 de M6 por modelo) e das famílias treinadas; sondas em mundos novos (semente 2026092604, 200 de M1 e 200
de M2) em 12 modelos (cru e gargalo, F ∈ {1, 4, 8}). Saídas: `docs/e4_results/e4.json`, `e4.md`; figura
`docs/figures/fig_e4_price_by_token.png` (`scripts/e4_figures.py`). Nada aqui altera as conclusões do E3.*

## A. Onde está o preço, token a token (bits da prova de referência, média dos 60 mundos; por papel do token)

**M2 (módulo fora da faixa; referência `mod (+ x (* c y)) n`, n ∈ {11, 13, 17, 19}, c até n − 1).** Regime cru, média das sementes:

| F | total | primeiro token (seleção) | forma | coeficiente | módulo | fim | fração no módulo |
|---|---|---|---|---|---|---|---|
| 0 | 108 | 19 | 40 | 20 | 20 | 9 | 0,19 |
| 1 | 41 | 0,0 | 2 | 17 | 22 | 0 | 0,53 |
| 2 | 45 | 0,0 | 2 | 17 | 23 | 4 | 0,50 |
| 4 | 46 | 0,0 | 2 | 16 | 24 | 3 | 0,53 |
| 8 | 55 | 0,0 | 3 | 18 | 28 | 5 | 0,52 |

Gargalo e nomeado: o mesmo desenho (F = 1: coeficiente 15–19, módulo 22–23; F = 8: módulo 24–27 no gargalo, 24 no nomeado).
A partir de F = 1, a seleção e a forma são de graça; **todo o preço está nas duas constantes fora da faixa**: o coeficiente (≈ 17 bits,
estável) e o módulo (≈ 22 bits em F = 1, **28 em F = 8**). O que sobe com a diversidade é o módulo: o modelo fica mais seguro de que
o módulo é 3, 5 ou 7. Previsto: ≥ 80 % no módulo; observado ≈ 50–55 % no módulo e ≈ 40 % no coeficiente — a previsão errou a divisão
e acertou o lugar (constantes, não forma nem seleção).

**M6 (família nova com armadilha; módulos dentro da faixa).** Regime cru, por semente (s1/s2):

| F | total | primeiro token | forma | coeficiente | módulo | fim |
|---|---|---|---|---|---|---|
| 0 | 73/72 | 17/21 | 27/20 | 6/6 | 12/13 | 11/12 |
| 1 | 26/29 | 0,0/**7,7** | 12,5/9,0 | 4,8/5,4 | 8,2/6,3 | 0/0,8 |
| 2 | 21/30 | 1,7/0,2 | 7,3/15,7 | 0,5/0,0 | 10,3/9,4 | 1,0/4,3 |
| 4 | 22/15 | 0,3/0,0 | 10,3/7,2 | 0,9/0,8 | 10,4/7,1 | 0,5/0 |
| 8 | 20/25 | 0,0/0,0 | 11,8/12,9 | 0,1/0,6 | 7,3/10,1 | 1,0/1,3 |

Por forma do invariante, em F = 8 (cru s1/s2; gargalo s1/s2):
- **dois campos** (`mod (+ x (* c y)) k`, ≈ 41 mundos): total **5,3/16,1** (gargalo **6,5/6,5**); forma 1,2/9,1 (1,1/1,7); coeficiente
  0,2/0,9 (0,2/0,4); **módulo 4,0/6,1 (5,2/4,4)**. O que resta de preço nos mundos que a diversidade comprou é o **módulo**: o modelo
  calcula k errado numa parte dos mundos (p(k verdadeiro) baixo em alguns, ≈ 1 nos outros).
- **um campo** (`mod y k`, ≈ 19 mundos): total **52/44** (gargalo 45/50); **forma 34,5/21,3 (27,8/27,7)**; módulo 14,4/18,6 (17,6/19,1).
  O preço está no token depois de `mod`: o modelo espera `+` e a referência escreve `y`. A forma de um campo não está no prior dos
  mundos de três campos, em nenhum F (F = 1: forma 19,8/17,2; F = 4: 27,4/27,3).
Previsto: em F = 1 preço na seleção e na forma; em F ≥ 4 nos coeficientes. Observado: em F = 1, forma e módulo (e a seleção só na
semente que caiu na armadilha); em F ≥ 4 os coeficientes ficam de graça e o que resta é o **módulo** (dois campos) e a **forma** (um campo).

## B. O que o modelo escreve no lugar do módulo novo (M2, posição do módulo sob forçamento; e decodificação gulosa)

Em todos os 30 modelos e 60 mundos, p(módulo verdadeiro) ≤ 1,8 × 10⁻⁴ (mediana da ordem de 10⁻⁶). A distribuição está toda em
{3, 5, 7}: média sobre mundos, cru F = 1: p(7) = 0,70/0,68, p(5) = 0,29/0,30, p(3) = 0,005/0,02; F = 8: p(7) = 0,885/0,888,
p(5) = 0,115/0,112, p(3) ≈ 0. **A escolha não depende do índice verdadeiro**: para n = 11, 13, 17 e 19 o argmax é 7 na grande maioria
e 5 no resto, nas mesmas proporções (por exemplo F = 8 cru s1: 9/0, 14/4, 12/0, 18/3 entre 7 e 5). A decodificação gulosa dos 60 mundos
de M2 confirma: 60/60 analisáveis, 0/60 válidas, módulo escrito 7 em 30–48 mundos, 5 em 10–27, 3 em 0–16 (só F = 2 s2 escreve 3
em 16). Com a diversidade, a massa concentra-se em 7 (0,70 → 0,89): o modelo "sabe" cada vez melhor que o módulo é o maior que conhece.

## C. Sabe mas não diz? (sondas lineares no fluxo residual, posição que prevê o módulo; 200 mundos novos por família)

| modelo | M1 (n ∈ {3, 5, 7}; acaso 0,33), melhor camada | M2 (n ∈ {11, 13, 17, 19}; acaso 0,25), melhor camada | M2 na camada 1 | ordenação numérica (Spearman máx.) |
|---|---|---|---|---|
| F1 cru s1/s2 | 1,00/1,00 | 0,385/0,470 | 0,37/0,335 | 0,07/0,16 |
| F1 gargalo s1/s2 | 1,00/1,00 | 0,485/0,445 | 0,435/0,36 | 0,18/0,08 |
| F4 cru s1/s2 | 1,00/1,00 | 0,530/0,475 | 0,39/0,30 | 0,15/0,06 |
| F4 gargalo s1/s2 | 1,00/1,00 | 0,470/0,460 | 0,305/0,40 | 0,14/0,18 |
| F8 cru s1/s2 | 1,00/1,00 | 0,480/0,490 | 0,315/0,37 | 0,16/0,22 |
| F8 gargalo s1/s2 | 1,00/1,00 | 0,575/0,435 | 0,35/0,29 | 0,06/0,12 |

Para os módulos do treino, o índice da rede é calculado e fica linearmente legível a partir da camada 3–4 (acurácia 1,0 em todos os 12
modelos). Para os módulos fora da faixa, o estado tem **informação parcial** (0,44–0,58 contra 0,25 de acaso, crescendo da camada 1
para as intermediárias em vários modelos) mas **nenhum eixo numérico**: a regressão que ordena 3 < 5 < 7 não ordena 11, 13, 17, 19
(Spearman ≤ 0,22). Dos dois desfechos previstos, este é o intermediário mais perto de "não calcula": o modelo não calcula o índice como
número que se estenda; distingue um pouco os mundos (traços que correlacionam com o índice), e escreve 7. A parede está sobretudo no
cálculo, não só na saída. Ressalva: a parte "parcial" pode vir de traços da entrada (tamanho dos geradores) e não de um cálculo do
índice; separar as duas coisas exigiria uma sonda sobre a entrada só, não feita aqui.

## D. Seleção: o modelo "vê" que M6 pede `mod` antes de escrever? (p(primeiro token = `mod` | prompt), média por mundo)

| F | cru s1/s2 | nomeado s1/s2 (p(`LINMOD`)) | um campo (cru) | dois campos (cru) |
|---|---|---|---|---|
| 0 | 0,000/0,000 | 0,000/0,000 | 0,0/0,0 | 0,0/0,0 |
| 1 | **1,000/0,008** | 0,61/0,71 | 1,0/0,004 | 1,0/0,009 |
| 2 | 0,60/0,91 | 1,00/1,00 | 0,67/0,89 | 0,58/0,92 |
| 4 | 0,89/1,00 | 0,97/1,00 | 0,80/1,00 | 0,93/1,00 |
| 8 | 1,00/1,00 | 1,00/1,00 | 1,0/1,0 | 1,0/1,0 |

A seleção é comprada cedo (F = 2) e por inteiro (F ≥ 4), **igualmente para os mundos de um campo que nunca são resolvidos**: o modelo
sabe que M6 pede `mod` e falha depois, na forma. A armadilha do plano capturou a seleção inteira de uma semente em F = 1
(p(`mod`) = 0,008; escreve a forma linear exata), e uma família a mais (F = 2) desfaz a captura. Em M2, p(`mod`) = 1,000 desde F = 1.

## Em palavras simples

O modelo guarda os números como uma lista, não como uma régua. Com variedade de famílias ele aprende o truque (resto da divisão) e
onde o truque entra; os números que já viu, ele calcula certo (3, 5 ou 7, lidos com acurácia perfeita por dentro). Quando o problema
pede um número que ele nunca viu, ele não o calcula: escolhe o maior da lista (7) na maioria das vezes, sem relação com o número
certo, e fica mais convicto disso quanto mais famílias viu. Nas famílias novas que ele consegue, o que ainda erra é o número (qual
resto), não a forma; a forma que nunca viu num mundo daquele tamanho (um só campo) ele não escreve mesmo sabendo que o truque é esse.

## O que não se afirma

Descritivo: sem ablação, sem patching, sem causalidade. Sondas lineares só mostram informação linearmente acessível. Duas sementes
de treino por célula; 200 mundos novos por família nas sondas. "Informação parcial" sobre o índice fora da faixa não foi separada de
traços da entrada. Nenhuma inferência sobre LLMs pré-treinados. As expectativas do protocolo eram guias de leitura, não regras: onde
erraram (divisão do preço em M2; coeficientes em M6) está dito acima.

## O que isto muda nas opções seguintes (decisão do Roberto; nenhuma admitida)

- A parede da faixa é uma parede de **cálculo**: o índice da rede não vira número fora do treino. A pergunta "diversidade de módulos no
  treino compra a faixa?" (opção 3 do E3) ganha uma versão mais interessante e mensurável com este instrumento: **o eixo numérico
  aparece na sonda quando o treino tem mais módulos** (interpolação contra extrapolação medida por dentro, não só por fora). Sabido:
  extrapolação numérica falha e interpolação funciona parcialmente; representações periódicas em aritmética modular. Acrescentaria:
  se e quando a representação do índice muda de categórica a numérica, e se isso acompanha a faixa. Custo ≈ US$3–5 (uma rodada de
  seis a oito corridas).
- O gargalo de tipo (opção 2) ajuda onde o preço restante é o módulo dos mundos de dois campos (4–5 bits contra 4–6 do cru: pouco) e
  sobretudo na forma (1,1/1,7 contra 1,2/9,1); o nomeado paga nos argumentos (coeficientes 15–26 bits em M6, F ≥ 4): o defeito de
  aridade da DSL, confirmado. Uma DSL de aridade fixa e mais sementes continuam a opção mais barata.
- O elo com o Qwen (opção 4) ganha uma medida concreta: o preço por token do invariante necessário, separando o token do operador,
  a forma e as constantes, nas paredes do paper 6.
