# Auditor independente de rastros propositores — v1

Componente prospectivo de desenvolvimento, 08/09/2026. Implementação:
`src/creative_machine/formal_routes/production_audit_v1.py`; testes:
`tests/test_p3_production_audit_v1.py`. Não altera contrato/executor,
pareamento nativo, mundos, matriz ou análise já fixados. Não é um lançador,
uma auditoria completa do lote ou um plano de execução admitido.

## O que é reconstruído

O auditor não reexecuta o runner com respostas simuladas e não usa seus
helpers de histórico, feedback ou `TokenBudget`. Compartilha apenas as
constantes de interface já congeladas e o contrato Lean como autoridade
formal. Implementa uma máquina de estados própria para reconstruir:

- identidade da célula propositora, mundo, braço, namespace, configuração
  exata e payload inicial por allowlist, a partir dos mundos congelados;
- ordem completa de eventos, contagens registradas, pedidos, respostas,
  histórico integral de mensagens e assinaturas de thinking;
- uma submissão completa por chamada, IDs únicos, bytes de ambas as saídas,
  recibos, revisões, feedback limitado e critérios de término;
- reservas conservadoras, uso de entrada/saída e cache, modelo retornado,
  custo configurado e todo o resumo final, sem confiar em `session.json`;
- seleção cronológica: somente a última submissão completa, jamais a
  melhor revisão anterior. Uma resposta truncada não substitui arquivos;
  protocolo inválido suprime a transferência, mesmo após ponte válida.

Cada revisão é recompilada em workspace novo, a partir da allowlist e dos
bytes registrados, usando o verificador congelado com sandbox. A ponte é
verificada só contra a base; o visível é verificado separadamente. Não há
consulta ao desempenho dos irmãos, cache herdado ou reaproveitamento da
pasta viva do propositor. A recompilação é auditoria de evidência existente,
não nova tentativa do modelo nem revisão/substituição de sua candidata.

São comparados status, hashes, declaração, axiomas, base, namespace e erros
que efetivamente compuseram o feedback. `stdout/stderr` completos das duas
verificações são preservados; timings de build e caminhos temporários nesses
canais não são critérios de igualdade semântica. Não se normaliza texto de
erro arbitrariamente: uma divergência no feedback exige revisão e bloqueia
a projeção, mesmo que decorra de variação legítima do ambiente.

## Limites e contabilidade

A configuração precisa ser exatamente a do blueprint: Opus 5/high,
main-account/us-east-1, 12 chamadas, 600 s por sessão, 300 s por requisição,
200 mil tokens de entrada, 20 mil de saída e 16.384 por resposta. Testes
portáteis exercitam limites sem reduzir essa configuração.

Reserva de entrada: `ceil(count * 1.10) + 1024`, com a aritmética float do
executor congelado, inclusive eventuais arredondamentos conservadores de
um token. A reserva de entrada não é devolvida após uma resposta; o excesso
reservado de saída é devolvido conforme uso conhecido. Escrita de cache é
limitada conservadoramente pelo dobro dos tokens; leitura entra integralmente
no limite e a 0,1× no custo. As tarifas fixas são US$5,50/27,50 por milhão.
Não há consulta nova ao contador nativo ou ao provedor.

Os timeouts são confrontados com os instantes monotônicos adjacentes: o
runner amostra tempo restante antes de gravar cada evento. Não se inventa
um instante exato de amostragem que o rastro não registra. Durações devem
caber nos respectivos intervalos; relógios regressivos, eventos fora de
ordem e alegações prematuras de término por 600 s falham na auditoria.

Um resultado com contabilidade `complete` significa somente que todas as
chamadas **registradas nessa sessão** foram reconstruídas e seu uso foi
conciliado localmente. Não é fatura AWS, autenticação do contador, comprovação
de ausência de chamadas externas/ocultas, quitação do orçamento diário/lote ou
permissão para liberar reservas. O lançador confiável ainda deverá garantir
cliente sem retries, procedência do runtime e conciliação externa.

## Evidência e fronteira de confiança

