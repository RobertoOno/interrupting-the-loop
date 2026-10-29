# Programa 3A — última calibração pequena do instrumento, v3

**REGISTRO DO CONGELAMENTO ANTES DA INFERÊNCIA — 05/09/2026.**

Atualização de fechamento: execução concluída, baseline 1/4, oráculo 4/4, ganho 3/4;
portão passou. Custo estimado US$1,357345. As três sessões sem solução terminaram
em `max_tokens` sem submissão, ressalva importante para a próxima etapa. Resultado
e auditoria completos: `CALIBRACAO_CONCEITUAL_RESULTADOS_V3.md`. O restante deste
documento registra a preparação original, anterior às chamadas.

Plano: `calibration_conceptual_plan_v3.json`, identificador
`p3a_conceptual_headroom_v3`. São oito sessões avaliadoras em dois novos fixtures de
calibração, sempre excluídos da amostra principal. Não há propositores, piloto
principal, P3B, inspeção de estados internos ou pods nesta rodada.

O congelamento precisa estar integralmente no Git antes de qualquer chamada. O
executor verifica os arquivos, não apenas a existência do plano no commit. A
preparação, a revisão local e o teste de isolamento não fazem inferência experimental.

## 1. O que foi corrigido antes do sorteio

### Alterar `n` não criava um novo problema de alcançabilidade

No desenvolvimento anterior, o início decodificado era `(n²+1,n,1)`. O primeiro
movimento incrementa `n`, e o segundo desfaz esse passo. A auditoria agora prova em
Lean que todos esses inícios, para `n` natural, têm **exatamente o mesmo conjunto de
estados alcançáveis**. Isso cobre todos os valores de `n` usados pelo gerador antigo;
mudanças afins de coordenadas não eliminam essa equivalência.

Prova: `generation_audit_v3/StartEquivalence.lean`, contra uma cópia exata da base do
protótipo preservado. Há seis auditorias axiomáticas, sem axiomas além dos três padrão.
Reprodução e resultados em `scripts/p3_generation_audit_v3.py` e
`generation_audit_v3.json`. Não se altera retrospectivamente o resultado dos testes
anteriores: eles verificavam correção e isolamento, não essa distinção entre instâncias.

O novo início decodificado é `(n²+c,n,1)`, com `XZ−Y²=c`. Desenvolvimento novo usa
apenas `c=2` e `c=3`; a calibração sorteia `c` entre 5, 7, 11, 13, 17 e 19. O caso
original tinha `c=1`, e as mutações singulares tinham `c=0`. Cada pacote prova que
valores conservados diferentes pertencem a componentes de alcançabilidade disjuntos,
incluindo a separação de todos os inícios originais `(n²+1,n,1)`.

Isso corrige a equivalência por mudança de início dentro da mesma componente. Não
prova novidade estrutural da família, ausência de outras equivalências, dificuldade
para modelos ou invenção de uma nova rota. O intermediário ainda é uma forma quadrática
conhecida. Os movimentos unitários, a política lógica e os tipos de alvo foram mantidos.

### Um estrato de palavras estava esgotado

Reconstruindo as 19 sementes de desenvolvimento da representação, mais fontes,
protótipos e pares de teste, todas as seis classes literais do primeiro irmão de
comprimento 6 já tinham sido expostas. Sortear outra semente reutilizaria uma classe.

Somente esse estrato passa a comprimento 8. Mantém-se o diagnóstico: a ação inteira
distingue os núcleos, mas a ação de bits os identifica para qualquer par de bits. O
visível permanece com comprimento 6, e o segundo irmão permanece com comprimento 8.
Todos os pares têm comprimentos e contagens iguais e não têm contexto comum não vazio.

O novo gerador declara previamente duas sementes de teste por família. Depois de
excluí-las também, restam 3 classes para o visível, 56 para o primeiro irmão e 162 para
o segundo, **antes da escolha sequencial dentro do mundo**; estes conjuntos não devem
ser somados como se fossem disjuntos. Cada escolha exclui sua classe das seguintes.
A amostragem é uniforme entre classes com um representante que satisfaz os testes,
não entre nomes de arquivos ou todas as variantes textuais de uma mesma classe.

As classes usam remoção de contexto comum, troca de símbolos, reversão de palavras
e ordem do par. Esse é um filtro literal explícito, **não um decisor de equivalência
algébrica**. A ampliação corrige a falta de casos disponíveis sob essa regra; não foi
escolhida depois de observar falhas de modelos nem é evidência de maior dificuldade.

## 2. Fixtures e revisão local

- `worlds/calibration/CAL3_I_E87C49876088749B/`: invariante, valor conservado fora das
  componentes usadas no desenvolvimento.
- `worlds/calibration/CAL3_R_F76437525B190ECB/`: representação, pares fora das classes
  de desenvolvimento declaradas.

Sementes, parâmetros, hashes e metadados completos ficam nos arquivos de reprodução;
não entram no workspace do avaliador. Os namespaces usam identificadores derivados
por hash, não a semente em claro. Os pacotes anteriores não foram alterados.

`calibration_local_review_v3.json` registra a revisão desses fixtures: quatro fontes
corretas, seis fechamentos pelo oráculo e seis pela adaptação relevante em workspaces
limpos, dezoito sondas sem ponte sem solução e duas mutações com negação do alvo
provada e rejeição do oráculo original. Os controles sham são corretos na própria
fonte, mas suas adaptações falham; há contraexemplos formais dessa compatibilidade.
Esses resultados são **locais**, não uma terceira medição comportamental.

