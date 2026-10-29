# Ensaio integrado de produção e transferência v1

Status: integração **sintética**, não lançador experimental nem resultado de
pesquisa. Implementação em `transfer_rehearsal_v1.py`; cenários de teste em
`tests/test_p3_transfer_rehearsal_v1.py`. Não modifica o blueprint ou componentes
históricos selados.

## O que conecta

O ensaio usa os materializadores, executores de sessão, auditores independentes
de rastros, revisão de conteúdo e diário de ciclo de vida existentes. O cliente
consome exclusivamente respostas JSON previamente fornecidas: não aceita um
cliente externo, fábrica de cliente, credenciais ou SDK de provedor. Os
verificadores Lean podem ser reais ou fixtures explicitamente injetadas.

A entrada contém todas as 26 posições fixas, mesmo quando uma ponte ausente ou
inelegível fará seus dois receptores serem excluídos. Cada posição contém até
12 pares `input_tokens`/`response`. Não existe seleção adaptativa de cenários
durante a execução. Uma resposta gravada é um dado sintético, não uma resposta
autenticada do provedor cujo identificador aparece no JSON.

1. Materializar e executar cada um dos seis propositores, em ordem fixa.
2. Selar os arquivos brutos e auditar cada sessão antes da próxima admissão.
3. Preparar todos os pacotes de revisão depois das seis auditorias. A preparação
   refaz a auditoria do propositor; ambas as versões ficam preservadas, e suas
   projeções precisam concordar.
4. Entregar ao callback apenas uma cópia do pacote mascarado, em ordem de
   identificador opaco. Registrar o primeiro julgamento permitido por ponte.
5. Somente com conteúdo resolvido, registrar a barreira e percorrer os vinte
   receptores fixos. Transferir os bytes exatos da ponte selecionada, ou registrar
   a exclusão explícita do receptor candidato inelegível. Executar B/O novos.
6. Guardar projeções, análise bloqueada e manifesto de integridade do pacote.

O processamento é sequencial, portanto respeita o máximo de duas sessões
simultâneas sem exercitar paralelismo entre sessões. A concorrência do diário
possui seus próprios testes; isto não é uma validação de workers concorrentes.

## Falhas e revisão pendente

Uma falha antes da intenção de início não inventa uma sessão. Uma falha depois
da intenção deixa a posição como `technical_failure`, com observação científica
nula e contabilidade pendente. Preserva o selo bruto quando ele existe. Falha
de auditoria interrompe novas admissões e não se transforma em U=0.

Falha ambígua de persistência preserva a intenção em aberto, sem tentar reparar
o diário ou recomeçar a célula. O diretório de destino precisa ser novo; não há
resume, overwrite, reposição ou retry automático.

Se o append do início já foi confirmado, uma falha posterior ao salvar seu
checkpoint externo continua sendo falha **depois** da intenção. O estado durável
prevalece sobre uma variável local que ainda não foi atualizada.
`recorded_session_count` conta intenções admitidas no diário, não chamadas ao
cliente: uma interrupção antes da primeira resposta pode consumir uma posição.

Um callback que retorna `None`, ou um julgamento explícito pendente, impede a
barreira e qualquer receptor. `None` significa ausência de decisão; um recibo
pendente já registrado não pode ser substituído neste ensaio. Em ambos os casos
o pacote fica preservado, mas não existe retomada automática desse diretório.
Um julgamento inválido é falha do processo, não rejeição matemática da ponte.

Os callbacks e verificadores injetados são código de teste confiado, não um
sandbox. Os julgamentos dos testes são fixtures, não avaliação semântica real.
A allowlist de entrada ao revisor não prova que uma pessoa ou processo externo
jamais viu o braço; esse cegamento continua sendo obrigação operacional.

## Integridade e limites

Cada arquivo escrito pelo integrador é retido por bytes e identidade local.
Cada diretório de célula é inventariado ao encerrar sua tentativa; arquivos já
retidos não podem ser substituídos nessa etapa. O pacote é novamente conferido
nos limites das sessões, antes/depois de callbacks e no fechamento. Mudanças,
entradas extras, links simbólicos/duros e substituições de inode impedem um
fechamento bem-sucedido. Leituras usam descritores relativos, `O_NOFOLLOW`,
limites de tamanho/entradas e checagem de estabilidade durante a leitura.

O inventário total aceita até 10 mil entradas, arquivos de até 256 MiB e total
de 512 MiB, sem reutilizar o limite de 256 entradas de um auditor de sessão
para o lote inteiro. São limites do ensaio sintético, não dimensionamento já
validado para a futura coleta experimental.

`closure_manifest.json` sela tipos, tamanhos e hashes de todo o pacote,
incluindo diretórios vazios, resumo, análise e diário, excluindo apenas a si
mesmo. Seu hash é devolvido ao chamador junto com o head do diário; para detectar
reescrita posterior, guardar essas referências fora do diretório. Inodes servem
à detecção local de substituição durante o processo, não à verificação de uma
cópia transportada. Hashes não autenticam autoria/procedência. Este mecanismo
não é uma barreira contra código concorrente arbitrário com o mesmo usuário.

Mesmo `complete_rehearsal` deixa a auditoria independente do lote, a conciliação
financeira e a verificação externa da barreira pendentes. A análise não revela
contrastes científicos, nem autoriza execução, principal ou mecanismos. Os
recibos de reserva/preflight/procedência são explicitamente sintéticos e não
reservam nem liberam fundos reais.

## Próximo componente

Validação local de 08/09: **39 testes passaram em 355,47 s**, incluindo um teste
com verificação Lean/sandbox real de propositores das duas famílias seguido de
interrupção técnica deliberada. Os demais cenários usam verificadores sintéticos
explícitos. Regressão de diário/matriz/análise: **187 passaram em 2,38 s**.
O teste completo das 26 posições levou 67,94 s; a suíte integrada tem job próprio
no CI, em paralelo à suíte anterior de aproximadamente 17 minutos. A cobertura
é a união dos dois jobs, ambos com timeout de 20 minutos; a integração Lean real
mantém a checagem explícita de disponibilidade, sem simular aprovação no CI.

Ainda faltam posse vitalícia do worker, conciliação/admissão financeira,
auditor independente do pacote inteiro e plano final/preflight/publicação/CI
antes da coleta. O ensaio não substitui esses portões. A sequência científica
permanece produção/transferência, replicação fora do desenvolvimento e portões
da principal; nenhuma antecipação da etapa mecanística.

O auditor do lote deverá recomputar os vínculos entre plano, inventário, diário,
rastros, julgamentos e exclusões, em vez de confiar em `summary.json` ou nas
projeções já produzidas pelo integrador. Deverá validar os recibos de conteúdo
sem emitir novo julgamento semântico, reauditar sessões com os bytes exatos da
ponte do pai e conservar contabilidade incerta. A procedência e conciliação
externa não podem ser deduzidas de um pacote internamente consistente.
