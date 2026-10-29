# A2 — consolidação da forma em pesos: replicação e "forma + cálculo" (pré-registro, 2026-09-14, 01:45; aprovado pelo Roberto às 01:35)

*Replica `A2_CONSOLIDACAO_V1.md` (lido em 14/09 01:06: `form_written_and_form_specific`) com nova semente de treino e novo sorteio de
instâncias, mesma receita e mesmas regras, e acrescenta dois braços de 48 sessões para uma previsão nova (P4). Nenhuma sessão antes
deste registro. Leitura pelo `analysis_a2_consolidation_v2.py` (escrito e testado antes dos dados).*

## O que muda em relação à v1 (e só isso)

- **Instâncias novas**: 48 de treino (`a2c2-train-01..48`, fase `a2_consolidation2_train`) e 6 retidas (`a2c2-held-1..6`, fase
  `a2_consolidation2_heldout`): `SA980E398 SEF1D66BD SD63B34D6 S3FC9C651 S4C58716A SCFD02289`; ids sem colisão com os conjuntos
  anteriores. **Retidas verificadas 36/36 (14/09, 02:40, `runs/a2/a2c2_verify/`)** e todos os exemplos de treino verificados pelo verificador real antes do
  treino (`docs/a2c2_data/verification.json`, portão do script do pod).
- **Semente de LoRA nova**: 2026091402 (v1: 2026091301). Receita idêntica: r 16, α 32, dropout 0,05, atenção+MLP, lr 2e-4, 108 passos,
  lote efetivo 8, perda só na resposta. Adaptadores `a2c2-p1`, `a2c2-p2`, `a2c2-p3`.
- **Braços principais** (144 sessões cada, sem pensamento, T 0,7/top-p 0,8, como na v1): base, p1, p2, p3.
- **Braços novos (P4)**, só em L2 e L3, 6 instâncias × 2 degraus × 4 = 48 sessões cada, **com pensamento** (`enable_thinking=true`,
  `reasoning_effort` medium, T 1,0/top-p 0,95, mesmo teto de 16 384 tokens por sessão, contando o raciocínio): **p2t** = o adaptador p2
  com pensamento; **baset** = a base com pensamento. Motivo: na v1 o p2 escreveu em L2/L3 o esqueleto certo com coeficientes chutados;
  a pergunta é se a forma gravada mais o cálculo em contexto preenche os parâmetros, contra o pensamento sozinho.

## Regras pré-declaradas

- Replicação: **replicada** se o veredito dos quatro braços for de novo `form_written_and_form_specific` (P1 confirmada, P2
  confirmada, P3 limpa, regras da v1 inalteradas). Qualquer outro veredito é registrado como não replicado, com o veredito encontrado.
- **P4 (forma nos pesos + cálculo em contexto)**: p2t sobe em L2 contra p2 **e** contra baset (mesma regra de subida: permutação por
  sinal unilateral p < 0,05 sobre as seis instâncias e diferença agrupada ≥ 0,25). L3 é reportado com os mesmos contrastes, sem entrar
  na regra. Se p2t sobe contra p2 mas não contra baset, o ganho é do pensamento, não da forma gravada. Descritivo: baset contra base.
- Falhas de infraestrutura não são observadas; retomada só de células sem resultado, registrada.

## Operação e custo

Uma H200 com SSH (`scripts/a2c_pod_v2.sh`, `A2C_TAG=a2c2`, `A2C_SEED=2026091402`): fumaça, portão de dados, três adaptadores, servidor
BF16 + LoRA; cadeia de teste `scripts/a2c_run_all_v2.sh` (fumaça por modelo servido, preflight dos seis planos, base → p1 → p2 → p3 →
baset → p2t, leitura, parada). 672 sessões; ≈ 6 h ≈ US$30 de GPU; zero Bedrock. Evidência em `docs/a2c2_evidence_v1/`.

## O que não se afirma

O mesmo que na v1. P4 positiva diz que o cálculo dos parâmetros pode vir do raciocínio em contexto sobre uma forma gravada; não diz
que o cálculo se grava. Uma família; seis instâncias por sorteio; duas sementes ao todo.

## Emendas prospectivas

