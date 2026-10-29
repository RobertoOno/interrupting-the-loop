# Programa 3 — Especificação do gerador de mundos formais

*Especificação técnica v0.4, 2026-09-04. Núcleo e executor comportamental implementados;
calibrações Codex v1 e Bedrock v2 encerradas, sem passagem do portão comportamental.*

Adendo de desenvolvimento v3: um gerador independente (`conceptual_generator.py`)
agora produz instâncias de invariante quadrático e representação não comutativa, com
fontes e adaptações verificadas. Ele só emite pacotes de desenvolvimento, nunca mundos
elegíveis para calibração/principal; não altera o gerador congelado descrito abaixo.
Novas instâncias dessas famílias conhecidas não estabelecem novidade estrutural.
Especificação e revisão: `docs/p3/FONTES_E_GERADOR_CONCEITUAL_V3.md`.

Continuação de 05/09: `calibration_worlds_v3.py` acrescenta preparação separada de
calibração, sem modificar esse gerador de desenvolvimento. Corrige a equivalência
de todos os inícios antigos por alcançabilidade e o esgotamento do primeiro irmão de
comprimento 6. As exclusões são anteriores ao sorteio e aos modelos; a distinção de
componentes conservadas é provada, mas o filtro de palavras continua sendo literal,
sem alegação de novidade estrutural. Protocolo: `docs/p3/CALIBRACAO_CONCEITUAL_V3.md`.

## 1. Objeto produzido

Cada semente gera um projeto Lean autocontido chamado **mundo**. Um mundo contém:

- uma base formal comum;
- um alvo visível `G0`;
- dois alvos irmãos ocultos `G1` e `G2`;
- uma ponte-oráculo `B*`, nunca exposta nos braços experimentais;
- um exemplo-fonte relevante, isomorfo na estrutura mas diferente em símbolos e objetos;
- um exemplo-fonte sham, pareado em tamanho e forma, cuja ponte não resolve o mundo-alvo;
- metadados com semente, molde, hashes, vocabulário e caminho-oráculo.

`G0`, `G1` e `G2` compartilham a mesma ponte abstrata, mas possuem fechamentos locais distintos.
Uma prova ou reformulação específica de `G0` não deve ajudar mecanicamente em `G1` ou `G2`.

## 2. Moldes do piloto

Os moldes abaixo descrevem a primeira geração. A opção `difficulty="hard"` (gerador
0.3.0) preserva as mesmas perguntas, mas T1 inclui cinco modos e composição interna;
T2 substitui árvores finitas por termos indexados, com variáveis e vínculo local. Em T2,
a lei útil quantifica ambientes relacionados para continuar válida ao entrar no vínculo.
Os arquivos padrão antigos são reproduzidos byte a byte, sem reescrever os fixtures v1.

Os metadados dos novos mundos fixam a allowlist dos três axiomas padrão do Lean. Nenhum
axioma específico do problema é introduzido. Provas são auditadas transitivamente; `sorryAx`
permanece proibido. Essa política é separada da política zero-axiomas histórica de v1.

Serão usados dois moldes, quatro mundos de cada.

### T1 — Transporte de invariante

O mundo fornece uma relação, uma propriedade preservada por cada passo e uma trilha dependente
de comprimento arbitrário. O alvo exige transportar a propriedade por um passo seguido de uma
trilha. A ponte-oráculo é a indução geral sobre trilhas; os irmãos exigem compor duas trilhas ou
uma trilha, um passo local e outra trilha.

A fonte relevante demonstra a mesma arquitetura em outro conjunto de tipos e símbolos. O sham
tem comprimento, número de lemas e formato de prova semelhantes, mas transporta uma propriedade
incompatível ou na direção errada.

### T2 — Mudança de representação

O mundo apresenta duas codificações de um mesmo objeto e regras locais em cada representação.
O alvo é difícil na codificação de entrada e curto após provar que uma normalização, projeção ou
tradução comuta com a operação relevante. A ponte-oráculo é essa lei geral; os irmãos usam
instâncias não vistas da mesma mudança de representação.

A fonte relevante contém uma mudança de representação análoga, sem compartilhar nomes ou
constantes. O sham mostra uma equivalência verdadeira, mas sem a propriedade de comutação que o
alvo exige.

Esses moldes calibram seleção e abstração de rota. Não devem ser descritos como abdução plena;
uma segunda geração, posterior ao piloto, poderá introduzir mundos em que o próprio tipo da
representação intermediária não é antecipado pelo gerador.

## 3. Estrutura de arquivos

