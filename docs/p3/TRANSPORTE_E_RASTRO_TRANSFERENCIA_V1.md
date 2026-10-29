# Transporte protegido e vínculo com o rastro — v1

Componentes operacionais prospectivos:
`transfer_transport_v1.ProtectedSession` e
`transfer_transport_audit_v1.audit_transport_links`.
Não alteram os executores, prompts, matrizes ou fontes congeladas. Não são
o lançador do lote nem o plano final de admissão experimental.

## Antes de cada chamada

O chamador fornece cliente, célula já admitida pelo diário, request inicial
canônico, posse do worker, reserva e fornecedor de conciliação corrente.
O guard substitui somente `client.messages`, preservando o tipo nativo
registrado nos rastros existentes. Não cria clientes ou resolve credenciais.

No perfil experimental exige exatamente o cliente Mantle, SDK 1.4.0,
perfil `main-account`, região `us-east-1`, endpoint regional fixo, SigV4 e
zero retries, sem credenciais explícitas que substituam o perfil. Não há
fallback de modelo/região/autenticação. O cliente é de uma única célula;
depois do fechamento, `messages` permanece bloqueado, não volta a ser livre.
O host deve fechar o cliente nativo ao terminar.

Antes de contagem nativa **e** inferência: verifica posse/identidade, cliente,
recibos preservados, prazo da sessão e conciliação financeira atualizada.
Grava e sincroniza uma intenção durável com hash do corpo, tempo, turno e
checagem financeira. Somente depois despacha o método nativo, sem mudar o
request. A conclusão contém a contagem ou a resposta JSON completa e seu hash;
isso preserva a resposta mesmo quando validação posterior detecta erro.
Falhas de persistência impedem nova chamada e mantêm a reserva aberta.

Confere interface canônica e primeiro input, alternância count/create, corpo
idêntico ao contado, timeouts de 30/300 s, 12 turnos e 600 s. Um segundo
`TokenBudget` usa a mesma implementação congelada e confere os tetos de
entrada/saída e a redução de `max_tokens` após revisões. Resposta terminal,
exceção, perda de posse, orçamento desatualizado ou reentrância fecham o guard.
Não há retomada, repetição de pedido nem settlement automático.

O guard não decide a elegibilidade da ponte, interpreta o conteúdo da prova
ou autoriza destinatários. Cabe ao lançador validar plano/preflight/CI,
admitir a célula uma vez no diário, cumprir a barreira dos seis propositores
e preparar somente inputs canônicos. A reserva e o claim não bastam para isso.
As proteções pressupõem o host e os componentes publicados cooperantes, não
impõem uma política a código arbitrário com as mesmas credenciais AWS.

## Auditoria independente dos vínculos

O auditor é somente leitura e não importa executores para executar sessões.
Recebe referências externas de fechamento, plano, claim e reserva. Confere
inventário exato, encadeamento, perfil, configuração e vinculação da célula.
Cada operação precisa corresponder a um par de eventos do rastro: mesmo corpo,
timeout, turno, contagem/resposta e intervalo de tempo. Arquivos adicionais,
contradições sob hashes novos e alteração durante a leitura são rejeitados.
Transporte falho ou incerto bloqueia; não vira observação matemática ou U=0.

Retorna também os hashes dos arquivos brutos e referências de conciliação
para o auditor do lote cruzá-los com seus próprios snapshots e recibos.
**Não substitui** a auditoria independente Lean/rastro, a conferência dos
recibos financeiros externos ou o perfil experimental do lote completo.
Não autentica a AWS: esses registros são observações do host. Flags de
autenticidade do provedor, validação financeira externa e admissão científica
permanecem falsas. Trocar `synthetic` por `experimental` não aprova o pacote.

## Validação e sequência

Testes usam diário/claim temporários e clientes simulados, incluindo os dois
executores inalterados, revisões com orçamento acumulado, limite de turnos,
falhas do provedor, persistência e orçamento, respostas inconsistentes e
auditoria adversarial. A inspeção do objeto SDK real testa somente configuração,
sem chamar seus métodos de rede; é ignorada explicitamente se o SDK está ausente.

Próximo encadeamento: plano executável e lançador experimental com retenção
dos recibos de conciliação, revisão mascarada e auditoria independente do lote
nesse perfil. Fechar preflight/publicação/CI e conciliação efetiva antes da coleta.
Não repetir o ensaio sintético nem reabrir S16/v3/W8/D12 como substituto.

Validação final local dos dois componentes: **52 testes** (33 do transporte,
19 da auditoria de vínculos). Com o contrato do plano executável, **98 passed
em 7,10 s**. Compileall, diff-check e blueprint original conferidos. A regressão
anterior de transporte/worker/orçamento/histórico passou com 99 testes; houve
um aviso de `fork` após o SDK iniciar threads, sem falha. Não ocultar esse aviso
como se fosse validação de portabilidade entre sistemas operacionais.