`build_evidence_manifest(repository, artifacts, cell_id=..., data_kind=...,
execution_plan_sha256=...)` constrói um inventário, **não uma aprovação**.
O manifesto vincula hashes de todos os arquivos, diretórios, célula,
mundo/braço, tipo de dado, blueprint e referência ao plano de execução.
Deve ser salvo fora da pasta bruta. Alterar arquivos e gerar um manifesto
novo não restaura a procedência de um selo previamente retido.

`audit_proposer_trace(...)` exige o selo externo
`expected_evidence_sha256` e uma referência separada de plano quando
`data_kind="experimental"`. Não aceita usar o blueprint como plano final.
O futuro lançador deverá reter esse selo ao encerrar a sessão, antes da
auditoria. A validação do plano final e de sua cadeia de admissão pertence
ao auditor do lote, ainda pendente; uma string de hash não a substitui.

JSON com chaves duplicadas/números não finitos, inventário extra, arquivo
ausente, symlink, hardlink ou mutação durante leitura/auditoria falha.
A leitura usa descritores relativos com `O_NOFOLLOW` para não atravessar
diretórios substituídos por links. Limites locais: 256 entradas, 256 MiB
por arquivo e 512 MiB totais; nada é truncado para caber. Os inputs
congelados e a implementação do auditor são novamente conferidos no fim.

O modo experimental proíbe checker injetado e exige os rótulos de cliente
Mantle e verificador real no rastro. Esses rótulos são evidência local,
**não atestados criptográficos do provedor**. Todo o pipeline depende do
lançador/runtime confiável e das evidências externas de execução. Um pacote
inteiramente fabricado e re-selado por quem controla o host não se torna
autêntico por passar na consistência interna.

## Saídas e bloqueios

Em caso de aprovação, retorna manifesto/hash, hash da implementação,
relatórios frescos de todas as revisões, resumo reconstruído e uma projeção
de célula compatível com `transfer_analysis_v1`. A projeção separa produção,
solução visível, revisão anterior válida e seleção final. **Conteúdo de
ponte selecionada fica `pending`**, nunca aprovado por validade Lean.
Sem ponte selecionada, conteúdo fica `not_applicable`.

`TraceAuditError` indica contradição, inventário inseguro ou desacordo com
verificação fresca. `TraceAuditBlocked` indica sessão técnica ou falha de
infraestrutura na recompilação. Nenhuma exceção produz observação
matemática, U=0, seleção alternativa, liberação de reserva ou retry.

Este v1 é deliberadamente conservador com rastros técnicos: preserva o
pacote original e não produz projeção aprovada nem custo reconciliado,
mesmo quando o resumo declara uso conhecido. O lançador/auditor do lote
deverá conservar a célula técnica/pendente e reconciliar suas reservas com
evidências externas. Relatórios parciais do compilador não são descartados
nem reinterpretados como ponte selecionada.

Dados sintéticos permitem checker/cliente de teste e permanecem
explicitamente sintéticos, inclusive quando usam Lean real com fixtures
conhecidas. Nunca são pontes produzidas pelo modelo ou resultados do lote.
Todos os campos de admissão de receptor/lote/principal/mecanismos continuam
falsos. Não marcar o lote como auditado pela aprovação de uma única sessão.

## Verificação e próximo componente

112 testes locais aprovados em 42,80 s. Cobrem os seis inputs da matriz,
términos e limites, perda de revisões, supressão por protocolo, truncamento,
contabilidade/cache, adulterações mesmo sincronizando resumo e evento final,
isolamento de revisões, selos/procedência, erros técnicos e integração com
a análise. Quatro testes usam Lean real: fixtures nas duas famílias,
detecção de aceitação falsa e reconstrução de rejeições seguida de ponte
válida sem solução visível. Os demais são portáteis sem SDK ou Lean.
Regressão conjunta com matriz/análise/runner/contrato: 324 testes aprovados
em 76,59 s; blueprint reconstruído com o hash original preservado.

Próximo: política operacional prospectiva de conteúdo/cegamento, receptor
com classificação técnica nova, auditoria/barreira do lote, lançador com
reservas e concorrência, plano final/preflight/publicação/CI. Nenhuma etapa
científica foi substituída por estes testes de instrumentação.