Cada mundo congelado terá a seguinte organização conceitual:

```text
worlds/Wxx/
  lakefile.toml
  lean-toolchain
  World/Base.lean
  World/ChallengeVisible.lean
  World/Holdout1.lean
  World/Holdout2.lean
  Sources/Relevant.md
  Sources/Sham.md
  Hidden/Oracle.lean
  Hidden/OracleChecks.lean
  metadata.json
```

O diretório `Hidden/` não entra em nenhum workspace de agente. As fontes são fornecidas como
material de contexto; a solução não pode importá-las. A ponte candidata precisa importar apenas
`World.Base`.

O alvo é fixado como uma proposição sem `sorry`:

```lean
def VisibleStatement : Prop := ...
```

O candidato entrega dois arquivos:

```text
Bridge.lean    # helpers e theorem candidate_bridge; importa somente World.Base
Solution.lean  # theorem candidate_solution : VisibleStatement; pode importar Bridge
```

Separar a ponte da solução permite transferir apenas o intermediário para um agente novo. A
prova visível e a conversa que a produziu nunca entram na avaliação causal.

## 4. Construção sem vazamento

1. A semente mestre e as oito sementes de mundo são sorteadas e registradas.
2. O gerador produz todos os arquivos, inclusive os irmãos e o oráculo.
3. Um verificador mecânico prova que `Oracle.lean` fecha os três alvos.
4. Os artefatos são hasheados e commitados antes da primeira chamada de modelo.
5. Os workspaces dos agentes são materializados por allowlist; `Hidden/`, irmãos e metadados
   sem tratamento ficam ausentes.
6. Rede e busca web ficam desabilitadas durante as sessões.

Os símbolos recebem identificadores neutros derivados da semente. Todos os braços de um mundo
veem exatamente os mesmos nomes. Não haverá comparação “nomes naturais versus nomes opacos” no
piloto; isso seria outro fator experimental.

## 5. Portões de qualidade do mundo

Um mundo só entra no piloto se passar, antes da exposição aos modelos:

- **Existência:** o oráculo prova `G0`, `G1` e `G2` usando `B*`.
- **Não vacuidade:** a base é construída a partir de definições e teoremas, não de postulados
  arbitrários; quando o molde introduzir hipóteses, o pacote contém uma instância-testemunha que
  as satisfaz conjuntamente. Isso impede fechar os alvos por explosão a partir de uma base
  inconsistente.
- **Axiomas:** as provas dependem apenas da allowlist fixada para o projeto; preferencialmente,
  as regras do mundo aparecem como hipóteses ou teoremas provados, não axiomas globais.
- **Fixação do alvo:** o verificador compara a assinatura do candidato com a proposição congelada.
- **Sem atalhos proibidos:** `sorry`, `admit`, novos `axiom`, `unsafe`, `native_decide`, `extern`,
  `implemented_by` e alterações nos arquivos do mundo invalidam a tentativa.
- **Não trivialidade automática:** na implementação Lean-puro do piloto, tentativas fixas com
  `simp` e `grind` não fecham o alvo. Outras baterias só poderão ser acrescentadas antes do
  congelamento e serão então aplicadas a todos os mundos.
- **Corte estrutural:** no grafo do gerador, a ponte-oráculo cruza um corte entre fatos locais e
  fechamento do alvo; não é apenas o alvo renomeado.
- **Generalização:** a mesma ponte fecha os dois irmãos com terminações locais diferentes.
- **Sham válido:** a fonte sham é correta em seu próprio mundo e pareada à relevante, mas sua
  ponte canônica, transplantada pelo adaptador mecânico pré-especificado, não fecha nenhum dos
  três alvos do mundo-alvo. Isso não afirma a impossibilidade de um agente extrair outra ideia do
  sham; essa possibilidade é precisamente parte do controle experimental.

Todos os mundos usados para desenvolver e calibrar esses portões são descartados e nunca entram
na amostra principal. Até o fechamento v2 são quatro: dois originais e dois estruturais novos.

## 6. Verificador de submissão

Para cada tentativa, o harness cria um diretório limpo e somente então copia os arquivos
permitidos. A aceitação exige:

1. `Bridge.lean` compila sozinho contra `World.Base`.
2. `Solution.lean` compila e prova exatamente `VisibleStatement`.
3. `#print axioms candidate_bridge` e `candidate_solution` respeitam a allowlist.
4. A varredura de sintaxe não encontra construções proibidas.
5. Nenhum arquivo congelado mudou de hash.
6. O log contém cada chamada ao Lean, retorno, tempo, tokens e arquivos resultantes.

