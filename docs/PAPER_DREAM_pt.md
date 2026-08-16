# Onde mora a criatividade num modelo de linguagem: nem no sampler, nem no prompt — em interromper o loop

> Versão em português do rascunho principal (2026-08-16), tradução integral
> de `PAPER_DREAM.md`. Caderno de laboratório: `PLANO.md`. Números e
> figuras são os mesmos da versão inglesa; nomes de condições e de
> variáveis ficam em inglês porque são identificadores do código.

## Resumo (rascunho)

[[ABSTRACT_PT]]

## 1. Tese e programa

O insight humano não é resposta a um prompt estranho; ele nasce dentro de
um loop fechado de pensamento que se alimenta da própria saída — na
incubação, no devaneio, no sono — quando um desvio gerado espontaneamente
sobrevive à revisão crítica e é ligado de volta ao que veio antes. A
neurociência descreve três redes acopladas: a de modo padrão (geração
espontânea, recuperação de memória), a executiva (avaliação) e a de
saliência (o interruptor que decide o que merece atenção); pessoas mais
criativas mostram mais acoplamento entre as duas primeiras (Beaty et al.).
Construímos um análogo desse loop num modelo de linguagem e perguntamos,
com controles, quais das suas partes importam — e se as partes que nós e
os outros costumamos otimizar (decodificação, prompting) importam de fato.

## 2. Pilha de medição (compartilhada por todos os experimentos)

- **Gerador**: só modelos base (modelos instruct estão colapsados em modo):
  Qwen3-8B-Base, OLMo-2-13B (corpus público), Qwen3-30B-A3B-Base (MoE,
  53 tok/s), em 8 bits sobre Apple silicon via MLX, com um sampler em numpy
  que enxerga os logits completos.
- **Juízes**: Claude Sonnet 5 / Opus 5 via Bedrock, sempre de família
  diferente da do gerador, medianas de k amostras (k=3–5), rubricas com
  dimensões independentes de 0 a 10; rubrica "equivalente mais próximo +
  delta de novidade" para ideias; surpresa / conexão / coerência para as
  janelas do devaneio.
- **Calibração do instrumento** (§6): dispersão intra-janela de k
  julgamentos medida antes do uso; efeitos abaixo de ~1 ponto são
  declarados indetectáveis.
- **Novidade objetiva** onde disponível: contagens infini-gram contra o
  corpus de treino do OLMo-2.
- **Estatística**: ICs bootstrap sobre diferenças; unidade = janela ou
  semente.

## 3. Hipótese 1 — o sampler (Fase 1; detalhes em PAPER.md)

Método: nos passos cuja entropia cai numa banda calibrada, repontuar os
candidatos que passam pelo piso por `log P + λ·z(distância ao EMA do
contexto)`. Achados: (a) OLMo-2-13B, 3 prompts × 5 sementes, grade
totalmente pareada: novidade de 4-gramas 21.5% → 45.5% (λ=2), Δ bootstrap
pareado +24.0 pp [18.2, 29.5] (λ=1: +14.6 [7.9, 21.9]), monotônico em λ e
presente em cada prompt; P(bloco literal de ≥8 palavras do treino) 0.80 →
0.20 nos dois braços da máquina (uma redução de 4× declarada como taxa — o
"zero blocos" do piloto era uma célula, não a distribuição); custo de
coerência ~+1.2 ppl sob juiz de outra família, sem correlação com a
novidade dentro dos braços (Spearman +0.12). (b) O *teto* de entropia
(bifurcações de gênero) transfere entre famílias de modelo. (c) Três modos
de escape (recitação, colagem, paráfrase factual). O detector de recitação
(queda de entropia entre metades) é reportado descritivamente: no exp1 tem
AUC 0.71 para blocos de ≥8 palavras e precisão 0.33 no limiar 0.35, e
nenhuma taxa de falso positivo pôde ser medida porque o braço baseline não
tinha telemetria — um detector calibrado é trabalho futuro. **Limite**: em
busca verificada (bin packing, 8B e 30B, até 3.200 heurísticas
verificadas) o operador não se separa da amostragem plain — um nulo
delimitado. E no loop de devaneio (§5) o mesmo empurrão não produz
diferença em surpresa, conexão ou delta julgados. A novidade de superfície
é real e não sobe de nível.

## 4. Hipótese 2 — o prompt (PAPER_B.md, negativo)

