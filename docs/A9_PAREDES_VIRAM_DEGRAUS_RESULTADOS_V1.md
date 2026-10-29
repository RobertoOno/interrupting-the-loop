# A9 — as paredes viram degraus? Resultados (leitura única, 2026-09-20, 01:40; registrada às 01:44; status: LIMITE, com achados descritivos)

*Pré-registro `docs/A9_PAREDES_VIRAM_DEGRAUS_V1.md` (19/09, 08:16, antes de qualquer sessão), emendas operacionais E1 (09:27, 12 sessões no
cliente) e E2 (14:28, keepalive e silêncio máximo de 600 s no stream), ambas anteriores a qualquer observação do A9. Pergunta: mais uma volta
do laço, agora com as 52 provas que o próprio own2 produziu nas paredes, **compõe** (resolve uma família nova que exige duas formas que ele
aprendeu), **barateia** (resolve sem pensar o que antes exigia pensar) ou **satura**? Leitura pelo script escrito antes dos dados
(`scripts/analysis_a9.py` → `docs/a9_results/read.md`), feita uma vez pela cadeia, com todos os onze braços completos (594 sessões, zero não
observadas). Evidência `docs/a9_evidence_v1/` (3 702 arquivos, manifesto verificado); commit automático `ac655a5c` antes de qualquer
interpretação.*

## Leitura pré-registrada: `saturates`

| bloco | own3 | own2 | base | own3 contra own2 |
|---|---|---|---|---|
| **W5 (família nova, composição), com pensamento — primário** | 9/18 | 7/18 | 1/18 | +0,11 (p = 0,375) |
| W5, sem pensamento | 0/18 | 0/18 | | 0,00 (piso) |
| W1–W4 novas, sem pensamento | 2, 1, 0, 0 de 18 | 0, 0, 0, 0 | 0, 0, 0, 2 | +0,11; +0,06; 0; 0 (piso) |
| W1–W4 novas, com pensamento | 8, 15, 14, 12 de 18 | 9, 13, 11, 14 | | −0,06; +0,11; +0,17; −0,11 |
| escada original, sem pensamento (retenção) | L1 20, L2 2, L3 2, L4 2, L5 17, E 21 de 24 | 19, 0, 1, 0, 16, 24 (16/09) | | nenhuma queda pela regra |

**P-compõe ✗** (em W5 o own3 não sobe contra o own2). **P-barateia ✗** (sem pensamento, nenhuma família sobe: 3/72 contra 0/72).
**P-retém ✓** (nenhuma queda na escada nem em W1–W4). Veredito pré-declarado: **`saturates`**. Pelo critério de morte escrito antes, a linha
"mais uma volta na mesma família" encerra aqui: a terceira volta não acrescentou nem composição nem barateamento nesta escala, e também não
estragou nada.

## O que os dados mostram além do veredito (descritivo, sem regra)

**1. A generalização do laço chega a uma quinta família.** W5 é dura para a base: 1 de 18, com 13 sessões no teto de 131 mil tokens. Os
adaptadores do laço resolvem 7 e 9 de 18; own3 contra a base +0,44 (p = 0,016, passa a regra do programa), own2 contra a base +0,33
(p = 0,125). Nenhum dos dois viu W5; o own3 viu provas próprias de W1 e W3, as duas peças.

**2. A terceira volta moveu π e não moveu a taxa.** Com o classificador validado do A6, o tipo de invariante da **primeira** submissão:

| com pensamento | W1 | W2 | W3 | W4 | resolvidas |
|---|---|---|---|---|---|
| own2: tipo certo de primeira | 4/18 | 0/18 | 5/18 | 9/18 | 47/72 |
| own3: tipo certo de primeira | **13/18** | **9/18** | **17/18** | 9/18 | 49/72 |

O que o own2 alcançava **consertando** (8 de 12 em W1, 13 de 18 em W2, 6 de 8 em W3), o own3 escreve **de primeira**, e o total resolvido é
o mesmo. Em W3 isso poupa tokens (mediana 17 mil contra 61 mil). O conserto virou hábito; o alcance não cresceu. Sem pensamento o mesmo
movimento aparece sem a execução: o own3 escreve o tipo certo em 14 de 18 em W1 e em 18 de 18 em W3 (own2: 5 e 3) e resolve 2 e 0. É o padrão
de L2 e L3 no A2: **a forma grava, a execução com parâmetros a inferir não**; E e L5 baratearam na iteração 2 porque as provas de lá são
curtas e sem parâmetro.

