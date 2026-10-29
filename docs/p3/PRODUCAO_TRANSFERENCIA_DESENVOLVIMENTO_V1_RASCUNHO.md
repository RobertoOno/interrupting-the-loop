# Próximo diagnóstico: produzir uma ponte e transferir somente a ponte

**RASCUNHO DE DESENVOLVIMENTO — 08/09/2026 — NÃO CONGELADO.**
Preparação elegível após o fechamento auditado S16. Não inicia amostra
principal nem altera o pré-registro principal, os mundos ou planos anteriores.

## Pergunta

Já sabemos que a ponte-oráculo ajuda neste instrumento, nos limites
testados. Falta medir se um modelo produz uma ponte válida ao trabalhar
somente no alvo visível, e se a ponte ajuda receptores novos em irmãos
que o propositor não viu. Resolver o visível e produzir um intermediário
transferível serão registrados separadamente.

## Escopo proposto

Conservar **ambos** os mundos de calibração v3/S16 e as três fontes já
previstas: D0 (alvo apenas), D (fonte relevante) e C2 (sham correto e
pareado). Não excluir a família de invariante porque apresentou teto em
16.384; ela é informativa para testar a instrumentação mesmo quando a
utilidade binária possa ser zero. Nenhum caso novo escolhido por sucesso.

Usar o regime maior de S16 para propositores e avaliadores: Opus 5/high,
16.384 tokens por resposta, 20 mil de saída e 200 mil de entrada totais,
600 s por sessão, 300 s por requisição, até 12 requisições e concorrência
máxima dois. Fixar tudo em plano próprio antes das respostas.
É escolha prospectiva para o próximo diagnóstico, não alteração de S16.

Uma sessão propositora por braço/mundo: seis. Cada uma entrega
`Bridge.lean` e `Solution.lean` separadamente. Ponte precisa importar
somente `World.Base`; solução prova exatamente o alvo visível. Auditoria
permite somente os axiomas padrão já adotados, sem `sorryAx`, novos axiomas,
metaprogramação proibida ou mudanças dos inputs. O verificador histórico
de proposição tem política zero-axiomas: criar versão nova, não alterá-lo.

A ponte final válida será testada em dois avaliadores novos, um por irmão.
Cada receptor recebe somente base, seu alvo e a ponte quando tratada —
nunca fonte, conversa, solução visível ou rótulo de braço. A sessão de
avaliação e a ponte são imutáveis; provas podem usar um intermediário
diferente do oráculo, sem pontuação por similaridade textual.

Baselines e oráculos serão novos e contemporâneos. Não reutilizar as
respostas S16 como controles. Uma baseline por mundo/irmão será comum aos
três contrastes daquele mundo, como no desenho original; essa dependência
deve ficar explícita. No máximo seis propositores + doze avaliações de
pontes candidatas + quatro baselines + quatro oráculos = **26 sessões**.
Se uma ponte for inválida/ausente, não há receptor com essa ponte; registrar
o motivo, sem substituir por oráculo ou nova tentativa propositora.

## Antes do congelamento

1. Implementar e testar o contrato de duas saídas e as verificações
   independentes de ponte/solução visível, inclusive ponte válida quando
   a solução visível falha. Não apagar esse caso por um `ok` conjunto.
2. Testar por allowlist e rastros que G1/G2, oráculo e metadados ocultos
   não entram no contexto ou feedback do propositor. Não usar irmãos para
   selecionar, revisar ou escolher a ponte final.
3. Entregar ao receptor somente os bytes da ponte aceita; validar ponte
   contra a base em workspace novo, sem artefatos compilados herdados.
4. Medir tokens das fontes com a contagem nativa, fixar tolerância D/C2
   antes de qualquer resposta e documentar diferença de conteúdo. Parear
   comprimento não iguala informação matemática ou dificuldade cognitiva.
5. Fixar política de término e seleção da ponte sem acesso ao desempenho
   nos irmãos; preservar todas as versões e rejeições. Sem melhor-de-N,
   retry técnico automático, recuperação seletiva ou mudanças pós-resposta.
6. Fixar matriz, cegamento dos receptores, ordem, scripts de análise,
   critérios de validade/avanço e arquivos por hash; testes e CI antes
   da primeira chamada. Uma falha técnica preserva evidências e suspende
   novas admissões, não vira incapacidade matemática ou nova semente.