Três braços de input (pedido típico / par de conceitos distantes / contexto
improvável composto) mais duas ablações (só fragmentos, só registro),
desenvolvidos pelo Opus 5, julgados pelo Sonnet 5 (k=3), n≈15/braço: o
prompt típico igualou ou superou todo braço improvável; dois foram
significativamente piores; a improbabilidade do input (distância semântica
kNN a 10k prompts reais, ou perplexidade) não se correlacionou com a
novidade julgada (|r| < 0.2). Um efeito piloto (n=8) não replicou. Inputs
improváveis vindos de fora são ruído.

[[SECTION_5_PT]]

## 6. O instrumento, medido

As mesmas 89 janelas, k=5, dois juízes: Opus 5 com dispersão 0.71 (notas
contínuas, resolução com ruído de ±0.7); Sonnet 5 com dispersão 0.27, mas
por dar zero em `connects_distant` quase sempre (uma régua que só lê "0" é
consistente). A rubrica de três dimensões tem dispersões de 0.45–0.70.
Consequência: juízes-LLM detectam efeitos ≥1–2 pontos (arcabouço vs nu,
saliência vs relógio) e não conseguem arbitrar efeitos de meio ponto
(empurrão vs plain) — por isso o nulo do empurrão é reportado como
"indetectável nesta resolução", não "ausente". Um limiar binário sobre um
juiz ruidoso é uma moeda: a mesma janela recebeu 5.24 numa noite e 4.48 na
seguinte.

[[SECTION_7_PT]]

## 8. Trabalhos relacionados

**Decodificação.** A amostragem por núcleo [holtzman2020curious] trunca a
cauda pouco confiável; a amostragem localmente típica [meister2023typical]
mira a surprisal humana; o min-p [nguyen2025minp] escala o truncamento com
a confiança do modelo e é exatamente o nosso piso de coerência; a
decodificação contrastiva [li2023contrastive] e o direcionamento estilo
PPLM [dathathri2020pplm] moldam a distribuição para perto ou para longe de
uma referência. Todos regulam a cauda; o nosso sampler a *corteja*, e
mostramos que isso compra só novidade de superfície. **Medição de
novidade.** O infini-gram [liu2024infinigram] e o Rusty-DAWG
[merrill2024rustydawg] tornam computável a novidade literal contra os dados
de treino; Saakyan et al. [saakyan2026death] mostram, com 8.618 anotações
de especialistas, que ~91% das expressões n-gram-novas do quartil superior
não são julgadas criativas — o nosso modo de escape por paráfrase factual e
o nulo do empurrão no nível das ideias são confirmações mecanísticas
independentes. **Busca verificada.** O FunSearch
[romeraparedes2024funsearch] e o AlphaEvolve [novikov2025alphaevolve]
acoplam um LLM a um avaliador duro; o nosso nulo em bin packing e o
arcabouço DREAM sugerem que a estrutura do loop, não o operador de
amostragem, é onde olhar em seguida. **Cognição.** Cognição criativa como
acoplamento das redes de modo padrão e executiva [beaty2016dynamics], com
regiões de saliência se acoplando primeiro [beaty2018robust]; criatividade
como conexão de conceitos semanticamente distantes [kenett2018semantic];
efeitos de incubação na resolução de problemas [sio2009incubation];
processamento preditivo [clark2013whatever]; sonhos como ruído
anti-sobreajuste [hoel2021overfitted]; a tríade novidade/surpresa/valor de
Boden [boden2004creative]; integração conceitual [fauconnier2002way]; busca
por novidade [stanley2015greatness]. O DREAM é uma engenharia explícita dos
três primeiros num loop de texto.

[[SECTION_9_PT]]

## 10. Reprodutibilidade

Tudo neste repositório (117 testes): núcleo do sampler, adaptador MLX,
monitor de saliência, motor do devaneio, juízes, cliente de novidade,
executores de experimento com execução noturna resumível e registro
térmico. A telemetria por passo, os textos e os julgamentos de cada
execução ficam em `runs/`; o registro datado de decisões em
`docs/PLANO.md`. Custo de juiz de todo o programa até aqui: ≈US$100.

## Referências

Ver `docs/references.bib` (as entradas marcadas [verified] foram conferidas
nas páginas do editor/arXiv em 2026-08-16; as marcadas [check] são obras
padrão a confirmar antes da submissão).
