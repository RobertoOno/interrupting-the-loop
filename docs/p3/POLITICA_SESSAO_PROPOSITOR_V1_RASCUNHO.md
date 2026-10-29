# Sessão propositora: término, revisão e escolha da ponte

**Rascunho prospectivo de desenvolvimento — 08/09/2026.**
Componente implementado e testado, ainda sem plano congelado ou admissão
do diagnóstico. Não altera os experimentos anteriores.

## Interface e orçamento

`production_runner_v1.py` implementa uma sessão nova. Recebe explicitamente
o cliente; não constrói credenciais, não contém lançador de lote e não
consulta irmãos. O futuro lançador deve validar congelamento/ambiente/CI,
conciliar consumo e registrar reservas diárias/do lote **antes** de passar
um cliente real. A existência desta função não substitui esses portões.

Configuração proposta: Opus 5/high, perfil `main-account`, região
`us-east-1`; 16.384 tokens por resposta, 20 mil de saída e 200 mil de entrada
totais, 600 s por sessão, até 12 requisições, 300 s por requisição. O
executor rejeita configurações acima desses tetos e mudanças silenciosas
de modelo/perfil/região/esforço. Limites menores existem para testes locais;
o plano do lote deverá exigir a configuração maior exata, não apenas estes
limites superiores. Não há controle de concorrência neste componente;
o lançador deverá impor no máximo duas sessões em paralelo.

Cada chamada de inferência é precedida da contagem nativa com o mesmo
corpo de mensagens, sistema e ferramenta. `build_production_request` é
compartilhado com o futuro preflight de pareamento D/C2. Reutiliza-se o
orçamento conservador de tokens existente: reserva de entrada contada
mais 10% e 1.024 tokens; saída limitada pelo menor entre teto por resposta
e saldo de saída. A entrada reservada acumula conservadoramente, não é
substituída pelo consumo menor observado. Não há continuação automática
quando não couber uma próxima requisição. Contagem tem timeout máximo
30 s; conferência Lean tem no máximo 120 s compartilhados entre comandos;
ambas consomem o prazo remanescente da sessão.

O cliente deve expor `max_retries=0`. Não há retry na aplicação ou fallback
de modelo. A reserva externa proposta permanece US$1,65 por sessão;
tarifas, ambiente, conciliação e plano ainda precisam ser conferidos antes
da admissão. O diário local não é um limite de cobrança imposto à conta AWS.

## Uma chamada, duas saídas completas

A única ferramenta é `check_submission`. Recebe exatamente
`bridge_source: string` e `solution_source: string | null`, ambos obrigatórios.
`null` omite explicitamente a solução visível; string vazia é um arquivo
submetido, não ausência. Não aceita nomes de arquivo arbitrários.

Uma chamada completa substitui **ambos** os arquivos. Antes da substituição,
os bytes e hashes são preservados em um diretório novo de revisão. Se a
solução for omitida em uma revisão posterior, o arquivo de trabalho anterior
é retirado; sua cópia histórica permanece. Não há aproveitamento silencioso
de solução antiga com ponte nova.

O contrato verifica a ponte só contra Base e a solução visível separadamente.
O relatório deve vincular os mesmos bytes, base, namespace e declarações;
inconsistência entre verificador e executor é falha técnica. O feedback
ao modelo contém apenas os dois estados e seus erros, no máximo 10 mil
caracteres de erro por componente, com indicação explícita de truncamento.
O relatório bruto completo é preservado. Não há feedback de irmãos,
utilidade da ponte, fonte ocultada, oráculo ou seleção de família.

## Regra de seleção e término

Identificador: `last_complete_submission_no_valid_fallback_v1`.

Vale a **última submissão completa**, por ordem cronológica, não a última
ponte válida do histórico. Portanto uma ponte válida anterior pode ser
descartada se o modelo entregar uma versão inválida por último. O histórico
fica disponível para diagnóstico de produção/revisão, sem transferir
seletivamente versões antigas ou escolher pela utilidade nos irmãos.

Termina na primeira ocorrência aplicável:

- Ponte e solução visível verificadas: encerra imediatamente, sem pedir
  mais uma resposta ou tentar melhorar a ponte.
- Resposta final sem ferramenta ou recusa: encerra; conserva como candidata
  a última submissão completa, se houver.