## Análise e limites

Relatar por mundo e braço: validade da ponte, solução visível, soluções
dos dois irmãos com/sem ponte e U. Reportar H1/oráculo contemporâneo antes
de interpretar transferência. Com dois mundos, **não aplicar o teste
confirmatório de oito mundos nem declarar H2 confirmada**. Todas as células
permanecem no inventário; ausência/invalidade de ponte é resultado de
produção, não erro de infraestrutura. A convenção U=0 para ponte inválida
precisa permanecer distinguível de uma ponte válida cuja utilidade foi zero.

As regras exatas de avanço deste diagnóstico devem ser escritas antes do
congelamento. S16 permite preparar esse passo, não elimina sua própria
revisão nem autoriza chamar estes dados de principal. Se houver teto,
preservá-lo: não retirar família, elevar limites ou selecionar outro alvo
para criar diferença. Réplicas em instâncias/famílias não usadas no
desenvolvimento e a elegibilidade/novidade da principal ficam para etapas
próprias. P3B e mecanismos não são inferidos deste diagnóstico.

Reserva nominal proposta pelos tetos atuais: 26 × US$1,65 = **US$42,90**;
teto operacional proposto US$50, dentro de US$150/dia AWS, após conciliar
consumo e compromissos. Não é reserva já efetuada ou fatura prevista.
Não precisa de pod GPU. O total real pode ser menor por pontes inválidas
ou sessões que terminem cedo, sem expandir a matriz para gastar a diferença.

## Implementação local do contrato — 08/09

Criado `src/creative_machine/formal_routes/production_contract_v1.py`,
sem modificar `submission.py`, `workspace.py` ou os executores congelados.
O contrato é infraestrutura em desenvolvimento, **não congelamento ou
admissão do diagnóstico**. Não implementa ainda a política de escolha da
versão final nem uma sessão propositora no provedor.

O novo verificador retorna `bridge` e `visible` separadamente. A primeira
compilação da ponte recebe somente configurações e `World.Base`; a segunda,
da solução visível, recebe a mesma ponte e o alvo visível. Ambas partem de
bytes conferidos, em diretórios novos e no sandbox de rede/arquivos. Nenhum
cache `.olean`, manifesto de dependências antigo, fonte D/C2 ou irmão é
copiado para o compilador. Um resultado `visible=rejected/missing` não
revoga `bridge=valid`; ponte inválida impede a verificação da solução que
depende dela, explicitamente `blocked_by_bridge`.

A auditoria confiável inspeciona o ambiente Lean: exige exatamente um dos
dois nomes permitidos, com declaração de teorema, dependências axiomáticas
padrão, origem no módulo de saída correspondente (`Bridge`/`Solution`) e
tipo visível definicionalmente igual ao alvo congelado. Não usa
regex de texto do candidato para inferir a existência de um teorema, nem
aceita mensagens `#print` produzidas por ele como recibo. Erros no código
do auditor ou recibos incompletos são falhas de infraestrutura, não rejeições
matemáticas. Testes com provas conhecidas detectaram e permitiram corrigir
um erro inicial de integração do auditor visível antes de qualquer coleta.

O contrato acrescenta instruções prospectivas iguais a D0/D/C2: 100 mil
bytes UTF-8 por arquivo; imports no início; sem comandos `#`, notação ou
sintaxe personalizada, metaprogramação ou opções arbitrárias; somente
`maxRecDepth` e `maxHeartbeats` podem ser ajustados. O filtro é conservador
e não substitui o sandbox ou a auditoria axiomática. O prazo padrão de
verificação é **120 s compartilhados entre os comandos**, a ser integrado
ao restante dos 600 s da sessão. Timeout, exaustão de recursos Lean, falha
do ambiente congelado ou do auditor suspendem a admissão; não são U=0
nem autorização de retry. Diagnósticos brutos e eventual ponte já verificada
permanecem disponíveis na exceção para o futuro executor registrar.

O artefato de ponte vincula os bytes exatos ao hash, base, toolchain,
identificador de mundo e nome da declaração. Criar um artefato **não
seleciona uma revisão**. Ao preparar o receptor, a ponte é recompilada só
contra a base, sem acesso ao alvo irmão. O workspace entregue contém
somente os inputs do receptor e a ponte imutável; não contém a conversa,
fonte, solução visível, rótulo D/D0/C2 ou artefatos compilados do propositor.
Isso é isolamento de canais/arquivos: a ponte naturalmente pode codificar
conhecimento adquirido no visível/fonte, que é o intermediário em teste.
Ainda será necessário auditar o conteúdo e o rastro completo do executor;
estes testes locais não demonstram cegamento de chamadas ainda inexistentes.

