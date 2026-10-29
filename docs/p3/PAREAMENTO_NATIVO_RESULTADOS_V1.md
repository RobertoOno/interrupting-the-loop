# Pareamento nativo D/C2 — encerrado

**08/09/2026.** Ambas as famílias passaram o controle de comprimento sem
alteração das fontes. A tolerância simétrica de 5%, seu código e os hashes
dos pedidos foram publicados **antes** da medição, no commit
`ab9573a617e646e0098795b14324812170547837`.

## Resultados e escopo

Incrementos nativos estimados acima do mesmo contexto vazio:

- **Invariante:** D=689, C2=691 tokens; diferença simétrica **0,289855%**.
- **Representação:** D=1.328, C2=1.324 tokens; diferença **0,301659%**.

Contexto vazio: 1.005 tokens. O portão usa `2×|D−C2|/(D+C2)≤0,05`, não
os totais completos de prompt. Estes últimos foram contados separadamente:
invariante D0/D/C2 = 2.226/2.926/2.928; representação = 1.967/3.306/3.302.
São diagnósticos de entrada, não tokens de saída ou uso faturado.

As onze chamadas nativas terminaram normalmente, sem retry, em 3,396 s,
entre 06:44:20 e 06:44:23 UTC (03:44 em São Paulo). Cliente real
`AnthropicBedrockMantle`, SDK 1.4.0, Opus 5, endpoint regional us-east-1,
perfil `main-account`. Nenhuma fonte foi preenchida, encurtada, reformulada
ou substituída em função da contagem.

**Conclusão estrita:** o pareamento de comprimento está resolvido para estas
fontes e esta interface. Isso não iguala informação matemática, dificuldade,
conteúdo transferível ou grau de reconhecimento. Não mede produção/uso de
ponte, não é resultado comportamental e não confirma invenção. A semântica
dos controles permanece a descrita no registro histórico das fontes.

## Rastro e verificação

- [Regra prospectiva](PAREAMENTO_NATIVO_FONTES_V1.md) e
  [plano por hashes](source_matching_plan_v1.json).
- [Resultado](source_matching_evidence_v1/result.json),
  [proveniência](source_matching_evidence_v1/provenance.json),
  [eventos](source_matching_evidence_v1/events.jsonl) e
  [manifesto](source_matching_evidence_v1/manifest.json).
- 26 arquivos no pacote: onze pedidos exatos, onze respostas JSON em bytes
  originais, proveniência, sequência, resultado e manifesto. Não contém
  credenciais ou cabeçalhos de autenticação.
- `PYTHONPATH=src .venv/bin/python scripts/p3_source_matching_v1.py audit`
  reconstruiu os onze valores, os incrementos e a decisão, conferindo
  interfaces, hashes, inventário e eventos. Não repetir `run`.

Validação anterior à medição: 33 testes novos, incluindo transporte simulado
com o SDK real; 167 testes conjuntos com contrato/executor aprovados em
34,17 s. [CI do congelamento](https://github.com/RobertoOno/creative-machine/actions/runs/34195753681)
aprovado: **1593 passed/43 skipped em 118,91 s**. No CI, integração com SDK
ausente é pulada explicitamente; contagens sintéticas dos testes não são
as medições acima. Código, política, plano e testes deste preflight ficam
preservados; não alterar arquivos congelados para futuras necessidades.

## Continuação

Fecha-se somente este controle. O diagnóstico de até 26 sessões segue em
preparação, nos mesmos dois mundos expostos e com controles novos. O
[rascunho de análise e decisões](ANALISE_TRANSFERENCIA_DESENVOLVIMENTO_V1_RASCUNHO.md)
explicita integridade/completude, portão contemporâneo B/O, U medido versus
zero convencionado de produção e decisões diante de transferência positiva
ou de sua ausência. Ainda precisa de código/testes, matriz/ordem e revisão.

Auditor de rastros, política de conteúdo/cegamento da ponte, adaptador do
receptor, orquestração de reservas/admissão e preflight/CI também permanecem
antes do congelamento do lote. Não refazer S16/W8 nem reutilizá-los como
controles. Principal, confirmação/replicação, P3B e mecanismos continuam
separados; seguir o plano não exige fabricar contraste ou apressar conclusão.
