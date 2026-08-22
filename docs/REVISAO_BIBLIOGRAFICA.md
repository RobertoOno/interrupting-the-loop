# Revisão bibliográfica — o que a comunidade tentou para tornar LLMs mais criativos e capazes de explorar a fronteira do conhecimento, e o que resultou

*Creative-machine, 2026-08-22 (v0.1, em construção). Objetivo: mapa por famílias de
abordagem, com o resultado medido de cada uma e a ligação com o que nós medimos
(paper 1, arXiv:2608.19893; paper 2 "Mass, Not Frontier", rascunho). Referências em
inglês; BibTeX reaproveitável em `paper2/references.bib` (a completar).*

## 0. O quadro em uma página

A literatura converge, por caminhos diferentes, para três fatos que o nosso
programa encontrou em miniatura:

1. **Alinhamento e treino por recompensa estreitam a distribuição.** RLHF melhora
   generalização e reduz diversidade (Kirk et al., ICLR 2024); RL com recompensa
   verificável (RLVR) eleva pass@1 mas o modelo BASE tem pass@k maior em k grande —
   o RL realoca massa dentro do suporte que o base já tinha (Yue et al., 2025;
   seguidos por Yuan et al. 2026 "overtraining", entre outros); alinhamento corta
   ~30% do Creativity Index (Lu et al., ICLR 2025); modelos maiores são MENOS
   diversos (NoveltyBench, 2025); treinar recursivamente nos próprios dados apaga
   as caudas (Shumailov et al., Nature 2024). → Nosso "massa, não fronteira" e
   "consolidar paga com as caudas" são a mesma lei medida com verificador.
2. **Estímulo em inferência compra novidade local e homogeneiza o coletivo.**
   Ideias de IA elevam a criatividade individual e reduzem a diversidade coletiva
   (Doshi & Hauser, Science Advances 2024; 2026: colapso de diversidade de ideias
   medido ex ante); decodificação pode devolver diversidade ao modelo instruído
   usando o base como guia (conformative decoding, 2025) ou trocando temperatura
   sob risco (selective sampling, 2025). → Nosso paper 1: variação barata, sem
   composição; nosso schema: integração sem progressão.
3. **A fronteira de verdade veio de busca + verificador com propositor LARGO,
   não treinado.** FunSearch (cap sets, bin packing; milhões de amostras),
   AlphaEvolve (13 de 50+ problemas melhorados; 4×4 em 48 multiplicações —
   complexas, como nota E. Davis; milhares de amostras com LLM de ponta); ideias
   de LLM julgadas mais novas que as de humanos (Si et al. 2024) perdem o
   diferencial quando executadas (Si & Hashimoto 2025, "ideation–execution gap").
   → Nossos S, V e C: seleção satura, verificador no prompt é imitado, o base não
   treinado é o melhor descobridor.

## 1. Decodificação e amostragem (novidade de superfície)

- **Holtzman et al. (ICLR 2020)**, nucleus: maximizar verossimilhança dá laços
  repetitivos; truncar a cauda não confiável dá texto longo julgado de alta
  qualidade e tão diverso quanto o humano. **Zhang, Duckworth, Ippolito &
  Neelakantan (2021)**, "Trading Off Diversity and Quality": primeira avaliação
  humana em larga escala do espectro qualidade–diversidade; a "armadilha da
  verossimilhança" (as sequências mais prováveis são ruins); decodificação é um
  **dial unidimensional** — nenhum amostrador escapa da fronteira. **Mirostat
  (ICLR 2021)**: armadilhas do tédio (repetição) e da confusão (incoerência);
  controle de surpresa por perplexidade evita ambas. **Typical sampling (Meister et
  al., TACL 2023)**; **ε/η-sampling (Hewitt et al., 2022)**: truncar = remover ruído
  de suavização — fidelidade, não novidade. **Contrastive search (Su et al., NeurIPS
  2022)** e **contrastive decoding (Li et al., ACL 2023)**: penalizar o que um modelo
  pequeno também diria ("anti-genérico") melhora coerência (preferido 2,6× sobre
  nucleus) — anti-amador, não anti-provável.
- **Min-p (Nguyen et al., ICLR 2025 oral)** — "qualidade+diversidade em alta
  temperatura" — e a crítica **"Turning Down the Heat" (2025, 2506.13681)**: dados
  omitidos/estatística incorreta; min-p não supera as linhas de base em qualidade,
  diversidade ou trade-off; no máximo benefício fraco em temperaturas onde o
  desempenho absoluto é pior. **Peeperkorn et al. (ICCC 2024), "Is Temperature the
  Creativity Parameter of LLMs?"**: temperatura correlaciona fracamente com
  novidade, moderadamente com incoerência — **temperatura não é um botão de
  criatividade**. **Chen & Ding (EMNLP 2023)**: GPT-4 guloso supera 96% dos humanos
  no DAT; amostragem sobe o DAT de modelos fracos com custo de estabilidade.
  **Arias et al. (COLING 2025), "Decoding Decoded"**: varredura grande — top-p 0,95 e
  T=1 aproximam o humano; beam colapsa (diversidade 12,8); hiperparâmetros importam
  mais que escala; nenhuma configuração rende "ideias novas", só menos repetição.
  **Shi et al. (EMNLP 2024)**: 13 métodos × 11 tarefas — nenhum vencedor universal;
  ganhos frágeis e dependentes de tuning.
