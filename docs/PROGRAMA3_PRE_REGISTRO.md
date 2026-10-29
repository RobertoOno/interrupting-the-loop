# Programa 3A — Pré-registro do piloto causal de pontes

**RASCUNHO v0.2 — AMOSTRA PRINCIPAL NÃO CONGELADA — 2026-09-04.**

**Estado mais recente, 08/09:** S16 encerrada e auditada: baseline/oráculo
0/4–4/4 em 8.192, 2/4–4/4 em 16.384; ambos os portões passam. Ganho
menor e teto da baseline na família de invariante no limite maior.
Próximo passo é preparar diagnóstico de produção/transferência separado,
não congelar ou admitir automaticamente estes mundos na principal.
Registro: `docs/p3/SENSIBILIDADE_LIMITE_RESPOSTA_RESULTADOS_V1.md`.
As decisões confirmatórias abaixo continuam em rascunho, sem alteração
retroativa de critérios. Nenhum propositor executado até este registro.

**Histórico de 05/09:** calibração conceitual v3 encerrada, portão aprovado
(baseline 1/4, oráculo 4/4, ganho 3/4; oito sessões válidas). As três baselines sem
solução atingiram 8.192 tokens na primeira resposta, sem submissão; o ganho é sob
o protocolo limitado. A próxima checagem de sensibilidade está apenas em rascunho.
Nenhum propositor ou mundo principal iniciado; novidade estrutural continua aberta.
Registro: `docs/p3/CALIBRACAO_CONCEITUAL_RESULTADOS_V3.md`.

Estado após o fechamento v2: plano congelado no commit `bbc96fa` antes da inferência;
8/8 células válidas, baseline 4/4, oráculo 4/4, ganho zero. Gate não passou.
Nenhum propositor ou mundo principal executado. Resultado/evidência em
`docs/p3/CALIBRACAO_BEDROCK_V2.md`. As decisões prospectivas abaixo permanecem registradas;
o resultado não altera os dois planos congelados nem seus critérios.

Etapa de desenvolvimento posterior: dois protótipos conceituais foram implementados e
verificados apenas localmente (`docs/p3/PROTOTIPOS_CONCEITUAIS_V3.md`). Não são uma terceira
calibração nem integram a amostra: já foram vistos, não são sorteados e usam estruturas
conhecidas. Na continuação local, fontes/sham e um gerador de instâncias de desenvolvimento
foram implementados (`docs/p3/FONTES_E_GERADOR_CONCEITUAL_V3.md`). Nenhuma nova chamada
comportamental ocorreu. Esses pacotes também são inelegíveis para calibração/principal
e não satisfazem uma alegação de novidade estrutural. O próximo gate precisará de novos
fixtures, exclusões e congelamento; os critérios abaixo não foram alterados pelos testes
locais. O inventário inclui sementes de testes em `docs/p3/development_exclusions_v3.json`.

Calibração conceitual v3 preparada em 05/09: após corrigir equivalência dos inícios e
esgotamento de um estrato de palavras, dois fixtures próprios e oito sessões foram
congelados em `docs/p3/calibration_conceptual_plan_v3.json` antes da inferência.
É uma última calibração pequena do instrumento em famílias conhecidas, não o principal
e não uma validação de novidade estrutural. Modelo/interface/limites e portão causal
da v2 foram mantidos. Detalhes: `docs/p3/CALIBRACAO_CONCEITUAL_V3.md`.

Atualização antes das chamadas v2: Roberto autorizou continuar via Claude/AWS após a
estimativa de custo. O novo gate é independente da calibração Codex v1 e usa o plano
`docs/p3/calibration_bedrock_plan_v2.json`: Opus 5, dois novos mundos descartáveis e uma
ferramenta de envio/checagem de provas. Limite da calibração: US$15 a preço de lista,
antes de impostos; reserva nominal máxima de tokens = US$13,20. P3B e o módulo interno
mantêm protocolos e orçamentos separados; não entram nas 104 sessões de P3A.

