# Onde mora a criatividade num modelo de linguagem: nem no sampler, nem no prompt — em interromper o loop

> Versão em português do rascunho completo v1 (2026-08-16, noite), tradução
> integral de `PAPER_DREAM.md`. Caderno de laboratório: `PLANO.md`. Números e
> figuras são os mesmos da versão inglesa; nomes de condições e de
> variáveis ficam em inglês porque são identificadores do código.

## Resumo (rascunho)

De onde vem a novidade quando um modelo de linguagem gera texto sem
tarefa? Testamos três hipóteses com uma única pilha de medição (um modelo
base rodando localmente, juízes-LLM de outra família com medianas de k
amostras, ICs bootstrap e — para um braço — novidade literal contra o
corpus público de treino do próprio modelo). **(1) O sampler.** Um
decodificador anti-provável com banda de entropia, que empurra cada passo
em direção a tokens semanticamente distantes, reduz a taxa de blocos
literais de 8+ palavras do treino de 0.80 para 0.20 das gerações e
aproximadamente dobra a novidade de 4-gramas sobre a amostragem min-p
(21.5% → 45.5%; Δ pareado +24.0 pp, IC [18.2, 29.5]) a um pequeno custo de
perplexidade — mas essa novidade de superfície não sobe ao nível das
ideias: dentro de um loop de devaneio, o mesmo empurrão não produz
diferença mensurável em relação à amostragem plain em surpresa, conexão ou
delta de novidade julgados (1.335 julgamentos, 2 juízes, 3 rubricas).
**(2) O prompt.** Inputs compostos para ficarem longe de qualquer prompt
humano não superam um pedido típico quando um modelo forte os desenvolve
(Opus 5; n=15/braço, k=3): inputs improváveis são ruído. **(3) O loop.**
A geração contínua nua de um modelo base é morta: converge para os
atratores mais profundos do pré-treino (órbitas literais, rodapés de
site, gabaritos de prova) e fica lá (surpresa julgada 0.33/10). Um loop
fechado de devaneio construído sobre a arquitetura da cognição espontânea
— revisão acionada por saliência, esquecimento seletivo, reseed,
reencontro — dá vida a ele (surpresa 3.22; vs nu, δ de Cliff = +0.88, p ≈
10⁻¹⁶, 10 sementes, Opus 5 k=5). A ablação e uma segunda bateria (18
condições, 1.695 janelas julgadas, k = 5 cada) localizam o efeito em duas
operações e dizem do que elas são feitas. A *habituação* (não deixar o loop se
alimentar do próprio passado literal) ergue o fluxo de 0.33 para 1.70; a
*interrupção* — injetar periodicamente uma nova frase de partida sobre o
contexto preservado — ergue-o para 3.08 e carrega toda a conexão (1.08 →
3.15, δ = +0.75). A interrupção precisa levar para longe: injetar a
premissa ou o próprio passado do fluxo é tão ruim quanto não interromper;
uma volta só funciona como costura curta que abre uma frase nova. O seu
rendimento depende do fio que ela quebra e decai com a distância:
interromper a cada 75 tokens é morto (0.88), a cada 150 dá 3.08, e os 150
tokens depois de quebrar um fio de 300–900 tokens pontuam 5.3–5.9 com
coerência ~6 — o melhor texto do programa — antes de o fluxo se
reassentar em ~3.2; o melhor ritmo é uma quebra a cada ~300 tokens. A
saliência é boa leitora e mau metrônomo: seleciona as janelas que valem
julgamento, mas, como gatilho de interrupção, dispara raro e desigual
demais (2.18 vs 4.70 para a mesma costura num relógio casado). Dentro da
rede (residual em 13 camadas, logit lens), a geração nua congela em todas
as camadas, mais na superfície, e termina certa (entropia final 0.34); o
que o juiz chama de surpresa é partida na superfície com continuidade
profunda; e a interrupção que funciona mal move o estado profundo
(+0.01–0.03 de cosseno ao longo de uma injeção, sem retorno à premissa),
enquanto o esquecimento é um reencontro profundo com o começo (+0.2, e o
estado da própria premissa recuperado) que o juiz premia menos. A escada
nu → habituação → interrupção → arcabouço replica numa segunda família de
gerador (Qwen3-8B-Base) (Qwen3-8B-Base: 0.68 → 1.47 → 2.73, conexão
0.87 → 3.23, δ = +0.80). Neste sistema, a criatividade não
está no ruído injetado na decodificação, nem na estranheza do input, nem
num arcabouço cognitivo elaborado — está em **interromper o loop**: deixar
um fio se desenvolver e depois obrigá-lo a recomeçar em outro lugar, sobre
tudo o que ele lembra.

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

