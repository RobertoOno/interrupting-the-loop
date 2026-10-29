# Programa 3A — resultado da calibração de headroom v1

**Executado em 2026-09-04. Material descartável; não pertence à amostra principal.**

## Resultado

As oito sessões congeladas em `calibration_headroom_plan_v1.json` terminaram sem falha de
infraestrutura. Depois da correção auditável do scorer, sem repetir qualquer chamada de modelo:

- baseline sem ponte: 3/4 alvos resolvidos;
- ponte-oráculo: 4/4 alvos resolvidos;
- ganho pareado: 1/4, média `+0,25`;
- gate: **não passou**. A regra exigia baseline no máximo 2/4 e ganho em pelo menos 2/4.

Por par, T1/G1, T1/G2 e T2/G2 foram resolvidos com e sem ponte. Somente T2/G1 separou as
condições: o oráculo passou; a baseline produziu uma prova que compilava, mas cuja auditoria
transitiva reportou dependência de `propext`, fora da allowlist axiomática.

Isso não é evidência contra a hipótese de transferência. É evidência de que os dois primeiros
fixtures não oferecem headroom suficiente para medir o efeito com `gpt-5.6-sol` em esforço
`high`: o agente rederivou localmente a ponte em T1 e expandiu as reescritas em T2. Conforme a
regra anterior aos dados, o próximo passo é construir mundos de calibração descartáveis mais
difíceis, mantendo o modelo, e não executar propositores nem gerar a amostra principal.

## Correção do scorer

A primeira leitura automática marcou duas soluções válidas como negativas porque procurava
`evaluation_solution` somente no namespace raiz. Os agentes haviam declarado os teoremas no
namespace exato do mundo. O erro afetou uma baseline e um oráculo, portanto a primeira contagem
2/4 versus 3/4 é inválida.

O verificador foi corrigido para aceitar somente duas localizações: raiz ou namespace exato do
mundo, mantendo idênticos o tipo congelado, imports, scanner, compilação e auditoria de axiomas.
Os oito arquivos originais foram rechecados; houve zero nova sessão de modelo. A leitura inicial
foi preservada em `calibration_headroom_results_v1_initial_invalid.json`, e o resultado corrigido
em `calibration_headroom_results_v1.json` identifica célula por célula quando houve rescore.

## Proveniência e custo observado

- Modelo: `gpt-5.6-sol`; esforço `high`; Codex CLI 0.153.1.
- Tempo somado das sessões: 379,86 s; duas células no máximo em paralelo.
- Telemetria emitida pelo cliente: 585.286 tokens de entrada, dos quais 422.912 em cache;
  10.819 de saída, dos quais 2.686 de raciocínio.
- Artefatos brutos: `runs/p3/calibration/p3a_calibration_headroom_v1/` (ignorado pelo Git).
- Manifesto rastreado dos artefatos brutos: `calibration_headroom_raw_manifest_v1.sha256`.
- Nenhuma GPU, pod ou sessão propositora foi usada.
