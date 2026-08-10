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
- [x] **6. Loop evolutivo (versão estética mínima)** — piloto 2026-08-09:
  `scripts/evolve.py` (gerar → funil → extrair sentença mais nova →
  ressemear, linhagem registrada). Aberto: verificador programático estilo
  FunSearch para domínios verificáveis, e o detector de paráfrase factual
  (ver piloto abaixo).
