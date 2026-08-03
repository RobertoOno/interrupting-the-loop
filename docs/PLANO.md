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

## Métricas

- **Coerência**: perplexidade sob um segundo modelo.
- **Novidade**: distância a corpus; para OLMo, consulta infini-gram ao Dolma.
- **Valor**: juiz (LLM forte ou verificador programático) — o gargalo real.
- **Telemetria por passo**: entropia da distribuição, rank do token escolhido,
  distância semântica percorrida, P(token escolhido). É o que permite *ver*
  o instrumento enquanto toca.

## Roadmap

- [ ] **1. Esqueleto** (nuvem): pacote Python; núcleo do sampler (recebe
  logits + embeddings → token) com anti-provável adaptativo por entropia
  (parâmetros: λ, piso de coerência, gatilho de entropia); métricas;
  telemetria; testes com distribuição sintética; adapter `mlx-lm` pronto.
- [ ] **2. Primeira execução** (Mac): Qwen3-8B-Base; calibrar λ, piso,
  gatilho; sentir onde o texto quebra.
- [ ] **3. Harness de experimentos**: varreduras de parâmetros, logging
  estruturado, comparação lado a lado com decodificação normal.
- [ ] **4. OLMo-2** + métrica de novidade via infini-gram.
- [ ] **5. Fase 2**: blending conceitual via API (pares distantes por
  embeddings → costura → juiz).
- [ ] **6. Loop evolutivo**: seleção dos desvios sobreviventes; nos domínios
  verificáveis (matemática/código), verificador programático estilo FunSearch.
