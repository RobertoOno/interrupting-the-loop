# Matriz e análise executáveis — diagnóstico de desenvolvimento

**08/09/2026 — componentes prospectivos, lote ainda não admitido.**
Implementação do [rascunho de análise](ANALISE_TRANSFERENCIA_DESENVOLVIMENTO_V1_RASCUNHO.md).
O arquivo `transfer_design_draft_v1.json` é um blueprint por hashes, com
estado `DRAFT_NOT_ADMITTED`, não o congelamento do executor completo.

## Matriz e ordem

`transfer_design_v1.py` define 26 posições: seis propositores D0/D/C2,
doze receptores candidatos condicionais, quatro baselines B e quatro
oráculos O. Mantém ambos os mundos CAL3 expostos e inelegíveis à principal.
Cada receptor candidato aponta para seu propositor e para uma baseline
compartilhada no mesmo mundo/irmão; cada O também usa essa baseline.
Nenhuma resposta histórica integra o lote novo.

IDs são opacos e determinísticos, derivados da identidade da posição. A
ordem de cada uma das duas fases usa o ranking SHA256 ascendente de
`2026090802:phase:cell_id`, com ID como desempate. É uma permutação
pseudoaleatória reproduzível, definida antes dos dados; não há busca por
uma ordem favorável. Produção ocupa posições 1–6; avaliação 7–26. A
concorrência máxima permanece dois. Saltar uma candidata inelegível não
renumera, substitui ou reordena as demais posições.

Antes de iniciar qualquer receptor, os seis propositores precisam estar
encerrados e auditados e suas decisões de transferência seladas. A ordem
concreta fica no blueprint e será vinculada pelo plano de execução final.
IDs/rótulos/filiação/baselines são **metadados do host**, não conteúdo a
entregar aos modelos. Nomes opacos não bastam para provar cegamento; isso
depende do materializador e da auditoria dos requests.

O blueprint vincula configuração maior S16, política cronológica de seleção,
mundos/arquivos, inputs iniciais dos propositores já contados e proveniência
do pareamento nativo encerrado. A preparação somente confere hashes antigos:
não reconta tokens, recompila Lean, sorteia mundos ou executa sessões.
Reserva nominal US$42,90, teto proposto US$50 e limite AWS US$150/dia
continuam parâmetros de planejamento, sujeitos à conciliação/admissão.

## Entrada auditada, não confiança no `session.json`

`transfer_analysis_v1.py` recebe a matriz e **projeções do futuro auditor**.
Não é o auditor de rastros e não autentica uma declaração externa de que
uma auditoria passou. O lançador/auditor deverá reconstruir cada projeção
dos bytes reais, vincular os hashes à execução congelada e verificar fase,
isolamento, uso/custos, término, revisão selecionada e compilação em ambiente
novo. Ler ou marcar um `session.json` não cumpre esse contrato.

O dataset exige versão, hash do blueprint, origem `synthetic`/`experimental`,
relatório de auditoria do lote, hash do plano de execução congelado separado,
estado de conciliação e todas as 26 posições. O hash de evidência de uma sessão
é do seu manifesto completo, incluindo identidade/proveniência, não só de
uma prova que poderia coincidir entre sessões; não pode ser reutilizado.
Cada posição tem estado, auditoria, contabilidade, hash de evidência e
observação. Os estados distinguem `completed`, `not_started`,
`skipped_no_bridge` e `technical_failure`. Uma posição omitida/duplicada,
reclassificada ou com campos desconhecidos é erro de integridade de entrada.

Na produção: desfecho, término, número de revisões, validade da última
submissão, existência de uma revisão anterior válida, solução visível,
hash da ponte selecionada e revisão de conteúdo. Somente `valid_bridge`
com conteúdo aprovado produz elegibilidade. Conteúdo pendente bloqueia;
rejeitado permanece um desfecho de contrato separado da invalidade formal.
A regra de conteúdo ainda será operacionalizada antes do lote; o analisador
não a inventa nem seleciona revisões para contornar uma rejeição.

Nos receptores: solução verificada/não resolvida/protocolo inválido,
indicador binário de solução e hash da ponte recebida. B exige ausência de
ponte; O exige o hash do oráculo congelado; candidatos exigem exatamente o
hash final aprovado do seu propositor. Ponte de outra revisão/experimento
não é substituto. Posições saltadas não podem conter respostas inventadas.

## Escores, bloqueios e decisões

O analisador não divulga agregados científicos parciais. Falha técnica,
posição necessária não encerrada, auditoria/conteúdo pendente ou
contabilidade não conciliada retorna `not_interpretable`, motivos e
inventário; `world_results`, `control_gate` e `contrasts` ficam nulos.
Esses estados não recebem zero nem uma conclusão matemática.

Em um inventário completo/auditado, calcula os ganhos por irmão e
`U = média(Y_com_ponte − B)` por mundo/braço. U negativo é preservado.
Ausência/invalidez/protocolo inválido/rejeição do conteúdo da ponte geram
U=0 **convencionado**, `utility_measured=false` e `with_bridge=null`, sem
imputar resposta aos receptores inexistentes. O zero de uma ponte válida
testada conserva `utility_measured=true`. Solução visível não é requisito
de transferência; são destacados casos que ajudam sem resolver o visível,
perda de revisão válida e supressão de ponte válida por protocolo inválido.

Primeiro se avaliam quatro pares B/O contemporâneos: O≥3, B≤2, ganho≥2.
Todos os motivos de falha aparecem separadamente, com resultados das duas
famílias e indicação de teto. Se o portão falhar, não se interpreta ausência
de transferência como limite de produzir rotas. Se passar e qualquer braço
tiver U medido >0, a decisão é preparar estudo independente, não admitir
principal ou mecanismos. Sem U positivo, encerrar o diagnóstico e revisar
todas as falhas antes de outra bateria. Vantagem de C2/D0 é preservada.

Contrastes D−C2 e D−D0 são descritivos. Não se aplicam H1/H2 de oito mundos,
p-valores de sessões/irmãos ou bootstrap de duas famílias. Baselines são
compartilhadas e há somente duas unidades de mundo no desenho —
expostas e estruturalmente relacionadas ao desenvolvimento, não
uma amostra aleatória que fundamente generalização estatística.

Dados sintéticos exercitam as mesmas regras, mas têm
`experimental_decision=null`, marcação explícita de simulação e nenhuma
admissão. Toda saída, mesmo experimental, declara que é análise de projeções
e não uma reauditoria dos rastros; este módulo nunca autoriza execução.

## Uso e continuação

`PYTHONPATH=src .venv/bin/python scripts/p3_transfer_development_v1.py prepare`
cria o blueprint uma vez, sem sobrescrever. `validate` reconstrói e compara.
`analyze --observations arquivo.json` analisa somente a entrada explícita;
`--output arquivo-novo.json` preserva resultados existentes. Não existe
comando `run`, cliente implícito, reserva ou gerenciamento de GPU.

Antes do lote: auditor/reconstrutor de rastros, política de conteúdo e
cegamento, receptor com a nova política técnica, orquestração de reservas/
concorrência/admissão e plano final congelado com preflight/CI. As etapas
principal, confirmação/replicação, P3B e mecanismos continuam separadas.