A política v2 permite somente os axiomas padrão `propext`, `Quot.sound` e
`Classical.choice`, transitivamente. Novos axiomas e `sorryAx` continuam proibidos.
A política zero-axiomas do gate v1 foi preservada para seus resultados; não se reclassifica
o passado. A mudança evita medir dependências de táticas/definições legítimas do Lean
como se fossem ausência de rota. Não há comparação pareada de capacidade entre v1/v2.

Nenhuma geração ou execução da **amostra principal** está autorizada por este documento. A
calibração estrutural fixou Lean 4.33.1 sem Mathlib. O primeiro gate comportamental, somente nos
dois mundos descartáveis, foi congelado antes das chamadas em
`docs/p3/calibration_headroom_plan_v1.json`. A palavra `CONGELADO`, as sementes e os hashes da
amostra principal precisam entrar em um commit anterior à primeira chamada principal.

## 1. Pergunta

Em mundos formais inéditos com verificador exato, uma fonte estrutural relevante ajuda um agente
a produzir um lema-ponte **causalmente útil** em alvos irmãos ocultos, além do que produzem o
enunciado sozinho e uma fonte estrangeira pareada?

Este piloto testa o instrumento e a transferência de uma arquitetura formal. Ele não autoriza
concluir “invenção de rota” apenas porque D supera C2: D recebe um análogo estrutural. Invenção
sem rota análoga fornecida será o objeto de P3B, com mundos e pré-registro novos, somente se o
portão causal de P3A funcionar.

## 2. Unidade e amostra

- Unidade primária de inferência: **mundo**, nunca tentativa, chamada ou alvo irmão.
- Amostra principal: 8 mundos, 4 do molde T1 e 4 do molde T2.
- Cada mundo possui 1 alvo visível, 2 irmãos ocultos, 1 ponte-oráculo, 1 fonte relevante e
  1 fonte sham.
- Haverá uma sessão propositora por braço e mundo no piloto.
- Todos os mundos usados para desenvolver o gerador, ajustar prompts e fixar orçamentos são de
  calibração e ficam excluídos para sempre da amostra principal. Até este fechamento: dois em v1
  e dois novos em v2, quatro no total.

## 3. Braços

**D0 — alvo apenas.** O agente recebe a base, o alvo visível e o contrato de saída.

**D — fonte relevante.** Recebe o mesmo material de D0 e um exemplo resolvido de outro mundo
com a mesma arquitetura causal, mas outros símbolos e objetos.

**C2 — sham pareado.** Recebe o mesmo material de D e uma fonte correta, pareada em extensão,
número de declarações e forma superficial, cuja ponte não se aplica ao alvo.

**O — ponte-oráculo.** Recebe o material de D0 e a ponte correta. É controle positivo da
manipulação, não competidor experimental. Não há sessão propositora em O: `B*` é entregue
diretamente às sessões avaliadoras dos irmãos.

D e C2 terão entradas de tamanho casado dentro de uma tolerância fixada na calibração. Todos os
braços usam o mesmo modelo, parâmetros, ferramentas e orçamento. O prompt pede dois produtos
separados: `Bridge.lean`, que importa apenas a base, e `Solution.lean`, que prova o alvo visível.

## 4. Avaliação independente

Cada ponte válida de D0, D e C2, além de `B*` no braço O, é avaliada em `G1` e `G2` por sessões
novas. O avaliador:

- não vê `G0`, a fonte, a solução, a conversa nem o rótulo do braço;
- recebe somente a base, o alvo irmão e, na condição tratada, `Bridge.lean`;
- é pareado com uma condição sem ponte sob o mesmo modelo e orçamento;
- não pode editar a ponte nem os arquivos congelados;
- pode escrever apenas a solução do irmão.