- **Nagarajan, Wu, Ding & Raghunathan (ICML 2025 spotlight), "Roll the dice & look
  before you leap"**: em abstrações mínimas de criatividade aberta, o treino
  token-a-token é míope e memoriza; treino multi-token (sem professor, difusão) dá
  saída mais diversa/original; **"seed-conditioning" (ruído no prefixo) iguala ou
  bate temperatura** — o teto está no paradigma de treino/decodificação;
  aleatoriedade no prefixo > aleatoriedade por token. **Tan et al. (EMNLP 2024)**:
  trade-off probabilidade–qualidade em modelos alinhados — amostrar troca
  verossimilhança sob o prior pré-alinhamento por recompensa.
- **Linha 2025–26 "puxar de volta à entropia do base"**: conformative decoding
  (Peeperkorn et al., 2507.20956: o modelo instruído guiado pelo próprio base
  recupera diversidade; o DPO é o passo que mais a perde); EPIC/decodificação
  alinhada à entropia (Ahmed & Singh, jan 2026, 2601.01714); modulação calibrada por
  variância (jun 2026, 2606.22511); selective sampling (Troshin et al., 2510.01218).
  → O trabalho atual de decodificação trata o **colapso induzido pelo alinhamento**,
  não a criatividade em si. *Liga-se a:* o nosso sampler anti-provável (novidade
  n-grama 2×, nada em ideias) é um ponto desse dial; o **Cultural Alien Sampler
  (NeurIPS 2025 Creative AI)** é o mesmo desenho (tipicidade baixa sob guarda de
  coerência) — útil para diversidade, calado sobre valor.

## 2. Prompting e andaimes (estimular em inferência)

- **Brainstorm-then-select (Summers-Stay et al., AAAI-23 wkshp)**: gerar muitos e
  selecionar bate brainstorming simples no AUT. **Tree of Thoughts (Yao et al.,
  NeurIPS 2023)**: escrita criativa — coerência 7,56 vs 6,93 (CoT); novidade não
  medida. **Girotra et al. (Wharton 2023), "Ideas are Dimes a Dozen"**: ChatGPT-4
  supera estudantes de elite em qualidade média e variância de ideias de produto;
  a maioria das melhores ideias do pool veio do modelo — **o problema é dispersão,
  não média**. **Meincke, Mollick & Terwiesch (2024), "Prompting Diverse Ideas"**:
  pools do GPT-4 são menos diversos que grupos humanos; CoT dá a maior diversidade
  (próxima dos humanos); persona "Steve Jobs" ajuda pouco (números de fonte
  secundária). **LLM Discussion (Lu et al., COLM 2024)**: discussão multiagente com
  papéis bate baselines em AUT/Instances/criatividade científica. **Zhao et al.
  (2024; MIR 2025)**: TTCT modificado — LLMs fracos em originalidade, fortes em
  elaboração; colaboração multi-LLM sobe originalidade. **Wang, Huang, Shen & Uzzi
  (Nature Human Behaviour 2025/26)**: 9.198 humanos vs 215.542 observações de LLM
  — humanos um pouco acima na média e **muito acima na cauda direita**; personas
  "gênio" ajudam só até um limiar; outras engenharias de prompt mistas/negativas.
  **Agents' Room (Huot et al., DeepMind, ICLR 2025)**: decomposição por teoria
  narrativa melhora qualidade longa; novidade não é o alvo. **Verbalized Sampling
  (Zhang et al., 2025/ICML 2026)**: pedir uma DISTRIBUIÇÃO de respostas com
  probabilidades dá 1,6–2,1× (até 2–3×) de diversidade — um "repulsor do modo" em
  nível de prompt. **Mirowski et al. (FAccT 2024), "A Robot Walks into a Bar"**: 20
  comediantes — material brando/estereotipado; o achatamento por segurança derrota
  o apoio a especialistas.
- *Liga-se a:* a interrupção do paper 1 é um andaime mínimo (novidade local, sem
  composição); a memória esquemática é o andaime que compra integração;
  "gerar-muitos-e-selecionar" é a única receita que aparece em todas as seções — e
  sempre dentro da distribuição do modelo.

## 3. Medir criatividade — e os achados de homogeneização

- **Testes de pensamento divergente saturam**: Koivisto & Grassini (Sci Rep 2023):
  chatbots > humano médio, os melhores humanos > melhores respostas; Hubert, Awa &
  Zabelina (Sci Rep 2024): GPT-4 mais original/elaborado no AUT/DAT; Bellemare-Pepin
  et al. (2024/25; vs 100k humanos): acima da média, abaixo dos muito criativos;
  **Haase et al. (J. Creativity 2025), "Has the creativity of LLMs peaked?"**: 14
  modelos acima da média humana, mas **0,28% das respostas** na faixa dos 10%
  melhores humanos; sem melhora em 18–24 meses. **Nakajima et al. (EACL 2026,
  CDAT)**: no DAT os SOTA ficam abaixo de baselines não criativas; condicionando
  novidade à adequação, famílias menores são as mais criativas e as avançadas
  trocam novidade por adequação. **Schapiro et al. (2026)**: nenhum teste humano
  prevê ideação científica; DRAT.
