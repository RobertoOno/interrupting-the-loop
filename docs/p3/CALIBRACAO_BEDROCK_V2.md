# Programa 3A — calibração Bedrock v2

Estado: oito células concluídas em 2026-09-04; portão não passou por teto da baseline.
Plano congelado em `calibration_bedrock_plan_v2.json`, no commit
`bbc96fa315671b9694ae3ef6eb440fcf14ad46e7`, anterior à primeira inferência.

## Objetivo e limites

Medir o portão do instrumento em dois novos mundos descartáveis: quatro alvos irmãos,
cada um com e sem ponte-oráculo. Sem propositores, sem P3A principal, sem P3B e sem pod.
P3A/P3B permanecem o eixo da pesquisa; o módulo de mecanismos internos é independente.

O gate exige quatro pares válidos, oráculo ≥3/4, baseline ≤2/4 e ganho líquido ≥2/4.
Nenhum agregado foi usado para mudar prompts, orçamento ou mundos dentro da bateria.

## Protocolo

- Modelo `anthropic.claude-opus-5`, esforço high, Bedrock Mantle, perfil AWS main-account,
  região us-east-1; SDK anthropic 1.4.0. Sem fallback ou repetição automática.
- Oito conversas novas, duas simultâneas, com apenas os arquivos de cada avaliador.
- Uma ferramenta: envio completo de Solution.lean e feedback do Lean. Sucesso verificado
  encerra a sessão. O modelo não recebe shell, ferramentas de leitura ou busca externa.
- Até 12 chamadas e 600 segundos por sessão; máximo de 8192 tokens de saída por chamada,
  20.000 por sessão e 200.000 tokens de entrada reservados cumulativamente.
- Reserva de entrada: contagem prévia gratuita ×1,10 +1024 tokens. Uma chamada incerta
  mantém a reserva inteira. Limite nominal da bateria: US$15, com US$13,20 de reserva
  máxima de tokens a preços regionais publicados, antes de impostos.
- A cobrança estimada usa os tokens reportados, distinguindo entrada, saída e cache;
  não é uma consulta da fatura nem um limite imposto pela AWS.
- Axiomas padrão admitidos: propext, Quot.sound, Classical.choice; novos axiomas e
  sorryAx proibidos. A política zero-axiomas original de v1 permanece histórica.

## Mundos e verificações anteriores às chamadas

T1: `CAL2_T1_6A99B5D87E404DF3`, modos indexados e composição de rotas; fontes 649/649 palavras.
T2: `CAL2_T2_9E9C8F0211D9DA4F`, termos com vínculo e transporte entre ambientes relacionados;
fontes 503/503 palavras. Sementes e hashes completos estão no plano.

Ambos passaram compilação de base/alvos/oráculo, auditoria de axiomas, testemunha de
não vacuidade, compilação de ambas as fontes, adaptador relevante e rejeição intencional
do sham e das automações fixas. Oito workspaces passaram bloqueio de leitura do oculto,
bloqueio de rede e compilação Lean. O verificador recompila somente fontes permitidas,
sem importar caches ou artefatos extras.

Testes: 161 passed, 6 skipped; os testes de orçamento/protocolo usam respostas simuladas,
sem inferência. O endpoint gratuito de contagem aceitou o formato exato da requisição
com ferramentas e raciocínio: primeira entrada com 2713 tokens estimados.

V2 muda modelo, interface, mundos e política lógica; não é comparação de modelos com v1.

## Fontes de preço e protocolo

- https://platform.claude.com/docs/en/about-claude/pricing
- https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-opus-5.html
- https://platform.claude.com/docs/en/build-with-claude/token-counting

## Resultado

Oito células válidas, quatro pares completos, sem falhas de infraestrutura, chamadas incertas
ou repetição. Cada célula terminou com uma única chamada ao modelo e uma prova aceita pelo
Lean na primeira submissão, sob a política axiomática congelada.

- Sem ponte: 4/4 alvos resolvidos.
- Com ponte-oráculo: 4/4 alvos resolvidos.
- Ganho líquido: 0/4. **Portão não passou.** O oráculo passou seu limiar, mas baseline e
  ganho não satisfizeram os limiares pré-especificados.
- Uso reportado: 21.862 tokens de entrada e 9.863 de saída; nenhum token de cache.
- Custo estimado: **US$0,3914735**, calculado com US$5,50/milhão de entrada e
  US$27,50/milhão de saída. É estimativa pelos tokens, antes de impostos/descontos privados,
  não valor consultado na fatura AWS. Nenhum pod foi criado.

