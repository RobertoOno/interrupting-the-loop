# A7 — instrumento com parede real (pré-registro, 2026-09-16, 21:18, commit `b7811841`)

*Decisão do Roberto em 16/09 à noite ("vamos anotar tudo e seguir com o A7"), depois da leitura da iteração 2 sem curador. A discussão
da madrugada separou três sentidos de "novo para o modelo": novo para os pesos (temos), novo para o repertório (temos, nesta escada) e
**novo para o sistema**, algo que o modelo não alcança com o orçamento máximo e que o laço passa a alcançar. A escada L1–E não pode
responder ao terceiro, porque a base com pensamento resolve todos os seus degraus, o mais difícil a 9/24. O A7 constrói degraus que
sejam parede para a base e pergunta se o produto do laço sem curador os atravessa. Nenhuma sessão de modelo antes deste registro; as
leituras são scripts escritos antes dos dados.*

## Definições operacionais

- **Parede** (para um modelo, nesta família): um degrau em que o modelo, com pensamento a 131 072 tokens, T 1,0/top-p 0,95, 3600 s e
  12 turnos, **não resolve nenhuma** de todas as tentativas medidas em instâncias retidas. "Qualquer orçamento" não é mensurável; a
  definição é relativa a este orçamento máximo e ao número de tentativas, dito em cada leitura.
- **Parede de ideia** e não de ferramenta: com a prova completa e verificada de uma instância irmã em contexto (mesmo degrau, constantes
  diferentes), a base resolve uma fração não desprezível. Se nem a forma dada destrava, a parede é de alcance em Lean, não de ideia, e o
  candidato sai.
- **Travessia**: o adaptador do laço sem curador (`a2c4-own2`, iteração 2) sobe contra a base nas mesmas células de uma parede
  confirmada, pela regra do programa.

## Candidatos (`src/creative_machine/formal_routes/ladder_walls_v1.py`)

Mesmo formato de mundo, mesmo modo provador e mesmo verificador da escada (mundos Mathlib), uma instância por degrau. Cada candidato tem
prova de referência verificada pelo verificador das sessões, checagem de falsificação (a prova é rejeitada num mundo mutado cuja
afirmação é falsa, e uma testemunha prova a falsidade) e **certificado de ausência de atalho**: busca exaustiva de invariantes lineares
exatos que separem e de formas lineares módulo m (m até 30; até 12 em 4 campos) invariantes e separadoras. Só o invariante pretendido pode
aparecer.

| degrau | construção | por que pode ser parede | ingredientes que o laço já consolidou |
|---|---|---|---|
| W1 pell_mod | automorfismo de Pell de x² − Dy² mais translações por um primo p; a quantidade só se conserva **módulo p**; alvos ⟨t, 0⟩ têm resíduo quadrado, o início não | composição de forma quadrática (E/L5) com resíduo (L3) | E, L5, L3 |
| W2 plane_lattice | translações no plano de uma forma escondida αx + βy + z; o invariante linear exato existe mas **não separa** (o alvo está no plano); a obstrução é uma forma linear módulo k, o índice da rede | armadilha: o invariante de L2 falha e é preciso o de L3 | L2, L3 |
| W3 hyperbolic4 | 4 campos e 4 deslocamentos; cisalhamentos SL2 agindo em dois vetores ao mesmo tempo conservam (x−cx)(w−cw) − (y−cy)(z−cz); alvos com valor a² + b² ≥ 0 | L4 levado a 4 dimensões | nenhum (o laço não produz L4) |
| W4 lattice_mod_p | a construção de L3 com primo grande (11 a 19) e índice da rede exatamente p | calibração: só inferência de parâmetros | L3 |

Verificação prévia: uma instância de desenvolvimento de cada candidato passou em Lean (módulos, referência, mutação, testemunha); os
certificados deram limpo em 20 sementes por candidato, depois de W4 ser corrigido para índice de rede igual ao primo (antes, 5 de 12
sementes tinham atalho por paridade). As oito instâncias da triagem (`docs/a7_screen_worlds.json`, `worlds/walls/`) passaram 8/8 em Lean
(`docs/a7_screen_verification.json`).

## Fase 1 — triagem (esta noite)

Duas instâncias retidas por candidato × 4 tentativas = 8 células por braço, pensamento a 131 072 tokens (agente idêntico ao de
`a2c2_baset131`; só o nome do modelo muda):
- `a7s_base_v1`: base Qwen3.8-27B, braços **sem exemplo** e **com a prova irmã** (a prova verificada da outra instância do mesmo
  candidato, `docs/a7_sources/`), 64 células.
- `a7s_own2_v1`: adaptador `a2c4-own2` sem exemplo, 32 células.

Classificação por candidato (`scripts/analysis_a7_screen.py`): `not_a_wall` se a base sem exemplo resolve ≥ 1/8; `tooling_wall` se
resolve 0/8 e com a prova irmã ≤ 1/8; `wall_candidate` se 0/8 sem exemplo e ≥ 2/8 com a prova irmã. O own2 é descritivo na triagem
(sinal precoce se ≥ 2/8 num candidato a parede); nenhuma afirmação sai daqui. Veredito: `walls_found` ou `no_wall_in_family`.

