# Auditor independente dos rastros receptores — v1

Implementação: `src/creative_machine/formal_routes/recipient_audit_v1.py`.
Estado: componente de instrumentação; não constitui admissão do lote.

## Entrada e vínculo

`audit_recipient_trace` recebe repositório, diretório bruto, célula da matriz,
tipo explícito de evidência e, quando aplicável, `BridgeArtifact` externo.
O contrato receptor determina os inputs canônicos: base, irmão correto e
ponte exata. O auditor não escolhe a ponte a partir do que o rastro declara.
O manifesto vincula mundo, braço, irmão, propositor-pai, metadados e hash da
ponte, blueprint, plano de execução e inventário de bytes/diretórios.

`build_evidence_manifest` apenas inventaria. O lançador deverá guardar seu
hash fora do diretório bruto no fechamento da sessão. Recalcular um hash
após adulteração não prova procedência. Modo experimental exige esse selo,
referência separada ao plano final, cliente identificado e ausência de
checker injetado. O blueprint rascunho não serve como plano final.

## Reconstrução

Compartilha com o auditor propositor somente utilitários de inventário
seguro, JSON estrito e envelopes temporais. Não chama o executor, seus
helpers de requisição/feedback, `TokenBudget` ou qualquer provedor.
Importa as constantes públicas da interface; identifica por hash os
arquivos do auditor, seus utilitários, contrato e executor receptores.

Reconstrói mensagens iniciais e todo o histórico, contagem nativa,
requisições, respostas, reservas, uso/cache, custos regionais, revisões,
feedback limitado e término. Exige configuração exata do blueprint,
recibos e eventos consistentes e inventário sem extras, symlinks ou
hardlinks. JSON duplicado/não finito, booleanos usados como inteiros,
sequências inválidas e relógios regressivos são recusados.

Seleção segue a última submissão completa, inclusive rejeitada, sem
recuperar uma revisão anterior. Primeira prova válida encerra a sessão;
truncamento não executa ferramenta; protocolo inválido suprime seleção.
Término normal sem prova é `not_solved`. Falha técnica bloqueia auditoria,
sem produzir score, liberar reserva externa ou autorizar repetição.

## Nova verificação formal

Para cada revisão, reconstrói workspace temporário só com inputs
canônicos e os bytes da solução; não reaproveita caches ou ambiente vivo.
`verify_recipient` recompila a ponte contra a base isolada e a solução
contra o irmão correto, em sandbox Lean. Compara status, declarações,
axiomas, erros, hashes e identidade. Só stdout/stderr podem diferir entre
execuções; o novo relatório completo permanece na saída da auditoria.

A montagem interna usa a especificação canônica do contrato, sem inferir
admissão. Mesmo sem submissão, chama o verificador com solução ausente:
uma ponte fornecida precisa passar novamente pela verificação Base-only.
Falha de infraestrutura preserva a exceção original como causa, incluindo
relatórios parciais quando fornecidos pelo contrato.

Cada nova verificação recebe até 120 segundos de auditoria. Não é uma
continuação da sessão do modelo nem altera seu orçamento de 600 segundos.
Timeouts/durações originais são conferidos contra os intervalos registrados;
isso verifica consistência local, não atesta latência por assinatura externa.
Ao terminar, reconfere inputs congelados, implementação e inventário bruto.

## Saída e limites

Retorna manifesto/hash, rechecagens, resumo reconstruído e projeção da
célula no esquema de análise. Evidências sintéticas são identificadas como
tais; checker injetado é permitido somente nesse modo de teste.

Continuam explicitamente falsos: validação de pai/conteúdo, barreira de
fases, aprovação do lote e admissão de inferência, amostra principal ou
etapa mecanística. A consistência do cliente registrado não é assinatura
do provedor. Uso local não substitui conciliação externa diária/do lote.

O próximo componente deverá integrar os seis propositores fechados e
auditados, revisão de conteúdo, recibos de procedência, seleção exata das
pontes, barreira anterior aos receptores, unicidade e contabilidade externa.
Depois virão plano final e preflight. Este auditor não muda matriz,
experimentos encerrados, critérios científicos ou limites financeiros.

## Verificação de implementação

Testes em `tests/test_p3_recipient_audit_v1.py` cobrem as vinte posições,
ausência/truncamento/protocolo inválido, reservas e seleção, falsificação
de rastros/recibos/identidades, selos, falhas técnicas e isolamento da nova
verificação. Incluem provas conhecidas nas duas famílias, falsa aceitação
e sequência rejeitada→válida com Lean real; esses casos são fixtures, não
observações experimentais. Integrações reais são explicitamente ignoradas
quando Lean/sandbox não está disponível no host do CI.