Os dois mundos v2 estão encerrados e permanentemente excluídos da amostra principal,
assim como os dois mundos v1. Nenhum propositor nem sessão principal foi executado.
Esta calibração não testa H2 nem refuta transferência/invenção: mostra falta de margem
para medir ganho de sucesso nestes dois mundos, neste modelo e protocolo.

## Inspeção das provas após o fechamento

Nas quatro células sem ponte, a solução cria espontaneamente um lema auxiliar reutilizável:

- T1: `sound`/`sound_aux` generaliza modos e estados; indução estrutural cobre as arestas,
  a parada e as composições. O alvo é então uma aplicação curta desse lema.
- T2: `hom_eval` generaliza termo e ambiente; o caso de vínculo usa igualdade funcional
  dos ambientes estendidos. Essa rota usa um ambiente canônico mapeado, diferentemente
  da formulação do oráculo com dois ambientes relacionados, e também é válida.

A leitura pós-resultado é que modos, índices e vínculo aumentaram a elaboração da prova,
mas conservaram um esquema de indução/homomorfismo reconhecível nas definições. Isto é
uma interpretação do código entregue, não uma medida de estados internos do modelo.

Descritivamente, as células sem ponte consumiram 8.884 tokens de saída e as com oráculo,
979. Não se troca o desfecho por economia de tokens após ver os dados: são apenas quatro
pares de uma calibração, sem desenho confirmatório de eficiência. O gate permanece falho.
Como modelo, interface, mundos e política lógica mudaram de v1 para v2, não se atribui
a diferença entre calibrações a superioridade de um modelo.

## Decisão e próximo desenho

Não iniciar as até 104 sessões principais, enfraquecer o modelo ou reduzir retroativamente
seu orçamento para obter contraste. Não há indicação, nesta bateria, de que mais capacidade
ou crédito resolva o gargalo do instrumento.

Antes de outra calibração paga, revisar o gerador em trabalho local:

1. Especificar a escolha de invariante ou representação que o problema exige, distinguindo-a
   da execução de uma indução já sugerida pelo tipo de dados. Acrescentar construtores ou
   tamanho, isoladamente, não é critério de dificuldade.
2. Construir um protótipo em que o intermediário seja demonstrável a partir da base e útil
   em vários irmãos, mas sua formulação não esteja fornecida pela assinatura do alvo.
   Não trocar descoberta por nomes arbitrários a adivinhar, metaprogramação ou inconsistência.
3. Rever, antes de conectar o modelo, a aplicação curta do oráculo, as rotas diretas conhecidas,
   a não vacuidade e a fidelidade da fonte/sham. Manter os portões e registrar também falhas.
4. Só então congelar novos fixtures descartáveis, protocolo e orçamento em outro commit.
   Manter a amostra principal independente; não reutilizar estes alvos nem selecionar apenas
   mundos que produziram o efeito desejado para compor o resultado principal.

P3A/P3B permanecem separados e preservados. O módulo de mecanismos internos continua com
modelo instrumentável, protocolo e orçamento próprios; não substitui a validação comportamental.

## Evidência e reprodução

- `calibration_bedrock_results_v2.json`: cópia exata do agregado da execução.
- `calibration_bedrock_evidence_v2/`: cópias das oito provas finais e dos respectivos
  `result.json`, incluindo auditoria Lean, uso e modelo reportado. Sem raciocínio privado
  do modelo ou credenciais.
- `calibration_bedrock_raw_manifest_v2.sha256`: manifesto integral de 95 arquivos, verificado
  após a execução. Seus caminhos são relativos ao diretório bruto, não a esta pasta.
- Brutos locais, fora do Git: `runs/p3/calibration/p3a_bedrock_headroom_v2/`.
  Incluem plano, proveniência, entradas, respostas, provas e resultados. O manifesto
  não substitui esses arquivos nem torna as chamadas estocásticas reproduzíveis por si só.

As provas arquivadas podem ser rechecadas sem AWS, no ambiente Mac/Lean congelado:

```bash
PYTHONPATH=src .venv/bin/python scripts/p3_recheck_bedrock_v2.py
```

O script confere hashes, materializa cada célula a partir do mundo e condição do plano,
copia sua `Solution.lean` e chama `verify_evaluator_solution` com os axiomas padrão
permitidos e o mesmo sandbox. Os arquivos-base/oráculo estão versionados em
`worlds/calibration/`. Não usa os brutos em `runs/` nem importa cliente de modelo.
Mudanças de implementação ou do binário sandbox exigem recuperar o ambiente congelado,
não sobrescrever os hashes históricos.

Rechecagem pós-arquivamento executada: oito provas recompiladas e aceitas, coincidindo
com os oito resultados originais; zero chamadas de modelo.
