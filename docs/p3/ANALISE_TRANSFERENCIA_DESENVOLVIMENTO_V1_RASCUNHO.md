# Análise e decisões do diagnóstico de produção/transferência

**RASCUNHO PROSPECTIVO — 08/09/2026 — NÃO CONGELADO.**
Complementa o [desenho de até 26 sessões](PRODUCAO_TRANSFERENCIA_DESENVOLVIMENTO_V1_RASCUNHO.md).
Não altera o pré-registro principal, protocolos S16/v3 ou evidências encerradas.
Matriz e regras abaixo já têm implementação/testes separados, descritos em
[Matriz e análise executáveis](MATRIZ_E_ANALISE_TRANSFERENCIA_V1.md). O plano
completo ainda precisa de auditoria, receptor, orquestração e revisão antes
de respostas experimentais de produção/transferência.

## Inventário e dependências

Conservar os mesmos dois mundos expostos, invariante e representação. Para
cada mundo: três propositores D0/D/C2; dois receptores por ponte final válida
e elegível; dois controles sem ponte (B); dois com ponte-oráculo (O).
Máximo: seis propositores, doze receptores candidatos, quatro B e quatro O.
Ponte inválida/ausente não gera receptor, mas suas duas posições continuam
no inventário, com motivo explícito. Não substituir a ponte, o mundo ou a sessão.

A matriz de posições é fixada antes das respostas. Primeiro terminam os seis
propositores e a auditoria de seleção/artefato; nenhum resultado de irmão é
usado para escolher ponte. Depois executam-se os vinte lugares possíveis de
receptores/controles, saltando apenas os inelegíveis pela produção. As ordens
de ambas as fases estão definidas no blueprint por ranking SHA256 com a
semente de ordem 2026090802; serão vinculadas no plano final, sem escolher
ou reordenar a partir de sucesso. Concorrência máxima dois; falha técnica
suspende novas admissões e preserva o que já estiver em curso.

Todos os controles serão novos. A mesma baseline de cada mundo/irmão participa
dos três contrastes D0/D/C2 e do contraste O. Isso **não** fornece baselines
independentes para cada braço. Irmãos, condições e revisões tampouco são
unidades independentes de inferência; há apenas dois mundos, um por família.

## Escores separados

Para mundo w, braço a e irmão j, registrar a solução binária do receptor
`Y[w,a,j]` e do controle `B[w,j]`. Para uma ponte válida, elegível e com os
dois receptores tecnicamente válidos:

`U[w,a] = ((Y[w,a,1] − B[w,1]) + (Y[w,a,2] − B[w,2])) / 2`.

U pode ser negativo; não truncar no zero. A mesma fórmula calcula U do
oráculo contemporâneo. Reportar também os quatro resultados individuais,
e não somente o saldo: ganhos em um irmão podem ocultar perdas no outro.

Guardar separadamente validade formal da ponte, elegibilidade de transferência,
solução visível, motivo de término, número de revisões e desfecho de produção.
Ausência/invalidade de ponte ou violação do contrato de saída recebem
**U de produção convencionado em zero**, sem inventar receptor ou taxa de
solução com ponte. Marcar `utility_measured=false`; não misturar esse zero
com `utility_measured=true` de ponte válida que efetivamente não ajudou.

Ponte válida com solução visível ausente/rejeitada continua elegível pela
política de sessão. Resolver o visível não é pré-requisito nem substituto
para utilidade. Uma falha técnica, um rastro inconsistente ou uma auditoria
pendente recebe estado não interpretável, nunca U=0 ou ausência comportamental.

Reportar, descritivamente, `U_D − U_C2`, `U_D − U_D0` e a matriz
solução-visível/utilidade. Não usar os testes de oito mundos, p-valores
de sessões/irmãos, bootstrap de duas famílias ou declarar H2 confirmada.
Vantagem de C2 ou D0 também é resultado a preservar. O contraste D/C2 não
mede invenção: D recebe uma fonte estruturalmente alinhada.

## Árvore de decisão proposta, anterior aos dados

Aplicar nesta ordem, mantendo disponíveis todos os resultados brutos:

1. **Integridade e completude.** Exigir todos os propositores e controles
   planejados, os dois receptores de cada ponte elegível, rastros reconstruídos,
   verificações isoladas e contabilidade conciliável. Posições legitimamente
   não executadas por falha de produção não tornam o lote incompleto. Qualquer
   falha técnica/auditoria pendente interrompe a decisão científica; não admitir
   reposição automática nem aumentar o orçamento de uma célula.
