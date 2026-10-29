# A2 — piloto de competência com Mathlib (pré-registro, 2026-09-13)

*Pré-condição de A2 (consolidar esqueletos curados em pesos). O piloto de competência em ambiente Std (`A2_PILOTO_COMPETENCIA_V1.md`,
três modelos, 552 sessões sem exemplo, zero soluções; a nota de ambiente não corrigiu a sintaxe) encerrou com "sem instrumento sem
Mathlib". Roberto pediu pesos abertos (para depois investigar e interferir nos priors por dentro; APIs fechadas não servem) e
concordou com a lista deste registro. Isto é uma mudança de instrumento, pré-registrada do zero. Nenhuma sessão antes deste registro.*

## O que muda no instrumento (e só isso)

1. **Ambiente Mathlib.** Mundos `env=mathlib` (`World/Base.lean` com `import Mathlib`; Mathlib `v4.33.1`, Lean 4.33.1; cache
   compartilhado `CM_LAKE_SHARED`). Mesmo gerador, mesma família "inalcançabilidade por quantidade conservada", mesmos degraus
   L1–L5 e o mundo extra E (forma de Pell). Instâncias novas, fase `a2_mathlib_pilot`, sementes `a2m-1`…`a2m-6`:
   `S0CC2F200`, `S8AB251F6`, `S030C8CC2`, `SCEBF34DB`, `S808E8666`, `S9E33A160` (36 mundos). Excluídas de A2.
