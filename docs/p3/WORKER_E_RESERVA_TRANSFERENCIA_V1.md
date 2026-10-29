# Execução única e reserva financeira de transferência v1

Componentes: `transfer_worker_v1.py` e `transfer_budget_v1.py`. São controles
operacionais a integrar ao lançador experimental, não uma admissão completa.
Não alteram o desenho de dois mundos, as 26 posições ou o regime dos modelos.

## Posse do worker

`WorkerClaim` cria exclusivamente um arquivo permanente por identificador de
lote e mantém sua trava pelo tempo de vida do contexto. O diretório de registro
e o identificador precisam ser canônicos, definidos pelo plano final e usados
por todas as cópias cooperantes. Trocar registro ou identificador para contornar
uma tentativa anterior não é permitido. O mecanismo não é uma trava distribuída
entre máquinas ou cópias com registros diferentes.

Uma saída normal, exceção ou morte do processo nunca apaga o claim. Não existe
prazo de expiração, tomada de posse por PID aparentemente morto, retomada de
intenção incerta ou reinício automático. O contexto fecha seus descritores,
mas deixa o arquivo para impedir uma segunda execução. Uma criança criada
por fork não é o dono e não pode liberar a trava do pai. Os descritores não
são herdados por exec.

Antes de cada admissão e requisição externa, `assert_owned` deve verificar
PID do processo, identidade do registro/arquivo, links e bytes originais.
Isso detecta perda de posse observada; não é sandbox contra código hostil do
mesmo usuário. A propriedade depende da integridade do host e dos caminhos
canônicos. O claim vincula o hash do plano, mas não afirma que ele foi aprovado.

## Conciliação externa e reserva

`TransferBudget` acrescenta uma única reserva de **US$50** ao diário Claude/AWS
existente, usando o mesmo flock e esquema compatível com `aws_daily_budget.py`.
O módulo histórico permanece intacto. O total diário considera reservas ainda
abertas de dias anteriores. Não há settlement, liberação por timeout, compra,
recarga ou alteração de limite nestes novos componentes.

O chamador deve fornecer um recibo de conciliação separado, seu hash retido
externamente e uma allowlist de conciliadores. O recibo declara o snapshot do
diário, o dia civil em `America/Sao_Paulo`, horário UTC, escopos externos
reconciliados, referências de evidências, limite superior de uso não registrado
e compromissos abertos não registrados. Esses dois últimos valores devem
excluir o que o diário já cobre, evitando dupla contagem.

A declaração explícita de contabilidade externa completa é necessária; não
é inferida de um diário vazio, de saldo disponível, de Cost Explorer atrasado
ou da ausência de processos locais. Hashes/allowlists não provam identidade,
honestidade ou completude da declaração. Este não é um teto imposto pela AWS
para agentes que ignorem o registro comum. A coleta exige coordenação e
conciliação efetivas, além da validade estrutural do recibo.

Na reserva, sob trava, deve valer:

`compromissos locais + uso externo superior + compromissos externos + 50 <= 150`.

O recibo tem validade operacional máxima de 30 minutos e somente no dia civil
observado. Na virada do dia ou em mudança do diário por outros agentes, uma
conciliação atualizada é necessária. A reserva existente não expira com essa
exigência. Os decimais são tratados com precisão suficiente para os valores
limitados do contrato, inclusive diferenças menores que a precisão padrão.

## Antes de requisições e falhas

`check_before_request` verifica novamente posse, hash externo do recibo de
reserva, vínculo ao plano/lote, reserva presente e ainda não liquidada,
conciliação atual e limite do dia. Pode reutilizar o recibo de conciliação da
admissão se a única mudança do diário foi a própria reserva e o prazo/dia
continuam válidos. Não cria reserva nova, não executa cliente e não marca
`inference_admitted` como verdadeiro.

Trava ocupada impede a operação imediatamente. Arquivo parcial, troca de
inode/diretório, link, inconsistência de evento ou erro de gravação bloqueiam
novas admissões sem reparo. Se o append pode ter ocorrido, a reserva fica
preservada; não se tenta novamente com outro nome. Settlement encontrado
durante execução interrompe o gate, em vez de presumir que o worker recebeu
novo orçamento. A exceção não se transforma em falha matemática ou U=0.

Perfis sintético e experimental são explícitos. Injeção do relógio é permitida
apenas no perfil sintético. Testes usam diretórios temporários, sem escrever
no diário AWS real ou criar claims da coleta. Ainda faltam ligação ao plano
executável, critérios de publicação/CI/preflight, procedência experimental e
integração ao cliente antes de qualquer requisição real.

Validação local: **53 testes novos**, mais **14 testes do diário histórico**,
total **67 passed em 0,41 s**. Inclui concorrência entre processos, queda,
fork, alteração de identidade/bytes, erro ambíguo de fsync, relógio regressivo,
virada civil do dia, mudança do diário por terceiros e precisão decimal no
limiar financeiro. Compileall e diff-check aprovados; blueprint congelado
preservado. Esses resultados verificam controles locais, não uso externo AWS.