- Resposta truncada (`max_tokens`): encerra; não executa ferramentas presentes
  nessa resposta, mesmo se parecerem completas. Não extrai código da prosa
  nem substitui os arquivos por fragmentos. Conserva a última submissão
  completa anterior, se houver.
- Limite de requisições, tokens ou tempo antes de nova chamada: encerra
  com a última submissão completa e verificada. Não muda limites ou células.
- Ferramenta desconhecida, múltipla, identidade repetida ou argumentos fora
  do contrato: saída de protocolo inválida, sem ponte selecionada e sem
  recuperação da anterior. É resultado de produção/protocolo, não prova
  de incapacidade matemática.
- Falha técnica: suspende a admissão, preserva rastros e não entrega ponte
  para transferência automática, mesmo se houver verificação parcial válida.

Se a última ponte for válida, a ausência/rejeição da solução visível **não**
impede elegibilidade para transferência. Se a ponte for inválida, não há
artefato selecionado. Se não houver submissão completa, registrar ausência.
Sem códigos de resultado intercambiáveis: `valid_bridge`, `invalid_bridge`,
`no_complete_submission`, `invalid_protocol_output` ou
`not_interpretable_infrastructure`. A etapa de análise deverá distinguir
ausência/invalidade de U=0 medido com uma ponte válida; este executor não
calcula U nem aplica testes inferenciais.

## Rastros, falhas e contabilidade

O diretório de sessão deve ser novo e separado do workspace; outputs prévios
são rejeitados antes de contato com o cliente. Registra:

- Input exato, hashes de interface/arquivos, configuração e política;
- Classe do cliente e presença de verificador injetado, para não confundir
  testes sintéticos com execução do provedor;
- Sequência, timestamp UTC, tempo monotônico, contagens nativas, reservas,
  corpos completos dos pedidos/respostas e limites/durações das chamadas;
- Toda submissão, hash, relatório bruto, feedback e motivo de término;
- Artefato final de ponte com bytes e proveniência, quando elegível.

Mensagens anteriores são copiadas, não objetos mutáveis compartilhados.
Blocos de raciocínio/assinaturas do provedor são preservados sem editar;
isso não constitui evidência de mecanismo neural. Outputs, artefatos e
metadados de sessão não são acrescentados aos inputs do modelo. O plano
do lote deverá exigir cliente real aprovado e `checker_injected=false`.

Timeout de inferência ou resposta sem uso auditável conserva reserva
incerta. Uso inválido/acima da reserva ou modelo reportado divergente exige
`accounting_complete=false` e `external_reservation_must_remain_open=true`;
não conciliar usando apenas um custo parcial ou `uncertain_request=false`.
Um modelo divergente não tem sua tarifa presumida igual à solicitada.

Falha do verificador, recurso Lean, recibo, workspace ou formato do provedor
interrompe novas admissões. Guarda logs e eventual ponte parcialmente
verificada. Se o próprio registro em disco falhar e a função lançar exceção,
o chamador deve conservar **toda a reserva externa** e suspender o lote.
Nenhuma exceção autoriza repetir a sessão. Os custos por tokens usam tarifas
configuradas e escrita de cache conservadora; não são fatura da AWS.

## Pendências antes do lote

Testes de sessão e integração local não substituem auditoria independente
do lote. Ainda faltam contagem nativa D/C2 e tolerância, matriz/ordem, análise
e critérios de avanço, auditor/reconstrutor de rastros, orquestração das
reservas/concorrência e admissão congelada com preflight/CI. O receptor
deverá receber somente os bytes selecionados, recompilados pelo contrato
em ambiente novo; não ler diretamente a pasta de revisões. Revisar também
seu adaptador de execução para a mesma política de falhas técnicas; não
presumir que o executor histórico implemente as novas regras. Revisão de
conteúdo/cegamento do artefato continua necessária: isolamento de arquivos
e validade Lean não certificam, por si só, ausência de cópias textuais
indevidas no conteúdo produzido pelo modelo.

Continuam os seis propositores D0/D/C2 em ambos os mundos expostos e até
vinte receptores/controles contemporâneos, máximo 26 sessões. Não há
promoção à principal, H2 confirmatória, P3B ou mecanismos por implementar
este executor. Fixtures-oráculo dos testes são instrumentação conhecida,
nunca pontes produzidas pelo modelo ou controles novos do diagnóstico.
