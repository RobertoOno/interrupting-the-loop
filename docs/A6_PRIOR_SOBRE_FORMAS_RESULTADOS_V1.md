# A6 — o prior sobre formas: resultados (2026-09-19, 08:28; status: PROVEITOSO como instrumento, secundário e descritivo)

*Método registrado antes de rodar (`docs/A6_PRIOR_SOBRE_FORMAS_V1.md`, commit `f8381cce`, 08:19). 3 021 sessões observadas do provador (3 066 depois do A8-c)
(Qwen3.8-27B e adaptadores) em 32 braços de A2, réplica, E8, laço sem curador (iterações 1 e 2), A7 e A8. Sem GPU. Tabela
`docs/a6_results/sessions.jsonl`, relatório `docs/a6_results/report.md` (`scripts/a6_forms.py`, `scripts/a6_model.py`). Nenhuma regra primária
de nenhum nó muda; as taxas já estavam lidas.*

## O instrumento passou nos dois critérios de morte

**Classificador** (tipo de invariante da primeira submissão: linear, linear com módulo, quadrática diagonal, quadrática mista, quadrática com
módulo, nenhuma). Validação à mão, rotulando antes de ver o rótulo automático: **57 de 60 (95 %)** na amostra estratificada, acima do critério
de 90 %. As três discordâncias: a notação `≡ … [ZMOD 5]` não era reconhecida; invariância escrita como relação entre dois estados sem as
palavras Step/Reaches; e uma prova por parametrização de Fibonacci, fora da taxonomia. As duas primeiras foram corrigidas e o classificador
corrigido foi conferido numa **segunda amostra nova de 40: 40 de 40**. O classificador reproduz as duas listagens à mão das erratas de hoje
(L4 do own2: 16 lineares e 8 diagonais; curado no A8: Pell exata, linear exata, bilinear, `% p`).
**π e θ se distinguem**: 17 contrastes de θ têm intervalo de 90 % fora do zero.

## O que π e θ dizem (mediana e intervalo de 90 %, bootstrap bayesiano sobre instâncias)

**Q1, consolidação curada sem pensamento.** A base já escreve o tipo certo nos degraus baixos (π = 0,98 em L1, 0,92 em L3, 0,59 em L2) e não
executa (θ = 0,19; 0,02; 0,03). Em L1 a consolidação moveu só θ (+5,4 nats); em L2 moveu π a ≈ 1 e **não** moveu θ (−1,5 e +0,4 nas duas
rodadas): a forma gravada com coeficientes chutados, agora como número. Em L4, L5 e E moveu os dois (π da base em E era 0,22). Previsão
registrada: certa em L2; **errada em L3**, onde θ subiu +2,9 nats (de 0,02 a 0,29), ainda longe de 1.

**Q2, o laço contra o curado em famílias novas (A8, com pensamento). O achado do nó.** A previsão era "own2 e base têm π alto e diferem em θ".
Metade errada: **o adaptador do laço acerta o tipo na primeira submissão MENOS vezes que a base** (π own2: 0,13 em W1, 0,24 em W2, 0,40 em W4;
base: 0,50, 0,82, 0,93; Δlogit π entre −1,9 e −3,0). Ele começa pela forma mais simples do repertório (Pell exata em W1, linear exata em W2 e
W4, as armadilhas), é rejeitado, e **conserta**: das sessões que começam com o tipo errado, chegam ao tipo certo depois 10 de 16 em W1 (9
resolvidas), 14 de 14 em W2 (8 resolvidas), 9 de 11 em W4 (7 resolvidas). A base quase nunca conserta (W1: 0 de 9 que começam errado) e,
quando começa certo, não executa (W1 0/9, W2 4/15, W4 4/17). O curado começa certo onde um esqueleto treinado serve (π = 0,97 em W3 e W4) e
zero onde é preciso compor (0 de 18 em W1 e em W2), conserta só em W2 (8 de 18 sessões chegam ao módulo, 7 resolvidas; em W1 nenhuma) e
executa mal (θ = 0,15 em W3, contra 0,89 do laço). *(Números do curado atualizados às 13:15 de 19/09 com o braço completo do A8-c, 72 sessões;
a versão das 08:28 usava as 27 sessões então disponíveis e dizia "nunca conserta".)*
Leitura: **o que o laço melhorou fora da distribuição não é a ideia inicial, é a execução e o conserto sob o verificador, a um quinto dos
tokens.** A base tem a ideia e não tem a mão; o laço tem a mão e chega à ideia por tentativa; o curado tem o molde.

**Q3, a parede do laço em L4 é de π, não de θ.** π(`quad_mixed`) na primeira submissão: own2 0,02 (sem pensar) e 0,05 (pensando), contra 0,85
do curado e 0,54 da base com pensamento. Quando o own2 com pensamento chega ao tipo certo (10 de 23 sessões consertam), resolve metade (θ = 0,72
nas que têm o tipo certo); as 13 que nunca chegam resolvem zero. Previsão certa.

**Q4, o pensamento move θ, não π.** Com a forma gravada (p2), pensar dá +3,7 e +2,7 nats em θ em L2 e L3, e π cai um pouco (0,98 → 0,95 e
0,91). Sem a forma (base), pensar também move θ (+1,6 e +3,1) e π só em L2 (+1,0). Previsão certa.

## Uma frase

Nos dados que temos, **π (que forma o modelo tenta) é escrito pelo que ele viu em treino**, e é onde estão as duas paredes medidas: a do laço
em L4 (nunca produziu a forma mista, então nunca a tenta) e a do curado em W1/W2 (tem os moldes e não os compõe). **θ (executar e consertar)
é o que a prática verificada e o pensamento melhoram**, e é o que generaliza.

## O que não se afirma

Análise secundária sobre dados já lidos; classificador heurístico (95 % e 100 % em duas amostras, não em tudo); "forma" é o tipo do
invariante, não a prova; com pensamento, a primeira submissão já passou por raciocínio; θ por tipo tem n pequeno em várias células (os
intervalos dizem quanto); o braço curado do A8 entrou completo (72 sessões) na atualização das 13:15. Um modelo, um gerador de mundos nosso.

## Consequências

Para o paper separado do A2: a decomposição π/θ substitui as frases sobre "forma" por números, e o resultado Q2 muda a história do A8: a
generalização do laço é de **conserto e execução**, não de ideia inicial. Para o A9 (em curso): W5 exige compor duas formas; a pergunta vira
se o own3 tenta a composição de primeira (π) ou chega a ela consertando. Para o desenho do próximo nó: mover π sem curadoria é o problema em
aberto, e é o nome técnico do que o Roberto chama de descoberta sem dica.
