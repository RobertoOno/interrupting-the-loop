# Programa 3A — resultado da calibração conceitual v3

**ENCERRADA EM 05/09/2026. PORTÃO CONGELADO PASSOU.**

Resultado: baseline 1/4, ponte-oráculo 4/4, ganho líquido pareado 3/4. As oito sessões
foram válidas, quatro pares completos; zero falhas de infraestrutura e zero chamadas
incertas. O resultado satisfaz os quatro critérios pré-especificados, sem mudar scorer,
orçamento, modelo, mundos, ordem ou regra de decisão depois de observar as saídas.

**Ressalva central:** as três sessões sem solução terminaram no limite de 8.192 tokens
da primeira resposta, antes de qualquer submissão de prova. O contraste é ganho de
sucesso **sob este protocolo limitado**, não demonstração de que o modelo não consegue
achar a rota com uma resposta mais longa ou em outro regime de interação.

## Protocolo e proveniência

Plano `calibration_conceptual_plan_v3.json`, congelado no commit `7134d8b`. Executado
sob `6d159a5`, que acrescentou somente o controle diário externo ao protocolo; os
arquivos congelados continuaram byte-idênticos. O executor conferiu cada arquivo
contra o commit, as oito entradas completas contra seus hashes e o isolamento antes
de construir o cliente. Modelo reportado em todas as respostas: `claude-opus-5`.

Janela do diário: 05/09, 00:25:50–00:30:39, `America/Sao_Paulo` (inclui preflight e
finalização). Oito sessões novas, no máximo duas simultâneas. Nove requisições de
inferência no total; chamadas de contagem de tokens não são requisições de inferência.
Nenhum pod, propositor D/D0/C2, piloto principal, P3B ou módulo de estados internos.

Mantidos da v2: esforço high, ferramenta única, 12 chamadas máximas por sessão,
600 s por sessão, 120 s por requisição, 200 mil tokens cumulativos de entrada,
20 mil de saída, 8.192 de saída por requisição, axiomas padrão do Lean. O plano
fixou que uma resposta sem chamada de ferramenta termina a sessão; `max_tokens`
sem submissão é `output_limit`, um insucesso válido, não falha de infraestrutura.

## Resultado por mundo

**Invariante, `CAL3_I_E87C49876088749B`:** baseline 1/2, oráculo 2/2, ganho 1/2.
O irmão 1 sem ponte atingiu `max_tokens` sem submissão. No irmão 2, o modelo definiu
um invariante quadrático com sinal oposto ao do oráculo, provou sua preservação em
um passo e em alcançabilidade, e fechou o alvo. A primeira submissão teve um erro
de sintaxe na alternativa `refl`; a segunda foi aceita. Não se trata de prova
rejeitada por matemática nem evidência de inacessibilidade geral dessa família.

**Representação, `CAL3_R_F76437525B190ECB`:** baseline 0/2, oráculo 2/2, ganho 2/2.
Ambas as sessões sem ponte atingiram `max_tokens` sem submissão. As duas sessões
com ponte aplicaram `oracle_bridge` aos contextos e à testemunha inteira, fechando
a contradição por computação decidível.

Todas as quatro soluções com ponte usam explicitamente `oracle_bridge`; todas
foram aceitas na primeira submissão. As cinco provas finais aceitas passaram
novamente pelo verificador em workspaces novos, com assinatura exata e auditoria
axiomática. Não houve mudança de classificação na rechecagem.

## O que o truncamento permite — e não permite — concluir

As três respostas truncadas reportam exatamente 8.192 tokens de saída, `stop_reason`
igual a `max_tokens`, somente um bloco `thinking` com texto vazio, nenhum `tool_use`
e nenhuma avaliação Lean. Não há texto de raciocínio observável para classificar se
o modelo já havia escolhido o intermediário ou se ainda estava procurando por ele.
Nenhuma tentativa parcial foi resgatada ou transformada em sucesso por inspeção humana.