A baseline sem ponte é executada uma vez por mundo e irmão e reutilizada nos contrastes do mesmo
mundo. A ordem das condições com/sem ponte e dos braços é sorteada antes das execuções.

## 5. Desfechos

Para cada braço e mundo:

- `visible_solved`: a solução visível compila e prova a declaração congelada;
- `bridge_valid`: a ponte compila contra a base e passa a auditoria de axiomas/sintaxe;
- `holdout_with_bridge`: proporção dos dois irmãos resolvida com a ponte;
- `holdout_without_bridge`: proporção dos dois irmãos resolvida pela baseline;
- `U = holdout_with_bridge − holdout_without_bridge`: utilidade causal da ponte;
- custo auxiliar: chamadas ao Lean, tokens, tempo e custo monetário.

Falha em produzir ponte, ponte inválida, timeout do agente ou solução rejeitada recebe `U = 0`.
Falha de infraestrutura confirmada pelo protocolo abaixo não recebe zero: a célula é refeita com
o mesmo input e o evento é registrado antes de revelar resultados agregados.

## 6. Hipóteses e testes

**Portão H1 — instrumento.** O braço O deve ter utilidade média positiva e `U_O > 0` em pelo
menos 6 dos 8 mundos. Também exigimos ganho absoluto médio de pelo menos 0,25. Se falhar, H2 não
é interpretada; o instrumento volta ao desenho.

**Primária H2 — transferência.** `U_D > U_C2`. O teste será uma permutação exata unilateral dos
oito contrastes pareados por mundo, com α = 0,05. Serão reportados os oito contrastes, média,
mediana, intervalo bootstrap sobre mundos e o p bilateral como sensibilidade.

**Secundária H3 — além do alvo.** `U_D > U_D0`, com o mesmo contraste pareado, sem afirmação
confirmatória independente; o p será reportado com ajuste Holm junto aos demais secundários.

**Secundária H4 — solução versus rota.** Associação entre `visible_solved` e `U > 0`, descritiva,
com a matriz completa por mundo. O interesse são células que resolvem `G0` sem ajudar os irmãos e
células que produzem ponte útil mesmo quando não fecham `G0`.

Não haverá teste tendo sessões ou irmãos como unidades independentes. Resultados serão mostrados
também separadamente por molde, apenas de forma descritiva no piloto.

## 7. Critérios de decisão

**Instrumento validado:** H1 passa.

**Sinal para confirmar:** instrumento validado, H2 passa e D tem `U_D > U_C2` em pelo menos
6 dos 8 mundos. Nesse caso, uma bateria confirmatória usa mundos e sementes novos, duas sessões
por braço e o mesmo endpoint.

**Hipótese não suportada:** instrumento validado, mas H2 não passa. O resultado é preservado e
publicável como limite da transferência sob o desenho.

**Instrumento inadequado:** H1 falha. Não se conclui sobre transferência; ajusta-se o gerador em
novos mundos de calibração, nunca reusando a amostra vista.

Não haverá mudança de modelo, orçamento, prompt, mundo ou regra de pontuação após a primeira
execução principal.

## 8. Validade e exclusões

Uma célula é válida quando o workspace tem os hashes esperados e o processo do agente iniciou com
o contexto correto. A decisão do agente de não chamar Lean é descumprimento comportamental e
resultado negativo, não motivo para repetição. Erro de rede do cliente, indisponibilidade do
modelo, processo morto pelo host antes do início do turno ou corrupção do workspace são falhas de
infraestrutura. Código Lean incorreto, timeout após início normal, uso de construção proibida e
exaustão do orçamento são resultados válidos negativos.

Atalhos proibidos: `sorry`, `admit`, novos `axiom`, `unsafe`, `native_decide`, `extern`,
`implemented_by`, mudança de declarações congeladas, acesso a `Hidden/` ou aos irmãos durante a
proposição, rede e busca externa.

## 9. Cegamento, vazamento e leitura