Compilar não basta para atribuir fidelidade informal a uma ponte, mas basta para estabelecer que
ela é uma consequência válida da base e pode ser entregue ao avaliador causal.

## 7. Avaliação causal da ponte

Para cada `Bridge.lean` válido:

1. cria-se um agente avaliador novo, sem memória da sessão propositora;
2. o avaliador recebe `World.Base`, um alvo irmão e a ponte candidata;
3. uma execução pareada recebe os mesmos arquivos, mas sem a ponte;
4. modelo, limite de iterações, tempo e parâmetros são idênticos;
5. o processo é repetido para `G1` e `G2`;
6. a diferença média de sucesso é a utilidade causal daquela ponte.

A ponte pode ter uma forma diferente de `B*`. Ela ganha crédito apenas se for válida e melhorar
o fechamento dos irmãos. Uma generalização trivial de `G0` tende a ter utilidade zero porque os
irmãos foram ocultados e possuem fechamentos distintos.

## 8. Telemetria e artefatos

Por sessão serão preservados:

- mundo, braço e identificador aleatório;
- prompt/contexto exato;
- modelo e parâmetros exatos;
- sequência completa de edições e respostas do Lean;
- `Bridge.lean` e `Solution.lean` finais;
- resultado, axiomas, número de verificações, tokens, tempo e custo;
- hash de todos os inputs congelados.

Os rótulos de braço ficam cegos na tabela de análise até a leitura única. Falhas de infraestrutura
são separadas de provas rejeitadas por um critério escrito antes dos dados.

## 9. Implementação mínima

A primeira implementação deve conter somente:

1. gerador determinístico dos dois moldes;
2. validador de mundo e de vazamento;
3. materializador de workspace por braço;
4. verificador de `Bridge.lean`/`Solution.lean`;
5. esquema JSONL de telemetria;
6. testes sintéticos dos portões.

Ela não contém chamadas a modelos. O harness de agentes só pode ser ligado aos dois mundos
descartáveis depois da revisão deste marco; a amostra principal continua bloqueada até o
pré-registro receber a palavra `CONGELADO` em commit separado.

## 10. Marco implementado — calibração estrutural v0.2

O núcleo está em `src/creative_machine/formal_routes/` e contém gerador, validação, materialização
por allowlist, verificador de submissão e contrato JSONL de telemetria. O comando reproduzível é:

```bash
PYTHONPATH=src .venv/bin/python scripts/p3_worlds.py generate-calibration
PYTHONPATH=src .venv/bin/python scripts/p3_worlds.py validate --lean \
  worlds/calibration/CAL_T1_E2CCC255 \
  worlds/calibration/CAL_T2_15CCB41E
```

Versão fixada: Lean 4.33.1, release oficial, commit
`819816b2e0a3bf405af45ae5c7af2491d8f5bee6`. Não há dependência de Mathlib nesta fase.

Mundos permanentemente descartáveis:

- `CAL_T1_E2CCC255`, semente `e2ccc2555a3cccc7`;
- `CAL_T2_15CCB41E`, semente `15ccb41e67d0ca58`.

Ambos passam: hashes e inventário exatos; ausência de symlinks; testemunha de não vacuidade;
oráculo fechando `G0/G1/G2`; fontes relevante e sham compilando sem axiomas; adaptador relevante
compilando; adaptador sham rejeitado pela obrigação esperada; e baselines `simp`/`grind`
rejeitadas. As fontes ficaram pareadas em palavras (T1: 176/176; T2: 252/252).

Verificação em 2026-09-04: `tests/test_formal_routes.py` = 15 passed; suíte completa = 148 passed,
6 skipped. Isso valida a infraestrutura e a lógica dos fixtures, não H1: falta ainda medir com
agentes descartáveis se a ponte-oráculo altera sucesso sob um orçamento útil.

## 11. Executor comportamental v0.3

O adaptador em `src/creative_machine/formal_routes/codex_runner.py` inicia uma sessão efêmera e
sem memória por célula, preserva o JSONL bruto e passa apenas um ambiente de processo saneado. O
perfil de permissões nega leitura na raiz e reabre somente o workspace exato, paths mínimos do
sistema, `~/.elan` e `/opt/homebrew`; comandos não têm rede. Busca, MCP, apps, plugins, skills,
hooks, browser, computer use e multiagente ficam desativados. O modelo continua alcançável pelo
processo hospedeiro, mas seus comandos locais permanecem confinados.

