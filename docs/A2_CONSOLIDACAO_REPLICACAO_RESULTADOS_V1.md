# A2 — consolidação da forma em pesos: RÉPLICA (leitura única, 2026-09-14, 18:46; status: PROVEITOSO)

*Réplica pré-registrada em `docs/A2_CONSOLIDACAO_REPLICACAO_V1.md` (emendas E1–E8 ali, com hora). Mesma receita da rodada 1
(`docs/A2_CONSOLIDACAO_RESULTADOS_V1.md`): 48 instâncias de treino novas (`a2c2-train-01..48`), 6 instâncias retidas novas, três
adaptadores LoRA treinados do zero (p1: forma de E/L5; p2: seis formas; p3: controle de sintaxe), base Qwen3.8-27B servida em BF16 numa
H200. Acrescenta dois braços de pensamento em L2/L3 (baset131, p2t131: pensamento ligado, 131 072 tokens) e, por E8, dois braços sem
pensamento na mesma configuração (basen131, p2n131; leitura separada, abaixo). Leitura pelo script escrito antes dos dados
(`scripts/analysis_a2_consolidation_v2.py`); evidência integral em `docs/a2c2_evidence_v1/` (4 341 arquivos, 163 MB, manifesto SHA-256
verificado, incluindo as células abortadas antes da E5 e as células cortadas pelo proxy).*

## Leitura pré-registrada (`docs/a2c2_results/consolidation.md`)

| braço | L1 | L2 | L3 | L4 | L5 | E |
|---|---|---|---|---|---|---|
| base (sem adaptador) | 4/24 | 0/24 | 0/24 | 0/24 | 1/24 | 0/24 |
| p1: forma de E/L5 gravada (96 exemplos) | 0/24 | 0/24 | 0/24 | 0/24 | **24/24** | **24/24** |
| p2: seis formas gravadas (288) | **24/24** | 1/24 | 7/24 | **24/24** | **24/24** | **24/24** |
| p3: controle de sintaxe (288) | 0/24 | 0/24 | 0/24 | 0/24 | 0/24 | 0/24 |

Subidas contra a base (sign-flip unilateral sobre as seis instâncias, p = 0,016 em todas, diferença agrupada ≥ +0,83): p1 em L5 e E
e em nenhum outro degrau; p2 em L1, L4, L5 e E (L3 +0,29, p = 0,062, abaixo da regra); p3 em nenhum. Regras: P1 forma-específica ✓,
P2 currículo ✓, P3 limpo ✓. **Veredito: `form_written_and_form_specific`; réplica: `replicated`.**

Rodada 1, para comparação: base 4/1/0/0/0/0; p1 0/0/0/0/24/24; p2 24/0/7/24/24/24; p3 zero. Os totais são os mesmos a menos de uma
célula (base 5 e 5; p1 48 e 48; p2 103 e 104; p3 0 e 0), com instâncias, treino e adaptadores todos novos.

## P4: forma nos pesos + raciocínio em contexto (braços de pensamento, L2/L3)

| braço | pensamento | L2 | L3 | respostas por sessão (mediana) | tokens de saída (mediana) | 1º turno |
|---|---|---|---|---|---|---|
| p2 (sem pensamento, 16k) | desligado | 1/24 | 7/24 | 8–12 | 3,9k / 5,5k | 1 / 7 |
| baset131 (base) | ligado | 6/24 | 8/24 | 11,5 | 81k / 122k | 0 / 0 |
| p2t131 (adaptador p2) | ligado | **19/24** | **18/24** | 2 / 1 | 3,4k / 2,7k | 2 / 8 |

Contrastes (regra de subida: p < 0,05 e diferença agrupada ≥ 0,25): em L2, p2t131 contra p2 +0,75 (p = 0,016) ↑ e contra baset131
+0,54 (p = 0,016) ↑; baset131 contra base +0,25 (p = 0,062). Em L3, p2t131 contra p2 +0,46 (p = 0,031) ↑, contra baset131 +0,42
(p = 0,016) ↑; baset131 contra base +0,33 (p = 0,016) ↑. **P4 ✓.**