Verificação final da preparação: suíte completa com **244 passed, 6 skipped**.
As oito células passaram o preflight: leitura fora do workspace negada, rede negada
e Lean funcional. Esses testes não chamaram o provedor de inferência.

As sondas são as mesmas: `simp`, `grind` limitado a quatro divisões em casos e `omega`,
com 200.000 heartbeats e 30 segundos por compilação. Falhas por sintaxe, infraestrutura
ou limite de recursos não são aceitas como evidência de dificuldade.

O gerador novo é `calibration_worlds_v3.py`; o antigo e seus assets continuam imutáveis.
Testes de desenvolvimento só podem usar sementes declaradas. A preparação da calibração
sorteia uma vez após excluir esses casos; se a revisão falhar, para sem chamadas,
sem sobrescrever artefatos e sem reamostragem automática.

## 3. Desenho congelado

Mantidos da v2: Claude Opus 5 (`anthropic.claude-opus-5`) via Bedrock/Mantle,
`main-account`, `us-east-1`, esforço `high`, prompt e ferramenta `check_solution`.
Limites por sessão: 12 chamadas, 600 segundos, 120 segundos por requisição, 200 mil
tokens cumulativos de entrada, 20 mil de saída e até 8.192 de saída por requisição.
No máximo duas sessões paralelas. Sem retries automáticos, fallback ou cache solicitado.

Cada mundo fornece dois irmãos; cada irmão tem uma condição sem ponte e outra com a
ponte-oráculo. São quatro pares, oito sessões independentes. A ordem é sorteada antes
da execução e cada entrada completa tem seu próprio hash. O avaliador recebe somente
base, um alvo, contrato de saída e, quando aplicável, ponte imutável. Não recebe fonte,
alvo visível, irmão vizinho, diagnósticos ou resultado de outra sessão.

Política lógica: somente `propext`, `Quot.sound` e `Classical.choice` como dependências
transitivas; novos axiomas e `sorryAx` proibidos. O verificador compara a assinatura
com o alvo congelado e recompila as fontes em diretório limpo, sem caches herdados.

O portão só passa com quatro pares válidos e, simultaneamente:

- oráculo resolve pelo menos 3/4;
- baseline resolve no máximo 2/4;
- ganho líquido pareado é de pelo menos 2/4.

Sem quatro pares válidos, a rodada é inconclusiva por infraestrutura. Não se converte
ausência de dado em fracasso de prova nem se repete silenciosamente uma sessão. Economia
de tokens não substitui o desfecho de solução. Uma nova ausência de margem de ganho
encerra esta sequência de calibrações pequenas e exige reavaliar domínio/operacionalização.

Este é um teste de **utilidade causal da ponte em famílias conhecidas**. Mesmo passando,
não autoriza concluir invenção, prior vazio ou novidade estrutural, nem inicia
automaticamente o piloto principal. P3B e mecanismos internos mantêm protocolos próprios.

## 4. Custo e controles de execução

Mantido o teto de planejamento de **US$15**, com limites de tokens que correspondem
a **US$13,20** de reserva nominal para oito sessões (US$1,65 por sessão). Não é um
pagamento nem uma reserva de saldo já realizada na AWS.

A referência consultada informa US$5 por milhão de tokens de entrada e US$25 por milhão
de saída para Opus 5; endpoints regionais adicionam 10%. O plano usa, portanto, US$5,50
e US$27,50 por milhão. Fontes: [preços oficiais](https://platform.claude.com/docs/en/about-claude/pricing)
e [roteamento regional no Bedrock](https://platform.claude.com/docs/en/build-with-claude/claude-in-amazon-bedrock).

O limite é uma proteção da aplicação a preços de lista, **não um bloqueio de faturamento
imposto pela AWS**. Impostos e condições comerciais particulares não entram nessa conta.
Contagens recebem margem conservadora antes da chamada; requisições incertas retêm
reserva e não são repetidas automaticamente. O custo v2 de US$0,3914735 é histórico,
não uma previsão de consumo para estes alvos.

Antes da inferência, o executor confere todos os arquivos contra o commit e refaz os
oito testes de isolamento. Qualquer alteração no modelo, orçamento, portão, política
lógica, código, mundo ou entrada bloqueia a execução. O diretório de execução é único:
`runs/p3/calibration/p3a_conceptual_headroom_v3`. Não se pode repeti-la apenas trocando
o diretório de saída. Erros precisam de diagnóstico e decisão explícita, não rollback
dos resultados ou sobrescrita do plano.

## Reprodução e execução separadas

Comandos **sem inferência experimental**:

```bash
PYTHONPATH=src .venv/bin/python scripts/p3_generation_audit_v3.py
PYTHONPATH=src .venv/bin/python scripts/p3_calibration_v3.py validate
PYTHONPATH=src .venv/bin/python scripts/p3_calibration_v3.py preflight
PYTHONPATH=src .venv/bin/python scripts/p3_calibration_v3.py check-commit
.venv/bin/python -m pytest -q
```

Somente o subcomando `run` faz chamadas pagas. A preparação deste congelamento não o
executou. O registro dos testes de isolamento está em
`calibration_sandbox_preflight_v3.json`; o próprio executor exige nova checagem antes
das chamadas. Os planos v1/v2 e a amostra principal permanecem preservados.