- **Escrita vs especialistas**: **Chakrabarty et al. (CHI 2024), "Art or Artifice?"**:
  TTCW, 48 histórias, 10 escritores profissionais — histórias de LLM passam 3–10×
  menos testes; **nenhum juiz LLM correlaciona com especialistas**; **"Can AI
  writing be salvaged?" (CHI 2025)**: taxonomia de idiossincrasias (clichês,
  exposição desnecessária), GPT-4o/Claude/Llama indistinguíveis em qualidade;
  Gómez-Rodríguez & Williams (2023) e **"Pron vs Prompt" (Marco et al., EMNLP
  2024)**: contra um romancista premiado (5.400 notas), GPT-4 perde em toda
  dimensão; **escreve melhor a partir dos títulos do humano que dos seus**.
  Ismayilzada et al. (2024/25): 60 LLMs vs 60 pessoas — mais complexos no estilo,
  menos novos/surpreendentes/diversos. **Xu et al. (PNAS 2025), "Echoes in AI"**:
  elementos de enredo idiossincráticos se repetem entre gerações e entre modelos;
  humanos raramente ecoam. **Lu et al. (ICLR 2025)**: Creativity Index (ver quadro).
  **Si et al. 2024 / Si & Hashimoto 2025**: novidade julgada não sobrevive à
  execução.
- **Homogeneização (o dilema social)**: **Anderson, Shah & Kreminski (C&C 2024)**:
  usuários do ChatGPT produzem mais ideias, mais detalhadas e menos distintas entre
  si; menos senso de autoria. **Doshi & Hauser (Science Advances 2024)**: +8,1% de
  novidade, +9% de utilidade (até +26,6% "melhor escrita" para os menos
  criativos), histórias ~10,7% mais parecidas entre si. **Kumar et al. (CHI 2025)**:
  ganho de curto prazo, desempenho sem assistência PIOR depois. **Padmakumar & He
  (ICLR 2024)**: escrever com InstructGPT (não com GPT-3 base) reduz a diversidade
  entre autores. **Wenger & Kenett (PNAS Nexus 2026)**: 22 LLMs vs 100+ humanos —
  respostas de LLM muito mais parecidas entre si, mesmo controlando estrutura;
  **"Artificial Hivemind" (Jiang et al., NeurIPS 2025 D&B best paper)**: trocar de
  fornecedor não devolve diversidade; juízes premiam o modo. **Azad et al. (2026)**:
  colapso de diversidade de ideias medido ex ante. **2026**: "Narrative Flattening"
  (Li … Evans: OLMo Base→SFT→DPO→RLVR comprime variação temática/afetiva/
  estilística), "Where does output diversity collapse in post-training?" (OLMo-3:
  Think perde no SFT, Instruct no DPO; composição dos dados). → **O colapso está
  nos dados de pós-treino, não na arquitetura.**
- *Liga-se a:* o paper 1 inteiro é uma lição de instrumento (o juiz de janela não
  vê o texto injetado, a auto-cópia além do horizonte, o todo); a literatura
  confirma que juízes LLM não rastreiam criatividade de especialista e premiam o
  modo. Qualquer claim "mais criativo" precisa de: novidade condicionada à
  adequação, avaliação do TODO, cauda direita (não média), e — onde houver — o
  mundo como juiz (execução/verificador).

## 4. Treino: RLHF/RLVR, auto-treino, objetivos de diversidade, abertura

**4.1 Alinhamento e RL com recompensa: o que acontece com a distribuição.**
- **Kirk et al. (ICLR 2024)**, 2310.06452: RLHF generaliza melhor que SFT fora da
  distribuição (a vantagem cresce com o deslocamento) e reduz significativamente a
  diversidade por entrada; "colapso de modo". **Mohammadi (2024), "Creativity Has
  Left the Chat"** (2406.05587): Llama-2 alinhado vs base — entropia menor,
  embeddings em aglomerados apertados, **"estados atratores"**. **Murthy, Ullman &
  Hu (NAACL 2025)**, 2411.04427: populações simuladas de LLM — alinhado <
  instruído < humanos em diversidade conceitual.
- **Yue et al. (NeurIPS 2025, oral)**, 2504.13837: RLVR vence em pass@1, o BASE
  vence em pass@k grande em famílias/algoritmos/domínios; a cobertura "origina-se
  e é limitada pelo base"; seis algoritmos de RLVR semelhantes; destilação, sim,
  expande. **A réplica principal: ProRL (Liu et al., NVIDIA 2025)**, 2505.24864:
  >2k passos com controle de KL, resets da política de referência e tarefas
  diversas movem a fronteira (RL > base em todo pass@k, inclusive onde o base é 0%);
  ganhos maiores onde o base é fraco — duração e regularização importam (vale
  conferir se a v5 de Yue responde). **"The Invisible Leash" (Wu et al., NeurIPS
  2025)**, 2507.14843: RLVR é restrito ao suporte (não amostra soluções de prior
  zero), uma reponderação conservadora; na prática o encolhimento do suporte
  domina. **"Echo Chamber" (Zhao et al., COLM 2025)** + **"Spurious Rewards" (Shao
  et al., 2025)**: RL amplifica padrões do pré-treino (recompensa ALEATÓRIA dá +21,4
  no MATH-500 no Qwen2.5-Math; não no Llama/OLMo) — o teto de novidade é o
  pré-treino. **Karan & Du (ICLR 2026), "Reasoning with Sampling: Your Base Model
  is Smarter Than You Think"**, 2510.14901: amostragem "de potência" (MCMC) do base,
  SEM treino, ≈ GRPO no MATH500 e melhor fora da distribuição — a "capacidade" que
  o RL acrescenta já estava no base.