- Sementes e hashes dos mundos são commitados antes das chamadas.
- Workspaces são criados por allowlist e verificados antes e depois da sessão.
- Identificadores de braço são substituídos por rótulos aleatórios nos artefatos de análise.
- O script de análise e os testes são escritos antes da execução principal.
- A tabela agregada é aberta uma única vez depois de todas as células e verificações concluídas.
- Resultados parciais não orientam reexecução, seleção de mundo ou alteração de prompt.
- Logs completos, inclusive tentativas inválidas, são preservados fora do Git e recebem manifesto
  de checksums; resultados estáveis entram no Git.

## 10. Orçamento experimental

O piloto contém:

- 8 mundos × 3 braços propositores (D0, D, C2) = 24 sessões propositoras;
- 8 mundos × 2 irmãos = 16 baselines sem ponte;
- 24 pontes candidatas × 2 irmãos = até 48 avaliações com ponte candidata;
- 8 pontes-oráculo × 2 irmãos = 16 avaliações de controle positivo;
- total máximo: 104 sessões de agente, além de verificações Lean locais e baratas.

Os limites finais serão determinados nos dois mundos descartáveis e então copiados literalmente
para esta seção. Não haverá pod de GPU; o custo será de inferência remota e CPU local. Tokens e
tempo serão registrados por célula. O cliente autenticado por conta não expõe custo monetário por
sessão; esse campo ficará nulo em vez de receber uma estimativa apresentada como medição.

### Gate comportamental 1 — headroom (histórico; concluído)

Antes de qualquer propositor, serão executadas somente 8 sessões avaliadoras: 2 mundos × 2 irmãos
× {sem ponte, ponte-oráculo}. A configuração congelada é Codex CLI 0.153.1 (binário SHA-256
`0cf2d42e90ddd50fa5b7eedd5d72f109b68d33e5a6ce7c3fc2c87e4180edcd59`), modelo
`gpt-5.6-sol`, esforço `high`, timeout externo de 600 segundos e no máximo duas células em
paralelo. O identificador disponível é um alias sem snapshot datado; por isso versão e hash do
cliente também entram na proveniência.

O gate passa somente com os quatro pares válidos, oráculo resolvendo pelo menos 3/4, baseline
resolvendo no máximo 2/4 e ganho pareado em pelo menos 2/4. Se houver teto da baseline, criam-se
mundos descartáveis mais difíceis; o modelo não é enfraquecido para fabricar contraste. Se houver
piso do oráculo, protocolo e dificuldade são inspecionados antes de qualquer orçamento mais forte.
Não há repetição automática. Apenas uma falha de infraestrutura, registrada antes da agregação,
pode repetir a mesma célula e o mesmo input.

Cada sessão usa perfil de permissões próprio: leitura negada fora do workspace exato, salvo paths
mínimos do sistema e runtime Lean; escrita apenas no workspace; rede de comandos, busca web, apps,
plugins, skills, hooks, browser, computer use e multiagente desativados. Um preflight sem modelo
confirma negação do oráculo oculto e da rede, escrita local e compilação Lean.

**Resultado v1:** oito células válidas, sem falha de infraestrutura; após corrigir um bug de
resolução de namespace no scorer e reavaliar os mesmos arquivos sem nova chamada, baseline 3/4,
oráculo 4/4, ganho pareado 1/4. O gate não passou por teto da baseline. Conforme a regra acima,
esses fixtures ficam encerrados e serão substituídos por mundos descartáveis mais difíceis antes
de qualquer propositor. Ver `docs/p3/CALIBRACAO_HEADROOM_V1.md`.

## 11. Sequência antes do congelamento

1. Implementar gerador, verificador, isolamento e telemetria sem conectar modelos.
2. Escrever testes dos atalhos, vazamentos e hashes.
3. Gerar dois mundos de calibração, confirmar não vacuidade e passagem do oráculo e verificar que
   o transplante mecânico pré-especificado do sham falha.
