# Sessão receptora: protocolo, término e rastros

**Rascunho prospectivo de desenvolvimento — 08/09/2026.**

Implementação: `src/creative_machine/formal_routes/recipient_runner_v1.py`.
Contrato formal usado: [CONTRATO_RECEPTOR_TRANSFERENCIA_V1.md](CONTRATO_RECEPTOR_TRANSFERENCIA_V1.md).
Este componente executa uma sessão receptora isolada, mas não cria cliente,
não admite células, não impõe a barreira do lote e não autentica seus próprios
rastros. Nenhuma chamada de modelo é feita por testes ou importação do módulo.

## Fronteira de admissão

O chamador fornece explicitamente `record`, repositório, `cell_id`, eventual
`BridgeArtifact`, diretório novo de evidências, configuração e cliente com
`max_retries=0`. O executor reconstrói a identidade da célula pelo blueprint
e chama `render_recipient`, que confere inputs, alvo e ponte. Um artefato
candidato continua sendo apenas vínculo de bytes; revisão de conteúdo,
filiação à última revisão propositora, procedência e aprovação permanecem
responsabilidades do futuro lançador/auditor do lote.

Antes do primeiro contato com o provedor:

- a configuração precisa estar nos limites prospectivos do regime maior;
- o output `Solution.lean` precisa estar ausente;
- workspace e diretório de evidências precisam ser novos e disjuntos;
- o payload inicial precisa ser reproduzível pelo contrato;
- o cliente não pode ter retries do SDK habilitados.

O componente não instancia credenciais nem consulta AWS. O modo experimental
futuro deverá exigir o cliente Mantle previsto, plano final congelado, CI,
reserva diária/lote e conciliação externa antes de passá-lo à função.

## Interface apresentada ao receptor

O sistema declara uma única ferramenta, `check_solution`, com exatamente
`solution_source: string`. Uma chamada completa substitui a saída de trabalho
e cria uma revisão imutável com bytes e SHA256. String vazia é uma submissão
e será verificada; não existe valor `null`, nome arbitrário de arquivo ou
segundo campo. Não se extrai código de prosa.

O pedido ao provedor contém apenas sistema, ferramenta, configuração do
modelo e o payload renderizado pelo contrato. Dados do host guardados em
`input.json` — célula, mundo, holdout e hashes — não são inseridos na mensagem.
Também não entram fonte D/C2, conversa propositora, solução visível, outro
irmão, pacote/decisão de conteúdo, resultados ou caminhos locais.

Para a mesma ponte, mundo e irmão, D0/D/C2 continuam com mensagens iniciais
idênticas. Isso mascara a origem da candidata; não mascara a existência da
ponte nem transforma B/O em duplo-cego. O nome congelado `oracle_bridge`
continua presente no payload O conforme o contrato anterior.

O feedback de uma revisão contém somente `status`, `valid`, `errors` e
`feedback_truncated` da solução. Erros são concatenados e limitados aos
primeiros 10.000 caracteres deterministicamente; o relatório integral,
inclusive ponte e saídas do compilador, fica apenas no rastro do host.
Nenhum campo de mundo, braço, conteúdo, utilidade, irmão ou ponte é devolvido
na conversa. Blocos completos do assistente, inclusive thinking assinado,
são preservados sem serem interpretados como evidência mecanística.

## Seleção e término

Política: `last_complete_solution_no_valid_fallback_v1`.

Cada submissão completa passa pelo verificador do receptor com o saldo
temporal da sessão. Uma prova válida termina imediatamente. Portanto não há
uma revisão posterior a um sucesso para “melhorar” ou selecionar. Enquanto
as provas forem rejeitadas, o modelo pode revisar; se a sessão terminar
normalmente, a última submissão completa é a candidata final, mesmo rejeitada.

Os términos normais são:

- `proof_verified`: a última revisão provou o alvo exato;
- `model_stopped`: resposta final/recusa sem ferramenta;
- `output_limit`: resposta truncada, cuja ferramenta inteira é ignorada;
- `token_budget`, `request_limit` ou `session_limit`: não cabe nova chamada.

Uma resposta truncada nunca substitui a revisão anterior. Ferramenta errada,
múltiplas ferramentas, ID vazio/repetido, `stop_reason` incompatível, campo
ausente/extra ou tipo inválido termina como `invalid_output`. A saída anterior
é suprimida para o desfecho da sessão; não há recuperação de uma revisão
rejeitada nem continuação automática. Texto final sem submissão é um resultado
auditável de tarefa não resolvida, não falha técnica.

O resumo usa categorias compatíveis com a análise prospectiva:

