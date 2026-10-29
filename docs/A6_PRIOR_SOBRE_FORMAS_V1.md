# A6 — o prior sobre formas como objeto: π (o que o modelo tenta) separado de θ (como executa). Registro do método (2026-09-19, 08:19)

*Nó anotado em 13/09 a pedido do Roberto (leitura 2 da árvore: "o prior sobre formas, com classificador de forma e posteriores largos, como
análise secundária pré-registrada, sem tocar a regra primária"). Iniciado em 19/09 em paralelo ao A8-c/A9, sem GPU. **Não é confirmatório**:
as taxas de todos estes nós já foram lidas, e duas contagens de forma já foram olhadas hoje (as erratas do A8 e da iteração 2, ambas por
detector errado meu). Justamente por isso o método fica escrito antes de rodar: taxonomia, classificador, validação à mão com critério de
morte, modelo e perguntas. Nenhuma regra primária de nenhum nó muda.*

## Objeto

Por sessão do provador (Qwen3.8-27B e adaptadores; mundos da escada L1–E e das paredes W1–W5):
**forma** = o tipo de invariante que a **primeira submissão** declara (o prior do modelo sobre formas, antes de qualquer retorno do
verificador); **sucesso** = a sessão terminar resolvida. Modelo: forma ~ Categórica(π[condição, degrau]); sucesso | forma ~
Bernoulli(θ[condição, degrau, forma]). Uma intervenção (adaptador, pensamento, exemplo) pode mover π, θ ou os dois; a permutação sobre
taxas não distingue.

## Taxonomia (tipo de invariante, não nome nem tática)

`linear` (função linear dos campos, exata) · `linear_mod` (linear com módulo ou divisibilidade) · `quad_diag` (só quadrados, exata) ·
`quad_mixed` (produto de campos diferentes, exata) · `quad_mod` (quadrática, diagonal ou mista, com módulo) · `none` (nenhuma função do
estado na primeira submissão, ou nenhuma submissão). Tipo necessário por degrau, fixado pelo gerador: L1 e L2 `linear`; L3, W2 e W4
`linear_mod`; L4 e W3 `quad_mixed`; L5 e E conforme a forma de referência do gerador (lida do mundo, não suposta); W1 e W5 `quad_mod`.
**Tipo certo** = a primeira submissão declara o tipo necessário do degrau.

## Classificador e validação (critério de morte 1)

Heurístico, sobre o código Lean que o verificador recebeu (`scripts/a6_forms.py`): expressão da função do estado (`def`/`let`/`have` sobre
`State`, qualquer nome), produto de fatores com campos (`has_field_product`), campos diferentes no produto (misto) ou iguais (diagonal),
marcadores modulares na submissão. **Validação à mão**: amostra estratificada de 60 sessões (nó × braço × degrau, semente fixa 20260919),
rotulada por leitura antes de ver o rótulo do classificador; concordância no tipo (seis classes) ≥ 90 % ou o nó para aqui e fecha como
limite do instrumento. Discordâncias listadas no relatório.

## Modelo e incerteza

Unidade = instância. Para cada (condição, degrau): π = taxa de tipo certo na primeira submissão; θ_certo = taxa de sucesso das sessões que
declararam o tipo certo; θ_errado idem para as demais. Incerteza por **bootstrap bayesiano sobre instâncias** (pesos Dirichlet(1,…,1), 4 000
réplicas, semente fixa), com suavização de Jeffreys (+½) dentro de cada instância para evitar logits infinitos; contrastes entre condições
pareados por instância quando as instâncias são as mesmas. Reporta-se mediana e intervalo de 90 % de Δlogit π e Δlogit θ_certo, em nats.
Decomposição: P(sucesso) = π·θ_certo + (1−π)·θ_errado.

## Perguntas (escritas antes de rodar)

- **Q1, consolidação curada (A2 e réplica, sem pensamento)**: o adaptador p2 move π, θ ou os dois em relação à base, por degrau? Previsão
  registrada: move π a ≈ 1 em todos os degraus (grava a forma) e θ só onde a forma não tem parâmetros a inferir (L1, L4, L5, E), não em L2/L3.
- **Q2, laço contra curado fora da distribuição (A8, com pensamento)**: own2, curm2 e base em W1–W4. Previsão: own2 e base têm π alto
  e diferem em θ (a base tem a ideia e perde na forma); curm2 tem π baixo onde o tipo necessário é uma composição (W1, W2) e π alto com θ
  baixo onde um esqueleto treinado serve (W3, W4).
- **Q3, a parede do laço em L4 (iteração 2)**: π(`quad_mixed`) de own2 contra base com pensamento e curados. Previsão: ≈ 0 contra ≈ 0,6 e 1.
- **Q4, pensamento (E8 e P4)**: com a forma gravada (p2), o pensamento move θ e não π? Previsão: sim (π já é ≈ 1; θ sobe em L2/L3).
- **Critério de morte 2**: se os intervalos de Δlogit θ_certo forem largos demais para separar qualquer par de condições nas quatro
  perguntas (todos contendo zero), π e θ não se distinguem com estes dados e o nó fecha como limite.

## O que não se afirma

Classificador heurístico validado numa amostra, não em tudo; "forma" é o tipo de invariante declarado, não a prova inteira; a primeira
submissão com pensamento já passou por raciocínio, então π com pensamento é o prior **depois** de pensar; sessões sem submissão entram como
`none`. Análise secundária e descritiva sobre dados já lidos: serve para orientar o paper e o desenho do próximo nó, não para vereditos.