- **E1 (14/09, 04:45; operacional, antes de qualquer sessão).** A primeira alocação (`tm0jknwiyp7rll`) caiu na fumaça: o host tinha driver
  CUDA 12.8 e o `pip` instala torch 2.13 para CUDA 13.0 ("driver too old"); o treino de fumaça falhou sem que o script visse (código de
  saída mascarado por `| tail`) e o vLLM caiu pelo mesmo motivo; pod removido pelo próprio script (31 min, ≈ US$2,4). Correções no
  `a2c_pod_v2.sh`: `--min-cuda-version 13.0` na criação, checagem do treino pelo manifesto do adaptador, driver impresso no log. Nenhum
  adaptador da replicação foi treinado nessa tentativa. Log guardado em `runs/a2c2/pod_attempt1_driver.log`.
- **E2 (14/09, 05:05, a pedido do Roberto; antes de qualquer célula dos braços com pensamento).** O teto de 16 384 tokens media o
  orçamento, não o modelo (no piloto, 85 % das sessões com pensamento cortaram no teto). Os braços `baset` e `p2t` passam a rodar com
  **131 072 tokens por sessão e por requisição** (`b128k`), prazos de 2 400 s por requisição e 3 600 s por sessão, servidor relançado
  com contexto de 163 840 e 16 sequências (planos `a2c2_baset131_plan_v1.json`, `a2c2_p2t131_plan_v1.json`; os planos de 16k não rodam).
  A regra P4 é a mesma. Os quatro braços sem pensamento não mudam (respondem em 2–3 mil tokens). Cadeia `a2c_run_all_v3.sh`.
- **E3 (14/09, 06:40; operacional, registrado depois do fato).** Ao trocar a cadeia v2 pela v3 (E2), o `screen -X quit` não matou o
  processo da cadeia v2, e por ≈ 3 min houve até três cadeias concorrentes no mesmo servidor e nos mesmos diretórios (uma no braço
  base, duas no p1). O executor impede que a mesma célula seja materializada duas vezes (a segunda tentativa falha e pára a admissão
  daquela cadeia), portanto cada `result.json` foi escrito por um único processo. Todos os processos foram encerrados por PID; 8 células
  parciais da base e 8 do p1 (sem resultado) foram apagadas e serão refeitas; 64 resultados da base e 3 do p1 foram mantidos (mesmo plano,
  servidor e configuração; sessões completas). A cadeia v3 única retomou às 06:38 pelas células sem resultado. Logs das tentativas em
  `runs/a2c2/run_all_v2_waiting.log`, `run_all_v3_attempt*.log`. Nenhuma célula dos braços com pensamento rodou antes da E2.
- **E4 (14/09, 12:08; operacional, antes de qualquer célula dos braços com pensamento).** O relançamento automático do servidor a 160k
  (E2) falhou: o `pkill -f 'vllm serve'` remoto casou com o próprio comando SSH e matou o shell antes de subir o servidor novo (o antigo
  já morto; GPU a zero, sem log). Servidor a 160k iniciado à mão por SSH às 12:06 com o mesmo comando; padrão do `pkill` corrigido no
  script (`vllm[ ]serve`). Nenhuma sessão dos braços de pensamento havia começado.
- **E5 (14/09, 13:05; instrumento dos braços com pensamento, antes de qualquer célula lida).** Com o pensamento ligado, o adaptador p2
  (treinado sem pensamento) escreve o arquivo Lean **dentro do raciocínio** e deixa o conteúdo vazio; a extração, que só olhava o
  conteúdo, dava `unsolved` em um turno (28 células do p2t131 assim). A P4 seria ilegível por formato. Regra emendada, igual para os dois
  braços de pensamento: sem submissão no conteúdo, a extração usa o raciocínio (último bloco cercado; senão o trecho a partir do
  último `import Mathlib`, o arquivo final que o modelo escreveu), com a mesma regra dali em diante; evento `submission_from_reasoning`
  registrado. Teste adicionado. Os braços sem pensamento não são afetados (raciocínio vazio). **baset131 e p2t131 refeitos do zero** sob
  a regra emendada; as células anteriores ficam guardadas como abortadas (`*_aborted_pre_E5`), não lidas.
