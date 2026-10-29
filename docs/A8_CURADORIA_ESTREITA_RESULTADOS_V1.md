# A8 — a curadoria estreita? Resultados (leitura do nó em 2026-09-19, 07:01, com um braço incompleto; segunda leitura declarada, A8-c, às 13:12 com o braço completo; status: INTERESSANTE)

*Pré-registro `docs/A8_CURADORIA_ESTREITA_V1.md` (17/09, 20:59), emendas operacionais E1–E3. Pergunta: dois adaptadores treinados nas
mesmas 135 células, um com as provas do próprio modelo e outro com as nossas provas curadas, testados com a base em quatro famílias de
degrau que nenhum viu; a curadoria estreita fora da distribuição, e o laço generaliza? Leitura pelo script escrito antes dos dados
(`scripts/analysis_a8_narrow.py` → `docs/a8_results/narrow.md`), feita **uma vez, com o braço curado incompleto** (27 de 72 células), a
alternativa registrada em E2 quando o Roberto decidiu não recarregar o RunPod. Evidência: `docs/a8_evidence_v1/` (1 209 arquivos, 69 MB,
manifesto verificado, incluindo as 23 sessões interrompidas ou cortadas do braço curado).*

## Leitura pré-registrada

| família | base | own2 (laço, sem curador) | curm2 (curado pareado) | own2 contra base | curm2 contra base | own2 contra curm2 |
|---|---|---|---|---|---|---|
| W1 Pell módulo primo | 0/18 (piso) | **13/18** | 0/4 | +0,72 (p = 0,016) ↑ | 0,00 | +0,78 (p = 0,125) |
| W2 rede no plano | 6/18 | 11/18 | 1/6 | +0,28 (p = 0,125) | −0,17 (p = 0,94) | +0,44 (p = 0,031) ↑ |
| W3 hiperbólica em 4 campos | 5/18 | **14/18** | 1/9 | +0,50 (p = 0,031) ↑ | −0,07 (p = 0,75) | +0,60 (p = 0,062) |
| W4 primo grande | 4/18 (piso) | **14/18** | 3/8 | +0,56 (p = 0,031) ↑ | +0,07 (p = 0,50) | +0,60 (p = 0,062) |

Regras: **P-generaliza ✓** (own2 sobe contra a base em três das quatro famílias; a regra pedia duas); **P-estreita ✗** (curm2 não cai contra
a base em família nenhuma pela regra). **Veredito pré-declarado: `self_generalises_only`.**

## Leitura

**O laço generaliza, e isso agora está medido com a regra do programa em quatro famílias novas.** O adaptador feito só com provas que o
modelo produziu e o verificador aceitou, sem nenhuma escolha nossa, resolve 52 de 72 células em degraus que nunca viu, contra 15 de 72
da base com o mesmo pensamento, gastando um quinto dos tokens (medianas por família de 19 a 52 mil contra 100 a 131 mil da base). É a
terceira medida independente do mesmo efeito, depois das iterações 1 e 2 do laço sem curador, e a primeira fora da escada em que ele foi
treinado.

**A curadoria não estreita abaixo da base, até onde o braço incompleto deixa ver; ela reproduz o esqueleto treinado e não compõe.** O
adaptador curado fica em 5 de 27, perto dos 21 % da base, e nenhuma família mostra queda pela regra; o 0 de 18 do A7 em W1 era próprio
daquele degrau, onde a base também está no piso. O que as submissões mostram (diagnóstico **posterior à leitura, sem regra**:
`scripts/a8_invariant_attempts.py` → `docs/a8_results/invariant_attempts.json`, e listagem à mão das 19 sessões do curado em W1–W3): o
curado escreve sempre `def measure` com um dos esqueletos do treino, escolhido pela superfície do mundo. Em W1, a forma de Pell exata, sem
o módulo p (0 de 4 com algo modular); em W2, a forma linear exata, que é a armadilha (1 de 6 com algo modular); em W3, a forma bilinear
com deslocamentos do L4, que é o tipo certo (9 de 9), e falha na execução (1 de 9 resolvida); em W4, a medida `% p` do L3 (8 de 8; 3
resolvidas). Onde a obstrução é a **composição** de dois esqueletos treinados (W1: quadrática e modular; W2: linear e modular), ele tenta
a composição em **1 de 10** sessões; a base em 35 de 36 e o adaptador do laço em 36 de 36. No total de W1–W3, o tipo necessário aparece
em 10 de 19 sessões do curado, 45 de 54 da base e 53 de 54 do laço. A base tem a ideia quase sempre (em W1, 17 de 18 escrevem algo
modular e nenhuma resolve) e perde na forma da prova, no teto de 131 mil tokens; o adaptador do laço tem a ideia e a forma. A leitura
honesta: **a curadoria não ajuda fora da distribuição; grava esqueletos que não se compõem; a medida da queda pela regra ficou pela
metade.**

**Por que ficou pela metade.** Três tentativas de completar o braço curado falharam por operação minha: um desligamento planejado (E1),
dois envios interrompidos por link ruim (E2) e, na terceira, um pod que ficou pronto uma hora depois de a cadeia de coleta ter desistido, e
que ficou cinco horas ocioso até o guarda removê-lo (E3, ≈ US$37 sem dado). O Roberto decidiu não recarregar; a leitura foi feita com o que
havia, como a E2 previa. Não há como reabrir esta leitura; uma medida completa do estreitamento exigiria um pré-registro novo.

## O que não se afirma