Embora cada sessão pudesse acumular até 20 mil tokens de saída, o executor não
continua automaticamente após uma resposta sem ferramenta. Portanto o teto por
resposta ficou ativo antes do teto cumulativo. Esse comportamento já estava no
protocolo congelado: não invalida nem autoriza reclassificar retrospectivamente
o portão, mas limita a generalização e exige uma checagem de robustez antes da escala.

Não se reporta teste de significância: são **dois mundos**, quatro pares de irmãos
dependentes e uma sessão por condição/alvo. O ganho observado não deve ser tratado
como quatro mundos independentes, estimativa populacional precisa ou comparação de
modelos com v1/v2. As famílias são conhecidas; o resultado não testa novidade
estrutural, ausência de prior, invenção ou transferência de fontes.

## Uso e custo

Uso reportado e conferido diretamente nas nove respostas: 24.415 tokens de entrada,
44.475 de saída, criação/leitura de cache zero. Custo estimado pelos preços regionais
congelados: **US$1,357345**, antes de impostos ou condições comerciais particulares.
É uma estimativa por uso, não leitura da fatura. Tarifas e fontes oficiais estão no
plano e em `CALIBRACAO_CONCEITUAL_V3.md`.

Em 05/09 o Roberto autorizou continuidade com limite de US$150/dia para Claude/AWS.
A rodada manteve seu teto de US$15: o diário local reservou esse valor antes de iniciar
e conciliou a reserva para US$1,357345 após concluir sem incertezas. É o consumo de
inferência iniciado nesta sessão nesse dia, não o total certificado da conta inteira.
Consumo de outros agentes precisa ser conciliado à parte; não há trava AWS global.
Política: `AWS_LIMITE_DIARIO.md`; recibo arquivado: `aws_daily_usage_2026-09-05_v3.jsonl`.

## Evidência e reprodução offline

- `calibration_conceptual_evidence_v3/`: cópia integral e verbatim dos 92 arquivos
  brutos, incluindo plano, proveniência, entradas, respostas, verificações,
  workspaces, cinco provas finais, oito resultados e agregado `summary.json`.
- `calibration_conceptual_raw_manifest_v3.sha256`: manifesto original da execução.
- `calibration_conceptual_recheck_v3.json`: inventário e todos os hashes conferidos,
  uso conciliado com respostas, agregado recomposto e cinco provas rechecadas.
- `scripts/p3_recheck_conceptual_v3.py`: reprodução dessas verificações sem AWS.

```bash
PYTHONPATH=src .venv/bin/python scripts/p3_recheck_conceptual_v3.py
PYTHONPATH=src .venv/bin/python scripts/p3_calibration_v3.py validate
PYTHONPATH=src .venv/bin/python scripts/p3_bedrock.py validate
.venv/bin/python -m pytest -q
```

O diretório de execução e o diário impedem nova invocação automática desta rodada.
Nenhum arquivo bruto, mundo, resultado v1/v2 ou alvo cego foi alterado.
Após o fechamento, o invólucro de orçamento também passou a recusar uma execução se
o agregado já arquivado estiver presente, inclusive em clone sem a pasta `runs/`.
É uma proteção operacional contra repetição, sem mudança no executor científico.

Validação final do repositório: **258 passed, 6 skipped**, incluindo 14 testes do
controle diário e do invólucro (concorrência, limite, virada de dia, reservas incertas
e bloqueio de rodada já arquivada). Os validadores dos planos v2/v3 continuam passando.

## Encaminhamento

Preservar o primeiro contraste positivo deste instrumento. Antes de propositores ou
piloto maior, pré-registrar uma sensibilidade separada ao limite por resposta, com
ambos os braços e sessões novas: não repetir somente os três insucessos nem juntar
novas saídas ao agregado original. Proposta revisável em
`SENSIBILIDADE_LIMITE_RESPOSTA_V3_RASCUNHO.md`, ainda sem execução ou congelamento.
Mesmo se robusto, a questão de novidade estrutural do principal permanece aberta.
