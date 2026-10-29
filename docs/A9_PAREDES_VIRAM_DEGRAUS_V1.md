# A9 — as paredes viram degraus? Acumular compõe, satura ou estreita (pré-registro, 2026-09-19, 08:16)

*Decisão do Roberto em 19/09 de manhã, com recarga (saldo US$190,81) e ≈ 24 h de máquina ligada antes de uma viagem. O A8 mostrou que o
adaptador do laço (`a2c4-own2`) generaliza a quatro famílias que nunca viu (52/72 contra 15/72 da base). O que ainda não sabemos é a pergunta
do programa: **acumular estende o alcance ou só o barateia?** Este nó dá mais uma volta na manivela com as provas que o próprio own2 produziu
nas paredes, e testa em instâncias novas e numa família nova que **compõe** duas delas. Nenhuma sessão de A9 antes deste registro; a família
W5 nunca foi mostrada a modelo nenhum. Leitura: `scripts/analysis_a9.py`, escrita e testada com dados sintéticos antes dos dados
(`tests/test_a9_analysis.py`).*

## Desenho fixo

**Terceiro adaptador, `a9-own3`**: os 135 exemplos de `a2c4-own2` (byte-idênticos, `docs/a2c4_data/own.jsonl`) mais **uma linha por sessão do
braço own2 do A8 cuja submissão final o verificador aceitou** (52 provas: W1 13, W2 11, W3 14, W4 14, nas 24 instâncias do A8, que passam a ser
instâncias de **treino**), renderizadas como nas iterações 1 e 2 (prompt do provador sem exemplo; cabeçalho + definições do mundo + o corpo que
o modelo escreveu). Sem seleção, sem dedup, sem ordenação: até três provas por instância entram. 187 exemplos; as 52 novas verificadas
52/52 no verificador real e as 135 anteriores conferidas byte a byte contra o arquivo verificado em 16/09 (`docs/a9_data/`,
`scripts/a9_prepare.py`). Receita congelada (`scripts/a2c_train.py`: LoRA r16, α32, 108 passos, lote 8, 4096, bf16), semente 2026091901.

**Instâncias de teste, todas novas** (nenhuma em comum com treino ou com o A8): 24 de W1–W4 (sementes `a9-<W>-1..6`, certificado limpo,
Lean 24/24) e 6 de **W5 `hyperbolic4_mod_p`**, família construída hoje no mesmo gerador sem tocar W1–W4: quatro campos com deslocamentos,
dois cisalhamentos SL2 que conservam exatamente a forma bilinear de W3, mais translações de x e de w por um primo p, que só a conservam
**módulo p**; alvo pontual com outro resíduo. Exige a ideia de W3 (a forma) **e** a de W1 (só vale módulo p). Certificado exaustivo sem
atalho linear nem modular (m ≤ 12) em 24 sementes de desenvolvimento e nas 6 de teste; prova de referência e mutação verificadas em Lean 6/6
(`docs/a9_w5_worlds.json`, `docs/a9_w5_verification.json`).

**Braços** (mesmas células dentro de cada bloco, sem exemplo, 3 tentativas por instância; agente com pensamento idêntico ao do A8
— 131 072 tokens, T 1,0/top-p 0,95, 3600 s, 12 turnos — e agente sem pensamento idêntico ao de `a2c2_base` — T 0,7/top-p 0,8, 16k, 900 s):

| bloco | braços | células por braço |
|---|---|---|
| W5, com pensamento (**primário**) | base, own2, own3 | 18 |
| W5, sem pensamento | own2, own3 | 18 |
| W1–W4 novas, sem pensamento | base, own2, own3 | 72 |
| W1–W4 novas, com pensamento | own2, own3 | 72 |
| escada original (retidas da iteração 2), sem pensamento | own3, contra o run de own2 de 16/09 nas mesmas células | 144 |

## Regras pré-declaradas

Subida(x, y, bloco): diferença pareada de taxas sobre as instâncias do bloco, sign-flip unilateral p < 0,05 (mínimo 0,0156 com seis
instâncias) **e** diferença média ≥ 0,25. Queda: o espelho.

- **P-compõe (primária)**: em W5, com pensamento, own3 **sobe** contra own2.
- **P-barateia**: em W1–W4 novas, **sem pensamento**, own3 sobe contra own2 em pelo menos 2 das 4 famílias.
- **P-retém**: own3 **não cai** contra own2 em nenhum dos seis degraus da escada sem pensamento, nem em nenhuma das quatro famílias com
  pensamento.
- **Vereditos**: `composes` (P-compõe ✓) | `cheapens_only` (só P-barateia ✓) | `saturates` (nenhuma), com `_with_forgetting` se P-retém ✗.
- **Teto e piso**: onde o comparador passa de 0,75 a subida não pode atingir o limiar; onde fica abaixo de 0,25, a queda não pode. Reportado
  por bloco, não contornado. Em particular, se own2 já resolver W5 acima de 0,75, P-compõe não pode passar e isso será dito como teto.
- **Descritivos, sem regra**: a base em W5 (0/18 = candidata a parede; qualquer acerto = não é parede); own2 e own3 contra a base em W5; W5
  sem pensamento; W1–W4 com pensamento; tokens; tipo de invariante submetido (detector corrigido em 19/09: produto de campos e módulo na mesma
  submissão é a composição que W5 pede).
- **Critério de morte**: `saturates` encerra a linha "mais uma volta na mesma família": a terceira volta não acrescenta nem composição nem
  barateamento nesta escala. `composes` abre a pergunta seguinte (a escada é aberta?), a decidir com o Roberto.