## Fase 2 — confirmação (condicional à triagem; regras fixadas agora)

Para cada `wall_candidate`: seis instâncias retidas novas (sementes `a7-confirm-<W>-1..6`, certificado limpo, verificadas em Lean).
Braços: base sem exemplo × 8 tentativas (48 células); own2 sem exemplo × 8 (48); base com prova irmã × 4 (24); `a2c4-curm2` (curado
pareado da iteração 2) sem exemplo × 8 (48, descritivo: separa "o laço" de "qualquer adaptador de Lean").
- **Parede confirmada**: base sem exemplo 0/48 (limite superior unilateral de 95 % ≈ 6 % por tentativa).
- **Travessia**: own2 sobe contra a base pela regra do programa (diferença pareada de taxas sobre as seis instâncias, sign-flip
  unilateral p < 0,05, mínimo 0,0156, **e** diferença agrupada ≥ 0,25).
- Vereditos por candidato: `loop_crosses_a_wall` | `wall_holds_for_the_loop` | `not_a_wall_at_scale` (a base resolve ≥ 1/48).
- Leitura para o programa: um `loop_crosses_a_wall` é a primeira evidência, nesta família, de novo para o sistema (relativo ao
  orçamento medido); se curm2 também atravessa, a travessia é de consolidação em geral, não do laço sem curador em particular.

## Critérios de morte

- Triagem `no_wall_in_family`: os quatro candidatos são alcançáveis pela base ou são paredes de ferramenta. Uma rodada de construções mais
  duras, pré-registrada à parte, ou mudança de domínio (Mathlib real, fronteira do paper 3), decidida com o Roberto.
- Confirmação `wall_holds_for_the_loop` em todas as paredes: o laço sem curador não atravessa paredes nesta escala; o passo seguinte seria
  busca com acumulação (muitas tentativas por instância de treino da parede) ou curadoria, decidido com o Roberto.

## O que não se afirma

Uma família (inalcançabilidade por quantidade conservada em Lean), paredes construídas por nós, um modelo, um adaptador, orçamento finito.
Não é descoberta matemática: os invariantes são conhecidos. Parede significa parede para este modelo neste orçamento, não impossibilidade.

## Operação e custo

Um pod H200 (`scripts/a7_serve_pod.sh`: base BF16 + `a2c4-own2`, contexto 163 840, 16 sequências), cadeia `scripts/a7_screen_chain.sh`
com laço de retomada e leitura automática, guarda `scripts/a2c3_guard.sh` com prazo. Triagem: 96 células de pensamento ≈ 6–7 h + subida
≈ US$30–35; saldo RunPod US$62,65 no registro. Confirmação: ≈ 168 células por parede ≈ US$55 cada, **exige recarga**. Bedrock: zero.
Evidência: `docs/a7_screen_evidence_v1/`, manifesto SHA-256.

## Emendas prospectivas

- **E1 (16/09, 21:24, commit `9f96325f`; antes de qualquer célula da triagem — o servidor subiu às 21:28:42 e a primeira célula começou às 21:28:52).** O Roberto recarregou o
  RunPod (saldo US$212). A confirmação passa a ser **encadeada automaticamente** depois da leitura da triagem, sem nova decisão, porque o
  desenho e as regras já estavam fixados acima. Três ajustes prospectivos, todos motivados por custo e escritos antes dos dados:
  (i) **no máximo três paredes são confirmadas**, escolhidas por uma **ordem fixa agora**, W1, W2, W3, W4 (composição, armadilha,
  forma sem ingrediente consolidado, calibração), entre as classificadas `wall_candidate`; nenhuma escolha pelo tamanho de efeito;
  (ii) o braço descritivo `a2c4-curm2` cai de 8 para **4 tentativas** por instância (24 células por parede), o resto fica igual;
  (iii) a confirmação roda num pod novo que serve a base e os dois adaptadores. Custo previsto ≈ 144 células por parede, ≈ US$35–40 cada.
  A regra de travessia, a definição de parede confirmada e os vereditos não mudam. Se a triagem der `no_wall_in_family`, nada é lançado.
- **Registro de horários (16/09, 21:35).** Os horários acima foram corrigidos para os dos commits (antes estavam escritos como 21:30).
  O pipeline da confirmação (`analysis_a7_confirm.py` com testes de regra, planos, pod e cadeia) foi commitado às 21:28:57 (`b0e3c55c`),
  **5 segundos depois do início da primeira célula da triagem** e antes de qualquer resultado dela (as sessões duram dezenas de minutos) e
  de qualquer dado de confirmação. As regras da confirmação estavam fixadas em `b7811841` (21:18) e E1 (21:24), antes da triagem começar.
