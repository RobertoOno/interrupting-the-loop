# A2 sem curador, iteração 2 — resultados (leitura única, 2026-09-16, 16:29; status: PROVEITOSO)

*Pré-registro `docs/A2_SEM_CURADOR_ITER2_V1.md` (15/09, 16:30), com duas observações registradas antes de qualquer célula de teste, a
segunda corrigindo a primeira. Pergunta: a escada sobe sem curador? Leitura pelo script escrito antes dos dados
(`scripts/analysis_a2_own2.py` → `docs/a2c4_results/own2.md`); diagnósticos em `docs/a2c4_results/diagnostics.md`; evidência integral em
`docs/a2c4_evidence_v1/` (4 613 arquivos, 179 MB, manifesto SHA-256 verificado, incluindo as 17 células refeitas por corte do proxy).*

## Fase 1 — produção e comparador

O adaptador da iteração 1 (`a2c3-own`, treinado só com provas próprias de L1–L3) com pensamento a 131 072 tokens tentou uma vez L4, L5 e
E das 48 instâncias de treino: **75/144 provas verificadas** (E 38/48, L5 35/48, **L4 2/48**). Portão de 12 passado com folga. Conjunto
cumulativo de 135 exemplos próprios (60 da iteração 1, byte-idênticos, mais 75) e 135 curados pareados; 270/270 recompilados. Dois LoRA
(108 passos, semente 2026091502): `a2c4-own2` e `a2c4-curm2`. O comparador, a base com o mesmo pensamento nas seis instâncias retidas,
fez E 12/24, L5 10/24, L4 9/24: sem teto para a regra.

## Fase 2 — leitura pré-registrada (seis instâncias retidas, 24 células por degrau)

Sem pensamento:

| braço | L1 | L2 | L3 | L4 | L5 | E |
|---|---|---|---|---|---|---|
| base | 4 | 0 | 0 | 0 | 1 | 0 |
| own (iteração 1) | 24 | 0 | 1 | 0 | 0 | 0 |
| **own2** (iteração 2, sem curador) | 19 | 0 | 1 | 0 | **16** | **24** |
| curm2 (curado pareado) | 24 | 1 | 13 | 8 | 24 | 24 |
| p2 (curado, seis formas, 288 exemplos) | 24 | 1 | 7 | 24 | 24 | 24 |

Com pensamento a 131k:

| braço | L2 | L3 | L4 | L5 | E |
|---|---|---|---|---|---|
| base (baset131) | 6 | 8 | 9 | 10 | 12 |
| own (ownt131, iteração 1) | 21 | 19 | — | — | — |
| **own2t131** | 20 | 17 | 6 | 22 | 22 |
| curm2t131 | 16 | 11 | 6 | 24 | 24 |

Regras (subida = sign-flip unilateral p < 0,05 sobre as seis instâncias e diferença agrupada ≥ 0,25):
- **P-subida-simples ✓**: own2 sobe contra a base em L5 (+0,62, p = 0,031) e em E (+1,00, p = 0,016).
- **P-subida-pensamento ✗**: own2t131 contra baset131 em L5 +0,50 e em E +0,42, ambos com p = 0,062 (cinco das seis instâncias na
  direção certa, uma empatada); em L4, −0,12.
- **Retenção**: sem queda pela regra. own2 contra own em L1 −0,21; own2t131 contra ownt131 em L2 −0,04 e L3 −0,08.
- **Valor da curadoria ✓**: curm2 sobe contra own2 em L3 (+0,50, p = 0,031).

**Veredito pré-declarado: `ladder_climbs_without_curator`.**

## Leitura

**A escada subiu dois degraus sem curador.** A cadeia inteira foi feita pelo laço: a base com pensamento produziu provas de L1–L3; elas
foram consolidadas sem seleção; esse adaptador, com pensamento, produziu provas de E e L5, degraus que nunca viu; elas foram
consolidadas de forma cumulativa; e o adaptador resultante resolve **E em 24/24 e L5 em 16/24 nas instâncias retidas, sem pensamento, no
primeiro turno, com mediana de ≈ 540 tokens**. A base sem pensamento faz 0/24 e 1/24. A base com pensamento pleno faz 12/24 e 10/24
gastando ≈ 100 mil tokens por sessão. O modelo consolidado, de primeira e sem pensar, supera o melhor esforço do modelo original.

**Com pensamento, a subida é direcional mas não passa a regra.** own2t131 chega a 22/24 em E e em L5 contra 12 e 10 da base com o mesmo
pensamento, com p = 0,062 nos dois degraus. Fica registrado como o que é: direção consistente, abaixo do limiar pré-declarado.