## O que não se afirma

Uma base, um gerador de mundos nosso, uma receita de treino, seis instâncias por família, três tentativas. W5 é uma composição de duas
famílias **que o own3 viu em treino** (provas próprias de W1 e W3); um resultado positivo diz que formas aprendidas das próprias provas se
compõem numa família nova, não que o laço fabrica uma ideia ausente do prior. O comparador de retenção na escada é um run de outro dia
(16/09), mesma pilha por comando e mesmas células. Os braços sem pensamento medem o barateamento (primeiro turno), não o alcance.

## Operação e custo

Um único pod H200 para a janela inteira (`scripts/a9_pod.sh`): fase 1 serve base + own2 + curm2 e completa o braço curado do A8 (A8-c, E4 do
A8); quando os dados e este registro estão commitados (`runs/a9/data_ready`), a cadeia (`scripts/a9_chain.sh`) pede o treino do own3 no
próprio pod (destacado e conferido por sondagem, para um link caído não o matar), baixa o adaptador em pedaços com checksum, e a fase 3 serve
base + own2 + curm2 + own3. `scripts/a9_run.sh` roda os braços em ordem de prioridade (W5 com pensamento primeiro), com o laço de retomada
(falha de infraestrutura não é observação; até 3 repetições); nenhum braço com pensamento começa depois de 20/09 02:30 e nenhum braço depois
de 04:15; leitura única, diagnósticos, arquivo `docs/a9_evidence_v1/` com manifesto, commit e push automáticos; o pod é removido pela cadeia,
com guarda independente (prazo 20/09 05:30 e checagem de vida da cadeia) e vigia de 30 min (`scripts/a9_watch.sh`). **Se o prazo cortar um
braço, a leitura é feita com o n observado, declarado.** Estimativa: A8-c ≈ 3 h, treino ≈ 0,5 h, A9 ≈ 9–10 h ≈ US$65 no total; Bedrock zero.

Incidente operacional antes de qualquer célula (08:14): o `serve()` do script do pod nunca iniciou o vLLM, porque o `pgrep` de guarda casava
com a linha de comando do próprio shell remoto; 12 min de pod ocioso (≈ US$1). Corrigido sem reiniciar: servidor da fase 1 iniciado à mão com
as mesmas flags do A8 (`/workspace/a9/start_vllm.sh`) e um auxiliar (`scripts/a9_serve_fix.sh`) faz o mesmo na fase 3.

## Emendas prospectivas

- **E1 (19/09, 09:27; operacional; nenhuma célula do A9 rodada; nenhuma regra, plano, agente ou limiar muda).** Na primeira hora do A8-c, cinco
  sessões do braço curado terminaram em falha de transporte depois de **26 a 63 minutos com menos de 1,7 mil tokens gerados**: o servidor
  comporta ≈ 10 sequências longas (cache KV a 91 % com 10 rodando), o cliente abre 16, e os pedidos excedentes esperam na fila do vLLM sem
  receber bytes até o proxy cortar. Não é observação perdida (o laço de retomada refaz), mas ocupa vagas e gasta as repetições de cada
  célula. Para os **braços com pensamento do A9**, o cliente passa a abrir **12** sessões em vez de 16 (`CM_MAX_PARALLEL=12` no
  `scripts/a9_run.sh`; o campo `max_parallel` dos planos commitados não é tocado). Vale para todos os braços com pensamento do A9, então
  nenhuma comparação interna muda de condição; os braços sem pensamento (sessões de ≈ 1 min) seguem com 16. O A8-c termina como começou
  (16), igual às 27 primeiras células do braço.
- **E2 (19/09, 14:28; operacional, nível de transporte; nenhuma regra, plano, agente, célula ou limiar muda; nenhuma observação do A9 existe
  ainda).** A primeira leva do A9 (`a9_w5own3_v1`, 12 sessões iniciadas às 13:40:21) perdeu-se inteira: às **13:43:32** as doze conexões de
  streaming ficaram mudas no mesmo segundo (queda silenciosa de rede no caminho cliente–proxy; o servidor seguiu gerando e terminou os pedidos
  sem ninguém receber) e o cliente só desistiu pelo tempo-limite de leitura de 2 400 s, às 14:23:32, as doze com a mesma duração (2 591 s). São
  falhas de infraestrutura, não observações: foram movidas para `.failed1` e refeitas pela regra (uma das três repetições de cada célula
  gasta). Custo ≈ 40 min de GPU quase ociosa. Correção no cliente (`openai_session_v1.http_post_stream`), valendo para todo processo iniciado
  depois desta emenda: (i) **keepalive TCP** no soquete (sonda após 30 s, a cada 10 s, 3 falhas), para o sistema abortar em ≈ 1 min uma conexão
  que morreu sem aviso; (ii) o silêncio aceito **entre dois pedaços** de um stream passa a ser no máximo **600 s**, em vez do tempo-limite
  inteiro do pedido (o modelo envia pedaços enquanto gera; silêncio longo é fila ou morte). O que o modelo recebe e o que é verificado não
  mudam; uma falha continua sendo falha de infraestrutura e a sessão inteira é refeita, como antes. Testado contra um servidor local de
  streaming (stream normal; stream mudo cortado no limite) e pelos 14 testes da sessão. O vigia passa a olhar também o servidor
  (`vllm:num_requests_running`): plano rodando com o servidor parado por 5 min é anomalia.
(registrar aqui, com hora do relógio ou do commit, antes de qualquer célula afetada)
