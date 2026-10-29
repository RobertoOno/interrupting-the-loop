# S16 — contraste preservado, mas menor com mais espaço

Fechamento auditado em 08/09/2026. Execução de 07/09, 23h40–23h50,
America/Sao_Paulo. Dez provas submetidas, dez revalidadas em workspaces
novos; seis sessões encerradas por limite de saída sem submissão.

## Resultado e decisão

As 16 células planejadas terminaram, com uma requisição cada, sem falhas
técnicas, retries ou uso incerto. São **dois mundos de calibração conhecidos**,
com dois irmãos dependentes por mundo; não 16 réplicas independentes.

- **8.192 tokens/resposta:** sem ponte 0/4, com oráculo 4/4; ganho 4/4.
- **16.384 tokens/resposta:** sem ponte 2/4, com oráculo 4/4; ganho 2/4.

Os critérios prospectivos passam separadamente nos dois limites: quatro
pares válidos, oráculo >=3/4, baseline <=2/4 e ganho >=2/4. Decisão congelada:
`robust_under_tested_response_limits_prepare_transfer_not_main_admission`.

O resultado sustenta **preparar a produção e transferência de pontes**.
Não admite automaticamente a amostra principal, não demonstra invenção
e não habilita a etapa mecanística em outro modelo.

## A decomposição por família importa

No mundo de invariante, sem ponte, os dois irmãos falham em 8.192 e passam
em 16.384. As respostas bem-sucedidas consomem 9.731 e 11.608 tokens de
saída, respectivamente. Com oráculo, ambos passam nos dois limites.
Portanto, a diferença binária desta família desaparece com o limite maior.

No mundo de representação, sem ponte, os dois irmãos terminam por limite
de saída em ambos os regimes: 8.192 e 16.384 tokens, sem submissão à
ferramenta. Com oráculo, ambos passam nos dois regimes. Essa família
responde pelo contraste restante no regime de 16.384.

Logo, “robusto aos limites testados” se refere ao **portão agregado**,
não à magnitude do efeito nem a cada família. A baseline melhora e o ganho
cai pela metade. Não concluir que o modelo seja incapaz de descobrir as
rotas: em uma família ele já o fez sob o protocolo maior; na outra, sabemos
apenas que não submeteu uma solução dentro dos limites testados.

Não haverá terceiro limite, repetição seletiva ou descarte pós-resultado
da família com teto. O resultado anterior v3 (1/4 versus 4/4) permanece
intacto e não foi usado como controle contemporâneo ou somado a S16.

## Auditoria e integridade

Auditor novo, posterior à coleta, em `scripts/p3_audit_sensitivity_v1.py`.
Não altera o scorer online nem seus critérios. Reconstrói pedidos, contexto,
limites, reservas de tokens, respostas/modelo, feedback, paradas, escores
e custo; compara as entradas às materializações congeladas e o código ao
commit prospectivo `032cc01b1c8bdc8151d9be3817a1368a6fd6445b`.

Foram verificados os 199 arquivos brutos e seu inventário exato, as 30
fontes do plano, 16 preflights de isolamento e a correspondência entre
fonte submetida e salva. Todas as dez submissões foram reexecutadas em
Lean 4.33.1, em workspaces novos, com assinatura exata e a mesma allowlist
transitiva de axiomas. Todas passaram na primeira submissão original.
As seis falhas restantes não continham prova submetida para recompilar.

O agregado foi reconstruído e os critérios contados novamente por um
caminho separado, mantendo quatro pares por limite. A auditoria passou
no diretório original e na cópia arquivada, com resultados idênticos.
É nova execução do mesmo verificador Lean, não um segundo kernel
independente nem uma repetição das inferências.

Limitação de telemetria: o executor não gravou timestamps individuais de
cada requisição. O timeout é conferido nas fontes/configuração congeladas
e nos totais de sessão; não se apresenta uma cronologia interna de latência
que não foi observada. Todas as sessões terminaram abaixo de 600 s.

Arquivo bruto: `response_limit_sensitivity_evidence_v1/` (199 arquivos,
561.641 bytes). Fechamento: `response_limit_sensitivity_closure_v1/`
(81 arquivos, incluindo snapshot de 69 fontes/artefatos e ferramentas
de auditoria seladas). Manifestos conferidos antes/depois da cópia.
**Não editar o auditor, archiver ou seus testes selados após o fechamento**;
correções futuras precisam de versão e registro novos.

## Uso e custo

Uso reportado: 30.456 tokens de entrada e 103.094 de saída; cache zero.
Reconstituição decimal a preços regionais congelados: **US$3,002593**,
contra reserva operacional de US$30. A reserva foi conciliada às
23:50:43 de 07/09. Nenhuma reserva incerta permaneceu neste lote.
Estimativa de inferência por tokens, não fatura com impostos/acordos privados.

O diário local foi comparado aos recibos e copiado somente para esta rodada.
O limite AWS de US$150/dia permanece separado do RunPod; o diário local não
é um bloqueio global de faturamento. Não foi necessário recurso GPU em S16.

## Continuação elegível

Preparar um diagnóstico de produção/transferência nos mundos já expostos,
com D0, D e C2, receptores novos e controle-oráculo contemporâneo. Manter as
duas famílias e o regime maior evita escolher apenas o contraste favorável.
O desenho proposto está em
[produção/transferência de desenvolvimento](PRODUCAO_TRANSFERENCIA_DESENVOLVIMENTO_V1_RASCUNHO.md).

Antes de inferir: implementar contrato/verificador de propositor com axiomas
padrão, testar cegamento e importação das pontes, conferir pareamento de
tokens D/C2 e congelar o novo protocolo. A exigência de novidade do principal
continua aberta; esses mundos seguem inelegíveis. Não confundir uma ponte
fornecida útil com evidência de que o modelo consiga produzi-la e transferi-la.

## Reprodução offline

```bash
.venv/bin/python scripts/p3_archive_sensitivity_v1.py --verify
.venv/bin/python scripts/p3_audit_sensitivity_v1.py \
  --raw docs/p3/response_limit_sensitivity_evidence_v1 \
  --manifest docs/p3/response_limit_sensitivity_closure_v1/raw-manifest.sha256
.venv/bin/python -m pytest -q tests/test_p3_sensitivity_audit.py tests/test_p3_sensitivity_archive.py
```

56 testes sintéticos passaram antes do arquivamento. O CLI de auditoria não
constrói cliente de provedor. Não executar novamente o lançador S16.