Testes novos em `tests/test_p3_production_contract_v1.py`: allowlists,
mutação/symlinks, bytes/caches, tentativa de falsificar auditoria, falhas
técnicas e verificação real de identidade/tipo/axiomas em Lean. Provas-oráculo
existentes das **duas famílias** são fixtures locais identificadas, nunca
respostas experimentais, pontes produzidas pelo modelo ou controles do lote.
Testes genuinamente dependentes de Lean/sandbox são separados dos portáteis
para o CI sem esses runtimes.

Validação local final do contrato: **75 testes aprovados em 26,81 s**, dos
quais 13 executam Lean/sandbox reais. Inclui rejeitar uma solução herdada
do módulo errado e impedir a substituição da declaração visível pela ponte.
O primeiro marco publicado (`7ea9c7a`) passou no CI: 1504 passed/38 skipped,
141,80 s, execução `34187293163`; essa execução precede os dois últimos
testes e a checagem explícita de origem do teorema.

Próximo: implementar o executor propositor e seus rastros/testes de sessão,
fixar seleção/término sem informação dos irmãos, contagem nativa D/C2,
matriz/ordem, análise e critérios de avanço; então revisar, congelar fontes,
publicar/validar CI e conciliar orçamento antes da admissão. S16/W8 seguem
fechados; principal, replicação, P3B e mecanismos não são antecipados.

## Implementação local da sessão propositora — 08/09

Criado `production_runner_v1.py`, com testes próprios e
[política prospectiva de sessão](POLITICA_SESSAO_PROPOSITOR_V1_RASCUNHO.md).
Usa o contrato anterior sem modificá-lo. A última submissão completa é a
candidata final, sem retorno à última versão válida se a posterior falhar.
Ponte e solução visível permanecem separadas; duas verificações válidas
encerram imediatamente. Resposta truncada não é executada como submissão;
violação do protocolo ou falha técnica não recupera automaticamente versões
anteriores. Todas as versões e rejeições ficam registradas.

Rastros incluem inputs, pedidos/respostas, tempos, reservas, uso e feedback
exatos. Artefato selecionado tem bytes/hash/proveniência; a elegibilidade
permanece pendente de auditoria, não admite receptores por si só. O módulo
não cria cliente ou reservas externas e não é lançador de lote. Exige-se
cliente sem retry; nenhum modelo menor ou perfil alternativo é fallback.

Permanecem pendentes o pareamento nativo/tolerância D/C2, matriz/ordem,
análise/portões, auditor de rastros e orquestrador de reservas/admissão,
preflight, congelamento e publicação/CI do plano completo. Os mesmos dois
mundos expostos e o máximo de 26 sessões continuam; não substituir os
controles por S16 nem iniciar mecanismos a partir desta implementação.

## Pareamento nativo encerrado; análise prospectiva — 08/09

O controle de comprimento foi congelado/publicado em `ab9573a` antes de
contar. Onze contagens nativas Opus 5/Mantle, auditadas: invariante D/C2
689/691 tokens incrementais (0,290%); representação 1328/1324 (0,302%).
Ambos passam a tolerância simétrica pré-fixada de 5%, sem alterar fontes.
[Relatório/evidências](PAREAMENTO_NATIVO_RESULTADOS_V1.md). Não recontar
ou editar o pacote fechado para implementar o restante do lote.

Novo [rascunho de análise e decisões](ANALISE_TRANSFERENCIA_DESENVOLVIMENTO_V1_RASCUNHO.md):
validade e completude primeiro, controles contemporâneos depois; distinguir
U medido de zero convencionado por falha de produção; não truncar prejuízo
negativo. Transferência positiva prepara estudo independente, não confirma
H2 ou admite mecanismos; ausência de ganho pede exame completo das falhas,
sem fabricar contraste ou concluir teto geral. A regra ainda precisa de
implementação/testes, matriz/ordem e revisão antes do congelamento do lote.