O verificador de avaliação exige `Solution.lean`, imports exatos conforme a condição, theorem
`evaluation_solution` com o tipo congelado, compilação pelo Lean e auditoria transitiva de axiomas.
O auditor pós-sessão rejeita mutação de input, symlink e qualquer saída além do contrato.

O plano `docs/p3/calibration_headroom_plan_v1.json` fixa antes dos dados modelo, esforço, timeout,
prompt e hash, cliente e hash do binário, manifestações dos mundos, oito células, ordem aleatória
e regra do gate. O comando de preflight, que não chama modelo, é:

```bash
PYTHONPATH=src .venv/bin/python scripts/p3_calibration.py validate-plan
PYTHONPATH=src .venv/bin/python scripts/p3_calibration.py sandbox-probe
```

Verificação anterior às chamadas: plano válido com 8 células; leitura do oculto negada; escrita
no workspace permitida; Lean funcional; rede negada. Testes específicos atualizados: 20 passed;
suíte completa: 153 passed, 6 skipped.

## 12. Resultado do primeiro gate comportamental

O gate v1 foi executado nas oito células, sem falhas de infraestrutura. Um bug do scorer procurava
o theorem de saída somente no namespace raiz; duas provas válidas estavam no namespace do mundo.
O scorer namespace-aware reavaliou os mesmos arquivos, sem nova chamada: baseline 3/4, oráculo
4/4 e ganho pareado 1/4 (`+0,25`). O gate congelado exigia ganho em pelo menos 2/4 e baseline no
máximo 2/4, portanto **não passou**.

O resultado localiza o problema no gerador: os alvos permitiam ao modelo rederivar a indução de T1
ou expandir diretamente T2 em menos de um minuto. Os dois fixtures ficam encerrados. A próxima
versão deve elevar a complexidade estrutural descartável mantendo aplicação curta do oráculo,
antes de qualquer propositor ou mundo principal. Resultado, correção e proveniência estão em
`docs/p3/CALIBRACAO_HEADROOM_V1.md`.

## 13. Implementação e resultado Bedrock v2

O modo `difficulty=hard` usa gerador 0.3.0, preservando byte a byte os fixtures padrão 0.2.0.
T1 tem cinco modos, caminhos indexados e composição binária/ternária; T2 tem termos indexados
pelo escopo, variáveis, vínculo local e transporte entre ambientes. A política axiomática
prospectiva admite apenas os três axiomas padrão Lean, sem novos axiomas nem `sorryAx`.

Os dois novos fixtures e o executor Bedrock foram congelados no commit `bbc96fa`, antes das
chamadas. A checagem Lean usa cópias limpas por allowlist, sem caches externos herdados;
o sandbox nega leitura do oculto e rede. A suíte completa anterior às chamadas passou com
161 testes e 6 skips; contagem de tokens e reservas limitam a exposição da aplicação.

Resultado: baseline 4/4 e oráculo 4/4, oito células válidas e todas na primeira submissão.
O gate não passou. O modelo produziu lemas auxiliares por indução em T1 e T2; a sintaxe
mais elaborada continuou sugerindo uma rota familiar. Não houve propositores/amostra principal.
Os fixtures estão encerrados. A próxima revisão deve exigir escolha de um intermediário não
fornecido pelo esquema da definição, não apenas mais construtores ou mais texto. Critérios,
provas finais, custos e limites de interpretação: `docs/p3/CALIBRACAO_BEDROCK_V2.md`.

## 14. Protótipos conceituais v3 — não integrados ao gerador

Dois exemplos escritos durante o desenvolvimento exploram escolhas diferentes de intermediário:
`DEV_INVARIANT_V3` (conservação quadrática não fornecida) e `DEV_REPRESENTATION_V3` (interpretação
não comutativa de palavras não fornecida). Os pacotes estão em `worlds/prototypes/`, não em
`worlds/calibration/`; ambos têm `phase=prototype`, `eligible_for_main=false`,
`eligible_for_calibration=false` e `sources_ready=false`.

O módulo separado `formal_routes/prototypes.py` não muda o gerador ou os executores congelados.
Revisão: duas pontes, seis fechamentos, 18 sondas automáticas sem solução e duas mutações
semanticamente falsificadoras; 185 testes passam, 6 pulam. Não houve chamadas experimentais.
Esses exemplos usam estruturas conhecidas e não comprovam ineditismo, dificuldade ou H1.
Gerador de novas instâncias, fontes/sham e próximo protocolo ainda dependem de revisão.
Parecer, evidência e riscos em `docs/p3/PROTOTIPOS_CONCEITUAIS_V3.md`.