## 5. Hipótese 3 — o loop (DREAM)

**Arquitetura** (Drift–Review–Escalate–Accumulate–Memory: deriva,
revisão, escalada, acúmulo, memória): um único fluxo longo, sem tarefa,
EOS mascarado, a saída como próximo contexto; um monitor de saliência
sobre a telemetria do próprio fluxo (salto semântico, cristalização,
recorrência, estagnação, colapso de gênero na superfície) aciona um juiz
de outra família (coerência / conecta-distantes / delta); uma janela
aprovada dispara a escalada (regime estreito + retorno textual injetado à
premissa); a estagnação dispara um kick e, depois, uma mudança de assunto
com **esquecimento seletivo** (reconstruir a memória de trabalho: premissa
+ janelas guardadas + nova semente; as âncoras — regiões visitadas —
persistem); um termo opcional de ponte no sampler recompensa mover-se em
direção a regiões antigas e distantes.

**Calibração por atrator** (7 sondagens sem juiz): um modelo base deixado
sem tarefa recita a web — EOS precoce, ruminação erudita, órbitas literais
de 4 frases, rodapés de site, tabelas de tradução — cada uma mapeada e
transformada em mecanismo (máscara de EOS; estagnação+kick; habituação
graduada; detector de gênero; esquecimento). A dieta de pré-treino do
gerador foi a variável dominante: o OLMo-2 afunda em rodapés mesmo com
esquecimento; o Qwen3-30B deriva em prosa. **O contexto acumulado é o
poço**: com 3k tokens de boilerplate no cache, toda semente injetada era
puxada de volta em ~20 tokens; o esquecimento é o que deixa uma semente
pegar.

**Resultados.**
- Empurrão vs plain dentro do loop: nenhuma separação em nenhuma rubrica
  (§3).
- Saliência vs relógio: a revisão acionada por saliência supera a revisão
  por temporizador em surpresa e conexão (ICs positivos), a ⅓ do custo de
  juiz.
- **Arcabouço vs nu** (5 sementes, λ=0 em ambos, Opus k=5): surpresa 3.24
  ± 1.77 vs 0.47 ± 0.76 (IC [+1.99, +3.60]); conexão 1.48 ± 1.37 vs 0.27
  ± 0.63 (IC [+0.61, +1.87]); coerência 3.48 vs 2.60 (IC [−0.08, +1.74]);
  3/21 janelas do arcabouço com surpresa ≥5 e coerência ≥5, 0/30 nuas.
- **Ablação** (10 sementes × {arcabouço completo, só saliência, nu +
  reseed por relógio, nu}; 212 janelas, Opus k=5): arcabouço vs nu replica
  (surpresa 3.22 vs 0.33, δ = +0.88, p ≈ 10⁻¹⁶). Só-saliência chega a
  2.74 (arcabouço − só-saliência IC [−0.26, +1.24]). **Nu + reseed por
  relógio** — sem saliência, sem esquecimento, sem kicks — chega a surpresa
  3.08 (IC vs arcabouço [−0.50, +0.80]), conexão 3.15 (arcabouço abaixo:
  δ = −0.60, p ≈ 3×10⁻⁸) e coerência 4.78 (δ = −0.41), com 12/60 janelas
  julgadas surpreendentes *e* coerentes vs 8/50 no arcabouço e 0/60 no
  nu. O braço de reencontro nunca disparou (estava atrelado ao juiz
  binário aposentado), então a sua ablação é vazia aqui — a bateria 2 o
  testa diretamente (§5.1). **Leitura**: a interrupção carrega o efeito;
  o resto do arcabouço não paga o seu custo nesta resolução, e o
  esquecimento troca conexão por retorno à premissa. (O §5.1 corrige uma
  coisa: o braço nu também não tinha a habituação do arcabouço, o que
  explica parte da diferença.)