Próximos componentes: análise/matriz executáveis, auditor de rastros e
conteúdo/cegamento, receptor com política técnica nova, orquestrador de
reservas/admissão, preflight e publicação/CI do plano completo. Mantêm-se
ambos os mundos expostos e as 26 sessões máximas. Este diagnóstico continua
em preparação, separado da principal, confirmação, P3B e mecanismos.

## Matriz e análise implementadas — 08/09

`transfer_design_v1.py` e `transfer_analysis_v1.py`, CLI separado e
[contrato operacional](MATRIZ_E_ANALISE_TRANSFERENCIA_V1.md). Blueprint
`transfer_design_draft_v1.json`, estado `DRAFT_NOT_ADMITTED`: 26 posições
fixas, seis propositores antes da fase de receptores, ordem por ranking
SHA256/2026090802, filiação de cada ponte e baseline compartilhada explícitas.
Confere referências dos mundos e do pareamento encerrado sem reexecutá-lo.

Análise exige inventário completo de posições e projeções do futuro auditor,
vinculadas por hashes à matriz, evidências e plano final separado. Não é um
auditor nem autentica um campo `passed` fornecido externamente. Bloqueios
técnicos/de auditoria/contabilidade retornam motivos e nenhum agregado
científico parcial. Zero convencionado de produção, U medido=0, dano U<0
e ajuda sem solução visível continuam distinguíveis. O resultado identifica
dependência das baselines, perdas entre revisões e conteúdo pendente/rejeitado.

Portão contemporâneo B/O precede interpretação; não há teste confirmatório
ou promoção automática. Testes sintéticos cobrem as 256 configurações
binárias dos controles e casos favoráveis a todos os braços, sem produção
de resultados experimentais. Próximo: auditor/reconstrutor, política de
conteúdo/cegamento, receptor e reservas/admissão, com preflight/CI e revisão
do plano completo antes do lote. Não refazer componentes encerrados.

## Auditor independente dos propositores implementado — 08/09

Novo `production_audit_v1.py` e [contrato operacional](AUDITOR_RASTROS_PROPOSITOR_V1.md).
Reconstrói inputs/histórico, chamadas, revisões, feedback, reservas/custo,
término e seleção, sem usar a máquina de estados/helpers do executor.
Recompila cada revisão em workspace novo com o contrato Lean congelado;
resumo e seleção precisam concordar com os rastros e a verificação fresca.

112 testes aprovados em 42,80 s, incluindo quatro integrações Lean reais,
ambas as famílias e adulterações. Produz projeção compatível com a análise,
mas mantém conteúdo da ponte pendente e todos os campos de admissão falsos.
Falhas técnicas/inconsistências bloqueiam projeções e conciliação automática,
não recebem U=0. Selos externos e plano separado são exigidos no modo
experimental; consistência de logs locais não autentica o provedor nem
substitui a procedência do lançador e a conciliação diária/lote.

Próximo trabalho começa pela regra operacional de conteúdo/cegamento, depois
receptor com política técnica nova, auditoria/barreira e reservas/admissão
do lote, plano final/preflight/publicação/CI. Não reimplementar este auditor
nem refazer matriz, executor, pareamento nativo, S16 ou W8.

## Política e fluxo de revisão do conteúdo implementados — 08/09

Novo `bridge_content_v1.py` e [política operacional](CONTEUDO_E_CEGAMENTO_PONTE_V1.md).
Prepara pacote após auditoria do rastro, com ponte/base/G0 e ambas as fontes
em pool comum a D0/D/C2, sem rótulos, histórico, solução visível, irmãos,
oráculo ou resultados. O mascaramento não é alegação de duplo-cego;
exposição prévia precisa ser declarada e o vínculo candidata/braço não
pode ter sido entregue ao revisor. O host guarda os vínculos separadamente.

Cinco critérios tratam conversa/instruções, fonte como documento, solução
visível completa, escopo matemático e metadados experimentais. Adaptação
legítima, inclusive código matemático literal usado como auxiliar, não é
vetada por similaridade. Ponte trivial ou presumivelmente inútil também
não é rejeitada por esse motivo. Flags lexicais apenas auxiliam a leitura.

