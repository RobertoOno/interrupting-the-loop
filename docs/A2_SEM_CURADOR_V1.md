# A2 sem curador — consolidar as provas próprias verificadas (pré-registro, 2026-09-14, 22:10)

*Direção do Roberto após a réplica do A2 (14/09, noite): a "dica", mesmo gravada nos pesos, cheira forçada; o alvo é um método que
descubra sem dicas. O A2 mostrou que a forma cabe nos pesos e que o cálculo fica no contexto, com a forma curada por nós e o alvo à
vista. Este nó tira o curador: a única fonte de forma é o que o próprio modelo provou e o verificador aceitou nos degraus de baixo de
instâncias de treino; nada é escolhido, editado ou ordenado por nós. Pergunta: consolidar as provas próprias verificadas move o modelo
em instâncias retidas, sozinho e com raciocínio em contexto? Se não, o laço com valor externo precisa de curador e não é autônomo aqui.
Nenhuma célula antes deste registro; a leitura é o script escrito antes dos dados (`scripts/analysis_a2_own.py`).*

## Desenho fixo

**Fase 1 — produção (noite de 14→15/09).** Base Qwen3.8-27B BF16 (sem adaptador), modo provador, pensamento ligado com 131 072 tokens
por sessão e por resposta, T 1,0/top-p 0,95, 3600 s por sessão, 12 turnos, verificação 180 s: a mesma configuração dos braços baset131
e p2t131 da réplica. Alvos: L1, L2 e L3 das 48 instâncias de treino da réplica (`docs/a2c2_data/manifest.json`, `train_instances`),
**uma tentativa por célula** (144 células, `docs/a2c3_prod_plan_v1.json`, 12 em paralelo). Servidor: `scripts/a2c3_serve_pod.sh` (H200,
mesma pilha e mesmos flags do servidor de 160k da réplica); cadeia `scripts/a2c3_prod.sh` com o laço de retomada da E6 (falha de
infraestrutura refeita até 3 vezes; não é observação); guarda `scripts/a2c3_guard.sh`. As instâncias retidas não entram na produção.

**Conjunto de treino "próprio" (sem seleção).** Toda célula da produção cuja submissão final passou no verificador vira um exemplo:
prompt = o mesmo prompt do provador da célula; completion = cabeçalho + definições do mundo (como no prompt) + o corpo verificado que o
modelo escreveu (lemas auxiliares e teorema, tirados de `Solution.lean` da célula, sem o invólucro de namespace), no mesmo formato dos
exemplos curados de `docs/a2c2_data/p2.jsonl`. Sem edição, sem deduplicação, sem ordenação por tamanho ou estilo; falhas e provas feias
entram como estão. Cada exemplo é recompilado antes do treino (portão de dados: 100 % verificados, como na consolidação).
**Portão de rendimento**: se a produção render **menos de 24** provas verificadas, o nó encerra antes de treinar com o status "sem
produção suficiente" (o modelo não produz sozinho, nesta dificuldade, material bastante para consolidar); nada é treinado.

**Controle curado pareado (`curm`).** Os exemplos curados (`docs/a2c2_data/p2.jsonl`) de exatamente as mesmas células (instância, degrau)
que o modelo resolveu na produção: mesmo tamanho e composição, forma curada em vez da própria. Mede o que a curadoria acrescenta a dados
iguais; não é o braço principal.

**Fase 2 — consolidação e teste (15/09).** Dois adaptadores LoRA com a receita da consolidação (r 16, α 32, dropout 0,05, atenção +
MLP, AdamW 2e-4, cosseno, batch efetivo 8, 4096 tokens, bf16, **108 passos** cada, semente 2026091501, treino sem pensamento):
`a2c3-own` (próprio) e `a2c3-curm` (curado pareado). Quatro braços nas seis instâncias retidas da réplica, células idênticas às dos
braços já lidos (planos gerados e conferidos: configuração do agente igual à de `a2c2_base` para os braços sem pensamento e à de
`a2c2_baset131` para os de pensamento; só o nome do modelo muda):
`a2c3_own_v1` e `a2c3_curm_v1` (sem pensamento, 16k, seis degraus × 4 = 144 cada); `a2c3_ownt131_v1` e `a2c3_curmt131_v1` (pensamento
131k, L2/L3 × 4 = 48 cada). Comparadores já lidos em 14/09 nas mesmas células: base, baset131, p2, p2t131 (mesmos pesos, mesma
amostragem; servidor de outra instância, nota na leitura).

