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

*(a preencher com o varredor A: nucleus/typical/min-p/contrastive; anti-verossimilhança;
mirostat; 2025: conformative decoding, selective sampling; avaliação)*

- **Peeperkorn et al. (2025), "Mind the Gap: Conformative Decoding to Improve
  Output Diversity of Instruction-Tuned LLMs"** (arXiv 2507.20956). Mede a "lacuna
  de diversidade" criada pelo alinhamento (DPO é o passo que mais a reduz) e guia o
  modelo instruído pelo base, mais diverso; aumenta diversidade mantendo ou
  melhorando qualidade. *Liga-se a:* nosso base é o melhor descobridor; o base como
  propositor num portfólio.
- **Troshin et al. (2025), "Control the Temperature: Selective Sampling"**
  (arXiv 2510.01218). Alterna greedy e alta temperatura conforme um classificador
  de risco; melhora o trade-off qualidade–diversidade em raciocínio. *Liga-se a:*
  nosso sampler anti-provável (novidade só de superfície) — a versão "guiada" do
  mesmo botão.

## 2. Prompting e andaimes (estimular em inferência)

*(a preencher com o varredor A: brainstorming, personas, ToT criativo, pipelines de ideias)*

- **Doshi & Hauser (2024), Science Advances 10(28)**, "Generative AI enhances
  individual creativity but reduces the collective diversity of novel content".
  Ideias de LLM tornam histórias mais criativas (sobretudo para escritores menos
  criativos) e mais parecidas entre si. *Liga-se a:* interrupção = novidade local;
  documento = coleção; homogeneização é a outra face da mesma moeda.
- **Azad et al. (2026), "Ex Ante Evaluation of AI-Induced Idea Diversity
  Collapse"** (arXiv 2605.06540): três modelos de fronteira "abaixo da paridade"
  com humanos em aglomeração de ideias; mitigável por desenho do protocolo de
  geração.

## 3. Medir criatividade (e o que o juiz não vê)

- **Lu et al. (ICLR 2025, oral), "AI as Humanity's Salieri"** (arXiv 2410.04265):
  Creativity Index por atribuição contra a web; autores profissionais 66,2% acima
  dos LLMs; alinhamento reduz 30,1%. *Liga-se a:* novidade n-grama do nosso
  sampler; auto-cópia além do horizonte do juiz.
- **Zhang et al. (2025), NoveltyBench** (arXiv 2504.05228): 20 modelos geram muito
  menos diversidade que humanos; maiores da mesma família, menos diversos.
- **Schapiro et al. (2026), "Assessing the Creativity of LLMs: Testing, Limits,
  and New Frontiers"** (arXiv 2605.13450): testes humanos de criatividade não
  preveem ideação científica; propõem o DRAT (associação remota divergente), único
  preditor significativo.
- **Si, Yang & Hashimoto (2024)**, 100+ pesquisadores: ideias de LLM julgadas MAIS
  novas que as de humanos, um pouco menos viáveis. **Si & Hashimoto (2025), "The
  Ideation–Execution Gap"** (arXiv 2506.20803): 43 pesquisadores executaram as
  ideias (103 h em média); as notas das ideias de LLM caem muito mais — a lacuna
  se fecha na execução. *Liga-se a:* "o juiz de janela vê novidade, não valor"; o
  mundo (execução/verificador) é o juiz que falta.
- *(companion)* paper 1: texto injetado, auto-cópia além do horizonte, janelas vs todo.

## 4. Treino: RLHF/RLVR, auto-treino, diversidade, abertura

- **Kirk et al. (ICLR 2024)**, RLHF generaliza melhor que SFT e reduz muito a
  diversidade (por entrada e entre entradas) — trade-off generalização↔diversidade.