O que as sessões mostram (`docs/a2c2_results/diagnostics.md`): o p2t131 escreve na primeira submissão o esqueleto gravado com
coeficientes chutados, exatamente como o p2 (em L2, primeira submissão válida em 2/24 e medida igual à referência em 0/24; no p2, 1/24),
recebe a rejeição do verificador, e na segunda resposta corrige os coeficientes: 19/24 em L2 com mediana de 2 submissões e ≈ 3 mil
tokens por sessão. Em L3 o primeiro chute acerta 8/24 (o p2, 7/24) e as voltas seguintes levam a 18/24. A base com o mesmo pensamento
gasta ≈ 100 mil tokens e 11–12 respostas por sessão para 6/24 e 8/24, nunca no primeiro turno, com formas heterogêneas (com e sem lema
auxiliar; `simp`, `omega`, `norm_num`, `linarith`, `decide`). Todas as 37 soluções do p2t131 têm o esqueleto treinado (lema auxiliar +
indução + `omega`/`grind`), como todas as 152 de p1 e p2.

Leitura: o adaptador dá a forma; o raciocínio em contexto faz o cálculo que a forma deixa em aberto (o sistema linear dos coeficientes);
o verificador dá o sinal de erro entre uma e outra. É a divisão de trabalho "forma nos pesos, cálculo em contexto, valor no
verificador", agora medida em instâncias retidas e replicada. Ressalva registrada antes da leitura da E8: a comparação p2t131 contra p2
confunde pensamento com configuração (amostragem T 1,0/top-p 0,95 em vez de 0,7/0,8, orçamento 131k em vez de 16k, 3600 s em vez de
900 s); a comparação contra baset131 é limpa. A E8 (abaixo) fecha esse buraco.

## E8: braços sem pensamento na configuração dos braços de pensamento

Leitura única às 20:39 (`scripts/analysis_a2_e8.py` → `docs/a2c2_results/e8_same_config.md`; regra e interpretação fixadas em E8 antes
das células). Os dois braços novos têm células, ordem e hashes de entrada idênticos aos braços de pensamento; o único campo do agente que
muda é `enable_thinking`.

| braço | pensamento | amostragem | orçamento | L2 | L3 | submissões por sessão (mediana) | tokens de saída (mediana) |
|---|---|---|---|---|---|---|---|
| p2 | desligado | T 0,7 / top-p 0,8 | 16k | 1/24 | 7/24 | 8 / 12 | 3,9k / 5,5k |
| p2n131 | desligado | T 1,0 / top-p 0,95 | 131k | 2/24 | 5/24 | 12 / 12 | 5,9k / 5,5k |
| p2t131 | ligado | T 1,0 / top-p 0,95 | 131k | **19/24** | **18/24** | 2 / 1 | 3,4k / 2,7k |
| base | desligado | T 0,7 / top-p 0,8 | 16k | 0/24 | 0/24 | | |
| basen131 | desligado | T 1,0 / top-p 0,95 | 131k | 2/24 | 0/24 | 12 / 12 | 24k / 25k |
| baset131 | ligado | T 1,0 / top-p 0,95 | 131k | 6/24 | 8/24 | 12 / 9,5 | 81k / 122k |

Contrastes em L2: p2t131 contra p2n131 **+0,71 (p = 0,016) ↑** (P4-limpa ✓); p2n131 contra p2 +0,04 (p = 0,50) (configuração sozinha
não move); baset131 contra basen131 +0,17 (p = 0,125); basen131 contra base +0,08 (p = 0,50). Em L3: p2t131 contra p2n131 +0,54
(p = 0,016) ↑; p2n131 contra p2 −0,08; baset131 contra basen131 +0,33 (p = 0,016) ↑; basen131 contra base 0,00. **Veredito
pré-declarado: `reasoning_is_the_active_ingredient_given_the_form`.** A diagonal inversa (pensamento ligado com T 0,7/top-p 0,8) não é
necessária pela regra fixada; fica como opção se um revisor a pedir.