Uma base, dois adaptadores de uma mesma receita, quatro famílias construídas por nós, três tentativas por instância; o braço curado com 27
células em 19 das 24 instâncias, o que torna a regra P-estreita quase inatingível (poucas instâncias pareadas por família) e não permite
dizer que a curadoria **não** estreita, só que não se viu queda. "Curadoria" aqui é a nossa referência uniforme, não curadoria em geral.

## Operação e custo

Coleta principal em 17→18/09 (base e own2 completos, ≈ US$46); três tentativas de completar o braço curado (≈ US$2 + US$37 + a parte
útil de 27 células na primeira noite). Saldo RunPod US$124 → US$40,81. Guarda corrigido depois do erro: passa a remover o pod assim que
a cadeia de coleta deixa de existir (`A2C3_CHAIN_PATTERN`), não só por marcador ou prazo.

## Status: INTERESSANTE

Positivo firme na metade que tinha dados completos (o laço generaliza a famílias novas, 3 de 4 pela regra) e pergunta central meio
respondida (a curadoria não cai abaixo da base pela regra; reproduz o esqueleto treinado mais próximo e compõe dois esqueletos em 1 de 10
sessões, contra 35/36 da base e 36/36 do laço; a queda pela regra ficou sem poder com 27 células). Consequências: o paper
separado do A2 ganha a generalização fora da escada como resultado, e a curadoria entra como observação descritiva com n declarado; a
medida completa do estreitamento fica anotada na árvore como pendência barata para quando houver saldo.

## A8-c — segunda leitura, com o braço curado completo (19/09, 13:12; registrada às 13:15)

*Declarada antes de qualquer célula nova (E4 do pré-registro, 07:54). Mesmo script, mesmas regras, arquivos próprios
(`docs/a8_results/narrow_c.{md,json}`); a leitura das 07:01 continua sendo a leitura do nó. As 45 células pendentes rodaram em 19/09 das 08:22
às 13:12 num pod novo com o mesmo comando de instalação e as mesmas flags; 27 células foram refeitas por corte de transporte (33 repetições,
nenhuma esgotou as três); **72 de 72 observadas**. Evidência `docs/a8c_evidence_v1/` (694 arquivos, verificado), commit automático
`d5f3e79e` antes de qualquer interpretação.*

| família | base | own2 (laço) | curm2 (curado, completo) | curm2 contra base | own2 contra curm2 |
|---|---|---|---|---|---|
| W1 | 0/18 (piso) | 13/18 | **0/18** | 0,00 | +0,72 (p = 0,016) ↑ |
| W2 | 6/18 | 11/18 | 7/18 | +0,06 (p = 0,50) | +0,22 (p = 0,062) |
| W3 | 5/18 | 14/18 | 3/18 | −0,11 (p de queda = 0,38) | +0,61 (p = 0,031) ↑ |
| W4 | 4/18 (piso) | 14/18 | 6/18 | +0,11 (p = 0,38) | +0,44 (p = 0,078) |

**Veredito da segunda leitura: `self_generalises_only`, o mesmo.** Com o braço completo a regra P-estreita tinha poder e **não passou**: o
adaptador curado resolve 16 de 72 (22 %), a base 15 de 72 (21 %). A curadoria **não estreita abaixo da base** fora da distribuição; o 0 de 18 do
A7 era de W1, onde a base também fica em zero. O que o curado perde é para o laço, não para a base: own2 sobe contra ele pela regra em W1 e W3
e fica no limiar em W2 e W4.

**As formas, agora com 72 sessões** (classificador validado do A6): a primeira submissão do curado é **uniforme por família**: Pell exata em
18 de 18 de W1 (e nenhuma submissão de nenhuma sessão chega ao módulo: 0 de 18 resolvidas), linear exata em 18 de 18 de W2 (a armadilha; 8
sessões consertam para o módulo e 7 delas resolvem), bilinear com deslocamentos em 18 de 18 de W3 (tipo certo, 3 resolvidas) e `% p` em 18 de
18 de W4 (tipo certo, 6 resolvidas). Composição de dois moldes (W1 e W2): 8 de 36 sessões, contra 35 de 36 da base e 36 de 36 do laço. O
curado **escreve o molde treinado mais parecido com o mundo, sempre**; conserta às vezes quando o conserto é acrescentar um módulo a uma
forma linear (W2), nunca quando é acrescentá-lo a uma quadrática (W1); e onde o molde é o tipo certo, executa pior que o laço (3/18 e 6/18
contra 14/18 e 14/18).

**Custo**: ≈ 5 h 15 de H200 ≈ US$24. A causa dos cortes de transporte foi identificada durante a coleta (pedidos além da capacidade de cache
do servidor esperam sem bytes até o proxy cortar) e tratada para o A9 (E1 do A9); o A8-c terminou com o mesmo paralelismo das 27 primeiras
células.

## Errata (08:05 de 19/09)

A versão das 07:10 dizia que, fora da forma do L3, o curado escrevia o tipo de invariante necessário em 1 de 19 sessões (base 45/54, laço
48/54). O número estava errado: o detector de forma quadrática procurava `^2`/`sq` e não via formas bilineares escritas como produto, que é
como a forma hiperbólica de W3 é escrita (`(s.x - 2) * (s.z - 3) - …`). Apontado por uma sessão paralela do Roberto; conferido aqui com o
detector corrigido (produto de dois fatores com campos do estado, `has_field_product`) e com a listagem à mão das 19 sessões: W3 é 9 de 9,
não 0 de 9; o total é 10 de 19; o laço vai a 53/54; a base fica em 45/54. A leitura pré-registrada, as taxas e o veredito não mudam. Muda o
diagnóstico descritivo: o curado não deixa de tentar; ele reproduz o esqueleto treinado mais próximo da superfície do mundo e não compõe
dois esqueletos.