- `verified`, com `target_solved=true`;
- `not_solved`, incluindo término normal sem prova válida ou sem submissão;
- `invalid_protocol_output`, sempre sem solução selecionada;
- `not_interpretable_infrastructure`, sem observação científica.

Uma revisão final normal é copiada byte a byte para `selected_solution`,
inclusive quando rejeitada, para tornar explícita a regra cronológica. Em
protocolo inválido ou falha técnica não existe seleção, embora todas as
revisões anteriores continuem no pacote bruto para auditoria.

## Tempo, tokens e custo

Configuração prospectiva: Claude Opus 5/high, `main-account/us-east-1`,
até 12 requisições, 600 s por sessão, 300 s por requisição, 200 mil tokens
de entrada, 20 mil de saída e 16.384 por resposta. Configuração menor pode
ser injetada nos testes; o plano final deverá exigir a configuração exata.

Cada inferência é precedida por contagem nativa com exatamente o mesmo corpo,
sem `max_tokens`. A entrada é reservada por `ceil(contagem × 1,10) + 1024`;
a saída usa o menor entre 16.384 e o saldo total. Entrada reservada não é
devolvida; saída não usada é devolvida após uso conhecido. Cache write entra
2× no limite conservador e cache read integralmente. Não há retry ou fallback.

Contagem usa no máximo 30 s. Contagem, inferência e verificação compartilham
o prazo de 600 s; o verificador recebe no máximo 120 s e nunca mais que o
saldo da sessão. Se a contagem consumir o prazo, nenhuma reserva ou chamada
de inferência é admitida. O teto nominal permanece US$1,65 por sessão; o
custo calculado no rastro usa as tarifas configuradas, não uma fatura AWS.

Desde o momento em que a inferência é chamada até uso válido ser conciliado,
a reserva fica incerta. Erro/timeout de inferência, decode, uso inválido/acima
da reserva ou modelo divergente mantém `accounting_complete=false` e exige
preservar a reserva externa. Exaustão normal de orçamento antes da chamada
não é falha técnica e não cria cobrança incerta.

## Integridade, falhas e evidências

O runner reconfere o payload e os bytes de `Solution.lean` antes de cada
requisição, ao redor da escrita/verificação e no fechamento. Alterações dos
inputs, criação externa do output ou symlink são bloqueios técnicos. O
relatório do checker não é aceito pelo tipo nominal apenas: célula, mundo,
namespace, alvo, todos os hashes de input, ponte, bytes da solução, status,
declaração e axiomas são confrontados com os dados confiáveis.

Timeout/recurso/falha do Lean, ponte fornecida inválida, erro de adaptador,
recibo incorreto ou inconsistência do relatório termina como
`infrastructure_failure`, com `halt_admissions=true`. Diagnósticos brutos e
eventual relatório de ponte já validada são preservados. Não vira
`not_solved`, U=0, retry, recuperação de uma revisão nem liberação de reserva.

O diretório de sessão registra:

- `input.json` com interface, configuração, identidade e hashes do host;
- `events.jsonl` sequencial com tempos UTC/monotônicos, corpos completos das
  contagens/requisições/respostas, reservas, uso, submissões e feedback;
- todas as revisões, relatórios integrais e seleção final quando aplicável;
- `session.json` com término, desfecho, tokens, custos e incertezas.

Falha de escrita do próprio pacote pode lançar sem produzir resumo; o chamador
deve então preservar toda reserva externa e suspender novas admissões. Logs
locais não autenticam o provedor ou provam ausência de chamadas ocultas. O
próximo componente deverá reconstruir a máquina de estados e rever cada prova
em ambiente novo, sem confiar no resumo ou nos helpers deste executor.

## Trabalho restante

O próximo componente é `recipient_audit_v1`: auditor independente de rastros,
incluindo inventário seguro, seleção, histórico, contabilidade e recompilação
de todas as revisões. Depois vêm lançador/auditor do lote, unicidade do primeiro
recibo de conteúdo, barreira dos seis propositores, procedência, reservas,
concorrência, conciliação e plano final/preflight/CI.

Este executor não admite o diagnóstico, não modifica o blueprint original e
não produz resultados de transferência nos testes. Principal, replicação,
P3B e mecanismos conservam portões próprios posteriores.

Validação local: **76 testes específicos aprovados**, dois com sessões
sintéticas verificadas pelo Lean/sandbox real nas duas famílias. A regressão
conjunta com contrato receptor, executor propositor, matriz e análise aprovou
**335 testes em 155,73 s**. As demais respostas, contagens e falhas são
fixtures injetadas; nenhuma credencial ou inferência paga foi utilizada.
