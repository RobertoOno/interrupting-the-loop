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
