# Contrato de verificação do receptor — Programa 3

**08/09/2026 — componente implementado; lote ainda não admitido.**

Implementação: `src/creative_machine/formal_routes/recipient_contract_v1.py`.
Testes: `tests/test_p3_recipient_contract_v1.py`. Este contrato prepara os
inputs do receptor e verifica sua prova. Não é executor de sessões no
provedor, auditor de rastros, revisão de conteúdo ou lançador de lote.
Não modifica os contratos históricos, S16, pareamento nativo ou W8/D12.

## Vínculo com a matriz e inputs

Cada chamada recebe o repositório confiável e um `cell_id` das 20 posições
de receptores da matriz de desenvolvimento: quatro B, quatro O e doze
condicionais D0/D/C2. O blueprint é reconstruído e comparado, incluindo as
dependências congeladas. Seu SHA256 permanece
`74e0ee9e49aa92797d6951023345c5d38dc46dd1d28eea1fae3db0db1035fa81`.
Ele continua `DRAFT_NOT_ADMITTED`; os componentes novos deverão constar
de um plano final separado, sem reescrever esse blueprint.

O alvo não vem de um hash arbitrário no registro do workspace: é derivado
da célula e dos arquivos congelados do mundo. Reescrever o alvo e atualizar
o hash local juntos não permite aceitar outra tarefa. Cada workspace novo
contém somente:

- `lakefile.toml`, `lean-toolchain` e `World/Base.lean`;
- o irmão indicado pela célula, copiado para `World/ChallengeEvaluation.lean`;
- `Bridge.lean` apenas quando a condição o prevê;
- `TASK.md` canônico desta versão.

A única saída permitida é `Solution.lean`. Fontes D/C2, alvo visível,
outro irmão, conversa propositora, pacote de revisão, rótulos de braço,
metadados do host e caches não entram no payload inicial. O renderizador
usa uma allowlist positiva e nunca inclui a saída já escrita. Arquivos
extras, diretórios extras mesmo vazios, symlinks ou mudanças nos inputs
são erros de integridade, não respostas matemáticas inválidas.

Uma candidata deve chegar como `BridgeArtifact`, com bytes UTF-8, hash,
mundo, namespace, declaração e hashes da base concordantes. Isso vincula
bytes; **não comprova seleção cronológica, revisão de conteúdo, procedência
ou admissão**. B não recebe artefato. O recebe os bytes exatos de
`Hidden/Oracle.lean` previstos na matriz, sem renomear ou limpar o arquivo.

Para a mesma ponte, mundo e irmão, os payloads D0/D/C2 são idênticos.
Não há promessa de cegamento completo B/O: a ausência/presença de ponte
é observável e o identificador congelado `oracle_bridge` permanece visível
em O. Não se altera uma evidência congelada para fabricar esse cegamento.

## Verificação em Lean

`materialize_recipient` exige um destino inexistente. Para uma candidata,
reutiliza o materializador congelado que recompila a ponte contra a base
antes de copiá-la. Para B/O, a materialização é estática; não substitui
preflight do runtime ou verificação da ponte-oráculo.

Em cada `verify_recipient`, qualquer ponte fornecida, inclusive O, é
novamente compilada e auditada em um primeiro diretório temporário com
somente a base e configurações. Nem o alvo do receptor nem sua solução
estão disponíveis nessa etapa. Uma segunda etapa nova recebe a base e
apenas o alvo correto; recompila os mesmos bytes da ponte, quando presente,
e depois compila `Solution.lean`. Nenhum artefato `.olean` é herdado do
propositor, do workspace vivo ou da primeira etapa.

Um auditor confiável separado importa o módulo compilado e inspeciona o
ambiente Lean. Para a solução, exige:

1. Exatamente um nome público permitido: `evaluation_solution` global ou
   no namespace exato do mundo.
2. Declaração de teorema, não definição, originada em `Solution.lean`.
   Um nome herdado de `Bridge.lean` não vale como resposta do receptor.
3. Tipo definicionalmente igual ao `Holdout1Statement` ou
   `Holdout2Statement` congelado daquela célula, via `Lean.Meta.isDefEq`.
4. Dependências axiomáticas transitivas limitadas a `propext`, `Quot.sound`
   e `Classical.choice`, via `Lean.collectAxioms`.

A ponte recebe a mesma checagem de identidade, natureza, origem em
`Bridge.lean` e axiomas, sem exigir similaridade com o oráculo ou força
matemática específica. Para candidata, o nome encontrado também deve
concordar com o artefato recebido. Seu conteúdo é assunto da revisão
separada, não deste verificador.