O que a E8 acrescenta: na mesma configuração, com o mesmo verificador e o mesmo feedback de rejeição, o adaptador sem pensamento escreve
o esqueleto com coeficientes chutados e repete até o limite de 12 turnos sem acertar (2/24 em L2, 7 soluções em 48 sessões, 6 delas na
primeira submissão, 498 submissões ao todo); o mesmo adaptador com pensamento corrige na segunda resposta. O que muda entre uma e outra
não é a amostragem, o orçamento ou o tempo, mas o raciocínio entre a rejeição e a submissão seguinte: é ali que o cálculo dos parâmetros
acontece. A base sem pensamento nessa configuração fica em 2/24 e 0/24 com 24 mil tokens por sessão; com pensamento, 6/24 e 8/24 com
100 mil. Evidência da E8 em `docs/a2c2_e8_evidence_v1/` (596 arquivos, 58 MB, manifesto verificado).

## Emendas e registro operacional (o que aconteceu, em ordem)

- **E1** (min-cuda 13): a primeira alocação tinha driver CUDA 12.8 e o treino falhou escondido por `| tail`; pod refeito com
  `--min-cuda-version 13.0` e checagem do manifesto de treino. **E2** (aprovada): braços de pensamento no orçamento máximo do modelo
  (131 072 tokens; servidor relançado com contexto de 160k, 16 sequências). **E3** (operacional): três cadeias concorrentes por
  ≈ 3 min ao trocar a cadeia; 16 diretórios parciais removidos; nenhuma célula duplicada foi lida. **E4** (operacional): o relançamento
  do servidor por `pkill -f 'vllm serve'` matava o próprio comando ssh; servidor de 160k subiu à mão às 12:08.
- **E5**: com pensamento, o adaptador escreve o arquivo Lean dentro do raciocínio e deixa o conteúdo vazio; a extração passou a usar o
  raciocínio quando o conteúdo não traz submissão (evento `submission_from_reasoning`). Os dois braços de pensamento foram refeitos do
  zero; as células anteriores estão no arquivo como `*_aborted_pre_E5`, não lidas. Na rodada lida, a extração pelo raciocínio foi usada em
  12/48 células do p2t131 e 2/48 do baset131. Respostas truncadas a 131k: 11 (p2t131) e 14 (baset131).
- **E6**: o proxy do RunPod corta respostas longas em streaming de forma intermitente. Na rodada 1 do baset131 as oito conexões caíram de
  uma vez (13:14; cinco antes de qualquer token de saída); o laço de retomada refez as oito na rodada 2, que correu sem cortes, e o p2t131
  não teve nenhum corte. Falha de infraestrutura não é observação; as oito células cortadas estão no arquivo (`*.failed1.failed1`: o laço
  renomeou de novo as pastas já marcadas, defeito cosmético corrigido na cadeia da E8). **E7**: prazo do guarda estendido. **E8**:
  pré-registro dos braços na configuração igual (aprovado pelo Roberto), leitura separada.
- Custo: pod H200 `5k4b6fvxiv15g6` a US$4,59/h criado às 04:41 (treino dos três adaptadores, servidor às 06:37) e removido pelo guarda às
  20:39 ao fim da leitura E8: ≈ 16 h ≈ US$73, mais ≈ US$2,4 da primeira alocação (E1, driver antigo, 04:07–04:38). Saldo RunPod ao fechar:
  US$45,48; nenhum pod ativo (confirmado pela API). Bedrock: zero.

## O que não se afirma

Seis instâncias retidas, uma semente de treino por adaptador, uma base (Qwen3.8-27B). P4 é uma comparação em dois degraus (L2, L3) e
diz respeito a coeficientes de uma forma linear ou modular já gravada; não diz que o raciocínio inventa a forma (o baset131 mostra o
contrário: sem a forma, o pensamento pleno gasta 100 mil tokens para 6–8/24). Nada sobre outras famílias de alvos, sobre o Mathlib
como domínio (o piloto ficou em "limite pela regra") ou sobre modelos fechados.

## Status: PROVEITOSO

Segundo resultado positivo replicado em pesos abertos: a forma curada é escrita nos pesos, é específica da forma, transfere para
instâncias novas, e o raciocínio em contexto completa o que a forma deixa aberto (E8: é o raciocínio, não a configuração). Próximos
passos, por decisão do Roberto: (i) seção do paper 5 sobre a alavanca; (ii) análise secundária A6 (prior bayesiano sobre formas) sobre
estes dados; (iii) plano A do 27B em 131k para a pergunta de competência do piloto Mathlib; (iv) a diagonal inversa (pensamento ligado
com T 0,7/top-p 0,8, ≈ US$20–25) só se um revisor a pedir.
