# Programa 3 — O intervalo da rota

*Documento de enquadramento, atualizado em 2026-09-08. Instrumento implementado;
v1/v2 sem margem, v3 e sensibilidade S16 com portões aprovados nos limites testados.
P3A principal e P3B ainda não executados.*

## Decisão de programa

Estado mais recente: S16 terminou e foi auditada. Sem/com ponte: 0/4 versus 4/4
em 8.192 tokens e 2/4 versus 4/4 em 16.384. Ambos os portões passam, mas o
ganho diminui e desaparece na família de invariante sob o limite maior.
Dez provas revalidadas; seis truncamentos sem submissão. Preparar produção/
transferência em diagnóstico separado, não admitir automaticamente a principal.
Registro: `docs/p3/SENSIBILIDADE_LIMITE_RESPOSTA_RESULTADOS_V1.md`.

Histórico v3: a calibração conceitual v3 terminou com baseline 1/4, oráculo 4/4
e ganho 3/4 em quatro pares válidos. Passou no portão pré-especificado. As três
baselines sem solução atingiram o limite da primeira resposta sem submissão: antes
de escalar, cabe uma sensibilidade separada a esse limite, sem reclassificar a v3.
Registro e evidência: `docs/p3/CALIBRACAO_CONCEITUAL_RESULTADOS_V3.md`. Ainda não é
teste de transferência, invenção, novidade estrutural ou mecanismos internos.

Histórico: a calibração Bedrock v2 terminou com 4/4 alvos resolvidos tanto
com quanto sem ponte, todos na primeira submissão. O portão não passou; não é resultado
contra transferência ou invenção. O próximo passo é redesenhar a escolha de intermediário
exigida pelos mundos, antes da amostra principal ou de nova bateria paga. Detalhes e
evidência: `docs/p3/CALIBRACAO_BEDROCK_V2.md`.

Dois protótipos locais desse redesenho já foram verificados: escolha de invariante
quadrático e escolha de representação não comutativa. Não são ainda mundos inéditos
nem calibração comportamental. Suas limitações e o portão antes de novas chamadas estão
em `docs/p3/PROTOTIPOS_CONCEITUAIS_V3.md`.

Etapa local seguinte: fontes relevante/sham, adaptações e gerador de instâncias de
desenvolvimento foram implementados e verificados. A revisão confirma o risco de
reconhecimento de famílias conhecidas; não preenche a exigência mais forte de novidade
do piloto principal. Naquele marco ainda não havia terceira calibração. Escopo, controles e
portões restantes: `docs/p3/FONTES_E_GERADOR_CONCEITUAL_V3.md`.

Em 05/09 foi preparada a última calibração pequena v3, com correções de equivalência
e exclusões verificadas antes do sorteio, mantendo modelo, interface, orçamento e
portão causal. Plano independente congelado antes da execução:
`docs/p3/CALIBRACAO_CONCEITUAL_V3.md`. Continua sendo uma checagem do instrumento em
famílias conhecidas; não satisfaz automaticamente a exigência de novidade do principal.

O Programa 3 deixa de perguntar como produzir mais variação dentro de um laço e passa a
perguntar **quem produz a rota que torna uma busca longa localmente verificável**. O objeto
central não é a prova final nem o melhor escore: é um lema, representação ou princípio
intermediário que reduz a distância entre o prior do propositor e o alvo.

A hipótese de trabalho é:

> Agentes escalam em profundidade quando recebem uma rota decomponível e feedback local
> exato. A lacuna aparece quando precisam inventar o intermediário que cria essa rota.

Chamamos essa lacuna de **intervalo da rota**: a diferença entre o que o mesmo agente
consegue concluir com uma ponte válida fornecida e sem ela, mantendo alvo, biblioteca,
verificador e orçamento constantes.

O programa será separado em dois estágios para não confundir transferência com invenção:

- **P3A — instrumento e transferência:** verifica se uma ponte válida causa ganho em alvos
  ocultos e se uma fonte estrutural relevante ajuda a produzir essa ponte. Este é o piloto
  descrito nos documentos atuais.
- **P3B — invenção de rota:** depois de P3A validar a medida, remove a rota análoga e exige que o
  agente proponha um intermediário não antecipado em sua entrada. Esse estágio terá desenho e
  pré-registro próprios; não será inferido retroativamente dos resultados de P3A.