O sucesso depende do recibo emitido pela execução separada do auditor,
nunca de uma mensagem semelhante impressa durante a compilação candidata.
Filtros de fonte são conservadores e não substituem kernel ou sandbox.
Usa-se o sandbox existente por padrão; adaptadores injetados são fronteira
de teste e não comprovam procedência de uma execução experimental.

## Regras prospectivas e erros

Lean 4.33.1/Std, sem Mathlib. `Solution.lean` admite até 100.000 bytes UTF-8,
helpers matemáticos e apenas os imports prescritos no início: o alvo e,
quando fornecida, a ponte. Não são admitidos novos axiomas, provas admitidas,
comandos `#`, sintaxe/notação customizada, metaprogramação proibida ou
declarações inseguras. Somente `maxRecDepth` e `maxHeartbeats` podem ser
ajustados. As instruções são canônicas e não dependem da origem D0/D/C2.

Saída ausente fica `missing`; violação do formato/filtro ou rejeição Lean
comum fica `rejected`; prova aprovada fica `valid`. Ausência/rejeição não
é automaticamente um desfecho de sessão: término e seleção cronológica
serão responsabilidades do novo executor.

Cada verificação compartilha um único prazo de no máximo 120 segundos,
sem reiniciar o orçamento a cada comando. Esse prazo deverá caber no saldo
dos 600 segundos da sessão; materialização/recompilação não autoriza tempo
extra fora dela. O chamador deve fornecer o limite restante adequado.

Timeout, recursos Lean esgotados, processo interrompido, erro de adaptador,
falha de compilação dos inputs congelados ou do auditor e recibo ausente
ou inválido geram `VerificationInfrastructureError`. Não viram prova
rejeitada, U=0, retry ou liberação de reserva. Falha de uma ponte fornecida
é falha do input admitido, nunca incapacidade do receptor. A exceção retém
diagnósticos do processo e, após uma ponte já verificada, o relatório
parcial correspondente. Violações dos vínculos do workspace geram
`WorkspaceIntegrityError`; deriva dos arquivos confiáveis também bloqueia
a operação. O executor futuro deve tratar ambos como bloqueios técnicos.

Inputs e saída são conferidos de novo após a compilação. `RecipientReport`
retém hashes, célula, mundo, namespace, alvo, relatório da ponte e relatório
da solução para o host. `feedback()` expõe somente status/validade/erros
da solução; não deve ser substituído pela serialização do relatório inteiro.
Truncamento determinístico do feedback, rastros e histórico exato ainda
serão implementados no executor e conferidos pelo auditor independente.

## Integração ainda necessária

As entradas públicas são `materialize_recipient`, `render_recipient` e
`verify_recipient`, sempre vinculadas à célula e, para candidatas, ao mesmo
artefato. Não reutilizar nem alterar o loop histórico `bedrock_runner.py`,
que classifica timeout como rejeição e não possui todo o protocolo novo.

Próximos componentes: executor receptor versionado, auditor independente
dos seus rastros, depois lançador/auditor do lote. Este último deve impor
unicidade, filiação da ponte selecionada, primeiro recibo de conteúdo,
mascaramento efetivo e barreira de todos os seis propositores antes de
qualquer receptor. Ler também
[a política de conteúdo e cegamento](CONTEUDO_E_CEGAMENTO_PONTE_V1.md)
antes dessa integração. Conteúdo pendente não autoriza receptor.

Plano final, preflight, procedência do cliente, reservas, concorrência e
conciliação diária/lote continuam requisitos anteriores à admissão. A
implementação deste contrato não amplia a matriz nem antecipa replicação,
principal, P3B ou mecanismos.

## Cobertura de testes

Fixtures portáteis cobrem as 20 posições, allowlists e igualdade de payload
D0/D/C2, integridade, falso recibo, prazo compartilhado e falhas técnicas em
todas as fases. Integrações reais Lean/sandbox cobrem ambas as famílias e
B/O/candidata, tipo, identidade, natureza e origem da declaração, além de
dependência axiomática indireta via `Lean.trustCompiler` sem uma declaração
`axiom` na fonte candidata.

As provas conhecidas e adaptações do oráculo são fixtures identificadas,
não respostas de modelos, novas medições B/O ou resultados de transferência.
Testes reais são explicitamente separados dos portáteis no CI sem Lean.

Validação local: **122 testes específicos aprovados**, dos quais 14 com
Lean/sandbox reais. Regressão conjunta com contrato propositor e
matriz/análise: **275 passed em 115,93 s**. Isso verifica a implementação
do contrato; não certifica o executor de sessões ainda pendente.
