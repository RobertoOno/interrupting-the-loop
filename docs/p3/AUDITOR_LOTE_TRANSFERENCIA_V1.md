# Auditor independente do pacote de transferência v1

Implementação: `transfer_batch_audit_v1.py`, entrada `audit_rehearsal_batch`.
Perfil atual: **pacote sintético completo do ensaio integrado**, não adaptador
de coleta experimental nem autorização de inferência. O formato experimental
com procedência, posse do worker e recibos financeiros reais ainda precisa
de contrato e integração próprios.

## Independência e entrada

O auditor não importa nem executa o integrador, os runners de sessão ou seu
cliente gravado. Reutiliza o contrato cronológico do diário, os auditores de
rastros já validados, os contratos de workspace e o validador de recibos de
conteúdo. Independência aqui significa reconstrução a partir das evidências,
não uma segunda implementação de todos os contratos matemáticos.

O chamador fornece três referências externas: hash do manifesto de fechamento,
hash do plano do ensaio e head do diário. Também fornece a allowlist de
revisores, que deve concordar com o plano. Ler esses valores exclusivamente de
arquivos alteráveis dentro do próprio pacote não prova integridade histórica.
Reescrever coerentemente pacote **e** referências externas não é detectável
como falsificação de autoria por um esquema de hashes.

O pacote permanece somente leitura. Verificações Lean utilizam workspaces
temporários novos dos auditores de sessão. Para testes portáveis, checkers
podem ser explicitamente injetados, sempre no perfil sintético. Não há cliente
de modelo, revisão semântica nova, reparo, retry ou liberação de reservas.

## Verificações

1. Inventário próprio, limitado e baseado em descritores de arquivo; rejeita
   links simbólicos/duros, entradas não regulares, arquivos ausentes/extras,
   diretórios extras e mudanças de conteúdo/identidade durante a auditoria.
   Manifesto externo cobre tudo, exceto a si próprio.
2. Plano e cenário das 26 posições, fontes da implementação e blueprint,
   referências sintéticas de reserva/procedência/preflight. Uma troca de
   `synthetic` por `experimental` não promove o pacote.
3. Replay do diário com head externo, ordem fixa, unicidade, auditoria antes
   da próxima admissão, revisões e barreira. Todos os checkpoints externos
   de uma execução completa devem concordar com seus respectivos eventos.
4. Reconstrução dos inputs canônicos de cada workspace. Caminhos absolutos
   históricos são metadados, nunca locais a abrir; uma cópia transportada do
   pacote pode ser auditada. Os arquivos finais devem corresponder aos inputs
   imutáveis e à última submissão completa, sem arquivos de contexto extras.
5. Nova auditoria de todas as sessões executadas, incluindo todas as revisões
   e os casos sem submissão. Comparação com os recibos preservados, ignorando
   apenas os fluxos de diagnóstico stdout/stderr que podem conter caminhos
   temporários; vereditos, erros, declarações, hashes e contadores permanecem
   vinculados. A label de verificação original continua coerente com o input.
6. Vínculo dos eventos brutos ao intervalo de início/encerramento no diário;
   respostas e contagens gravadas concordam com o cenário, sem inferir que
   a identificação textual de um modelo autentique uma resposta real.
7. Reconstrução do pacote mascarado e validação do julgamento já registrado.
   Nenhum critério é julgado de novo; a estrutura, os trechos ancorados, as
   declarações do revisor e o status derivado devem concordar. A preparação
   de todos os pacotes antecede o primeiro julgamento.
8. Receptores candidatos vinculados ao pai auditado e elegível, por bytes
   exatos. Ausência ou rejeição gera apenas as exclusões candidatas previstas;
   B/O não podem ser omitidos. O analisador recompõe as 26 posições e mantém
   as dependências das baselines compartilhadas e irmãos.
9. Custos internos reconstruídos por sessão concordam com o diário e são
   somados em decimal. Dataset, análise e resumo arquivados precisam ser
   idênticos às derivações independentes, mas nunca são fonte da aprovação.

## Resultado e bloqueios

`status: passed` significa consistência de um **pacote sintético completo**.
O relatório inclui os novos recibos de auditoria, dataset reconstruído e
verificação interna da barreira. A análise permanece bloqueada e os indicadores
de procedência autenticada, conciliação financeira externa, posse do worker,
inferência, principal e mecanismos permanecem falsos. O valor somado é custo
de tokens **sintéticos**, não gasto AWS certificado.

Pacote parcial, revisão pendente, diário interrompido ou encerramento técnico
gera `BatchAuditBlocked`. Essa versão não reconstitui um resultado de pesquisa
parcial nem declara verificados todos os recibos do restante desse pacote.
Uma nova verificação Lean indisponível também bloqueia; não implica falsidade
matemática. Contradições de conteúdo/referência/inventário geram erro e impedem
aprovação. Nenhuma exceção autoriza zerar utilidade, reparar o lote ou repor
uma sessão. Arquivos e compromissos permanecem preservados.

## Limites e próximos passos

Validação local de 08/09: **43 testes passaram em 216,57 s**, incluindo uma
checagem Lean/sandbox real que rejeita a aceitação falsa de uma fixture em
pacote intacto. Um pacote completo de 26 sessões foi reconstruído; outro, com
14 sessões e 12 exclusões por ausência de ponte, foi auditado depois de copiado.
Testes também reencadeiam hashes do diário e dos recibos para separar mera
detecção de alteração das verificações de custo, intervalos e julgamento.
Regressão de diário/matriz/análise: **187 passaram em 1,72 s**.

O CI mantém a suíte anterior e os dois arquivos novos de integração/auditoria
em três jobs complementares, cada um com timeout de 20 minutos. Nenhum teste
é retirado da cobertura; a integração com Lean mantém a condição explícita
de disponibilidade do ambiente.

A allowlist, os hashes e as declarações do revisor não autenticam sua
identidade ou honestidade, nem provam ausência de exposição prévia. Callbacks
de teste são código confiado; não há sandbox contra um processo malicioso
arbitrário do mesmo usuário. A comparação de arquivos/inodes detecta alterações
observadas, não fornece autenticidade criptográfica do provedor.

Ainda faltam posse vitalícia do worker, conciliação/admissão financeira e
perfil de evidência experimental com plano final, preflight e publicação/CI.
A sequência científica segue produção/transferência de desenvolvimento,
replicação independente e portões próprios da principal; não antecipa
mecanismos nem transforma transferência de uma fonte em invenção.