## Por que o caso Fermat importa

O repositório `anthropics/fermats-last-theorem`, consultado em 2026-09-04, apresenta uma
formalização completa em Lean da rota Frey–Serre–Ribet–Wiles/Taylor–Wiles: 60.475 módulos,
29.511 teoremas e checagem pelo kernel do Lean, pelo `leanprover/comparator` e pelo kernel
independente nanoda. Os arquivos Lean foram produzidos por agentes sobre Mathlib e material
humano de código aberto. A rota matemática, porém, é conhecida e explicitada em
`PROOF-PATH.md`; o repositório publica um único endpoint consolidado, não as tentativas,
prompts, falhas ou decisões dos agentes.

Isso é um caso positivo extraordinário de **dedução verificada em escala**, não evidência
isolada de que o sistema inventou a rota. É precisamente o contraste de que precisamos:
comprimento não é o mesmo que distância criativa. Uma derivação pode ter dezenas de milhares
de nós e ainda assim ser atravessável quando cada obrigação local é verificável e a arquitetura
global está dada.

Fontes:

- <https://github.com/anthropics/fermats-last-theorem>
- <https://raw.githubusercontent.com/anthropics/fermats-last-theorem/main/PROOF-PATH.md>
- <https://raw.githubusercontent.com/anthropics/fermats-last-theorem/main/formalization.yaml>
- <https://raw.githubusercontent.com/anthropics/fermats-last-theorem/main/ATTRIBUTION.md>

## Continuidade com a série

O novo programa não abandona o `creative-machine`; ele torna seu resultado acumulado mais
preciso.

- Papers 1 e 4: intervenções aumentam variação julgada, mas não constroem progressão longa.
- Paper 2: consolidação move massa para o conhecido-bom, não o teto, e pode apagar caudas.
- Paper 3: busca verificada melhora quando recebe uma família executável, mas permanece presa
  à família de construção.
- Programa 2: a correspondência com uma fonte não superou o braço que via apenas o alvo; no
  problema famoso, o modelo reconstruiu o próprio prior.
- Caso Fermat: quando rota e verificador são densos, agentes conseguem executar uma derivação
  de escala extrema.

A pergunta comum deixa de ser “o modelo consegue trabalhar por muito tempo?” e passa a ser:
**o que acontece quando removemos exatamente a ponte que transforma o problema em trabalho
local?**

## Definições operacionais

**Mundo formal inédito.** Um pequeno projeto Lean gerado antes das chamadas, com tipos,
operações e regras parametrizadas que não correspondem a um teorema publicado. A semente do
gerador e os hashes são congelados antes da primeira execução.

“Inédito” aqui significa uma instância sintética anterior às chamadas e ausente do corpus
público, não uma contribuição matemática comparável a um novo teorema humano.

**Alvo visível.** O teorema que o propositor recebe e tenta provar.

**Alvos irmãos ocultos.** Dois teoremas não mostrados ao propositor, construídos a partir da
mesma estrutura causal. Eles impedem que uma reformulação específica do alvo visível seja
confundida com uma rota reutilizável.

**Lema-ponte.** Uma declaração Lean provada a partir do mundo-base, colocada em arquivo separado
da solução. Pode diferir da ponte do gerador; não é avaliada por semelhança textual.

**Utilidade causal da ponte.** Variação na taxa de solução dos alvos irmãos por um agente novo,
com versus sem o lema-ponte, sob o mesmo orçamento e sem acesso à conversa, à fonte ou à solução
do propositor.

**Intervalo da rota.** Ganho produzido pela ponte-oráculo sobre o braço sem rota. É primeiro uma
checagem do instrumento: se nem a ponte correta ajudar, o benchmark não mede o que pretende.

## Perguntas e hipóteses

1. **H1 — manipulação.** A ponte-oráculo aumenta a solução dos alvos irmãos em relação ao
   alvo-sem-rota. Sem esse efeito, o instrumento é inválido.
2. **H2 — transferência causal.** Uma fonte estrutural relevante produz pontes com utilidade
   causal maior que uma fonte estrangeira pareada, mas estruturalmente irrelevante.
