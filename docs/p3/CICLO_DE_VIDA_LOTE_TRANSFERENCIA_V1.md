# Diário do ciclo de vida do lote de transferência — v1

Componente prospectivo em `transfer_lifecycle_v1.py`, 08/09/2026.
Implementa cronologia e intenções duráveis; não é ainda o lançador,
auditor independente do lote, reserva financeira ou admissão experimental.
Não executa provedor, Lean, revisão semântica, pontuação ou conciliação.

## Autoridades separadas

O chamador entrega o blueprint validado por `load_blueprint`. A abertura
vincula por hash esse blueprint, a implementação do diário, um plano final
separado, recibo de reserva, procedência e preflight. Identifica evidência
sintética/experimental e preserva os limites de duas sessões simultâneas,
US$1,65 nominais por sessão e US$50 reservados para o lote.

Esses hashes são referências, não validação do conteúdo dos objetos.
O lançador deverá verificar plano/publicação/ambiente, autoria/procedência,
orçamento diário e compromissos externos antes de chamar modelos. O auditor
do lote deverá reconstruir cada rastro com os auditores existentes, conferir
pacotes/julgamentos, conciliar os recibos e só então produzir a projeção
integrada. Um campo `passed` no diário não substitui essas verificações.

## Eventos e invariantes

Cada evento tem sequência, timestamp UTC, payload de esquema exato, hash
anterior e hash próprio. A ordem das 26 posições vem do blueprint; não há
API de retry, troca de alvo, nova semente, retorno a revisão anterior ou
omissão de posição elegível.

- `batch_opened`: única abertura, com as referências externas.
- `cell_started`: intenção registrada antes do trabalho externo. Consome
  a posição uma vez; permite no máximo duas sessões em andamento. Exige
  que sessões já encerradas tenham sua auditoria registrada antes de
  abrir outra vaga. Vincula o recibo do workspace e o hash da ponte.
- `cell_closed`: selo dos rastros e uso reportado. Término normal exige
  contabilidade completa e custo dentro da reserva por sessão. Falha
  técnica suspende novas admissões imediatamente no diário, preservando
  custo conhecido/ausente e até um estouro reportado, sem descartá-lo.
- `trace_audited`: primeiro recibo de auditoria da sessão já encerrada,
  ligado ao selo bruto. Para propositores, registra desfecho de produção
  e hash da ponte final; não declara conteúdo aprovado. Falha de auditoria
  interrompe novas admissões. Sessão técnica não pode receber `passed`.
- `review_prepared`: somente depois dos seis propositores auditados, para
  ponte final formalmente válida. Sela vínculo e pacote com ID opaco.
- `review_recorded`: primeiro recibo daquele pacote/vínculo, com conteúdo
  `passed`, `rejected` ou `pending`. Não permite substituir julgamento,
  preparar pacote alternativo ou reaproveitar recibo de outra candidata.
- `phase_barrier`: uma vez, sem sessões ativas, depois dos seis propositores
  auditados e de todas as decisões de conteúdo resolvidas. Vincula por hash
  todos os selos, auditorias, seleções e recibos. Pendência bloqueia a
  barreira; adjudicação não é implementada nesta versão.
- `cell_skipped`: depois da barreira e na posição prevista, somente para
  ponte candidata inelegível, com motivo e evidência do pai. Sem rastro,
  sessão ou reserva fictícios. Não permite excluir baseline/oráculo.
- `halted`: registra impedimento externo explícito e referência à evidência.
- `batch_closed`: não permite sessões ainda ativas. Fechamento normal exige
  todas as posições consumidas e auditorias registradas; fechamento após
  impedimento preserva posições não iniciadas, sem inventar respostas.

A barreira antecede qualquer receptor, inclusive B/O. Candidatos recebem
exatamente o hash selecionado de seu pai, O o oráculo congelado de seu mundo,
B nenhuma ponte. Validade formal e conteúdo permanecem separados: rejeição
de conteúdo não reclassifica a ponte como inválida em Lean.

Falha interrompe novas admissões, mas não impede registrar encerramentos e
auditorias das sessões que já estavam em andamento. Os custos são decimais,
sem arredondar o subtotal; valores desconhecidos são listados separadamente.
O subtotal conhecido não é custo total ou fatura. O diário nunca libera a
reserva externa, nem mesmo quando suas 26 posições estão encerradas.

## Persistência e retomada

`Journal.create` é exclusivo e não substitui arquivo existente. O diretório
pai precisa existir. `append` exige o hash anterior esperado, adquire trava
exclusiva de arquivo e reconstrói/valida todo o prefixo antes de acrescentar
um evento. Duas threads/processos com o mesmo hash esperado não podem ambos
consumi-lo. Não há retry automático de uma operação com referência obsoleta.

Arquivos regulares, sem symlinks/hardlinks; limites de 1 MiB e 256 eventos;
JSON estrito, sem duplicatas/não finitos. Escrita trata gravações curtas e
faz `fsync` no arquivo e no diretório. Releituras e conferência de identidade
detectam alterações de bytes, inode ou pai durante a operação. Arquivo
parcial após falha permanece preservado: não truncar, reparar ou recriar
silenciosamente. Uma falha após escrita pode significar intenção já gravada;
é ambiguidade a reconciliar, não autorização para repetir uma célula.

A trava por operação não é posse exclusiva do worker durante toda a sua
vida. O lançador ainda precisa desse controle e de uma política de retomada
de fases; não pode reiniciar sessões com intenção ativa e estado incerto.

`read(expected_head_sha256=...)` confere um checkpoint externo. A cadeia
interna sozinha não detecta truncamento de cauda ou história inteiramente
reescrita e recalculada. Guardar o selo de fechamento fora do diário e
validá-lo na auditoria independente; não alegar assinatura do provedor.

O diário é material do host: contém vínculos entre célula, ponte e pacote.
Não mostrá-lo ao revisor de conteúdo nem ao modelo receptor. O lançador
deverá expor ao revisor somente os pacotes mascarados já especificados.

## Verificação e próximo encaixe

109 testes específicos aprovados. Incluem 26 sessões, doze exclusões
explícitas por produção/conteúdo inelegível, dois workers, competição entre
threads e processos, barreira, primeira revisão, falha/uso incerto, alterações
de recibos/bytes, gravação parcial e substituição de arquivo/diretório.
Regressão com matriz e análise: **187 passed em 1,55 s**. São referências
sintéticas; nenhum recibo de teste constitui evidência experimental.

Próximo: conectar o diário aos executores, auditores de sessão e revisão
de conteúdo em um lançador com posse de worker e admissão financeira;
implementar auditor independente do lote e fluxo mascarado de revisão.
Depois congelar plano completo, publicar/validar CI e executar preflight.
Principal, replicação, P3B e mecanismos mantêm seus portões próprios.