O recibo exige revisor identificado/autorizado, leitura integral, atestados,
justificativas por critério/flag e trechos exatos para violações/dúvidas.
Deriva conteúdo rejeitado, pendente ou aprovado; não certifica automaticamente
a correção semântica do revisor. Mantém bytes/validade formal/seleção
originais e não admite receptor por si só. A unicidade do primeiro recibo,
mascaramento no fluxo real e barreira dos seis propositores ainda serão
impostos pelo lançador/auditor do lote, não pela API pura de revisão.

Política SHA256 `8eda252f4d9ef861a4e0c74b0f33ad555433d59483c7898503628ec2427dd8ce`.
Próximo: receptor com classificação técnica nova, seus rastros/auditoria,
admissão/concorrência/reservas e plano final/preflight/publicação/CI.
Interface propositora e pareamento nativo continuam sem alteração.

## Contrato de verificação do receptor implementado — 08/09

Novo `recipient_contract_v1.py` e
[contrato operacional](CONTRATO_RECEPTOR_TRANSFERENCIA_V1.md). Vincula cada
receptor ao alvo exato de sua posição na matriz, entrega somente os inputs
permitidos e preserva os bytes da ponte. D0/D/C2 com a mesma ponte produzem
payloads idênticos; o identificador congelado `oracle_bridge` de O continua
visível, sem alegação de cegamento completo B/O.

Ponte recompilada contra a base apenas; solução verificada em segunda
etapa nova contra o irmão correto. Auditor do ambiente Lean exige teorema
público único, origem em `Solution.lean`, tipo exato e axiomas transitivos
padrão. Tempo compartilhado de até 120 s, limitado futuramente pelo saldo
da sessão; falhas técnicas não são rejeições matemáticas. Relatório para o
host separado do feedback ao receptor. Não altera verificador ou runner
propositores, pareamento nativo ou experimentos encerrados.

Este componente não é ainda o executor receptor nem auditoria de rastros
ou admissão do lote. Próximo: esses dois componentes, depois lançador com
unicidade/barreira/procedência, reservas/concorrência/conciliação e plano
final/preflight/publicação/CI. Blueprint original preservado, ainda
`DRAFT_NOT_ADMITTED`; testes com provas conhecidas não são coleta do lote.

## Executor de sessão receptora implementado — 08/09

Novo `recipient_runner_v1.py` e
[política prospectiva](POLITICA_SESSAO_RECEPTOR_V1_RASCUNHO.md). Uma única
ferramenta substitui `Solution.lean`; a primeira prova válida encerra a
sessão. Antes disso, vale sempre a última submissão completa. Truncamento
não executa ferramenta; protocolo inválido suprime a candidata anterior.

Contagem nativa e inferência usam o mesmo corpo. Reservas conservadoras,
uso/cache, custo e incerteza seguem o regime maior; contagem, inferência e
verificação compartilham os 600 s. O verificador recebe no máximo 120 s e
o saldo restante. Falha técnica preserva evidência e bloqueia admissão,
sem ser `not_solved`, U=0 ou autorização de retry.

O host registra histórico, bytes/revisões, relatórios, feedback truncado,
seleção e contabilidade. A mensagem do receptor mantém a allowlist do
contrato; D0/D/C2 com a mesma ponte continuam idênticos. Dados de célula e
origem só ficam no pacote do host. O runner valida os campos do relatório
contra célula, alvo, inputs, ponte e solução; não confia no checker injetado.

Ainda não é coleta nem lote admitido: falta auditor independente desses
rastros e depois a integração/barreira/procedência/conciliação/plano final.
O executor não cria cliente ou credenciais e testes usam respostas sintéticas.

## Auditor de rastros receptores implementado — 08/09

Novo `recipient_audit_v1.py` e
[contrato operacional](AUDITOR_RASTROS_RECEPTOR_V1.md). Reconstrói de forma
independente histórico, seleção da última submissão completa, contabilidade,
identidade e inventário. Reexecuta cada verificação em workspace novo;
mesmo sem submissão confere os inputs e verifica a ponte fornecida.

O vínculo candidato vem de artefato externo e o selo deve ser retido fora
dos rastros. Não infere procedência, aprovação de conteúdo, barreira de
fases ou conciliação externa a partir da consistência local. Essas
exigências ficam para o lançador/auditor do lote, próximo componente.

105 testes específicos aprovados, quatro com Lean/sandbox real. Cobertura
inclui todas as vinte posições receptoras, falsificação coordenada dos
resumos, alteração de bytes/recibos, custos, protocolo, interrupções e
aceitação falsa rejeitada pela nova verificação. Blueprint preservado.
O timeout do CI passa de 10 para 20 minutos para acomodar a suíte; nenhum
limite de sessão, dado ou critério científico muda por isso.