2. **Modo provador** (`openai_session_v1.py`, `mode="prover"`) para provadores de prova inteira treinados num único molde e sem
   ferramentas. O turno do usuário é o molde nativo deles (Pythagoras-Prover e Goedel-Prover-V2 usam o mesmo):

   > Complete the following Lean 4 code:
   > ```lean4
   > import Mathlib / import Aesop / set_option maxHeartbeats 400000 / open BigOperators Real Nat Topology Rat
   > ⟨definições do mundo: State, move1…, Step, Reaches, start — sem namespace⟩
   > theorem evaluation_solution : ⟨enunciado desdobrado de LadderStatement⟩ := by
   > ```
   > Before producing the Lean 4 code to formally prove the given theorem, provide a detailed proof plan outlining the main proof steps and strategies.

   Regra fixa de extração: o **último** bloco ```lean da resposta; dele, da última linha `theorem/lemma evaluation_solution` até o
   fim (um `end` final é descartado), mais as linhas anteriores que não sejam `import`/`namespace`/`section`/`end` nem repetição
   literal das definições do mundo ou do cabeçalho (lemas auxiliares ficam). O `Solution.lean` montado importa só
   `World.ChallengeEvaluation`, repete as linhas `set_option`/`open` do cabeçalho (mesmo contexto de elaboração do molde) e
   envolve tudo em `namespace ⟨ns⟩ … end ⟨ns⟩`. Vai ao **mesmo verificador** (tipo por `#check` contra `LadderStatement`, que aceita o
   enunciado desdobrado por igualdade definicional — testado com a prova de referência transplantada; axiomas padrão; `sorry`
   rejeitado). Rejeição volta como turno de texto: "The proof was rejected by Lean 4: ⟨erros + saída do compilador, últimos 6 000
   caracteres⟩ … provide the complete corrected Lean 4 code in a single ```lean4 code block, keeping the theorem statement unchanged."
   Resposta sem bloco de código encerra a sessão (`output_limit` se cortada no teto, senão `unsolved`); bloco sem
   `evaluation_solution` conta como submissão rejeitada com esse erro. Nos braços com exemplo, o `SOURCE.md` (mesmo arquivo do modo
   ferramenta) precede o molde como texto, com a nota "a separate formal problem and its complete proof … may or may not be useful".
   Limites, estados e registro por sessão são os do modo ferramenta. A entrada do modelo (hash do plano) é o prompt do provador.
3. **Limites para o ambiente Mathlib**: verificador 180 s por submissão (uma checagem com `import Mathlib` leva 20–55 s no Mac;
   60 s cortava), sessão 900 s (mesma fração de relógio para o modelo que os 600 s do Std com checagens de 3 s), orçamento 16 384
   tokens por sessão e por requisição (`b16k`; provadores escrevem plano + código; Qwen pensa), 300 s por requisição com SSE.
4. **Tratamento de janela de contexto**: um 400 do servidor que nomeie a janela encerra a sessão como `budget_exhausted`
   (tentativa observada e falha), não como falha de infraestrutura (que pararia o plano).

## Modelos e modos (ordem pré-declarada, por tamanho)

| ordem | modelo (HF) | servido como | modo | amostragem | GPU |
|---|---|---|---|---|---|
| 1 | `Pythagoras-LM/Pythagoras-Prover-4B` (Qwen3-4B; alvo principal de A2) | `pythagoras-4b` | provador | T 1,0, top-p 0,95 | H100 80 GB |
| 2 | `Goedel-LM/Goedel-Prover-V2-8B` (Qwen3-8B) | `goedel-v2-8b` | provador | T 1,0, top-p 0,95 | H100 80 GB |
| 3 | `Qwen/Qwen3.8-27B` (denso, geral; servido como `Qwen3.8-27B-FP8`, E4) | `qwen3.8-27b` | ferramenta (`check_solution`, `--tool-call-parser qwen3_coder` (E4), `--reasoning-parser qwen3`, `reasoning_effort` medium) | T 1,0, top-p 0,95 (modo pensante do cartão) | H100 80 GB |
| 4 | `Pythagoras-LM/Pythagoras-Prover-32B` | `pythagoras-32b` | provador | T 1,0, top-p 0,95 | H200 141 GB |

vLLM `vllm/vllm-openai:latest`, `--max-model-len 32768`, `--gpu-memory-utilization 0.92`, pelo proxy HTTP do RunPod, lançador
`scripts/a2_vllm_pod.sh` (teto 3 h por pod, remoção garantida). Lean local no Mac, 8 sessões em paralelo. Ordem das células
embaralhada pela semente padrão (2026091301). 12 turnos por sessão.

## Planos (um par por modelo; mesmos mundos, mesmas fontes)

- **A** `a2m_<modelo>_none_v1`: nenhum exemplo × {L1, L2, L3, L4, L5, E} × 4 tentativas = **144 sessões**.
- **B** `a2m_<modelo>_examples_v1`: esqueleto (o exemplo genérico de P3) e referência (a prova curada de E no formato de A1 v3,
  `docs/a2m_sources/`) × {L4, L5} × 4 = **96 sessões**. **B só roda se A passar competência e margem** (não gastar em modelo morto).
- **C** `a2m_opus_reference_v1`: Opus 5 (modo ferramenta, laço de A1, verificador 180 s, sessão 900 s), nenhum exemplo × {L4, L5, E}
  × 2 = **36 sessões**, reserva US$40 (teto contábil por sessão US$1,55, pior caso US$55,82 acima da reserva: a admissão pára
  quando o gasto real mais os tetos das sessões em curso alcançar US$40; esperado ≈ US$15 a ≈ US$0,4 por sessão). É **calibração descritiva** dos mundos Mathlib
  contra os Std de A1 (o Mathlib muda o que `omega`/`grind`/`nlinarith` alcançam); não entra na decisão.

## Regras pré-declaradas

Por modelo, `scripts/analysis_a2_pilot.py` (rótulo de orçamento lido do plano): **competência** taxa agrupada sem exemplo em L1 ≥ 0,5;
**margem** algum degrau entre L3, L4, L5 e E com taxa agrupada estritamente entre 0 e 1; **efeito do exemplo** em L4 e L5, referência
ou esqueleto poupam bits sobre nenhum (permutação por sinal sobre as seis instâncias, unilateral, p < 0,05; mínimo 0,0156).
**Admissão** = as três. Entre modelos, `scripts/analysis_a2_mathlib.py`: na ordem da tabela, **o primeiro admitido vira o substrato
de A2 e os seguintes não rodam**; se nenhum dos quatro for admitido, A2 encerra neste domínio ("nenhum modelo aberto ≤ 32B com este
instrumento"). Nada é escolhido pelo tamanho do efeito. Sessões com falha de infraestrutura não são observadas.

## Verificação, fumaça e leitura

- Os 36 mundos passam por `verify_step` (módulos compilam; referência pelo verificador das sessões) e `mutation_check` (referência
  rejeitada no mundo mutado; testemunha prova ¬enunciado) **uma vez**, antes de qualquer sessão. **Resultado (13/09, 11:38): 36/36 ok**
  (`runs/a2/a2m_verify/*.jsonl`, seis processos paralelos, um por instância; copiado para a evidência no fechamento). Cada plano passa
  por `preflight --no-lean` (deriva de hash da entrada; sonda do sandbox) antes de rodar.
- Fumaça por endpoint: uma requisição (molde do provador / chamada de ferramenta) para confirmar servidor e parsers; não é lida.
- Leitura única por modelo ao fechar A (e B, se admitido); leitura entre modelos ao fim. Status da rodada: limite / interessante /
  proveitoso. Evidência em `docs/a2m_evidence_v1/`.

## Custo

GPU (Secure, consulta no registro): H100 US$3,49/h (estoque alto), H200 US$4,59/h (médio). Por modelo ≈ 1,5–2,5 h (o gargalo é o
Lean com Mathlib no Mac): ≈ US$6–9 nos H100, ≈ US$8–12 no H200; total ≤ US$40 se os quatro rodarem, menos se um passar antes.
Bedrock: só o plano C (≈ US$15). **O plano C fica para o próximo dia civil de São Paulo**: o diário de 13/09 já soma US$132.35
e a reserva de US$40 estouraria os US$150/dia, que o módulo de orçamento recusa; C é descritivo e não entra na decisão.
Saldo RunPod no registro: US$175,78.

## Limitações declaradas

Pythagoras e Goedel foram treinados/avaliados em Lean 4.9 e Mathlib da época; nosso ambiente é 4.33.1 (nomes de lemas e táticas
mudaram; `grind` não existia). A deriva conta **contra** os provadores, nunca a favor. O exemplo em modo provador é texto no prompt
(provadores não têm sistema de arquivos); no modo ferramenta é arquivo — comparações **entre** modelos são descritivas; a decisão é por
regra dentro de cada modelo. Nada sobre consolidação ainda; a Opus é teto descritivo, não controle.

## Emendas prospectivas

- **E1 (13/09, 11:40, antes de qualquer célula; motivada pela fumaça do endpoint, que não é lida como dado).** O Pythagoras-4B devolve o
  arquivo completo como texto puro, sem cerca de markdown e sem plano em prosa (estilo DeepSeek-Prover: completa o bloco aberto no
  molde; 3 569 tokens, `finish_reason` stop). Regra de extração emendada: sem bloco cercado, a resposta inteira é tratada como o bloco
  (dali em diante a mesma regra: última linha `theorem evaluation_solution`, repetições das definições/cabeçalho descartadas). Sem cerca
  e sem essa linha, continua sem submissão; resposta cortada no teto (`finish_reason` length) não é submetida em nenhum caso
  (`output_limit`, como no modo ferramenta). Teste adicionado. Nenhuma célula do piloto rodou antes desta emenda.
- **E2 (13/09, 11:35–11:45, antes de qualquer célula; motivada pela fumaça e pelo preflight).** Dentro do sandbox da sessão, o `lake`
  não enxergava o cache Mathlib compartilhado (ligado ao workspace por link) nem conseguia rodar `git` para conferir a URL da
  dependência, concluía "mathlib: URL has changed" e tentava apagar o pacote e cloná-lo de novo (o sandbox negou a escrita; fora
  dele a verificação dos mundos e os testes sempre passaram). Mudanças, todas condicionadas a `CM_LAKE_SHARED` e por isso inertes para
  os mundos Std históricos: o perfil do sandbox passa a permitir **leitura** do diretório compartilhado e de
  `/Library/Developer/CommandLineTools`; o `git` real dessas ferramentas vai à frente do PATH (o atalho `/usr/bin/git` exige um cache
  gravável que o sandbox nega); `GIT_CONFIG_GLOBAL=/dev/null` e `GIT_CONFIG_NOSYSTEM=1` (o git aborta ao não poder ler `~/.gitconfig`).
  A escrita no cache continua negada pelo sandbox e, por precaução adicional, a árvore `.lake/packages` compartilhada ficou somente-leitura
  no sistema de arquivos (`chmod -R a-w`). O detalhe de erro do verificador passa a guardar as últimas oito linhas do `lake` (texto, não
  veredito). Testes adicionados. Nenhuma célula rodou antes.
- **E3 (13/09, 12:45, aprovada pelo Roberto; antes de qualquer célula do segundo modelo).** Ordem da fila alterada por competência
  esperada, não por tamanho: depois do Pythagoras-4B roda o **Qwen3.8-27B**; Goedel-Prover-V2-8B e Pythagoras-Prover-32B só se o 27B
  também não for admitido, e podem ser dispensados por decisão registrada. Motivo (operacional, não leitura): os provadores foram
  treinados em enunciados de olimpíada e falham de modo estrutural nas relações indutivas destes mundos (análise de casos e `simp`,
  nunca a indução com quantidade conservada); o 8B e o 32B são a mesma família. A regra de admissão por modelo e a regra de parada
  (o primeiro admitido vira o substrato) não mudam; a ordem em `analysis_a2_mathlib.py` passa a ser 4B, 27B, 8B, 32B.
- **E4 (13/09, 13:45, antes de qualquer célula do 27B; operacional).** O checkpoint BF16 `Qwen/Qwen3.8-27B` não cabe numa H100 de 80 GB
  (modelo multimodal com torre de visão; a receita oficial do vLLM exige quantização em GPU única): o primeiro pod não respondeu em
  40 min (502) e foi removido pelo lançador; o segundo foi parado antes de carregar. Serve-se o checkpoint oficial
  **`Qwen/Qwen3.8-27B-FP8`** (quantização fina em blocos de 128, "desempenho quase idêntico" segundo o cartão; Apache-2.0), com o
  parser de ferramentas **`qwen3_coder`** (o recomendado na receita; `hermes` estava no pré-registro) e `--reasoning-parser qwen3`.
  Nome servido, plano, prompts e limites inalterados. Se o 27B for admitido, a consolidação usaria os pesos BF16; a diferença fica
  registrada como limitação. **Adendo (14:57)**: a imagem `vllm/vllm-openai:latest` (v0.29.0) e a dedicada `qwen38` entram em crash loop
  com o padrão desta build: `max_num_seqs (1024) exceeds available Mamba cache blocks (815)` (arquitetura híbrida: um bloco de cache
  Mamba por sequência); o `pod logs` do `runpodctl` deu a causa. Serve-se com a imagem `qwen38` e `--max-num-seqs 64` (8 sessões em
  paralelo). Três pods perdidos no diagnóstico (BF16 ×2, FP8 ×1), ≈ US$6.
- **E5 (13/09, 15:18; registro, não protocolo).** A build de vLLM da imagem `qwen38` devolve o raciocínio do Qwen3.8 no campo `reasoning`
  (não `reasoning_content`), e o cliente de streaming só coletava o segundo: as chamadas de ferramenta funcionavam, mas o texto pensado
  não ficava gravado (inclusive nos 16k das sessões cortadas). Cliente corrigido para coletar ambos, com teste. O plano A do 27B,
  iniciado 15:06, foi **abortado antes de qualquer leitura** com 16 células concluídas (guardadas em
  `runs/a2/a2m_qwen38_27b_none_v1_aborted_20260913T1506`, não lidas, arquivadas como abortadas) e reiniciado do zero no mesmo pod às 15:19.
- **E6 (13/09, 17:10, aprovada pelo Roberto; antes de qualquer célula do plano B).** O plano B do Qwen3.8-27B (esqueleto e referência em
  L4/L5, 96 sessões) roda como **medida descritiva**, fora da regra de admissão (competência falhou): serve para conhecer o teto em
  contexto do 27B, que decide o substrato da consolidação. Não altera a decisão do piloto (`no_competence`) nem a regra entre modelos.
- **E7 (13/09, 17:10, aprovada pelo Roberto).** Goedel-Prover-V2-8B e Pythagoras-Prover-32B **dispensados**: mesma família do 4B, que
  não produziu a forma em 1 094 submissões; ≈ US$12 e 3 h com pouca chance. Veredito entre modelos: nenhum admitido ⇒ o piloto
  encerra; a continuação de A2 passa pela consolidação (`A2_CONSOLIDACAO_PROPOSTA_V1.md`, aprovada em princípio; pré-registro a congelar).
- **Verificação dos mundos em paralelo (13/09, 11:28).** A verificação sequencial (`verify_step` + `mutation_check`, 36 mundos) projetava
  ≈ 2 h e foi interrompida sem resultado lido; refeita com seis processos, um por instância, mesmas funções e timeouts de 900 s.

## Leituras únicas (por modelo, ao fechar o plano A)

- **Pythagoras-Prover-4B (13/09, 13:00; `docs/a2m_results/pythagoras4b.{md,json}`)**: 144 sessões, 0 não observadas, **0/24 em cada um dos
  seis degraus**; 1 095 submissões rejeitadas pelo Lean, 75 sessões no teto de saída, 52 no limite de turnos, 17 com orçamento esgotado;
  2,12 M tokens de saída, 245 s por sessão em média. Decisão pré-declarada: `no_competence_try_second_model`; plano B não roda. Pod
  `133wvk2x9sdzf6` removido. Próximo, por E3: Qwen3.8-27B.
- **Qwen3.8-27B (FP8; 13/09, 16:39, leitura feita pelo encadeamento automático `scripts/a2m_after_a.sh`; `docs/a2m_results/qwen38_27b.{md,json}`)**:
  144 sessões, 0 não observadas; **L1 4/24, L2 4/24, L3 2/24, L4 0/24, L5 1/24, E 0/24** (11 soluções, as primeiras de um modelo aberto
  nestes mundos); 122 sessões no teto de saída, 10 com orçamento esgotado, 1 no limite de turnos. Regras: competência **não** (0,17 < 0,5),
  margem sim, efeito do exemplo não medido (B não roda pela regra). Decisão pré-declarada: `no_competence_try_second_model`. Pod
  `i22bqyog2952sa` removido (103 min). Pela E3, seguem Goedel-8B e Pythagoras-32B, salvo dispensa registrada.
- **Qwen3.8-27B, plano B descritivo (E6; 13/09, 18:09; leitura A+B pelo encadeamento `scripts/a2m_run_b.sh`)**: 96 sessões, 0 não
  observadas. Em L5: referência **12/24**, esqueleto **10/24**, contra 1/24 sem exemplo; em L4: referência 1/24, esqueleto 0/24, contra
  0/24. Bits poupados (L4+L5, seis instâncias): referência +1,14 (p = 0,0156, o mínimo), esqueleto +0,84 (p = 0,031). **Efeito do
  exemplo: sim.** Decisão do piloto inalterada (`no_competence`), por regra. Pod `scxlc9ek4gu9ac` removido (59 min). Com E7, o
  piloto encerra: veredito entre modelos `no_open_model_admitted_A2_closes_in_this_domain`; a continuação é a consolidação, já
  pré-registrada, com o 27B como substrato (forma presente no prior, teto em contexto medido: L5 0,50).
