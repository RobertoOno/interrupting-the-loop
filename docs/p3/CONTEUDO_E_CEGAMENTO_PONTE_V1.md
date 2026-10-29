# Conteúdo da ponte e revisão com rótulos mascarados — v1

Política prospectiva do diagnóstico de desenvolvimento, 08/09/2026.
Implementação em `bridge_content_v1.py`, testes em
`tests/test_p3_bridge_content_v1.py`. Não muda prompts, fontes, mundos,
contrato Lean, executor, seleção cronológica ou blueprint congelados.
Não é admissão do lote e não reabre experimentos encerrados.

## Pergunta da revisão

**A ponte respeita o canal de transferência especificado?** Não perguntar
se ela é boa, inventiva, similar ao oráculo, provável de ajudar ou digna de
publicação. Uma ponte `True`, redundante ou sem utilidade esperada pode
passar no conteúdo; sua utilidade pertence aos receptores e à análise.

Isolamento de arquivos e validade Lean são necessários, mas não bastam:
um arquivo válido pode conter uma conversa em comentários, uma fonte
inteira, dados codificados ou uma prova completa do alvo visível.
Por outro lado, uma adaptação matemática legítima pode naturalmente
reutilizar nomes, definições ou padrões de prova da fonte.

Não usar distância textual, similaridade ao oráculo, proporção de tokens
copiados, novidade ou previsão de U como veto. Não retirar comentários,
renomear declarações ou "limpar" uma ponte para fazê-la passar. Os bytes
selecionados permanecem imutáveis, inclusive quando rejeitados.

## Cinco critérios, aplicados à ponte inteira

1. **Conversa/instruções.** Não transportar transcript, mensagens,
   ferramenta/feedback serializados ou instruções ao receptor/revisor,
   inclusive disfarçados/codificados. Comentários explicando matemática
   ou passos da prova são permitidos.
2. **Documento-fonte.** Não transportar a fonte como documento ou sua
   solução independente como carga adicional. Definições, intermediários
   e padrões de prova adaptados e usados no mundo-alvo são permitidos,
   mesmo com sobreposição textual. Não penalizar um braço por ter aprendido
   justamente a abstração cuja transferência estamos medindo.
   Código de prova incorporado legitimamente como auxiliar matemático pode
   ser literal; distinguir seu uso matemático de carregar um exemplo
   independente como contexto extra, sem um veto automático por tamanho/cópia.
3. **Solução visível.** Não transportar uma prova completa de G0: teorema
   renomeado, alias, wrapper, corpo inlined ou cópia em comentário também
   contam. Um intermediário geral que implica G0 como caso particular é
   permitido; implicar G0 não é, por si só, vazamento. Uma conjunção que
   embute especificamente G0 já demonstrado não vira intermediário apenas
   porque recebeu o nome `candidate_bridge`.
4. **Escopo matemático.** Somente o intermediário e auxiliares/explicações
   matematicamente pertinentes, sem cargas estranhas ao artefato. Não
   exigir elegância, novidade, força, sucesso visível ou dependência literal
   de cada auxiliar no termo elaborado. Redundância matemática não é
   automaticamente violação; dado/roteiro transportado disfarçado não é
   justificado só por estar em uma declaração Lean válida.
5. **Metadados experimentais.** Não transportar rótulo explícito de braço,
   sessão, orçamento, resultado de avaliação ou outros metadados do host.
   Namespaces matemáticos congelados e identificadores de uma adaptação
   legítima são permitidos. Reconhecer um método não equivale a receber
   explicitamente o rótulo de seu braço.

Exemplo permitido: adaptar uma quantidade conservada da fonte para os
estados da base e provar sua preservação para trajetórias gerais. Exemplo
proibido: copiar o documento com o exemplo-fonte completo para um comentário
ou declarar a prova inteira do alvo visível sob outro nome. Casos mistos
sem classificação segura permanecem pendentes; não mudar o critério com
base no desempenho posterior.

## O que o revisor recebe

Um pacote por ponte final selecionada, depois da auditoria dos propositores
e antes de qualquer receptor. Allowlist do pacote:

- instruções e cinco critérios versionados, ID opaco e hashes;
- bytes UTF-8 exatos da ponte, base e enunciado visível;
- **as duas fontes do mundo**, sem rótulo relevante/sham e ordenadas pelo
  SHA256 de seus bytes, iguais para D0, D e C2;
- sinalizações lexicais ancoradas em intervalos de bytes da ponte.

O pool comum permite distinguir documento copiado de adaptação matemática
sem revelar qual fonte foi atribuída. D0 também tem as duas referências
**na revisão**, não em sua sessão propositora. Nenhum modelo do experimento
recebe esse pool adicional: o pacote pertence exclusivamente à revisão.

Não incluir no pacote braço/célula do host, número de revisão, transcript,
`Solution.lean`, sucesso visível, oráculo, irmãos ou resultados de avaliação.
A função retorna separadamente `packet`, `binding` e `trace_audit`: somente
`packet` pode ser mostrado ao revisor. Nenhuma dessas estruturas pode ser
encaminhada ao receptor; ele receberá exclusivamente os inputs previstos
e os bytes imutáveis da ponte, se elegível.

Trata-se de **mascaramento de rótulos**, não garantia de duplo-cego. O
conteúdo matemático e os namespaces podem permitir reconhecer método/mundo;
conhecimento prévio dos mundos de desenvolvimento precisa ser declarado.
O revisor não pode receber o vínculo da candidata atual ao braço nem
consultar irmãos/oráculo para esse julgamento. Não se pode assinar uma
declaração falsa de cegamento porque o pacote, isoladamente, omite campos.

