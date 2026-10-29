# Contrato do plano executável — v1

`transfer_execution_plan_v1.py` define e valida a especificação operacional
que sucederá o blueprint. **O arquivo final do plano ainda não foi criado.**
O construtor bloqueia enquanto faltarem o lançador experimental, seu auditor
independente, o comando de execução e os respectivos testes. Arquivos vazios
ou testes de política não constituem implementação validada.

O blueprint permanece imutável. A especificação própria fixa sua referência,
os dois mundos/26 posições, orçamento US$50 e limite AWS US$150/dia São Paulo,
mesmo regime de modelo, seleção e controles contemporâneos. Fixa também
allowlists explícitas de revisor/conciliador, endpoint/SDK/zero retries,
política de conteúdo e sequência de revisão/barreira.

O diretório canônico é `/Users/robertoonofilho/wrk/creative-machine`;
run ID `p3a_transfer_development_v1`, registro `runs/worker-claims`, diário
compartilhado `runs/aws-budget/claude_daily.jsonl` e saída
`runs/p3a_transfer_development_v1`. Não existe opção de trocar ID/cópia/saída
para repetir uma coleta interrompida. O diretório da outra cópia permanece intocado.

## Fontes, publicação e CI

O inventário inclui fontes do programa formal, dependências históricas,
testes P3, diário AWS, workflow/dependências e evidências do pareamento nativo
já encerrado. Não inclui arquivos pessoais nem os checkpoints de continuidade
CLAUDE/PLANO. Comparar o plano com a reconstrução detecta drift mesmo se alguém
fornecer um hash novo para uma política alterada.

O commit das fontes/testes vem **antes** da publicação do JSON do plano,
evitando dependência circular de hashes. A conferência Git exige esse commit
como ancestral de HEAD, bytes iguais no commit de fontes, em HEAD e no disco,
além do plano exato publicado em HEAD. Não faz commit, push, reserva ou chamada.

A observação de CI reúne respostas separadas dos endpoints GitHub de run e
jobs. Valida repositório, workflow, evento push, SHA completo, conclusão e os
três jobs obrigatórios. Lista parcial/paginada, job duplicado, CI de outro SHA,
falha ou execução em andamento não aprovam as fontes. O host deve obter esses
dados de leituras GitHub autenticadas e preservá-los: um JSON estruturalmente
correto não autentica sua própria origem.

## Admissão ainda separada

`FROZEN_SPEC_NOT_ADMITTED` descreve a especificação, não libera inferência.
Faltam integração experimental do lote e perfil de auditoria, preflight real,
congelamento/publicação/CI das fontes completas e conciliação financeira
efetiva. Flags de autenticação do provedor, inferência/principal/mecanismos
permanecem falsas. Os testes de contrato usam inventários/CI fictícios
identificados; não são recibos reais nem autorização experimental.

Ao retomar, continuar os componentes faltantes; não gerar um plano com stubs,
repetir o pareamento de tokens ou promover o ensaio sintético por renomeação.

Validação local: **46 testes de contrato**, incluindo publicação em dois
commits Git reais de um repositório temporário, fontes/HEAD/disco divergentes,
ausência de componentes, deriva de política e CI incompleto/falso/pendente.
Com transporte e auditoria de vínculos: **98 passed em 7,10 s**. Nenhum JSON
de plano final foi criado; blueprint SHA original reconferido.