Falta integrar propositores/revisão de conteúdo/receptores com unicidade,
barreira, recibos, reservas e conciliação, depois congelar plano final e
realizar preflight. O diagnóstico continua não admitido.

## Diário de ciclo de vida do lote implementado — 08/09

Novo `transfer_lifecycle_v1.py` e
[contrato operacional](CICLO_DE_VIDA_LOTE_TRANSFERENCIA_V1.md). Registra
intenções únicas na matriz, até duas sessões em andamento, encerramentos,
auditorias, primeiro julgamento de conteúdo e barreira anterior a todos
os receptores. Nova admissão aguarda auditoria de sessões já encerradas.
Rejeição/ausência de ponte mantém exclusões explícitas sem reposições.

Diário com trava, encadeamento de hashes, compare-and-swap, gravação durável
e detecção de alteração/incompletude. Falha técnica suspende novas admissões
e preserva sessões em andamento e custos incertos. Não há recuperação
automática de cauda parcial, nova tentativa de célula ou troca de julgamento.

109 testes próprios, incluindo competição entre processos; regressão com
matriz/análise: **187 passed em 1,55 s**. Este componente verifica cronologia
de referências, não conteúdo dos recibos nem orçamento global; não chama
modelos, auditores, Lean ou conciliação e não admite o experimento.

Próximo: conectar executores/auditores/revisão ao diário, com posse de
worker, gate financeiro, fluxo mascarado e auditoria independente do lote;
depois plano final/preflight. Blueprint e componentes fechados preservados.

## Ensaio integrado sintético validado — 08/09

Novo `transfer_rehearsal_v1.py` e
[contrato do ensaio](ENSAIO_INTEGRADO_TRANSFERENCIA_V1.md). Conecta os seis
propositores, selagem/auditoria, revisão mascarada, barreira e até vinte
receptores com respostas previamente gravadas. Preserva as 26 posições,
os bytes finais da ponte e os controles contemporâneos, sem impor sucesso
no visível como condição adicional de transferência.

Falhas depois da intenção durável ficam técnicas/pendentes, inclusive se
falhar apenas o checkpoint posterior ao append. Revisão pendente impede
receptores; rejeição exclui apenas candidatos. Integridade do pacote é
conferida entre sessões, ao redor da revisão e no fechamento, com manifesto
externamente referenciável; alteração não produz sucesso silencioso.

**39 testes passaram em 355,47 s**, incluindo Lean real nas duas famílias;
regressão de diário/matriz/análise **187 passed em 2,38 s**. Integração tem
job separado no CI sem reduzir cobertura ou alterar limites científicos.

Isto é ensaio de engenharia, não coleta ou lançador experimental pronto.
Projeções permanecem sem interpretação científica até auditoria do lote e
conciliação próprias. Próximo: auditor independente do pacote inteiro,
posse do worker e admissão financeira, depois plano final/preflight/CI.

## Auditor independente do pacote sintético validado — 08/09

Novo `transfer_batch_audit_v1.py` e
[contrato operacional](AUDITOR_LOTE_TRANSFERENCIA_V1.md). Reconstrói o pacote
completo do ensaio sem chamar o integrador ou os runners: inventário e três
referências externas, diário/checkpoints, todas as sessões, revisão registrada,
vínculos das pontes candidatas, exclusões, custos internos, dataset e resumo.
Verifica os julgamentos já emitidos, sem reavaliar conteúdo semanticamente.

**43 testes passaram em 216,57 s**, incluindo recusa pelo Lean real de uma
aceitação sintética falsa; regressão **187 passed em 1,72 s**. Alterações
coordenadas com novos hashes não dispensam as verificações internas. Pacotes
parciais/técnicos permanecem bloqueados e preservados, sem imputação ou retry.

O perfil implementado aceita somente pacotes sintéticos completos. Sua
aprovação não autentica provedor, revisor ou contabilidade externa; análise e
admissão experimental continuam bloqueadas. Próximo: posse vitalícia do worker,
conciliação/admissão financeira e perfil de evidência experimental integrado
ao plano final/preflight/CI. Não repetir este auditor como preparação nova.
