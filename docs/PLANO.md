# A Máquina Criativa — visão e plano

> Memória viva do projeto. Registra a tese, os fundamentos, a arquitetura e as
> decisões tomadas. Atualizar sempre que uma decisão nova for tomada.

## A tese

Pensamentos novos surgem de "erros" de previsão. LLMs computam, a cada passo,
uma distribuição de probabilidade sobre todo o vocabulário — a estratégia de
decodificação é uma escolha *separada* do modelo. A cauda da distribuição já
contém o improvável-mas-possível; o que falta é uma política de decodificação
que a explore deliberadamente. A máquina busca gerar o token/conceito
**distante no espaço semântico mantendo coerência**.

Fato que sustenta a tese: humanos não falam o mais provável — texto humano
real carrega surpresa próxima da entropia esperada, não mínima (*typical
sampling*, Meister & Cotterell 2022). Texto de máxima probabilidade é
degenerado. O texto vivo mora numa faixa intermediária de improbabilidade;
a máquina empurra essa faixa mais para longe.

## O paradoxo central

**Distância e coerência são medidas pelo mesmo juiz.** Se coerência = "o
modelo acha plausível", o guarda da coerência puxa de volta para o provável.
O desvio coerente é um cabo de guerra, não uma otimização livre:

    score(token) = log P(token | contexto) + λ · distância_semântica(token, contexto)

A favor da máquina: LLMs são treinados para continuar qualquer prefixo da
melhor forma possível. Injetado um token improvável, o modelo **racionaliza**
— constrói a ponte de sentido. Nós fornecemos o acidente; ele, a costura
(análogo ao *cadavre exquis* surrealista, ao cut-up de Burroughs, às Oblique
Strategies de Eno).

## Fundamentos (referências-chave)

- **Typical sampling** — Meister & Cotterell 2022: surpresa humana ≈ entropia
  esperada, não mínima.
- **Predictive processing** — Friston, Andy Clark: cognição como minimização
  de erro de predição; insight = reconfiguração forçada pelo erro.
- **Overfitted brain hypothesis** — Erik Hoel: sonhos como injeção de ruído
  anti-overfitting; o "erro" como regularizador.
- **Schmidhuber** — criatividade como recompensa intrínseca por progresso de
  compressão: o interessante é o surpreendente-que-depois-se-revela-compressível.
- **Novelty search** — Lehman & Stanley (*Why Greatness Cannot Be Planned*):
  otimizar por novidade encontra trampolins que nenhum objetivo preveria.