2. **Controles contemporâneos.** Exigir os quatro pares B/O, O≥3/4,
   B≤2/4 e ganho líquido O−B≥2/4, como portão operacional de desenvolvimento.
   Não é o H1 confirmatório da principal. Separar insuficiência do oráculo,
   teto de baseline e ganho insuficiente; registrar cada família mesmo que
   o agregado passe. Falha desse portão impede interpretar ausência de
   transferência como limite de produção de rotas.
3. **Produção e transferência.** Com controles adequados, ao menos uma
   ponte candidata com U medido >0 é sinal mínimo para preparar o estudo
   independente de replicação/eligibilidade. Não exigir que o sinal venha
   de D, nem que D>C2, para preservar achados contrários à hipótese. Essa
   existência não confirma efeito de fonte, generalização ou invenção.
4. **Ausência de transferência positiva.** Com controles adequados e
   nenhuma ponte candidata com U medido >0, encerrar este diagnóstico e
   examinar todas as falhas: não produção, invalidez, revisão que perdeu
   ponte boa, resolução apenas local, ponte válida inútil ou prejudicial.
   A decisão é revisar a hipótese operacional antes de nova bateria, não
   repetir até obter efeito, aumentar modelo/limites ou declarar teto geral.

O limiar do terceiro item é deliberadamente mínimo e descritivo: os dados
servem para decidir o próximo desenho, não para demonstrar uma lei com duas
unidades. Uma replicação deve examinar a matriz inteira e seus controles,
sem selecionar apenas o braço/família favorável. Falar em limite exige
especificar o que de fato foi testado e os controles que excluíram outras
explicações; um zero isolado não encerra a linha de pesquisa.

## Portões ainda separados

Após este diagnóstico seguem elegibilidade/novidade dos mundos, preparação
da amostra principal e confirmação independente conforme seus próprios
protocolos. Instância com nova semente não é nova estrutura. P3B remove o
análogo fornecido e tem desenho próprio. A investigação de ativações continua
um módulo posterior: não substitui medir produção, transferência e robustez
comportamental, nem recebe admissão automática de um ganho ou de um teto.

Matriz/ordem, hashes, script e testes de análise estão implementados, com
blueprint próprio ainda não admitido. Antes do congelamento completo faltam:
auditor de rastros; política operacional de conteúdo da ponte e cegamento;
adaptador do receptor com a nova classificação de falhas;
reserva/concorrência/admissão; preflight e publicação/CI do executor final.

A auditoria de conteúdo não pode escolher uma ponte por parecer promissora,
exigir semelhança com o oráculo ou consultar irmãos. Deve tratar cópias
indevidas de fonte/conversa/solução segundo regra anterior aos dados. Não
remover texto, recuperar revisão anterior ou reparar silenciosamente o
artefato selecionado. Validade Lean e isolamento de arquivos, sozinhos,
não resolvem esse requisito; a regra precisa estar operacional antes do lote.

**08/09 — componente de auditoria dos propositores implementado.**
O [auditor independente de rastros](AUDITOR_RASTROS_PROPOSITOR_V1.md)
reconstrói a sessão, recompila cada revisão e fornece a projeção propositora
exigida pela análise. Não autentica a origem do provedor, não concilia o
orçamento externo e não aprova conteúdo da ponte. Sessões técnicas ou
inconsistentes não recebem projeção matemática. A aprovação de uma sessão
não aprova a barreira, os receptores ou o lote completo; essas partes
seguem pendentes, com a política de conteúdo como próximo componente.

**08/09 — revisão operacional do conteúdo implementada.**
[Política e recibos](CONTEUDO_E_CEGAMENTO_PONTE_V1.md) separam admissibilidade
do conteúdo de mérito/utilidade matemática. Cinco critérios e flags
explicitamente avaliados por revisor identificado; julgamentos claros,
violação ou incerteza derivam `passed/rejected/pending`. Não há classificador
semântico automático ou veto por semelhança com fonte/oráculo. Rejeição
mantém validade Lean e hash, diferindo de invalidade formal; incerteza
mantém o bloqueio da análise, sem U=0. O recibo vincula uma projeção nova,
sem alterar a saída original do auditor. Permanecem pendentes o fluxo real de
mascaramento, unicidade/barreira do lote, receptor e admissão/conciliação.