4. Conectar um agente apenas aos mundos descartáveis; fixar prompt e orçamento.
5. Revisar manualmente se os mundos medem seleção de rota, não erro de sintaxe ou adivinhação de
   nomes.
6. Preencher versão de Lean/Mathlib, modelo, parâmetros, orçamento, sementes e hashes.
7. Commitar o documento como `CONGELADO`.
8. Só então gerar/executar a amostra principal.

Estado em 2026-09-04: passos 1–3 concluídos; duas versões do passo 4 congeladas e executadas.
O gate v1 falhou por teto da baseline (3/4) apesar de o oráculo passar 4/4. Em v2, baseline e
oráculo passaram 4/4, todos na primeira submissão, sem ganho. Os quatro fixtures têm
`phase=calibration` e `eligible_for_main=false` em metadados hasheados e estão encerrados.
O passo 4 retorna ao desenho local: a estrutura ainda sugere a indução que resolve o problema;
aumentar apenas seu tamanho não validou a medida. Amostra principal e propositores continuam
bloqueados. Não há comparação de modelos entre v1 e v2.

## 12. Decisões recomendadas ainda abertas

- Redesenhar o gargalo conceitual e depois testar headroom em novos fixtures; a calibração
  Bedrock v2 com `anthropic.claude-opus-5`/`high` não o confirmou. Modelo e ferramentas serão
  os mesmos em todos os braços de qualquer bateria principal; não comparar resultados de
  provedores/harnesses como se fossem execuções equivalentes.
- Lean fechado em 4.33.1, sem Mathlib; qualquer mudança exige novos fixtures e novos hashes antes
  da calibração comportamental.
- Manter 8 mundos; reduzir para 6 diminui custo, mas deixa o teste pareado excessivamente discreto.
- Fazer uma revisão humana cega dos oito pacotes apenas quanto a vazamento, trivialidade e
  fidelidade ao molde, sem mostrar resultados de agentes.

## 13. Calibração Bedrock v2 — emenda prospectiva registrada antes das chamadas

O plano v2 foi commitado antes da primeira inferência (`bbc96fa`). T1 acrescenta modos indexados e
composição de rotas; T2 usa termos com variáveis e vínculo local, exigindo uma lei de
transporte generalizada para ambientes relacionados. O objetivo é exigir generalização,
em vez de expandir uma expressão finita maior. São novos mundos excluídos da amostra principal.

Cada avaliador recebe apenas os arquivos permitidos, em uma conversa nova. Dispõe de uma
única ferramenta `check_solution`, que recebe o arquivo completo, compila em diretório
limpo sem caches herdados e verifica assinatura e axiomas. Uma prova aceita encerra a
sessão; uma rejeição retorna o diagnóstico do compilador. A ferramenta não oferece leitura
de arquivos, shell nem rede ao modelo. O compilador roda isolado por filesystem e rede.

Limites iguais por célula: 12 chamadas, 600 segundos, até 200.000 tokens de entrada reservados
e 20.000 de saída; no máximo 8192 de saída por chamada e duas células simultâneas. Contagem
prévia gratuita de tokens com margem de 10% + 1024, contabilização de uso e reserva máxima
da chamada antes de enviá-la. Uma resposta incerta mantém a reserva e não é repetida.
O limite é uma guarda da aplicação a preços publicados, não um teto de cobrança imposto pela AWS.

Portão idêntico: quatro pares válidos, oráculo ≥3/4, baseline ≤2/4, ganho líquido ≥2/4.
Amostra principal e propositores só avançam após validação do instrumento e congelamento
próprio. A calibração não seleciona resultados para inflar a inferência principal.

Fechamento: o gate falhou com baseline 4/4 e oráculo 4/4; oito chamadas ao todo, sem repetição.
Custo estimado de US$0,3914735 pelos tokens reportados, antes de impostos/descontos. A menor
saída observada com oráculo é descritiva, não substitui o desfecho de sucesso congelado.