## Regras pré-declaradas (`scripts/analysis_a2_own.py`)

Subida(x, y, degrau): diferença pareada de taxas x − y sobre as seis instâncias, sign-flip unilateral p < 0,05 (mínimo 0,0156) **e**
diferença agrupada ≥ 0,25. Queda: o espelho.

- **P-próprio-pensamento**: ownt131 sobe contra baset131 em L2 ou em L3 (forma própria nos pesos + raciocínio em contexto > raciocínio só).
- **P-próprio-simples**: own sobe contra base em L1, L2 ou L3 (a forma própria transfere para instâncias novas dos mesmos degraus).
- **Transferência negativa**: own cai contra base em algum degrau (forma própria aplicada onde não cabe, como o p1 em L1).
- **Valor da curadoria** (descritivo): curm sobe contra own em algum degrau, ou curmt131 contra ownt131 em L2/L3.
- **Veredito**: `self_consolidation_moves` se P-próprio-pensamento ou P-próprio-simples; senão `needs_curator` se curm sobe contra base
  em algum degrau ou curmt131 contra baset131 em L2/L3 (o curado pareado funciona, o próprio não); senão
  `nothing_moves_at_matched_size` (nem próprio nem curado escrevem nada com este tamanho: inconclusivo sobre a curadoria).
- **Critério de morte do nó**: `needs_curator`. Status: proveitoso se `self_consolidation_moves`; limite se `needs_curator`;
  interessante/inconclusivo nos outros casos. Nada é escolhido pelo tamanho do efeito; leitura única.

## O que não se afirma

Uma família de alvos (quantidades conservadas em Lean), seis instâncias retidas, um modelo, uma semente de treino, produção em três
degraus com uma tentativa. Não é descoberta: é a pergunta de se o laço modelo + verificador, sem curador, acumula forma útil. Um
positivo aqui autoriza o passo seguinte (um problema que não desenhamos: Mathlib real ou a fronteira do paper 3); um negativo diz que a
alavanca precisa de curador neste modelo e nesta escala, e o programa registra isso antes de gastar no mundo real.

## Operação e custo

Fase 1: pod H200 a ≈ US$4,6/h, ≈ 40 min de subida (download + pip), 144 células de pensamento a ≈ 35 min cada com 12 em paralelo ≈
7–9 h → ≈ US$40–45; cap do pod 14 h; guarda com prazo 15/09 10:30. Fase 2: pod de treino/serviço ≈ 1,5 h + testes (288 células curtas
+ 96 com pensamento) ≈ 6–8 h → ≈ US$35–45. Total ≈ US$80–90; saldo RunPod US$245 no registro. Bedrock: zero. Evidência:
`docs/a2c3_evidence_v1/` (produção, dados de treino, adaptadores por hash, braços de teste, leitura, diagnósticos), manifesto SHA-256.

## Emendas prospectivas

- **E1 (14/09, 22:50; operacional).** A fase 2 é encadeada automaticamente (`scripts/a2c3_phase2.sh`, screen `a2c3ph2`): ao ver
  "production done", renderiza e verifica os dados (`scripts/a2c3_prepare.py`, testado antes numa produção substituta: 14 provas próprias
  do baset131 da réplica, 10/10 verificadas), aplica os portões de rendimento e de dados, commita os dados, sobe o pod de treino/serviço
  (`scripts/a2c3_train_pod.sh`: dois adaptadores, servidor de 160k com os dois LoRA) com guarda próprio (prazo 15/09 22:00), roda os
  quatro braços com o laço de retomada e faz a leitura. Nenhuma regra, plano ou célula muda; só o horário de início da fase 2 (na
  madrugada, em vez de na manhã). Guarda da produção trocado por um processo novo às 22:48 porque o arquivo do guarda foi editado
  enquanto rodava (arquivo de pod configurável); mesmo prazo 10:30.
(registrar aqui, com hora, antes de qualquer célula afetada)