- **Observação da triagem, 17/09, 02:27, commit `74ffc04e` (NÃO é emenda; nenhuma regra, plano ou limiar muda; o pod da confirmação
  ainda instalava a pilha, nenhuma célula dela tinha começado).** Leitura da triagem (`docs/a7_results/screen.md`): **W1 `wall_candidate`** (base sem exemplo 0/8,
  base com prova irmã 6/8, own2 7/8, sinal precoce de travessia); W2 (4/8), W3 (2/8) e W4 (3/8) `not_a_wall`. Confirmação lançada só
  para W1. Diagnóstico das sessões de W1, registrado agora para não virar explicação posterior: **a base tinha a ideia**. O invariante
  certo (forma quadrática módulo p) aparece já na primeira submissão em pelo menos 4 das 8 sessões sem exemplo (detector grosseiro por
  texto, que pode subcontar), e as rejeições são de engenharia da prova em Lean: padrões de `rcases` e de casos da indução, metas não
  resolvidas, táticas que falham; 7 das 8 sessões terminam no teto de 131 mil tokens corrigindo sintaxe. O own2 resolve 7/8 com mediana
  de 60 mil tokens escrevendo a mesma ideia numa forma de prova que funciona: um lema de invariância por movimento, `Int.ModEq`, indução
  em `Reaches` com casos em `Step`. Consequência para a leitura: o teste operacional de "parede de ideia" (a prova irmã destrava) não
  separa ideia de forma, porque a prova irmã entrega as duas; nesta família, o que falta à base em W1 é a **forma verificada da prova**
  sob o orçamento, não o conceito. Se a confirmação der `loop_crosses_a_wall`, será dito assim: o laço atravessa uma parede de forma,
  novo para o sistema neste orçamento, sem ideia matemática nova. O braço curm2 dirá se qualquer consolidação de provas da escada basta.
- **Observação da confirmação, 17/09, 07:29, commit `27635d85` (NÃO é emenda; regras e limiares intactos; braço da base completo, own2 em curso,
  referência e curm2 não iniciados; leitura ainda não feita).** (i) **O braço da base resolveu 6/48** nas seis instâncias novas de W1. Pela
  regra pré-declarada, W1 será `not_a_wall_at_scale`: o 0/8 da triagem era compatível com uma taxa de ≈ 10 % por tentativa, e é para isso
  que a confirmação existia. (ii) **Viés de transporte, novo e mensurável.** 17 das 48 células da base foram refeitas por corte do proxy
  (regra E6 da réplica: falha de infraestrutura não é observação). Os cortes acontecem sobretudo durante a primeira resposta longa (18 de
  23 tentativas cortadas antes de completar uma resposta), e sessões que pensam até o teto são as que falham. Refazer troca uma sessão
  longa por um sorteio novo, o que enriquece as células refeitas em sessões mais curtas, que são as que acertam: **4/17 resolvidas entre as
  refeitas contra 2/31 entre as nunca cortadas**. A taxa da base de 12,5 % está provavelmente inflada; o subconjunto sem corte dá ≈ 6,5 %
  e **ainda tem acerto**, então a conclusão "não é parede" sobrevive ao viés. A leitura vai reportar as duas contas. O viés favorece o braço
  com sessões longas que falham, em geral a base com pensamento; nas leituras anteriores, onde a base com pensamento era o comparador de
  baixo, ele joga contra as subidas medidas, isto é, a favor da prudência das conclusões positivas já registradas.
- **E2 (17/09, 13:22; operacional; nenhuma regra, plano ou limiar muda; leitura ainda não feita).** O Mac reiniciou por volta de
  11:22 (horário em que o script do pod registrou "removendo pod" no sinal de desligamento, mas a remoção não chegou a acontecer).
  Morreram a cadeia da confirmação, o guarda, o script do pod e o de arquivamento; **o pod e o servidor vLLM sobreviveram** (os três
  modelos respondendo às 13:20). Estado dos braços: base 48/48, own2 48/48 e prova irmã 24/24 completos antes do reinício; o braço
  descritivo curm2 tinha 3 resultados, todos falha de infraestrutura (movidos para `.failed1` pela regra E6), e 13 sessões interrompidas
  em voo (movidas para `*.interrupted_reboot`, preservadas, não são observação). O curm2 é **refeito inteiro (24 células)** no mesmo
  servidor por `scripts/a7_confirm_resume.sh`, que depois faz a leitura pré-registrada e remove o pod diretamente; guarda novo com prazo
  16:30; `scripts/a7_post_confirm.sh` relançado para arquivar e publicar. Custo extra do pod ligado sem cadeia entre 11:22 e a retomada:
  ≈ 2 h ≈ US$9. Lição operacional: o controle de custo depende do Mac; uma autodestruição dentro do pod foi tentada e não funcionou
  (o `runpodctl` da imagem não autoriza com a chave do pod).
- **Nota operacional POSTERIOR às leituras (17/09, 20:36; não é emenda e não é prospectiva; registrada depois dos dados só para o
  histórico).** O guarda removeu o pod no prazo de 16:30 enquanto o braço descritivo curm2 ainda rodava; ele ficou em 18 das 24 células
  (a leitura o marca como está). A leitura da confirmação correu às 16:51 com base 6/48, own2 30/48, prova irmã 19/24, curm2 0/18:
  `not_a_wall_at_scale` e `no_crossing`. Resultados e interpretação em `docs/A7_PAREDE_RESULTADOS_V1.md`.
(registrar aqui, com hora, antes de qualquer célula afetada)