- **Yue et al. (2025), "Does RL Really Incentivize Reasoning Capacity in LLMs
  Beyond the Base Model?"** (arXiv 2504.13837; NeurIPS 2025): RLVR sobe pass@1;
  em k grande o BASE vence; a fronteira de raciocínio ESTREITA com o treino; RL
  realoca massa dentro do suporte do base. → **a nossa escada de adaptadores em
  outro domínio.** Seguimentos 2025–26: entropia colapsa (Cui et al.; "Revisiting
  Entropy…" 2511.05993), auto-jogo com síntese de problemas para sustentar pass@k
  (2508.14029), "diversity collapse como overtraining" + Bayesian Boundary Gating
  (Yuan et al. 2026, 2606.15455), PAEC, controle flexível de entropia (2602.09782).
- **Shumailov et al. (Nature 2024)**: colapso de modelo — caudas desaparecem
  (cedo: erros acumulam; tarde: eventos raros somem). *Liga-se a:* nosso random
  arm degrada; nosso attract/repel apagam caudas mesmo com filtro de valor.
- **Ismayilzada et al. (2025), Creative Preference Optimization** (arXiv
  2505.14442): otimização de preferência com sinais de novidade/diversidade/
  surpresa/qualidade (MuCE, 200k avaliações humanas); supera GPT-4o em avaliação
  humana e automática; valida em NoveltyBench. *Liga-se a:* treinar para a
  diversidade É possível — a pergunta é se compra fronteira ou só dispersão
  (nosso QD: dispersão de medíocres).
- *(a preencher com o varredor B: STaR/ReST/ReST-EM e saturação; QDAIF; ELM;
  novelty/curiosity RL; open-endedness — Hughes et al. 2024, OMNI, Voyager)*

## 5. Busca + verificador: onde a fronteira realmente moveu

- **FunSearch (Romera-Paredes et al., Nature 2024)**: cap sets e bin packing; milhões
  de amostras; propositor pequeno, não treinado; seleção por ilhas.
- **AlphaEvolve (Novikov et al., 2025; arXiv 2506.13131)**: 4×4 com 48 multiplicações
  escalares (primeira melhora sobre Strassen em 56 anos — para matrizes COMPLEXAS);
  em 50+ problemas, igualou 75% e melhorou 20% (13: 7 geometria elementar, 5 análise
  real, 1 combinatória; e.g., kissing number em 11-D 593 vs 592 = 0,36% do intervalo
  conhecido); ganhos práticos no Google (0,7% de recursos, 1% do treino do Gemini,
  23% num kernel). **Milhares** de amostras (vs milhões) com LLM de ponta e contexto
  rico. **E. Davis (2025), "Some comments on AlphaEvolve"**: ceticismo sobre a
  significância prática/teórica (multiplicações complexas; resultados matemáticos
  "arbitrários" vs os obtidos por teoria), sistema altamente configurável (quanto
  do resultado é o sistema "out of the box"?). *Liga-se a:* propositor largo +
  verificador duro; nosso S mostrou seleção saturando onde não há folga.
- *(a preencher com o varredor C: EoH/ReEvo/LLaMEA/LLM-SR; Eureka; AI Scientist e
  críticas; AI co-scientist; episódios de 2025–26 com problemas de Erdős e reações)*

## 6. Teoria e programas de pesquisa

- Boden (tipos de criatividade); Schmidhuber (progresso de compressão); novelty
  search (Lehman & Stanley 2011) e MAP-Elites (Mouret & Clune 2015); open-endedness
  (Hughes et al. 2024); "distância em bits" (nosso ENSAIO_BITS).
- *(a preencher)*

## 7. Síntese provisória — o que a comunidade aprendeu (e nós confirmamos)

1. Inferência compra variação e, com memória certa, integração; não compra
   progressão nem valor.
2. Treino por recompensa/auto-treino compra confiabilidade (pass@1, massa) e paga
   com diversidade/caudas (pass@k, colapso); filtrar por valor é necessário e não
   suficiente; objetivos de diversidade devolvem dispersão, não fronteira (por ora).
3. A fronteira que moveu veio de propositor LARGO + verificador DURO + muitas
   amostras + seleção — sem treinar o propositor. Implicação de desenho:
   portfólio (base para propor, adaptador para explotar), gastar em seleção.
4. Lacunas abertas: objetivos que preservem caudas de VALOR (não só dispersão);
   medir criatividade científica (DRAT); o papel do domínio com folga; consolidar
   sem colapsar (BBG-like: treinar só onde a fronteira ainda cresce).