3. **H3 — além do prior.** A fonte relevante supera também o braço que recebe apenas o alvo.
4. **H4 — solução não basta.** Resolver o alvo visível e produzir uma ponte útil nos irmãos são
   eventos distintos. O primeiro mede execução local; o segundo, abstração reutilizável.

H2 é a hipótese primária. H1 é um portão de validade; H3 e H4 são secundárias.

## O que já existe e onde fica nossa contribuição

Sistemas recentes já usam Lean como árbitro, agentes que planejam e repositórios de lemas.
`AlphaProof Nexus` testa busca formal em problemas abertos; `OpenProver` usa uma arquitetura
planner–worker–verifier; `MathlibLemma` produz e formaliza lemas ausentes da biblioteca. Portanto,
o Programa 3 não reivindicará ter inventado geração de lemas ou agentes Lean.

O recorte proposto é experimental: **isolar a informação de rota e medir causalmente a
reutilização de uma ponte em alvos ocultos**, com fonte relevante, sham pareado, alvo apenas e
ponte-oráculo dentro de mundos gerados e anteriores às chamadas.

Isso identifica seleção e transferência de rota em P3A. A reivindicação mais forte — invenção
de uma representação ou lema intermediário sem análogo fornecido — fica reservada a P3B.

Referências de comparação:

- AlphaProof Nexus: <https://arxiv.org/abs/2605.22763>
- OpenProver: <https://arxiv.org/abs/2607.09217>
- MathlibLemma: <https://arxiv.org/abs/2602.02561>

## Escopo inicial

### Encaixe da investigação interna (decisão com Roberto, 04/09)

P3A e P3B permanecem o eixo científico. A investigação interna será um módulo explicativo,
com protocolo, modelo aberto e orçamento próprios, apoiado em um contraste reproduzível.
Ela não é requisito para iniciar P3B: o portão necessário continua sendo a validade do
instrumento. Usar uma ponte no avaliador e criar uma ponte no propositor são mecanismos
diferentes; um resultado sobre o primeiro não explica automaticamente o segundo.

O Claude via AWS pode sustentar o estudo comportamental. Um modelo aberto em pod será
necessário para intervenções internas; qualquer contraste precisará ser reproduzido nele
antes de atribuir-lhe um mecanismo. Estados de um modelo não explicam outro por analogia.
Necessidade de modelos mais fortes, crédito adicional ou expansão material de orçamento
será comunicada a Roberto com estimativa antes da execução.

### Piloto comportamental

O primeiro piloto é um **teste do instrumento**, não uma demonstração de criatividade geral e
não uma tentativa de resolver matemática em aberto. Serão usados oito mundos pequenos de dois
moldes formais, com verificação barata e sem GPU. O modelo, o orçamento e as versões de
Lean/Mathlib serão únicos e fixados no pré-registro.

Os alvos cegos de otimização descritos em `docs/ALVOS_CEGOS.md` ficam preservados como uma
segunda etapa de validade externa. Só devem ser retomados se o instrumento formal distinguir
ponte fornecida, ponte transferida e ausência de ponte.

## Entregáveis

1. Gerador determinístico de mundos e seus metadados.
2. Verificador que fixa a declaração-alvo, proíbe atalhos e audita axiomas.
3. Harness de quatro braços com workspaces isolados e telemetria completa.
4. Avaliador causal em alvos irmãos ocultos.
5. Pré-registro e análise escritos antes dos resultados.
6. Pacote público contendo mundos, candidatos, logs, verificações e resultados nulos ou
   positivos.

## Limites de interpretação

- Sucesso em P3A pode mostrar produção e transferência de uma abstração reutilizável
  no recorte testado, não invenção sem análogo fornecido. Essa pergunta pertence a P3B;
  nenhum dos dois equivale automaticamente a descoberta matemática humana ampla.
- Fracasso pode localizar a ausência de transferência ou um instrumento ruim; o portão-oráculo
  separa esses casos.
- Nomes opacos reduzem recuperação textual, mas podem introduzir dificuldade artificial; não
  serão tratados como sinônimo de novidade.
- O kernel certifica a consequência formal, não a importância, naturalidade ou elegância da
  ponte. A utilidade nos irmãos é o nosso substituto causal mínimo.