- **E6 (14/09, 13:05; operacional).** O proxy do RunPod corta respostas longas em streaming de forma intermitente ("peer closed
  connection"): 2 falhas de infraestrutura em 9 células do baset131, e o executor pára o run a cada falha. Laço de retomada
  (`runs/a2c2/finish2.sh`): células cujo resultado é falha de infraestrutura têm o resultado descartado e são refeitas (até 3 vezes por
  célula; contagem em `retries.json`; diretórios das tentativas falhas preservados), o run é retomado pelas células sem resultado até
  não restar nenhuma. Falha de infraestrutura continua não sendo observação. Leitura v2 ao fim, guarda remove o pod (prazo 22:30).
- **E7 (14/09, 14:49; operacional).** Rodada 1 do baset131: o proxy cortou as 8 conexões em streaming de uma vez (13:14; 5 delas antes de
  qualquer token de saída), e o laço de E6 refez as 8 na rodada 2, que segue sem cortes (19 células lidas às 14:46; mediana ≈ 103 mil tokens de
  saída por sessão, ≈ 38 min por célula com 8 em paralelo). Projeção de término da cadeia ≈ 21:00, apertada contra o prazo do guarda
  (22:30). Guarda trocado por `runs/a2c2/guard2.sh` (screen `g2pod`), mesmo gatilho ("analysis done") e prazo estendido para 15/09 00:30;
  o guarda antigo foi encerrado por PID. Exposição máxima adicional ≈ 2 h de H200 (≈ US$9). Nenhuma célula, plano ou regra de leitura muda.
- **E8 (14/09, 18:20; pré-registrada antes das células; aprovada pelo Roberto).** Pergunta do Roberto: o que falta para as comparações
  ficarem equivalentes? Entre os braços sem pensamento (base, p2) e os de pensamento (baset131, p2t131) mudam quatro fatores de uma vez:
  pensamento no template (ligado, esforço `medium`), amostragem (T 0,7/top-p 0,8 → T 1,0/top-p 0,95, a recomendação do cartão do modelo
  para cada modo), orçamento (16 384 → 131 072 tokens por sessão e por resposta) e tempo (900 → 3600 s por sessão). p2t131 contra baset131
  é limpo (só o adaptador muda); p2t131 contra p2 não é. Complemento: dois braços **sem pensamento na configuração dos braços de
  pensamento** — `basen131` (base) e `p2n131` (adaptador p2): T 1,0/top-p 0,95, 131 072 tokens, 3600 s, verificação 180 s, mesmo servidor
  de 160k, L2 e L3, 4 tentativas × 6 instâncias retidas = 48 células cada (`docs/a2c2_basen131_plan_v1.json`, `docs/a2c2_p2n131_plan_v1.json`;
  células, ordem e hashes de entrada idênticos aos dos planos de pensamento; o único campo do agente que muda é `enable_thinking`).
  Leitura própria, escrita antes dos dados (`scripts/analysis_a2_e8.py` → `docs/a2c2_results/e8_same_config.{md,json}`): regra
  **P4-limpa**: p2t131 sobe em L2 contra p2n131 (mesma regra de subida: sign-flip unilateral p < 0,05 sobre as seis instâncias e diferença
  agrupada ≥ 0,25); sinal **configuração-sozinha**: p2n131 sobe em L2 contra p2; descritivos: baset131 contra basen131, basen131 contra
  base, e tudo em L3. Interpretação fixada: P4-limpa sem configuração-sozinha = o raciocínio é o ingrediente ativo dado o esqueleto
  gravado; P4-limpa com configuração-sozinha = o raciocínio sobe, mas a configuração também move, e a diagonal inversa (pensamento
  ligado com T 0,7/top-p 0,8, ≈ 96 células, ≈ US$20–25) fica registrada como pendência a decidir antes de publicar; configuração-sozinha
  sem P4-limpa = configuração, não raciocínio. P4 original não muda. Custo ≈ 30–40 min de H200 (≈ US$3). Laço de retomada igual ao de
  E6 (`runs/a2c2/finish3.sh`); ao fim da leitura E8 a cadeia libera o pod (`runs/a2c2/release_pod`) para o guarda (v4, prazo 21:00).
  Guarda-dados: ao fim, arquivo de evidências com todas as células (inclusive `*.failed*` e `*_aborted_pre_E5`), logs, planos, manifestos.
(registrar aqui, com hora, antes de qualquer célula afetada)