**L4 é a parede do laço, e agora ela tem mecanismo.** A produção só rendeu duas provas de L4. Nas instâncias retidas, **nenhuma primeira
submissão de L4 dos adaptadores próprios declara uma medida** (own2 e own2t131), e nenhuma é válida; **todas as primeiras submissões dos
adaptadores curados declaram** (curm2 e curm2t131), e 8 e 6 delas são válidas. O curado pareado tem só duas linhas de L4 no treino, as
mesmas duas células que o laço resolveu, e mesmo assim resolve 8/24 no primeiro turno. As duas provas próprias de L4 não transferem nada.
O laço grava o estilo que ele mesmo usa (indução direta, sem lema auxiliar), e esse estilo não serve a um degrau que exige uma medida
quadrática com deslocamentos. A observação de ontem à noite, feita em instâncias diferentes, sugeria uma queda grande em L4; nas mesmas
células a diferença contra a base com pensamento é −0,12, fora da regra. O que se confirma não é uma queda de taxa, é a forma: o laço
nunca escreve a medida. *(Errata de 19/09, no fim: esta contagem era do nome `measure`; o mecanismo correto é invariante do tipo errado.)*

**O que a curadoria compra, pela segunda vez: eficiência sem pensamento, não taxa com pensamento.** Sem pensamento, curm2 resolve 94 das
144 células (93 no primeiro turno, mediana de 458 tokens) contra 60 do own2. Com pensamento, o curado fica igual ou abaixo do próprio em
L2–L4, e em L3/L4 o raciocínio atrapalha o adaptador curado: curm2t131 resolve L3 em 11/24 contra 13/24 sem pensar, com mediana de
121 mil tokens e respostas truncadas no teto.

## O que isto é e o que não é, nos três sentidos discutidos em 16/09

- **Novo para os pesos**: sim, e forte. O que custava 100 mil tokens de raciocínio a 50 % sai no primeiro turno a 100 % em E.
- **Novo para o repertório**: sim, na medida desta escada. O laço chegou a E e L5 a partir só de dados de L1–L3, sem curador, e o
  modelo consolidado supera a base com pensamento pleno nesses degraus.
- **Novo para o sistema**: esta escada não pode responder, porque a base com pensamento alcança todos os degraus. O nó A7 (instrumento
  com parede real) fica como a próxima pergunta de programa.

Limites: uma família de alvos, seis instâncias retidas, um modelo, uma semente por iteração, duas iterações; comparações com pensamento
em servidores de instâncias diferentes (mesmos pesos, mesma amostragem, mesmas células).

## Operação e custo

Pod da produção `d99xqqrqnpm3jw` (15/09 15:40 → 16/09 02:27, 647 min) e pod de treino e teste `8gaopo8p9wlqpc` (02:54 → 16:29, 815 min),
H200 a US$4,59/h, ambos removidos pelos scripts e confirmados pela API: ≈ 24,4 h ≈ US$112, acima da estimativa de US$95–105 porque
curm2t131 precisou de três rodadas (cortes do proxy e sessões longas no teto). Saldo RunPod US$175,37 → US$62,65. Zero Bedrock. Cadeia
autônoma da produção à leitura.

## Status: PROVEITOSO

O laço produz, verifica, consolida e sobe sem curador enquanto a produção alcança o degrau seguinte, e para onde a própria forma não
serve. Decisões com o Roberto: (i) nó A7, um instrumento em que a base com pensamento pleno fique em zero, para a pergunta de novo para o
sistema; (ii) o estreitamento de estilo em L4, testável barato misturando na produção provas da base e do adaptador; (iii) paper separado
com A2, réplica, E8 e as duas iterações sem curador; (iv) recarga do RunPod antes de qualquer nova rodada de GPU.

## Errata (08:05 de 19/09) — o mecanismo de L4

A frase "nenhuma primeira submissão de L4 dos adaptadores próprios declara uma medida" contava o **nome** `measure`, que é a nomenclatura
das nossas referências curadas. Contando o que está escrito (`scripts/a2c4_l4_forms.py` → `docs/a2c4_results/l4_first_submission_forms.json`;
as 24 sessões de own2 conferidas à mão): own2 declara uma função do estado em **24 de 24** primeiras submissões (nomes `inv`, `q`,
`state_inv`, `invariant`), mas do tipo errado: forma **linear** em 16 e quadrática **diagonal** (x² − 2y² + z², com deslocamentos) em 8. O
termo misto que o L4 exige (produto de campos diferentes, como em `(s.x - 4) * (s.z - 3) - 2 * (s.y - 3) * (s.y - 3)`) aparece em **0 de
24**, em nenhuma submissão de nenhuma sessão. Os curados escrevem o termo misto em 20 de 20 (curm2) e 21 de 21 (curm2t131) primeiras
submissões; a base com pensamento em 14 de 22; own2 com pensamento em 1 de 24 na primeira submissão e em 11 de 24 ao longo da sessão (6
resolvidas). O mecanismo correto é **invariante do tipo errado**, não falta de medida: o laço reproduz as formas que ele mesmo produziu
(linear de L2, quadrática diagonal de E/L5) e nunca produziu a forma mista. Taxas, regras e veredito não mudam. Apontado por uma sessão
paralela do Roberto; os números dela para own2 e curm2 (3/24 e 12/20) vinham de outro detector heurístico; a listagem à mão fixa 8/24
quadráticas, 0/24 mistas e 20/20.