**3. Sem pensamento, o adaptador do laço se comporta como o curado.** Em W5 sem pensamento, o own3 escreve o molde de W3 (a forma bilinear
exata) em **18 de 18** primeiras submissões e nunca a composição: o molde treinado mais parecido com o mundo, exatamente o que o adaptador
curado fazia no A8. Com pensamento, o mesmo own3 tenta a composição em 14 de 18 sessões (own2 em 7, base em 12). **Quem compõe é o
pensamento, não os pesos**; os pesos trazem os moldes.

**4. A base tem a ideia também em W5.** Tenta a composição já na primeira submissão em 10 de 18 sessões, mais que os dois adaptadores (own3
5, own2 1), e resolve uma. É o mesmo retrato de W1 no A8: ideia sem mão.

## Um defeito do instrumento, achado na leitura das provas

O certificado de W5 testava invariantes lineares exatos e formas lineares módulo m. Lendo as provas aceitas apareceram **dois atalhos que ele
não testava**: (i) **invariante de ordem**: W5 só tem movimentos "para frente" (tirei os cisalhamentos inversos de W3 para caber as
translações), então regiões como x ≥ a e y ≥ b podem ser fechadas pelos movimentos e o alvo cair fora; (ii) a órbita modular do **par** de
formas (x + z, y + w). Das 17 sessões resolvidas em W5, 4 usaram atalho (own2 três, own3 uma); pela rota pretendida (forma quadrática
módulo p) as contagens são base 1, own2 4 e own3 8 de 18 (`scripts/a9_w5_routes.py` → `docs/a9_results/w5_routes.json`). **Contagem posterior,
sem regra**: own3 contra own2 só na rota pretendida dá +0,22 (p = 0,11), que também não passaria. Uma prova verificada é uma prova; a leitura
pré-registrada conta todas e fica como está. Para uma próxima família: exigir inversos ou testar invariantes de ordem e projeções modulares em
duas dimensões no certificado.

## O que não se afirma

Um modelo, uma receita, um gerador nosso, seis instâncias por família, três tentativas. `saturates` vale para **esta** terceira volta, com 52
provas novas de quatro famílias e um teste de composição de duas delas; não diz que nenhum laço satura sempre. O teste de composição tinha
poder limitado (seis instâncias; own2 já em 0,39) e um instrumento com atalhos. O comparador de retenção é um run de 16/09. Os achados 2–4
são descritivos e vêm de um classificador heurístico validado em amostra (A6), não de regra.

## Operação e custo

Janela única de 17 h 42 de H200 (19/09 07:57 → 20/09 01:40; 1 062 min ≈ US$82): A8-c ≈ US$24, treino ≈ US$2, A9 ≈ US$56; saldo US$190,81 →
US$108,99. Dois incidentes meus ou de rede, ambos antes de qualquer observação afetada e ambos registrados: o guarda `pgrep` que impedia o
servidor de subir (12 min) e a queda silenciosa de rede às 13:43 que ensurdeceu doze sessões por 40 min (E2). Depois das 14:24: **zero falhas
de transporte nas 594 sessões observadas do A9** (576 delas já com o cliente corrigido). A cadeia leu, arquivou, commitou, publicou e removeu o pod sozinha à 01:40; guarda e armadilha
do script confirmaram que não havia mais pod.

## Status: LIMITE

A pergunta do nó teve resposta limpa e negativa: acumular mais uma volta na mesma família **satura**; não compõe, não barateia, não esquece.
O que fica de útil é o retrato do mecanismo, coerente com o A6: consolidar move π para as formas que o modelo já produziu (o conserto vira
primeira tentativa) e não estende o que ele consegue resolver; sem pensamento, pesos consolidados, próprios ou curados, escrevem o molde mais
parecido; compor é trabalho do pensamento. O problema em aberto continua com o mesmo nome: mover o alcance, isto é, π para formas que o modelo
**nunca** produziu, sem que alguém as mostre.