- **Trajetórias** (espaço de embeddings de sentença, PCA por semente, 10
  sementes): a geração nua tem raio explorado 0.18 e passo médio 0.14 —
  congela — terminando a distância 0.78 da premissa; o arcabouço tem raio
  0.51 (IC vs nu [+0.27, +0.40]) e volta a 0.57 da premissa (IC [−0.37,
  −0.06] vs nu); o reseed por relógio se espalha pelo espaço em saltos
  (48 pseudo-fechamentos) mantendo o contexto inteiro, que é de onde vem a
  sua vantagem em conexão.
- Qualitativo: o loop elabora os próprios achados depois do reencontro
  ("Everything that almost happened piled up inside her like snow falling
  sideways through open windowsills into rooms filled with silence
  instead of noise [...] She kept a notebook because sometimes almosts
  piled up too much to be ignored").

### 5.1 Do que é feita a interrupção (bateria 2)

A ablação deixou o efeito numa única operação e levantou quatro perguntas
sobre ela. A bateria 2 responde a elas com as mesmas 10 sementes, 4.500
tokens por célula, λ = 0, sem esquecimento, sem juiz no loop; as janelas
de cada célula são julgadas offline (Opus 5, k = 5, três dimensões) em
dois tipos de ponto de revisão — **corte** (os 160 tokens imediatamente
antes de cada injeção: o que o fluxo produziu até ser interrompido) e
**relógio** (uma grade uniforme de 150 tokens gerados, descartando pontos
a menos de 20 tokens de um corte) — com posições exatas de token (cada
célula guarda o seu fluxo de tokens e a posição de cada evento e
injeção).

- **Controle do confundidor.** Ao desenhar a bateria descobrimos que o
  braço `bare` da ablação rodava sem a habituação do arcabouço (uma
  penalidade de repetição graduada sobre os últimos 512 tokens, fator
  1.15), que todos os braços interrompidos tinham. A geração nua morre em
  órbitas *literais* ("Highly recommended." ×100, tabelas de números,
  gabaritos de prova) — exatamente o que uma penalidade de repetição
  desfaz — de modo que `bare` vs `bare + reseed por relógio` confundia
  interrupção com habituação. **`bare_habit`** (habituação, sem
  interrupção de nenhum tipo) separa as duas.
- **Conteúdo.** O mesmo relógio (150), texto injetado diferente: uma
  mudança de assunto neutra (o `bare_reseed` da ablação), uma costura de
  **reencontro** que pede ao fluxo que volte ao seu começo ("Which is
  exactly what the first line had meant, seen from here:"), a **própria
  premissa**, ou uma janela do **próprio passado** do fluxo (≥400 tokens
  atrás; antes de ter um passado, a premissa) — pensamento alimentando
  pensamento.
- **Timing.** A costura de reencontro injetada no **evento de saliência**
  (salto / cristalização / recorrência, sem juiz como porteiro) vs no
  relógio, e vs só-saliência sem injeção.
- **Frequência.** A mudança de assunto neutra a cada 75 / 150 / 300 / 600
  / 900 tokens (900 também com a costura de reencontro: os controles de
  frequência casada para a pergunta de timing).

**Resultados** (60 janelas por braço salvo indicação; Δ são ICs bootstrap
pareados por semente sobre as 10 sementes; δ de Cliff e Mann–Whitney
sobre janelas).

- **Habituação e interrupção são duas operações, e as duas importam.** Nu
  0.28 → nu + habituação **1.70** (surpresa Δ +1.42 [+1.12, +1.72];
  conexão 0.20 → 1.08; coerência 2.06 → 4.08) → nu + habituação + reseed
  por relógio **3.08** (Δ +1.38 [+0.92, +1.92] sobre a habituação
  sozinha). A habituação remove as órbitas literais e compra cerca de
  metade do ganho de surpresa; a interrupção compra a outra metade e
  **toda a conexão** (1.08 → 3.15, Δ +2.07 [+1.63, +2.57], δ = +0.75, p ≈
  5×10⁻¹³) e a coerência (4.08 → 4.78). O arcabouço completo sobre a
  habituação sozinha: surpresa +1.49 [+0.80, +2.19] (pareado +1.80
  [+0.97, +2.75]), conexão +0.55 [+0.06, +1.10]. A manchete da ablação
  sobrevive corrigida: não "só a interrupção", mas
  "não deixe o loop comer o próprio passado literal, e interrompa-o" — com
  o efeito de conexão pertencendo à interrupção.
- **A interrupção precisa levar para longe.** Com o mesmo relógio (150),
  uma mudança de assunto neutra e uma costura de reencontro ficam
  próximas: 3.08 / 3.15 / 4.78 vs 2.68 / 3.64 / 4.72 (surpresa / conexão
  / coerência; a costura troca alguma surpresa por conexão, Δ conexão
  +0.49 [−0.09, +1.07], não significativo). Injetar a **própria premissa**
  (1.14 / 1.04 / 3.18) ou uma janela do **próprio passado** do fluxo (1.42
  / 1.52 / 3.06) é tão ruim quanto não interromper — todo IC pareado vs a
  mudança neutra exclui zero (conexão −2.11 [−2.83, −1.46] e −1.63 [−2.37,
  −0.91]; coerência −1.60 e −1.72; δ ≈ −0.6 a −0.7). Qualitativamente, a
  injeção do próprio passado *reforça* o atrator em que o fluxo estiver
  (um poço de gabarito de prova recebeu de volta as suas próprias
  questões). Uma volta só funciona como costura curta que ainda abre uma
  frase nova; uma volta literal fecha o loop. (Janelas que terminam antes
  de 100 tokens gerados — o fragmento de dois tokens antes do primeiro
  corte de relógio — são excluídas de todas as tabelas da bateria 2; 73
  janelas assim, surpresa média 0.95. Aplicada à bateria de ablação, a
  mesma regra tira 10 janelas do nu e 3 do arcabouço: nu 0.33 → 0.28,
  arcabouço 3.22 → 3.19, nada mais muda; os números da ablação acima são
  como julgados.)
- **Timing: a saliência é boa leitora e mau metrônomo.** A costura de
  reencontro injetada nos eventos de saliência (salto, cristalização,
  recorrência; 1–9 por célula, mediana ≈5) torna as *janelas de evento*
  melhores do que só-saliência sem injeção (3.92 / 2.99 / 3.75 vs 2.63 /
  1.39 / 3.71; conexão Δ +1.6) — mas o *fluxo* que ela produz é pobre:
  janelas uniformes 2.18 / 1.68 / 3.93, contra **4.70 / 3.48 / 5.50** para
  a mesma costura num relógio de frequência casada (a cada 900 tokens;
  surpresa Δ +2.02 [+1.62, +2.44] pareado por semente, coerência +0.78
  [+0.40, +1.15]) e 5.48 / 2.87 / 5.95 para uma mudança neutra a cada 900
  (45/60 janelas surpreendentes *e* coerentes — a melhor célula do
  programa). Os eventos de saliência selecionam bons momentos para olhar,
  e é por isso que a revisão acionada por saliência venceu a revisão por
  relógio antes (§5, dream_def); mas como gatilho de interrupção eles
  disparam de forma desigual e rara, deixando fluxos presos por milhares
  de tokens. A saliência deve decidir *onde olhar*, não *quando
  interromper*.
- **Frequência: o rendimento de uma interrupção depende do fio que ela
  quebra, e decai com a distância dele.** Com a mudança neutra a cada 75
  tokens o fluxo está morto (surpresa 0.88, δ = −0.83 vs 150): nada tem
  tempo de se desenvolver. A cada 150: 3.08. A cada 300, 600 e 900, as
  janelas que terminam até ~160 tokens *depois* de uma interrupção pontuam
  **5.28 / 3.35 / 5.95**, 5.40 / 3.20 / 5.65 e 5.90 / 2.80 / 6.10
  (surpresa / conexão / coerência; n = 40, 20, 40) — os maiores valores do
  programa, com 34/60 das janelas iniciais de 300 julgadas surpreendentes
  *e* coerentes (12/60 a 150) — enquanto janelas mais fundas no segmento
  voltam a ≈3.2–3.3 de surpresa e ficam lá (300: 3.29 / 2.99 / 6.00; 600:
  3.24; 900: 3.20). A mesma forma de janela (uma quebra mais 150 tokens de
  desenvolvimento) pontua 3.08 quando o fio quebrado tinha 150 tokens e
  5.3–5.9 quando tinha 300–900: a surpresa precisa de um fundo
  desenvolvido para quebrar. Ponderando as duas fases pela sua fração do
  fluxo (160/período), o período 300 dá o melhor fluxo — 4.35 / 3.18 /
  5.97 — contra 3.82 / 2.69 / 5.52 (600), 3.68 / 2.43 / 5.35 (900), 3.08 /
  3.15 / 4.78 (150) e 0.88 / 1.35 / 3.15 (75); a conexão cai conforme os
  segmentos se alongam. O ritmo do loop é: deixar um fio se desenvolver
  por algumas centenas de tokens, depois quebrá-lo para longe.

### 5.2 Uma segunda família de gerador

As quatro condições que carregam o argumento, rodadas de novo no
Qwen3-8B-Base (denso, 36 camadas; as mesmas 10 sementes, 4.500 tokens,
λ = 0, julgadas offline como na bateria 2). A escada replica com a mesma
forma e valores um pouco mais baixos: nu 0.68 / 0.38 / 3.45 (surpresa /
conexão / coerência; 110 janelas) → nu + habituação **1.47** / 0.87 / 3.93
(surpresa Δ +0.78 [+0.45, +1.13] pareado por semente) → nu + habituação +
reseed por relógio **2.73** / **3.23** / 4.42 (Δ +1.26 [+0.52, +2.14] sobre
a habituação; conexão Δ +2.37 [+1.68, +3.12], δ = +0.80, p ≈ 10⁻¹⁴) ≈
arcabouço completo 2.73 / 1.53 / 4.30 (146 janelas; conexão Δ +0.66
[+0.27, +1.07] sobre a habituação, de novo abaixo do reseed por relógio
simples). Numa segunda família, a habituação compra parte da surpresa, a
interrupção compra o resto e toda a conexão, e o arcabouço elaborado não
acrescenta nada sobre a interrupção simples.

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

## 7. Dentro da rede

Juízes e embeddings de sentença veem o texto; o residual do próprio
modelo vê a computação. Passamos de novo cada fluxo terminado pelo gerador
(uma única passada com KV cache; posições exatas de token) e capturamos o
residual em 13 camadas (uma a cada 4 das 48 do Qwen3-30B-A3B; uma a cada
3 das 36 do Qwen3-8B), com média sobre janelas de 64 tokens (passo 32),
mais um logit lens em cada camada capturada (a norma final e o
desembutimento aplicados ao estado intermediário). Três perguntas:

- **H1 — onde o fluxo congela?** Geometria da trajetória por camada dos
  vetores de janela (passo médio entre janelas consecutivas, raio
  explorado), por condição; e a **camada de compromisso** do logit lens —
  a camada capturada a partir da qual o token top-1 não muda mais — como
  medida de quão cedo a rede decidiu.
- **H2 — o movimento de que camada prediz a surpresa julgada?** Para cada
  janela julgada, a sua novidade na camada *l* (distância de cosseno entre
  o estado médio da janela e o estado médio de tudo o que veio antes) e o
  seu passo local (vs os 160 tokens anteriores); Spearman com a surpresa
  julgada, agregada e dentro de cada condição.
- **H3 — a que profundidade chega uma interrupção?** Distância de cosseno
  entre os 64 tokens antes de uma injeção e os 64 depois dela (pulando o
  texto injetado), por camada, menos o mesmo em posições aleatórias; e a
  mudança na similaridade com o estado da própria premissa (depois −
  antes) — se um reencontro traz a rede de volta ao seu começo na sua
  própria representação, e a que profundidade.

**Resultados** (bateria de ablação, 40 células, Qwen3-30B-A3B; vetores de
janela centrados pela média por camada antes da geometria de cosseno;
bateria 2 e família 8B abaixo).

- **H1 — o congelamento está em toda parte, e é mais fundo na
  superfície.** O passo médio da geração nua entre janelas consecutivas é
  de um terço a um quarto do de qualquer condição interrompida em todas as
  camadas (0.06 → 0.03 vs 0.20–0.28 → 0.05–0.08 da camada 0 à 47); o seu
  raio explorado é 0.13 nas camadas de entrada contra 0.42–0.53, e a
  diferença estreita com a profundidade mas nunca fecha (0.24 vs 0.33–0.34
  na camada 47, ICs disjuntos). As três condições interrompidas são
  geometricamente parecidas dentro da rede; o que as separa é o que o juiz
  lê. O logit lens acrescenta uma torção: na geração nua o token top-1 se
  estabiliza *mais tarde* (índice médio de compromisso estável 11.12
  [11.04, 11.25] de 12 vs 10.88–10.96) enquanto a distribuição final é
  muito mais confiante (entropia final 0.34 vs 0.42–1.08) — a assinatura
  da cópia, uma computação de camadas tardias que termina certa. Dentro
  das células nuas, as janelas julgadas mais surpreendentes são as que se
  comprometem mais cedo (ρ = −0.54, p ≈ 5×10⁻⁵) e com mais entropia (ρ =
  +0.50).
- **H2 — o que o juiz chama de surpresa é partida na superfície com
  continuidade profunda.** Agregando as condições, a novidade da janela
  julgada em relação a tudo o que veio antes se correlaciona com a
  surpresa julgada nas camadas de entrada (ρ = +0.47 na camada 0) e nada
  no topo (−0.04 na camada 47) — mas o número agregado é carregado pelo
  contraste nu/interrompido. Dentro das condições interrompidas o sinal
  inverte com a profundidade: o passo local na camada 0 se correlaciona
  positivamente com a surpresa (só-saliência +0.46, arcabouço +0.23) e na
  camada 47 negativamente (−0.34, −0.14); a novidade em relação a todo o
  passado é negativa em profundidade (só-saliência −0.53 na camada 47,
  arcabouço −0.35). A surpresa julgada sobe com a mudança lexical e *cai*
  com o afastamento do estado profundo em relação ao próprio passado do
  fluxo: as janelas que o juiz premia são novas na superfície e contínuas
  por baixo. Uma entropia final mais alta também prediz surpresa dentro
  das condições (só-saliência ρ = +0.47, p = 0.004).
- **H3 — a interrupção que funciona mal toca o estado profundo.** Ao longo
  de um reseed do arcabouço *com esquecimento* (contexto reconstruído a
  partir da premissa), o estado 64 tokens depois da injeção difere do
  estado anterior em +0.09 (camada 4) crescendo até +0.21 (camada 40) de
  cosseno além do controle em posições aleatórias, e a sua similaridade
  com o estado da própria premissa sobe +0.09 → +0.20 com a profundidade:
  o esquecimento é um reencontro profundo com o começo, na representação
  da rede. Ao longo de um reseed por relógio *sobre contexto preservado* as
  mesmas medidas são +0.01–0.03 e ≈0 em todas as camadas — e essa é a
  interrupção que o juiz mais premia (§5). Surpresa e conexão julgadas não
  são deslocamentos representacionais profundos; são partidas de
  superfície sobre um contexto profundo intacto, que é também por que esse
  braço mantém a maior conexão. Ao longo do fluxo, a similaridade com o
  estado da premissa tem forma de U na profundidade (≈0.9 na camada 0,
  ≈0.45–0.53 na camada 16, subindo de novo no topo) e é ordenada na camada
  do topo: arcabouço 0.85 > só-saliência 0.79 > reseed por relógio 0.67 >
  nu 0.55 — o "retorno à premissa" do arcabouço nos embeddings de sentença
  é um fenômeno da camada do topo.

**Bateria 2 (100 células) e família Qwen3-8B (40 células).**
- *A profundidade da interrupção escala com o fio que ela quebra, não com
  o que é injetado.* No período 150 todo conteúdo move o estado profundo
  em +0.01–0.02 além do controle (costura de reencontro, premissa, próprio
  passado igualmente); a 300, +0.02–0.04; a 600, +0.04–0.075; a 75, ≈0.
  Quanto mais longo o segmento, mais longe o estado derivou e maior o
  salto que a injeção produz — a contraparte interna à rede do resultado
  de frequência (§5.1). A costura por saliência é a única injeção na
  escala de 150 tokens que move o estado profundo de forma confiável
  (+0.02 → +0.05) e o traz em direção à premissa (+0.02 → +0.03 em todas as
  camadas), e é também o braço cujo fluxo o juiz avalia pior: movimento
  profundo e qualidade julgada se dissociam aqui também.
- *Geometria por conteúdo.* Os braços mortos são os congelados: injetar a
  premissa ou o próprio passado dá raios explorados de 0.20–0.33 (como nu
  + habituação, 0.35–0.42) contra 0.42–0.51 para a costura de reencontro e
  0.50–0.61 para os períodos 300–600 — os maiores do programa; o fluxo do
  relógio de 75 fica em 0.25–0.40 com uma distribuição final muito
  confiante (entropia 0.24, a mais baixa de qualquer braço interrompido):
  um fluxo cortado a cada 75 tokens reentra num poço entre os cortes.
  Sobre as 668 janelas julgadas da bateria 2, o movimento na camada 0
  prediz a surpresa julgada dentro de todas as condições (ρ +0.3 a +0.6),
  e uma entropia final mais alta a prediz em toda parte (ρ +0.3 a +0.6):
  confiante é sem surpresa.
- *Segunda família (Qwen3-8B-Base, 36 camadas, uma a cada 3 capturada).*
  H1 replica: raio do nu 0.14 → 0.16 (camada 0 → 35) contra 0.46 → 0.23
  (reseed por relógio) e 0.54 → 0.32 (arcabouço), com nu + habituação no
  meio (0.33 → 0.23); o nu tem a distribuição final mais confiante
  (entropia 0.18 vs 0.35–0.96). H3 replica a dissociação: reseeds com
  esquecimento movem o estado profundo em +0.03 → +0.10 (pico no meio da
  rede) e o trazem em direção à premissa (+0.10 na camada 21); reseeds por
  relógio sobre contexto preservado o movem em +0.01–0.03 sem retorno. A
  ordenação da camada de compromisso *não* replica (no 8B o arcabouço se
  compromete mais tarde, 10.35 vs 9.45–9.92) — reportamos o compromisso
  tardio da geração nua como observação no 30B, não como lei.

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

## 9. Limitações e próximos passos

Dez sementes; duas famílias de gerador para o loop (Qwen3-30B-A3B e
Qwen3-8B, ambas Qwen3 — uma terceira família, OLMo-2, afunda em rodapés e
não passou pelas baterias); juízes-LLM (Opus 5, calibrado, não humano — um
pacote de avaliação humana cega com 42 janelas de 7 condições está pronto
e aguarda o avaliador); só sementes narrativas em inglês; a amostra
julgada de cada célula é de 6 janelas por tipo, espalhadas uniformemente,
e os braços por saliência são julgados tanto em momentos selecionados
quanto numa grade uniforme (ambos reportados); a análise do residual é
correlacional e usa janelas com média em 13 camadas, não atenção nem
intervenções causais. Os resultados de frequência e conteúdo dizem do que
é feita uma boa interrupção em um sistema; se o ritmo (~300 tokens) e a
regra "leve para longe, depois deixe voltar sozinho" valem para outros
gêneros e para tarefas com verificador é a próxima pergunta — a fusão para
a qual o programa aponta: um loop interrompido sobre um *problema*, com um
verificador no lugar do juiz. Também a seguir: um monitor de saliência
usado como leitor (que janelas guardar) dentro de um loop movido a relógio,
a combinação que esta bateria recomenda; e a validação humana do juiz.

## 10. Reprodutibilidade

Tudo neste repositório (117 testes): núcleo do sampler, adaptador MLX,
monitor de saliência, motor do devaneio, juízes, cliente de novidade,
executores de experimento com execução noturna resumível e registro
térmico. A telemetria por passo, os textos e os julgamentos de cada
execução ficam em `runs/`; o registro datado de decisões em
`docs/PLANO.md`. Custo de juiz de todo o programa até aqui: ≈US$120.

## Referências

Ver `docs/references.bib` — todas as entradas conferidas na página do
editor/arXiv (2026-08-16/17).