O plano final deverá identificar revisores autorizados. Pode ser um humano
ou o assistente desta conversa, sem criar outro agente ou juiz automático.
O assistente só pode assumir a revisão se o fluxo tiver mantido o vínculo
da candidata atual ao braço fora de sua vista: preparar os pacotes no host
e ler apenas os pacotes, sem abrir o mapa/transcripts. Caso esse vínculo
já tenha sido recebido, preservar a pendência e pedir revisão apropriada;
familiaridade prévia declarada com os mundos não apaga exposição à candidata.

## Sinalizações não são classificadores

O scanner local identifica marcadores como `candidate_solution`,
`VisibleStatement`, `source_solution`, cercas de código, campos de
transcript, rótulos explícitos de braço e nomes de artefatos ocultos.
Mantém posições em **bytes UTF-8**, inclusive com acentos e CRLF.

Presença de sinalização não rejeita automaticamente: o texto pode ser uma
referência matemática legítima. Ausência não aprova: payload codificado,
paráfrase, prova inlined ou alias podem não produzir qualquer marcador.
Toda ponte exige leitura integral e os cinco julgamentos, mesmo sem flags.
Não se está estimando sensibilidade/especificidade de um classificador.

## Registro, decisão e integração

`prepare_content_review` audita os rastros brutos usando o auditor existente
e só prepara pacote para ponte final válida, ainda pendente de conteúdo.
Não aceita resgatar versão anterior, avaliar produção ausente/inválida ou
substituir protocolo/falha técnica por revisão de conteúdo. Vincula hashes
da evidência, relatório de auditoria, ponte, pacote, política e implementação.
Guardar pacote, relatório e binding fora da pasta bruta; reter o hash do
binding no registro confiável do lote antes de solicitar o julgamento.

`record_content_review` recebe o bundle, o hash externo do binding, uma
lista de revisores autorizados fornecida pelo plano/chamador confiável e
um julgamento explícito. Exige identificação/tipo/descrição do revisor,
declaração de exposição prévia e atestados de leitura completa, não uso de
resultados/utilidade, não consulta a irmãos/oráculo e não recebimento do
rótulo da candidata. Atestado falso/incompleto invalida a revisão, não a
ponte: não converter problema do processo em falha de produção.

Cada critério e cada sinalização deve receber `clear`, `violation` ou
`uncertain`, com justificativa de até 4 mil caracteres. Violação/incerteza
exige intervalos dos bytes exatos e hashes dos trechos; no caso de uma
flag, o intervalo precisa tocar a região sinalizada. Violação de flag
também precisa ser classificada em um dos cinco critérios substantivos.
Não existe campo livre `passed` ou critério de "utilidade provável".

Decisão derivada, nesta ordem:

- alguma violação substantiva → conteúdo `rejected`;
- sem violação, mas alguma incerteza → `pending`;
- todos os critérios e flags claros → `passed`.

A rejeição mantém a ponte formalmente válida, seu hash e o sucesso visível
originais; muda somente a admissibilidade do conteúdo na projeção nova.
Sem reinterpretar validade formal, editar o artefato ou recuperar revisão.
Pendência impede interpretar o lote e não vira U=0. Rejeição definitiva
entra na convenção de produção prevista na análise, distinguível de
invalidade Lean e de utilidade zero efetivamente medida.

O recibo preserva o julgamento completo, autor/método, hashes, timestamp e
limites de validade. O código verifica estrutura/proveniência/atestados,
**não a verdade semântica dos julgamentos ou a honestidade do autor**.
Recibos com justificativas fictícias não são evidência experimental. Os
testes sintéticos de recibos não são validação de concordância entre
revisores ou demonstração de cegamento de sessões ainda não realizadas.

Um julgamento inicial por ponte. Não coletar vários e escolher um favorável.
A API pura não impõe unicidade ou cronologia global: o futuro lançador e o
auditor do lote deverão selar o primeiro recibo de cada posição e a barreira
antes dos receptores. Dúvida que necessite adjudicação exige registro próprio
anterior à avaliação, sem apagar o julgamento inicial ou usar desempenho.
Este v1 não implementa adjudicação automática nem reabre células.

Todos os indicadores de admissão do lote/receptor/principal/mecanismos e de
barreira permanecem falsos. `content_eligibility_only=true` significa que
somente este requisito foi satisfeito, não permissão para chamar um modelo.
Testes continuam identificados como sintéticos, inclusive com Lean real.

## Próximo passo

Validação: 71 testes específicos aprovados em 44,29 s, incluindo integração
Lean real nas duas famílias, byte ranges UTF-8/CRLF, todos os critérios,
pendência/rejeição, adulteração e invariância do pool D0/D/C2. Regressão
conjunta com auditor/matriz/análise: 261 testes em 88,19 s; os 71 específicos
foram repetidos após a clarificação final sobre reutilização literal de
código matemático. Julgamentos de teste são fixtures, não revisões reais.
Hash da política serializada:
`8eda252f4d9ef861a4e0c74b0f33ad555433d59483c7898503628ec2427dd8ce`.

Adaptar o receptor e seus rastros à política técnica nova, manter allowlist
e bytes da ponte nas chamadas reais, implementar auditoria/barreira do
lote, unicidade dos recibos, procedência, reservas e concorrência. Só então
congelar o plano completo, rodar preflight/publicação/CI e admitir coleta.
Não mudar a interface propositora para esta política; se uma mudança futura
de prompt for necessária, exige nova versão e avaliação de seus controles.