- **Boden** — tríade novidade/surpresa/**valor**; P-creativity vs H-creativity.
  Gerar o distante é fácil; reconhecer o distante-valioso é o problema real.
- **Conceptual blending** — Fauconnier & Turner: ideia nova como casamento de
  estruturas de domínios distantes.
- **Distância semântica na criatividade humana** — Beaty, Kenett: ideias
  julgadas criativas conectam conceitos semanticamente distantes (medido com
  embeddings).
- **FunSearch** (Nature 2023) e **AlphaEvolve** (2025) — únicos casos
  documentados de LLM produzindo o que nenhum humano pensou. Receita: LLM como
  gerador de variação + **verificador externo duro** + loop evolutivo. O erro
  só vira inovação com um sistema de seleção ("o olho de Fleming").
- **Mode collapse por RLHF** — modelos instruídos têm distribuição
  artificialmente estreitada; literatura mostra queda mensurável de
  diversidade. Consequência: usar modelos **base**, nunca chat/instruct, no
  papel de perturbador.
- **Vizinhança na literatura (checada 2026-08-09)**: min-p (arXiv
  2407.01082) é o nosso piso; Rusty-DAWG (2406.13069), Creativity Index e
  infini-gram (2401.17377) são a régua padrão de novidade n-gram — falamos a
  língua da área. Fronteira ativa que co-descobrimos por experimento:
  "Death of the Novel(ty)" (ICLR 2026, 2509.22641) argumenta que novidade
  n-gram sozinha não é criatividade — exatamente o nosso modo de escape 3
  (paráfrase factual); "Measuring LLM Novelty as the Frontier of Original
  and High-Quality Output" (OpenReview) propõe novidade = originalidade ×
  qualidade — a estrutura do nosso funil. Não encontrado equivalente: o
  empurrão *ativo* para a cauda semanticamente distante (vs regular a
  cauda), o **teto** de entropia por fronteira de gênero, e a taxonomia
  operacional dos três modos de escape com detectores.

## Arquitetura: quatro órgãos

1. **Perturbador** — decodificação anti-provável *adaptativa por entropia*.
   Insight central: coerência mora desproporcionalmente na sintaxe, nomes e
   aritmética — pontos onde a distribuição é pontuda (baixa entropia). Os
   pontos férteis são as bifurcações de **alta entropia**, onde o próprio
   modelo admite muitas continuações; só ali se escolhe a cauda.
2. **Integrador** — o próprio modelo racionalizando/costurando o desvio.
3. **Avaliador** — coerência via perplexidade de um segundo modelo (fácil);
   **valor** via LLM-juiz ou verificador programático (difícil, essencial).
4. **Loop de seleção** — desvios sobreviventes alimentam a próxima geração:
   evolução, não sorteio único.

## Duas frentes (atacar ambas, uma por vez)

- **Fase 1 — máquina de tokens**: o perturbador no sampler. Exige logits
  completos a cada passo → modelo base open-weights rodando localmente.
  Nível estético: o desvio contínuo, "instrumento para tocar".
- **Fase 2 — máquina conceitual**: blending forçado de conceitos distantes.
  A perturbação está no loop/prompt, não no sampler: *nós* escolhemos pares
  de conceitos distantes via embeddings; um modelo forte via API costura e
  outro julga. Não precisa de logits nem de GPU.

## Decisões de infra (2026-08-03)

- **Princípio: para o perturbador, acesso aos logits vale mais que tamanho do
  modelo.** APIs expõem no máximo top-~20 logprobs — a cauda fica invisível.
  A criatividade, no nosso desenho, vem da política de decodificação + seleção,
  não da inteligência do modelo.
- **Execução: Mac M5 Pro, 48 GB RAM unificada** (máquina do Roberto). GPU
  enxerga ~35 GB via memória unificada.
- **Framework: MLX** (`mlx-lm`) — aceita `logits_processors` e samplers
  customizados em Python puro. (llama.cpp descartado para pesquisa: customizar
  sampler é C++.)
- **Modelos-alvo do perturbador** (sempre versão base):
  - `Qwen3-8B-Base` 8-bit (~9 GB) — calibração rápida, dezenas de tok/s.
  - `OLMo-2-13B` 8-bit (~14 GB) / `OLMo-2-32B` 4–6 bit (~18–26 GB) — **corpus
    de treino público (Dolma)**: via infini-gram dá para verificar se uma
    sequência gerada existe nos dados de treino → métrica *objetiva* de
    novidade. É o modelo que sustenta a afirmação "gerou o que não estava lá".
  - Teto do hardware: 70B em 4-bit cabe (~40 GB) mas é lento demais (~5 tok/s)
    para o loop interativo — não é o alvo.
- **Fase 2 via API**: Kimi K2 (open-weights, tem K2-Base, mas 1T params →
  self-host impraticável; via API é ótimo integrador, forte em escrita
  criativa e barato), DeepSeek, Claude como juiz.
- **Embeddings** (régua de distância): sentence-transformers, roda em CPU/MPS.
- **Sem treino/fine-tuning**: tudo inference-time. Sem cluster.
- **Divisão de trabalho**: nuvem = oficina (código, métricas, testes com
  distribuições sintéticas — sem pesos reais); Mac = sala de concerto
  (execução, calibração, escuta). Git é a ponte.

## Decisões de design do sampler (2026-08-03, item 1 do roadmap)

- **Piso de coerência relativo (estilo min-p)**: candidato precisa de
  `p ≥ floor × p_max`. Piso absoluto quebraria exatamente onde perturbamos —
  nas distribuições achatadas, todo token tem p baixa.
- **Régua de distância da Fase 1: embeddings de entrada do próprio modelo.**
  De graça via MLX, sempre no vocabulário certo. O adapter chama o *módulo*
  de embedding (não indexa a matriz), então funciona igual com
  `QuantizedEmbedding` (dequantiza no lookup).
- **Contexto = EMA dos embeddings** dos tokens vistos (prompt incluído, via
  `observe_prompt`), meia-vida configurável (default 16 tokens).
- **Anti-atrator emergente** (descoberto nos testes sintéticos): o sampler
  observa o próprio desvio, então o contexto migra na direção do que escolhe —
  o desvio de agora vira o normal de depois, e o polo distante alterna. A
  máquina não fica presa no mesmo desvio; oscila entre polos
  (`test_context_follows_deviation_and_oscillates`).
- **Escolha entre candidatos**: `sample` de softmax(score) (default, via
  Gumbel-max) ou `argmax` determinístico. Com λ=0 o modo perturbado degenera
  para min-p sampling — os casos-limite são samplers conhecidos, bom sinal.
- **`max_candidates`** (default 128): teto de candidatos que entram no lookup
  de embeddings, mantém o custo por passo limitado.
- **Núcleo em numpy puro**; mlx só no adapter, com import preguiçoso — a
  suíte sintética roda em qualquer máquina (43 testes; os de mlx pulam onde
  não há Apple silicon).

## Primeira execução (2026-08-04, smoke test 0.6B)

Pipeline validado ponta a ponta com `Qwen3-0.6B-Base-8bit` (o 8B Base não
existe quantizado para MLX; baixamos o bf16 e quantizamos localmente).
Defaults (λ=3, gatilho 2.0, piso 0.05): taxa de perturbação 34%, rank médio
2.6 nos perturbados, distância média 0.89, perplexidade 3.2 — texto coerente.

- **Achado**: o anti-provável saiu *mais* coerente que o baseline categorical
  T=1, que degenerou sozinho (base 0.6B amostra lixo da cauda profunda). O
  piso min-p já é um guarda melhor que o sampling padrão.
- **Decisão de método**: baseline justo = **min-p com o mesmo piso, mesma
  temperatura, λ=0 implícito** — isola exatamente o efeito do empurrão de
  distância. `generate_mlx.py --baseline` faz isso.

## Calibração no 8B (2026-08-09) — item 2 concluído

Quatro varreduras no `Qwen3-8B-Base-8bit` (quantizado local, ~31 tok/s;
`scripts/sweep_lambda.py`, prompt narrativo do faroleiro, seed 0). Cada
colapso observado virou um mecanismo do sampler:

1. **Piso global** — com o piso só nas bifurcações, um passo *não*-perturbado
   amostrou rank 540 (p≈10⁻⁶) e quebrou o texto (quiz, chinês): o acidente
   burro foi 30× mais fundo que o desvio deliberado (rank ≤ 18). O piso de
   coerência agora vale em todo passo; o que é adaptativo é só o empurrão.
   Bônus: λ=0 ≡ baseline min-p exatamente.
2. **Régua padronizada** — o spread de distâncias entre candidatos é ~0.08
   (espaço de embeddings anisotrópico): λ cru < 6 era no-op (trajetórias
   idênticas) e a distância média (~0.8) não discrimina. Distâncias agora são
   z-scoradas por passo entre os candidatos (`distance_scale="standardize"`);
   λ lê-se em nats/σ, faixa útil 0.5–3.
3. **EOS sem empurrão** (`no_push_ids`) — o EOS é "distante de tudo" e o
   empurrão o favorecia (escolhido com d=0.94 num passo perturbado; geração
   morreu com 36 tokens). A forma mais radical de desviar é sair do texto —
   proibida por design; EOS ainda vence pelo próprio logprob.
4. **Banda de entropia** (`entropy_ceiling`) — os colapsos de registro
   (aula de gramática em chinês com λ=3, quiz NLI com gatilho 3.0, o EOS em
   H=4.75) aconteceram todos em passos de entropia altíssima: bifurcações de
   *documento/gênero*, não de narrativa. O empurrão agora atua na banda
   [gatilho, teto); acima do teto, sampling normal com piso — desviar dentro
   da narrativa, segurar o trilho nas encruzilhadas de gênero. Validação: com
   banda [2.0, 4.5], o λ=3 que colapsava produziu a melhor peça até aqui (a
   fábula das tempestades — ver `docs/GALERIA.md`).

**Calibração recomendada (Qwen3-8B-Base)**: λ 1–3 standardized (default 1.5),
banda [2.0, 4.5] nats, piso 0.05, meia-vida 16, modo sample. Perturba ~45–50%
dos passos em prosa, ppl 5–7 (baseline min-p ~3–4), sem colapso de gênero nas
rodadas com banda. Defaults dos scripts refletem isso; o core mantém
`entropy_ceiling=None` (neutro) — teto é política de uso, calibrada por
modelo.

**Deriva residual conhecida**: transições suaves de documento por caminhos de
entropia média (ex.: atribuir a frase a um autor fictício e derivar para
resenha) ainda ocorrem (~1 em 3 gerações com λ=2). Não é degeneração — é
colagem; caso para o Avaliador/loop de seleção, não para mais guardas no
sampler. Hipótese adicional: prompts mais longos ancoram o gênero.

## Revisão da branch antiga (2026-08-09)

`origin/claude/llm-unlikely-predictions-fa5yej` continha uma implementação
paralela do item 1 (sessão antiga, na nuvem): mesmo núcleo conceitual, sem
nada da calibração em modelo real — inclusive com o bug do sampling
desprotegido fora do gate. **Absorvido**: o `ToyLM` (modelo de brinquedo
determinístico com alternância de entropia + embeddings clusterizados),
portado para `src/creative_machine/toy.py` com teste de integração do loop
completo — a oficina da nuvem testa o instrumento inteiro sem pesos.
**Descartado**: o resto (backends próprios, loop de geração manual, entropia
normalizada por log V — alternativa considerada e rejeitada: recalibramos por
modelo de qualquer forma). A branch remota ficou como registro histórico;
`main` é a fonte única.

## Item 4 — novidade objetiva via infini-gram (2026-08-09, em andamento)

- Módulo `creative_machine/novelty.py`: cliente infini-gram (API pública,
  rate-limit-educado, zero dependências novas) + `novelty_report`: fração de
  janelas de n palavras com count 0 no corpus (n ∈ {4,6,8}) e o maior trecho
  do texto presente no corpus (extensão gulosa; counts são monótonos).
- **Índice resolvido**: `v4_olmo-2-1124-13b-instruct_llama` — corpus de
  treino completo da família 13B (superconjunto do que o base viu →
  conservador para "o modelo viu isto?"). Modelo alvo:
  `allenai/OLMo-2-1124-13B` (base) quantizado 8-bit local.
- **Primeira medição comparativa** (textos do Qwen da rodada com banda,
  mesma seed/prompt; medição contra o corpus OLMo — valida o instrumento;
  a alegação literal "não estava no treino" fecha quando o gerador for o
  próprio OLMo):

  | n-grama | baseline min-p | máquina (λ=3, banda) |
  |---|---|---|
  | 4 | 13.9% novos | 32.6% novos (2.3×) |
  | 6 | 62.9% | 91.1% |
  | 8 | 91.2% | 97.7% |
  | maior cópia | 8 palavras | 8 palavras |

  O empurrão desloca a curva inteira de novidade sem alongar o maior trecho
  copiado: mais recombinação local, zero cópia extra. n=1 por braço —
  significância exige o harness multi-seed (item 3).

### Resultado central (gerador e corpus casados) — item 4 concluído

`OLMo-2-13B-Base` 8-bit local (~17 tok/s; banda [2.0, 4.5] transferiu do
Qwen sem retoque, sem colapso de gênero). Geração vs corpus de treino da
própria família, mesmo prompt/seed:

  | métrica (vs treino do OLMo) | baseline min-p | λ=1 | λ=2 | λ=3 |
  |---|---|---|---|---|
  | 4-gramas novos | 12.3% | 35.9% | 49.2% | 45.3% |
  | 6-gramas novos | 71.9% | 87.3% | 90.6% | 85.7% |
  | 8-gramas novos | 96.8% | **100%** | **100%** | **100%** |
  | maior bloco copiado | 9 palavras | <8 | <8 | <8 |

  **Nenhuma geração da máquina contém bloco de 8+ palavras do treino; o
  baseline contém um de 9.** Novidade de 4-gramas triplica. A alegação
  "gerou o que não estava lá" agora é literal — e a régua corrigiu uma
  intuição: o texto λ=3 em registro oitocentista ("brooks flow, torrents
  dash, rivulets trickle") *parecia* eco de Gutenberg; não há bloco de 8+
  no corpus — pastiche de estilo, não cópia.

  Ressalvas: 1 prompt, 1 seed por braço (multi-seed no item 3); novidade
  n-gram = recombinação local, não novidade conceitual — o distante-valioso
  (Boden) continua sendo o gargalo do Avaliador. Textos do OLMo em
  `docs/GALERIA.md` (fábula do sino, litania do mar).

## Avaliador mínimo e o funil de seleção (2026-08-09)

`evaluator.py` + `scripts/evaluate_experiment.py` — o embrião do órgão 3/4:

- **Juiz de outra família** (Qwen julga OLMo): ppl da continuação dada o
  prompt. Resultado no exp1: baseline 7.3±2.0, máquina 8.4–8.5±1.6–3.1 —
  o desvio custa ~+1.2 de ppl aos olhos de um juiz independente. Resolve o
  paradoxo do juiz único para coerência.
- **Dois modos de colapso, dois detectores complementares** (validados
  lendo os casos-limite): colapso-recitação (exercício, credencial factual)
  *cristaliza* a entropia → `entropy_drop_score` pega (queda >0.35 da 1ª
  para a 2ª metade; saudável assenta ~0.2); colapso-colagem (relógio → guia
  turístico de Paris com navegação de site) mantém entropia alta e o
  detector não vê — mas o juiz flagra (ppl 15.3 vs teto 10.2). O filtro é a
  conjunção: `collapse < 0.35 AND judge_ppl < 1.5×mediana(baseline)`.
- **Funil no exp1**: 20/30 células da máquina sobrevivem; ranking por
  novidade média. O topo redescobriu automaticamente a parábola da
  cartógrafa que havia sido selecionada à mão para a galeria — o curador
  automático aproxima o humano.
- Falso positivo conhecido do detector: narrativa que assenta em registro
  infantil simples (entropia cai sem colapso). Aceito: em seleção,
  precisão > recall — perder um bom custa pouco, deixar passar lixo custa o
  funil.

Próximo: fechar o loop (item 6) — sementes da shortlist realimentam a
geração; e a Fase 2 (item 5).

## Piloto do loop evolutivo (2026-08-09)

3 gerações, 3 linhagens iniciais, OLMo gera + Qwen julga + infini-gram mede
(622 consultas). O que o piloto mostrou:

- **A seleção negativa funciona entre linhagens**: o relojoeiro (que colapsa
  consistentemente em exercício, collapse 0.62–0.68) foi *extinto* pelo
  funil na geração 0. A cartógrafa caiu pelo teto do juiz nesta config.
- **Deriva temática coerente e crescentemente específica** na linhagem
  sobrevivente: teoria do faroleiro → mergulhadores de dobrões → "rumors
  persisted that Bimini contained the Fountain of Youth". Tema marítimo
  mantido por 3 gerações sem instrução (EMA + sementes carregam semântica).
- **Terceiro modo de escape descoberto — paráfrase factual**: a linhagem
  Bimini terminou em narrativa histórica *correta* de Ponce de León —
  novelty n-gram 0.91, juiz 7.6, entropia estável: **nenhuma das três
  réguas detecta**. Recontagem de conhecimento com palavras novas ≠
  invenção. Os três modos de escape mapeados: recitação (entropia despenca
  → detector pega), colagem (juiz flagra), paráfrase factual (aberto).
  Caminhos possíveis: checagem de entidades reais (NER), ou juiz-LLM
  perguntando "invenção ou recontagem?" — ponte natural para a Fase 2.
- **Aprendizado de população**: quase-extinção na geração 1 (1 semente).
  Próxima versão: repescagem por rank quando sobreviventes < 2, ou
  população maior.

## Híbrido Fase 1+2 (2026-08-10) — resultado negativo informativo

Hipótese: sementes surreais do nosso sampler → menos `known_equivalent` que
pares de conceitos. **Não confirmada: 11/11 também com equivalente.** Mas o
diagnóstico muda o quadro:

- **As sementes estavam contaminadas pelo modo de escape 3.** A maioria não
  era surreal — eram paráfrases factuais que a régua n-gram marca como
  "novas" (estatística de Alzheimer, o relato Ostman/Sasquatch de 1924,
  história de guildas). Prompts "enciclopédia/guia de campo" convidam o
  base model à recitação. O detector de paráfrase factual saiu de "aberto"
  para **pré-requisito** do pipeline de sementes.
- A única semente genuinamente da máquina (a litania "everything flows away
  to sea") produziu o único score alto (5.65) — anedótico, na direção da
  hipótese.
- **Questão de régua descoberta**: "existe equivalente?" sempre acha um
  parente — toda invenção tem precursores (blockchain ≈ ledger + gossip;
  o que importa é o *delta*). Próxima rubrica: `nearest_equivalent` +
  `novel_delta` ("o que isto adiciona sobre o vizinho mais próximo?") —
  invenção real = parente próximo E delta claro. Sem isso, 32/32
  "recombinações" pode medir o viés do juiz, não a geração.

Próximos degraus definidos: (1) rubrica novel_delta; (2) filtro
anti-factual de sementes (heurística: anos/números/nomes próprios; depois
NER/juiz); (3) re-rodar híbrido com sementes limpas.

### Confronto sob a régua de delta (2026-08-10) — os 3 degraus executados

| braço | julgados | c/ delta | delta_signif. média (máx) | score médio (máx) |
|---|---|---|---|---|
| pares de conceitos (rejulgado) | 10 | 9 | 2.50 (4) | 3.62 (5.24) |
| sementes surreais limpas | 13 | 13 | 2.38 (4) | 3.50 (5.52) |

- **A régua antiga era o gargalo**: "existe equivalente?" dava 32/32
  recombinações; "qual o delta?" revela deltas articuláveis em 22/23. A
  pergunta certa muda a resposta — invenção se mede pelo delta, não pela
  ausência de parentes.
- **Empate entre perturbadores** (n pequeno): sementes surreais ≈ pares de
  conceitos em delta e score. A hipótese do híbrido não se sustenta nem
  morre com n=10–13; deixa de ser prioridade.
- **Teto comum ~4/10 de delta — e um padrão sistemático**: o juiz aponta
  repetidamente a mesma anatomia ("mecanismo é pseudo-física, MAS a
  consequência institucional é genuinamente boa"): Resonance Stewardship
  (captura regulatória de infraestrutura envelhecida), Somnomemorics
  (inversão atuarial velho=estável=barato → engenharia de antiguidade
  falsa). **O costurador é fraco em mecanismo físico e forte em efeitos de
  segunda ordem institucionais.** Hipótese seguinte natural: blends em
  domínio institucional/econômico (onde "mecanismo" é regra de incentivo,
  não física) devem ter delta maior.
- Filtro de sementes funcionou (pegou até comentário Disqus); vazamento
  menor: "Rosalba recalls" (adicionar verbos de memória à lista).
- Custo total da Fase 2 até aqui: ~US$0.35.

## Experimento do input improvável (2026-08-15) — a hipótese original do Roberto

Tese: prompts humanos são amostras da distribuição de treino; todos ativam
as mesmas regiões. Um input que nenhum humano faria ativa configurações não
ativadas → criatividade. Desenho: 3 braços de input, mesma tarefa
(desenvolver ideia com mecanismo), Opus 5 desenvolve (Bedrock,
`main-account`), Sonnet 5 julga (rubrica de delta), improbabilidade do
input **medida** (ppl sob Qwen3-8B). 8 células/braço, ~US$1.5.

| braço | ppl do input | delta_signif | score médio (máx) |
|---|---|---|---|
| típico ("me dê uma ideia inovadora sobre X") | 287 | 4.43 ± 0.49 | 5.86 (6.54) |
| par de conceitos distantes | 777 | 4.50 ± 0.87 | 5.83 (6.95) |
| **contexto composto improvável** | 256 | **5.12 ± 0.93** | **6.64 (7.56)** |

- **O braço improvável venceu** (+0.7 de delta médio, +0.8 de score, os 3
  melhores blends do experimento; primeiro score >7 e primeiro delta 6 de
  toda a Fase 2 — teto anterior era 4). Com n=8 é sinal, não prova
  (~1σ). Direção da hipótese.
- **Reviravolta metodológica**: a perplexidade n-gram do input NÃO mede a
  improbabilidade certa. Os pares de conceitos têm a ppl mais alta (777:
  duas palavras soltas são "estranhas" para um LM) e o menor delta; o
  contexto composto tem ppl *baixa* (256: é prosa fluente) e o maior delta.
  Correlação log-ppl × delta = −0.26. **Improbabilidade sintática ≠
  improbabilidade semântica**: o que importa é o quão longe o *pedido* está
  dos pedidos plausíveis, não quão estranha é a superfície. Régua correta
  para o definitivo: distância do embedding do input ao centróide de um
  corpus de prompts reais (ex.: um subconjunto de instruções públicas),
  não ppl.
- **Anatomia do que funcionou**: os três melhores vieram do registro
  "instructions left for a successor who will not be human" — o Opus
  sustentou o frame estranho sem domesticar e derivou mecanismos com lógica
  interna (arquivo de saudade apagável por "bondade administrada";
  orçamento de capacidade de um agente atado à entropia de uma enquete
  sobre ele mesmo; calendário como recibo termodinâmico de combustível
  queimado). O modelo forte NÃO colapsou o input de volta para o familiar —
  o medo da Fase 2 (Kimi domesticava) não se confirmou com o Opus.
- Ruído: 1 refusal (`typical`, classificador de segurança do Opus 5 num
  prompt inócuo) — tratar com fallback no definitivo.

Próximo (Paper B, `docs/PAPER_B.md`): régua semântica de improbabilidade,
n≥30/braço, k=3 julgamentos por célula, braço extra "improvável sem
registro" para separar o efeito do registro do efeito dos fragmentos.

### Definitivo (2026-08-15, interrompido em 79/150 células por decisão —
o quadro já estava claro; ~US$18): **o efeito do piloto NÃO se replica.**

| braço | n | delta (mediana de 3 juízes) | Δ vs típico (IC95) |
|---|---|---|---|
| típico | 15 | **5.20 ± 1.05** | — |
| conceitos | 14 | 4.00 ± 1.25 | [−2.04, −0.36] ✗ pior |
| improvável | 15 | 4.60 ± 0.95 | [−1.33, +0.13] |
| fragmentos (sem registro) | 16 | 4.69 ± 1.26 | [−1.34, +0.29] |
| registro (sem fragmentos) | 15 | 4.40 ± 0.80 | [−1.47, −0.13] ✗ pior |

- O prompt típico venceu ou empatou com todos; dois braços improváveis são
  *significativamente piores*. Correlação improbabilidade×delta ≈ 0 em
  qualquer régua (kNN +0.05; centróide −0.07; log-ppl −0.17). O piloto
  (n=8, k=1) era variância + juiz de humor variável — exatamente o que o
  desenho k=3/n=30 existia para pegar. **Bom nulo**: régua semântica
  construída e validada, ablação feita, custo controlado.
- Leitura: com um desenvolvedor forte (Opus 5, effort alto), o pedido
  típico já extrai mecanismos sólidos e o juiz premia coerência; o input
  estranho externo custa coerência sem comprar delta. **O improvável de
  fora é ruído** — o que fundamenta a migração da hipótese para o loop
  interno (DREAM, abaixo). Paper B fica como capítulo negativo honesto do
  Paper A (ou seção do paper do DREAM), não como paper próprio.
- Infra a corrigir antes de reusar o juiz: `max_tokens` do julgamento
  (2 JSONs cortados), regex de parse mais tolerante, refusal-fallback
  cobrindo o desenvolvedor em todos os caminhos.

## O loop de devaneio — projeto de arquitetura (2026-08-15)

### A tese (Roberto)

A mente não é um LLM que recebe prompts. É um sistema em **loop fechado
com o próprio output** — pensamento gerando pensamento — e o novo surge
quando esse loop, rodando sem tarefa, produz um desvio que sobrevive à
crítica. O improvável de fora é ruído; o improvável fértil é o que o
próprio sistema gera de dentro, porque já vem costurado ao resto do que ele
sabe. Consequência: **a criatividade não está no input, está no loop.**
(Corrobora: no híbrido, a única semente boa foi a única gerada pelo nosso
sampler; no experimento do input improvável, o prompt estranho *externo*
não bate o típico na prévia parcial.)

### O que a neurociência acrescenta

Três redes, não dois modos (Beaty et al., 2014–2024): a **default mode**
(geração espontânea, recuperação de memória — o devaneio), a **executiva**
(avaliação, controle) e a **de saliência** (o *switch*: decide o que merece
atenção e alterna as outras duas). O achado central: pessoas mais criativas
têm mais *acoplamento* DMN–executiva — sinergia, não revezamento rígido.
Insight = desvio gerado no modo espontâneo que sobrevive à passagem pelo
modo crítico; incubação = deixar o loop rodar sem tarefa. Também: a fase de
geração ativa recuperação de memória (lobo temporal medial) — o novo é
recombinação de material *acumulado*.

### O que já temos que corresponde

| órgão da mente | o que temos | o que falta |
|---|---|---|
| default mode (devaneio) | o sampler anti-provável — desvio *dentro* da geração, EMA de contexto migrando (o anti-atrator) | rodar sem tarefa, longo, com o output como próximo contexto |
| executiva (crítica) | o funil: juiz cross-family, detector de colapso, régua de delta | rodar *intercalado* no fluxo, não em batelada no fim |
| saliência (switch) | a banda de entropia (decide *onde* desviar) | um sinal de "isto merece atenção" que dispare a crítica no meio do fluxo |
| memória acumulada | o EMA (meia-vida 16 tokens); a população do loop evolutivo | memória de longo prazo do que o loop já pensou (dias, não tokens) |

### Arquitetura proposta: DREAM (Drift–Review–Escalate–Accumulate–Memory)

Um fluxo único e longo, sem prompt de tarefa (só uma semente inicial),
com quatro processos acoplados:

1. **Deriva** (default mode): o sampler anti-provável gera continuamente
   em modo "solto" — banda de entropia larga, λ alto, meia-vida do EMA
   longa (o contexto lembra mais). O texto gerado É o próximo contexto.
   Sem instrução, sem persona: base model puro pensando alto.
2. **Saliência** (o switch): um monitor barato roda a cada N tokens sobre
   o fluxo e dispara quando detecta um *evento*: (a) salto semântico —
   distância entre o EMA de agora e o EMA de M tokens atrás acima de um
   limiar (o pensamento mudou de região); (b) queda de entropia depois de
   um trecho de alta entropia (o modelo "cristalizou" algo depois de
   vagar); (c) recorrência — o fluxo voltou a um tema de muito antes (o
   loop se fechou). Sem saliência, nada é avaliado — a crítica não roda o
   tempo todo (isso mataria a deriva, como o controle executivo mata o
   devaneio).
3. **Revisão** (executiva): no evento, o trecho recente vai ao juiz — que
   pergunta três coisas: é coerente? conecta duas regiões *distantes* do
   que veio antes (o critério de Beaty/Kenett)? tem delta sobre o parente
   mais próximo? Se passa: **insight candidato** registrado com proveniência
   (posição no fluxo, EMA antes/depois, veredito). Se não passa: o fluxo
   segue; nada é descartado do texto (a deriva não é editada — a mente não
   apaga devaneios, só não os promove).
4. **Escalada** (o acoplamento DMN–executiva): quando um insight candidato
   é registrado, o loop **muda de regime**: por um trecho, o sampler roda
   com banda estreita e λ baixo (modo "desenvolver o achado", quase
   normal), e o insight é injetado como contexto explícito — o pensamento
   *elabora* o que a saliência marcou. Depois volta à deriva. Isso é a
   sinergia: geração e controle no mesmo fluxo, alternando por sinal
   interno, não por relógio.
5. **Memória** (acumulação): os insights candidatos vão para uma memória de
   longo prazo (arquivo versionado); sementes de sessões futuras são
   sorteadas dela — o loop de amanhã começa do que o de hoje achou (a
   população do `evolve.py`, elevada a dias). Métrica de longo prazo: os
   insights ficam mais *conectados* entre si com o tempo? (a rede de
   conceitos do próprio sistema fica mais densa — o "material acumulado").

### Como medir (o que torna isso ciência e não poesia)

- **Controle A**: mesmo fluxo com sampler plain (λ=0) — o loop sem
  devaneio. **Controle B**: prompts improváveis externos (o experimento de
  hoje) no mesmo orçamento de tokens. **Controle C**: saliência
  desligada, crítica por relógio (a cada N tokens) — testa se o *switch*
  importa.
- **Variáveis**: taxa de insights candidatos por 10k tokens; delta médio
  dos candidatos (juiz); *distância conectada* — quão longe estão as duas
  regiões que o insight une (Beaty); sobrevivência ao rejulgamento k=3;
  e, no longo prazo, densidade da memória.
- **Predição da tese**: DREAM > controle B (loop interno bate input
  externo) e DREAM > controle C (o switch por saliência bate a crítica por
  relógio). Se DREAM ≈ A, a deriva não importa e a tese cai; se DREAM ≈ C,
  a saliência não importa (só o intercalar).

### Custo e ordem de construção

Tudo local exceto o juiz (Bedrock, só nos eventos de saliência — barato
por construção). Ordem: (1) monitor de saliência sobre o telemetria que já
existe (puro numpy, testável com o ToyLM); (2) o fluxo Deriva+Escalada como
modo novo do sampler (dois SamplerConfigs alternando por sinal); (3) a
Revisão plugando o juiz existente; (4) a memória como diretório em `runs/`
+ sorteio de sementes; (5) os três controles no harness. Estimativa: 2–3
sessões para o piloto.

### Construído e calibrado até aqui (2026-08-15, noite)

`salience.py` (jump / crystallize / recurrence / stagnation +
`genre_collapse_score`), `dream.py` (motor: `generate_step` manual, EOS
mascarado, KV cache único, regimes drift/escalate/kick trocáveis sem
perder o EMA, reseed por injeção de semente, juiz só nos eventos),
`scripts/dream_run.py` (controles plain/clock, `--no-judge` para
calibrar), habituação graduada no sampler (`repetition_window/penalty`),
juiz da Revisão (`judge_reverie`: coerência / conecta-regiões-distantes /
delta). 115 testes.

**Cinco sondas de deriva sem juiz (OLMo-2-13B, 1.5k–3k tokens) — os
poços da mente sem controle, cada um ensinando um mecanismo:**

| sonda | o que aconteceu | lição / mecanismo |
|---|---|---|
| 1 | morreu em 125 tokens (EOS) | mascarar EOS; laço próprio sobre `generate_step` |
| 2 | ruminação erudita (Eco→Heráclito→Platão, 1.500 tokens circulando; ao fim recita o Crátilo) | detector de estagnação + kick (λ alto por um trecho) |
| 3 | começo lindo → quiz → **órbita literal** de 4 frases que λ=4 não quebra (distribuição pontuda: a banda nunca abre) | habituação graduada por frequência recente (o kick não chuta porta fechada) |
| 4 | sem órbita, mas **afunda no rodapé de site** ("Terms of Service \| © LLC") por 2.000 tokens; jump disparava a cada 24 (EMA rápido curto demais) | detector de colapso de gênero por superfície (diversidade lexical, capitalização, símbolos — separa 0.09 vs 0.6); EMA rápido 24 |
| 5 | detector dispara, reseed injeta semente boa ("what if gravity suddenly stopped working") e **em 20 tokens volta ao rodapé** — 12 vezes seguidas | **o contexto acumulado É o poço**: 3k tokens de boilerplate no KV cache puxam qualquer semente de volta |

**Achado central da calibração**: um loop fechado *sem esquecimento*
converge para o atrator mais frequente do pré-treino e não sai — a
"mente" do modelo base largada não devaneia, **recita a web**. A mente
humana escapa disso porque (a) o buffer de trabalho é curto e (b) o que
persiste é a memória *selecionada* (o que a saliência marcou), não o
fluxo bruto; e (c) valores puxam o devaneio (interesse), não só
habituação empurrando de trás. **Próxima mudança (arquitetural):
esquecimento seletivo** — no reseed, truncar o KV cache e reter só
semente inicial + trechos/insights bons + nova semente; deriva com janela
curta, memória longa apenas do que valeu. Também: testar Qwen3-30B como
Deriva (outra dieta de pré-treino, poço de boilerplate possivelmente
mais raso).

**Sondas 6–7 (mesma noite): o gerador era a variável dominante.**
- Sonda 6 (OLMo + esquecimento seletivo): a dinâmica mudou (3 reseeds em
  vez de 12; a saliência volta a variar) mas o destino não — os 200 tokens
  "de antes do colapso" já eram o começo do colapso; qualquer fatia do
  fluxo do OLMo carrega a semente do rodapé. Como Deriva, o OLMo-2 é o
  gerador errado (perfeito para a Fase 1 pelo corpus público; errado para
  devanear pela dieta de web crua).
- **Sonda 7 (Qwen3-30B-A3B, mesma semente/config): devaneia.** 1.000+
  tokens de narrativa genuína (a menina, o caderno "The Edge", a pena
  negra), reseeds voltando para *prosa* (fábula do gênio, com moral) e ao
  fim uma deriva para devaneio matemático que **encena um insight**
  ("Perhaps instead of viewing summation as repeated addition, we should
  view it as repeated application of addition! Ahhhhh… Aha!"). Zero
  boilerplate em 14k caracteres. Poços restantes são os nossos: repetição
  de parágrafos (órbita longa; a estagnação pega, o kick resolve) e
  história que se reinicia. **Decisão: Qwen3-30B é a Deriva do DREAM.**
  Próximo: primeira rodada com juiz.

**Primeiras rodadas com juiz (dream1, dream2; ~US$0.15 total):**
- dream1 (semente do faroleiro): a semente carrega o gênero — "X had one
  theory about Y, and it was this:" é frase de *sinopse* no pré-treino; o
  Qwen deslizou em 3 linhas para blurb de livro infantil e #kidlitreview.
  13 revisões, todas `connects_distant: 0`, vereditos precisos. Regra:
  sementes devem ser narrativa em primeira ordem (algo aconteceu a
  alguém), nunca frames de metadiscurso.
- dream2 (semente do caderno, deriva boa): 7 revisões, 1 score não-zero
  (2.29). Sobre a melhor prosa (a pena negra), o juiz: "coerente, mas
  vinheta genérica que **abandona a premissa do caderno em vez de ligá-la**".
  **Achado**: a deriva pura produz *mudança de assunto*, não insight —
  o loop vaga fluentemente de tema em tema *abandonando* o anterior. O EMA
  de contexto puxa para longe (anti-atrator por desenho); não existe força
  de **retorno com síntese**. Insight, pela definição que adotamos (Beaty),
  é ligar o novo ao velho — e nada no Deriva empurra para a ligação. A
  saliência e o juiz funcionaram como desenhados (o crítico não deixou
  passar nada; a Escalada não disparou porque nada mereceu).

**Estado do DREAM ao fim da noite**: o loop inteiro toca junto (Deriva,
Saliência, Revisão, Escalada, reseed com esquecimento) e a Deriva devaneia
sem cair nos poços; o que falta é o mecanismo que a mente tem e o loop não:
a **puxada de volta com síntese** — o insight nasce quando o devaneio
*reencontra* a premissa. Próximo mecanismo (a implementar): a Escalada
como *reencontro* — não só "desenvolver o achado", mas injetar, no evento
de saliência, um retorno explícito à premissa/regiões antigas (as
recorrências e a memória de insights) e pedir ao Deriva que costure; e/ou
um segundo termo no score do sampler que, em vez de só distância ao
contexto recente, recompense *proximidade a regiões antigas distantes do
recente* (a ponte). É a diferença entre vagar e devanear.

**A ponte (2026-08-16, madrugada) — implementada e testada em 3 rodadas:**
`bridge` no sampler (bônus por aproximar-se de âncoras antigas *distantes
do contexto recente*, z-scorado como o empurrão), âncoras = premissa +
snapshots do EMA lento, Escalada com reencontro textual.
- dream3: primeira escada de scores (2.0→3.91), recorrências cedo — a
  ponte puxa de volta. Mas puxou a premissa como **repetição literal**, e o
  Qwen racionalizou a repetição no gênero em que ela é normal: **corpus
  paralelo de tradução** (`ru:`/`zh-cn:`, cada frase em três línguas). Poço
  novo, detector adicionado (tags de língua + script não-latino);
  habituação alargada para a memória de trabalho inteira (voltar ao tema,
  não à frase).
- dream4: sem corpus paralelo; melhor 4.16 — e o veredito do juiz é o
  marco: sobre "Almost-happens happened late one night [...] Her notebook
  held names for nameless things", ele diz `connects_distant: 4`, "converte
  a lista de hipotético em realizado — um *payoff* do setup anterior".
  **Três rodadas antes dizia "abandona a premissa"; agora diz "o setup se
  cumprindo".** O loop dobrou sobre si mesmo. O que falta para o 5: a
  conexão é premissa+eco, não *duas margens distantes* — porque após o
  reseed com esquecimento só sobrava a premissa como âncora. Correção
  (dream5): âncoras persistem através do esquecimento — apaga-se o texto do
  poço, não a memória do que foi pensado (esqueço o fluxo, lembro os temas).
- **dream5 (4.500 tokens, âncoras persistentes): o primeiro insight
  candidato do DREAM.** A janela "the boy didn't become an adult, he
  became an animal; [...] someone didn't die, he lived; the world didn't
  spin, it stopped. **Almost-happens happened late one night.**" — a
  premissa (coisas que quase aconteceram) invertida em realização: os
  quases aconteceram, a lista virou clímax. Três julgamentos da mesma
  janela: **4.76 / 5.24 / 4.93** — exatamente sobre o limiar 5; o juiz vê
  e nomeia ("converts the catalog into a realized climax, collapsing the
  almost/real distinction the text spent building"; `connects_distant`
  5–6) e desconta ("payoff competente do próprio setup, não um salto").
  Curva do melhor score por rodada: 0 → 2.29 → 3.91 → 4.16 → 4.76 —
  sobe a cada mecanismo. Um candidato marginal em 4.500 tokens com dez
  mudanças de assunto: a tese da raridade em ação.
- Gargalo atual mudou: não é mais o poço, é a **frequência de reseed** —
  10 em 4.500 tokens; a "mente" muda de assunto antes de sintetizar.
  Próximo: (a) k=3 com mediana no juiz da Revisão (a Escalada não pode
  depender do humor de um julgamento); (b) reseed menos ansioso (mais kicks
  antes de reseed, janela de estagnação maior) para as ideias amadurecerem;
  (c) então os três controles (plain / clock / input externo) para a
  primeira comparação formal do DREAM.
- **dream6 (k=3 mediana, reseed paciente): o ciclo completo fechou.**
  `[step 788] INSIGHT via crystallize: score 5.24 delta 4.0` (mediana de
  3; `connects_distant` 6) — a Escalada disparou pela primeira vez, o
  reencontro foi injetado ("It came back to the notebook, of course; it
  always did, but this time") e o modelo, em regime estreito, **elaborou
  o achado**: "Everything that almost happened piled up inside her like
  snow falling sideways through open windowsills into rooms filled with
  silence instead of noise. [...] Piled up until almosts were real. She
  kept a notebook because sometimes almosts piled up too much to be
  ignored." — as inversões da deriva integradas à premissa numa imagem
  única, e a mecânica do insight com explicação interna (os quases se
  acumulam até virarem reais). Deriva → Saliência → Revisão → Escalada,
  de ponta a ponta, com produto legível. Um candidato em 4.500 tokens
  (0.22/1k); depois dele o loop voltou ao ciclo estagnação→reseed sem
  novo candidato — reseed ainda ansioso demais (11). Custo ~US$0.30.

**Primeira comparação formal (2026-08-16, madrugada; 1 rodada/condição,
mesma semente, 4.500 tokens, juiz k=3):**

| condição | revisões | candidatos | melhor score |
|---|---|---|---|
| **DREAM** (deriva + saliência) | 10 | **1** | **5.24** |
| controle A — plain (λ=0, sem ponte) | 8 | 0 | 2.71 |
| controle C — clock (saliência off, juiz a cada 150) | 30 | 0 | 2.88 |

Ambas as predições na direção da tese: DREAM > plain (o devaneio importa)
e DREAM > clock (o *switch* importa: o relógio revisou 3× mais, gastou 4×
mais tokens de juiz e não achou nada — revisa onde nada aconteceu). n=1
por condição: **direção, não prova**. Custo dos controles ~US$0.50.

**Experimento definitivo do DREAM (a rodar)**: 5 sementes narrativas em
primeira ordem × 3 condições (+ o controle B de input externo com a mesma
rubrica), 4.500 tokens, k=3; métricas: candidatos/1k, melhor mediana,
`connects_distant` médio das revisões; IC bootstrap sobre sementes.
~US$5 de juiz, ~4h de máquina (rodar de madrugada, tampa aberta).
Predição: DREAM > C > A em candidatos/1k; se DREAM ≈ A a deriva não
importa; se DREAM ≈ C o switch não importa.

**Resultado do definitivo (rodou 20:52–21:58 de 2026-08-15, 15 células,
~1h, térmica nominal em todos os checkpoints, ~US$4): NULO — e um achado
sobre o instrumento.**

| condição | revisões | score médio | ≥4 | melhor por semente |
|---|---|---|---|---|
| DREAM | 49 | 0.48 | 1 | 4.48, 2.88, 2.88, 0, 0 |
| plain | 40 | 0.46 | 0 | 2.71, 2.88, 3.11, 0, 2.29 |
| clock | 150 | 0.10 | 0 | 3.78, 2.88, 0, 0, 1.82 |

- **Zero candidatos acima do limiar em todas as 15 células — inclusive
  `s0_none`, a configuração exata do dream6.** A mesma janela (passo 788,
  texto idêntico) que ontem recebeu 5.24 (mediana de 3) hoje recebeu
  4.48 (mediana de 3): **a diferença é inteiramente do juiz**. O "primeiro
  insight" do dream6 e o "não-insight" de hoje são a mesma janela em dias
  diferentes. Com a variância do juiz (~±0.5–1 mesmo com k=3), o limiar 5
  não é um detector — é uma moeda.
- ICs bootstrap: DREAM−plain [−0.41, +0.44] em todas as revisões (empate);
  DREAM−clock [+0.10, +0.70] (o DREAM revisa melhor que o relógio — mas o
  relógio dilui a média revisando 3× mais onde nada aconteceu; no melhor
  por semente, empate). **A comparação de ontem (n=1) não se replica.**
- Sinais fracos e honestos: o DREAM tem o único ≥4 (4.48) e o melhor por
  semente mais alto; nenhuma condição passa de ~3 nas outras 4 sementes.
  As sementes novas (mapa, padeiro, relógio, rio) renderam pouco em todas
  as condições — a semente do caderno era excepcionalmente fértil, e boa
  parte da "curva ascendente" 0→4.76 vinha de *uma* semente e da
  variância do juiz.

**Leitura**: (1) o loop toca junto e produz janelas na faixa 4–5 numa
semente boa — mas *não* de forma que os controles não produzam também, na
amostra que temos; (2) o gargalo real agora é **a régua**: um juiz LLM
com ±1 de ruído sobre um limiar binário não mede diferenças da ordem
que estamos procurando. Antes de qualquer mecanismo novo: régua melhor —
k maior *e* score contínuo (sem limiar) como métrica primária, e/ou juiz
mais forte (Opus como juiz), e/ou avaliação humana cega das top janelas de
cada condição; (3) e mais sementes (n=5 é pouco para efeitos deste
tamanho). O DREAM segue como programa; a evidência a favor, hoje, é
qualitativa (dream6 elaborou o achado de forma legível), não estatística.

**Medindo a régua (2026-08-16, madrugada; 89 janelas × k=5 × 2 juízes =
890 julgamentos, ~US$12):**

| juiz | spread intra-janela | DREAM | plain | clock | DREAM−plain | DREAM−clock |
|---|---|---|---|---|---|---|
| Opus 5 | 0.71 (sd 0.30) | 1.41 (máx 4.16) | 1.67 | 0.67 | [−0.87, +0.38] | [+0.14, +1.34] |
| Sonnet 5 | 0.27 (sd 0.11) | 0.57 (máx 4.76) | 0.35 | 0.00 | [−0.26, +0.74] | [+0.21, +1.02] |

- **O Sonnet é "consistente" porque dá zero em quase tudo** (`connects_
  distant: 0` → score 0 na média geométrica; todas as 30 janelas do clock
  = 0). O Opus distribui scores contínuos e por isso tem resolução — ao
  custo de ±0.7 de ruído, da mesma ordem que as diferenças entre
  condições. Nenhum dos dois é instrumento de precisão para este efeito.
- **DREAM ≈ plain nos dois juízes** (ICs cruzam zero); **DREAM > clock**
  em ambos (a saliência revisa melhor que o relógio). O único ≥4 é do
  DREAM (a janela do caderno).
- **Conclusão honesta**: com esta amostra e esta régua, o loop *com*
  deriva (λ + ponte) não se distingue do loop *sem* deriva no mesmo
  arcabouço; o que se distingue é a saliência (vs relógio). A peça da
  arquitetura que a evidência sustenta hoje é o **switch**, não o empurrão.

## Auditoria externa (Claude Science, leitura de `runs/`, 2026-08-16 manhã)

Um agente independente recomputou os dados brutos. **Quatro correções
aceitas** (números reproduzidos por nós): (1) o abstract misturava o
baseline do piloto n=1 (12.3%) com a média multi-seed (45.5%): a razão
honesta é **2.1×**, não 3×; (2) "zero blocos de 8+ palavras" era uma
célula — no grid, 3/15 células da máquina têm bloco ≥8 (vs 12/15 do
baseline): **taxa 0.80 → 0.20**, resultado mais forte dito como
probabilidade; (3) o grid é pareado (prompt×seed): bootstrap pareado dá
ICs mais apertados (λ=2: +24.0 pp [18.2, 29.5]); (4) o detector de
recitação (`entropy_drop_score`) tem AUC 0.71 e precisão 0.33 no limiar
0.35 sobre o exp1 — "segunda metade mais quieta" descreve assentamento
normal; sem telemetria do baseline não há taxa de falso positivo. Passa a
descritivo; correção barata: logar JSONL do braço λ=0. **Uma
discordância**: o "nulo do DREAM" dele vem do contador binário de insights
(`insights_per_1k`) — instrumento que já tínhamos aposentado; o resultado
do arcabouço vem do re-julgamento contínuo (`rejudge_surprise.json`), que
ele não analisou. Sua conclusão sobre o instrumento ("gargalo no scorer")
coincide com a nossa. Papers corrigidos.

## Ablação do arcabouço (2026-08-16, 10 sementes × 5 condições, 212 janelas
re-julgadas Opus k=5; ~US$15) — o controle de honestidade venceu

| condição | surpresa | conexão | coerência | boas (S≥5 & H≥5) |
|---|---|---|---|---|
| **arcabouço** (saliência+esquecimento+reseed+kick) | 3.22 ± 1.91 | 1.60 ± 1.52 | 3.72 ± 1.67 | 8/50 |
| só saliência (revisão gatilhada, sem reseed) | 2.74 ± 1.76 | 1.36 ± 1.36 | 3.71 ± 1.59 | 2/42 |
| **nu + reseed por relógio** (sem saliência, sem esquecimento) | **3.08 ± 1.48** | **3.15 ± 1.53** | **4.78 ± 0.95** | **12/60** |
| nu | 0.33 ± 0.70 | 0.17 ± 0.52 | 2.08 ± 1.86 | 0/60 |

- Arcabouço vs nu replica com 10 sementes: surpresa δ=+0.88, p≈10⁻¹⁶.
- **Mas nu+reseed-por-relógio empata com o arcabouço em surpresa (IC
  [−0.50, +0.80]) e o supera em conexão (δ=−0.60, p≈3×10⁻⁸) e coerência
  (δ=−0.41).** Quase todo o efeito "estrutura vs nada" é explicado por
  **uma** operação: interromper periodicamente e injetar uma nova frase de
  partida. Saliência, esquecimento seletivo e kicks não somam surpresa em
  cima disso; o esquecimento *tira* conexão (a nua-com-reseed lembra tudo
  e conecta mais).
- Reencontro: nunca disparou (atrelado ao juiz binário) — `abl_forget` ≡
  `scaffold0` em texto nos 10 casos; ablação vazia; a testar com gatilho
  por saliência.
- Geometria (todas as sementes): o arcabouço volta mais perto da premissa
  (0.57 vs 0.72 só-saliência vs 0.78 nu) e explora 3× o raio da nua;
  nu+relógio salta pelo espaço (48 "fechamentos") — assinaturas distintas,
  e o juiz prefere a do relógio-sem-esquecer em conexão.

**Leitura**: a tese estrutural sobrevive na forma mais simples e mais
forte — geração contínua sem interrupção é morta (0.33; congela no poço), e
o que a ressuscita é **interromper e ressemear**, sobre contexto
preservado. Os mecanismos elaborados (saliência como gatilho de *revisão*
continua valendo — dream_def — mas não como arquitetura de *geração*)
não pagam seu custo. Abstract a reescrever: "creativity is in interrupting
the loop". Próxima pergunta boa, e barata: **frequência** e **qualidade da
semente de interrupção** — é onde o efeito mora.

**Teste da leitura 3 — rubrica de surpresa (mesmas 89 janelas, Opus
k=5, três dimensões independentes, ~US$5):**

| dimensão | DREAM | plain | clock | DREAM−plain | DREAM−clock |
|---|---|---|---|---|---|
| surpresa | 2.97 ± 1.87 | 3.48 ± 2.01 | 1.43 ± 1.65 | [−1.50, +0.49] | [+0.63, +2.43] ✓ |
| conexão | 1.93 ± 1.75 | 1.97 ± 1.27 | 0.73 ± 0.96 | [−0.80, +0.74] | [+0.50, +1.93] ✓ |
| coerência | 4.37 ± 1.99 | 4.14 ± 1.36 | 3.73 ± 2.24 | [−0.64, +1.10] | [−0.47, +1.70] |

- **O empurrão não compra surpresa** (plain até ligeiramente acima; IC
  cruza zero). Empate em conexão e coerência. Leitura 3 descartada; fica
  a **leitura 2**: dentro do arcabouço DREAM, o sampler anti-provável
  (λ + ponte) não produz diferença mensurável sobre amostragem plain — em
  nenhuma das réguas (delta, conexão, surpresa, coerência; 1.335
  julgamentos, 2 juízes). O que produz diferença robusta é a **saliência**
  (vs relógio, ICs positivos em surpresa e conexão).
- Os "top por surpresa" são quase todos "abandona um loop degenerado por
  algo não relacionado": o juiz premia o **reseed** (nossa injeção de
  semente), não a deriva. A surpresa visível é a mudança de assunto.

**Síntese da noite (2026-08-16, 03h)** — o que a evidência sustenta e o
que não:
1. Sustenta: o **switch por saliência** (revisar quando o fluxo faz algo
   notável) bate revisão por relógio, com IC, em duas rubricas. É a peça
   de Beaty que sobreviveu à medição.
2. Sustenta (qualitativo): o arcabouço — esquecimento, reseed, reencontro,
   Escalada — produz elaborações legíveis (dream6). Não medimos o
   arcabouço contra sua ausência (o controle plain o *inclui*).
3. **Não sustenta**: que o empurrão anti-provável token-a-token melhore o
   devaneio. Isso é coerente com a Fase 1? Sim, se lida com cuidado: lá o
   empurrão comprou *novidade n-gram* (recombinação local, medida contra o
   corpus) e custou coerência; aqui a régua é conexão/surpresa/delta de
   *ideia*, e nesse nível o empurrão não aparece. **A novidade de superfície
   não sobe de nível sozinha.** É a mesma lição de "Death of the Novelty",
   agora dentro do nosso próprio loop.
4. Instrumento: juiz-LLM tem ±0.6–0.7 de ruído por dimensão mesmo com k=5;
   detecta efeitos ≥1 ponto (saliência vs relógio), não efeitos de meio
   ponto. Diferenças menores exigem avaliação humana cega ou n muito maior.

**Próximo passo lógico**: o experimento que falta é **arcabouço vs sem
arcabouço** — DREAM completo (com λ=0, já que o empurrão não importa) vs
geração contínua sem saliência/esquecimento/reseed/reencontro. Se o
arcabouço vencer, a tese "a criatividade está no loop" tem sua evidência
na forma certa: é a *estrutura do loop* (esquecer, voltar, elaborar), não
o ruído no sampler, que faz o devaneio.

**Arcabouço vs nada (2026-08-16, 03h17–04h05, 10 células, térmica
nominal; re-julgamento Opus k=5, 3 dimensões, 51 janelas, ~US$4):**

| dimensão | arcabouço DREAM (λ=0) | geração nua | diff (IC95) |
|---|---|---|---|
| **surpresa** | **3.24 ± 1.77** (n=21) | 0.47 ± 0.76 (n=30) | **[+1.99, +3.60]** ✓ |
| **conexão** | **1.48 ± 1.37** | 0.27 ± 0.63 | **[+0.61, +1.87]** ✓ |
| coerência | 3.48 ± 1.22 | 2.60 ± 2.12 | [−0.08, +1.74] |

**O arcabouço vence, e vence forte**: ~7× a surpresa e ~5× a conexão da
geração contínua nua, com ICs longe de zero, sem perda de coerência (se
algo, ganho). 3/21 janelas do arcabouço com surpresa ≥5 e coerência ≥5;
0/30 na nua. Juiz sobre a melhor: "a dead stretch of sidebar boilerplate
suddenly breaks into a lucid dream-image of a river renamed at..." (a
semente do rio reencontrada como imagem onírica).

**Conclusão do programa DREAM (primeira evidência com significância)**:
a criatividade do loop está na sua **estrutura** — saliência (quando
olhar), esquecimento seletivo (soltar o poço), reseed (mudar de assunto),
reencontro/Escalada (voltar e elaborar) — e **não** no empurrão
anti-provável do sampler (λ, ponte: sem efeito mensurável, 1.335
julgamentos). Isso refina a tese do Roberto na direção mais forte:
pensamento gerando pensamento cria *quando o loop tem a arquitetura da
mente* — esquecer, voltar, saber quando prestar atenção. O ruído injetado
é irrelevante; a dinâmica é tudo.

Ressalvas honestas: n=5 sementes; juiz-LLM (Opus, k=5, ±0.5 por dimensão)
— o efeito aqui é grande o bastante para o instrumento (≥2 pontos), ao
contrário do empurrão; a "geração nua" é um controle forte mas não o
único possível (falta desmontar o arcabouço peça a peça: só saliência /
só esquecimento / só reencontro — a ablação que diz *qual* parte da
estrutura importa). Custo total do DREAM até aqui: ~US$30 de juiz.

## Bateria 2 — do que é feita a interrupção? (2026-08-16, tarde; em execução)

**Confundidor descoberto ao desenhar a bateria** (antes que um revisor o
achasse): a condição `bare` usa um `SamplerConfig` cru — **sem** a
habituação (`repetition_window=512, repetition_penalty=1.15`) — enquanto
todas as condições interrompidas herdam o `drift` padrão do DreamConfig,
que a tem. `bare` vs `bare_reseed` difere portanto em *duas* coisas
(interrupção e habituação), não em uma. E os textos do `bare` morrem em
**loops literais** ("Highly recommended." ×100, tabelas de números,
gabarito de prova) — exatamente o que uma penalidade de repetição desfaz.
Logo o controle que falta é `bare_habit`: habituação, sem interrupção
alguma. Se ficar vivo, o mecanismo do paper não é "interromper", é "não
deixar o loop comer o próprio passado literal"; se ficar morto, a tese
"interromper" fica limpa. Leitura qualitativa das primeiras células: sem
loops literais, mas ainda no poço de gênero (papo de chatbot, gabarito de
inglês parafraseado, blurb de autoajuda) — longe da premissa. O juiz
decide.

**Desenho** (10 sementes × 8 condições, 4.500 tokens, λ=0, sem
esquecimento, sem juiz no loop; janelas julgadas offline por Opus k=5;
`scripts/dream_battery2.py`, `runs/dream_b2/`):

| condição | o que testa |
|---|---|
| `bare_habit` | habituação sem interrupção — o confundidor |
| `clock_reenc` | relógio 150, injeta um *reencontro* (volta à premissa) em vez de mudança de assunto — **conteúdo** |
| `clock_premise` | relógio 150, injeta a própria frase de abertura — conteúdo |
| `clock_self` | relógio 150, injeta uma janela do **próprio passado** do fluxo (≥400 tokens atrás; antes disso, a premissa) — pensamento alimentando pensamento |
| `sal_reenc` | reencontro disparado pelo **evento de saliência** (sem juiz) — **timing** (vs `clock_reenc`) e vs `abl_salience` (mesmo timing, sem injeção) |
| `clock75/300/600` | mudança de assunto neutra em outras **frequências** |

Melhorias de medição: `tokens.json` por célula (ids do fluxo + posição
exata de cada evento/injeção — as janelas antigas eram cortadas por índice
de passo, que desloca alguns tokens a cada injeção); pontos de revisão
`cut` (logo antes de cada injeção: o que o fluxo produziu até ser
interrompido) e `clock` (grade uniforme de 150, pontos a ≤20 tokens de um
`cut` descartados); rejulgador com cap por (célula, tipo). Textos de
reencontro neutros quanto à premissa (o padrão antigo dizia "the
notebook", de uma semente só). Reencontro rearmado por saliência sem
passar pelo juiz binário aposentado (`reencounter_on_event`).

**Resultados parciais (2026-08-16, 15h; Q1 e Q2 completos, 60 janelas
por braço, ICs pareados por semente):**

| condição | surpresa | conexão | coerência |
|---|---|---|---|
| nu (sem habituação) | 0.33 | 0.17 | 2.08 |
| nu + habituação (`bare_habit`) | **1.70** | 1.08 | 4.08 |
| nu + habituação + reseed neutro/150 (`bare_reseed`) | **3.08** | **3.15** | **4.78** |
| relógio/150, costura de reencontro | 2.28 | 3.03 | 4.30 |
| relógio/150, a própria premissa | 1.12 | 0.90 | 3.07 |
| relógio/150, o próprio passado | 1.36 | 1.33 | 2.95 |

- **Q1**: habituação e interrupção são duas operações e as duas importam
  em surpresa (Δ +1.37 [+1.07, +1.67] e depois +1.38 [+0.92, +1.92]);
  a **conexão é toda da interrupção** (+2.07 [+1.63, +2.57], δ=0.75).
  A manchete corrigida: "não deixe o loop comer o próprio passado
  literal, e interrompa-o".
- **Q2**: **a interrupção precisa levar para longe.** Neutro > costura de
  reencontro (surpresa −0.80 [−1.35, −0.25]; conexão empata) ≫ premissa ≈
  próprio passado (todos os ICs pareados excluem zero; δ≈−0.7) — injetar
  uma *volta* equivale a não interromper. O próprio passado realimenta o
  atrator (o poço de gabarito de prova recebeu de volta as suas próprias
  questões). O juiz vê conexão quando o fluxo acha sozinho o caminho de
  volta, não quando é mandado voltar. Isso inverte a intuição de projeto
  do DREAM (reencontro como peça-chave) — e é exatamente o tipo de coisa
  que só a medição mostra.
- **Q3 (timing) — a saliência é boa leitora e mau metrônomo** (fechado
  19h30, com controles de frequência casada a cada 900): a costura de
  reencontro nos eventos de saliência (1–9/célula) melhora as *janelas de
  evento* (3.92 / 2.99 / 3.75 vs só-saliência 2.63 / 1.39 / 3.71), mas o
  *fluxo* fica pobre: janelas uniformes 2.18 / 1.68 / 3.93 vs **4.70 /
  3.48 / 5.50** para a mesma costura no relógio de 900 (surpresa Δ +2.02
  [+1.62, +2.44] pareado) e 5.48 / 2.87 / 5.95 para o neutro a cada 900
  (45/60 "boas" — a melhor célula do programa). A saliência decide *onde
  olhar*, não *quando interromper*.
- **Q4 (frequência) — o rendimento da interrupção depende do fio que ela
  quebra, e decai.** 75: morto (0.88, δ −0.83 vs 150). 150: 3.08. 300 /
  600 / 900: janelas até ~160 tokens *depois* da quebra **5.28 / 3.35 /
  5.95**, 5.40 / 3.20 / 5.65 e 5.90 / 2.80 / 6.10 (34/60 "boas" no início
  de 300 vs 12/60 a 150); mais fundo no segmento volta a ≈3.2. Ponderando
  as fases pela composição do fluxo (160/período): 300 dá o melhor fluxo
  (4.35 / 3.18 / 5.97) > 600 (3.82) > 900 (3.68) > 150 (3.08) > 75 (0.88);
  a conexão cai com segmentos mais longos. Ritmo: deixar desenvolver
  algumas centenas de tokens, depois quebrar para longe.
- Correção de medição no caminho: o primeiro `cut` das condições novas
  cai no passo 2 (janela de 2 tokens) e a amostragem uniforme sempre o
  pegava — 73 janelas degeneradas (S 0.95) excluídas (`MIN_STEP=100`);
  sem elas, a costura de reencontro fica em 2.68 / **3.64** / 4.72 (troca
  surpresa por conexão em relação ao neutro; conexão +0.49 [−0.09, +1.07]).

**Q5 — segunda família (Qwen3-8B-Base, 40 células, 398 janelas)**: a
escada replica com a mesma forma: nu 0.68 → habituação **1.47** (Δ +0.78
[+0.45, +1.13]) → interrupção **2.73** (Δ +1.26; conexão 0.87 → **3.23**,
Δ +2.37 [+1.68, +3.12], δ=0.80) ≈ arcabouço 2.73 (conexão 1.53).

**Dentro da rede (2026-08-16, noite; 180 células capturadas, 13 camadas +
logit lens; `docs/APPENDIX_HIDDEN_*.md`, `docs/figures/hidden_*.png`)**:
- H1: o nu congela em todas as camadas, mais na superfície (raio 0.13 vs
  0.42–0.53 na camada 0; 0.24 vs 0.33–0.34 no topo, ICs disjuntos); no
  30B ele "decide tarde e com certeza" (compromisso estável 11.12 vs
  10.9; entropia final 0.34 vs 0.42–1.08 — assinatura de cópia); no 8B a
  ordem de compromisso não replica (só a entropia).
- H2: o que o juiz chama de surpresa é *partida na superfície com
  continuidade profunda*: passo na camada 0 ρ +0.2 a +0.6 com a surpresa
  dentro das condições; em profundidade o sinal inverte nas condições por
  saliência (−0.3 a −0.5); entropia final ρ +0.3 a +0.6 em toda parte
  ("confiante = sem surpresa").
- H3: o reseed **com esquecimento** move o estado profundo (+0.09 → +0.21
  de cosseno além do controle) e o traz de volta à premissa (+0.20); o
  reseed por relógio **sobre contexto preservado** quase não o toca
  (+0.01–0.03, sem volta) — e é o que o juiz premia. A profundidade da
  interrupção escala com o comprimento do fio quebrado (75 ≈ 0; 150 0.01;
  300 0.02–0.04; 600 0.04–0.075), não com o conteúdo injetado. Replica no
  8B (+0.03 → +0.10 vs +0.01–0.03).
- Correção operacional: a captura fez o sistema debulhar (25 GB no
  compressor) por logits fp32 de 13 camadas vivos no grafo preguiçoso do
  MLX; corrigido com avaliação por camada + `mx.clear_cache()` + bloco de
  256 (23 s → 8–14 s por célula).

**Terceira família — OLMo-2-13B (2026-08-17, 05h20–10h20; 40 células,
395 janelas Opus k=5, captura em 14 camadas; `runs/dream_famolmo/`)**: a
escada replica pela terceira vez: nu 1.35 / 0.91 / 2.97 → habituação 2.37
/ 1.51 / 4.05 → interrupção **3.11 / 3.17** / 3.28 (conexão +1.66 [+1.10,
+2.20], δ=0.58) ≈ arcabouço 3.08 / 1.89 / 4.48. Nuance nova: no OLMo a
interrupção simples **custa coerência** (−0.77 [−1.58, +0.03]) e o
arcabouço com esquecimento a preserva (4.48 vs 3.28) — quando o poço é
boilerplate de web, esquecer é o que deixa a semente pegar (confirma a
inferência das sondagens de calibração). O nu do OLMo é menos morto que o
do Qwen (vaga entre gêneros em vez de travar em loops literais; raio 0.36
vs 0.13). H3 replica, maior: esquecimento +0.20→+0.38 e volta à premissa
+0.13–0.18; relógio +0.02–0.06, sem volta.

**Juiz de segunda família (2026-08-17, manhã; `scripts/judge_agreement.py`,
`runs/judge_agreement/`)**: Kimi K2.6 (Moonshot, OpenRouter) rejulgou 140
janelas (20/condição) com a mesma rubrica, k=5: concordância com o Opus
surpresa ρ=+0.85, conexão +0.77, coerência +0.71 (n=140); mais generoso e
mais ruidoso (dispersão 2.0–2.6 vs 0.5–0.7), mesma ordem de condições em
tudo. Custo ~US$1. Avaliação humana: pacote v2 (63 janelas, interface em
inglês) + guia do avaliador (`docs/blind/RATER_GUIDE.md`, cláusula
anti-IA); Roberto contratando 2 avaliadores no Workana; `blind_score.py`
calcula concordância humano–humano (Spearman, alpha de Krippendorff) e
humano–Opus. Roberto avaliou 10 janelas: ρ +0.37/+0.47 (n=10; escala
comprimida no topo, contexto não lido — regra explicada; versão leve
`pack_v1_lite.html`). **Avaliadora 1 (2026-08-17)**: 63/63, escala
inteira; surpresa ρ=+0.47 (p=1e-4) com o Opus e a ordem das condições
reproduzida (interrupção 7.7–9.0 > arcabouço 4.6 > nu/habituação
3.2–3.9); coerência ρ=+0.23 — para a leitora, a mudança de assunto dentro
da janela lê como quebra de coerência. Confirmou por escrito: sem IA;
consente descrição anônima ("native/bilingual English speaker"). Grupo: Jessica (UK, nativa, editora), Claudia (BR, não-nativa avançada,
acadêmica), Naviab (PK, nativa/bilíngue) entregues; Cecilia (AR, bilíngue,
editora/criativa) em andamento; Beatriz S., Annaliese descartadas; Kelsey
indisponível; Sheila não contratada. ORCID do Roberto:
0009-0006-8650-629X (na capa). Nome de publicação: Roberto I. Ono Filho.

**Três avaliadoras (2026-08-17)**: 63/63 cada, escalas inteiras, calibrações
distintas (médias de surpresa 3.4 Jessica / 4.3 Claudia / 6.1 Naviab). Cada
uma vs Opus em surpresa ρ 0.40 / 0.50 / 0.47 (p ≤ 1e-3); coerência 0.60 /
0.47 / 0.23. **Média das três vs Opus: surpresa ρ=+0.58 (p=7e-7), coerência
+0.52 (p=1e-5)** — tanto quanto elas concordam entre si (Spearman par a par
0.71/0.38/0.25 surpresa, α intervalar 0.30; coerência 0.69/0.60/0.42, α
0.38). Ordem humana de consenso: relógio 300 6.5 ≈ reseed 6.4 > costura 5.3
> saliência 5.0 > arcabouço 3.6 ≈ habituação 3.6 > nu 1.5; interrupção − nu
[+3.1, +6.5]; habituação − nu [+0.1, +3.9]. Em coerência humanos preferem
habituação sem interrupção (7.7) às interrompidas (5.7–6.3). Parágrafo do
§6 escrito com esses números; falta a Cecilia. Pagamentos: Jessica R$ 267,24;
Claudia R$ 300,00; Naviab R$ 186,94 (no paper: R$187–300, ~US$35–55).

**Estado do manuscrito (2026-08-16, 20h)**: rascunho completo v1 —
`docs/PAPER_DREAM.md` (inglês) e `docs/PAPER_DREAM_pt.md` (tradução
integral), HTMLs autocontidos com 16 figuras e 6 apêndices
(`docs/manuscript.html`, `docs/manuscrito.html`). Falta para "final":
avaliação humana cega (`docs/blind/pack_v1.html`, 42 janelas) e passada
de revisão; venue a decidir (ver seção Publicação).

Encadeada na mesma execução: **segunda família de gerador** —
Qwen3-8B-Base-8bit em `bare` / `bare_habit` / `bare_reseed` / `scaffold0`
(`runs/dream_fam8b/`), para saber se "nu morto / interrompido vivo" é sobre
modelos ou sobre um modelo.

**Interpretabilidade (código pronto, roda depois das baterias —
`scripts/hidden_states.py`, `scripts/hidden_analysis.py`)**: uma passada
do fluxo pelo próprio modelo com KV cache, capturando o residual em 13
camadas (0..47 de 4 em 4): vetores de janela (64 tokens, passo 32) por
camada → **H1** geometria por camada e condição (em que camada o `bare`
congela?); **H2** novidade da janela julgada vs todo o passado, por
camada, correlacionada com a surpresa julgada (que camada "vê" a
surpresa?), mais logit lens (camada de compromisso: primeira camada cujo
top-1 já é o final — o modelo decide cedo ou tarde nas janelas
surpreendentes?); **H3** distância antes/depois de cada injeção por
camada, menos controle em posições aleatórias (a que profundidade a
interrupção chega, por tipo de conteúdo?).

## Parecer externo (2026-08-18) e revisão maior

Parecer de um revisor externo (`docs/revisor_externo.txt`, ~1.400 linhas):
"major revision / weak reject" — contribuição real e memorável (interromper
sem apagar o contexto), mas (1) unidade estatística é a semente, não a
janela (pseudorreplicação); (2) a frase injetada está *dentro* das janelas
julgadas (confundidor: o juiz pode premiar a nossa frase); (3) validação
humana estratificada pelo próprio juiz, sem "connection", 9 janelas/cond.;
(4) faltam baselines (interrupção sem habituação; sham/fronteira neutra;
EOT permitido; penalidade forte); (5) título/abstract prometem "criatividade"
e os dados sustentam "surpresa/conexão narrativa julgada"; inconsistências
("three families" = 3 modelos de 2 famílias; prompt = Claude→Claude apesar
da regra cross-family; "nobody judges during generation" vs juiz no loop do
scaffold; "carries all of the connection"; "attractor"/"dead"); análise
interna superinterpretada; related work pequeno (11 refs a incluir).
Concordância nossa: quase total. Discordância parcial: manter sampler e
prompt como motivação curta (não remover), com linguagem calibrada.

**Plano P0 (2026-08-18 →)**: (a) janelas só-gerado (margem 32 após a
injeção, 96 tokens, nenhuma janela cruza duas injeções; contexto anterior
mostrado, região julgada só com tokens do modelo) e rejulgamento de todos
os conjuntos (`rejudge_gen.json`); (b) bateria 3: interrupção sem
habituação (150 e 300), sham (só "\n\n") a 300, sham contínuo ("And so, as
before,") a 300, EOT permitido como fronteira natural (`bare_eos`),
habituação forte 1.3 (`habit_strong`); (c) estatística por semente como
principal (permutação exata nos 10 pares; janela → apêndice); (d) rodada 2
humana: amostra aleatória, 3 dimensões, 5 avaliadoras; (e) reescrita:
título/abstract/conclusão calibrados, terminologia, inconsistências,
hiperparâmetros, link do repositório, related work +11; figuras com pontos
por semente; análise interna como descritiva.

**Execução do P0 (2026-08-18, tarde/noite)** — feito até agora: (a)
`windows_generated` + `--protocol gen` (janelas de 96 tokens só-gerado, 32
após a injeção; deslocamentos 160/300/450/600/750 para a curva de
decaimento; grade de 150 nos braços sem injeção) e cinco trabalhadores de
rejulgamento em `dream_scaffold`, `dream_b2` (dois), `dream_fam8b`,
`dream_famolmo` (`rejudge_gen.json`); (b) bateria 3 (`runs/dream_b3`, 80
células: `nohabit150/300`, `sham_break300`, `sham_cont300`, `bare_eos`,
`habit_strong`, `reset_reseed300`, `reset_break300`), julgamento `gen`
encadeado; (c) `scripts/analysis_gen.py` — célula como unidade, IC
bootstrap sobre células, diferenças pareadas por semente com permutação
exata por sinal (2^10), Cliff δ sobre médias de célula, q-valores BH por
família de comparações, figuras `fig9_*` com os 10 pontos pareados,
`docs/APPENDIX_GEN.md`; (d) `scripts/blind_pack3.py` (rodada 2: janelas
só-gerado, células ao acaso, três dimensões, guia embutido, EN) e
`blind_score.py` generalizado; (e) paper: related work +11 referências
verificadas no ACL Anthology (novos parágrafos: repetição/auto-reforço/
entrainment; avaliação de criatividade e juízes; loops de steering em
histórias; tuned lens), método reescrito (protocolo primário só-gerado,
unidade = célula, juiz no loop esclarecido — nas 10 células do scaffold no
30B o juiz Sonnet revisou 80 eventos e **nenhum** passou o limiar: escalada e
re-encontro julgado nunca dispararam; nas famílias o scaffold rodou sem
juiz), modelos base como decisão de escopo, "three generator models from two
families", hiperparâmetros completos, as dez premissas, prompt do juiz
literal, parâmetros/datas de API, fonte dos 10k prompts (Alpaca), link do
repositório (a criar), declaração ética; instrumento (repetibilidade ≠
validade; limites da rodada 1 humana), limitações, rede como descritiva,
sampler/prompt como "dois nulos motivadores" com linguagem calibrada.
Rascunhos Markdown (`PAPER_DREAM*.md`) congelados na v1; o LaTeX é o
mestre. Pendente: `exp_loop`, introdução, resumo, discussão, conclusão e
título — só com os números do protocolo novo.

**Bateria 4, confirmatória (pré-registro, 2026-08-18 ~17:10, antes de
qualquer resultado da bateria 3 ou do rejulgamento `gen`)**: dez premissas
NOVAS (`NEW_SEEDS` em `scripts/dream_battery2.py`, escritas agora, nunca
usadas), semente do RNG = 1, cinco braços × 10 células no Qwen3-30B-A3B:
`bare_habit`, `clock300`, `sham_break300`, `nohabit300`, `reset_reseed300`;
protocolo `gen`, unidade = célula, teste de permutação exato pareado.
Contrastes pré-especificados (unilaterais no sentido indicado, α = 0,05):
**primário** H1: `clock300` > `bare_habit` em surpresa. Secundários: H2:
`clock300` > `sham_break300` em surpresa (a mudança de assunto vale mais que
uma fronteira neutra); H3: `clock300` > `reset_reseed300` em conexão
(preservar o contexto carrega a conexão); H4: `clock300` vs `nohabit300` em
surpresa (bilateral: a habituação importa dado que há interrupção?). Tudo o
mais é exploratório. Rodada encadeada após a bateria 3 (`runs/dream_confirm`).

**Resultados do protocolo só-gerado (2026-08-18, noite; unidade = célula,
10 premissas; IC bootstrap sobre células; p = permutação exata pareada por
sinal)** — os conjuntos scaffold, b2, 8B e OLMo rejulgados; b3 e a
confirmatória em julgamento/geração:

- *Escada no 30B (janelas de 96 tokens só-gerado, 32 após a injeção; grade de
  150 nos braços sem injeção)*: bare 0,45 / 0,30 / 2,52 → habituação 1,55 /
  1,27 / 4,56 → habituação + interrupção 150 **3,02 / 3,68 / 6,12** → scaffold
  2,70 / 1,85 / 6,02. Interrupção sobre habituação: surpresa +1,5 [+0,8, +2,3],
  p = 0,004; conexão +2,6 [+1,7, +3,6], p = 0,004, δ = +1,00 (todas as
  premissas); coerência +1,9 [+0,2, +3,3]. O efeito da interrupção **sobrevive
  à exclusão do texto injetado**; o da habituação sozinha encolhe (0,45 →
  1,55 em surpresa; era 0,28 → 1,70 no protocolo de eventos).
- *Conteúdo (150)*: neutro ≈ costura (3,02 / 3,68 vs 2,94 / 3,96); premissa
  (1,29 / 1,01) e passado próprio (0,90 / 1,05) tão ruins quanto não
  interromper (p ≤ 0,016, δ −0,84 a −1,00). Inalterado.
- *Ritmo/decaimento*: **a descoberta "o rendimento cresce com o fio quebrado"
  (5,3–5,9 após 300–900 vs 3,1 após 150) desaparece** — era em boa parte o
  juiz lendo a frase injetada. Janela pós-interrupção (32–128 tokens de texto
  gerado): 3,0 (150), 2,9 (300), 3,3 (600), 2,5 (900), todas as diferenças
  pareadas contra 150 cobrindo zero; conexão maior no período mais curto (3,7
  vs 2,1–2,9); coerência sobe levemente com o período; decaimento dentro do
  segmento fraco. Estimativa de fluxo (por deslocamento, ponderada pelo trecho
  do segmento): 150 melhor ou igual. Período 75 não é mensurável no protocolo
  novo (nenhuma janela de 96 tokens gerados cabe entre duas injeções).
- *Saliência*: as janelas pós-injeção da costura por saliência são tão boas
  quanto as da costura no relógio 900 (3,4 / 2,7 vs 3,5 / 3,1); a diferença
  está no fluxo entre interrupções (janelas ≥300 tokens após a última
  injeção: 1,7 vs 3,0). "Boa leitora, mau metrônomo" fica, com esta forma.
- *Famílias*: 8B 0,43 → 1,37 → 2,76 (interrupção sobre habituação: surpresa
  +1,4, p = 0,008; conexão +2,2, p = 0,002), scaffold 2,70 / 2,35. OLMo 1,41
  → 2,14 → 2,81 (conexão +1,5, p = 0,008; surpresa +0,7, p = 0,29), scaffold
  3,34 / 2,04 / 6,30 (melhor braço em surpresa e coerência no OLMo:
  esquecimento tira o fluxo do poço de boilerplate).
- *Teste–reteste do instrumento, de graça*: `scaffold0` e `abl_forget` são
  **byte-idênticos** nas 10 células (o juiz do loop nunca passou → o
  re-encontro nunca disparou) e foram julgados independentemente: medianas de
  5 iguais em 91% das janelas em surpresa (|Δ| médio 0,09), 85% conexão, 71%
  coerência; médias de célula diferem −0,01 [−0,09, +0,07]. Consequência: a
  comparação abl_forget vs scaffold da v1 era vazia (textos idênticos); a
  afirmação "kicks/escalada não acrescentam" saiu do texto.
- *Concordância entre protocolos* (médias por condição, evento vs só-gerado):
  ρ = +0,62 surpresa, +0,94 conexão, +0,86 coerência (14 condições).
- *Juiz "capturado"*: em ~1% das chamadas o Opus responde no modo da janela
  degenerada (boilerplate, código) em vez de JSON — entrainment do próprio
  juiz; a mediana das chamadas restantes resolve.

## Publicação — opções com prazos verificados (2026-08-16)

- **Título final (2026-08-17)**: *Interrupting the Loop: Where Creativity
  Lives in a Language Model*. "Not the sampler, not the prompt" fica no
  resumo. DREAM permanece como nome da hipótese de origem (Método) e a
  receita mínima ganha o termo "the interrupted loop" (Discussão).

- **Decisão (2026-08-17, revista)**: na hora de publicar, **migrar com o
  histórico inteiro** — clone-espelho do repositório privado, `git
  filter-repo --replace-text` para purgar o placeholder de afiliação (a empresa)
  dos dois commits de `paper/main.tex` (datas/mensagens preservadas; hashes
  mudam), push para um **repositório novo e público** com nome de publicação
  (p.ex. `interrupting-the-loop`); este fica arquivado e a sessão atual não
  é tocada. Antes disso: README em inglês; tradução integral deste caderno
  para `docs/NOTEBOOK.md` (último passo, com o texto final); `CLAUDE.md` em
  inglês; a versão PT do manuscrito pode ficar como extra.
- Avaliadores humanos: anônimos no paper (perfil, recrutamento, remuneração
  e cegueira descritos; sem nomes; agradecimento anônimo); JSONs em
  `runs/blind/`, fora do git; só estatísticas agregadas publicadas.

- **arXiv** (cs.CL / cs.AI): sem prazo; preprint assim que a bateria 2, a
  segunda família e a interpretabilidade estiverem no manuscrito. Serve
  de base a qualquer submissão abaixo.
- **ICLR 2027** — em **abril de 2027, no Brasil**; abstract **18/09/2026**,
  paper **25/09/2026** (AoE). Top-tier, competitivo; exigiriam avaliação
  humana e segunda família de gerador (ambas em curso). Timing e local
  atraentes; risco alto.
- **NeurIPS 2026 workshops** (dez/2026; prazo sugerido de submissão
  **29/08/2026**, cada workshop define o seu): "Can We Trust the Judge?
  Building Reliable Evaluation for Language Models" (Atlanta) — encaixa o
  nosso §6 (instrumento medido: Sonnet inflado em zero, Opus ±0.7, limiar
  binário = moeda) como paper curto metodológico; "Interpretability as a
  Science" (Sydney) — a análise de estados ocultos, se der resultado;
  "Principles of Generative Modeling" (Paris). O Creative AI Track fechou
  em 03/08.
- **ICCC'27** (International Conference on Computational Creativity; a
  edição de 2026 foi em Coimbra, 29/06–03/07, com abstract ~1/03 e paper
  ~8/03) — a casa natural do paper principal; prazo esperado ~março/2027.
- Cuidado: há conferências predatórias com a sigla "ICCC" (WASET,
  "conferenceindex") — ignorar; a real é computationalcreativity.net.

## Métricas

- **Coerência**: perplexidade sob um segundo modelo.
- **Novidade**: distância a corpus; para OLMo, consulta infini-gram ao Dolma.
- **Valor**: juiz (LLM forte ou verificador programático) — o gargalo real.
- **Telemetria por passo**: entropia da distribuição, rank do token escolhido,
  distância semântica percorrida, P(token escolhido). É o que permite *ver*
  o instrumento enquanto toca.

## A tese da raridade (Roberto, 2026-08-10)

Criar o novo-que-importa é raro também em cérebros naturais — pouquíssimos
humanos o fazem, mesmo com uma vida de treino. A raridade não é defeito do
processo criativo; é a estatística dele. Consequência de design: não
esperar valor de cada geração, e sim **volume barato de variação + funil
implacável + critério de valor que não seja gosto**. As duas primeiras
partes existem; a terceira é a rota do verificador (item 7).

## Roadmap

- [x] **1. Esqueleto** — feito 2026-08-03: pacote `creative_machine`
  (`src/`), núcleo do sampler adaptativo por entropia, métricas, telemetria
  JSONL, 43 testes sintéticos, adapter `mlx-lm` e script
  `scripts/generate_mlx.py` para a primeira execução.
- [x] **2. Primeira execução** — feito 2026-08-09: Qwen3-8B-Base-8bit
  calibrado (ver "Calibração no 8B"); os pontos de quebra viraram quatro
  mecanismos novos do sampler; primeiros artefatos em `docs/GALERIA.md`.
- [x] **3. Harness de experimentos** — feito 2026-08-09:
  `run_experiment.py` (grid prompts × seeds × braços, um load; fase de
  novidade com IC bootstrap vs baseline) + `sweep_lambda.py`. Resultado com
  significância (3 prompts × 5 seeds, OLMo-13B, 3133 consultas):

  | braço | 4-gramas novos | 6-gramas novos | Δ4 vs baseline (IC95) |
  |---|---|---|---|
  | baseline min-p | 21.5% ± 10.4 | 70.9% ± 12.4 | — |
  | λ=1 | 36.0% ± 12.8 | 87.6% ± 7.7 | [+6.9, +23.0]pp ✓ |
  | λ=2 | 45.5% ± 11.2 | 89.7% ± 6.1 | [+16.3, +31.4]pp ✓ |

  Todos os ICs excluem zero; efeito monotônico em λ; λ=2 dobra a novidade
  local. **Modo de falha mapeado**: as piores células do λ=2 são colapsos de
  fronteira de gênero — exercício de matemática (prompt do relojoeiro) e
  recitação factual (credencial real de 13 palavras copiada do corpus). Ao
  cruzar o gênero, o texto fica *menos* novo: o modelo recita. A novidade
  n-gram não detecta o colapso didático (números novos contam como novos) —
  os dois fatos apontam o mesmo próximo órgão: detector de gênero/Avaliador.
- [x] **4. OLMo-2 + novidade via infini-gram** — feito 2026-08-09:
  OLMo-2-13B-Base 8-bit rodando; `novelty.py` + `novelty_check.py`; índice
  do corpus da família resolvido; resultado central: zero blocos de 8+
  palavras do treino nas gerações da máquina (baseline: 9), novidade de
  4-gramas 3× a do baseline.
- [ ] **7. Rota do verificador (decidida 2026-08-10)**: domínio 1 = online
  bin packing (verificador determinístico, baselines clássicos, espaço de
  melhoria comprovado por FunSearch/AlphaEvolve). Pergunta do experimento:
  **o sampler anti-provável encontra heurísticas que a amostragem normal
  não encontra, no mesmo orçamento?** Braços: λ=0 vs λ calibrado, mesmo
  modelo (Qwen3-8B-Base — mais código no treino), mesmo n de amostras;
  seleção pelo verificador, não por juiz. Domínio 2 candidato: mecanismos
  econômicos verificáveis por simulação (leilões, incentivos).

  **V0 rodado (amostragem pura, 40/braço, `runs/verify2`)**: qualidade
  empatada (CI da diferença de excess cruza zero); ambos os braços
  *reinventaram* o best-fit (excess_min = baseline exato), nenhum o
  superou — esperado sem evolução (FunSearch usou milhões de amostras +
  loop). Sinais: (a) validade 40/40 no anti-provável vs 34/40 no plain —
  contra-intuitivo, re-testar; (b) **perturb_rate ~0.15 em código vs ~0.45
  em prosa** — a banda confirma que código é cristalizado, mas com só 15%
  dos tokens empurrados o operador quase não atua: recalibrar a banda para
  código (trigger < 2.0?) antes de concluir; (c) infra: detokenizer do
  streaming perde 1 espaço na fronteira da completion (61/80 mortes até o
  fix). Próximo: o loop evolutivo verificado (prompt com melhores versões
  anteriores, estilo FunSearch) — é onde o operador de variação
  realmente compete.

  **V1 — evolução verificada (5 ger × 20/braço, banda de código [0.9, 4.0],
  `runs/evoverify1`)**: o primeiro sinal. O braço plain ficou **100
  amostras parado no best-fit** (nunca saiu do platô em 5 gerações). O
  braço anti-provável **saiu do platô na geração 3** com uma heurística de
  forma não-humana (transformação não-linear em dois estágios:
  `(rr+item)^(-1/3) − √rr` escalada por `|item−rr|`, re-pontuada por razão
  quadrática sobre o resultado) que domina o best-fit no treino (0.0590 vs
  0.0610) mas **empata em teste** (0.0593 vs 0.0588) — a vantagem não
  generalizou (20 instâncias de treino = overfit fácil). Leitura honesta:
  n=1 corrida/braço; "o anti-provável explora onde o plain congela" é
  sugestivo, não provado. Experimento definitivo desenhado: treino maior
  (100+ instâncias), 5+ corridas por braço com seeds de experimento
  distintas, mais gerações, e teste de significância sobre as curvas.
  Perfil de entropia de código medido: p50=0.57, p80=2.17, p95=4.14 —
  código cristaliza muito abaixo da prosa; a banda de prosa só engajava
  ~20% dos passos.

  **§8-B definitivo (2026-08-15, 5 corridas × 8 ger × 20/braço, treino
  100, teste 200, `runs/evoverify_definitive`, ~2h de máquina, térmica
  nominal o tempo todo): RESULTADO NULO LIMPO.** Fugas do platô no treino:
  plain 2/5, anti-provável 1/5. Em teste, nenhum campeão de nenhum braço
  bate o best-fit (0.0603) além do ruído (melhor: 0.0599 antiprob_r1,
  0.0600 plain_r1); as fugas do plain no treino (0.0639, 0.0649)
  *pioraram* em teste (0.0610) — overfit ao conjunto de seleção. Média de
  excess em teste: plain 0.0605, antiprob 0.0602. **O sinal do V1 era
  variância de n=1.** Conclusão honesta: neste problema, com este modelo
  (8B base) e este orçamento (160 amostras/corrida), o operador
  anti-provável não separa da amostragem plain sob evolução verificada; o
  gargalo é a capacidade do gerador de propor heurísticas melhores que o
  best-fit, não a política de variação. Não generaliza para "anti-provável
  não ajuda em busca verificada" — generaliza para "não a este custo". O
  que mudaria o quadro: modelo maior, orçamento 10–100×, ou domínio onde o
  espaço de heurísticas acima do baseline é mais denso. Item 7 fica como
  infraestrutura pronta + resultado nulo documentado; a rota B só volta
  com um desses três.

  **Decisão (2026-08-15): voltar com modelo maior E orçamento maior de uma
  vez** — `Qwen3-30B-A3B-Base` (MoE, 30B total / 3B ativos: conhecimento
  de 30B com velocidade acima do 8B denso; 8-bit ~32 GB cabe nos 48 GB).
  Levantamento de alternativas: Qwen3-Coder-Next-Base (80B MoE, o melhor
  coder base atual — não cabe), Qwen2.5-Coder-32B base (denso, ~8 tok/s
  em 6-bit — aposta de capacidade, plano B), Olmo-3-1125-32B base (corpus
  público — candidato para o §8-A do Paper A). Cache HF limpo (Mistral-7B
  descartado em favor do Olmo-3 como terceira família).

  **§8-B no Qwen3-30B-A3B (2026-08-15, 5 × 8 × 40/braço = 3.200
  heurísticas, treino 100, teste 200, `runs/evoverify_30b`, ~1h): NULO DE
  NOVO, agora com modelo 4× maior e orçamento 2×.** Fugas no treino: plain
  2/5, antiprob 3/5 — mas todas rasas (melhor treino 0.0633 vs 0.0652) e
  **nenhuma sobrevive ao teste** (médias 0.0602 vs 0.0604; melhor 0.0600 vs
  baseline 0.0603 — ruído). Validade 5/6 → 90%+ em ambos os braços. O teto
  do gerador subiu pouco: um base 30B redescobre o best-fit à vontade, mas
  não propõe nada estruturalmente melhor com 320 amostras/corrida. Dois
  modelos, dois orçamentos, mesmo resultado → o nulo é robusto **neste
  domínio**: online bin packing com itens uniformes(0.1, 0.7) tem best-fit
  perto do ótimo (excess ~6% do LB); o espaço acima do baseline é ralo
  demais para qualquer operador de variação brilhar com <10³ amostras. O
  FunSearch precisou de ~10⁶ e de instâncias OR-Library difíceis. Lição:
  a próxima tentativa da rota B, se houver, precisa de **domínio com
  headroom mensurável** (baseline claramente sub-ótimo), não de mais
  modelo. Rota B pausada; foco no Paper A.
- [x] **5. Fase 2 (piloto)** — 2026-08-10: pipeline completo
  (`data/concepts.txt` ~580 conceitos → embeddings da régua da casa → pares
  na banda de distância p75–95 → Kimi K2.6 costura → Claude Sonnet 5 julga
  via OpenRouter; ~US$0.05/rodada de 12). **Resultado sóbrio: 21/21 blends
  julgados receberam `known_equivalent`** — recombinações fluentes e
  vistosas, nenhuma invenção pelo critério do juiz duro (scores 2.0–5.65,
  nenhum ≥7). O detector nascido da paráfrase de Ponce de León funcionou na
  primeira missão: o sistema *sabe* que ainda não inventou. Aprendizados
  operacionais: kimi-k2.6 raciocina por default (desligar via
  `reasoning.enabled=false`); filtros de conteúdo derrubam julgamentos de
  texto médico (célula falha sozinha, corrida segue); o juiz tem variância
  entre corridas (mesmo blend, 3.56 vs 5.65 — julgamento fino exige k
  amostras). Próximos degraus: costura com mecanismo obrigatório +
  autocrítica; julgamento k-amostrado; e o híbrido Fase 1+2 — usar as
  frases surreais do *nosso* sampler como matéria-prima da costura (a
  vantagem que só nós temos).
- [ ] **8. Fusão — loop interrompido sobre um problema com verificador
  (desenho, 2026-08-16; executar depois do paper).** Duas lições se
  encontram: na rota B o gargalo foi o *teto do gerador num domínio sem
  headroom*, não o operador de variação; no DREAM, o que dá vida ao fluxo
  de um modelo base é *interromper e ressemear sobre contexto preservado*.
  Experimento: um domínio com headroom mensurável (bin packing com
  distribuição difícil / instâncias OR-Library, ou uma construção
  combinatória pequena com pontuador), em que a *proposta* é um devaneio
  sobre o problema — o modelo pensa em prosa+código num fluxo longo,
  interrompido a cada N tokens com (a) reseed neutro, (b) reencontro com o
  enunciado, (c) o próprio melhor programa verificado até ali (self); a
  cada corte extrai-se o candidato e verifica-se. Comparar com amostragem
  few-shot plain no mesmo orçamento de tokens: melhor pontuação em teste e
  **diversidade** dos programas verificados (distância de edição / AST); e
  timing relógio vs saliência. É a versão verificável de "pensamento
  gerando pensamento". Custo: máquina, não API.
- [x] **6. Loop evolutivo (versão estética mínima)** — piloto 2026-08-09:
  `scripts/evolve.py` (gerar → funil → extrair sentença mais nova →
  ressemear, linhagem registrada). Aberto: verificador programático estilo
  FunSearch para domínios verificáveis, e o detector de paráfrase factual
  (ver piloto abaixo).