- **Mecanismo e remédios (2025–26)**: **Cui et al., "The Entropy Mechanism of RL"**
  (2505.22617): R = −a·e^H + b — o desempenho é gargalado pela exaustão de entropia;
  Clip-Cov/KL-Cov. **Wang et al. (Qwen, NeurIPS 2025)**: atualizar só os ~20% de
  tokens de alta entropia ("bifurcações") iguala ou supera o treino completo — a
  exploração mora em poucas bifurcações. Objetivos que restauram exploração:
  entropia na vantagem (Cheng et al.), **pass@k como recompensa** (Chen et al.,
  2508.10751), **exploração por resultado** (Song, Kempe & Munos: o RL reduz a
  diversidade até no conjunto de treino e a perda transfere para problemas não
  resolvidos; bônus UCB + penalidade de repetição recuperam pass@k), **"Rewarding
  the Unlikely"** (He, Fried & Welleck, EMNLP 2025: pass@80 = pass@256 do GRPO),
  SvS (síntese de variantes mantém entropia). **GX-Chen et al. (2025), "KL-Regularized
  RL is Designed to Mode Collapse"**: β baixo + recompensas verificáveis iguais
  especificam um alvo UNIMODAL por construção. 2026: **Yuan et al.** (colapso =
  sobretreino; Bayesian Boundary Gating), **Zhou** (inversão de pass@k em "prompts
  de fronteira" cujos traços raros nunca aparecem nos grupos de rollout),
  **UCPO**, **OPEFO (ACL 2026)**, **BODHI** (colapso de entropia é perda de
  ramificação SEMÂNTICA), **Matsutani et al. (ICLR 2026) "RL Squeezes, SFT
  Expands"**. → Em 2026 a inversão de pass@k é aceita e explicada; os remédios são
  portões/âncoras por problema, não "mais RL".
  *Liga-se a:* a nossa escada de adaptadores (attract → repel_anch = 100% ≡ best
  fit) é a inversão de pass@k medida com verificador de domínio; "âncora por
  problema" é o nosso "o base é o melhor descobridor".

**4.2 Laços de auto-treino e sua saturação.**
- **STaR (Zelikman et al., NeurIPS 2022)**: gerar → filtrar pela resposta →
  racionalizar → ajustar; ≈ modelo 30× maior no CommonsenseQA — elicita, não
  acrescenta. **ReST (Gulcehre et al. 2023)**: retornos decrescentes após poucos
  passos de Improve (sobreajuste). **ReST-EM (Singh et al., TMLR 2024)**: 3
  iterações (41,9) > 1 iteração com 3× dados (40,3); várias iterações sobreajustam.
  **Quiet-STaR (COLM 2024)**. **Self-Rewarding LMs (Yuan et al., ICML 2024)**: DPO
  iterativo com o modelo como juiz, 3 rodadas; os autores preveem saturação;
  **DIVE (Qin et al. 2025)**: auto-aperfeiçoamento iterativo perde diversidade;
  seleção de pares consciente de diversidade devolve +10–45% com qualidade igual.
- **Por que satura**: **"Mind the Gap" (Song et al., ICLR 2025)**, 2412.02674 — o
  auto-aperfeiçoamento é governado pela lacuna geração–verificação; **"The
  Sharpening Mechanism" (Huang et al. 2024)** — auto-aperfeiçoamento = afiar para o
  que o modelo já tem certeza. **SRT (Shafayat et al. 2025)**: auto-recompensa por
  voto majoritário iguala a recompensa verdadeira no início e depois "colapso
  súbito e completo" por hacking; **"Self-Improvement Can Self-Regress" (2026)**:
  pass@1 sobe em dezenas de passos e cai (às vezes a ~0); KL/EWC não evitam.
  **Absolute Zero (Zhao et al., NeurIPS 2025 spotlight)**: auto-jogo propor-e-
  resolver com executor de código como verificador, sem dados; **DéjàQ (2026)**:
  problemas verificáveis evoluídos por QD na zona de aprendibilidade. → O laço
  vive enquanto houver verificador externo E diversidade no propositor de
  tarefas.
- **Linha do colapso de modelo**: Shumailov et al. (Nature 2024: caudas primeiro);
  **Gerstgrasser et al. (COLM 2024)**: ACUMULAR (não substituir) dados limita o
  erro; **Guo et al. (NAACL 2024)**: diversidade lexical/sintática/semântica cai a
  cada recursão, pior em tarefas criativas; **Feng et al. (ICLR 2025)**: até
  verificadores imperfeitos evitam o colapso; **"When AI Reviews Its Own Code"
  (2026)**: sem portão colapsa rápido, portão humano retarda, auto-portão
  "carimba" (aceitação sobe, correção cai). → **As caudas morrem primeiro; só
  verificação exógena + acumulação mantêm a distribuição larga.** *Liga-se a:*
  nosso random arm degrada; nosso attract mantém largura por hash e perde caudas
  de valor; nossos vereditos confabulados = auto-portão que carimba.

**4.3 Objetivos de diversidade/novidade no treino.**
- **ELM (Lehman et al., OpenAI 2022)**, 2206.08896: mutação por diff + MAP-Elites
  gera centenas de milhares de "Sodaracers" ausentes do pré-treino e depois
  destila num LM condicional — a invenção acontece no laço QD externo; o LLM é o
  operador de variação. **QDAIF (Bradley et al., ICLR 2024)**: LM como mutador E juiz
  de qualidade/diversidade em MAP-Elites; cobre mais do espaço descritor com alta
  qualidade. **Recompensas de curiosidade/novidade**: red-teaming por curiosidade
  (Hong et al., ICLR 2024), Rainbow Teaming (2024), MERCI (ICLR 2026: pseudo-contagem
  em trajetórias de raciocínio). **"Forcing Diffuse Distributions" (Zhang,
  Schwarzschild, Carlini, Kolter, Ippolito, COLM 2024)**: diversidade treinável
  quando o conjunto válido é definível. **DivPO (Lanchantin et al., Meta 2025)**:
  pares "raro-mas-bom vs comum-mas-ruim": +45,6% diversidade de personas, +74,6% em
  histórias. **DDPO/DORPO (Chung et al., COLM 2025)**; **CrPO (Ismayilzada et al.,
  EMNLP Findings 2025)**. **DARLING (Li et al., Meta 2025)**: partição semântica
  aprendida × recompensa de qualidade em RL online — maior pass@1 E pass@k em
  matemática ("otimizar diversidade catalisa exploração"). **Polychromic Objectives
  (ICLR 2026)**: objetivo em nível de conjunto para PPO que refina o repertório
  diverso do pré-treino. → **A diversidade como termo de recompensa é a melhor
  alavanca do lado do treino hoje — e todos os ganhos são redistribuições do que o
  repertório pré-treinado contém.** *Liga-se a:* nosso QD devolveu dispersão de
  medíocres; DivPO/DARLING escolhem "raro-mas-BOM" — a nossa próxima versão, se
  houver, é essa.
- **Diagnósticos do modo**: NoveltyBench (COLM 2025); **"Artificial Hivemind" (Jiang
  et al., NeurIPS 2025 D&B best paper)**: homogeneidade intra e inter-modelos em
  26k prompts; modelos de recompensa/juízes penalizam respostas válidas-mas-
  diferentes; **Verbalized Sampling (Zhang et al., ICML 2026)**: a causa é o **viés
  de tipicidade** nos dados de preferência; VS dá 2–3× diversidade sem treino;
  **Hamilton & Mimno (2026)**: 11 palavras em 88,3% de 20k histórias de 4 modelos,
  rastreadas a dados de preferência compartilhados; **Sui (2026)**: 28 modelos com
  incerteza menor que escritores profissionais; remédios 2026: anotações no
  pré-treino (Springer et al.), restauração seletiva de camadas. → A causa converge
  para dados de pós-treino + juízes + KL-RL; os consertos ancoram no pré-treino.

**4.4 Abertura (open-endedness) com LLMs.**
- **POET/Enhanced POET (Wang, Lehman, Clune, Stanley, 2019/2020)**: co-evoluir
  ambientes e solucionadores. **Hughes et al. (ICML 2024, oral), "Open-Endedness is
  Essential for ASI"**: aberto = sequência de artefatos **nova E aprendível** para um
  observador; modelos de fundação treinados em dados fixos "não podem ser
  infinitamente novos"; o caminho são sistemas abertos construídos SOBRE eles.
  **Voyager (TMLR 2024)**: currículo automático + biblioteca de habilidades +
  auto-verificação no Minecraft, sem ajuste de pesos. **OMNI/OMNI-EPIC (ICLR
  2024/2025)**: LM como modelo de "interessante e aprendível"; EPIC gera ambientes
  e recompensas como código. **Darwin Gödel Machine (Zhang, Hu, Lu, Lange, Clune,
  ICLR 2026)**: arquivo de agentes auto-modificáveis; SWE-bench 20,0 → 50,0.
  **AC/DC (ICLR 2026)**: co-evolução de LLMs mesclados e tarefas sintéticas.
  **Picbreeder com VLMs (GECCO 2026)**: difere qualitativamente do arquivo humano.
  **Mutation Without Variation (GECCO 2026)**: ver §5.5. **Cultural Alien Sampler
  (Artiles et al., NeurIPS 2025 Creative AI)**: separa "coerência composicional" de
  "tipicidade cultural" — originalidade = baixa tipicidade sob guarda de coerência;
  mais diverso que GPT-4. *Liga-se a:* é exatamente o nosso sampler anti-provável
  com piso de coerência, reformulado — e com o mesmo teto que encontramos
  (superfície) enquanto a medida for diversidade e não valor.

*Ressalvas do varredor:* venue não confirmada/preprint para ProRL, DivPO, DARLING,
SRT, Pass@k Training, e a maioria dos itens de 2026; números do ProRL vêm do
resumo; conferir se a v5 de Yue et al. responde ao ProRL antes de citar como
debate resolvido.

## 5. Busca + verificador: onde a fronteira realmente moveu

**5.1 Os carros-chefe (linhagem DeepMind).**
- **FunSearch — Romera-Paredes et al., Nature 625 (2024)**: cap set de tamanho 512
  em n=8 (antes 496) e conjunto admissível de 237.984 → novo limite inferior da
  capacidade de cap sets 2,2202 (maior avanço em ~20 anos); bin packing online
  5,30%/4,19% de excesso vs 5,81%/6,06% do best fit. Propositor = PaLM 2/Codey
  **pré-treinado, nunca ajustado**; ~2,5 milhões de programas por corrida.
  *Liga-se a:* o nosso domínio, a nossa escolha de propositor cru.
- **AlphaEvolve — Novikov et al. (2025), arXiv 2506.13131**: 4×4 **complexas** em 48
  multiplicações (primeira melhora sobre Strassen nesse cenário em 56 anos); 50+
  problemas: ~75% igualados, ~20% melhorados (13; E. Davis: 7 de geometria
  elementar, 5 de análise real, 1 de combinatória; kissing number em 11-D 592 → 593
  = 0,36% do intervalo conhecido); infra Google: 0,7% de recursos, kernel +23% → 1%
  do treino do Gemini, FlashAttention até +32,5%. **Milhares** de amostras com LLM
  de ponta e contexto rico (vs milhões do FunSearch).
- **E. Davis (2025), "Some comments on AlphaEvolve"** (lido na íntegra): as
  multiplicações são complexas (valor prático limitado; recursivo dá O(n^2,792) vs
  O(n^2,37) teórico); resultados matemáticos "arbitrários" face aos obtidos por
  teoria (Ganzinov 2025; de Laat & Leijenhorst 2024); sistema altamente
  configurável — quanto do resultado é "out of the box" é desconhecido;
  indisponível fora do Google.
- **Georgiev, Gómez-Serrano, Tao & Wagner (2025), "Mathematical exploration and
  discovery at scale"** (arXiv 2511.02864; repositório público): AlphaEvolve em 67
  problemas — redescobre o melhor conhecido na maioria; melhora em alguns.
- **Dupont, Eisenberger, …, Alman, Vassilevska Williams, Balog (ago 2026)**, ω <
  2,371177 (antes 2,371339), arXiv 2608.16884: reformulação humana + otimização
  moderna; AlphaEvolve como passo de **refino** do otimizador. *Divisão de trabalho
  atual: humanos reformulam, o agente evolutivo pole.*
- **AlphaProof — Hubert et al., Nature (2025)**: RL sobre milhões de problemas
  auto-formalizados em Lean + RL em tempo de teste; 3 de 5 problemas não-geométricos
  da IMO 2024 (prata). **AlphaGeometry (Nature 2024) / AG2 (2025)**: 25/30 → 84% dos
  problemas de geometria da IMO 2000–2024; o ganho veio sobretudo de AMPLIAR a
  linguagem do domínio (66% → 88%), não do modelo. **AlphaTensor (Nature 2022)**:
  4×4 sobre GF(2) em 47 multiplicações — **sem LLM** (AlphaZero): o esqueleto
  verificador+busca carrega o resultado.
- **PatternBoost — Charton, Ellenberg, Wagner, Williamson (2024)**, arXiv 2411.00566:
  alterna busca local clássica com uma fase global em que um transformer é
  **treinado nas melhores construções achadas até ali** e reamostrado (treinado do
  zero, não um LLM pré-treinado); melhores soluções conhecidas em vários problemas
  extremais e um **contraexemplo a uma conjectura de 30 anos**. *Liga-se a:* é o
  braço "consolidar o que funcionou no propositor" — a nossa Bateria C — feito
  com um modelo pequeno e dedicado, e com busca local forte em volta.

**5.2 Busca evolutiva/heurística guiada por LLM.**
- **EoH — Liu et al., ICML 2024** (2401.02051): evolui "pensamentos" em linguagem +
  código; bate heurísticas manuais em bin packing com orçamento de consultas
  ordens de grandeza menor que o FunSearch. **ReEvo — Ye et al., NeurIPS 2024**
  (2402.01145): reflexões do LLM como "gradientes verbais"; SOTA/competitivo em 5
  tipos de algoritmo × 6 problemas. **LLaMEA — van Stein & Bäck, IEEE TEVC 2025**:
  otimizadores gerados batem CMA-ES/DE em baixa dimensão; vantagem encolhe fora do
  regime pontuado. **LLM-SR — Shojaee et al., ICLR 2025 (oral)** + **LLM-SRBench
  (ICML 2025)**: em 239 problemas resistentes a memorização, o melhor sistema
  chega a 31,5% de acurácia simbólica — a lacuna mais nítida entre "recupera uma
  lei conhecida" e "descobre uma nova". **Eureka — Ma et al., ICLR 2024**:
  recompensa como código evoluído; supera especialistas em 83% de 29 ambientes.
  **OPRO — Yang et al., ICLR 2024**: LLM como otimizador funciona em objetivos
  "de texto", não compete com solvers em combinatória dura.
- **ShinkaEvolve — Sakana AI (2025)**, arXiv 2509.19349 (aberto): SOTA em circle
  packing com **150 amostras** (bate a solução do AlphaEvolve); ganhos vêm de
  amostragem adaptativa de pais, **rejeição por novidade** e bandido sobre um
  ensemble de LLMs. *Liga-se a:* diversidade, não qualidade do modelo, é a
  restrição ativa. **LEVI (2026)**, arXiv 2605.09764: arquiteturas de busca
  melhores substituem LLMs maiores (3,3–6,7× menos orçamento). **Zarankiewicz
  (Bhan et al., mai 2026)**, arXiv 2605.01120, com OpenEvolve aberto: valores
  exatos inéditos de Z(11,21,3,3)=116, Z(11,22,3,3)=121, Z(12,22,3,3)=132 + 41
  limites novos — o paradigma já rende matemática verificada fora do Google.

**5.3 Agentes de ciência autônoma e suas auditorias.**
- **AI Scientist (Lu, Lu, Lange, Foerster, Clune, Ha, 2024)** e **v2 (2025)**: um de
  três papers passaria num workshop da ICLR 2025 (nota 6,33; retirado). Auditoria
  **Beel, Kan & Baumgart (2025)**, arXiv 2502.14297: revisão de literatura rasa,
  avaliação de novidade não confiável, incapaz de detectar as próprias falhas —
  passa a barra social, não a de correção. **Agent Laboratory (Schmidgall et al.,
  Findings EMNLP 2025)**: valor é throughput/custo (−84%), humano continua sendo o
  verificador. **AI co-scientist (Gottweis et al., 2025; Nature 2026)**: três casos
  com bancada; o caso cf-PICI ("pirataria de cauda") é **recapitulação, sob direção
  de especialistas, de um resultado não publicado** — não descoberta espontânea.
- **Si, Yang & Hashimoto (2024)** / **Si & Hashimoto (2025) "Ideation–Execution
  Gap"**: ver §3 — o resultado negativo mais importante desta literatura: novidade
  julgada não é proxy de descoberta. **MOOSE-Chem (Yang et al., ICLR 2025)**:
  hipóteses de 51 papers de 2024 redescobertas por modelos com corte em 2023 a
  partir de "inspirações" — evidência limpa de **recombinação do conhecido**.

**5.4 2025–26: problemas em aberto e o que se aprendeu.**
- **Episódio GPT-5/Erdős (out 2025)**: "10 problemas em aberto resolvidos" → Thomas
  Bloom (erdosproblems.com): "aberto" = ele desconhecia solução publicada; o modelo
  fez **busca bibliográfica eficaz**; claim recuado. Hipótese-padrão da comunidade
  desde então: **recuperação até prova em contrário**.
- **Bubeck et al. (nov 2025), "Early science acceleration experiments with GPT-5"**
  (2511.16072): quatro resultados matemáticos novos, "modestos", verificados por
  humanos, com humanos no circuito.
- **Feng, Trinh, Bingham et al. (DeepMind, jan 2026)**, "Semi-Autonomous Mathematics
  Discovery with Gemini" (2601.22401): 700 conjecturas "abertas"; 13 tratadas — **5
  soluções aparentemente novas, 8 eram soluções já publicadas** (~62% recuperação);
  os autores nomeiam o risco de "plágio subconsciente".
- **Erdős #728 (jan 2026)**: GPT-5.2 Pro + Aristotle, prova **formal em Lean**
  (2601.07421) — primeiro problema de Erdős tido como resolvido de forma autônoma;
  **#397** (≈30 anos) verificado por Terence Tao, que o chamou de "fruta mais
  baixa": problemas negligenciados, solúveis por técnica padrão, não a fronteira
  (relato de imprensa sobre posts no Mathstodon; não verificado na fonte).
  *O que converteu claim em aceitação foi o verificador (Lean).*

**5.5 Análises sistemáticas: por que funciona e onde quebra.**
- **Large Language Monkeys — Brown et al. (2024)**, 2407.21787: cobertura cresce
  log-linear com o número de amostras por 4 ordens de grandeza (SWE-bench Lite:
  15,9% com 1 amostra → 56% com 250); exige verificador de domínio — sem ele, a
  seleção estaciona muito abaixo da cobertura. **Massa vence fronteira só onde há
  verificador.**
- **Yue et al. (2025)**: base vence RLVR em pass@256 — suporte direto à escolha de
  propositor não treinado.
- **"Mutation Without Variation" (GECCO'26 workshop)**, 2606.05408: sem pressão de
  seleção, cadeias de mutação por LLM **colapsam em regiões atratoras** (em 87% das
  cadeias, >93% das mutações revisitam uma forma já vista; ciclos curtos e
  auto-laços dominam; mutação de subárvore em GP clássica não faz isso). *Liga-se
  a:* a nossa auto-cópia, os nossos poços — o propositor LLM é intrinsecamente um
  atrator; novidade tem de ser imposta de fora (ilhas, rejeição por novidade,
  resets).
- **Bin packing auditado duas vezes**: **Sim, Renau & Hart (EvoApplications 2025)**,
  2501.11411 — a maioria das heurísticas evoluídas por LLM **não generaliza**
  (especialistas estreitos, caros); **Herrmann & Pallez (2025/26)**, 2510.27353 —
  heurísticas legíveis mas opacas, alternativas humanas simples são mais
  eficientes e gerais; o avanço é do arcabouço de busca/avaliação, não do LLM.
  *Liga-se a:* a nossa escolha de domínio e a folga pequena; as nossas funções
  consolidadas são best-fit afiado.

**Leitura transversal (§5):** toda descoberta verificada desta literatura está
atrás de um **escore barato e checável por máquina**; onde o verificador é um juiz
(revisor LLM, nota de novidade, primeira impressão de especialista) o resultado
inverte na execução ou dissolve na auditoria. **A força do propositor não é o
gargalo; a diversidade das propostas é** (propositores não treinados por escolha;
RLVR encolhe pass@k; mutação por LLM colapsa em atratores; maquinário de novidade
compra ~3 ordens de grandeza de eficiência amostral). E os episódios de 2025–26
convergem para um número: 8 de 13 "soluções" do Gemini eram literatura; as de
GPT-5 em outubro, todas; os casos inequívocos são pequenos, verificados
formalmente e descritos por Tao como a cauda negligenciada, não a fronteira.

## 6. Teoria e programas de pesquisa

- Boden (tipos de criatividade); Schmidhuber (progresso de compressão); novelty
  search (Lehman & Stanley 2011) e MAP-Elites (Mouret & Clune 2015); open-endedness
  (Hughes et al. 2024); "distância em bits" (nosso ENSAIO_BITS).
- *(a preencher)*

## 7. Síntese — o que a comunidade aprendeu (2019–2026), e o que nós acrescentamos

1. **Decodificação é um dial, não uma porta.** Vinte anos de amostradores compram
   menos repetição e mais dispersão de superfície; temperatura não é criatividade;
   o único claim "criativo" de decodificação recente (min-p) está contestado; o
   trabalho de 2025–26 reconhece que está consertando o colapso do alinhamento
   (puxar o modelo de volta ao base), não criando novidade. *Nosso sampler: idem.*
2. **Prompting compra variação e dispersão bounded; a cauda direita humana não é
   alcançada.** Gerar-muitos-e-selecionar, CoT para variância, discussão
   multiagente, distribuições verbalizadas — tudo real, tudo dentro da distribuição
   do modelo; personas plateiam. *Nossa interrupção: variação local; nossa memória
   esquemática: integração; nenhuma progressão.*
3. **Medir é a metade do problema.** Testes de divergência saturam na média e
   falham na cauda; juízes LLM não rastreiam especialistas e premiam o modo;
   novidade julgada não sobrevive à execução; o colapso está nos dados de
   pós-treino. *Nosso paper 1 é uma contribuição exatamente aqui.*
4. **Treino por recompensa estreita por construção; auto-treino afia e satura;
   colapso de modelo apaga caudas.** RLHF/RLVR/KL-RL concentram massa; pass@k
   inverte; laços STaR/ReST saturam em 2–3 rodadas e, sem sinal exógeno,
   regridem; verificação + acumulação são o que mantém a distribuição larga.
   *Nossa Bateria C: massa −1,7 pp, caudas apagadas, consolidar sem filtro degrada
   — a mesma lei, com verificador de domínio e controle aleatório.*
5. **Objetivos de diversidade devolvem dispersão do repertório; "raro-mas-bom" é
   a fronteira do lado do treino.** DivPO, DARLING, CrPO, polychromic, QD; nosso QD
   devolveu dispersão de medíocres — o próximo passo óbvio é o par "raro-mas-BOM".
6. **Onde a fronteira moveu, o desenho foi sempre o mesmo: propositor LARGO (não
   treinado) + verificador DURO + muitas amostras + seleção com pressão de
   novidade.** FunSearch, AlphaEvolve, ShinkaEvolve, PatternBoost (com modelo
   dedicado), Lean nos Erdős; e a lição das auditorias: o mérito é do arcabouço,
   as heurísticas evoluídas não generalizam, mutação por LLM colapsa em atratores
   sem seleção. *Nossos S, V, C e N chegam ao mesmo lugar pelo caminho negativo.*
7. **Lacunas em aberto (onde valeria investir)**: (a) objetivos que preservem
   caudas de VALOR, não só dispersão (gating por problema tipo BBG; "raro-mas-bom";
   âncora no base); (b) portfólio propositor-cru + explotador consolidado +
   verificador, medido por taxa de "melhores que o conhecido" em domínios com
   folga; (c) medir criatividade científica (DRAT) e no TODO; (d) abertura de
   verdade: co-evoluir problemas e soluções (POET/OMNI/DGM) em vez de otimizar um
   objetivo fixo; (e) a peça ainda ausente em toda a literatura: **consolidar o que
   o mundo aprovou sem apagar o que o mundo ainda não julgou**.

*Este documento será revisado; itens marcados "a verificar" ou de fonte
secundária devem ser conferidos antes de citação formal. BibTeX parcial em
`paper2/references.bib`.*
