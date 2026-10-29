# Pareamento nativo D/C2 — regra anterior à medição

**08/09/2026.** Este documento, código, fontes e hashes dos pedidos serão
congelados em commit antes da primeira contagem deste preflight. É um
congelamento apenas da medição de comprimento, não do lote de produção/
transferência, de critérios inferenciais ou da amostra principal.

## Métrica e tolerância

Conservar as quatro fontes originais dos dois mundos CAL3 usados em S16.
Para cada fonte, contar `FILE SOURCE.md\n` seguido dos bytes UTF-8 originais,
em uma mensagem de usuário, com exatamente o sistema, ferramenta, thinking,
esforço e modelo de `build_production_request`. Contar também o mesmo pedido
contendo apenas `FILE SOURCE.md\n`. Subtrair essa contagem comum de cada uma
das quatro contagens: D e C2 são **incrementos nativos estimados de entrada**,
não a contagem lexical absoluta do arquivo, nem uso faturado.

Regra primária, fixada antes dos resultados: `2 × |D − C2| / (D + C2) ≤ 0,05`,
**em ambas as famílias**. A fronteira é inclusiva e calculada por comparação
inteira equivalente. Incremento não positivo invalida a medição. 5% é uma
tolerância operacional de comprimento, não um limiar de equivalência
estatística ou cognitiva. Evita exigir identidade exata ou permitir grandes
desbalanceamentos; não é calibrada com os valores deste preflight.

Contar ainda os seis pedidos iniciais completos D0/D/C2, renderizados pelo
materializador do novo propositor. Esses valores são diagnóstico de contexto
e orçamento: **não entram no denominador do portão**, pois a parte comum do
prompt poderia diluir um desbalanceamento das fontes. São onze pedidos,
em ordem fixa: contexto vazio; fonte D/C2 e inputs D0/D/C2 de invariante;
fonte D/C2 e inputs D0/D/C2 de representação. Não há réplicas escolhidas,
média entre tokenizadores ou comparação por outro modelo.

## Interface, evidências e decisões

SDK Anthropic **1.4.0**, cliente `AnthropicBedrockMantle`, Opus 5, perfil `main-account`, `us-east-1`,
endpoint regional explícito `bedrock-mantle.us-east-1.api.aws/anthropic`,
operação `/v1/messages/count_tokens`, retries zero e até 30 s por pedido.
O corpo usa o mesmo construtor da sessão propositora, sem `max_tokens`;
não chama `messages.create`, não gera provas nem cria cache de prompts.
O diretório de evidências é único; uma tentativa anterior, mesmo incompleta,
impede outra execução. Erro preserva pedidos, resposta/erro bruto disponível
e sequência, sem fallback para inferência, tokenizador local ou outro serviço.

Plano contém hashes do código/contrato/política, mundos e pedidos. O executor
confere os bytes contra o commit antes de construir o cliente. Registra commit,
SDK/ambiente, endpoint, horários, pedidos exatos, bytes JSON das respostas e
identificadores do provedor; não registra credenciais ou cabeçalhos de auth.
Manifesto permite conferir a integridade; auditor local reconstrói os valores
e a decisão sem chamadas. Testes usam clientes explicitamente sintéticos.

Se ambos passam: fechar somente o controle de comprimento e continuar matriz,
análise, auditoria e admissão prospectiva do lote. Se algum falha: registrar
o desbalanceamento e revisar fontes em versão própria, antes de respostas
experimentais; não mudar tolerância, preencher automaticamente com texto,
reescrever fontes históricas ou retirar a família. Erro técnico não é falha
de pareamento nem resultado matemático. Nenhuma saída admite principal,
P3B ou mecanismos automaticamente.

As fontes já foram verificadas em Lean. Invariante relevante conserva forma
quadrática e sham conserva soma; representação relevante usa ação compatível
com a relação-alvo e sham usa translações comutativas. O sham ainda oferece
métodos genéricos úteis. Comprimento semelhante não iguala conteúdo matemático,
informação transferível ou dificuldade, e não prova que a rota é inédita.
Não se modifica o [registro histórico das fontes](FONTES_E_GERADOR_CONCEITUAL_V3.md).

## Referências da interface e preços

A documentação descreve contagem como estimativa de entrada; ela pode diferir
ligeiramente do uso reportado na inferência e não usa cache. A operação de
contagem é apresentada como gratuita, com limite próprio de requisições.
[Contagem de tokens — documentação Claude](https://platform.claude.com/docs/en/build-with-claude/token-counting).
Usamos a integração AWS gerida, não Claude Platform on AWS/Marketplace:
[Claude em Amazon Bedrock, Opus 4.7 e posteriores](https://platform.claude.com/docs/en/build-with-claude/claude-in-amazon-bedrock).

Conferência de preços em 08/09: Opus 5, US$5/25 por milhão de entrada/saída,
mais 10% regional: US$5,50/27,50. Mantém-se a reserva nominal proposta de
US$1,65 por sessão do futuro lote, máximo 26/US$42,90 e teto operacional
US$50, sujeito à conciliação do limite AWS US$150/dia. Os tokens deste
contador não são consumo de inferência a lançar como se fossem respostas.
[Preços oficiais](https://platform.claude.com/docs/en/about-claude/pricing).

## Reprodução

`PYTHONPATH=src .venv/bin/python scripts/p3_source_matching_v1.py prepare`
cria o plano uma única vez; `validate` verifica o estado local. Publicar e
validar testes/CI antes de `run`. Depois, `audit` apenas lê/reconstrói as
evidências. Não alterar este contrato congelado para fazê-lo passar.
